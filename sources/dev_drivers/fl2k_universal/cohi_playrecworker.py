"""
cohi_playrecworker.py  –  fl2k_universal
COHIWizard universal worker for the fl2k USB-VGA DAC.

Implements the 4-layer architecture (Schritt 1).  One worker handles all
three input modes; the backend C++ library is selected at runtime:

  Mode A  IQ-file + optional audio overlay
          filenames  non-empty
          library    libdspfl2k.so  (from fl2k_fast_plus)

  Mode B  Pure AM audio synthesis (no IQ file)
          audioplaylist configured, filenames empty
          library    libdspflmod.so  (from fl2k_fast_modulator)

  Error   Neither file nor playlist → SigError emitted

Library search order for each .so:
  1. fl2k_universal/  (own directory – place rebuilt .so here)
  2. fl2k_fast_plus/  or  fl2k_fast_modulator/  sibling directories

config_wizard.yaml keys used:
  autoAGC_DspWorker       bool   (default False)
  gain_correction_fl2k_C  float  (default 1.0)
  audioplaylist           str    path to CSV; empty / absent → overlay disabled
  audio_rate_hz           int    PCM sample rate for ffmpeg (default 25000)
  audio_mix_level         float  amplitude weight (default 1.0)
  audio_base_port         int    first UDP port (default 1234)
  audio_mod_index         float  AM modulation index 0–1 (default 0.9)
  flmod_baseband_rate     float  optional baseband rate override in Hz (default 0 = auto)
  ffmpeg_path             str    ffmpeg binary (default 'ffmpeg')
"""

import csv
import ctypes
import os
import subprocess
import threading
import time
from urllib.parse import urlparse, urlunparse

import numpy as np
import psutil
import yaml
from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Library loaders
# ---------------------------------------------------------------------------

def _setup_lib_plus(lib, libpath):
    """Wire argtypes/restype for libdspfl2k.so."""
    VoidP  = ctypes.c_void_p
    Int    = ctypes.c_int
    Float  = ctypes.c_float
    CharP  = ctypes.c_char_p
    FloatP = ctypes.POINTER(ctypes.c_float)

    lib.dsp_fl2k_create.restype  = VoidP
    lib.dsp_fl2k_create.argtypes = []
    lib.dsp_fl2k_destroy.restype  = None
    lib.dsp_fl2k_destroy.argtypes = [VoidP]
    lib.dsp_fl2k_configure.restype  = Int
    lib.dsp_fl2k_configure.argtypes = [
        VoidP, Float, Float, Float, Int,
        ctypes.POINTER(ctypes.c_char_p), Int,
    ]

    class DspAudioChannel(ctypes.Structure):
        _fields_ = [
            ("freq_hz",         ctypes.c_float),
            ("bandwidth_hz",    ctypes.c_float),
            ("name",            ctypes.c_char * 64),
            ("udp_port",        ctypes.c_int),
            ("mod_index",       ctypes.c_float),
            ("schroeder_phase", ctypes.c_float),
        ]
    lib._DspAudioChannel = DspAudioChannel

    try:
        _fn_addr = ctypes.cast(lib.dsp_fl2k_configure_audio, ctypes.c_void_p).value
        lib._has_audio_api = bool(_fn_addr)
    except (AttributeError, ctypes.ArgumentError, TypeError, OSError):
        lib._has_audio_api = False

    if lib._has_audio_api:
        lib.dsp_fl2k_configure_audio.restype  = Int
        lib.dsp_fl2k_configure_audio.argtypes = [
            VoidP,
            ctypes.POINTER(DspAudioChannel),
            Int, Float, Float,
        ]
        lib.dsp_fl2k_prefill_audio.restype  = None
        lib.dsp_fl2k_prefill_audio.argtypes = [VoidP, Int]
    else:
        print(f"[fl2k_universal] WARNING: dsp_fl2k_configure_audio not in {libpath} – audio overlay unavailable")

    MonitorCB  = ctypes.CFUNCTYPE(None, FloatP, Int, VoidP)
    ProgressCB = ctypes.CFUNCTYPE(None, Float, VoidP)
    FinishedCB = ctypes.CFUNCTYPE(None, VoidP)
    ErrorCB    = ctypes.CFUNCTYPE(None, CharP, VoidP)
    NextfileCB = ctypes.CFUNCTYPE(None, CharP, VoidP)

    lib.dsp_fl2k_set_monitor_cb.restype   = None
    lib.dsp_fl2k_set_monitor_cb.argtypes  = [VoidP, MonitorCB,  VoidP]
    lib.dsp_fl2k_set_progress_cb.restype  = None
    lib.dsp_fl2k_set_progress_cb.argtypes = [VoidP, ProgressCB, VoidP]
    lib.dsp_fl2k_set_finished_cb.restype  = None
    lib.dsp_fl2k_set_finished_cb.argtypes = [VoidP, FinishedCB, VoidP]
    lib.dsp_fl2k_set_error_cb.restype     = None
    lib.dsp_fl2k_set_error_cb.argtypes    = [VoidP, ErrorCB,    VoidP]
    lib.dsp_fl2k_set_nextfile_cb.restype  = None
    lib.dsp_fl2k_set_nextfile_cb.argtypes = [VoidP, NextfileCB, VoidP]

    lib.dsp_fl2k_start.restype      = Int
    lib.dsp_fl2k_start.argtypes     = [VoidP]
    lib.dsp_fl2k_stop.restype       = None
    lib.dsp_fl2k_stop.argtypes      = [VoidP]
    lib.dsp_fl2k_set_pause.restype  = None
    lib.dsp_fl2k_set_pause.argtypes = [VoidP, Int]
    lib.dsp_fl2k_set_gain.restype   = None
    lib.dsp_fl2k_set_gain.argtypes  = [VoidP, Float]
    lib.dsp_fl2k_is_running.restype  = Int
    lib.dsp_fl2k_is_running.argtypes = [VoidP]
    lib.dsp_fl2k_check_device.restype  = Int
    lib.dsp_fl2k_check_device.argtypes = []
    lib.dsp_fl2k_seek.restype  = None
    lib.dsp_fl2k_seek.argtypes = [VoidP, ctypes.c_int64, Int]

    lib._MonitorCB  = MonitorCB
    lib._ProgressCB = ProgressCB
    lib._FinishedCB = FinishedCB
    lib._ErrorCB    = ErrorCB
    lib._NextfileCB = NextfileCB


def _setup_lib_mod(lib, libpath):
    """Wire argtypes/restype for libdspflmod.so."""
    VoidP  = ctypes.c_void_p
    Int    = ctypes.c_int
    Float  = ctypes.c_float
    CharP  = ctypes.c_char_p
    FloatP = ctypes.POINTER(ctypes.c_float)

    lib.dsp_flmod_create.restype  = VoidP
    lib.dsp_flmod_create.argtypes = []
    lib.dsp_flmod_destroy.restype  = None
    lib.dsp_flmod_destroy.argtypes = [VoidP]
    lib.dsp_flmod_configure.restype  = Int
    lib.dsp_flmod_configure.argtypes = [VoidP, Float, Float, Float, Float, Int]

    class DspFLModChannel(ctypes.Structure):
        _fields_ = [
            ("freq_hz",      ctypes.c_float),
            ("bandwidth_hz", ctypes.c_float),
            ("name",         ctypes.c_char * 64),
            ("udp_port",     ctypes.c_int),
            ("mod_index",    ctypes.c_float),
        ]
    lib._DspFLModChannel = DspFLModChannel

    lib.dsp_flmod_configure_channels.restype  = Int
    lib.dsp_flmod_configure_channels.argtypes = [
        VoidP,
        ctypes.POINTER(DspFLModChannel),
        Int, Float, Float,
    ]
    lib.dsp_flmod_prefill.restype  = None
    lib.dsp_flmod_prefill.argtypes = [VoidP, Int]

    MonitorCB  = ctypes.CFUNCTYPE(None, FloatP, Int, VoidP)
    FinishedCB = ctypes.CFUNCTYPE(None, VoidP)
    ErrorCB    = ctypes.CFUNCTYPE(None, CharP, VoidP)

    lib.dsp_flmod_set_monitor_cb.restype   = None
    lib.dsp_flmod_set_monitor_cb.argtypes  = [VoidP, MonitorCB,  VoidP]
    lib.dsp_flmod_set_finished_cb.restype  = None
    lib.dsp_flmod_set_finished_cb.argtypes = [VoidP, FinishedCB, VoidP]
    lib.dsp_flmod_set_error_cb.restype     = None
    lib.dsp_flmod_set_error_cb.argtypes    = [VoidP, ErrorCB,    VoidP]

    lib.dsp_flmod_start.restype      = Int
    lib.dsp_flmod_start.argtypes     = [VoidP]
    lib.dsp_flmod_stop.restype       = None
    lib.dsp_flmod_stop.argtypes      = [VoidP]
    lib.dsp_flmod_set_pause.restype  = None
    lib.dsp_flmod_set_pause.argtypes = [VoidP, Int]
    lib.dsp_flmod_set_gain.restype   = None
    lib.dsp_flmod_set_gain.argtypes  = [VoidP, Float]
    lib.dsp_flmod_is_running.restype  = Int
    lib.dsp_flmod_is_running.argtypes = [VoidP]
    lib.dsp_flmod_check_device.restype  = Int
    lib.dsp_flmod_check_device.argtypes = []

    lib._MonitorCB  = MonitorCB
    lib._FinishedCB = FinishedCB
    lib._ErrorCB    = ErrorCB


def _load_lib_plus() -> "ctypes.CDLL | None":
    """Load libdspfl2k.so – own dir first, then fl2k_fast_plus sibling."""
    import platform
    here     = os.path.dirname(os.path.abspath(__file__))
    _libname = "libdspfl2k.dll" if platform.system() == "Windows" else "libdspfl2k.so"
    candidates = [
        os.path.join(here, _libname),
        os.path.join(here, "..", "fl2k_fast_plus", _libname),
    ]
    if platform.system() == "Windows":
        try:
            os.add_dll_directory(here)
        except (AttributeError, OSError):
            pass
    for libpath in candidates:
        if os.path.isfile(libpath):
            try:
                lib = ctypes.CDLL(libpath)
                _setup_lib_plus(lib, libpath)
                print(f"[fl2k_universal] Loaded libdspfl2k from {libpath}")
                return lib
            except OSError as exc:
                print(f"[fl2k_universal] Cannot load {libpath}: {exc}")
    print(f"[fl2k_universal] libdspfl2k.so not found – searched: {candidates}")
    return None


def _load_lib_mod() -> "ctypes.CDLL | None":
    """Load libdspflmod.so – own dir first, then fl2k_fast_modulator sibling."""
    import platform
    here     = os.path.dirname(os.path.abspath(__file__))
    _libname = "libdspflmod.dll" if platform.system() == "Windows" else "libdspflmod.so"
    candidates = [
        os.path.join(here, _libname),
        os.path.join(here, "..", "fl2k_fast_modulator", _libname),
    ]
    if platform.system() == "Windows":
        try:
            os.add_dll_directory(here)
        except (AttributeError, OSError):
            pass
    for libpath in candidates:
        if os.path.isfile(libpath):
            try:
                lib = ctypes.CDLL(libpath)
                _setup_lib_mod(lib, libpath)
                print(f"[fl2k_universal] Loaded libdspflmod from {libpath}")
                return lib
            except OSError as exc:
                print(f"[fl2k_universal] Cannot load {libpath}: {exc}")
    print(f"[fl2k_universal] libdspflmod.so not found – searched: {candidates}")
    return None


_LIB_PLUS = _load_lib_plus()
_LIB_MOD  = _load_lib_mod()

# Serialize fl2k device access across worker instances (both libs use same USB dongle).
_device_free = threading.Event()
_device_free.set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Turn ffmpeg_path config entry into an executable path."""
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
# CSV playlist parser
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
                    print(f"[fl2k_universal] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[fl2k_universal] CSV line {lineno}: cannot parse "
                          f"'{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[fl2k_universal] Cannot read playlist '{csv_path}': {exc}")
    return stations


# ---------------------------------------------------------------------------
# Seek proxy
# ---------------------------------------------------------------------------

class _SeekProxy:
    def __init__(self, handle, lib):
        self._handle = handle
        self._lib    = lib

    def seek(self, offset, whence=0):
        self._lib.dsp_fl2k_seek(
            self._handle, ctypes.c_int64(offset), ctypes.c_int(whence)
        )


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """
    Universal fl2k worker – three operational modes selected at runtime:

      IQ-file present              → libdspfl2k.so  (Mode A: IQ ± audio overlay)
      No IQ-file, playlist set     → libdspflmod.so (Mode B: pure AM synthesis)
      Neither configured           → SigError

    __slots__ layout (compatible with all COHIWizard drivers):
      0  filename          – list of WAV file paths (may be empty for Mode B)
      1  timescaler        – bytes/second (informational)
      2  TEST              – True → dry-run mode
      3  pause             – True → mute
      4  fileHandle        – seek proxy (Mode A) or None (Mode B)
      5  data              – 1024-float monitor window
      6  gain              – amplitude scale factor [0…2]
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

    def __init__(self, sdrcontrol_inst, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix         = False
        self.DATASHOWSIZE   = 1024
        self.mutex          = QMutex()
        self.stemlabcontrol = sdrcontrol_inst
        self._handle        = None
        self._ffmpeg_procs  = []
        self._concat_files  = []

    # ---------------------------------------------------------------- accessors
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
    # Audio stream management (shared by both modes)
    # ----------------------------------------------------------------
    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        channels = []
        N_total = len(stations)
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
                    print(f"[fl2k_universal] Cannot read m3u '{url}': {_exc}")

                _entries = [e for e in _entries if os.path.isfile(e)]
                if not _entries:
                    print(f"[fl2k_universal] m3u '{url}': no valid files – skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="fl2ku_concat_",
                    delete=False, encoding="utf-8"
                )
                _cf.write("ffconcat version 1.0\n")
                for _ in range(200):
                    for _e in _entries:
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
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"fl2ku_ffmpeg_ch{idx}.log"

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
                print(f"[fl2k_universal] ffmpeg ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz']/1e3:.1f} kHz -> UDP {port} "
                      f"(PID {proc.pid}), log -> {_logfile}")
                self._ffmpeg_procs.append(proc)
                schroeder_phase = np.pi * idx * (idx + 1) / max(1, N_total)
                channels.append({
                    "freq_hz":         sta["freq_hz"],
                    "bw_hz":           bw_hz,
                    "name":            name,
                    "udp_port":        port,
                    "mod_index":       mod_index,
                    "schroeder_phase": schroeder_phase,
                })
            except OSError as exc:
                print(f"[fl2k_universal] Failed to start ffmpeg for '{name}': {exc}")

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
        print("[fl2k_universal] Audio streams stopped.")

    # ----------------------------------------------------------------
    # Main entry point
    # ----------------------------------------------------------------
    def play_loop_filelist(self):
        """Serialize device access, then dispatch to implementation."""
        _device_free.wait()
        _device_free.clear()
        try:
            self._play_loop_filelist_impl()
        finally:
            _device_free.set()

    def _play_loop_filelist_impl(self):
        import faulthandler, sys
        faulthandler.enable(file=sys.stderr)

        filenames = self.get_filename()
        config    = self.get_configparameters()
        gain      = self.get_gain()
        TEST      = self.get_TEST()
        self.stopix = False
        self.set_fileclose(False)

        # ---- Read config_wizard.yaml ---------------------------------
        _use_agc_cpp   = False
        _gain_corr     = 1.0
        _audioplaylist = ""
        _audio_rate    = 25000
        _mix_level     = 1.0
        _base_port     = 1234
        _mod_index     = 0.9
        _bb_rate_yaml  = 0.0
        _ffmpeg_bin    = "ffmpeg"
        try:
            with open("config_wizard.yaml", "r") as _f:
                _cfg = yaml.safe_load(_f) or {}
            _use_agc_cpp   = bool(_cfg.get("autoAGC_DspWorker",       False))
            _gain_corr     = float(_cfg.get("gain_correction_fl2k_C", 1.0))
            _audioplaylist = str(_cfg.get("audioplaylist",            "")).strip()
            _audio_rate    = int(_cfg.get("audio_rate_hz",            25000))
            _mix_level     = float(_cfg.get("audio_mix_level",        1.0))
            _base_port     = int(_cfg.get("audio_base_port",          1234))
            _mod_index     = float(_cfg.get("audio_mod_index",        0.9))
            _bb_rate_yaml  = float(_cfg.get("flmod_baseband_rate",    0.0))
            _ffmpeg_bin    = _resolve_ffmpeg_bin(str(_cfg.get("ffmpeg_path", "")))
        except Exception as _e:
            print(f"[fl2k_universal] config_wizard.yaml read error: {_e}; using defaults")

        has_iq    = bool(filenames)
        _stations = parse_audio_playlist(_audioplaylist) if _audioplaylist else []
        has_audio = bool(_stations)

        print(f"[fl2k_universal] mode: has_iq={has_iq}, has_audio={has_audio}")

        if has_iq:
            if _LIB_PLUS is None:
                self.SigError.emit(
                    "libdspfl2k.so not found.\n"
                    "Build it with:  cd dev_drivers/fl2k_fast_plus && make"
                )
                self.SigFinished.emit()
                return
            self._run_fl2k_plus_path(
                filenames, _stations, config, gain, TEST,
                _use_agc_cpp, _gain_corr, _audioplaylist,
                _audio_rate, _mix_level, _base_port, _mod_index, _ffmpeg_bin,
            )
        elif has_audio:
            if _LIB_MOD is None:
                self.SigError.emit(
                    "libdspflmod.so not found.\n"
                    "Build it with:  cd dev_drivers/fl2k_fast_modulator && make"
                )
                self.SigFinished.emit()
                return
            self._run_flmod_path(
                _stations, config, gain, TEST,
                _use_agc_cpp, _gain_corr,
                _audio_rate, _mix_level, _base_port, _mod_index, _ffmpeg_bin,
                _bb_rate_yaml,
            )
        else:
            self.SigError.emit(
                "fl2k_universal: Weder IQ-File noch Audio-Playlist konfiguriert.\n"
                "Bitte IQ-WAV-Datei öffnen und/oder 'audioplaylist' in config_wizard.yaml setzen."
            )
            self.SigFinished.emit()

    # ----------------------------------------------------------------
    # Mode A: IQ file path (libdspfl2k.so)
    # ----------------------------------------------------------------
    def _run_fl2k_plus_path(
        self, filenames, stations, config, gain, TEST,
        use_agc_cpp, gain_corr, audioplaylist,
        audio_rate, mix_level, base_port, mod_index, ffmpeg_bin,
    ):
        LIB = _LIB_PLUS

        sampling_rate = config["irate"]
        lo_shift      = config["ifreq"]

        tSR = 10_000_000 * (1 + int((lo_shift + sampling_rate / 2) * 2 / 10_000_000))
        tSR = min(100_000_000, tSR)

        ratio = tSR / sampling_rate
        if sampling_rate > 500_000:
            import math
            if math.log2(ratio) % 1 != 0:
                self.SigInfomessage.emit(
                    f"target_rate / source_rate = {ratio:.4f} is not a power of 2. "
                    "Playback artefacts may occur > 500 kS/s."
                )

        if TEST:
            self._run_test_mode(filenames, sampling_rate)
            return

        # Device check
        self.mutex.lock()
        _dev_ok = False
        for _ in range(5):
            if LIB.dsp_fl2k_check_device() == 0:
                _dev_ok = True
                break
            time.sleep(0.3)
        if not _dev_ok:
            self.SigError.emit("fl2k device not found. Check the USB-VGA dongle connection.")
            self.SigFinished.emit()
            self.mutex.unlock()
            return
        self.mutex.unlock()

        # Audio overlay
        _audio_active = False
        _channels     = []
        if stations:
            _audio_active = True
            print(f"[fl2k_universal] Audio overlay: {len(stations)} station(s)")
            _channels = self._start_audio_streams(
                stations, base_port, audio_rate, mod_index, ffmpeg_bin
            )

        # Create C++ worker
        handle = LIB.dsp_fl2k_create()
        if not handle:
            self.SigError.emit("dsp_fl2k_create() returned NULL")
            self._stop_audio_streams()
            self.SigFinished.emit()
            return
        self._handle = handle
        self.set_fileHandle(_SeekProxy(handle, LIB))

        # Configure IQ
        fname_array = (ctypes.c_char_p * len(filenames))(
            *[f.encode() for f in filenames]
        )
        LIB.dsp_fl2k_configure(
            handle,
            ctypes.c_float(tSR),
            ctypes.c_float(float(lo_shift)),
            ctypes.c_float(float(gain * gain_corr)),
            ctypes.c_int(1 if use_agc_cpp else 0),
            fname_array,
            ctypes.c_int(len(filenames)),
        )

        # Configure audio overlay
        if _audio_active and _channels and not getattr(LIB, "_has_audio_api", False):
            self.SigError.emit(
                "Audio overlay deaktiviert: libdspfl2k.so enthält keine "
                "dsp_fl2k_configure_audio-Funktion. Bitte neu bauen: cd fl2k_fast_plus && make"
            )
            _audio_active = False
        if _audio_active and _channels:
            DspAudioChannel = LIB._DspAudioChannel
            ch_arr = (DspAudioChannel * len(_channels))()
            for i, ch in enumerate(_channels):
                ch_arr[i].freq_hz         = ch["freq_hz"]
                ch_arr[i].bandwidth_hz    = ch["bw_hz"]
                ch_arr[i].name            = ch["name"].encode("utf-8", errors="replace")[:63]
                ch_arr[i].udp_port        = ch["udp_port"]
                ch_arr[i].mod_index       = ch["mod_index"]
                ch_arr[i].schroeder_phase = ch.get("schroeder_phase", 0.0)
            rc = LIB.dsp_fl2k_configure_audio(
                handle, ch_arr,
                ctypes.c_int(len(_channels)),
                ctypes.c_float(float(audio_rate)),
                ctypes.c_float(float(mix_level)),
            )
            if rc != 0:
                self.SigInfomessage.emit(
                    f"dsp_fl2k_configure_audio returned {rc} – overlay disabled."
                )
            else:
                LIB.dsp_fl2k_prefill_audio(handle, ctypes.c_int(5000))

        # Callbacks
        @LIB._MonitorCB
        def _on_monitor(data_ptr, n, _ud):
            try:
                arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
                self.set_data(arr)
                self.SigIncrementCurTime.emit()
            except Exception as exc:
                print(f"[fl2k_universal] _on_monitor: {exc}", flush=True)

        @LIB._ErrorCB
        def _on_error(msg_ptr, _ud):
            try:
                msg = msg_ptr.decode(errors="replace") if msg_ptr else "(null)"
                print(f"[fl2k_universal/plus] C++ error: {msg}", flush=True)
                self.SigError.emit(msg)
            except Exception as exc:
                print(f"[fl2k_universal] _on_error: {exc}", flush=True)

        @LIB._NextfileCB
        def _on_nextfile(path_ptr, _ud):
            try:
                if path_ptr:
                    self.SigNextfile.emit(path_ptr.decode(errors="replace"))
            except Exception as exc:
                print(f"[fl2k_universal] _on_nextfile: {exc}", flush=True)

        @LIB._FinishedCB
        def _on_finished(_ud):
            print("[fl2k_universal/plus] C++ finished callback.", flush=True)

        LIB.dsp_fl2k_set_monitor_cb (handle, _on_monitor,  None)
        LIB.dsp_fl2k_set_error_cb   (handle, _on_error,    None)
        LIB.dsp_fl2k_set_nextfile_cb(handle, _on_nextfile, None)
        LIB.dsp_fl2k_set_finished_cb(handle, _on_finished, None)

        # Start
        rc = LIB.dsp_fl2k_start(handle)
        if rc != 0:
            codes = {-1: "already running", -2: "no files configured", -3: "fl2k device failed to open"}
            self.SigError.emit(f"dsp_fl2k_start failed (code {rc}: {codes.get(rc, '?')})")
            LIB.dsp_fl2k_destroy(handle)
            self._handle = None
            self._stop_audio_streams()
            self.SigFinished.emit()
            return

        # Polling loop
        while LIB.dsp_fl2k_is_running(handle) and not self.stopix:
            LIB.dsp_fl2k_set_pause(handle, 1 if self.get_pause() else 0)
            if not use_agc_cpp:
                LIB.dsp_fl2k_set_gain(
                    handle, ctypes.c_float(float(self.get_gain()) * gain_corr)
                )
            QThread.msleep(50)

        # Cleanup
        LIB.dsp_fl2k_stop(handle)
        LIB.dsp_fl2k_destroy(handle)
        self._handle = None
        self._stop_audio_streams()
        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ----------------------------------------------------------------
    # Mode B: Pure AM synthesis path (libdspflmod.so)
    # ----------------------------------------------------------------
    def _run_flmod_path(
        self, stations, config, gain, TEST,
        use_agc_cpp, gain_corr,
        audio_rate, mix_level, base_port, mod_index, ffmpeg_bin,
        bb_rate_yaml,
    ):
        LIB = _LIB_MOD

        center_freq = float(config.get("ifreq",     0))
        _lo_offset  = float(config.get("LO_offset", 0.0))

        # Baseband rate
        _bb_rate_min = float(config.get("irate", 1_250_000.0))
        if bb_rate_yaml > 0:
            _bb_rate = max(bb_rate_yaml, _bb_rate_min)
        elif stations:
            _s_freqs   = [s["freq_hz"] for s in stations]
            _s_bws     = [s["bw_hz"]   for s in stations]
            _band_span = max(_s_freqs) - min(_s_freqs) if len(stations) > 1 else 0.0
            _min_bb    = (_band_span + 2.0 * abs(_lo_offset) + 2.0 * max(_s_bws)) * 1.2
            _ratio     = min(8, max(1, int(10_000_000 / _min_bb)))
            _bb_rate   = max(10_000_000.0 / _ratio, _bb_rate_min)
            _ratio     = int(10_000_000 / _bb_rate)
            print(f"[fl2k_universal/mod] auto bb_rate: span={_band_span/1e3:.0f} kHz  "
                  f"ratio={_ratio} -> {_bb_rate/1e3:.0f} kHz")
        else:
            _bb_rate = _bb_rate_min

        tSR = 10_000_000 * (1 + int((center_freq + _bb_rate / 2) * 2 / 10_000_000))
        tSR = min(100_000_000, max(10_000_000, tSR))

        print(f"[fl2k_universal/mod] center={center_freq/1e3:.1f} kHz, "
              f"target={tSR/1e6:.0f} MS/s, baseband={_bb_rate/1e6:.3f} MS/s")

        if _bb_rate >= tSR:
            self.SigError.emit(
                f"flmod_baseband_rate ({_bb_rate/1e6:.3f} MS/s) must be "
                f"< target_rate ({tSR/1e6:.0f} MS/s)."
            )
            self.SigFinished.emit()
            return

        if TEST:
            print("[fl2k_universal/mod] TEST mode: simulating for 5 s without hardware.")
            time.sleep(5)
            self.set_fileclose(True)
            self.SigFinished.emit()
            return

        # Device check
        self.mutex.lock()
        _dev_ok = False
        for _ in range(5):
            if LIB.dsp_flmod_check_device() == 0:
                _dev_ok = True
                break
            time.sleep(0.3)
        if not _dev_ok:
            self.SigError.emit("fl2k device not found. Check the USB-VGA dongle connection.")
            self.SigFinished.emit()
            self.mutex.unlock()
            return
        self.mutex.unlock()

        # Start ffmpeg audio streams
        _channels = self._start_audio_streams(
            stations, base_port, audio_rate, mod_index, ffmpeg_bin
        )

        # Apply LO_offset shift to all carriers
        if _channels and _lo_offset != 0.0:
            for ch in _channels:
                ch["freq_hz"] += _lo_offset

        # Create C++ worker
        handle = LIB.dsp_flmod_create()
        if not handle:
            self.SigError.emit("dsp_flmod_create() returned NULL")
            self._stop_audio_streams()
            self.SigFinished.emit()
            return
        self._handle = handle

        # Configure synthesis
        LIB.dsp_flmod_configure(
            handle,
            ctypes.c_float(float(tSR)),
            ctypes.c_float(float(center_freq)),
            ctypes.c_float(float(_bb_rate)),
            ctypes.c_float(float(gain * gain_corr)),
            ctypes.c_int(1 if use_agc_cpp else 0),
        )

        # Configure channels
        if _channels:
            DspFLModChannel = LIB._DspFLModChannel
            ch_arr = (DspFLModChannel * len(_channels))()
            for i, ch in enumerate(_channels):
                ch_arr[i].freq_hz      = ch["freq_hz"]
                ch_arr[i].bandwidth_hz = ch["bw_hz"]
                ch_arr[i].name         = ch["name"].encode("utf-8", errors="replace")[:63]
                ch_arr[i].udp_port     = ch["udp_port"]
                ch_arr[i].mod_index    = ch["mod_index"]
            rc = LIB.dsp_flmod_configure_channels(
                handle, ch_arr,
                ctypes.c_int(len(_channels)),
                ctypes.c_float(float(audio_rate)),
                ctypes.c_float(float(mix_level)),
            )
            if rc != 0:
                self.SigInfomessage.emit(
                    f"dsp_flmod_configure_channels returned {rc} – no audio overlay."
                )
            else:
                LIB.dsp_flmod_prefill(handle, ctypes.c_int(5000))

        # Callbacks
        @LIB._MonitorCB
        def _on_monitor(data_ptr, n, _ud):
            try:
                arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
                self.set_data(arr)
                self.SigIncrementCurTime.emit()
            except Exception as exc:
                print(f"[fl2k_universal/mod] _on_monitor: {exc}", flush=True)

        @LIB._ErrorCB
        def _on_error(msg_ptr, _ud):
            try:
                msg = msg_ptr.decode(errors="replace") if msg_ptr else "(null)"
                print(f"[fl2k_universal/mod] C++ error: {msg}", flush=True)
                self.SigError.emit(msg)
            except Exception as exc:
                print(f"[fl2k_universal/mod] _on_error: {exc}", flush=True)

        @LIB._FinishedCB
        def _on_finished(_ud):
            print("[fl2k_universal/mod] C++ finished callback.", flush=True)

        LIB.dsp_flmod_set_monitor_cb (handle, _on_monitor,  None)
        LIB.dsp_flmod_set_error_cb   (handle, _on_error,    None)
        LIB.dsp_flmod_set_finished_cb(handle, _on_finished, None)

        # Start
        rc = LIB.dsp_flmod_start(handle)
        if rc != 0:
            codes = {-1: "already running", -3: "fl2k device failed to open"}
            self.SigError.emit(
                f"dsp_flmod_start failed (code {rc}: {codes.get(rc, '?')})"
            )
            LIB.dsp_flmod_destroy(handle)
            self._handle = None
            self._stop_audio_streams()
            self.SigFinished.emit()
            return

        # Polling loop
        while LIB.dsp_flmod_is_running(handle) and not self.stopix:
            LIB.dsp_flmod_set_pause(handle, 1 if self.get_pause() else 0)
            if not use_agc_cpp:
                LIB.dsp_flmod_set_gain(
                    handle, ctypes.c_float(float(self.get_gain()) * gain_corr)
                )
            QThread.msleep(50)

        # Cleanup
        LIB.dsp_flmod_stop(handle)
        LIB.dsp_flmod_destroy(handle)
        self._handle = None
        self._stop_audio_streams()
        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ----------------------------------------------------------------
    # Test mode
    # ----------------------------------------------------------------
    def _run_test_mode(self, filenames, sampling_rate):
        DATABLOCKSIZE  = 1024 * 64
        JUNKSIZE       = DATABLOCKSIZE // 2
        junkspersecond = sampling_rate / JUNKSIZE

        for filename in filenames:
            self.SigNextfile.emit(filename)
            try:
                with open(filename, "rb") as fh:
                    fh.seek(216, 1)
                    data  = np.empty(DATABLOCKSIZE, dtype=np.int16)
                    size  = fh.readinto(data)
                    count = 0
                    while size > 0 and not self.stopix:
                        if not self.get_pause():
                            time.sleep(JUNKSIZE / sampling_rate)
                            size = fh.readinto(data)
                            count += 1
                            if count >= junkspersecond:
                                self.set_data(
                                    data[:self.DATASHOWSIZE].astype(np.float32)
                                )
                                self.SigIncrementCurTime.emit()
                                count = 0
                        else:
                            time.sleep(0.1)
                            if self.stopix:
                                break
            except OSError as exc:
                self.SigError.emit(f"Test mode file error: {exc}")
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ----------------------------------------------------------------
    def rec_loop(self):
        return

    def kill_orphan_fl2k(self):
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                cmd  = " ".join(proc.info.get("cmdline") or []).lower()
                if "fl2k_file" in name or "fl2k_file" in cmd:
                    print(f"[fl2k_universal] killing orphan fl2k_file PID {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
