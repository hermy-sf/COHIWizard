"""
cohi_playrecworker.py  –  fl2k_modulator variant
COHIWizard device-driver worker for the fl2k USB-VGA DAC, pure AM synthesizer.

No IQ-WAV file is needed.  N web-radio stations are AM-modulated onto
individual carriers and summed into a complex baseband, which is then
upsampled once to the FL2K output rate.

Signal chain:
  ffmpeg → u8 PCM mono @ audio_rate_hz → UDP socket → libdspflmod.so
The C++ library resamples each stream to baseband_rate, AM-modulates it
onto its carrier, sums all channels, upsamples to target_rate and feeds
the FL2K DAC.

Signal processing is performed by a cpp-library DspWorkerFLMod.cpp based on liquiddsp.
This library was inspired by AMWaveSynth by radiolab81 (https://github.com/radiolab81/AMWaveSynth)

CSV format (semicolon-separated, same as fl2k_plus):
  Frequenz;Bandbreite;Programmname;URL
  175 kHz;10.0 kHz;Canal Sud;http://91.224.148.160:8000/canalsud-live
  600 kHz;4.5 kHz;Radio Dismuke;"http://74.208.228.126:8020/;stream.mp3"

config_wizard.yaml keys used by this driver:
  audioplaylist           str    path to CSV (required; empty → silence)
  audio_rate_hz           int    PCM rate for ffmpeg (default 25000)
  audio_mix_level         float  amplitude weight, 1.0 = equal power (default 1.0)
  audio_base_port         int    first UDP port, increments per channel (default 1234)
  audio_mod_index         float  AM modulation index 0–1 (default 0.9)
  flmod_baseband_rate     float  optional baseband rate override in Hz (default: 0 = auto).
                                 Auto selects the largest integer divisor of 10 MS/s
                                 that fits all carriers with 20 % guard margin.
  autoAGC_DspWorker       bool   C++ AGC (default False)
  gain_correction_fl2k_C  float  amplitude correction factor (default 1.0)
  ffmpeg_path             str    ffmpeg binary (default 'ffmpeg')
"""

import csv
import ctypes
import os
import subprocess
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
    here    = os.path.dirname(os.path.abspath(__file__))
    libpath = os.path.join(here, "libdspflmod.so")
    try:
        lib = ctypes.CDLL(libpath)
    except OSError as exc:
        print(f"[fl2k_mod] Cannot load libdspflmod.so: {exc}\n"
              f"  Build it with:  cd {here} && make")
        return None

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
        Int,   # n_channels
        Float, # audio_rate
        Float, # mix_level
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

    print(f"[fl2k_mod] Loaded {libpath}")
    return lib


_LIB = _load_lib()


# ---------------------------------------------------------------------------
# Helpers shared with fl2k_plus
# ---------------------------------------------------------------------------

def _ffmpeg_url(url: str) -> str:
    """Percent-encode semicolons in URL paths for ffmpeg's URL parser."""
    try:
        p = urlparse(url)
        if p.params:
            base = urlunparse(p._replace(params=""))
            return base + "%3B" + p.params.replace(";", "%3B")
    except Exception:
        pass
    return url


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
                    print(f"[fl2k_mod] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[fl2k_mod] CSV line {lineno}: cannot parse "
                          f"'{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[fl2k_mod] Cannot read playlist '{csv_path}': {exc}")
    return stations


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """
    Worker for the fl2k_modulator driver (pure AM synthesizer).

    Compatible with the COHIWizard playrec_worker interface.
    filenames (slot 0) are not used; the carrier CSV playlist drives output.

    __slots__ layout (compatible with other COHIWizard drivers):
      0  filename          – unused (no IQ file needed)
      1  timescaler        – unused
      2  TEST              – True → dry-run (silence, no hardware)
      3  pause             – True → mute
      4  fileHandle        – None (no file)
      5  data              – 1024-float monitor window
      6  gain              – amplitude scale factor [0…2]
      7  formattag         – unused
      8  datablocksize     – unused
      9  fileclose         – True when stopped
     10  configparameters  – dict with ifreq (center Hz), irate (ignored)
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

            _url_lower   = url.lower()
            _is_http     = _url_lower.startswith(("http://", "https://", "rtsp://"))
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
                    print(f"[fl2k_mod] Cannot read m3u '{url}': {_exc}")

                if not _entries:
                    print(f"[fl2k_mod] m3u '{url}' empty – skipped.")
                    continue

                import os as _os
                _valid = []
                for _e in _entries:
                    if _os.path.isfile(_e):
                        _valid.append(_e)
                    else:
                        print(f"[fl2k_mod] WARNING: m3u entry not found, skipping: {_e}")
                _entries = _valid
                if not _entries:
                    print(f"[fl2k_mod] m3u '{url}': no files found on disk – channel skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="flmod_concat_",
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
                    ffmpeg_bin,
                    "-re",
                    "-f", "concat", "-safe", "0",
                    "-i", _cf.name,
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            elif _is_http and urlparse(url).params:
                _curl_cmd = ["curl", "-s", "--max-time", "0", "--", url]
                cmd = [
                    ffmpeg_bin,
                    "-i", "pipe:0",
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]
            else:
                _curl_cmd = None
                cmd = [
                    ffmpeg_bin,
                    "-reconnect", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                    "-i", _ffmpeg_url(url),
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]

            import tempfile, pathlib
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"flmod_ffmpeg_ch{idx}.log"

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
                print(f"[fl2k_mod] ffmpeg ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz']/1e3:.1f} kHz → UDP {port} "
                      f"(PID {proc.pid}), log → {_logfile}")
                self._ffmpeg_procs.append(proc)
                channels.append({
                    "freq_hz":   sta["freq_hz"],
                    "bw_hz":     bw_hz,
                    "name":      name,
                    "udp_port":  port,
                    "mod_index": mod_index,
                })
            except OSError as exc:
                print(f"[fl2k_mod] Failed to start ffmpeg for '{name}': {exc}")

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
        import os as _os
        for _cf in self._concat_files:
            try:
                _os.unlink(_cf)
            except OSError:
                pass
        self._concat_files.clear()
        print("[fl2k_mod] Audio streams stopped.")

    # ----------------------------------------------------------------
    def play_loop_filelist(self):
        if _LIB is None:
            self.SigError.emit(
                "libdspflmod.so not found – build it with  make  in "
                "the fl2k_modulator driver directory."
            )
            self.SigFinished.emit()
            return

        import faulthandler, sys
        faulthandler.enable(file=sys.stderr)

        config    = self.get_configparameters()
        gain      = self.get_gain()
        TEST      = self.get_TEST()
        self.stopix = False
        self.set_fileclose(False)

        # ---- Read config_wizard.yaml --------------------------------
        _use_agc_cpp    = False
        _gain_corr      = 1.0
        _audioplaylist  = ""
        _audio_rate     = 25000
        _mix_level      = 1.0
        _base_port      = 1234
        _mod_index      = 0.9
        _bb_rate_yaml   = 0.0          # 0 = auto-compute from CSV carrier span
        _ffmpeg_bin     = "ffmpeg"
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
            _ffmpeg_bin    = (str(_cfg.get("ffmpeg_path", "ffmpeg")).strip() or "ffmpeg")
        except Exception as _e:
            print(f"[fl2k_mod] config_wizard.yaml read error: {_e}; using defaults")

        center_freq = float(config.get("ifreq",     0))
        _lo_offset  = float(config.get("LO_offset", 0.0))

        # ---- Audio playlist (parsed early to determine baseband rate) ----
        _stations = []
        if _audioplaylist:
            _stations = parse_audio_playlist(_audioplaylist)
            if _stations:
                print(f"[fl2k_mod] {len(_stations)} station(s) from '{_audioplaylist}'")
            else:
                print(f"[fl2k_mod] Playlist empty – running in silence mode.")
        else:
            print("[fl2k_mod] No audioplaylist configured – silence mode.")

        # ---- Baseband rate: GUI selection is the enforced minimum ----
        _bb_rate_min = float(config.get("irate", 1_250_000.0))

        if _bb_rate_yaml > 0:
            _bb_rate = max(_bb_rate_yaml, _bb_rate_min)
        elif _stations:
            _s_freqs   = [s["freq_hz"] for s in _stations]
            _s_bws     = [s["bw_hz"]   for s in _stations]
            _band_span = max(_s_freqs) - min(_s_freqs) if len(_stations) > 1 else 0.0
            # Required span: carrier spread + LO_offset asymmetry + audio guard band (×1.2)
            _min_bb    = (_band_span + 2.0 * abs(_lo_offset) + 2.0 * max(_s_bws)) * 1.2
            _ratio     = min(8, max(1, int(10_000_000 / _min_bb)))
            _bb_rate   = max(10_000_000.0 / _ratio, _bb_rate_min)
            _ratio     = int(10_000_000 / _bb_rate)
            print(f"[fl2k_mod] auto bb_rate: span={_band_span/1e3:.0f} kHz  "
                  f"ratio={_ratio} → {_bb_rate/1e3:.0f} kHz")
        else:
            _bb_rate = _bb_rate_min

        # target_rate: smallest multiple of 10 MS/s that covers the band
        tSR = 10_000_000 * (1 + int((center_freq + _bb_rate / 2) * 2 / 10_000_000))
        tSR = min(100_000_000, max(10_000_000, tSR))

        print(f"[fl2k_mod] center={center_freq/1e3:.1f} kHz, "
              f"target={tSR/1e6:.0f} MS/s, baseband={_bb_rate/1e6:.3f} MS/s")

        # Sanity: baseband_rate must be < target_rate
        if _bb_rate >= tSR:
            self.SigError.emit(
                f"flmod_baseband_rate ({_bb_rate/1e6:.3f} MS/s) must be "
                f"< target_rate ({tSR/1e6:.0f} MS/s)."
            )
            self.SigFinished.emit()
            return

        # ---- TEST mode (dry-run, no hardware) -----------------------
        if TEST:
            print("[fl2k_mod] TEST mode: simulating for 5 s without hardware.")
            time.sleep(5)
            self.set_fileclose(True)
            self.SigFinished.emit()
            return

        # ---- Device check -------------------------------------------
        self.mutex.lock()
        if _LIB.dsp_flmod_check_device() != 0:
            self.SigError.emit(
                "fl2k device not found. Check the USB-VGA dongle connection."
            )
            self.SigFinished.emit()
            self.mutex.unlock()
            return
        self.mutex.unlock()

        # ---- Start ffmpeg subprocesses ------------------------------
        _channels = []
        if _stations:
            _channels = self._start_audio_streams(
                _stations, _base_port, _audio_rate, _mod_index, _ffmpeg_bin
            )

        # ---- Optional uniform band shift via LO_offset ---------------------
        if _channels and _lo_offset != 0.0:
            print(f"[fl2k_mod] LO_offset={_lo_offset/1e3:+.1f} kHz → "
                  f"shifting all carriers by {_lo_offset/1e3:+.1f} kHz")
            for ch in _channels:
                ch["freq_hz"] += _lo_offset

        # ---- Create C++ worker --------------------------------------
        handle = _LIB.dsp_flmod_create()
        if not handle:
            self.SigError.emit("dsp_flmod_create() returned NULL")
            self._stop_audio_streams()
            self.SigFinished.emit()
            return
        self._handle = handle

        # ---- Configure synthesis ------------------------------------
        _LIB.dsp_flmod_configure(
            handle,
            ctypes.c_float(float(tSR)),
            ctypes.c_float(float(center_freq)),
            ctypes.c_float(float(_bb_rate)),
            ctypes.c_float(float(gain * _gain_corr)),
            ctypes.c_int(1 if _use_agc_cpp else 0),
        )

        # ---- Configure channels -------------------------------------
        if _channels:
            DspFLModChannel = _LIB._DspFLModChannel
            ch_arr = (DspFLModChannel * len(_channels))()
            for i, ch in enumerate(_channels):
                ch_arr[i].freq_hz      = ch["freq_hz"]
                ch_arr[i].bandwidth_hz = ch["bw_hz"]
                ch_arr[i].name         = ch["name"].encode("utf-8", errors="replace")[:63]
                ch_arr[i].udp_port     = ch["udp_port"]
                ch_arr[i].mod_index    = ch["mod_index"]

            rc = _LIB.dsp_flmod_configure_channels(
                handle,
                ch_arr,
                ctypes.c_int(len(_channels)),
                ctypes.c_float(float(_audio_rate)),
                ctypes.c_float(float(_mix_level)),
            )
            if rc != 0:
                self.SigInfomessage.emit(
                    f"dsp_flmod_configure_channels returned {rc} – no audio overlay."
                )
            else:
                # Prefill raw_fifo buffers (5 s) to give drift margin
                _LIB.dsp_flmod_prefill(handle, ctypes.c_int(5000))

        # ---- Register callbacks -------------------------------------
        @_LIB._MonitorCB
        def _on_monitor(data_ptr, n, _ud):
            try:
                arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
                self.set_data(arr)
                self.SigIncrementCurTime.emit()
            except Exception as _exc:
                print(f"[fl2k_mod] _on_monitor: {_exc}", flush=True)

        @_LIB._ErrorCB
        def _on_error(msg_ptr, _ud):
            try:
                msg = msg_ptr.decode(errors="replace") if msg_ptr else "(null)"
                print(f"[fl2k_mod] C++ error: {msg}", flush=True)
                self.SigError.emit(msg)
            except Exception as _exc:
                print(f"[fl2k_mod] _on_error: {_exc}", flush=True)

        @_LIB._FinishedCB
        def _on_finished(_ud):
            print("[fl2k_mod] C++ finished callback.", flush=True)

        _LIB.dsp_flmod_set_monitor_cb (handle, _on_monitor,  None)
        _LIB.dsp_flmod_set_error_cb   (handle, _on_error,    None)
        _LIB.dsp_flmod_set_finished_cb(handle, _on_finished, None)

        # ---- Start DSP + FL2K threads -------------------------------
        rc = _LIB.dsp_flmod_start(handle)
        if rc != 0:
            codes = {-1: "already running", -3: "fl2k device failed to open"}
            self.SigError.emit(
                f"dsp_flmod_start failed (code {rc}: {codes.get(rc, '?')})"
            )
            _LIB.dsp_flmod_destroy(handle)
            self._handle = None
            self._stop_audio_streams()
            self.SigFinished.emit()
            return

        # ---- Polling loop -------------------------------------------
        while _LIB.dsp_flmod_is_running(handle) and not self.stopix:
            _LIB.dsp_flmod_set_pause(handle, 1 if self.get_pause() else 0)
            if not _use_agc_cpp:
                _LIB.dsp_flmod_set_gain(
                    handle, ctypes.c_float(float(self.get_gain()) * _gain_corr)
                )
            QThread.msleep(50)

        # ---- Cleanup ------------------------------------------------
        _LIB.dsp_flmod_stop(handle)
        _LIB.dsp_flmod_destroy(handle)
        self._handle = None

        self._stop_audio_streams()
        self.set_fileHandle(None)
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
                    print(f"[fl2k_mod] killing orphan fl2k_file PID {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
