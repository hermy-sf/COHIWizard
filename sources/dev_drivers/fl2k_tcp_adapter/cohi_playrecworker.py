"""
fl2k_tcp_adapter / cohi_playrecworker.py  —  Schritt 5 Skeleton
COHIWizard 4-Layer architecture: placeholder worker for TCP-output mode.

STATUS: SKELETON
----------------
This driver is a placeholder for the future TCP-output mode of libdspfl2k.so.

Today, fl2k_universal writes directly to fl2k USB via libdspfl2k.so.
When libdspfl2k.so gets a TCP output mode, this driver will:
  1. Configure the C++ worker to output to TCP localhost:1234
  2. The fl2k_tcp_adapter/SDR_control.py starts fl2k_tcp on port 1235
  3. socat redirects 1234 → 1235
  4. fl2k_tcp drives the USB dongle

Until then: selecting this driver shows a clear status message and exits.

SMISDR integration (alternative):
  SMISDR listens on port 1234 directly.  Once the worker has TCP output,
  SMISDR can be used without socat by pointing it at port 1234.
"""

import time
from PyQt5.QtCore import QObject, QMutex, pyqtSignal


class playrec_worker(QObject):
    """
    Skeleton worker for fl2k_tcp_adapter.

    Emits an informational message explaining the current status and exits.
    Replace this with the actual TCP-output implementation once
    libdspfl2k.so supports dsp_fl2k_configure_tcp_output().
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
        self.mutex          = QMutex()
        self.stemlabcontrol = sdrcontrol_inst

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

    def play_loop_filelist(self):
        self._play_loop_filelist_impl()

    def _play_loop_filelist_impl(self):
        self.stopix = False
        self.set_fileclose(False)

        msg = (
            "fl2k_tcp_adapter: TCP-Ausgabemodus noch nicht verfügbar.\n"
            "\n"
            "Dieser Adapter ist ein Skeleton für die zukünftige TCP-Ausgabe von "
            "libdspfl2k.so.\n"
            "\n"
            "Was noch fehlt:\n"
            "  • libdspfl2k.so braucht dsp_fl2k_configure_tcp_output() (C++-Änderung)\n"
            "  • Dann: Worker → TCP:1234, socat 1234→1235, fl2k_tcp auf 1235\n"
            "\n"
            "Für jetzt fl2k_universal verwenden (USB-Direktmodus, voll funktionsfähig).\n"
            "Für SMISDR/radiolab81: sobald TCP-Ausgabe verfügbar ist, diesen Adapter nutzen."
        )
        self.SigInfomessage.emit(msg)
        print(f"[fl2k_tcp_adapter] {msg}")

        time.sleep(0.5)
        self.set_fileclose(True)
        self.SigFinished.emit()

    def rec_loop(self):
        return

    def kill_orphan_fl2k(self):
        pass
