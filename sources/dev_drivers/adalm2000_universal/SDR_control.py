"""
adalm2000_universal/SDR_control.py

Adapter for ADALM2000 in the 4-layer architecture.
Extends adalm2000/SDR_control.py with:
  - modulator: "P" (shows both IQ-file and audio-playlist GUI elements)
  - New unified adapter interface: setup(), teardown(), is_ready()
  - device_name: "adalm2000_universal"

Old methods (sdrserverstart, config_socket, sdrserverstop) kept unchanged.
"""
from PyQt5.QtCore import *
from socket import socket, AF_INET, SOCK_STREAM
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from scipy import signal as sig


class SDR_control(QObject):
    """Adapter class for ADALM2000 in the 4-layer architecture.

    Identification, server control (no-ops for USB-direct devices),
    and the new unified adapter interface (setup/teardown/is_ready).
    """
    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def identify(self):
        """Return device characteristics dict."""
        device_ID_dict = {
            "rates": {0: 0, 2500000: 1},
            "rate_type": "continuous",
            "RX": False,
            "TX": True,
            "device_name": "adalm2000_universal",
            "device_ID": 0,
            "max_IFREQ": 2500000,
            "min_IFREQ": 0,
            "resolutions": [16, 24, 32],
            "connection_type": "USB",
            "volume_mode": "crest",
            "modulator": "P",
        }
        return device_ID_dict

    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return True, "cannot record, RX mode not yet available in this device"

    def monitor(self):
        pass

    def config_socket(self, configparams):
        """DUMMY — ADALM2000 uses libm2k, not TCP sockets."""
        return True, "socket communication not applicable for ADALM2000"

    def startssh(self, configparams):
        """DUMMY — not used for ADALM2000."""
        return True, "SSH not applicable for ADALM2000"

    def sshsendcommandseq(self, shcomm):
        """DUMMY — not used for ADALM2000."""
        return True, "SSH not applicable for ADALM2000"

    def sdrserverstart(self, configparams):
        """DUMMY — ADALM2000 is USB-direct, no server needed."""
        return False, "sdrserver not applicable for ADALM2000"

    def sdrserverstop(self):
        """DUMMY — ADALM2000 is USB-direct, no server to stop."""
        return False, "sdrserver not applicable for ADALM2000"

    def RPShutdown(self, configparams):
        """Not applicable for ADALM2000."""
        return False, ""

    # === New unified adapter interface (Schritt 3) ===

    def setup(self, configparams) -> bool:
        """New unified adapter interface.
        ADALM2000 context is managed by the worker (libm2k init there).
        USB-direct: no server setup needed here.
        """
        return True

    def teardown(self) -> None:
        """New unified adapter interface.
        ADALM2000 context closed by the worker.
        """
        pass

    def is_ready(self) -> bool:
        """Check if ADALM2000 is reachable via libm2k."""
        try:
            import libm2k
            ctx = libm2k.m2kOpen()
            if ctx is not None:
                libm2k.contextClose(ctx)
                return True
        except Exception:
            pass
        return False
