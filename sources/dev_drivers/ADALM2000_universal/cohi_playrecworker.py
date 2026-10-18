"""
cohi_playrecworker.py — ADALM2000_universal

Architecture mirrors fl2k_universal: mode detected at runtime.

  Mode A  IQ-file present              → ffmpeg IQ ± audio overlay → libm2k
  Mode B  audio_only (no IQ file)      → ffmpeg AM synthesis → libm2k
  Error   Neither file nor playlist configured

config_wizard.yaml keys used:
  audioplaylist     str    path to semicolon-CSV (Frequenz;BW;Name;URL)
  audio_rate_hz     int    PCM sample rate for audio ffmpeg (default 25000)
  audio_mix_level   float  amplitude weight for audio channels (default 1.0)
  audio_base_port   int    first UDP port (default 1235)
  audio_mod_index   float  AM modulation index 0–1 (default 0.9)
  ffmpeg_path       str    ffmpeg binary (default 'ffmpeg')
  relaxfactor_OSR   float  OSR safety margin (default 1.2)
  volumefactor      float  global volume scale (default 1.0)
"""

import array
import ctypes
import csv
import os
import subprocess
import threading
import time
import queue
from urllib.parse import urlparse, urlunparse

import libm2k
import numpy as np
import yaml

from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_freq(s: str) -> float:
    s  = s.strip()
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
                    print(f"[ADALM2000_univ] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[ADALM2000_univ] CSV line {lineno}: cannot parse "
                          f"'{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[ADALM2000_univ] Cannot read playlist '{csv_path}': {exc}")
    return stations


def _ffmpeg_url(url: str) -> str:
    try:
        p = urlparse(url)
        if p.params:
            base = urlunparse(p._replace(params=""))
            return base + "%3B" + p.params.replace(";", "%3B")
    except Exception:
        pass
    return url


def _resolve_ffmpeg_bin(raw: str) -> str:
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
# C++ DSP library (libdspadlm.so)
# ---------------------------------------------------------------------------

class _DspAudioChannel(ctypes.Structure):
    """Mirrors DspAudioChannel in DspWorkerADALM.h — layout must match exactly."""
    _fields_ = [
        ("freq_hz",         ctypes.c_float),
        ("bandwidth_hz",    ctypes.c_float),
        ("name",            ctypes.c_char * 64),
        ("udp_port",        ctypes.c_int),
        ("mod_index",       ctypes.c_float),
        ("schroeder_phase", ctypes.c_float),
    ]

_lib_adlm = None


def _load_libdspadlm():
    global _lib_adlm
    _dir = os.path.dirname(os.path.abspath(__file__))
    _so  = os.path.join(_dir, "libdspadlm.so")
    try:
        lib = ctypes.CDLL(_so)
        lib.dsp_adlm_create.restype  = ctypes.c_void_p
        lib.dsp_adlm_create.argtypes = []
        lib.dsp_adlm_destroy.restype  = None
        lib.dsp_adlm_destroy.argtypes = [ctypes.c_void_p]
        lib.dsp_adlm_configure.restype  = ctypes.c_int
        lib.dsp_adlm_configure.argtypes = [
            ctypes.c_void_p, ctypes.c_float, ctypes.c_float,
            ctypes.c_float, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
        ]
        lib.dsp_adlm_configure_audio.restype  = ctypes.c_int
        lib.dsp_adlm_configure_audio.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_DspAudioChannel),
            ctypes.c_int, ctypes.c_float, ctypes.c_float,
        ]
        lib.dsp_adlm_prefill_audio.restype  = None
        lib.dsp_adlm_prefill_audio.argtypes = [ctypes.c_void_p, ctypes.c_int]
        for _name in ("set_monitor_cb", "set_progress_cb",
                      "set_finished_cb", "set_error_cb", "set_nextfile_cb"):
            fn = getattr(lib, f"dsp_adlm_{_name}")
            fn.restype  = None
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        lib.dsp_adlm_start.restype  = ctypes.c_int
        lib.dsp_adlm_start.argtypes = [ctypes.c_void_p]
        lib.dsp_adlm_stop.restype  = None
        lib.dsp_adlm_stop.argtypes = [ctypes.c_void_p]
        lib.dsp_adlm_set_pause.restype  = None
        lib.dsp_adlm_set_pause.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.dsp_adlm_set_gain.restype  = None
        lib.dsp_adlm_set_gain.argtypes = [ctypes.c_void_p, ctypes.c_float]
        lib.dsp_adlm_is_running.restype  = ctypes.c_int
        lib.dsp_adlm_is_running.argtypes = [ctypes.c_void_p]
        lib.dsp_adlm_seek.restype  = None
        lib.dsp_adlm_seek.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]
        lib.dsp_adlm_pull.restype  = ctypes.c_int
        lib.dsp_adlm_pull.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16), ctypes.c_int,
        ]
        _lib_adlm = lib
        print(f"[ADALM2000_univ] libdspadlm loaded: {_so}")
    except OSError as _e:
        print(f"[ADALM2000_univ] WARNING: libdspadlm not loaded ({_e})")


_load_libdspadlm()


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """
    Universal ADALM2000 worker — two operational modes selected at runtime:

      IQ-file present          → Mode A: ffmpeg IQ ± audio overlay → libm2k
      No IQ-file, playlist set → Mode B: ffmpeg pure AM synthesis   → libm2k
      Neither configured       → SigError

    __slots__ layout (compatible with all COHIWizard drivers):
      0  filename          – list of WAV file paths (empty for Mode B)
      1  timescaler        – bytes/second (informational)
      2  TEST              – True → dry-run mode
      3  pause             – True → mute
      4  fileHandle        – file object (Mode A) or None (Mode B)
      5  data              – 1024-sample monitor window
      6  gain              – amplitude scale factor
      7  formattag         – [wFormatTag, blockAlign, bitsPerSample]
      8  datablocksize     – read block size in bytes
      9  fileclose         – True when last file is closed
     10  configparameters  – dict with ifreq, irate, …
    """

    __slots__ = [
        "filename", "timescaler", "TEST", "pause",
        "fileHandle", "data", "gain", "formattag",
        "datablocksize", "fileclose", "configparameters",
    ]

    SigFinished         = pyqtSignal()
    SigIncrementCurTime = pyqtSignal()
    SigBufferOverflow   = pyqtSignal()
    SigError            = pyqtSignal(str)
    SigNextfile         = pyqtSignal(str)
    SigInfomessage      = pyqtSignal(str)

    def __init__(self, stemlabcontrolinst, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix             = False
        self.DATABLOCKSIZE_BASIC = 4096 * 1024 * 4
        self.DATASHOWSIZE       = 1024
        self.mutex              = QMutex()
        self.stemlabcontrol     = stemlabcontrolinst
        self.chunk_queue        = queue.Queue(maxsize=200)
        self._ffmpeg_procs      = []
        self._concat_files      = []

        configpath = os.path.join(os.getcwd(), "config_wizard.yaml")
        try:
            with open(configpath, "r") as stream:
                metadata = yaml.safe_load(stream)
            self.ffmpeg_path     = metadata.get("ffmpeg_path", "ffmpeg")
            self.relaxfactor_OSR = float(metadata.get("relaxfactor_OSR", 1.2))
            self.volumefactor    = float(metadata.get("volumefactor", 1.0))
        except FileNotFoundError:
            print(f"[ADALM2000_univ] config {configpath} not found, using defaults")
            self.ffmpeg_path     = "ffmpeg"
            self.relaxfactor_OSR = 1.2
            self.volumefactor    = 1.0

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

    # ----------------------------------------------------------------
    # OSR calculation
    # ----------------------------------------------------------------

    def maximize_OSR(self, SRDAC, lo_shift, sampling_rate):
        """Return largest OSR such that SRDAC/OSR still covers the signal band."""
        relaxfactor_OSR = self.relaxfactor_OSR
        f_nyquist = lo_shift + sampling_rate / 2
        r_max = SRDAC / (2 * relaxfactor_OSR * f_nyquist)
        for OSR in np.arange(int(np.floor(r_max)), 1, -1):
            r = SRDAC / OSR
            if SRDAC % r == 0:
                break
        return OSR

    # ----------------------------------------------------------------
    # Audio stream management
    # ----------------------------------------------------------------

    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        channels = []
        for idx, sta in enumerate(stations):
            port      = base_port + idx
            url       = sta["url"]
            bw_hz     = sta["bw_hz"]
            name      = sta["name"]
            lowpass_f = max(100, int(bw_hz / 2))

            _url_lower    = url.lower()
            _is_http      = _url_lower.startswith(("http://", "https://", "rtsp://"))
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
                    print(f"[ADALM2000_univ] Cannot read m3u '{url}': {_exc}")

                _local_files = [e for e in _entries if os.path.isfile(e)]
                _web_urls    = [e for e in _entries
                                if e.lower().startswith(("http://", "https://"))]
                _entries = _local_files + _web_urls
                if not _entries:
                    print(f"[ADALM2000_univ] m3u '{url}': no valid files or URLs – skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="adalm2k_univ_concat_",
                    delete=False, encoding="utf-8"
                )
                _cf.write("ffconcat version 1.0\n")
                for _ in range(200):
                    for _e in _entries:
                        _cf.write(f"file {_e!r}\n")
                _cf.close()
                self._concat_files.append(_cf.name)
                # HTTP/HTTPS entries in ffconcat require an explicit protocol whitelist
                _proto_opts = (
                    ["-protocol_whitelist", "file,http,https,tcp,tls,crypto"]
                    if _web_urls else []
                )
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin, "-re",
                    "-f", "concat", "-safe", "0",
                    *_proto_opts,
                    "-i", _cf.name,
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
                    f"udp://127.0.0.1:{port}?pkt_size=256&localport=0",
                ]
            else:
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin,
                    "-reconnect", "1", "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5", "-re",
                    "-i", _ffmpeg_url(url),
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256&localport=0",
                ]

            import tempfile, pathlib
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"adalm2k_univ_ch{idx}.log"
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
                print(f"[ADALM2000_univ] audio ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz']/1e3:.1f} kHz -> UDP {port} (PID {proc.pid})")
                channels.append({
                    "freq_hz":  sta["freq_hz"],
                    "bw_hz":    bw_hz,
                    "name":     name,
                    "udp_port": port,
                    "mod_index": mod_index,
                })
            except OSError as exc:
                print(f"[ADALM2000_univ] Failed to start ffmpeg for '{name}': {exc}")
        return channels

    def _stop_audio_streams(self):
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
        print("[ADALM2000_univ] Audio streams stopped.")

    def _diagnose_and_free_ports(self, base_port: int, n_ports: int) -> None:
        """Print which processes hold the target UDP ports; kill external ones."""
        import re, signal as _sig
        my_pid = os.getpid()
        try:
            raw = subprocess.check_output(["ss", "-ulnp"], text=True, timeout=4)
        except Exception as e:
            print(f"[ADALM2000_univ] port-check: ss failed ({e})")
            return
        targets = set(range(base_port, base_port + n_ports))
        found_any = False
        for line in raw.splitlines():
            m_port = re.search(r':(\d+)\s', line)
            if not m_port or int(m_port.group(1)) not in targets:
                continue
            found_any = True
            print(f"[ADALM2000_univ] port in use: {line.strip()}")
            for m_pid in re.finditer(r'pid=(\d+)', line):
                pid = int(m_pid.group(1))
                if pid == my_pid:
                    print(f"[ADALM2000_univ] WARNING: port {m_port.group(1)} "
                          f"held by THIS process (pid={pid}) — cannot free")
                else:
                    print(f"[ADALM2000_univ] Freeing UDP port {m_port.group(1)}: "
                          f"sending SIGTERM to pid={pid}")
                    try:
                        os.kill(pid, _sig.SIGTERM)
                    except ProcessLookupError:
                        pass
        if found_any:
            time.sleep(0.4)
        else:
            print(f"[ADALM2000_univ] ports {base_port}..{base_port+n_ports-1} are free")

    # ----------------------------------------------------------------
    # ffmpeg command builders
    # ----------------------------------------------------------------

    def gen_ffmpeg_cmd_iq(self, ffmpeg_path, SRAdalm, sampling_rate,
                          lo_shift, preset_volume):
        """IQ-only: upmix IQ stdin → RF → stdout (no audio overlay)."""
        a = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)
        ffmpeg_bin = _resolve_ffmpeg_bin(str(ffmpeg_path))
        return [
            ffmpeg_bin, "-y", "-loglevel", "error", "-hide_banner",
            "-f", "s16le", "-ar", str(sampling_rate), "-ac", "2", "-i", "-",
            "-filter_complex",
            f"[0:a]aresample=osr={int(SRAdalm)},channelsplit=channel_layout=stereo[re][im];"
            f"sine=frequency={int(lo_shift)}:sample_rate={int(SRAdalm)}[sine_base];"
            f"[sine_base]asplit=2[sine_sin1][sine_sin2];"
            f"[sine_sin2]biquad=b0={a}:b1=1:b2=0:a0=1:a1={a}:a2=0[sine_cos];"
            f"[re][sine_cos]amultiply[mod_re];"
            f"[im][sine_sin1]amultiply[mod_im];"
            f"[mod_re]volume=volume={preset_volume}[part_re];"
            f"[mod_im]volume=volume={preset_volume}[part_im];"
            f"[part_re][part_im]amix=inputs=2:duration=shortest[out]",
            "-map", "[out]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ]

    def gen_ffmpeg_cmd_iq_audio(self, ffmpeg_path, SRAdalm, sampling_rate,
                                lo_shift, preset_volume, stations,
                                audio_rate_hz, mod_index, base_port):
        """IQ upconversion + AM-modulated audio overlay.

        IQ is read from stdin; audio streams arrive on UDP ports base_port+i.
        """
        if not stations:
            return self.gen_ffmpeg_cmd_iq(ffmpeg_path, SRAdalm, sampling_rate,
                                          lo_shift, preset_volume)

        ffmpeg_bin = _resolve_ffmpeg_bin(str(ffmpeg_path))
        a_iq = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)

        cmd = [ffmpeg_bin, "-y", "-loglevel", "error", "-hide_banner"]
        cmd += ["-f", "s16le", "-ar", str(sampling_rate), "-ac", "2", "-i", "-"]
        for i, sta in enumerate(stations):
            cmd += ["-f", "u8", "-ar", str(audio_rate_hz), "-ac", "1",
                    "-i", f"udp://127.0.0.1:{base_port + i}?reuse=1"]

        fc_parts = []

        # IQ upconversion → [iq_rf]
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

        # AM-modulate each audio stream → [audio_rf_i]
        audio_labels = []
        for i, sta in enumerate(stations):
            fc_hz     = sta["freq_hz"]
            bw_hz     = sta["bw_hz"]
            lowpass_f = max(100, int(bw_hz / 2))
            a_au      = (np.tan(np.pi * fc_hz / SRAdalm) - 1) / (np.tan(np.pi * fc_hz / SRAdalm) + 1)
            label     = f"audio_rf_{i}"
            audio_labels.append(label)
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

        # Mix IQ RF + all audio RF signals
        all_labels  = "[iq_rf]" + "".join(f"[{l}]" for l in audio_labels)
        n_total     = 1 + len(audio_labels)
        fc_parts.append(f"{all_labels}amix=inputs={n_total}:duration=shortest[out]")

        cmd += ["-filter_complex", ";".join(fc_parts),
                "-map", "[out]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]
        return cmd

    def gen_ffmpeg_cmd_audioonly(self, ffmpeg_path, SRAdalm, stations,
                                 audio_rate_hz, mod_index, base_port,
                                 preset_volume):
        """Pure AM synthesis: N UDP audio streams → AM carriers → mixed RF output.

        No IQ file input. All carriers are generated synthetically by ffmpeg.
        """
        if not stations:
            return None

        ffmpeg_bin = _resolve_ffmpeg_bin(str(ffmpeg_path))

        cmd = [ffmpeg_bin, "-y", "-loglevel", "error", "-hide_banner"]
        for i in range(len(stations)):
            cmd += ["-f", "u8", "-ar", str(audio_rate_hz), "-ac", "1",
                    "-i", f"udp://127.0.0.1:{base_port + i}?reuse=1"]

        fc_parts     = []
        audio_labels = []
        for i, sta in enumerate(stations):
            fc_hz     = sta["freq_hz"]
            bw_hz     = sta["bw_hz"]
            lowpass_f = max(100, int(bw_hz / 2))
            a_au      = (np.tan(np.pi * fc_hz / SRAdalm) - 1) / (np.tan(np.pi * fc_hz / SRAdalm) + 1)
            label     = f"au_rf_{i}"
            audio_labels.append(label)
            fc_parts.append(
                f"[{i}:a]aresample=osr={int(SRAdalm)},lowpass=f={lowpass_f}[au{i}_raw];"
                f"[au{i}_raw]volume=volume={mod_index}[au{i}_scaled];"
                f"sine=frequency={int(fc_hz)}:sample_rate={int(SRAdalm)}[au{i}_carrier_base];"
                f"[au{i}_carrier_base]asplit=2[au{i}_c1][au{i}_c2];"
                f"[au{i}_c2]biquad=b0={a_au}:b1=1:b2=0:a0=1:a1={a_au}:a2=0[au{i}_cos];"
                f"[au{i}_scaled][au{i}_c1]amultiply[au{i}_mod];"
                f"[au{i}_cos]volume=volume=1.0[au{i}_carrier];"
                f"[au{i}_carrier][au{i}_mod]amix=inputs=2:duration=shortest[{label}]"
            )

        # Mix all carrier signals then apply final volume scaling
        if len(audio_labels) > 1:
            all_labels = "".join(f"[{l}]" for l in audio_labels)
            fc_parts.append(
                f"{all_labels}amix=inputs={len(audio_labels)}:duration=shortest[pre_out];"
                f"[pre_out]volume=volume={preset_volume}[out]"
            )
        else:
            fc_parts.append(f"[{audio_labels[0]}]volume=volume={preset_volume}[out]")

        cmd += ["-filter_complex", ";".join(fc_parts),
                "-map", "[out]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]
        return cmd

    # ----------------------------------------------------------------
    # Pipe threads (shared by both modes)
    # ----------------------------------------------------------------

    def pipe_reader_thread(self, stdout_pipe, buffer_size):
        try:
            while True:
                chunk = stdout_pipe.read(buffer_size)
                if not chunk:
                    break
                self.chunk_queue.put(chunk)
        except Exception as e:
            print(f"[ADALM2000_univ] Reader thread error: {e}")
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
                    print(f"[ADALM2000_univ] pusher: ao is None, chunk len={len(chunk)}")
        except Exception as e:
            print(f"[ADALM2000_univ] Pusher thread error: {e}")

    # ----------------------------------------------------------------
    # ADALM2000 hardware initialisation (shared)
    # ----------------------------------------------------------------

    def _init_adalm(self, SRDAC, OSR, TEST):
        """Open ADALM2000 context, configure analog output. Returns (ctx, ao) or emits SigError."""
        print("[ADALM2000_univ] checking for ADALM2000")
        self.mutex.lock()
        errorstate, value = self._check_ready_ADALM()
        self.mutex.unlock()

        if errorstate:
            if not TEST:
                self.SigError.emit(value)
                self.SigFinished.emit()
                return None, None
            print(f"[ADALM2000_univ] TEST mode – ADALM2000 not required ({value})")
            return None, None

        ctx = value
        ao  = None
        if not TEST:
            channel = 0
            ao = ctx.getAnalogOut()
            ao.setSampleRate(channel, SRDAC)
            ao.setOversamplingRatio(channel, int(OSR))
            ao.enableChannel(channel, True)
            ao.setKernelBuffersCount(0, 128)
            ao.setCyclic(False)
        return ctx, ao

    def _close_adalm(self, ctx, ao, TEST):
        if ao is not None:
            try:
                ao.push(0, [0.0] * 5000)
                time.sleep(0.01)
                ao.enableChannel(0, False)
                ao.setSampleRate(0, 0)
            except Exception as e:
                print(f"[ADALM2000_univ] Error closing ADALM ao: {e}")
        print("[ADALM2000_univ] closing ctx")
        if not TEST and ctx is not None:
            libm2k.contextClose(ctx)

    def _check_ready_ADALM(self):
        errorstate = False
        value      = ""
        try:
            ctx = libm2k.m2kOpen()
            ctx.calibrateDAC()
            value = ctx
        except Exception as e:
            value      = f"ADALM2000 not ready: {e}"
            errorstate = True
        return errorstate, value

    # ----------------------------------------------------------------
    # Main entry point
    # ----------------------------------------------------------------

    def play_loop_filelist(self):
        filenames     = self.get_filename()
        config        = self.get_configparameters()
        gain          = self.get_gain()
        TEST          = self.get_TEST()
        self.stopix   = False
        self.set_fileclose(False)

        # ---- Read config_wizard.yaml ----
        _audioplaylist = ""
        _audio_rate    = 25000
        _mix_level     = 1.0
        _base_port     = 2234
        _mod_index     = 0.9
        _op_mode       = ""
        _ffmpeg_path   = self.ffmpeg_path
        _use_agc_cpp   = False
        try:
            with open(os.path.join(os.getcwd(), "config_wizard.yaml"), "r") as f:
                _cfg = yaml.safe_load(f) or {}
            _audioplaylist = str(_cfg.get("audioplaylist",  "")).strip()
            _audio_rate    = int(_cfg.get("audio_rate_hz",  25000))
            _mix_level     = float(_cfg.get("audio_mix_level", 1.0))
            _base_port     = int(_cfg.get("adalm_audio_base_port", 2234))
            _mod_index     = float(_cfg.get("audio_mod_index", 0.9))
            _op_mode       = str(_cfg.get("last_modulator_type", "")).strip()
            _ffmpeg_path   = _resolve_ffmpeg_bin(str(_cfg.get("ffmpeg_path", "")))
            _use_agc_cpp   = bool(_cfg.get("autoAGC_DspWorker", False))
            if _op_mode == "band_only":
                _audioplaylist = ""
                print("[ADALM2000_univ] operating mode = band_only: audio overlay suppressed")
        except Exception as e:
            print(f"[ADALM2000_univ] config read error: {e}")

        _stations = parse_audio_playlist(_audioplaylist) if _audioplaylist else []
        has_audio = bool(_stations)
        has_iq    = bool(filenames) and filenames[0] not in ("", "no_file.dat")

        if _op_mode == "audio_only" or config.get("synth_only", False):
            has_iq = False

        print(f"[ADALM2000_univ] mode: has_iq={has_iq}, has_audio={has_audio}, op={_op_mode}")

        if has_iq:
            self._run_iq_mode(
                filenames, _stations, config, gain, TEST,
                _audio_rate, _mix_level, _base_port, _mod_index, _ffmpeg_path, _use_agc_cpp,
            )
        elif has_audio:
            self._run_audioonly_mode(
                _stations, config, gain, TEST,
                _audio_rate, _mix_level, _base_port, _mod_index, _ffmpeg_path, _use_agc_cpp,
            )
        else:
            if _op_mode == "audio_only":
                self.SigError.emit(
                    "ADALM2000_universal (audio_only): Keine Audio-Playlist konfiguriert.\n"
                    "Bitte 'audioplaylist' in config_wizard.yaml setzen (Pfad zur Stations-CSV)."
                )
            else:
                self.SigError.emit(
                    "ADALM2000_universal: Weder IQ-File noch Audio-Playlist konfiguriert.\n"
                    "Bitte IQ-WAV-Datei öffnen und/oder 'audioplaylist' in config_wizard.yaml setzen."
                )
            self.SigFinished.emit()

    # ----------------------------------------------------------------
    # Mode A: IQ file (+ optional audio overlay)
    # ----------------------------------------------------------------

    def _run_iq_mode(self, filenames, stations, config, gain, TEST,
                     audio_rate, mix_level, base_port, mod_index, ffmpeg_bin, use_agc):
        self._run_cpp_mode(
            audio_only=False,
            filenames=filenames, stations=stations,
            config=config, gain=gain, TEST=TEST,
            audio_rate=audio_rate, mix_level=mix_level,
            base_port=base_port, mod_index=mod_index, ffmpeg_bin=ffmpeg_bin, use_agc=use_agc,
        )

    # ----------------------------------------------------------------
    # Mode B: pure AM synthesis (no IQ file)
    # ----------------------------------------------------------------

    def _run_audioonly_mode(self, stations, config, gain, TEST,
                            audio_rate, mix_level, base_port, mod_index, ffmpeg_bin, use_agc):
        self._run_cpp_mode(
            audio_only=True,
            filenames=[], stations=stations,
            config=config, gain=gain, TEST=TEST,
            audio_rate=audio_rate, mix_level=mix_level,
            base_port=base_port, mod_index=mod_index, ffmpeg_bin=ffmpeg_bin, use_agc=use_agc,
        )

    # ----------------------------------------------------------------
    # C++ DSP engine (libdspadlm.so) — shared by Mode A and Mode B
    # ----------------------------------------------------------------

    def _run_cpp_mode(self, audio_only, filenames, stations, config, gain, TEST,
                      audio_rate, mix_level, base_port, mod_index, ffmpeg_bin, use_agc=False):
        SRDAC = 75_000_000

        if audio_only:
            max_carrier   = max(s["freq_hz"] for s in stations)
            max_bw        = max(s["bw_hz"]   for s in stations)
            OSR           = self.maximize_OSR(SRDAC, max_carrier, max_bw)
            lo_shift      = 0.0
        else:
            sampling_rate = config["irate"]
            lo_shift      = config["ifreq"]
            OSR           = self.maximize_OSR(SRDAC, lo_shift, sampling_rate)

        SRAdalm = SRDAC / OSR
        print(f"[ADALM2000_univ] {'audio_only' if audio_only else 'IQ'} mode: "
              f"SRAdalm={SRAdalm/1e6:.3f} MS/s, OSR={OSR}")

        for sta in stations:
            if sta["freq_hz"] + sta["bw_hz"] / 2 > SRAdalm / 2:
                self.SigError.emit(
                    f"ADALM2000_universal: Station '{sta['name']}' @ "
                    f"{sta['freq_hz']/1e3:.1f} kHz + BW/2 exceeds Nyquist "
                    f"({SRAdalm/2/1e3:.1f} kHz)."
                )
                self.SigFinished.emit()
                return

        if TEST:
            print("[ADALM2000_univ] TEST mode: dry run 5 s")
            time.sleep(5)
            self.set_fileclose(True)
            self.SigFinished.emit()
            return

        if _lib_adlm is None:
            self.SigError.emit(
                "ADALM2000_universal: libdspadlm.so nicht gefunden.\n"
                "Bitte 'make' im Verzeichnis ADALM2000_universal ausführen."
            )
            self.SigFinished.emit()
            return

        ctx, ao = self._init_adalm(SRDAC, OSR, TEST)
        if ctx is None and not TEST:
            return

        audio_channels = []
        if stations:
            audio_channels = self._start_audio_streams(
                stations, base_port, audio_rate, mod_index, ffmpeg_bin
            )
            time.sleep(1.0)
            print(f"[ADALM2000_univ] {len(audio_channels)} audio channel(s) started")

        handle = _lib_adlm.dsp_adlm_create()
        if not handle:
            self.SigError.emit("ADALM2000_universal: dsp_adlm_create() returned NULL")
            self._stop_audio_streams()
            self._close_adalm(ctx, ao, TEST)
            self.SigFinished.emit()
            return

        try:
            fnames_bytes = [f.encode() for f in (filenames or [])]
            if fnames_bytes:
                fnames_arr = (ctypes.c_char_p * len(fnames_bytes))(*fnames_bytes)
            else:
                fnames_arr = None

            r = _lib_adlm.dsp_adlm_configure(
                handle,
                ctypes.c_float(SRAdalm),
                ctypes.c_float(lo_shift),
                ctypes.c_float(gain),
                ctypes.c_int(1 if use_agc else 0),
                ctypes.c_int(1 if audio_only else 0),
                fnames_arr,
                ctypes.c_int(len(fnames_bytes)),
            )
            if r != 0:
                self.SigError.emit(f"ADALM2000_universal: dsp_adlm_configure failed ({r})")
                _lib_adlm.dsp_adlm_destroy(handle)
                self._stop_audio_streams()
                self._close_adalm(ctx, ao, TEST)
                self.SigFinished.emit()
                return

            if audio_channels:
                n = len(audio_channels)
                ch_arr = (_DspAudioChannel * n)()
                for idx, ch in enumerate(audio_channels):
                    # Schröder phase: minimises crest factor of composite AM signal
                    sp = float(idx * (idx + 1)) / n * 3.14159265
                    ch_arr[idx].freq_hz         = ch["freq_hz"]
                    ch_arr[idx].bandwidth_hz    = ch["bw_hz"]
                    ch_arr[idx].name            = ch["name"][:63].encode()
                    ch_arr[idx].udp_port        = ch["udp_port"]
                    ch_arr[idx].mod_index       = ch.get("mod_index", mod_index)
                    ch_arr[idx].schroeder_phase = sp
                _lib_adlm.dsp_adlm_configure_audio(
                    handle, ch_arr, ctypes.c_int(n),
                    ctypes.c_float(audio_rate), ctypes.c_float(mix_level),
                )
                _lib_adlm.dsp_adlm_prefill_audio(handle, ctypes.c_int(500))

            # Wire callbacks
            _CB_MONITOR  = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_float),
                                            ctypes.c_int, ctypes.c_void_p)
            _CB_NEXTFILE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)
            _CB_FINISHED = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
            _CB_ERROR    = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)

            def _on_monitor(data_ptr, n, _ud):
                try:
                    arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
                    self.set_data(arr)
                    self.SigIncrementCurTime.emit()
                except Exception as _exc:
                    print(f"[ADALM2000_univ] _on_monitor exception: {_exc}", flush=True)

            def _on_nextfile(path, _ud):
                if path:
                    self.SigNextfile.emit(path.decode(errors="replace"))

            def _on_finished(_ud):
                pass  # handled by pull returning -1

            def _on_error(msg, _ud):
                if msg:
                    self.SigError.emit(msg.decode(errors="replace"))

            _mon_cb = _CB_MONITOR(_on_monitor)
            _nxt_cb = _CB_NEXTFILE(_on_nextfile)
            _fin_cb = _CB_FINISHED(_on_finished)
            _err_cb = _CB_ERROR(_on_error)

            _lib_adlm.dsp_adlm_set_monitor_cb (handle, _mon_cb, None)
            _lib_adlm.dsp_adlm_set_nextfile_cb(handle, _nxt_cb, None)
            _lib_adlm.dsp_adlm_set_finished_cb(handle, _fin_cb, None)
            _lib_adlm.dsp_adlm_set_error_cb   (handle, _err_cb, None)

            r = _lib_adlm.dsp_adlm_start(handle)
            if r != 0:
                self.SigError.emit(f"ADALM2000_universal: dsp_adlm_start failed ({r})")
                _lib_adlm.dsp_adlm_destroy(handle)
                self._stop_audio_streams()
                self._close_adalm(ctx, ao, TEST)
                self.SigFinished.emit()
                return

            # Pull loop: DSP thread → ring → Python → libm2k
            # BLOCK = 4 × 65536: larger push blocks reduce sensitivity to OS
            # scheduling jitter and USB timing spikes that caused IQ-mode stutter.
            BLOCK    = 262144
            pull_buf = (ctypes.c_int16 * BLOCK)()
            out_arr  = array.array('h', [0] * BLOCK)
            stopev   = threading.Event()
            done_ev  = threading.Event()

            def _push_thread():
                import sys as _sys
                _push_count = 0
                _max_push_ms = 0.0
                _last_diag = time.time()
                _paused_prev = False

                while not stopev.is_set():
                    if self.get_pause():
                        if not _paused_prev:
                            _lib_adlm.dsp_adlm_set_pause(handle, ctypes.c_int(1))
                            _paused_prev = True
                        time.sleep(0.05)
                        continue
                    if _paused_prev:
                        _lib_adlm.dsp_adlm_set_pause(handle, ctypes.c_int(0))
                        _paused_prev = False
                    n = _lib_adlm.dsp_adlm_pull(handle, pull_buf, BLOCK)
                    if n < 0:
                        break
                    if n > 0 and ao is not None:
                        ctypes.memmove(out_arr.buffer_info()[0], pull_buf, n * 2)
                        _t0 = time.perf_counter()
                        try:
                            ao.pushRaw(0, out_arr if n == BLOCK else out_arr[:n])
                        except Exception as e:
                            print(f"[ADALM2000_univ] pushRaw error: {e}", flush=True)
                            break
                        _dt = (time.perf_counter() - _t0) * 1000.0
                        _push_count += 1
                        if _dt > _max_push_ms:
                            _max_push_ms = _dt
                        _now = time.time()
                        if _now - _last_diag >= 5.0:
                            print(
                                f"[ADALM2000_univ] push: n={_push_count}  "
                                f"max_pushRaw={_max_push_ms:.0f}ms  BLOCK={BLOCK}",
                                file=_sys.stderr, flush=True
                            )
                            _push_count = 0
                            _max_push_ms = 0.0
                            _last_diag = _now
                done_ev.set()

            push_t = threading.Thread(target=_push_thread, daemon=True)
            push_t.start()

            _last_tick = time.time()
            while not self.stopix:
                if done_ev.wait(timeout=0.1):
                    break
                if not use_agc:
                    _lib_adlm.dsp_adlm_set_gain(handle, ctypes.c_float(self.get_gain()))
                now = time.time()
                if now - _last_tick >= 1.0:
                    self.SigIncrementCurTime.emit()
                    _last_tick = now

            stopev.set()
            _lib_adlm.dsp_adlm_stop(handle)
            push_t.join(timeout=5.0)

        finally:
            _lib_adlm.dsp_adlm_destroy(handle)

        self._stop_audio_streams()
        self._close_adalm(ctx, ao, TEST)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ----------------------------------------------------------------
    # Format helpers
    # ----------------------------------------------------------------

    def _format_params(self, format_tag):
        """Return (preset_volume, formatstring, DATABLOCKSIZE) or (None, None, None) on error."""
        if format_tag[0] == 1:  # PCM
            if format_tag[2] == 16:
                return 5, "s16le", self.DATABLOCKSIZE_BASIC
            elif format_tag[2] == 24:
                return 100, "s24le", 4096 * 256 * 24
            else:
                return 1, "s32le", self.DATABLOCKSIZE_BASIC
        else:  # IEEE float
            if format_tag[2] == 32:
                return 1, "f32le", self.DATABLOCKSIZE_BASIC
            elif format_tag[2] == 16:
                return 200, "f16le", self.DATABLOCKSIZE_BASIC
            else:
                self.SigError.emit(f"Format not supported: {format_tag[2]}")
                self.SigFinished.emit()
                return None, None, None

    # ----------------------------------------------------------------
    def rec_loop(self):
        return
