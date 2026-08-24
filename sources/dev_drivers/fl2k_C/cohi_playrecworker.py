"""
fl2k_fast.py – COHIWizard device driver worker for fl2k USB-VGA DAC

Replaces the ffmpeg + fl2k_file subprocess pipeline with a single C++
shared library (libdspfl2k.so) that does:
  • IQ resampling and NCO frequency shift via liquiddsp
  • Direct fl2k device I/O via libosmo-fl2k

Drop-in replacement for cohi_playrecworker.py:
  • Same class name  playrec_worker(QObject)
  • Same __slots__ / accessor methods
  • Same Qt signals

Prerequisites:
  1. Build libdspfl2k.so in the same directory as this file:
       cd dev_drivers/fl2k_stream && make
  2. The fl2k USB-VGA dongle must be connected.

Author: scharfetter  (generated 2026)
"""

import ctypes
import os
import time
import signal as _signal

import numpy as np
import psutil
import yaml
from PyQt5.QtCore import QObject, QMutex, QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Load and configure the shared library
# ---------------------------------------------------------------------------

def _load_lib() -> ctypes.CDLL | None:
    """Load libdspfl2k.so from the same directory as this module."""
    here = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(here, "libdspfl2k.so")
    try:
        lib = ctypes.CDLL(lib_path)
    except OSError as exc:
        print(f"[fl2k_fast] Cannot load libdspfl2k.so: {exc}\n"
              f"  Build it with:  cd {here} && make")
        return None

    VoidP  = ctypes.c_void_p
    Int    = ctypes.c_int
    Float  = ctypes.c_float
    CharP  = ctypes.c_char_p
    FloatP = ctypes.POINTER(ctypes.c_float)

    # --- lifecycle ---
    lib.dsp_fl2k_create.restype  = VoidP
    lib.dsp_fl2k_create.argtypes = []

    lib.dsp_fl2k_destroy.restype  = None
    lib.dsp_fl2k_destroy.argtypes = [VoidP]

    lib.dsp_fl2k_configure.restype  = Int
    lib.dsp_fl2k_configure.argtypes = [
        VoidP,              # handle
        Float,              # target_rate
        Float,              # shift_freq
        Float,              # gain
        Int,                # use_agc
        ctypes.POINTER(ctypes.c_char_p),   # filenames[]
        Int,                # num_files
    ]

    # --- callbacks ---
    MonitorCB  = ctypes.CFUNCTYPE(None, FloatP, Int, VoidP)
    ProgressCB = ctypes.CFUNCTYPE(None, Float, VoidP)
    FinishedCB = ctypes.CFUNCTYPE(None, VoidP)
    ErrorCB    = ctypes.CFUNCTYPE(None, CharP, VoidP)
    NextfileCB = ctypes.CFUNCTYPE(None, CharP, VoidP)

    lib.dsp_fl2k_set_monitor_cb.restype  = None
    lib.dsp_fl2k_set_monitor_cb.argtypes = [VoidP, MonitorCB, VoidP]

    lib.dsp_fl2k_set_progress_cb.restype  = None
    lib.dsp_fl2k_set_progress_cb.argtypes = [VoidP, ProgressCB, VoidP]

    lib.dsp_fl2k_set_finished_cb.restype  = None
    lib.dsp_fl2k_set_finished_cb.argtypes = [VoidP, FinishedCB, VoidP]

    lib.dsp_fl2k_set_error_cb.restype  = None
    lib.dsp_fl2k_set_error_cb.argtypes = [VoidP, ErrorCB, VoidP]

    lib.dsp_fl2k_set_nextfile_cb.restype  = None
    lib.dsp_fl2k_set_nextfile_cb.argtypes = [VoidP, NextfileCB, VoidP]

    # --- control ---
    lib.dsp_fl2k_start.restype  = Int
    lib.dsp_fl2k_start.argtypes = [VoidP]

    lib.dsp_fl2k_stop.restype  = None
    lib.dsp_fl2k_stop.argtypes = [VoidP]

    lib.dsp_fl2k_set_pause.restype  = None
    lib.dsp_fl2k_set_pause.argtypes = [VoidP, Int]

    lib.dsp_fl2k_set_gain.restype  = None
    lib.dsp_fl2k_set_gain.argtypes = [VoidP, Float]

    lib.dsp_fl2k_is_running.restype  = Int
    lib.dsp_fl2k_is_running.argtypes = [VoidP]

    lib.dsp_fl2k_check_device.restype  = Int
    lib.dsp_fl2k_check_device.argtypes = []

    lib.dsp_fl2k_seek.restype  = None
    lib.dsp_fl2k_seek.argtypes = [VoidP, ctypes.c_int64, Int]

    # Keep ctypes callback types alive on the lib object so they are not GC'd
    lib._MonitorCB  = MonitorCB
    lib._ProgressCB = ProgressCB
    lib._FinishedCB = FinishedCB
    lib._ErrorCB    = ErrorCB
    lib._NextfileCB = NextfileCB
    print(f"[fl2k_fast] Loaded libdspfl2k.so from {lib_path}")
    return lib


_LIB = _load_lib()


# ---------------------------------------------------------------------------
# File-handle proxy: routes Python seek() calls to the C++ DSP engine
# ---------------------------------------------------------------------------

class _SeekProxy:
    """Thin proxy returned by get_fileHandle().

    playrec_c.jump_to_position_c() and jump_1_byte() call
        proxy.seek(offset, whence)
    which forwards the request to dsp_fl2k_seek() so the C++ DSP thread
    performs the actual file seek at the next block boundary and flushes
    the ring buffer.
    """
    def __init__(self, handle, lib):
        self._handle = handle
        self._lib    = lib

    def seek(self, offset, whence=0):
        self._lib.dsp_fl2k_seek(
            self._handle, ctypes.c_int64(offset), ctypes.c_int(whence)
        )


# ---------------------------------------------------------------------------
# playrec_worker – drop-in replacement for cohi_playrecworker.playrec_worker
# ---------------------------------------------------------------------------

class playrec_worker(QObject):
    """
    Worker class for streaming COHIRadio WAV files to the fl2k USB-VGA DAC.

    The COHIWizard core accesses state exclusively through the slot accessors
    below.  All DSP and hardware I/O runs inside a C++ shared library; this
    class provides the Qt signal / slot bridge.

    Slot dictionary  __slots__[i]  (same layout as the original driver):
      0  filename            – list of WAV file paths
      1  timescaler          – bytes per second (informational)
      2  TEST                – True → dry-run mode (no hardware output)
      3  pause               – True → mute output while keeping device alive
      4  fileHandle          – current open file handle (informational)
      5  data                – 1024-float monitor window (written every ~1 s)
      6  gain                – amplitude scale factor  [0 … 2]
      7  formattag           – [wFormatTag, blockAlign, bitsPerSample]
      8  datablocksize       – read block size in bytes
      9  fileclose           – set True when last file is closed
     10  configparameters    – dict with ifreq, irate, rates, icorr, …
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

    # ----------------------------------------------------------------
    def __init__(self, sdrcontrol_inst, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopix         = False
        self.DATASHOWSIZE   = 1024
        self.mutex          = QMutex()
        self.stemlabcontrol = sdrcontrol_inst
        self._handle        = None   # C++ DspFL2KHandle

    # ---------------------------------------------------------------- accessors
    def set_filename(self, v):    self.__slots__[0] = v
    def get_filename(self):       return self.__slots__[0]
    def set_timescaler(self, v):  self.__slots__[1] = v
    def get_timescaler(self):     return self.__slots__[1]
    def set_TEST(self, v):        self.__slots__[2] = v
    def get_TEST(self):           return self.__slots__[2]
    def set_pause(self, v):       self.__slots__[3] = v
    def get_pause(self):          return self.__slots__[3]
    def set_fileHandle(self, v):  self.__slots__[4] = v
    def get_fileHandle(self):     return self.__slots__[4]
    def set_data(self, v):        self.__slots__[5] = v
    def get_data(self):           return self.__slots__[5]
    def set_gain(self, v):        self.__slots__[6] = v
    def get_gain(self):           return self.__slots__[6]
    def set_formattag(self, v):   self.__slots__[7] = v
    def get_formattag(self):      return self.__slots__[7]
    def set_datablocksize(self, v): self.__slots__[8] = v
    def get_datablocksize(self):    return self.__slots__[8]
    def set_fileclose(self, v):   self.__slots__[9] = v
    def get_fileclose(self):      return self.__slots__[9]
    def set_configparameters(self, v): self.__slots__[10] = v
    def get_configparameters(self):    return self.__slots__[10]

    # ----------------------------------------------------------------
    def stop_loop(self):
        """Signal the play loop to terminate."""
        self.stopix = True

    # ----------------------------------------------------------------
    def play_loop_filelist(self):
        """
        Main entry point called by the COHIWizard QThread.

        Sets up the C++ DSP engine, starts it, then drives a lightweight
        polling loop that:
          • forwards pause / gain changes to C++
          • relays monitoring data → set_data + SigIncrementCurTime
          • propagates next-file notifications → SigNextfile
          • propagates error messages → SigError
          • emits SigFinished when done
        """
        if _LIB is None:
            self.SigError.emit(
                "libdspfl2k.so not found. Build it with  make  in the "
                "fl2k_stream driver directory."
            )
            self.SigFinished.emit()
            return

        filenames  = self.get_filename()   # list of paths
        TEST       = self.get_TEST()
        gain       = self.get_gain()
        config     = self.get_configparameters()
        self.stopix = False
        self.set_fileclose(False)

        # ---- Read fl2k_C-specific settings from config_wizard.yaml -----
        _use_agc_cpp   = False   # default: use Python-computed gain
        _gain_corr     = 1.0     # default: no correction
        try:
            with open("config_wizard.yaml", "r") as _f:
                _cfg = yaml.safe_load(_f) or {}
            _use_agc_cpp = bool(_cfg.get("autoAGC_DspWorker", False))
            _gain_corr   = float(_cfg.get("gain_correction_fl2k_C", 1.0))
        except Exception as _e:
            print(f"[fl2k_C] Could not read config_wizard.yaml: {_e}; using defaults")

        sampling_rate = config["irate"]
        lo_shift      = config["ifreq"]

        # Compute optimal fl2k DAC rate (same formula as original Python driver)
        tSR = 10_000_000 * (1 + int((lo_shift + sampling_rate / 2) * 2 / 10_000_000))
        tSR = min(100_000_000, tSR)

        # Warn if resampling ratio is non-power-of-two
        ratio = tSR / sampling_rate
        if sampling_rate > 500_000:
            import math
            is_pow2 = (math.log2(ratio) % 1 == 0)
            if not is_pow2:
                self.SigInfomessage.emit(
                    f"The ratio target_rate / source_rate ({ratio:.4f}) is not a "
                    f"power of 2. This may cause playback artefacts or instability "
                    f"at sample rates > 500 kS/s. Consider resampling the recording "
                    f"so that the ratio is 2, 4, 8, 16, …"
                )

        # ---- TEST mode: simulate timing without hardware ----------------
        if TEST:
            self._run_test_mode(filenames, sampling_rate)
            return

        # ---- Check device before allocating resources ------------------
        self.mutex.lock()
        if _LIB.dsp_fl2k_check_device() != 0:
            print("[fl2k_fast] fl2k device not found")
            self.SigError.emit(
                "fl2k device not found. Please check the USB-VGA dongle connection."
            )
            self.SigFinished.emit()
            self.mutex.unlock()
            self.timer.sleep(2)  # give the GUI a moment to update before returning
            return
        self.mutex.unlock()

        # ---- Create C++ worker -----------------------------------------
        handle = _LIB.dsp_fl2k_create()
        if not handle:
            self.SigError.emit("dsp_fl2k_create() returned NULL")
            self.SigFinished.emit()
            return
        self._handle = handle

        # Expose seek proxy so playrec_c.jump_to_position_c() / jump_1_byte() work
        self.set_fileHandle(_SeekProxy(handle, _LIB))

        # ---- Configure --------------------------------------------------
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

        # ---- Register callbacks (refs kept alive for GC) ----------------
        @_LIB._MonitorCB
        def _on_monitor(data_ptr, n, _ud):
            arr = np.ctypeslib.as_array(data_ptr, shape=(n,)).copy()
            self.set_data(arr)
            self.SigIncrementCurTime.emit()

        @_LIB._ErrorCB
        def _on_error(msg_ptr, _ud):
            if msg_ptr:
                self.SigError.emit(msg_ptr.decode(errors="replace"))

        @_LIB._NextfileCB
        def _on_nextfile(path_ptr, _ud):
            if path_ptr:
                self.SigNextfile.emit(path_ptr.decode(errors="replace"))

        @_LIB._FinishedCB
        def _on_finished(_ud):
            pass   # handled in the polling loop below

        _LIB.dsp_fl2k_set_monitor_cb (handle, _on_monitor,  None)
        _LIB.dsp_fl2k_set_error_cb   (handle, _on_error,    None)
        _LIB.dsp_fl2k_set_nextfile_cb(handle, _on_nextfile, None)
        _LIB.dsp_fl2k_set_finished_cb(handle, _on_finished, None)

        # ---- Start ------------------------------------------------------
        rc = _LIB.dsp_fl2k_start(handle)
        if rc != 0:
            codes = {-1: "already running", -2: "no files configured",
                     -3: "fl2k device failed to open"}
            self.SigError.emit(
                f"dsp_fl2k_start failed (code {rc}: {codes.get(rc, '?')})"
            )
            _LIB.dsp_fl2k_destroy(handle)
            self._handle = None
            self.SigFinished.emit()
            return

        # ---- Polling loop -----------------------------------------------
        while _LIB.dsp_fl2k_is_running(handle) and not self.stopix:
            # Propagate pause state
            _LIB.dsp_fl2k_set_pause(handle, 1 if self.get_pause() else 0)
            # When C++ AGC is active it manages gain internally; only push Python
            # gain when running in manual mode (autoAGC_DspWorker = false).
            if not _use_agc_cpp:
                _LIB.dsp_fl2k_set_gain(
                    handle, ctypes.c_float(float(self.get_gain()) * _gain_corr)
                )
            QThread.msleep(50)

        # ---- Cleanup ----------------------------------------------------
        _LIB.dsp_fl2k_stop(handle)
        _LIB.dsp_fl2k_destroy(handle)
        self._handle = None

        self.set_fileHandle(None)
        self.set_fileclose(True)
        self.SigFinished.emit()

    # ----------------------------------------------------------------
    def _run_test_mode(self, filenames, sampling_rate):
        """Dry-run: advance file position + emit timing signals; no hardware."""
        DATABLOCKSIZE = 1024 * 64
        JUNKSIZE      = DATABLOCKSIZE // 2
        junkspersecond = sampling_rate / JUNKSIZE

        for filename in filenames:
            self.SigNextfile.emit(filename)
            try:
                with open(filename, "rb") as fh:
                    fh.seek(216, 1)
                    data = np.empty(DATABLOCKSIZE, dtype=np.int16)
                    size = fh.readinto(data)
                    count = 0
                    while size > 0 and not self.stopix:
                        if not self.get_pause():
                            time.sleep(JUNKSIZE / sampling_rate)
                            size = fh.readinto(data)
                            count += 1
                            if count >= junkspersecond:
                                self.set_data(data[: self.DATASHOWSIZE].astype(np.float32))
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
        """Not applicable – fl2k is TX only."""
        return

    # ----------------------------------------------------------------
    # Compatibility helpers (kept from original driver)
    # ----------------------------------------------------------------

    def kill_orphan_fl2k(self):
        """Kill any stale fl2k_file processes left from a previous session."""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                cmd  = " ".join(proc.info.get("cmdline") or []).lower()
                if "fl2k_file" in name or "fl2k_file" in cmd:
                    print(f"[fl2k_fast] killing orphan fl2k_file PID {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
