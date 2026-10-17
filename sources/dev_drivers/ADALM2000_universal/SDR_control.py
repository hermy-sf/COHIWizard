"""
SDR_control.py — ADALM2000_universal

Adapter for ADALM2000 in the 4-layer architecture.
Three operational modes (selected at runtime by cohi_playrecworker.py):
  Mode A: IQ-file present, optional audio overlay  (modulator = "P")
  Mode B: audio_only – pure AM synthesis, no IQ file
  Error:  neither configured

device_name "ADALM2000_universal" differs from "adalm2000_universal" so
both drivers can coexist in the GUI device list.
"""
from PyQt5.QtCore import QObject, pyqtSignal


class SDR_control(QObject):

    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError   = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def identify(self):
        return {
            "rates":           {0: 0, 2500000: 1},
            "rate_type":       "continuous",
            "RX":              False,
            "TX":              True,
            "device_name":     "ADALM2000_universal",
            "device_ID":       0,
            "max_IFREQ":       2500000,
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "USB",
            "volume_mode":     "crest",
            "modulator":       "P",
        }

    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return True, "cannot record – RX mode not available on ADALM2000"

    def monitor(self):
        pass

    def config_socket(self, configparams):
        return True, "socket communication not applicable for ADALM2000"

    def startssh(self, configparams):
        return True, "SSH not applicable for ADALM2000"

    def sshsendcommandseq(self, shcomm):
        return True, "SSH not applicable for ADALM2000"

    def sdrserverstart(self, configparams):
        return False, "sdrserver not applicable for ADALM2000"

    def sdrserverstop(self):
        return False, "sdrserver not applicable for ADALM2000"

    def RPShutdown(self, configparams):
        return False, ""

    def setup(self, configparams) -> bool:
        return True

    def teardown(self) -> None:
        pass

    def is_ready(self) -> bool:
        try:
            import libm2k
            ctx = libm2k.m2kOpen()
            if ctx is not None:
                libm2k.contextClose(ctx)
                return True
        except Exception:
            pass
        return False
