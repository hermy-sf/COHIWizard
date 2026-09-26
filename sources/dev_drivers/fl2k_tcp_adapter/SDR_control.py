"""
fl2k_tcp_adapter / SDR_control.py  —  Schritt 5 Adapter-Skeleton
COHIWizard 4-Layer architecture: Adapter layer for fl2k via TCP.

PURPOSE
-------
This adapter starts the fl2k_tcp binary (from osmo-fl2k) as a TCP server on
port 1235.  A DSP-Worker that outputs data to TCP localhost:1234 can then be
redirected to this server via socat:

    socat TCP:localhost:1234 TCP:localhost:1235

CURRENT STATUS
--------------
SKELETON — Not yet fully functional.

The fl2k_universal worker (and its underlying libdspfl2k.so) currently outputs
data DIRECTLY to the fl2k USB device, not to a TCP socket.  To complete the
Schritt-5 architecture, libdspfl2k.so needs a TCP output mode added in C++:

    dsp_fl2k_configure_tcp_output(handle, "127.0.0.1", 1234)

Once that is available, this adapter's setup() method will:
  1. Start fl2k_tcp binary on port 1235 (already implemented below)
  2. Start socat redirecting 1234 → 1235
  3. The worker outputs to port 1234

WHAT IS IMPLEMENTED NOW
------------------------
- fl2k_tcp server startup / teardown (sdrserverstart / sdrserverstop)
- socat redirect management (setup / teardown)
- New unified adapter interface (setup, teardown, is_ready)

For SMISDR as client: SMISDR listens on port 1234 directly.  Replace the
socat step with no-op and point SMISDR at the worker's output port.

USAGE AS FALLBACK TODAY
------------------------
Set modulator_type: "all" in config_wizard.yaml, then select fl2k_tcp_adapter
in the device list.  The driver will report a warning that TCP output is not
yet available and exit gracefully.
"""

import os
import subprocess
import time

from PyQt5.QtCore import QObject, pyqtSignal


# Path to the fl2k_tcp binary (same location as other fl2k tools)
_HERE = os.path.dirname(os.path.abspath(__file__))
_FL2K_DIR = os.path.join(_HERE, "..", "__osmo-fl2k-64bit-20250105")


def _find_fl2k_tcp() -> str | None:
    """Find fl2k_tcp binary in the known osmo-fl2k directory."""
    import platform
    exe = "fl2k_tcp.exe" if platform.system() == "Windows" else "fl2k_tcp"
    candidate = os.path.join(_FL2K_DIR, exe)
    if os.path.isfile(candidate):
        return candidate
    # Fallback: search PATH
    import shutil
    return shutil.which("fl2k_tcp")


class SDR_control(QObject):
    """
    Adapter layer: starts fl2k_tcp binary as TCP server, manages socat redirect.

    4-Layer role: ADAPTER (Ebene 3)
    Sits between DSP-Worker (Ebene 2) and fl2k hardware client (Ebene 4).

    Existing COHIWizard interface (sdrserverstart / config_socket / sdrserverstop)
    is preserved. New unified interface (setup / teardown / is_ready) added.
    """

    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError   = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fl2k_tcp_proc = None
        self._socat_proc    = None
        self._fl2k_port     = 1235   # fl2k_tcp listens here
        self._worker_port   = 1234   # DSP-Worker outputs here (future)

    def identify(self):
        device_ID_dict = {
            "rates":           {1000: 0, 5000000: 1},
            "rate_type":       "continuous",
            "RX":              False,
            "TX":              True,
            "device_name":     "fl2k_tcp_adapter",
            "device_ID":       1,
            "max_IFREQ":       100000000,
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "USB",
            "watchdog":        False,
            "volume_mode":     "mean",
            "modulator":       "P",
        }
        return device_ID_dict

    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return True, "fl2k_tcp_adapter: recording not supported"

    def monitor(self):
        pass

    def config_socket(self, configparams):
        """No-op: TCP routing is handled by setup() / socat."""
        return False, ""

    def startssh(self, configparams):
        return False, "fl2k_tcp_adapter: SSH not applicable"

    def sshsendcommandseq(self, shcomm):
        return False, "fl2k_tcp_adapter: SSH not applicable"

    def sdrserverstart(self, configparams):
        """
        Start fl2k_tcp binary as TCP server on port 1235.
        The sample rate is derived from configparams["irate"].
        """
        errorstate = False
        value = ["", None]

        fl2k_tcp = _find_fl2k_tcp()
        if fl2k_tcp is None:
            msg = (f"fl2k_tcp binary not found in {_FL2K_DIR}. "
                   "Build osmo-fl2k or check __osmo-fl2k-64bit-20250105/.")
            self.SigError.emit(msg)
            errorstate = True
            value[0] = msg
            return errorstate, value

        # Stop any leftover instance first
        self._stop_fl2k_tcp()

        irate = configparams.get("irate", 10_000_000)
        cmd = [fl2k_tcp, "-a", "127.0.0.1", "-p", str(self._fl2k_port),
               "-s", str(irate)]

        try:
            self._fl2k_tcp_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            if self._fl2k_tcp_proc.poll() is not None:
                msg = "fl2k_tcp process terminated immediately after start."
                self.SigError.emit(msg)
                errorstate = True
                value[0] = msg
                return errorstate, value

            self.SigMessage.emit(
                f"fl2k_tcp started on port {self._fl2k_port} "
                f"@ {irate/1e6:.1f} MS/s (PID {self._fl2k_tcp_proc.pid})"
            )
            value[0] = "__process"
            value[1] = self._fl2k_tcp_proc
        except OSError as exc:
            msg = f"Cannot start fl2k_tcp: {exc}"
            self.SigError.emit(msg)
            errorstate = True
            value[0] = msg

        return errorstate, value

    def sdrserverstop(self):
        """Stop fl2k_tcp and socat."""
        self._stop_socat()
        self._stop_fl2k_tcp()
        return False, ""

    def RPShutdown(self, configuration):
        self.sdrserverstop()
        return False, ""

    # ----------------------------------------------------------------
    # === New unified adapter interface (Schritt 3 / Schritt 5) ===
    # ----------------------------------------------------------------

    def setup(self, configparams) -> bool:
        """
        New unified adapter interface.

        Starts fl2k_tcp server and socat redirect.

        NOTE: This will only be fully functional once libdspfl2k.so supports
        TCP output (dsp_fl2k_configure_tcp_output).  Until then, the DSP-Worker
        (fl2k_universal) writes directly to USB and this adapter is a skeleton.
        """
        err, _ = self.sdrserverstart(configparams)
        if err:
            return False

        # Start socat to redirect worker port 1234 → fl2k_tcp port 1235
        # Uncomment once the worker actually outputs to TCP 1234:
        # self._start_socat()

        self.SigMessage.emit(
            "[fl2k_tcp_adapter] NOTE: TCP output from DSP-Worker not yet available. "
            "libdspfl2k.so requires a TCP output mode (C++ change pending). "
            "fl2k_tcp server is running but will receive no data."
        )
        return True

    def teardown(self) -> None:
        """New unified adapter interface: stop fl2k_tcp server and socat."""
        self.sdrserverstop()

    def is_ready(self) -> bool:
        """Check if fl2k_tcp process is running."""
        if self._fl2k_tcp_proc is None:
            return False
        return self._fl2k_tcp_proc.poll() is None

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------

    def _stop_fl2k_tcp(self):
        if self._fl2k_tcp_proc is not None:
            try:
                self._fl2k_tcp_proc.terminate()
                self._fl2k_tcp_proc.wait(timeout=3)
            except Exception:
                try:
                    self._fl2k_tcp_proc.kill()
                except Exception:
                    pass
            self._fl2k_tcp_proc = None

    def _start_socat(self):
        """Start socat: redirect TCP localhost:1234 → localhost:1235."""
        import shutil
        socat = shutil.which("socat")
        if socat is None:
            self.SigMessage.emit("[fl2k_tcp_adapter] socat not found in PATH — skipping redirect.")
            return
        try:
            self._socat_proc = subprocess.Popen(
                [socat,
                 f"TCP:127.0.0.1:{self._worker_port}",
                 f"TCP:127.0.0.1:{self._fl2k_port}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.SigMessage.emit(
                f"[fl2k_tcp_adapter] socat redirect: "
                f"{self._worker_port} → {self._fl2k_port} (PID {self._socat_proc.pid})"
            )
        except OSError as exc:
            self.SigMessage.emit(f"[fl2k_tcp_adapter] socat start failed: {exc}")

    def _stop_socat(self):
        if self._socat_proc is not None:
            try:
                self._socat_proc.terminate()
                self._socat_proc.wait(timeout=2)
            except Exception:
                try:
                    self._socat_proc.kill()
                except Exception:
                    pass
            self._socat_proc = None
