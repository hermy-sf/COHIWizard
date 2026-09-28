"""
stemlab_eff_universal/cohi_playrecworker.py
COHIWizard device-driver worker for STEMlab 125-14.

Identical to stemlab_universal for IQ-only and IQ+Audio modes.
Audio-only mode replaces the NumPy AM synthesis with the C++ NCO engine
from libdspflmod.so (fl2k_fast_modulator) via a pull API, eliminating the
5–15 ms per-block DSP penalty that caused buzzing with 15+ carriers.

Signal chain (audio-only):
  ffmpeg → s16le PCM → UDP → libdspflmod C++ engine (ZOH + LUT NCO)
  → dsp_flmod_pull_iq() → float32 IQ → TCP → STEMLAB

Signal chain (IQ+Audio):
  WAV file IQ + NumPy AM overlay → TCP → STEMLAB  (unchanged from stemlab_universal)
"""

import ctypes
import csv
import math
import os
import pathlib
import platform
import socket as _socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse, urlunparse

import numpy as np
import yaml
from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Helpers (identical to stemlab_universal)
# ---------------------------------------------------------------------------

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
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    raw = (raw or "").strip()
    if not raw:
        return "ffmpeg"
    if os.path.isdir(raw):
        candidate = os.path.join(raw, exe_name)
        if os.path.isfile(candidate):
            return candidate
        print(f"[stemlab_eff] ffmpeg_path '{raw}' has no {exe_name} – falling back to PATH.")
        return "ffmpeg"
    return raw


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
                    print(f"[stemlab_eff] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[stemlab_eff] CSV line {lineno}: cannot parse '{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[stemlab_eff] Cannot read playlist '{csv_path}': {exc}")
    return stations


# ---------------------------------------------------------------------------
# Thread-safe UDP audio ring buffer (for IQ+Audio mode only)
# ---------------------------------------------------------------------------

class _AudioBuffer:
    def __init__(self, udp_port: int, capacity: int = 500_000):
        self._sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", udp_port))
        self._sock.settimeout(0.1)
        self._buf       = np.zeros(capacity, dtype=np.float32)
        self._cap       = capacity
        self._wp        = 0
        self._rp        = 0
        self._lock      = threading.Lock()
        self._stop      = False
        self._underruns = 0
        self._thread    = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while not self._stop:
            try:
                raw     = self._sock.recv(8192)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                n       = len(samples)
                with self._lock:
                    space1 = min(n, self._cap - self._wp)
                    self._buf[self._wp : self._wp + space1] = samples[:space1]
                    if space1 < n:
                        self._buf[: n - space1] = samples[space1:]
                    self._wp = (self._wp + n) % self._cap
            except _socket.timeout:
                pass
            except Exception as exc:
                if not self._stop:
                    print(f"[stemlab_eff] AudioBuffer UDP reader error: {exc}")

    def read(self, n: int) -> np.ndarray:
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            available = (self._wp - self._rp) % self._cap
            to_read   = min(n, available)
            if to_read < n:
                self._underruns += 1
            part1 = min(to_read, self._cap - self._rp)
            out[:part1] = self._buf[self._rp : self._rp + part1]
            if part1 < to_read:
                out[part1:to_read] = self._buf[: to_read - part1]
            self._rp = (self._rp + to_read) % self._cap
        return out

    def level(self) -> int:
        with self._lock:
            return (self._wp - self._rp) % self._cap

    def close(self):
        self._stop = True
        self._thread.join(timeout=1.5)
        try:
            self._sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# libdspflmod.so loader with pull-API additions
# ---------------------------------------------------------------------------

def _setup_lib_mod(lib, libpath):
    """Wire argtypes/restype for libdspflmod.so including pull API."""
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
            ("freq_hz",         ctypes.c_float),
            ("bandwidth_hz",    ctypes.c_float),
            ("name",            ctypes.c_char * 64),
            ("udp_port",        ctypes.c_int),
            ("mod_index",       ctypes.c_float),
            ("schroeder_phase", ctypes.c_float),
        ]
    lib._DspFLModChannel = DspFLModChannel

    lib.dsp_flmod_configure_channels.restype  = Int
    lib.dsp_flmod_configure_channels.argtypes = [
        VoidP, ctypes.POINTER(DspFLModChannel), Int, Float, Float,
    ]
    lib.dsp_flmod_prefill.restype  = None
    lib.dsp_flmod_prefill.argtypes = [VoidP, Int]

    lib.dsp_flmod_set_gain.restype   = None
    lib.dsp_flmod_set_gain.argtypes  = [VoidP, Float]

    # Pull-mode API
    lib.dsp_flmod_pull_init.restype  = Int
    lib.dsp_flmod_pull_init.argtypes = [VoidP]
    lib.dsp_flmod_pull_iq.restype    = Int
    lib.dsp_flmod_pull_iq.argtypes   = [VoidP, FloatP, Int]
    lib.dsp_flmod_pull_stop.restype  = None
    lib.dsp_flmod_pull_stop.argtypes = [VoidP]


def _load_lib_mod():
    """Load libdspflmod.so; own dir first, then fl2k_fast_modulator sibling."""
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
                print(f"[stemlab_eff] Loaded libdspflmod from {libpath}")
                return lib
            except OSError as exc:
                print(f"[stemlab_eff] Cannot load {libpath}: {exc}")
    print(f"[stemlab_eff] libdspflmod.so not found – searched: {candidates}")
    return None


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """Worker for STEMlab 125-14 (eff_universal variant).

    IQ-only and IQ+Audio modes: identical to stemlab_universal.
    Audio-only mode: C++ NCO synthesis via libdspflmod pull API.
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
        self.stopix         = False
        self.DATABLOCKSIZE  = 1024 * 4
        self.DATASHOWSIZE   = 1024
        self.mutex          = QMutex()
        self.stemlabcontrol = stemlabcontrolinst
        self._ffmpeg_procs  = []
        self._concat_files  = []
        self._block_count   = 0

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

    # --------------------------------------------------------- audio streaming
    def _kill_orphaned_ffmpeg(self, base_port: int, n_channels: int) -> None:
        for i in range(n_channels):
            port    = base_port + i
            pattern = f"udp://127.0.0.1:{port}"
            try:
                subprocess.run(
                    ["pkill", "-f", pattern],
                    check=False, timeout=3
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        if n_channels > 0:
            time.sleep(0.3)

    def _build_ffmpeg_cmd(self, sta: dict, port: int, audio_rate: int,
                          ffmpeg_bin: str, pcm_format: str = "s16le") -> tuple:
        """Return (ffmpeg_cmd, curl_cmd_or_None) for one station.

        pcm_format: "s16le" for Python _AudioBuffer path (2 bytes/sample),
                    "u8"    for C++ libdspflmod path (1 byte/sample, 0–255).
        """
        url       = sta["url"]
        bw_hz     = sta.get("bw_hz", 9000.0)
        lowpass_f = max(100, int(bw_hz / 2))
        pkt_size  = 256 if pcm_format == "u8" else 512

        _url_lower    = url.lower()
        _is_http      = _url_lower.startswith(("http://", "https://", "rtsp://"))
        _is_local_m3u = _url_lower.endswith((".m3u", ".m3u8", ".pls")) and not _is_http

        _curl_cmd = None

        if _is_local_m3u:
            _entries = []
            try:
                with open(url, "r", encoding="utf-8", errors="replace") as _mf:
                    for _line in _mf:
                        _line = _line.strip()
                        if _line and not _line.startswith("#"):
                            _entries.append(_line)
            except OSError as _exc:
                print(f"[stemlab_eff] Cannot read m3u '{url}': {_exc}")
            _entries = [e for e in _entries if os.path.isfile(e)]
            if not _entries:
                print(f"[stemlab_eff] m3u '{url}': no valid files – channel skipped.")
                return None, None
            _cf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", prefix="stemeff_concat_",
                delete=False, encoding="utf-8"
            )
            _cf.write("ffconcat version 1.0\n")
            for _ in range(200):
                for _e in _entries:
                    _cf.write(f"file {_e!r}\n")
            _cf.close()
            self._concat_files.append(_cf.name)
            cmd = [
                ffmpeg_bin, "-re",
                "-f", "concat", "-safe", "0", "-i", _cf.name,
                "-af", f"lowpass=f={lowpass_f},volume=0.8",
                "-f", pcm_format, "-ar", str(audio_rate), "-ac", "1",
                f"udp://127.0.0.1:{port}?pkt_size={pkt_size}",
            ]
        elif _is_http and urlparse(url).params:
            _curl_cmd = ["curl", "-s", "--max-time", "0", "--", url]
            cmd = [
                ffmpeg_bin, "-i", "pipe:0",
                "-af", f"lowpass=f={lowpass_f},volume=0.8",
                "-f", pcm_format, "-ar", str(audio_rate), "-ac", "1",
                f"udp://127.0.0.1:{port}?pkt_size={pkt_size}",
            ]
        else:
            cmd = [
                ffmpeg_bin,
                "-reconnect", "1", "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", _ffmpeg_url(url),
                "-af", f"lowpass=f={lowpass_f},volume=0.8",
                "-f", pcm_format, "-ar", str(audio_rate), "-ac", "1",
                f"udp://127.0.0.1:{port}?pkt_size={pkt_size}",
            ]
        return cmd, _curl_cmd

    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        """Start ffmpeg + _AudioBuffer per station (IQ+Audio mode)."""
        self._kill_orphaned_ffmpeg(base_port, len(stations))
        channels = []
        N_total  = len(stations)
        for idx, sta in enumerate(stations):
            port = base_port + idx
            cmd, curl_cmd = self._build_ffmpeg_cmd(sta, port, audio_rate, ffmpeg_bin)
            if cmd is None:
                continue
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"stemeff_ffmpeg_ch{idx}.log"
            try:
                if curl_cmd is not None:
                    curl_proc = subprocess.Popen(
                        curl_cmd, stdout=subprocess.PIPE,
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
                print(f"[stemlab_eff] ffmpeg ch[{idx}] '{sta['name']}' "
                      f"@ {sta['freq_hz'] / 1e3:.1f} kHz -> UDP {port} (PID {proc.pid})")
                self._ffmpeg_procs.append(proc)
                schroeder_phase = math.pi * idx * (idx + 1) / max(1, N_total)
                channels.append({
                    "freq_hz":         sta["freq_hz"],
                    "bw_hz":           sta.get("bw_hz", 9000.0),
                    "name":            sta["name"],
                    "udp_port":        port,
                    "mod_index":       mod_index,
                    "schroeder_phase": schroeder_phase,
                })
            except OSError as exc:
                print(f"[stemlab_eff] Failed to start ffmpeg for '{sta['name']}': {exc}")
        return channels

    def _start_ffmpeg_procs(self, stations: list, base_port: int,
                             audio_rate: int, ffmpeg_bin: str) -> None:
        """Start ffmpeg processes only (no _AudioBuffer); C++ owns the UDP sockets.

        Uses u8 PCM format: the C++ mix_audio_block_fast reads bytes as unsigned 8-bit
        (value 0–255, centre 128), matching how fl2k_universal feeds its C++ engine.
        """
        for idx, sta in enumerate(stations):
            port = base_port + idx
            cmd, curl_cmd = self._build_ffmpeg_cmd(
                sta, port, audio_rate, ffmpeg_bin, pcm_format="u8"
            )
            if cmd is None:
                continue
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"stemeff_ffmpeg_ch{idx}.log"
            try:
                if curl_cmd is not None:
                    curl_proc = subprocess.Popen(
                        curl_cmd, stdout=subprocess.PIPE,
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
                print(f"[stemlab_eff] ffmpeg ch[{idx}] '{sta['name']}' "
                      f"@ {sta['freq_hz'] / 1e3:.1f} kHz -> UDP {port} (PID {proc.pid})")
                self._ffmpeg_procs.append(proc)
            except OSError as exc:
                print(f"[stemlab_eff] Failed to start ffmpeg for '{sta['name']}': {exc}")

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
        print("[stemlab_eff] Audio streams stopped.")

    # ----------------------------------------------------------- AM DSP (IQ+Audio mode only)
    def _modulate_audio_channels(self, audio_buffers, channels,
                                  n_samples: int, sample_rate: float,
                                  audio_rate: float, sample_offset: int,
                                  center_freq: float = 0.0):
        if all(buf.level() == 0 for buf in audio_buffers):
            return None, None
        audio_n   = max(1, int(round(n_samples * audio_rate / sample_rate)))
        t         = (np.arange(n_samples, dtype=np.float64) + sample_offset) / sample_rate
        overlay_i = np.zeros(n_samples, dtype=np.float32)
        overlay_q = np.zeros(n_samples, dtype=np.float32)
        xp        = np.arange(audio_n, dtype=np.float64) * (n_samples / audio_n)
        xi        = np.arange(n_samples, dtype=np.float64)
        for buf, ch in zip(audio_buffers, channels):
            audio_raw = buf.read(audio_n)
            if audio_n >= n_samples:
                audio_up = audio_raw[:n_samples].astype(np.float64)
            else:
                audio_up = np.interp(xi, xp, audio_raw)
            amp             = 1.0 + ch["mod_index"] * audio_up
            freq_offset     = ch["freq_hz"] - center_freq
            schroeder_phase = ch.get("schroeder_phase", 0.0)
            _TWO_PI         = 2.0 * np.pi
            phase_f32 = (_TWO_PI * freq_offset * t + schroeder_phase
                         ).astype(np.float64) % _TWO_PI
            phase_f32 = phase_f32.astype(np.float32)
            amp_f32   = amp.astype(np.float32)
            overlay_i += amp_f32 * np.cos(phase_f32)
            overlay_q += amp_f32 * np.sin(phase_f32)
        n_ch = max(1, len(channels))
        overlay_i /= n_ch
        overlay_q /= n_ch
        return overlay_i, overlay_q

    # --------------------------------------------------------- C++ pull synthesis
    def _init_cpp_overlay(self, config: dict, stations: list,
                           sampling_rate: float, mix_level: float,
                           base_port: int, audio_rate: int,
                           mod_index: float, ffmpeg_bin: str,
                           use_agc: bool, gain_corr: float):
        """Create and configure a C++ pull-mode synthesis engine for audio overlay.

        C++ binds UDP sockets, then ffmpeg is launched.
        Returns (lib, handle) ready for dsp_flmod_pull_iq calls,
        or (None, None) on any failure (error already emitted).
        """
        lib = _load_lib_mod()
        if lib is None:
            self.SigError.emit(
                "[stemlab_eff] Cannot load libdspflmod.so – "
                "build it in dev_drivers/fl2k_fast_modulator/ with 'make'."
            )
            return None, None

        handle = lib.dsp_flmod_create()
        if not handle:
            self.SigError.emit("[stemlab_eff] dsp_flmod_create() returned NULL")
            return None, None

        gain        = self.get_gain()
        center_freq = float(config.get("ifreq", 0.0))

        r = lib.dsp_flmod_configure(
            handle,
            ctypes.c_float(sampling_rate),        # target_rate (unused in pull mode)
            ctypes.c_float(center_freq),
            ctypes.c_float(sampling_rate),        # baseband_rate = IQ output rate
            ctypes.c_float(gain * gain_corr),     # initial amplitude
            ctypes.c_int(1 if use_agc else 0),    # AGC on/off
        )
        if r < 0:
            self.SigError.emit("[stemlab_eff] dsp_flmod_configure() failed")
            lib.dsp_flmod_destroy(handle)
            return None, None

        n_ch    = len(stations)
        N_total = n_ch
        DspFLModChannel = lib._DspFLModChannel
        ch_arr = (DspFLModChannel * n_ch)()
        for i, sta in enumerate(stations):
            ch_arr[i].freq_hz         = float(sta["freq_hz"])
            ch_arr[i].bandwidth_hz    = float(sta.get("bw_hz", 9000.0))
            ch_arr[i].name            = sta["name"][:63].encode()
            ch_arr[i].udp_port        = base_port + i
            ch_arr[i].mod_index       = float(mod_index)
            ch_arr[i].schroeder_phase = float(
                math.pi * i * (i + 1) / max(1, N_total)
            )

        r = lib.dsp_flmod_configure_channels(
            handle, ch_arr, ctypes.c_int(n_ch),
            ctypes.c_float(float(audio_rate)),
            ctypes.c_float(float(mix_level)),
        )
        if r < 0:
            self.SigError.emit("[stemlab_eff] dsp_flmod_configure_channels() failed")
            lib.dsp_flmod_destroy(handle)
            return None, None

        print(f"[stemlab_eff] C++ overlay: center={center_freq/1e3:.1f} kHz, "
              f"SR={sampling_rate:.0f} Hz, ch={n_ch}, "
              f"AGC={'on' if use_agc else 'off'}, gain_corr={gain_corr}")

        # C++ has bound UDP sockets — launch ffmpeg now
        self._kill_orphaned_ffmpeg(base_port, n_ch)
        self._start_ffmpeg_procs(stations, base_port, audio_rate, ffmpeg_bin)
        print("[stemlab_eff] Waiting 1 s for ffmpeg to start streaming...")
        time.sleep(1.0)

        lib.dsp_flmod_prefill(handle, ctypes.c_int(500))

        r = lib.dsp_flmod_pull_init(handle)
        if r < 0:
            self.SigError.emit("[stemlab_eff] dsp_flmod_pull_init() failed")
            lib.dsp_flmod_destroy(handle)
            self._stop_audio_streams()
            return None, None

        return lib, handle

    def _teardown_cpp_overlay(self, lib, handle) -> None:
        """Tear down C++ pull engine and stop ffmpeg."""
        if handle and lib:
            lib.dsp_flmod_pull_stop(handle)
            lib.dsp_flmod_destroy(handle)
        self._stop_audio_streams()

    def _run_eff_audio_only(self, config: dict, stations: list,
                             sampling_rate: float, mix_level: float,
                             base_port: int, audio_rate: int,
                             mod_index: float, ffmpeg_bin: str,
                             use_agc: bool, gain_corr: float) -> None:
        """Audio-only synthesis using libdspflmod pull API (C++ NCO engine).

        Replaces NumPy synthesis — handles 15+ carriers within the 1.6 ms
        block budget at 1.25 MS/s.  TCP sendall() backpressure paces the loop.
        """
        lib, handle = self._init_cpp_overlay(
            config, stations, sampling_rate, mix_level,
            base_port, audio_rate, mod_index, ffmpeg_bin,
            use_agc, gain_corr,
        )
        if lib is None:
            return

        try:
            N      = self.DATABLOCKSIZE // 2
            iq_buf = np.zeros(2 * N, dtype=np.float32)
            iq_ptr = iq_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            send_buf       = np.empty(2 * N, dtype=np.float32)
            blocks_per_sec = max(1, int(sampling_rate / N))
            self._block_count = 0

            print(f"[stemlab_eff] audio-only pull loop: N={N}, "
                  f"blocks_per_sec={blocks_per_sec}")

            while not self.stopix:
                if not self.get_pause():
                    gain = self.get_gain()
                    lib.dsp_flmod_set_gain(handle, ctypes.c_float(gain * gain_corr))

                    n_got = lib.dsp_flmod_pull_iq(handle, iq_ptr, ctypes.c_int(N))
                    if n_got <= 0:
                        self.SigError.emit("[stemlab_eff] dsp_flmod_pull_iq() returned error")
                        break

                    np.clip(iq_buf, -1.0, 1.0, out=send_buf)

                    try:
                        self.stemlabcontrol.data_sock.sendall(send_buf)
                    except Exception as exc:
                        if not self.stopix:
                            self.SigError.emit(f"[stemlab_eff] TCP send error: {exc}")
                        break

                    self._block_count += 1
                    if self._block_count >= blocks_per_sec:
                        self.SigIncrementCurTime.emit()
                        # Scale float ±1.0 → int16 ±32767 for spectrum display and AVC.
                        show_data = (
                            send_buf[:self.DATASHOWSIZE] * 32767.0
                        ).astype(np.int16)
                        self.set_data(show_data)
                        self._block_count = 0
                else:
                    time.sleep(0.1)
                    if self.stopix:
                        break
        finally:
            self._teardown_cpp_overlay(lib, handle)

    # ---------------------------------------------------------------- main loop
    def play_loop_filelist(self):
        self._play_loop_filelist_impl()

    def _play_loop_filelist_impl(self):
        filenames = self.get_filename()
        config    = self.get_configparameters()
        gain      = self.get_gain()
        TEST      = self.get_TEST()
        self.stopix = False
        self.set_fileclose(False)

        # ---- Read config_wizard.yaml ----------------------------------------
        _audioplaylist = ""
        _audio_rate    = 25000
        _mix_level     = 1.0
        _base_port     = 1234
        _mod_index     = 0.9
        _ffmpeg_bin    = "ffmpeg"
        _op_mode       = ""
        _use_agc       = False
        _gain_corr     = 1.0
        try:
            with open("config_wizard.yaml", "r") as _f:
                _cfg = yaml.safe_load(_f) or {}
            _audioplaylist = str(_cfg.get("audioplaylist",  "")).strip()
            _audio_rate    = int(_cfg.get("audio_rate_hz",  25000))
            _mix_level     = float(_cfg.get("audio_mix_level", 1.0))
            _base_port     = int(_cfg.get("audio_base_port", 1234))
            _mod_index     = float(_cfg.get("audio_mod_index", 0.9))
            _ffmpeg_bin    = _resolve_ffmpeg_bin(str(_cfg.get("ffmpeg_path", "")))
            _op_mode       = str(_cfg.get("last_modulator_type", "")).strip()
            _use_agc       = bool(_cfg.get("autoAGC_DspWorker",       False))
            _gain_corr     = float(_cfg.get("gain_correction_fl2k_C", 1.0))
            if _op_mode == "band_only":
                _audioplaylist = ""
                print("[stemlab_eff] operating mode = band_only: audio overlay suppressed")
        except Exception as _e:
            print(f"[stemlab_eff] config_wizard.yaml read error: {_e}; using defaults")

        has_iq    = bool(filenames)
        if _op_mode == "audio_only" or config.get("synth_only", False):
            has_iq = False
        _stations = parse_audio_playlist(_audioplaylist) if _audioplaylist else []
        has_audio = bool(_stations)

        sampling_rate = config["irate"]

        print(f"[stemlab_eff] mode: has_iq={has_iq}, has_audio={has_audio}, "
              f"SR={sampling_rate} S/s, stations={len(_stations)}")

        # ---- TEST mode ------------------------------------------------------
        if TEST:
            if has_iq:
                JUNKSIZE       = self.DATABLOCKSIZE // 2
                junkspersecond = sampling_rate / JUNKSIZE
                for filename in filenames:
                    self.SigNextfile.emit(filename)
                    try:
                        with open(filename, "rb") as fh:
                            fh.seek(216, 1)
                            data  = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
                            size  = fh.readinto(data)
                            count = 0
                            while size > 0 and not self.stopix:
                                time.sleep(JUNKSIZE / sampling_rate)
                                size = fh.readinto(data)
                                count += 1
                                if count >= junkspersecond:
                                    self.set_data(data[:self.DATASHOWSIZE].astype(np.float32))
                                    self.SigIncrementCurTime.emit()
                                    count = 0
                    except OSError as exc:
                        self.SigError.emit(f"TEST mode file error: {exc}")
            else:
                time.sleep(5)
            self.set_fileclose(True)
            self.SigFinished.emit()
            return

        # ---- Check TCP socket -----------------------------------------------
        if not hasattr(self.stemlabcontrol, "data_sock") or \
                self.stemlabcontrol.data_sock is None:
            self.SigError.emit(
                "[stemlab_eff] No TCP data socket – call config_socket() first."
            )
            self.SigFinished.emit()
            return

        # ---- Audio-only: C++ pull engine ------------------------------------
        if not has_iq and has_audio:
            self._run_eff_audio_only(
                config, _stations, sampling_rate,
                _mix_level, _base_port, _audio_rate, _mod_index, _ffmpeg_bin,
                _use_agc, _gain_corr,
            )
            self.set_fileclose(True)
            self.SigFinished.emit()
            return

        # ---- Start C++ overlay engine for IQ+Audio mode --------------------
        _cpp_lib    = None
        _cpp_handle = None
        if has_audio:
            _cpp_lib, _cpp_handle = self._init_cpp_overlay(
                config, _stations, sampling_rate, _mix_level,
                _base_port, _audio_rate, _mod_index, _ffmpeg_bin,
                _use_agc, _gain_corr,
            )
            if _cpp_lib is None:
                self.SigFinished.emit()
                return

        _dsp_times = []

        # Pre-allocate overlay buffer for IQ+Audio C++ pull
        N        = self.DATABLOCKSIZE // 2
        _ov_buf  = np.zeros(2 * N, dtype=np.float32)
        _ov_ptr  = _ov_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # ---- IQ-file mode (IQ-only or IQ+Audio) -----------------------------
        if has_iq:
            for ix, filename in enumerate(filenames):
                if self.stopix:
                    break
                self.SigNextfile.emit(filename)
                try:
                    fileHandle = open(filename, "rb")
                    self.set_fileHandle(fileHandle)
                    fmt = self.get_formattag()
                    self.set_datablocksize(self.DATABLOCKSIZE)
                    fileHandle.seek(216, 1)

                    if fmt[2] == 16:
                        data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
                    else:
                        data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)

                    normfactor     = (int(2 ** int(fmt[2] - 1)) - 1) if fmt[0] == 1 else 1
                    size           = fileHandle.readinto(data)
                    self.set_data(data)
                    timescaler     = self.get_timescaler()
                    junkspersecond = timescaler / (self.DATABLOCKSIZE * data.itemsize)
                    count          = 0
                    _block_file_pos = 216

                    _diag_done           = False
                    _block_budget_ms     = 1000.0 * (self.DATABLOCKSIZE // 2) / sampling_rate
                    _last_periodic_diag  = time.perf_counter()
                    _PERIODIC_DIAG_INTERVAL = 5.0
                    _iq_only_blocks      = 0

                    while size > 0 and not self.stopix:
                        if not self.get_pause():
                            _t_block_start = time.perf_counter()
                            n_elems   = size // data.itemsize
                            iq_float  = data[:n_elems].astype(np.float32) / normfactor
                            n_complex = n_elems // 2

                            if has_audio and _cpp_handle:
                                # Per-block gain update: C++ engine is gain authority
                                _cpp_lib.dsp_flmod_set_gain(
                                    _cpp_handle, ctypes.c_float(gain * _gain_corr)
                                )
                                n_got = _cpp_lib.dsp_flmod_pull_iq(
                                    _cpp_handle, _ov_ptr, ctypes.c_int(n_complex)
                                )
                                if n_got > 0:
                                    iq_i = iq_float[0::2]
                                    iq_q = iq_float[1::2]
                                    ov_i = _ov_buf[:2 * n_complex:2]
                                    ov_q = _ov_buf[1:2 * n_complex:2]
                                    result_i  = np.clip(gain * iq_i + _mix_level * ov_i,
                                                        -1.0, 1.0)
                                    result_q  = np.clip(gain * iq_q + _mix_level * ov_q,
                                                        -1.0, 1.0)
                                    send_data = np.empty(n_elems, dtype=np.float32)
                                    send_data[0::2] = result_i
                                    send_data[1::2] = result_q
                                else:
                                    send_data = (gain * iq_float).astype(np.float32)
                                    _iq_only_blocks += 1
                            else:
                                send_data = (gain * iq_float).astype(np.float32)

                            _last_dsp_ms = (time.perf_counter() - _t_block_start) * 1000.0
                            if has_audio:
                                _dsp_times.append(_last_dsp_ms)

                            if not _diag_done:
                                _diag_done = True
                                _nbytes = len(send_data) * send_data.itemsize
                                print(f"[stemlab_eff DIAG] fmt={fmt}, normfactor={normfactor}, "
                                      f"n_elems={n_elems}, gain={gain}, has_audio={has_audio}")
                                print(f"[stemlab_eff DIAG] send_data: len={len(send_data)}, "
                                      f"dtype={send_data.dtype}, bytes={_nbytes}")
                                print(f"[stemlab_eff DIAG] SR={sampling_rate}, "
                                      f"ifreq={config.get('ifreq','?')}, "
                                      f"DSP time={_last_dsp_ms:.2f} ms, "
                                      f"budget={_block_budget_ms:.2f} ms")

                            try:
                                self.stemlabcontrol.data_sock.sendall(send_data)
                            except BlockingIOError:
                                time.sleep(0.1)
                                self.SigError.emit("Blocking TCP socket error in stemlab_eff worker")
                                self._cleanup(_cpp_lib, _cpp_handle)
                                return
                            except ConnectionResetError:
                                time.sleep(0.1)
                                self.SigError.emit("TCP connection reset in stemlab_eff worker")
                                self._cleanup(_cpp_lib, _cpp_handle)
                                return
                            except Exception as exc:
                                time.sleep(0.1)
                                self.SigError.emit(f"TCP send error: {exc}")
                                self._cleanup(_cpp_lib, _cpp_handle)
                                return

                            _block_file_pos = fileHandle.tell()
                            size = fileHandle.readinto(data)
                            count += 1
                            if count > junkspersecond:
                                self.SigIncrementCurTime.emit()
                                count = 0
                                gain  = self.get_gain()
                                self.set_data(data)

                            _now = time.perf_counter()
                            if _now - _last_periodic_diag >= _PERIODIC_DIAG_INTERVAL:
                                _last_periodic_diag = _now
                                if _dsp_times:
                                    _dsp_avg = sum(_dsp_times) / len(_dsp_times)
                                    _dsp_max = max(_dsp_times)
                                    print(f"[stemlab_eff PERIODIC] "
                                          f"dsp_avg={_dsp_avg:.2f}ms dsp_max={_dsp_max:.2f}ms "
                                          f"({len(_dsp_times)} blk) "
                                          f"budget={_block_budget_ms:.2f}ms")
                                    _dsp_times.clear()
                                if has_audio and _cpp_handle:
                                    print(f"[stemlab_eff PERIODIC] "
                                          f"iq_only_blk={_iq_only_blocks}")
                                    _iq_only_blocks = 0
                        else:
                            time.sleep(0.1)
                            if self.stopix:
                                break

                    self.set_fileclose(True)
                    fileHandle.close()

                except OSError as exc:
                    self.SigError.emit(f"[stemlab_eff] File error: {exc}")

        else:
            self.SigError.emit(
                "[stemlab_eff] Neither IQ file nor audio playlist configured.\n"
                "Open a WAV file and/or set 'audioplaylist' in config_wizard.yaml."
            )

        self._cleanup(_cpp_lib, _cpp_handle)

    def _cleanup(self, cpp_lib=None, cpp_handle=None):
        if cpp_lib is not None:
            self._teardown_cpp_overlay(cpp_lib, cpp_handle)
        else:
            self._stop_audio_streams()
        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ---------------------------------------------------------------- rec_loop
    def rec_loop(self):
        """Recording via STEMLAB – delegates to stemlab_125_14 pattern."""
        self.GAINFACTOR = 1
        gain        = self.get_gain()
        size2G      = 2 ** 31
        self.stopix = False
        filename    = self.get_filename()
        timescaler  = self.get_timescaler()
        RECSEC      = timescaler * 2
        TEST        = self.get_TEST()

        fileHandle = open(filename, "ab")
        self.set_fileHandle(fileHandle)
        config     = self.get_configparameters()

        if not hasattr(self.stemlabcontrol, "data_sock") or \
                self.stemlabcontrol.data_sock is None:
            self.SigError.emit("[stemlab_eff] No TCP socket for recording.")
            self.SigFinished.emit()
            return

        try:
            while not self.stopix:
                data = self.stemlabcontrol.data_sock.recv(self.DATABLOCKSIZE * 2)
                if not data:
                    break
                arr = np.frombuffer(data, dtype=np.float32)
                arr = (arr * 32767.0).astype(np.int16)
                fileHandle.write(arr.tobytes())
        except Exception as exc:
            self.SigError.emit(f"[stemlab_eff] Recording error: {exc}")
        finally:
            fileHandle.close()
            self.set_fileHandle(None)
            self.set_fileclose(True)
            self.SigFinished.emit()
