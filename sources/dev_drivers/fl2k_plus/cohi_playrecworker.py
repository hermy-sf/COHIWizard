"""
cohi_playrecworker.py  –  fl2k_plus variant
COHIWizard device-driver worker for the fl2k USB-VGA DAC with AM audio overlay.

Extends fl2k_C with the ability to stream N live web-radio stations as
AM-modulated signals on top of the IQ-file playback.  Each station is
defined in a CSV playlist file whose path is read from config_wizard.yaml
under the key  audioplaylist.

Audio pipeline per station:
  ffmpeg  →  u8 PCM mono @ audio_rate_hz  →  UDP socket  →  libdspfl2k.so
The C++ library reads the UDP streams, AM-modulates each onto its carrier
frequency, and mixes the result into the complex IQ baseband before the
main upsampler.

CSV format (semicolon-separated, first line may be a header):
  Frequenz;Bandbreite;Programmname;URL
  175 kHz;10.0 kHz;Canal Sud;http://91.224.148.160:8000/canalsud-live
  600 kHz;4.5 kHz;Radio Dismuke;"http://74.208.228.126:8020/;stream.mp3"

Units accepted for frequency/bandwidth: Hz, kHz, MHz (case-insensitive).

config_wizard.yaml keys used by this driver:
  autoAGC_DspWorker       bool   (default False)
  gain_correction_fl2k_C  float  (default 1.0)
  audioplaylist           str    path to CSV; empty / absent → overlay disabled
  audio_rate_hz           int    PCM sample rate for ffmpeg (default 25000)
  audio_mix_level         float  amplitude weight, 1.0 = equal power (default 1.0)
  audio_base_port         int    first UDP port, increments per channel (default 1234)
  audio_mod_index         float  AM modulation index 0–1 (default 0.9)
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
# Shared-library loader
# ---------------------------------------------------------------------------

def _load_lib() -> ctypes.CDLL | None:
    import platform
    here     = os.path.dirname(os.path.abspath(__file__))
    _libname = "libdspfl2k.dll" if platform.system() == "Windows" else "libdspfl2k.so"
    libpath  = os.path.join(here, _libname)
    if platform.system() == "Windows":
        # Since Python 3.8, PATH is no longer searched for a DLL's own
        # dependencies (libosmo-fl2k.dll, libusb-1.0.dll, libwinpthread-1.dll);
        # the directory has to be registered explicitly.
        try:
            os.add_dll_directory(here)
        except (AttributeError, OSError):
            pass
    try:
        lib = ctypes.CDLL(libpath)
    except OSError as exc:
        print(f"[fl2k_plus] Cannot load {_libname}: {exc}\n"
              f"  Build it with:  cd {here} && make")
        return None

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

    # Audio channel struct – must match DspAudioChannel in DspWorkerFL2K.h
    class DspAudioChannel(ctypes.Structure):
        _fields_ = [
            ("freq_hz",      ctypes.c_float),
            ("bandwidth_hz", ctypes.c_float),
            ("name",         ctypes.c_char * 64),
            ("udp_port",     ctypes.c_int),
            ("mod_index",    ctypes.c_float),
        ]
    lib._DspAudioChannel = DspAudioChannel

    # Check whether dsp_fl2k_configure_audio exists in this .so.
    # On Python ≥ 3.13 lib.<missing> raises AttributeError immediately;
    # on older Python it returns a NULL function pointer.  We handle both.
    try:
        _fn_addr = ctypes.cast(lib.dsp_fl2k_configure_audio,
                               ctypes.c_void_p).value
        lib._has_audio_api = bool(_fn_addr)
    except (AttributeError, ctypes.ArgumentError, TypeError, OSError):
        lib._has_audio_api = False

    if not lib._has_audio_api:
        print(f"[fl2k_plus] WARNING: dsp_fl2k_configure_audio not found in "
              f"{libpath}.\n"
              f"  The library is probably from fl2k_C (no audio overlay).\n"
              f"  Run:  cd {here} && make   to rebuild.")
    else:
        lib.dsp_fl2k_configure_audio.restype  = Int
        lib.dsp_fl2k_configure_audio.argtypes = [
            VoidP,
            ctypes.POINTER(DspAudioChannel),
            Int,   # n_channels
            Float, # audio_rate
            Float, # mix_level
        ]
        lib.dsp_fl2k_prefill_audio.restype  = None
        lib.dsp_fl2k_prefill_audio.argtypes = [VoidP, Int]

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

    print(f"[fl2k_plus] Loaded {libpath}")
    return lib


_LIB = _load_lib()

# COHIWizard resets playthreadActive (and thus allows a new play_manager()
# call) as soon as the STOP button is pressed, well before the fl2k USB
# device has actually finished its native shutdown (which now waits
# properly for in-flight transfer cancellation, see DspWorkerFL2K.cpp).
# A quick re-Start can therefore try to fl2k_open() the same physical
# device while the previous session's fl2k_close() is still in progress,
# which crashes. Serialize device ownership across worker instances here
# instead of touching the shared playrec.py state machine.
_device_free = threading.Event()
_device_free.set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ffmpeg_url(url: str) -> str:
    """Encode semicolons in the URL path/params for ffmpeg's URL parser.

    Python's urlparse() and ffmpeg's av_url_split() both follow RFC 2396 and
    split "path;params" at the first semicolon.  SHOUTcast streams commonly use
    paths like /;stream.mp3.  ffmpeg silently drops the params part, causing an
    immediate open failure.  We rejoin path and params with '%3B' so ffmpeg sees
    a single unambiguous path token; ffmpeg's HTTP layer URL-decodes it back to
    ';' before issuing the GET request.
    """
    try:
        p = urlparse(url)
        if p.params:
            base = urlunparse(p._replace(params=""))
            return base + "%3B" + p.params.replace(";", "%3B")
    except Exception:
        pass
    return url


def _resolve_ffmpeg_bin(raw: str) -> str:
    """Turn the 'ffmpeg_path' config entry into an executable path.

    config_wizard.yaml stores the ffmpeg *installation directory* (see
    auxiliaries.is_ffmpeg_installed / playrec.checkffmpeg_install), not the
    exe itself, e.g. '...\\ffmpeg-master-latest-win64-gpl-shared/bin'.
    subprocess.Popen() cannot exec a directory, so it must be joined with
    the platform binary name here before use.
    """
    import platform
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    raw = (raw or "").strip()
    if not raw:
        return "ffmpeg"
    if os.path.isdir(raw):
        candidate = os.path.join(raw, exe_name)
        if os.path.isfile(candidate):
            return candidate
        print(f"[fl2k_plus] ffmpeg_path '{raw}' has no {exe_name} – falling back to PATH lookup.")
        return "ffmpeg"
    return raw


# ---------------------------------------------------------------------------
# CSV playlist parser
# ---------------------------------------------------------------------------

def _parse_freq(s: str) -> float:
    """Parse '175 kHz', '1.5 MHz', '9000 Hz' etc. → Hz (float)."""
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
    """
    Parse an AMWaveSynth-compatible semicolon-separated CSV.

    Columns: Frequenz ; Bandbreite ; Programmname ; URL
    Lines starting with '#' are comments; the first line may be a header.
    URLs containing semicolons must be quoted: "http://host:port/;stream.mp3"

    Returns list of dicts: {freq_hz, bw_hz, name, url}.
    """
    # Map typographic double-quote variants to ASCII “ (U+0022) so that
    # csv.reader’s quotechar recognises them as field delimiters.
    # 0x201C = U+201C LEFT DOUBLE QUOTATION MARK  “
    # 0x201D = U+201D RIGHT DOUBLE QUOTATION MARK “
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
                    print(f"[fl2k_plus] CSV line {lineno}: expected 4 columns, "
                          f"got {len(parts)} – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue  # header row
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[fl2k_plus] CSV line {lineno}: cannot parse "
                          f"'{freq_s}' / '{bw_s}' – skipped")
                    continue
                stations.append({
                    "freq_hz": freq_hz,
                    "bw_hz":   bw_hz,
                    "name":    name_s,
                    "url":     url_s,
                })
    except OSError as exc:
        print(f"[fl2k_plus] Cannot read audioplaylist '{csv_path}': {exc}")
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
    Worker for streaming COHIRadio WAV files to the fl2k DAC,
    with optional AM audio overlay from live web-radio streams.

    __slots__ layout (same as original fl2k_C driver):
      0  filename          – list of WAV file paths
      1  timescaler        – bytes/second (informational)
      2  TEST              – True → dry-run mode
      3  pause             – True → mute
      4  fileHandle        – seek proxy
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

    SigFinished          = pyqtSignal()
    SigIncrementCurTime  = pyqtSignal()
    SigBufferOverflow    = pyqtSignal()
    SigError             = pyqtSignal(str)
    SigNextfile          = pyqtSignal(str)
    SigInfomessage       = pyqtSignal(str)

    def __init__(self, sdrcontrol_inst, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix         = False
        self.DATASHOWSIZE   = 1024
        self.mutex          = QMutex()
        self.stemlabcontrol = sdrcontrol_inst
        self._handle        = None
        self._ffmpeg_procs  = []
        self._concat_files  = []   # temp ffconcat files for local m3u playlists

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
    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        """
        Start one ffmpeg subprocess per station.  Returns a list of channel
        dicts (with 'udp_port' added) ready for dsp_fl2k_configure_audio().
        """
        channels = []
        for idx, sta in enumerate(stations):
            port     = base_port + idx
            url      = sta["url"]
            bw_hz    = sta["bw_hz"]
            name     = sta["name"]

            # Half the RF bandwidth is the audio lowpass cut-off
            lowpass_f = max(100, int(bw_hz / 2))

            # Determine input type and build the ffmpeg command accordingly.
            _url_lower = url.lower()
            _is_http   = _url_lower.startswith(("http://", "https://", "rtsp://"))
            _is_local_m3u = (
                _url_lower.endswith((".m3u", ".m3u8", ".pls")) and not _is_http
            )

            if _is_local_m3u:
                # Parse the m3u ourselves and build an ffconcat file so ffmpeg
                # reliably handles local files with -stream_loop for endless play.
                _entries = []
                try:
                    with open(url, "r", encoding="utf-8", errors="replace") as _mf:
                        for _line in _mf:
                            _line = _line.strip()
                            if _line and not _line.startswith("#"):
                                _entries.append(_line)
                except OSError as _exc:
                    print(f"[fl2k_plus] Cannot read m3u '{url}': {_exc}")

                if not _entries:
                    print(f"[fl2k_plus] m3u '{url}' has no playable entries – skipped.")
                    continue

                # Filter out files that don't exist — otherwise ffmpeg starts,
                # fails immediately, and lingers as a zombie until session end.
                import os as _os
                _valid = []
                for _e in _entries:
                    if _os.path.isfile(_e):
                        _valid.append(_e)
                    else:
                        print(f"[fl2k_plus] WARNING: m3u entry not found, skipping: {_e}")
                _entries = _valid
                if not _entries:
                    print(f"[fl2k_plus] m3u '{url}': no files found on disk – channel skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="fl2k_concat_",
                    delete=False, encoding="utf-8"
                )
                # The concat demuxer does not support seeking, so -stream_loop -1
                # fails with "Operation not permitted" after the first pass.
                # Writing the playlist 200 times gives ~hours of playback in practice.
                _cf.write("ffconcat version 1.0\n")
                for _ in range(200):
                    for _e in _entries:
                        _cf.write(f"file {_e!r}\n")
                _cf.close()
                self._concat_files.append(_cf.name)
                print(f"[fl2k_plus] m3u '{url}': {len(_entries)} track(s) -> concat {_cf.name}")

                _curl_cmd = None
                cmd = [
                    ffmpeg_bin,
                    # -re: read at native (1×) speed so the UDP socket is not
                    # flooded with 700× worth of data, which would cause hundreds
                    # of wasted recv() syscalls per DSP block in the C++ engine.
                    "-re",
                    "-f", "concat", "-safe", "0",
                    "-i", _cf.name,
                    "-af", (f"lowpass=f={lowpass_f},"
                            f"volume=0.8"),
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            elif _is_http and urlparse(url).params:
                # SHOUTcast / URLs with a semicolon in the path, e.g.
                # http://host:port/;stream.mp3.
                # ffmpeg's av_url_split() strips everything from ';' onward,
                # even when percent-encoded.  Work around by piping through
                # curl which handles the URL verbatim.
                _curl_cmd = ["curl", "-s", "--max-time", "0", "--", url]
                cmd = [
                    ffmpeg_bin,
                    "-i", "pipe:0",
                    "-af", (f"lowpass=f={lowpass_f},"
                            f"volume=0.8"),
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            else:
                # HTTP / RTSP live stream — use reconnect flags for resilience.
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin,
                    "-reconnect", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                    "-i", _ffmpeg_url(url),
                    "-af", (f"lowpass=f={lowpass_f},"
                            f"volume=0.8"),
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]

            import tempfile, pathlib
            _logdir = pathlib.Path(tempfile.gettempdir())
            _logfile = _logdir / f"fl2k_ffmpeg_ch{idx}.log"

            try:
                if _curl_cmd is not None:
                    curl_proc = subprocess.Popen(
                        _curl_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                    )
                    proc = subprocess.Popen(
                        cmd,
                        stdin=curl_proc.stdout,
                        stdout=subprocess.DEVNULL,
                        stderr=open(_logfile, "w"),
                        close_fds=True,
                    )
                    curl_proc.stdout.close()  # let curl get SIGPIPE if ffmpeg dies
                    self._ffmpeg_procs.append(curl_proc)
                else:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=open(_logfile, "w"),
                        close_fds=True,
                    )
                print(f"[fl2k_plus] ffmpeg log -> {_logfile}")
                self._ffmpeg_procs.append(proc)
                print(f"[fl2k_plus] ffmpeg ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz']/1e3:.1f} kHz -> UDP {port} "
                      f"(PID {proc.pid})")
                channels.append({
                    "freq_hz":   sta["freq_hz"],
                    "bw_hz":     bw_hz,
                    "name":      name,
                    "udp_port":  port,
                    "mod_index": mod_index,
                })
            except OSError as exc:
                print(f"[fl2k_plus] Failed to start ffmpeg for '{name}': {exc}")

        return channels

    def _stop_audio_streams(self):
        """Terminate all ffmpeg subprocesses started by this worker."""
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
        # Remove temporary ffconcat files created for local m3u playlists.
        import os as _os
        for _cf in self._concat_files:
            try:
                _os.unlink(_cf)
            except OSError:
                pass
        self._concat_files.clear()
        print("[fl2k_plus] Audio streams stopped.")

    # ----------------------------------------------------------------
    def play_loop_filelist(self):
        """Wait for any previous session's fl2k device teardown to fully
        finish before claiming the device, so a fast re-Start after STOP
        can't race the native fl2k_close() of the session it's replacing."""
        _device_free.wait()
        _device_free.clear()
        try:
            self._play_loop_filelist_impl()
        finally:
            _device_free.set()

    def _play_loop_filelist_impl(self):
        if _LIB is None:
            self.SigError.emit(
                "libdspfl2k.so not found – build it with  make  in "
                "the fl2k_plus driver directory."
            )
            self.SigFinished.emit()
            return

        import faulthandler, sys
        faulthandler.enable(file=sys.stderr)

        filenames = self.get_filename()
        TEST      = self.get_TEST()
        gain      = self.get_gain()
        config    = self.get_configparameters()
        self.stopix = False
        self.set_fileclose(False)

        # ---- Read config_wizard.yaml --------------------------------
        _use_agc_cpp   = False
        _gain_corr     = 1.0
        _audioplaylist = ""
        _audio_rate    = 25000
        _mix_level     = 1.0
        _base_port     = 1234
        _mod_index     = 0.9
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
            _ffmpeg_bin    = _resolve_ffmpeg_bin(str(_cfg.get("ffmpeg_path", "")))
        except Exception as _e:
            print(f"[fl2k_plus] config_wizard.yaml read error: {_e}; using defaults")

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
                    f"Playback artefacts may occur > 500 kS/s."
                )

        # ---- TEST mode ----------------------------------------------
        if TEST:
            self._run_test_mode(filenames, sampling_rate)
            return

        # ---- Device check -------------------------------------------
        # A fast re-Start right after a STOP can hit the device while
        # Windows/WinUSB is still releasing the handle from the previous
        # session (a few hundred ms after our own native close() already
        # returned) -- retry briefly instead of failing on the first probe.
        self.mutex.lock()
        _dev_ok = False
        for _attempt in range(5):
            if _LIB.dsp_fl2k_check_device() == 0:
                _dev_ok = True
                break
            time.sleep(0.3)
        if not _dev_ok:
            self.SigError.emit(
                "fl2k device not found. Check the USB-VGA dongle connection."
            )
            self.SigFinished.emit()
            self.mutex.unlock()
            return
        self.mutex.unlock()

        # ---- Audio playlist -----------------------------------------
        _stations     = []
        _audio_active = False
        if _audioplaylist:
            _stations = parse_audio_playlist(_audioplaylist)
            if _stations:
                _audio_active = True
                print(f"[fl2k_plus] Audio overlay: {len(_stations)} station(s) "
                      f"from '{_audioplaylist}'")
            else:
                print(f"[fl2k_plus] Audio playlist '{_audioplaylist}' is empty "
                      "or unreadable – IQ-file-only mode.")
        else:
            print("[fl2k_plus] No audioplaylist configured – IQ-file-only mode.")

        # ---- Start ffmpeg subprocesses ------------------------------
        _channels = []
        if _audio_active:
            _channels = self._start_audio_streams(
                _stations, _base_port, _audio_rate, _mod_index, _ffmpeg_bin
            )

        # ---- Create C++ DSP worker ----------------------------------
        handle = _LIB.dsp_fl2k_create()
        if not handle:
            self.SigError.emit("dsp_fl2k_create() returned NULL")
            self._stop_audio_streams()
            self.SigFinished.emit()
            return
        self._handle = handle
        self.set_fileHandle(_SeekProxy(handle, _LIB))

        # ---- Configure IQ processing --------------------------------
        fname_array = (ctypes.c_char_p * len(filenames))(
            *[f.encode() for f in filenames]
        )
        _LIB.dsp_fl2k_configure(
            handle,
            ctypes.c_float(tSR),
            ctypes.c_float(float(lo_shift)),
            ctypes.c_float(float(gain * _gain_corr)),
            ctypes.c_int(1 if _use_agc_cpp else 0),
            fname_array,
            ctypes.c_int(len(filenames)),
        )

        # ---- Configure audio overlay --------------------------------
        if _audio_active and _channels and not getattr(_LIB, '_has_audio_api', False):
            self.SigError.emit(
                "Audio overlay deaktiviert: libdspfl2k.so enthält keine "
                "dsp_fl2k_configure_audio-Funktion.\n"
                "Bitte neu bauen:  cd fl2k_plus && make"
            )
            _audio_active = False
        if _audio_active and _channels:
            DspAudioChannel = _LIB._DspAudioChannel
            ch_arr = (DspAudioChannel * len(_channels))()
            for i, ch in enumerate(_channels):
                ch_arr[i].freq_hz      = ch["freq_hz"]
                ch_arr[i].bandwidth_hz = ch["bw_hz"]
                ch_arr[i].name         = ch["name"].encode("utf-8", errors="replace")[:63]
                ch_arr[i].udp_port     = ch["udp_port"]
                ch_arr[i].mod_index    = ch["mod_index"]

            rc = _LIB.dsp_fl2k_configure_audio(
                handle,
                ch_arr,
                ctypes.c_int(len(_channels)),
                ctypes.c_float(float(_audio_rate)),
                ctypes.c_float(float(_mix_level)),
            )
            if rc != 0:
                self.SigInfomessage.emit(
                    f"dsp_fl2k_configure_audio returned {rc} – overlay disabled."
                )
            else:
                # UDP sockets are now bound. Repeatedly drain them into the
                # 1 M-sample raw_fifo for 5 s so the large buffer starts nearly
                # full, giving ~2–3 h of drift margin against ffmpeg's ~0.3 %
                # systematic underdelivery when resampling 44.1 kHz → 25 kHz.
                _LIB.dsp_fl2k_prefill_audio(handle, ctypes.c_int(5000))

        # ---- Register C++ callbacks ---------------------------------
        @_LIB._MonitorCB
        def _on_monitor(data_ptr, n, _ud):
            try:
                arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
                self.set_data(arr)
                self.SigIncrementCurTime.emit()
            except Exception as _exc:
                print(f"[fl2k_plus] _on_monitor exception: {_exc}", flush=True)

        @_LIB._ErrorCB
        def _on_error(msg_ptr, _ud):
            try:
                msg = msg_ptr.decode(errors="replace") if msg_ptr else "(null)"
                print(f"[fl2k_plus] C++ error callback: {msg}", flush=True)
                self.SigError.emit(msg)
            except Exception as _exc:
                print(f"[fl2k_plus] _on_error exception: {_exc}", flush=True)

        @_LIB._NextfileCB
        def _on_nextfile(path_ptr, _ud):
            try:
                if path_ptr:
                    self.SigNextfile.emit(path_ptr.decode(errors="replace"))
            except Exception as _exc:
                print(f"[fl2k_plus] _on_nextfile exception: {_exc}", flush=True)

        @_LIB._FinishedCB
        def _on_finished(_ud):
            print("[fl2k_plus] C++ finished callback fired.", flush=True)

        _LIB.dsp_fl2k_set_monitor_cb (handle, _on_monitor,  None)
        _LIB.dsp_fl2k_set_error_cb   (handle, _on_error,    None)
        _LIB.dsp_fl2k_set_nextfile_cb(handle, _on_nextfile, None)
        _LIB.dsp_fl2k_set_finished_cb(handle, _on_finished, None)

        # ---- Start DSP + fl2k threads -------------------------------
        rc = _LIB.dsp_fl2k_start(handle)
        if rc != 0:
            codes = {-1: "already running", -2: "no files configured",
                     -3: "fl2k device failed to open"}
            self.SigError.emit(
                f"dsp_fl2k_start failed (code {rc}: {codes.get(rc, '?')})"
            )
            _LIB.dsp_fl2k_destroy(handle)
            self._handle = None
            self._stop_audio_streams()
            self.SigFinished.emit()
            return

        # ---- Polling loop -------------------------------------------
        while _LIB.dsp_fl2k_is_running(handle) and not self.stopix:
            _LIB.dsp_fl2k_set_pause(handle, 1 if self.get_pause() else 0)
            if not _use_agc_cpp:
                _LIB.dsp_fl2k_set_gain(
                    handle, ctypes.c_float(float(self.get_gain()) * _gain_corr)
                )
            QThread.msleep(50)

        # ---- Cleanup ------------------------------------------------
        _LIB.dsp_fl2k_stop(handle)
        _LIB.dsp_fl2k_destroy(handle)
        self._handle = None

        self._stop_audio_streams()
        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

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
                                    data[: self.DATASHOWSIZE].astype(np.float32)
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
                    print(f"[fl2k_plus] killing orphan fl2k_file PID {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
