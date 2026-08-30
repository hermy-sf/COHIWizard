"""
SDR_control.py  –  fl2k_universal adapter
4-layer architecture: Adapter layer for the fl2k USB-VGA DAC.

fl2k is a direct-USB device: no server, no network socket.
This adapter is therefore mostly a no-op, but it provides:
  - the legacy COHIWizard interface (sdrserverstart / config_socket / sdrserverstop)
  - the new unified adapter interface (setup / teardown / is_ready) for Schritt 3
"""
from PyQt5.QtCore import QObject, pyqtSignal
import os
import subprocess
import time


class SDR_control(QObject):
    """Adapter for the fl2k USB-VGA DAC (universal variant).

    Legacy interface (kept for compatibility with playrec.py):
        sdrserverstart / config_socket / sdrserverstop / startssh / sshsendcommandseq

    New unified adapter interface (Schritt 3):
        setup(configparams) -> bool
        teardown() -> None
        is_ready() -> bool
    """

    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError   = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchdog_count  = 0
        self.watchdog_active = False

    # ------------------------------------------------------------------
    # Device identification
    # ------------------------------------------------------------------
    def identify(self):
        """Return device characteristics dict consumed by playrec_v."""
        return {
            "rates":           {1000: 0, 5_000_000: 1},
            "rate_type":       "continuous",
            "RX":              False,
            "TX":              True,
            "device_name":     "fl2k_universal",
            "device_ID":       1,
            "max_IFREQ":       100_000_000,
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "USB",
            "watchdog":        True,
            "volume_mode":     "mean",
        }

    # ------------------------------------------------------------------
    # New unified adapter interface (Schritt 3)
    # ------------------------------------------------------------------
    def setup(self, configparams) -> bool:
        """Unified adapter setup. fl2k is USB-direct — nothing to start."""
        return True

    def teardown(self) -> None:
        """Unified adapter teardown. USB device is released by the worker."""
        pass

    def is_ready(self) -> bool:
        """Unified readiness check. Hardware presence is verified inside the worker."""
        return True

    # ------------------------------------------------------------------
    # Legacy interface (kept for playrec.py compatibility)
    # ------------------------------------------------------------------
    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return True, "cannot record – no RX mode available on fl2k"

    def monitor(self):
        pass

    def config_socket(self, configparams):
        """Legacy no-op: fl2k is driven directly by libdspfl2k.so, no TCP socket."""
        return False, ""

    def startssh(self, configparams):
        """Legacy no-op: fl2k needs no SSH."""
        return False, ""

    def sshsendcommandseq(self, shcomm):
        """Legacy no-op."""
        return

    def sdrserverstart(self, configparams):
        """Legacy no-op: libdspfl2k.so opens the USB device directly."""
        return False, ["", None]

    def sdrserverstop(self):
        """Legacy no-op."""
        return False, ""

    def RPShutdown(self, configuration):
        """Watchdog / orphan-kill handler called by playrec_c via SigRelay."""
        errorstate = False
        value      = ""
        try:
            testitem, worker = configuration
            if testitem.find("watchdog_start") > -1:
                self.watchdog_active = True
            if testitem.find("handle_no_fl2k") > -1:
                if worker is not None:
                    worker.kill_orphan_fl2k()
                print("[fl2k_universal] no dongle found – orphan processes cleaned")
                errorstate = True
                value = "fl2k_universal: no dongle found"
            if testitem.find("watchdog_increment") > -1 and self.watchdog_active:
                self.watchdog_count += 1
                if self.watchdog_count > 25:
                    self.watchdog_count  = 0
                    self.watchdog_active = False
            if testitem.find("watchdog_reset") > -1:
                self.watchdog_count = 0
        except Exception:
            pass
        return errorstate, value
