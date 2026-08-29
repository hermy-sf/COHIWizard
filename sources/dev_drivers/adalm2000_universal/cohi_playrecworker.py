"""
cohi_playrecworker.py — adalm2000_universal

Extends the original adalm2000 driver with:
  - Audio-overlay: reads a CSV playlist and AM-modulates audio streams
    onto individual RF carriers using an extended ffmpeg filter_complex.
  - Audio streams are fetched from internet/local sources via ffmpeg
    sub-processes, sent to UDP ports, and folded into the main filter.

Modes (selected automatically):
  IQ-File only:      filenames set, no audioplaylist → original behaviour
  IQ-File + Audio:   filenames set, audioplaylist set → AM overlay via ffmpeg
  Audio-only:        filenames empty, audioplaylist set → (not yet supported;
                     ADALM needs a carrier IQ input — use fl2k_universal instead)

config_wizard.yaml keys used in addition to the base adalm2000 driver:
  audioplaylist     str   path to semicolon-CSV (Frequenz;BW;Name;URL)
  audio_rate_hz     int   PCM sample rate for audio ffmpeg (default 25000)
  audio_mix_level   float amplitude weight (default 1.0)
  audio_base_port   int   first UDP port (default 1235, avoid clash with IQ)
  audio_mod_index   float AM modulation index 0-1 (default 0.9)
"""

import csv
import os
import subprocess
import threading
import time
import queue
import array
from struct import unpack
from urllib.parse import urlparse, urlunparse

import libm2k
import numpy as np
import yaml

from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


# ---------------------------------------------------------------------------
# Audio playlist helpers
# ---------------------------------------------------------------------------

def _parse_freq(s: str) -> float:
    """Parse '175 kHz', '1.5 MHz', '9000 Hz' etc. → Hz."""
    s = s.strip()
    sl = s.lower()
    if sl.endswith("mhz"):
        return float(s[:-3].strip()) * 1e6
    if sl.endswith("khz"):
        return float(s[:-3].strip()) * 1e3
    if sl.endswith("hz"):
        return float(s[:-2].strip())
    return float(s)


def parse_audio_playlist(csv_path: str) -> list:
    """Parse semicolon-separated CSV: Frequenz;Bandbreite;Programmname;URL"""
    _QUOTE_MAP = str.maketrans({0x201C: 0x22, 0x201D: 0x22})

    def _norm(lines):
        for line in lines:
            yield line.translate(_QUOTE_MAP)

    stations = []
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(_norm(fh), delimiter=";", quotechar='"',
                                skipinitialspace=True)
            for lineno, parts in enumerate(reader, 1):
                if not parts or parts[0].strip().startswith("#"):
                    continue
                if len(parts) < 4:
                    print(f"[adalm2000_univ] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[adalm2000_univ] CSV line {lineno}: cannot parse "
                          f"'{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[adalm2000_univ] Cannot read playlist '{csv_path}': {exc}")
    return stations


def _ffmpeg_url(url: str) -> str:
    """Percent-encode semicolons in URL paths for ffmpeg."""
    try:
        p = urlparse(url)
        if p.params:
            base = urlunparse(p._replace(params=""))
            return base + "%3B" + p.params.replace(";", "%3B")
    except Exception:
        pass
    return url


def _resolve_ffmpeg_bin(raw: str) -> str:
    """Turn ffmpeg_path config entry (directory or exe) into executable path."""
    import platform
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    raw = (raw or "").strip()
    if not raw:
        return "ffmpeg"
    if os.path.isdir(raw):
        candidate = os.path.join(raw, exe_name)
        if os.path.isfile(candidate):
            return candidate
        return "ffmpeg"
    return raw


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """Worker for adalm2000_universal — IQ streaming + optional AM audio overlay.

    Extends the base adalm2000 worker with audio playlist support.
    The audio overlay is realised by extending the ffmpeg filter_complex
    to AM-modulate each station onto its carrier and mix into the RF signal.
    """

    __slots__ = ["filename", "timescaler", "TEST", "pause", "fileHandle",
                 "data", "gain", "formattag", "datablocksize", "fileclose",
                 "configparameters"]

    SigFinished         = pyqtSignal()
    SigIncrementCurTime = pyqtSignal()
    SigBufferOverflow   = pyqtSignal()
    SigError            = pyqtSignal(str)
    SigNextfile         = pyqtSignal(str)
    SigInfomessage      = pyqtSignal(str)

    def __init__(self, stemlabcontrolinst, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix = False
        self.DATABLOCKSIZE_BASIC = 4096 * 1024 * 4
        self.DATASHOWSIZE = 1024
        self.mutex = QMutex()
        self.stemlabcontrol = stemlabcontrolinst
        self.output_chunks = []
        self.chunk_queue = queue.Queue(maxsize=200)
        self._ffmpeg_procs = []
        self._concat_files = []

        configpath = os.path.join(os.getcwd(), "config_wizard.yaml")
        try:
            with open(configpath, "r") as stream:
                metadata = yaml.safe_load(stream)
            self.ffmpeg_path = metadata["ffmpeg_path"]
            try:
                self.relaxfactor_OSR = float(metadata["relaxfactor_OSR"])
            except Exception:
                self.relaxfactor_OSR = 1.2
            try:
                self.volumefactor = float(metadata["volumefactor"])
            except Exception:
                self.volumefactor = 1
        except FileNotFoundError:
            print(f"[adalm2000_univ] config {configpath} not found, using defaults")
            self.ffmpeg_path = "ffmpeg"
            self.relaxfactor_OSR = 1.2
            self.volumefactor = 1

    # ---- slot accessors ----
    def set_filename(self, v):         self.__slots__[0]  = v
    def get_filename(self):            return self.__slots__[0]
    def set_timescaler(self, v):       self.__slots__[1]  = v
    def get_timescaler(self):          return self.__slots__[1]
    def set_TEST(self, v):             self.__slots__[2]  = v
    def get_TEST(self):                return self.__slots__[2]
    def set_pause(self, v):            self.__slots__[3]  = v
    def get_pause(self):               return self.__slots__[3]
    def set_fileHandle(self, v):       self.__slots__[4]  = v
    def get_fileHandle(self):          return self.__slots__[4]
    def set_data(self, v):             self.__slots__[5]  = v
    def get_data(self):                return self.__slots__[5]
    def set_gain(self, v):             self.__slots__[6]  = v
    def get_gain(self):                return self.__slots__[6]
    def set_formattag(self, v):        self.__slots__[7]  = v
    def get_formattag(self):           return self.__slots__[7]
    def set_datablocksize(self, v):    self.__slots__[8]  = v
    def get_datablocksize(self):       return self.__slots__[8]
    def set_fileclose(self, v):        self.__slots__[9]  = v
    def get_fileclose(self):           return self.__slots__[9]
    def set_configparameters(self, v): self.__slots__[10] = v
    def get_configparameters(self):    return self.__slots__[10]

    def stop_loop(self):
        self.stopix = True

    # ---- audio stream helpers ----

    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        """Start one ffmpeg subprocess per station, return channel list."""
        channels = []
        for idx, sta in enumerate(stations):
            port = base_port + idx
            url = sta["url"]
            bw_hz = sta["bw_hz"]
            name = sta["name"]
            lowpass_f = max(100, int(bw_hz / 2))

            _url_lower = url.lower()
            _is_http = _url_lower.startswith(("http://", "https://", "rtsp://"))
            _is_local_m3u = (
                _url_lower.endswith((".m3u", ".m3u8", ".pls")) and not _is_http
            )

            if _is_local_m3u:
                _entries = []
                try:
                    with open(url, "r", encoding="utf-8", errors="replace") as _mf:
                        for _line in _mf:
                            _line = _line.strip()
                            if _line and not _line.startswith("#"):
                                _entries.append(_line)
                except OSError as _exc:
                    print(f"[adalm2000_univ] Cannot read m3u '{url}': {_exc}")

                _valid = [e for e in _entries if os.path.isfile(e)]
                if not _valid:
                    print(f"[adalm2000_univ] m3u '{url}': no valid files – skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="adalm_concat_",
                    delete=False, encoding="utf-8"
                )
                _cf.write("ffconcat version 1.0\n")
                for _ in range(200):
                    for _e in _valid:
                        _cf.write(f"file {_e!r}\n")
                _cf.close()
                self._concat_files.append(_cf.name)
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin, "-re",
                    "-f", "concat", "-safe", "0", "-i", _cf.name,
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            elif _is_http and urlparse(url).params:
                _curl_cmd = ["curl", "-s", "--max-time", "0", "--", url]
                cmd = [
                    ffmpeg_bin, "-i", "pipe:0",
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            else:
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin,
                    "-reconnect", "1", "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                    "-i", _ffmpeg_url(url),
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]

            import tempfile, pathlib
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"adalm_univ_ch{idx}.log"
            try:
                if _curl_cmd is not None:
                    curl_proc = subprocess.Popen(
                        _curl_cmd, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, close_fds=True,
                    )
                    proc = subprocess.Popen(
                        cmd, stdin=curl_proc.stdout,
                        stdout=subprocess.DEVNULL,
                        stderr=open(_logfile, "w"), close_fds=True,
                    )
                    curl_proc.stdout.close()
                    self._ffmpeg_procs.append(curl_proc)
                else:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL,
                        stderr=open(_logfile, "w"), close_fds=True,
                    )
                self._ffmpeg_procs.append(proc)
                print(f"[adalm2000_univ] audio ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz']/1e3:.1f} kHz -> UDP {port} (PID {proc.pid})")
                channels.append({
                    "freq_hz":  sta["freq_hz"],
                    "bw_hz":    bw_hz,
                    "name":     name,
                    "udp_port": port,
                    "mod_index": mod_index,
                })
            except OSError as exc:
                print(f"[adalm2000_univ] Failed to start ffmpeg for '{name}': {exc}")
        return channels

    def _stop_audio_streams(self):
        """Terminate all audio ffmpeg subprocesses."""
        for proc in self._ffmpeg_procs:
            try:
                proc.terminate()
            except OSError:
                pass
        deadline = time.time() + 2.0
        for proc in self._ffmpeg_procs:
            remaining = max(0.0, deadline - time.time())
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
        self._ffmpeg_procs.clear()
        for _cf in self._concat_files:
            try:
                os.unlink(_cf)
            except OSError:
                pass
        self._concat_files.clear()
        print("[adalm2000_univ] Audio streams stopped.")

    # ---- ffmpeg command builders ----

    def gen_ffmpeg_cmd(self, ffmpeg_path, SRAdalm=2500000, sampling_rate=1250000,
                       lo_shift=1125000, preset_volume=1):
        """Original IQ-only ffmpeg command (unchanged from adalm2000 driver)."""
        formatstring = "s16le"
        a = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)
        ffmpeg_bin = os.path.join(str(ffmpeg_path), "ffmpeg") if os.path.isdir(str(ffmpeg_path)) else str(ffmpeg_path)

        ffmpeg_cmd = [
            ffmpeg_bin, "-y", "-loglevel", "error", "-hide_banner",
            "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",
            "-filter_complex",
            "[0:a]aresample=osr=" + str(SRAdalm) + ",channelsplit=channel_layout=stereo [re][im];"
            "sine=frequency=" + str(lo_shift) + ":sample_rate=" + str(SRAdalm) + "[sine_base];"
            "[sine_base] asplit=2[sine_sin1][sine_sin2];"
            "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
            "[re][sine_cos]amultiply[mod_re];"
            "[im][sine_sin1]amultiply[mod_im];"
            "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];"
            "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
            "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
        ]
        return ffmpeg_cmd

    def gen_ffmpeg_cmd_with_audio(self, ffmpeg_path, SRAdalm, sampling_rate,
                                   lo_shift, preset_volume, stations,
                                   audio_rate_hz, mod_index, base_port):
        """Extended ffmpeg command: IQ upconversion + AM-modulated audio overlay.

        Audio inputs are read from UDP ports (base_port + i).
        Each station is AM-modulated onto its carrier frequency and mixed
        with the main IQ RF signal.
        """
        if not stations:
            return self.gen_ffmpeg_cmd(ffmpeg_path, SRAdalm, sampling_rate,
                                       lo_shift, preset_volume)

        ffmpeg_bin = os.path.join(str(ffmpeg_path), "ffmpeg") if os.path.isdir(str(ffmpeg_path)) else str(ffmpeg_path)
        a_iq = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)

        cmd = [ffmpeg_bin, "-y", "-loglevel", "error", "-hide_banner"]
        # Input 0: IQ from stdin
        cmd += ["-f", "s16le", "-ar", str(sampling_rate), "-ac", "2", "-i", "-"]
        # Inputs 1..N: audio UDP streams
        for i, sta in enumerate(stations):
            port = base_port + i
            cmd += ["-f", "u8", "-ar", str(audio_rate_hz), "-ac", "1",
                    "-i", f"udp://127.0.0.1:{port}"]

        # Build filter_complex
        fc_parts = []

        # Step 1: upconvert IQ → RF → [iq_rf]
        fc_parts.append(
            f"[0:a]aresample=osr={int(SRAdalm)},channelsplit=channel_layout=stereo[iq_re][iq_im];"
            f"sine=frequency={int(lo_shift)}:sample_rate={int(SRAdalm)}[iq_sine_base];"
            f"[iq_sine_base]asplit=2[iq_s1][iq_s2];"
            f"[iq_s2]biquad=b0={a_iq}:b1=1:b2=0:a0=1:a1={a_iq}:a2=0[iq_cos];"
            f"[iq_re][iq_cos]amultiply[iq_mod_re];"
            f"[iq_im][iq_s1]amultiply[iq_mod_im];"
            f"[iq_mod_re]volume=volume={preset_volume}[iq_part_re];"
            f"[iq_mod_im]volume=volume={preset_volume}[iq_part_im];"
            f"[iq_part_re][iq_part_im]amix=inputs=2:duration=shortest[iq_rf]"
        )

        # Step 2: AM-modulate each audio stream → [audio_rf_i]
        audio_labels = []
        for i, sta in enumerate(stations):
            fc_hz = sta["freq_hz"]
            bw_hz = sta["bw_hz"]
            lowpass_f = max(100, int(bw_hz / 2))
            a_au = (np.tan(np.pi * fc_hz / SRAdalm) - 1) / (np.tan(np.pi * fc_hz / SRAdalm) + 1)
            label = f"audio_rf_{i}"
            audio_labels.append(label)
            # Resample + lowpass audio; generate carrier; AM-modulate (carrier + scaled_audio*carrier)
            fc_parts.append(
                f"[{i + 1}:a]aresample=osr={int(SRAdalm)},lowpass=f={lowpass_f}[au{i}_raw];"
                f"[au{i}_raw]volume=volume={mod_index}[au{i}_scaled];"
                f"sine=frequency={int(fc_hz)}:sample_rate={int(SRAdalm)}[au{i}_carrier_base];"
                f"[au{i}_carrier_base]asplit=2[au{i}_c1][au{i}_c2];"
                f"[au{i}_c2]biquad=b0={a_au}:b1=1:b2=0:a0=1:a1={a_au}:a2=0[au{i}_cos];"
                f"[au{i}_scaled][au{i}_c1]amultiply[au{i}_mod];"
                f"[au{i}_cos]volume=volume=1.0[au{i}_carrier];"
                f"[au{i}_carrier][au{i}_mod]amix=inputs=2:duration=shortest[{label}]"
            )

        # Step 3: mix all RF signals
        all_labels = "[iq_rf]" + "".join(f"[{l}]" for l in audio_labels)
        n_total = 1 + len(audio_labels)
        fc_parts.append(f"{all_labels}amix=inputs={n_total}:duration=shortest[out]")

        filter_complex = ";".join(fc_parts)
        cmd += ["-filter_complex", filter_complex,
                "-map", "[out]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]
        return cmd

    # ---- OSR calculation (unchanged from adalm2000) ----

    def maximize_OSR(self, SRDAC, lo_shift, sampling_rate):
        """Calculate optimal oversampling ratio."""
        relaxfactor_OSR = self.relaxfactor_OSR
        f_nyquist = lo_shift + sampling_rate / 2
        r_max = SRDAC / (2 * relaxfactor_OSR * f_nyquist)
        for OSR in np.arange(int(np.floor(r_max)), 1, -1):
            r = SRDAC / OSR
            if SRDAC % r == 0:
                break
        return OSR

    # ---- pipe threads (unchanged from adalm2000) ----

    def pipe_reader_thread(self, stdout_pipe, buffer_size):
        try:
            while True:
                chunk = stdout_pipe.read(buffer_size)
                if not chunk:
                    break
                self.chunk_queue.put(chunk)
        except Exception as e:
            print(f"[adalm2000_univ] Reader thread error: {e}")
        finally:
            self.chunk_queue.put(None)

    def pusher_thread(self, ao):
        push_count = 0
        try:
            samples_raw = array.array('h')
            while True:
                chunk = self.chunk_queue.get()
                if chunk is None:
                    break
                push_count += 1
                del samples_raw[:]
                samples_raw.frombytes(chunk)
                if ao is not None:
                    ao.pushRaw(0, samples_raw)
                else:
                    print(f"[adalm2000_univ] pusher: ao is None, chunk len={len(chunk)}")
        except Exception as e:
            print(f"[adalm2000_univ] Pusher thread error: {e}")

    # ---- main play loop ----

    def play_loop_filelist(self):
        """Main entry point called from QThread."""
        filenames = self.get_filename()
        TEST = self.get_TEST()
        gain = self.get_gain()
        self.stopix = False
        self.set_fileclose(False)
        configuration = self.get_configparameters()
        sampling_rate = configuration["irate"]
        lo_shift = configuration["ifreq"]

        # Read audio overlay config
        _audioplaylist = ""
        _audio_rate    = 25000
        _mix_level     = 1.0
        _base_port     = 1235  # offset from default 1234 to avoid clash
        _mod_index     = 0.9
        try:
            with open(os.path.join(os.getcwd(), "config_wizard.yaml"), "r") as f:
                _cfg = yaml.safe_load(f) or {}
            _audioplaylist = str(_cfg.get("audioplaylist", "")).strip()
            _audio_rate    = int(_cfg.get("audio_rate_hz", 25000))
            _mix_level     = float(_cfg.get("audio_mix_level", 1.0))
            _base_port     = int(_cfg.get("audio_base_port", 1235))
            _mod_index     = float(_cfg.get("audio_mod_index", 0.9))
        except Exception as e:
            print(f"[adalm2000_univ] config read error: {e}")

        _stations = parse_audio_playlist(_audioplaylist) if _audioplaylist else []
        has_audio = bool(_stations)
        ffmpeg_bin = _resolve_ffmpeg_bin(str(self.ffmpeg_path))
        print(f"[adalm2000_univ] has_audio={has_audio}, {len(_stations)} stations")

        # ADALM setup
        SRDAC = 75000000
        OSR = self.maximize_OSR(SRDAC, lo_shift, sampling_rate)
        print("[adalm2000_univ] checking for ADALM2000")
        self.mutex.lock()
        errorstate, value = self.check_ready_ADALM()
        ctx = value
        self.mutex.unlock()
        ao = None
        if not errorstate and not TEST:
            channel = 0
            ao = ctx.getAnalogOut()
            ao.setSampleRate(channel, SRDAC)
            ao.setOversamplingRatio(channel, int(OSR))
            ao.enableChannel(channel, True)
            ao.setKernelBuffersCount(0, 128)
            ao.setCyclic(False)
        elif not TEST:
            print("[adalm2000_univ] no ADALM2000 present")
            self.SigError.emit(value)
            self.SigFinished.emit()
            return

        # Format setup
        format_tag = self.get_formattag()
        ffmpeg_path = self.ffmpeg_path

        if format_tag[0] == 1:  # PCM
            if format_tag[2] == 16:
                formatstring = "s16le"
                preset_volume = 5
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
            elif format_tag[2] == 24:
                formatstring = "s24le"
                preset_volume = 100
                self.DATABLOCKSIZE = 4096 * 256 * 24
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
            else:
                formatstring = "s32le"
                preset_volume = 1
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
        else:  # IEEE float
            if format_tag[2] == 32:
                formatstring = "f32le"
                preset_volume = 1
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
            elif format_tag[2] == 16:
                formatstring = "f16le"
                preset_volume = 200
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float16)
            else:
                self.SigError.emit(f"Format not supported: {format_tag[2]}")
                self.SigFinished.emit()
                if not TEST:
                    libm2k.contextClose(ctx)
                return

        preset_volume *= self.volumefactor
        self.JUNKSIZE = self.DATABLOCKSIZE / 2

        # Start audio streams if needed
        audio_channels = []
        if has_audio:
            audio_channels = self._start_audio_streams(
                _stations, _base_port, _audio_rate, _mod_index, ffmpeg_bin
            )
            time.sleep(1.0)  # let ffmpeg start sending
            print(f"[adalm2000_univ] {len(audio_channels)} audio channel(s) started")

        # Start ffmpeg IQ process
        try:
            if has_audio and audio_channels:
                ffmpeg_cmd = self.gen_ffmpeg_cmd_with_audio(
                    ffmpeg_path, SRDAC / OSR, sampling_rate, lo_shift,
                    preset_volume, audio_channels, _audio_rate, _mod_index, _base_port
                )
            else:
                ffmpeg_cmd = self.gen_ffmpeg_cmd(
                    ffmpeg_path, SRDAC / OSR, sampling_rate, lo_shift, preset_volume
                )
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            print(f"[adalm2000_univ] ffmpeg started (PID {ffmpeg_process.pid})")
        except FileNotFoundError:
            print("[adalm2000_univ] ffmpeg not found")
            self._stop_audio_streams()
            if not TEST:
                libm2k.contextClose(ctx)
            return
        except Exception as e:
            print(f"[adalm2000_univ] ffmpeg start error: {e}")
            self._stop_audio_streams()
            if not TEST:
                libm2k.contextClose(ctx)
            return

        # Start pipe reader / pusher threads
        reader = threading.Thread(
            target=self.pipe_reader_thread,
            args=(ffmpeg_process.stdout, self.DATABLOCKSIZE)
        )
        reader.start()
        pusher = threading.Thread(target=self.pusher_thread, args=(ao,))
        pusher.start()

        # Main file loop
        for ix, filename in enumerate(filenames):
            if self.stopix:
                break
            fileHandle = open(filename, "rb")
            if format_tag[2] == 24:
                fileHandle.seek(212, 1)
            else:
                fileHandle.seek(216, 1)
            count = 0

            if format_tag[0] == 1:
                normfactor = int(2 ** int(format_tag[2] - 1)) - 1
            else:
                normfactor = 1

            if format_tag[2] == 16 or format_tag[2] == 32:
                size = fileHandle.readinto(data)
            elif format_tag[2] == 24:
                data = fileHandle.read(self.DATABLOCKSIZE * 3)
                size = len(data)
            else:
                size = fileHandle.readinto(data)

            junkspersecond = sampling_rate / self.JUNKSIZE
            self.SigNextfile.emit(filename)
            self.set_fileHandle(fileHandle)
            self.set_datablocksize(self.DATABLOCKSIZE)

            while size > 0 and not self.stopix:
                self.mutex.lock()
                if ffmpeg_process.poll() is not None:
                    self.SigError.emit("ffmpeg process terminated unexpectedly")
                    self.mutex.unlock()
                    break
                self.mutex.unlock()

                if not self.get_pause():
                    try:
                        if formatstring == "s16le":
                            ffmpeg_process.stdin.write((gain * data[:size]).astype(np.int16))
                        elif formatstring == "s32le":
                            ffmpeg_process.stdin.write((gain * data[:size]).astype(np.int32))
                        elif formatstring == "f32le":
                            ffmpeg_process.stdin.write((gain * data[:size]).astype(np.float32))
                        elif formatstring == "s24le":
                            ffmpeg_process.stdin.write(data)
                        else:
                            ffmpeg_process.stdin.write((gain * data[:size]).astype(np.float16))
                    except BrokenPipeError:
                        self.SigError.emit("ffmpeg pipe closed – restart required.")
                        self.SigFinished.emit()
                        self._stop_audio_streams()
                        if not TEST:
                            libm2k.contextClose(ctx)
                        return
                    except Exception as e:
                        self.SigError.emit(f"Write error: {e}")
                        self.SigFinished.emit()
                        self._stop_audio_streams()
                        if not TEST:
                            libm2k.contextClose(ctx)
                        return

                    QThread.usleep(1)

                    if format_tag[2] == 24:
                        data = fileHandle.read(self.DATABLOCKSIZE * 3)
                        size = len(data)
                    else:
                        size = fileHandle.readinto(data)

                    count += 1
                    if count > junkspersecond:
                        if format_tag[2] != 24:
                            self.set_data(data[:self.DATASHOWSIZE])
                        self.SigIncrementCurTime.emit()
                        count = 0
                        gain = self.get_gain()
                else:
                    aux1 = 0 * data[:size]
                    ffmpeg_process.stdin.write(aux1)
                    ffmpeg_process.stdin.flush()
                    time.sleep(0.1)
                    if self.stopix:
                        break

            self.set_fileclose(True)
            fileHandle.close()

        # Cleanup
        ffmpeg_process.stdin.close()
        ffmpeg_process.stdout.close()
        ffmpeg_process.terminate()
        ffmpeg_process.wait()
        reader.join()
        pusher.join()

        self._stop_audio_streams()

        if ao is not None:
            try:
                ao.push(0, [0.0] * 5000)
                time.sleep(0.01)
                ao.enableChannel(0, False)
                ao.setSampleRate(0, 0)
            except Exception as e:
                print(f"[adalm2000_univ] Error closing ADALM ao: {e}")

        self.SigFinished.emit()
        print("[adalm2000_univ] closing ctx")
        if not TEST:
            libm2k.contextClose(ctx)

    # ---- ADALM check (unchanged) ----

    def check_ready_ADALM(self):
        errorstate = False
        value = ""
        try:
            ctx = libm2k.m2kOpen()
            ctx.calibrateDAC()
            value = ctx
        except Exception as e:
            value = f"ADALM2000 not ready: {e}"
            errorstate = True
        return errorstate, value

    # ---- 24-bit helpers (unchanged from adalm2000) ----

    def read_24bit_block_np(self, file, blocksize):
        raw_data = file.read(blocksize * 3)
        if len(raw_data) < 3:
            return np.array([], dtype=np.int32)
        raw_array = np.frombuffer(raw_data, dtype=np.uint8).reshape(-1, 3)
        samples = raw_array[:, 0] | (raw_array[:, 1] << 8) | (raw_array[:, 2] << 16)
        samples = samples.astype(np.int32)
        samples[samples >= (1 << 23)] -= (1 << 24)
        return samples.astype(np.float32)

    def convert24_32(self, raw_data):
        if len(raw_data) < 3:
            return np.array([], dtype=np.int32)
        raw_array = np.frombuffer(raw_data, dtype=np.uint8).reshape(-1, 3)
        samples = raw_array[:, 0] | (raw_array[:, 1] << 8) | (raw_array[:, 2] << 16)
        samples = samples.astype(np.int32)
        samples[samples >= (1 << 23)] -= (1 << 24)
        return samples.astype(np.float32) * 256

    def rec_loop(self):
        return
