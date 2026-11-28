"""
smisdr_common/rawlink.py
========================
Output chain of smisdr_raw and smisdr_raw_universal (no Qt):

    worker --int16 I/Q--> [cohi_native_upconverter] --RF samples--> pump thread --> TCP data port

The up-conversion runs in the C++ tool, which also paces its output to real time (that is why
the worker needs no pacing of its own: a full pipe slows the worker down).  This is the same
chain that COHI-Player-Universal uses for hwconfig: smisdr.
"""
import atexit
import collections
import logging
import os
import shutil
import subprocess
import sys
import threading
import time

from dev_drivers.smisdr_common import net, protocol

logger = logging.getLogger("smisdr")

TOOL_NAME = "cohi_native_upconverter" + (".exe" if sys.platform.startswith("win") else "")
PUMP_READ_BYTES = 64 * 1024
STDIN_BUFFER_BYTES = 64 * 1024
GRACEFUL_WAIT_S = 3.0
STDERR_TAIL_LINES = 8
SILENCE_SAMPLES = 512

_live_links = set()


@atexit.register
def _kill_leftovers():
    """never leave an upconverter process behind if COHIWizard ends abnormally"""
    for link in list(_live_links):
        try:
            link.abort()
        except Exception:
            pass


class LinkError(Exception):
    pass


def resolve_tool_path(configured=""):
    """Path of cohi_native_upconverter: smisdr_upconverter_path from config_wizard.yaml, else
    smisdr_common/upconverter, else PATH. -> path or None"""
    if configured:
        return configured if os.path.isfile(configured) else None
    # the tool and its source live in smisdr_common/upconverter (shared by both raw drivers)
    here = os.path.dirname(os.path.abspath(__file__))
    local = os.path.join(here, "upconverter", TOOL_NAME)
    if os.path.isfile(local):
        return local
    return shutil.which(TOOL_NAME)


class RawLink:
    def __init__(self, host, data_port, control_port, tool_path, sample_format, offset_binary,
                 on_error=None):
        self.host = host
        self.data_port = data_port
        self.control_port = control_port
        self.tool_path = tool_path
        self.sample_format = sample_format
        self.offset_binary = offset_binary
        self._on_error = on_error
        self._proc = None
        self._sock = None
        self._pump = None
        self._closing = False
        self.failed = False
        self.failure_reason = ""
        self.params = None
        self._stderr_tail = collections.deque(maxlen=STDERR_TAIL_LINES)

    # ---- state ------------------------------------------------------------------
    @property
    def alive(self):
        return (self._proc is not None and self._proc.poll() is None
                and self._sock is not None and not self.failed)

    def stderr_tail(self):
        return " | ".join(self._stderr_tail)

    # ---- start --------------------------------------------------------------------
    def start(self, sample_rate, center_freq, target_rate):
        """Configure the device, connect the data port and start the upconverter.
        Raises LinkError with a message for the user."""
        self.close(graceful=False)
        self._closing = False
        self.failed = False
        self.failure_reason = ""
        self._stderr_tail.clear()

        if self.control_port is not None:
            ok = (net.send_control_command(self.host, self.control_port,
                                           protocol.format_width_command(self.sample_format))
                  and net.send_control_command(self.host, self.control_port,
                                               protocol.format_rate_command(target_rate)))
            if not ok:
                raise LinkError("the control port {}:{} did not accept the width/rate command"
                                .format(self.host, self.control_port))
            time.sleep(net.SETTLE_AFTER_CONTROL_S)
        try:
            self._sock = net.open_data_socket(self.host, self.data_port)
        except OSError as exc:
            raise LinkError("data port {}:{} not reachable ({})".format(self.host, self.data_port, exc))

        command = protocol.build_upconverter_command(
            self.tool_path, sample_rate, center_freq, target_rate, self.sample_format)
        logger.info("smisdr_raw: %s", " ".join(command))
        try:
            self._proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, bufsize=STDIN_BUFFER_BYTES)
        except OSError as exc:
            net.close_socket(self._sock)
            self._sock = None
            raise LinkError("{} could not be started: {}".format(TOOL_NAME, exc))

        threading.Thread(target=self._drain_stderr, args=(self._proc,),
                         name="smisdr-stderr", daemon=True).start()
        self._pump = threading.Thread(target=self._pump_loop, args=(self._proc, self._sock),
                                      name="smisdr-pump", daemon=True)
        self._pump.start()
        self.params = (sample_rate, center_freq, target_rate)
        _live_links.add(self)

    # ---- threads --------------------------------------------------------------------
    def _drain_stderr(self, proc):
        """A full stderr pipe would stop the upconverter: always read it."""
        try:
            for line in iter(proc.stderr.readline, b""):
                text = line.decode("utf-8", "replace").strip()
                if text:
                    self._stderr_tail.append(text)
                    logger.debug("%s: %s", TOOL_NAME, text)
        except (OSError, ValueError):
            pass

    def _pump_loop(self, proc, sock):
        """upconverter stdout -> TCP data connection"""
        passthrough = (self.sample_format in protocol.FORMATS_WIDE
                       or (self.sample_format == protocol.FORMAT_8 and not self.offset_binary))
        fd = proc.stdout.fileno()
        try:
            while True:
                raw = os.read(fd, PUMP_READ_BYTES)
                if not raw:
                    break
                sock.sendall(raw if passthrough
                             else protocol.convert_rf_block(raw, self.sample_format, self.offset_binary))
        except (OSError, ValueError) as exc:
            self._fail("sending to {}:{} failed ({})".format(self.host, self.data_port, exc))
            return
        if not self._closing:                                  # EOF without being asked to
            try:
                returncode = proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                returncode = proc.poll()
            self._fail("{} ended unexpectedly (return code {}){}".format(
                TOOL_NAME, returncode,
                ": " + self.stderr_tail() if self._stderr_tail else ""))

    def _fail(self, message):
        if self._closing or self.failed:
            return
        self.failed = True
        self.failure_reason = message
        logger.error("smisdr_raw: %s", message)
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass
        if self._on_error:
            self._on_error(message)

    # ---- data -------------------------------------------------------------------------
    def write(self, data):
        """int16 I/Q bytes to the upconverter; raises OSError if the chain is broken"""
        if self._proc is None or self.failed:
            raise BrokenPipeError("the output chain is not running")
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    # ---- end ---------------------------------------------------------------------------
    def abort(self):
        """Any thread: stop immediately (stop button). Unblocks a write()."""
        self._closing = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        net.close_socket(self._sock)

    def close(self, graceful=True):
        """graceful: let the upconverter drain its output and leave the DAC at zero;
        otherwise (stop, error) kill at once."""
        proc, sock, pump = self._proc, self._sock, self._pump
        if proc is None and sock is None:
            return
        self._closing = True
        if proc is not None:
            if graceful and not self.failed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=GRACEFUL_WAIT_S)
                except subprocess.TimeoutExpired:
                    pass
            if proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.error("smisdr_raw: %s does not end", TOOL_NAME)
        if pump is not None:
            pump.join(timeout=GRACEFUL_WAIT_S if graceful else 1.0)
        if sock is not None and graceful and not self.failed:
            try:
                sock.sendall(protocol.rf_silence(self.sample_format, self.offset_binary, SILENCE_SAMPLES))
            except OSError:
                pass
        net.close_socket(sock)
        for stream in (proc.stdin, proc.stdout, proc.stderr) if proc is not None else ():
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        self._proc = self._sock = self._pump = None
        self.params = None
        _live_links.discard(self)
