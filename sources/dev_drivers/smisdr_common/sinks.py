"""
smisdr_common/sinks.py
======================
Output stages for smiSDR / parlioSDR (no Qt).  A sink takes blocks of baseband I/Q as float32
(interleaved, +-1.0 = full scale) and gets them to the device:

    IqSink   smisdr_iq*   -> tagged 14 bit words with in-band signalling, paced, TCP; DUC in the FPGA
    RawSink  smisdr_raw*  -> int16 I/Q into cohi_native_upconverter -> RF samples -> TCP

Both are used by the file players (smisdr_iq, smisdr_raw: per-file worker) and by the live
drivers (smisdr_iq_universal, smisdr_raw_universal), where the worker of stemlab_universal
produces the signal (file + audio carriers) and writes it with ``sink.sendall(float32 array)``,
exactly as it does to the STEMLAB socket.

Common behaviour
  open(center, rate)   configure + connect; kept as it is if the parameters did not change
  send_iq / sendall    blocks (blocking; real-time pacing happens here / in the upconverter)
  send_silence         zero I/Q
  close(graceful)      graceful: leave the DAC at zero;  abort(): any thread, unblocks a send
  idle silence         (live drivers) if the producer is silent for > 0.3 s (pause, long
                       computation), zeros are sent so that the DAC / DUC does not hold the
                       last sample, which would be an unmodulated carrier
"""
import logging
import threading
import time

import numpy as np

from dev_drivers.smisdr_common import modes, net, protocol, rawlink

logger = logging.getLogger("smisdr")

IDLE_AFTER_S = 0.30         # producer silent for this long -> send silence
IDLE_BLOCK_S = 0.05         # duration of one silence block
IDLE_POLL_S = 0.02
CLOSE_SILENCE_FRAMES = 256


LEVEL_REPORT_S = 5.0        # level line in the log at most this often
CLIP_WARN_FRACTION = 0.001  # more than 0.1 % of the samples clipped: warning


class LevelMonitor:
    """Peak level, clipping and limiter action of what is sent, reported in the log every few
    seconds (digital overload is otherwise invisible: the stream looks fine at the device, the
    signal is not). ``ceiling`` is the value that corresponds to the full scale of the DAC stage."""

    def __init__(self, name, ceiling=1.0):
        self.name = name
        self.ceiling = float(ceiling)
        self.peak = 0.0                             # peak of the report interval, relative to ceiling
        self._clipped = 0
        self._total = 0
        self._next_report = time.monotonic() + LEVEL_REPORT_S

    def update(self, x, limiter=None):
        """x: what is sent (interleaved float32), limiter: the PeakLimiter in front, if any"""
        scaled = np.abs(np.asarray(x, dtype=np.float32)) / np.float32(self.ceiling)
        if len(scaled):
            self.peak = max(self.peak, float(np.max(scaled)))
            self._clipped += int(np.count_nonzero(scaled > 1.0001))
            self._total += len(scaled)
        now = time.monotonic()
        if now >= self._next_report:
            self._next_report = now + LEVEL_REPORT_S
            self.report(limiter)

    def report(self, limiter=None):
        if not self._total:
            return
        fraction = self._clipped / self._total
        text = "%s: peak %.0f %% of full scale, %d of %d samples clipped (%.2f %%)" % (
            self.name, self.peak * 100.0, self._clipped, self._total, fraction * 100.0)
        if limiter is not None and limiter.min_gain < 0.999:
            text += ", limiter reduced the level by up to %.1f dB" % (-20.0 * np.log10(limiter.min_gain))
        if limiter is not None:
            limiter.reset_stats()
        if fraction > CLIP_WARN_FRACTION:
            logger.warning(text + " - overdriven: lower the gain (slider / AGC target)")
        else:
            logger.info(text)
        self.peak = 0.0
        self._clipped = self._total = 0


class SinkError(Exception):
    """a problem that is worth an error box; the message is meant for the user"""


class _SinkBase:
    def __init__(self, host, cfg, idle_silence=False):
        self.host = host
        self.cfg = cfg
        self.params = None
        self._idle_enabled = idle_silence
        self._send_lock = threading.Lock()
        self._last_send = time.monotonic()
        self._idle_thread = None
        self._idle_stop = threading.Event()
        self._rate = None
        self.level = None
        self.limiter = None

    # ---- to be provided -----------------------------------------------------------
    @property
    def alive(self):
        raise NotImplementedError

    def open(self, center_freq, sample_rate):
        raise NotImplementedError

    def _transmit(self, x):
        """one block of shaped float32 I/Q; raises OSError"""
        raise NotImplementedError

    def _transmit_silence(self, frames):
        raise NotImplementedError

    def _close(self, graceful):
        raise NotImplementedError

    def abort(self):
        raise NotImplementedError

    # ---- common --------------------------------------------------------------------
    def _shape(self, iq, gain):
        """gain and peak limiter -> interleaved float32 that fits the DAC stage"""
        if self.limiter is not None:
            x = self.limiter.process(iq, gain)
        else:
            x = protocol._finite(iq) * np.float32(gain)
        if self.level is not None:
            self.level.update(x, self.limiter)
        return x

    def send_iq(self, iq, gain=1.0):
        with self._send_lock:
            self._transmit(self._shape(iq, gain))
            self._last_send = time.monotonic()

    def sendall(self, data):
        """interface of a socket for the worker of stemlab_universal: float32 I/Q, gain applied"""
        self.send_iq(np.asarray(data, dtype=np.float32), 1.0)

    send = sendall

    def send_silence(self, frames):
        with self._send_lock:
            self._transmit_silence(frames)
            self._last_send = time.monotonic()

    def close(self, graceful=True):
        self._stop_idle()
        self._close(graceful)

    def _start_idle(self):
        if not self._idle_enabled or self._idle_thread is not None:
            return
        self._idle_stop.clear()
        self._last_send = time.monotonic()
        self._idle_thread = threading.Thread(target=self._idle_loop, name="smisdr-idle", daemon=True)
        self._idle_thread.start()

    def _stop_idle(self):
        self._idle_stop.set()
        thread, self._idle_thread = self._idle_thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _idle_loop(self):
        while not self._idle_stop.wait(IDLE_POLL_S):
            if not self.alive or self._rate is None:
                continue
            if time.monotonic() - self._last_send < IDLE_AFTER_S:
                continue
            if not self._send_lock.acquire(blocking=False):
                continue                                    # the producer is sending right now
            try:
                self._transmit_silence(max(1, int(self._rate * IDLE_BLOCK_S)))
                self._last_send = time.monotonic() - IDLE_AFTER_S   # keep idling, do not reset the timer
            except OSError:
                pass                                        # the producer finds out on its next send
            finally:
                self._send_lock.release()


# ======================================================================================
class IqSink(_SinkBase):
    """DUC gateware: baseband I/Q with in-band signalling"""

    def __init__(self, host, cfg, idle_silence=False):
        super().__init__(host, cfg, idle_silence)
        self._sock = None
        self._pacer = None
        self._failed = False
        self._lock = threading.Lock()

    @property
    def alive(self):
        return self._sock is not None and not self._failed

    def open(self, center_freq, sample_rate):
        cfg, host = self.cfg, self.host
        nominal = protocol.supported_iq_rate(sample_rate)
        if nominal is None:
            raise SinkError("sample rate {} Hz of the recording is not supported by the DUC gateware "
                            "(only 250000, 500000 and 1250000 Hz). Please use the 'Resample' tab to "
                            "create a playable file.".format(int(sample_rate)))
        if self.alive and self.params == (nominal, center_freq):
            logger.info("smisdr_iq: same frequency / sample rate as the open connection - kept")
            return
        self._close(graceful=True)
        problem = protocol.iq_edge_problem(center_freq, nominal, cfg["ref_clock"])
        if problem:
            raise SinkError(problem)
        try:
            init_bytes = protocol.build_init_sequence(center_freq, nominal, cfg["ref_clock"])
        except ValueError as exc:
            raise SinkError(str(exc))

        if cfg["control_port"] is not None:
            soft_duc = self._prepare_mode()
            if not soft_duc:                      # the soft DUC ignores width and takes the rate from 'R'
                ok = (net.send_control_command(host, cfg["control_port"], "width 16\n")
                      and net.send_control_command(host, cfg["control_port"],
                                                   protocol.format_iq_bus_rate_command(nominal)))
                if not ok:
                    raise SinkError("the control port {}:{} did not accept the width/rate command"
                                    .format(host, cfg["control_port"]))
            time.sleep(net.SETTLE_AFTER_CONTROL_S)
        try:
            sock = net.open_data_socket(host, cfg["data_port"])
            sock.sendall(init_bytes)
        except OSError as exc:
            raise SinkError("data port {}:{} not reachable ({})".format(host, cfg["data_port"], exc))

        with self._lock:
            self._sock = sock
            self._failed = False
            self._pacer = protocol.Pacer(nominal)
            self.params = (nominal, center_freq)
            self._rate = nominal
            self.level = LevelMonitor("smisdr_iq")
            self.limiter = protocol.PeakLimiter(nominal, ceiling=1.0) if cfg["limiter"] else None
        logger.info("smisdr_iq: in-band init sent: NCO %s Hz, input rate %s Hz", center_freq, nominal)
        self._start_idle()

    def _prepare_mode(self):
        """parlioSDR only: bring the device into the mode that fits the I/Q stream.
        -> True if the soft DUC of the ESP32 is active (width / rate are not sent then)."""
        cfg, host, port = self.cfg, self.host, self.cfg["control_port"]
        if not cfg["mode_switch"]:
            return False
        try:
            mode = modes.query_mode(host, port)
            wish = cfg["iq_dsp"]
            if mode is None:
                if wish == "soft":
                    raise SinkError("smisdr_iq_dsp is 'soft', but the device does not know the command "
                                    "'mode' (no software DUC) - use smisdr_iq_dsp: fpga or auto")
                logger.info("smisdr_iq: device has no operating modes (smiSDR) - FPGA pass-through")
                return False
            if wish == "fpga":
                if mode == "duc":
                    modes.switch_mode(host, port, "raw")        # I/Q goes to the FPGA behind the ESP32
                return False
            if mode != "duc":
                modes.switch_mode(host, port, "duc")
            for command in cfg["duc_commands"]:
                message = modes.send_extra(host, port, command)
                if message:
                    logger.warning("smisdr_iq: %s", message)
            return True
        except modes.ModeError as exc:
            raise SinkError(str(exc))

    def _send_words(self, words, pairs):
        try:
            self._sock.sendall(words)
        except (OSError, AttributeError) as exc:           # AttributeError: closed meanwhile
            self._failed = True
            raise OSError(str(exc)) from exc
        self._pacer.pace(pairs)

    def _transmit(self, x):
        words = protocol.encode_iq_words(x, 1.0)
        self._send_words(words, len(words) // 4)

    def _transmit_silence(self, frames):
        self._send_words(protocol.silence_words(frames), frames)

    def abort(self):
        net.close_socket(self._sock)

    def _close(self, graceful):
        with self._lock:
            sock, self._sock = self._sock, None
            self._pacer = None
            self.params = None
        if sock is None:
            return
        if graceful and not self._failed:
            try:        # leave the DAC at zero instead of at the last sample value
                sock.sendall(protocol.silence_words(CLOSE_SILENCE_FRAMES))
            except OSError:
                pass
        net.close_socket(sock)


# ======================================================================================
class RawSink(_SinkBase):
    """finished RF samples from cohi_native_upconverter"""

    def __init__(self, host, cfg, idle_silence=False, on_error=None):
        super().__init__(host, cfg, idle_silence)
        self._link = None
        self._on_error = on_error

    @property
    def alive(self):
        return self._link is not None and self._link.alive

    def open(self, center_freq, sample_rate):
        cfg = self.cfg
        target = protocol.choose_target_rate(sample_rate, center_freq, cfg["sample_rate"],
                                             cfg["control_port"] is not None)
        if target is None:
            raise SinkError("the recording (centre {} Hz, up to {} Hz, {} Hz sample rate) does not fit "
                            "the output rate ({}) - use a higher smisdr_sample_rate".format(
                                int(center_freq), int(center_freq + sample_rate / 2.0),
                                int(sample_rate), cfg["sample_rate"]))
        wanted = (sample_rate, center_freq, target)
        if self.alive and self._link.params == wanted:
            logger.info("smisdr_raw: same frequency / sample rate as the running chain - kept")
            return
        self._close(graceful=True)
        if cfg["control_port"] is not None and cfg["mode_switch"]:
            try:                                    # parlioSDR in the soft DUC mode would misread RF samples
                if modes.query_mode(self.host, cfg["control_port"]) == "duc":
                    modes.switch_mode(self.host, cfg["control_port"], "raw")
            except modes.ModeError as exc:
                raise SinkError(str(exc))
        tool = rawlink.resolve_tool_path(cfg["upconverter_path"])
        if tool is None:
            raise SinkError("{} not found".format(rawlink.TOOL_NAME))
        link = rawlink.RawLink(self.host, cfg["data_port"], cfg["control_port"], tool,
                               cfg["format"], cfg["offset"], on_error=self._on_error)
        try:
            link.start(sample_rate, center_freq, target)
        except rawlink.LinkError as exc:
            raise SinkError(str(exc))
        self._link = link
        self.params = wanted
        self._rate = sample_rate
        self.level = LevelMonitor("smisdr_raw", ceiling=protocol.RAW_INPUT_CEILING)
        self.limiter = (protocol.PeakLimiter(sample_rate, ceiling=protocol.RAW_INPUT_CEILING,
                                             magnitude=True) if cfg["limiter"] else None)
        logger.info("smisdr_raw: chain started (centre %s Hz, input %s Hz, output %s Hz)",
                    center_freq, sample_rate, target)
        self._start_idle()

    def _write(self, data):
        link = self._link
        if link is None:
            raise BrokenPipeError("the output chain is not running")
        try:
            link.write(data)
        except OSError as exc:
            reason = link.failure_reason or str(exc)
            raise OSError(reason) from exc

    def _transmit(self, x):
        self._write(protocol.float_iq_to_int16(x, 1.0).tobytes())

    def _transmit_silence(self, frames):
        self._write(b"\x00" * (4 * frames))

    def abort(self):
        link = self._link
        if link is not None:
            link.abort()

    def _close(self, graceful):
        link, self._link = self._link, None
        self.params = None
        if link is not None:
            link.close(graceful=graceful)
