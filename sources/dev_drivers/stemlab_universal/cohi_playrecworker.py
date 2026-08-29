"""
stemlab_universal/cohi_playrecworker.py
COHIWizard device-driver worker for STEMlab 125-14, extended for 3 operating modes:

  IQ-only    — WAV file streamed as raw I/Q via TCP (identical to stemlab_125_14)
  IQ+Audio   — WAV file I/Q mixed with AM-modulated live audio streams (numpy DSP)
  Audio-only — Pure AM synthesis from CSV playlist, no WAV file required

Audio pipeline (IQ+Audio and Audio-only):
  ffmpeg → u8 PCM mono @ audio_rate_hz → UDP socket → _AudioBuffer (ring buffer)
  → _modulate_audio_channels() (numpy AM modulation) → TCP to STEMLAB

CSV format (semicolon-separated):
  Frequenz;Bandbreite;Programmname;URL

config_wizard.yaml keys used:
  audioplaylist      str    path to CSV; empty / absent → overlay disabled
  audio_rate_hz      int    PCM sample rate for ffmpeg (default 25000)
  audio_mix_level    float  audio amplitude relative to IQ level (default 1.0)
  audio_base_port    int    first UDP port, increments per channel (default 1234)
  audio_mod_index    float  AM modulation index 0–1 (default 0.9)
  ffmpeg_path        str    ffmpeg binary (default 'ffmpeg')
"""

import csv
import math
import os
import socket as _socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse, urlunparse

import numpy as np
import yaml
from scipy.signal import resample_poly
from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Helper functions (shared with fl2k_fast_plus pattern)
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
    import platform
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    raw = (raw or "").strip()
    if not raw:
        return "ffmpeg"
    if os.path.isdir(raw):
        candidate = os.path.join(raw, exe_name)
        if os.path.isfile(candidate):
            return candidate
        print(f"[stemlab_univ] ffmpeg_path '{raw}' has no {exe_name} – falling back to PATH.")
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
                    print(f"[stemlab_univ] CSV line {lineno}: expected 4 columns – skipped")
                    continue
                freq_s, bw_s, name_s, url_s = (p.strip() for p in parts[:4])
                if freq_s.lower() in ("frequenz", "frequency", "freq"):
                    continue
                try:
                    freq_hz = _parse_freq(freq_s)
                    bw_hz   = _parse_freq(bw_s) if bw_s else 9000.0
                except ValueError:
                    print(f"[stemlab_univ] CSV line {lineno}: cannot parse '{freq_s}'/'{bw_s}' – skipped")
                    continue
                stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz,
                                 "name": name_s, "url": url_s})
    except OSError as exc:
        print(f"[stemlab_univ] Cannot read playlist '{csv_path}': {exc}")
    return stations


# ---------------------------------------------------------------------------
# Thread-safe UDP audio ring buffer
# ---------------------------------------------------------------------------

class _AudioBuffer:
    """Receives u8 PCM audio via UDP from ffmpeg and stores in a ring buffer.

    ffmpeg sends packets of 256 bytes (pkt_size=256).  Each byte is one u8
    PCM sample (0–255).  We normalise to float32 in [-1, +1].
    """

    def __init__(self, udp_port: int, capacity: int = 500_000):
        self._sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", udp_port))
        self._sock.settimeout(0.1)
        self._buf  = np.zeros(capacity, dtype=np.float32)
        self._cap  = capacity
        self._wp   = 0
        self._rp   = 0
        self._lock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while not self._stop:
            try:
                raw     = self._sock.recv(8192)
                samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                with self._lock:
                    for s in samples:
                        self._buf[self._wp] = s
                        self._wp = (self._wp + 1) % self._cap
            except _socket.timeout:
                pass
            except Exception as exc:
                if not self._stop:
                    print(f"[stemlab_univ] AudioBuffer UDP reader error: {exc}")

    def read(self, n: int) -> np.ndarray:
        """Return n samples (float32, [-1,+1]). Zeros on underrun."""
        out = np.zeros(n, dtype=np.float32)
        with self._lock:
            available = (self._wp - self._rp) % self._cap
            to_read   = min(n, available)
            for i in range(to_read):
                out[i]   = self._buf[self._rp]
                self._rp = (self._rp + 1) % self._cap
        return out

    def close(self):
        self._stop = True
        self._thread.join(timeout=1.5)
        try:
            self._sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """Worker for STEMlab 125-14 with universal mode support.

    Modes (selected automatically at runtime):
      IQ-only    – WAV file → TCP → STEMLAB
      IQ+Audio   – WAV file + AM-modulated audio streams → TCP → STEMLAB
      Audio-only – AM-modulated audio streams only → TCP → STEMLAB

    __slots__ layout (COHIWizard standard):
      0  filename, 1 timescaler, 2 TEST, 3 pause, 4 fileHandle,
      5  data, 6 gain, 7 formattag, 8 datablocksize, 9 fileclose,
      10 configparameters
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
    def _start_audio_streams(self, stations: list, base_port: int,
                              audio_rate: int, mod_index: float,
                              ffmpeg_bin: str) -> list:
        """Start one ffmpeg process per station. Returns channel dicts."""
        channels = []
        for idx, sta in enumerate(stations):
            port      = base_port + idx
            url       = sta["url"]
            bw_hz     = sta["bw_hz"]
            name      = sta["name"]
            lowpass_f = max(100, int(bw_hz / 2))

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
                    print(f"[stemlab_univ] Cannot read m3u '{url}': {_exc}")

                _entries = [e for e in _entries if os.path.isfile(e)]
                if not _entries:
                    print(f"[stemlab_univ] m3u '{url}': no valid files – channel skipped.")
                    continue

                import tempfile as _tf
                _cf = _tf.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="stemuniv_concat_",
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
                cmd = [
                    ffmpeg_bin,
                    "-reconnect", "1", "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "5",
                    "-i", _ffmpeg_url(url),
                    "-af", f"lowpass=f={lowpass_f},volume=0.8",
                    "-f", "u8", "-ar", str(audio_rate), "-ac", "1",
                    f"udp://127.0.0.1:{port}?pkt_size=256",
                ]

            import pathlib
            _logfile = pathlib.Path(tempfile.gettempdir()) / f"stemuniv_ffmpeg_ch{idx}.log"

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
                print(f"[stemlab_univ] ffmpeg ch[{idx}] '{name}' "
                      f"@ {sta['freq_hz'] / 1e3:.1f} kHz -> UDP {port} "
                      f"(PID {proc.pid}), log -> {_logfile}")
                self._ffmpeg_procs.append(proc)
                channels.append({
                    "freq_hz":   sta["freq_hz"],
                    "bw_hz":     bw_hz,
                    "name":      name,
                    "udp_port":  port,
                    "mod_index": mod_index,
                })
            except OSError as exc:
                print(f"[stemlab_univ] Failed to start ffmpeg for '{name}': {exc}")

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
        print("[stemlab_univ] Audio streams stopped.")

    # ----------------------------------------------------------- AM DSP engine
    def _modulate_audio_channels(self, audio_buffers, channels,
                                  n_samples: int, sample_rate: float,
                                  audio_rate: float, sample_offset: int):
        """Compute AM overlay for n_samples IQ pairs at sample_rate.

        Returns (overlay_i, overlay_q) as float32 arrays of length n_samples.
        Each channel: I+jQ = A*(1 + m*a(t)) * exp(j*2π*f_c*t)
        """
        # Audio samples needed for this block at audio_rate
        audio_n = max(1, int(round(n_samples * audio_rate / sample_rate)))

        # Time axis for this IQ block
        t = (np.arange(n_samples, dtype=np.float64) + sample_offset) / sample_rate

        overlay_i = np.zeros(n_samples, dtype=np.float32)
        overlay_q = np.zeros(n_samples, dtype=np.float32)

        for buf, ch in zip(audio_buffers, channels):
            audio_raw = buf.read(audio_n)           # float32 [-1, +1]

            # Resample audio from audio_rate → sample_rate
            g         = math.gcd(n_samples, audio_n)
            audio_up  = resample_poly(audio_raw, n_samples // g, audio_n // g)
            audio_up  = audio_up[:n_samples].astype(np.float32)

            # AM modulation envelope: 1 + m*a(t)
            amp   = (1.0 + ch["mod_index"] * audio_up.astype(np.float64)).astype(np.float32)
            phase = (2.0 * np.pi * ch["freq_hz"] * t).astype(np.float32)

            overlay_i += amp * np.cos(phase)
            overlay_q += amp * np.sin(phase)

        # Normalise by channel count to prevent clipping
        n_ch = max(1, len(channels))
        overlay_i /= n_ch
        overlay_q /= n_ch

        return overlay_i, overlay_q

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
        try:
            with open("config_wizard.yaml", "r") as _f:
                _cfg = yaml.safe_load(_f) or {}
            _audioplaylist = str(_cfg.get("audioplaylist",  "")).strip()
            _audio_rate    = int(_cfg.get("audio_rate_hz",  25000))
            _mix_level     = float(_cfg.get("audio_mix_level", 1.0))
            _base_port     = int(_cfg.get("audio_base_port", 1234))
            _mod_index     = float(_cfg.get("audio_mod_index", 0.9))
            _ffmpeg_bin    = _resolve_ffmpeg_bin(str(_cfg.get("ffmpeg_path", "")))
        except Exception as _e:
            print(f"[stemlab_univ] config_wizard.yaml read error: {_e}; using defaults")

        has_iq    = bool(filenames)
        _stations = parse_audio_playlist(_audioplaylist) if _audioplaylist else []
        has_audio = bool(_stations)

        sampling_rate = config["irate"]

        print(f"[stemlab_univ] mode: has_iq={has_iq}, has_audio={has_audio}, "
              f"SR={sampling_rate} S/s")

        # ---- TEST mode ------------------------------------------------------
        if TEST:
            if has_iq:
                JUNKSIZE      = self.DATABLOCKSIZE // 2
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
                "[stemlab_univ] No TCP data socket – call config_socket() first "
                "(via sdrserverstart + boot-wait + config_socket or setup())."
            )
            self.SigFinished.emit()
            return

        # ---- Start audio streams if needed ----------------------------------
        _channels      = []
        _audio_buffers = []
        if has_audio:
            _channels = self._start_audio_streams(
                _stations, _base_port, _audio_rate, _mod_index, _ffmpeg_bin
            )
            if _channels:
                print(f"[stemlab_univ] Waiting 1 s for ffmpeg to start streaming...")
                time.sleep(1.0)
                for ch in _channels:
                    buf = _AudioBuffer(ch["udp_port"], capacity=500_000)
                    _audio_buffers.append(buf)
                time.sleep(0.5)   # pre-fill ring buffers

        # ---- IQ-file mode (IQ-only or IQ+Audio) -----------------------------
        if has_iq:
            sample_offset = 0
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

                    normfactor    = (int(2 ** int(fmt[2] - 1)) - 1) if fmt[0] == 1 else 1
                    size          = fileHandle.readinto(data)
                    self.set_data(data)
                    timescaler    = self.get_timescaler()
                    junkspersecond = timescaler / self.DATABLOCKSIZE
                    count         = 0

                    while size > 0 and not self.stopix:
                        if not self.get_pause():
                            iq_float  = gain * data[:size].astype(np.float32) / normfactor
                            n_complex = size // 2   # I/Q pairs

                            if has_audio and _audio_buffers:
                                iq_i = iq_float[0::2]
                                iq_q = iq_float[1::2]

                                ov_i, ov_q = self._modulate_audio_channels(
                                    _audio_buffers, _channels, n_complex,
                                    sampling_rate, _audio_rate, sample_offset
                                )
                                sample_offset += n_complex

                                result_i  = np.clip(iq_i + _mix_level * ov_i, -1.0, 1.0)
                                result_q  = np.clip(iq_q + _mix_level * ov_q, -1.0, 1.0)
                                send_data = np.empty(size, dtype=np.float32)
                                send_data[0::2] = result_i
                                send_data[1::2] = result_q
                            else:
                                send_data = iq_float

                            try:
                                self.stemlabcontrol.data_sock.send(send_data)
                            except BlockingIOError:
                                time.sleep(0.1)
                                self.SigError.emit("Blocking TCP socket error in stemlab_universal worker")
                                self.SigFinished.emit()
                                self._cleanup(_audio_buffers)
                                return
                            except ConnectionResetError:
                                time.sleep(0.1)
                                self.SigError.emit("TCP connection reset in stemlab_universal worker")
                                self.SigFinished.emit()
                                self._cleanup(_audio_buffers)
                                return
                            except Exception as exc:
                                time.sleep(0.1)
                                self.SigError.emit(f"TCP send error: {exc}")
                                self.SigFinished.emit()
                                self._cleanup(_audio_buffers)
                                return

                            size = fileHandle.readinto(data)
                            count += 1
                            if count > junkspersecond:
                                self.SigIncrementCurTime.emit()
                                count = 0
                                gain  = self.get_gain()
                                self.set_data(data)
                        else:
                            time.sleep(0.1)
                            if self.stopix:
                                break

                    self.set_fileclose(True)
                    fileHandle.close()

                except OSError as exc:
                    self.SigError.emit(f"[stemlab_univ] File error: {exc}")

        # ---- Audio-only mode ------------------------------------------------
        elif has_audio:
            N          = self.DATABLOCKSIZE // 2   # complex samples per block
            block_time = N / sampling_rate
            blocks_per_sec = max(1, int(sampling_rate / N))
            sample_offset  = 0
            self._block_count = 0

            while not self.stopix:
                if not self.get_pause():
                    ov_i, ov_q = self._modulate_audio_channels(
                        _audio_buffers, _channels, N,
                        sampling_rate, _audio_rate, sample_offset
                    )
                    sample_offset += N

                    result_i  = np.clip(_mix_level * ov_i, -1.0, 1.0)
                    result_q  = np.clip(_mix_level * ov_q, -1.0, 1.0)
                    send_data = np.empty(2 * N, dtype=np.float32)
                    send_data[0::2] = result_i
                    send_data[1::2] = result_q

                    try:
                        self.stemlabcontrol.data_sock.send(send_data)
                    except Exception as exc:
                        if not self.stopix:
                            self.SigError.emit(f"[stemlab_univ] TCP send error (audio-only): {exc}")
                        break

                    # Pace to real-time (with slight safety margin)
                    time.sleep(block_time * 0.85)

                    self._block_count += 1
                    if self._block_count >= blocks_per_sec:
                        self.SigIncrementCurTime.emit()
                        self._block_count = 0
                else:
                    time.sleep(0.1)
                    if self.stopix:
                        break

        else:
            self.SigError.emit(
                "[stemlab_univ] Neither IQ file nor audio playlist configured.\n"
                "Open a WAV file and/or set 'audioplaylist' in config_wizard.yaml."
            )

        # ---- Cleanup --------------------------------------------------------
        self._cleanup(_audio_buffers)

    def _cleanup(self, audio_buffers):
        for buf in audio_buffers:
            buf.close()
        self._stop_audio_streams()
        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ---------------------------------------------------------------- rec_loop
    def rec_loop(self):
        """Recording via STEMLAB – delegates to stemlab_125_14 pattern."""
        self.GAINFACTOR = 1
        gain       = self.get_gain()
        size2G     = 2 ** 31
        self.stopix = False
        filename   = self.get_filename()
        timescaler = self.get_timescaler()
        RECSEC     = timescaler * 2
        TEST       = self.get_TEST()

        fileHandle = open(filename, "ab")
        self.set_fileHandle(fileHandle)
        fmt = self.get_formattag()
        self.set_datablocksize(self.DATABLOCKSIZE)
        data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
        self.BUFFERFULL = self.DATABLOCKSIZE * 4

        if hasattr(self.stemlabcontrol, "data_sock"):
            size = self.stemlabcontrol.data_sock.recv_into(data)
        else:
            size = 1
        self.set_data((data[:size // 4] * 32767).astype(np.int16))

        count     = 0
        readbytes = 0
        totbytes  = 0

        while size > 0 and not self.stopix:
            if not TEST:
                self.mutex.lock()
                fileHandle.write(
                    (gain * self.GAINFACTOR * data[:size // 4] * 32767).astype(np.int16)
                )
                size      = self.stemlabcontrol.data_sock.recv_into(data)
                readbytes += size
                if readbytes > RECSEC:
                    gain = self.get_gain()
                    self.set_data((gain * data[:size // 4] * 32767).astype(np.int16))
                    self.SigIncrementCurTime.emit()
                    totbytes  += int(readbytes / 2)
                    readbytes  = 0
                if totbytes > size2G - self.DATABLOCKSIZE * 4:
                    self.stopix = True
                self.mutex.unlock()
            else:
                time.sleep(1)
                self.SigBufferOverflow.emit()
                count += 1
                self.SigIncrementCurTime.emit()
                self.mutex.lock()
                data[0] = 0.05
                fileHandle.write((data[:2] * 32767).astype(np.int16))
                self.set_data((data[:2] * 32767).astype(np.int16))
                self.mutex.unlock()
                time.sleep(0.1)

        self.SigFinished.emit()
