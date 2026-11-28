"""
smisdr_common/worker_base.py
============================
Common playback worker of the smisdr_iq and smisdr_raw drivers.

Implements the worker contract of dev_drivers/<driver>/cohi_playrecworker.py as used by
player/playrec.py (set_* / get_* slots, play_loop_filelist, stop_loop and the signals
SigFinished, SigIncrementCurTime, SigNextfile, SigError, SigInfomessage), including the
nextfile chain.  What differs between the drivers is only the output stage, which a
subclass provides:

    _open_output(center_freq, sample_rate) -> bool   start / keep / re-configure for a track
    _write_block(iq, gain)                           one block, float32 +-1.0, interleaved I/Q
    _write_silence(frames)                           zero I/Q (pause)
    _close_output(graceful)                          end of play or stop
    _abort_output()                                  from the GUI thread: unblock a blocking write

Deliberate differences to the reference worker stemlab_125_14:
  * the clock of the time display counts the bytes actually read (the reference counts blocks
    and runs slow with 24/32 bit files)
  * the monitor data for showRFdata is in the native scale of the file, so that the
    normalisation in showRFdata is right for 24/32 bit as well
  * pause sends silence instead of nothing, so that the DAC does not keep the last value
    (with the DUC this would be an unmodulated carrier)
  * TEST mode (no device) runs in real time
"""
import logging
import os
import time

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from dev_drivers.smisdr_common import iqfile, protocol

logger = logging.getLogger("smisdr")


class SmisdrWorkerBase(QObject):
    SigFinished = pyqtSignal()
    SigIncrementCurTime = pyqtSignal()
    SigBufferOverflow = pyqtSignal()
    SigError = pyqtSignal(str)
    SigNextfile = pyqtSignal(str)
    SigInfomessage = pyqtSignal(str)

    DEVICE_NAME = "smisdr"
    pausestate = False      # attribute read by playrec.py
    # Level calibration of the AVC monitor relative to the reference driver (see
    # AVC_MONITOR_CAL_DB in stemlab_125_14). 0 dB = the monitor shows the true digital
    # output level; to be fine-tuned on the hardware if the AVC settles too high / low.
    AVC_MONITOR_CAL_DB = 0.0
    # playrec.py reads DATABLOCKSIZE (in int16 entries = 2 per I/Q frame)
    DATABLOCKSIZE = 8192
    SILENCE_FRAMES = 1024

    def __init__(self, sdrcontrol, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sdrcontrol = sdrcontrol
        self.stopix = False
        self.pausestate = False
        self._filename = []
        self._timescaler = 1
        self._test = False
        self._pause = False
        self._file_handle = None
        self._data = np.zeros(0, dtype=np.float32)
        self._gain = 1.0
        self._formattag = [1, 4, 16]
        self._datablocksize = self.DATABLOCKSIZE
        self._fileclose = False
        self._configparameters = {}
        self._monitor_cal = 10.0 ** (self.AVC_MONITOR_CAL_DB / 20.0)
        self._error_reported = False

    # ---- slots used by playrec.py ---------------------------------------------------
    def set_filename(self, value):         self._filename = value
    def get_filename(self):                return self._filename
    def set_timescaler(self, value):       self._timescaler = value
    def get_timescaler(self):              return self._timescaler
    def set_TEST(self, value):             self._test = value
    def get_TEST(self):                    return self._test
    def set_pause(self, value):            self._pause = value
    def get_pause(self):                   return self._pause
    def set_fileHandle(self, value):       self._file_handle = value
    def get_fileHandle(self):              return self._file_handle
    def set_data(self, value):             self._data = value
    def get_data(self):                    return self._data
    def set_gain(self, value):             self._gain = value
    def get_gain(self):                    return self._gain
    def set_formattag(self, value):        self._formattag = value
    def get_formattag(self):               return self._formattag
    def set_datablocksize(self, value):    self._datablocksize = value
    def get_datablocksize(self):           return self._datablocksize
    def set_fileclose(self, value):        self._fileclose = value
    def get_fileclose(self):               return self._fileclose
    def set_configparameters(self, value): self._configparameters = value
    def get_configparameters(self):        return self._configparameters
    def set_modality(self, value):         pass

    def stop_loop(self):
        """called from the GUI thread"""
        self.stopix = True
        try:
            self._abort_output()
        except Exception:                                  # must never break the stop button
            logger.exception("%s: abort of the output failed", self.DEVICE_NAME)

    def rec_loop(self):
        self.SigError.emit("{}: this driver can only play, it cannot record".format(self.DEVICE_NAME))
        self.SigFinished.emit()

    play_loop = rec_loop        # playrec.py only starts play_loop_filelist; kept as a safe stub

    # ---- output stage, provided by the driver --------------------------------------
    def _open_output(self, center_freq, sample_rate):
        raise NotImplementedError

    def _write_block(self, iq, gain):
        raise NotImplementedError

    def _write_silence(self, frames):
        raise NotImplementedError

    def _close_output(self, graceful):
        raise NotImplementedError

    def _abort_output(self):
        pass

    # ---- helpers ----------------------------------------------------------------
    def _effective_center(self, center_freq):
        """centre frequency incl. the ppm correction of the recording (as in stemlab_125_14).
        ifreq of the configuration already contains the LO offset (playrec.py)."""
        icorr = float(self._configparameters.get("icorr", 0) or 0)
        return float(center_freq) * (1.0 + 1e-6 * icorr)

    def _track_parameters(self, index, info, previous):
        """(centre frequency, sample rate) of a file. The first file uses the values of the
        configuration (which the user may have corrected in the GUI); the following files
        of a nextfile chain use their own header."""
        cfg = self._configparameters
        center = cfg.get("ifreq") if index == 0 else None
        if center is None and info.center_freq is not None:
            center = info.center_freq + float(cfg.get("LO_offset", 0) or 0)
        if center is None:
            center = previous[0] if previous else cfg.get("ifreq", 0)
        rate = cfg.get("irate") if index == 0 else None
        if not rate:
            rate = info.sample_rate
        if not rate:
            rate = previous[1] if previous else None
        return float(center), (float(rate) if rate else None)

    # ---- main loop --------------------------------------------------------------
    def play_loop_filelist(self):
        """worker loop: plays the list of files (nextfile chain) to the device.
        Signals: SigNextfile(filename) per file, SigIncrementCurTime once per second of
        playtime, SigError(message), SigFinished at the end (also after an error)."""
        self.stopix = False
        self._error_reported = False
        self.set_fileclose(False)
        aborted = False
        try:
            aborted = not self._play_files(list(self.get_filename() or []))
        except Exception as exc:                           # the thread must end cleanly
            logger.exception("%s: unexpected error in the playback loop", self.DEVICE_NAME)
            aborted = True
            self.SigError.emit("{}: unexpected error: {}".format(self.DEVICE_NAME, exc))
        finally:
            try:
                self._close_output(graceful=not aborted and not self.stopix)
            except Exception:
                logger.exception("%s: closing the output failed", self.DEVICE_NAME)
            self.set_fileclose(True)
        self.SigFinished.emit()

    def _play_files(self, filenames):
        """-> False if playback was aborted by an error"""
        previous = None
        for index, filename in enumerate(filenames):
            if self.stopix:
                break
            try:
                info = iqfile.read_info(filename)
            except Exception as exc:
                self.SigError.emit("{}: cannot read the header of {}: {}".format(
                    self.DEVICE_NAME, os.path.basename(str(filename)), exc))
                continue
            problem = iqfile.check_format(info.fmt_tag, info.bits, info.channels)
            if problem:
                self.SigError.emit("{}: {}: {}".format(self.DEVICE_NAME,
                                                       os.path.basename(str(filename)), problem))
                continue
            center, rate = self._track_parameters(index, info, previous)
            if not rate:
                self.SigError.emit("{}: the sample rate of {} is unknown".format(
                    self.DEVICE_NAME, os.path.basename(str(filename))))
                continue
            center = self._effective_center(center)
            previous = (center, rate)

            if not self.get_TEST() and not self._open_output(center, rate):
                return False                               # error has been emitted

            with open(filename, "rb") as fh:
                self.SigNextfile.emit(filename)
                self.set_fileHandle(fh)
                fh.seek(info.data_offset, 0)
                if not self._play_one_file(fh, info, rate):
                    return False
                self.set_fileclose(True)
        return True

    def _play_one_file(self, fh, info, rate):
        """-> False on a transmission error"""
        frames = max(256, self.DATABLOCKSIZE // 2)
        reader = iqfile.IqBlockReader(fh, info.fmt_tag, info.bits, frames, info.data_offset)
        timescaler = max(1, int(self.get_timescaler() or 1))
        bytes_since_tick = 0
        test_pacer = protocol.Pacer(rate) if self.get_TEST() else None
        while not self.stopix:
            if self.get_pause():
                if test_pacer is not None:
                    time.sleep(0.1)
                else:
                    try:
                        self._write_silence(self.SILENCE_FRAMES)
                    except OSError as exc:
                        return self._transmission_error(exc)
                continue
            block = reader.read()
            if block is None:
                break
            monitor, iq, nbytes = block
            if test_pacer is not None:
                test_pacer.pace(len(iq) // 2)
            else:
                try:
                    self._write_block(iq, self.get_gain())
                except OSError as exc:
                    return self._transmission_error(exc)
            bytes_since_tick += nbytes
            if bytes_since_tick >= timescaler:
                bytes_since_tick -= timescaler
                self.set_data(np.asarray(monitor, dtype=np.float32) * np.float32(self._monitor_cal))
                self.SigIncrementCurTime.emit()
        return True

    def _emit_error_once(self, message):
        """one error box per failure, even if two threads notice it (socket and process)"""
        if not self._error_reported:
            self._error_reported = True
            self.SigError.emit(message)

    def _transmission_error(self, exc):
        if self.stopix:                                    # the stop button closed the socket
            return True
        logger.error("%s: transmission error: %s", self.DEVICE_NAME, exc)
        self._emit_error_once("{}: connection to the device lost ({})".format(self.DEVICE_NAME, exc))
        return False
