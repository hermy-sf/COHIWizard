"""
smisdr_common/control_base.py
=============================
Common part of the SDR_control adapters of smisdr_iq and smisdr_raw.

Both devices are network devices without a server to start: smiSDR / parlioSDR are always
on.  The adapter therefore only validates the settings; the connections are opened by the
playback worker (one data connection per play, see worker_base.py).  The legacy interface
that playrec.py calls (sdrserverstart / config_socket / sdrserverstop / RPShutdown ...)
is kept, the unified adapter interface (setup / teardown / is_ready) is provided as well.
"""
import logging

from PyQt5.QtCore import QObject, pyqtSignal

from dev_drivers.smisdr_common import settings
from dev_drivers.smisdr_common.sinks import IqSink, RawSink, SinkError

logger = logging.getLogger("smisdr")


class SmisdrControlBase(QObject):
    SigError = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modality = "play"
        self.settings = None
        self.host = None
        self._ready = False

    # ---- identification: provided by the driver ---------------------------------
    def identify(self):
        raise NotImplementedError

    def _load_settings(self):
        """-> settings dict or None (error has been signalled)"""
        try:
            return settings.load_settings()
        except settings.SettingsError as exc:
            logger.error("smisdr: %s", exc)
            self.SigError.emit(str(exc))
            return None

    def _check_settings(self, cfg):
        """driver specific checks of the settings, -> message or None"""
        return None

    # ---- unified adapter interface ------------------------------------------------
    def setup(self, configparams) -> bool:
        return bool(self.config_socket(configparams))

    def teardown(self) -> None:
        self.sdrserverstop()

    def is_ready(self) -> bool:
        return self._ready

    # ---- legacy interface used by playrec.py --------------------------------------
    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return True, "cannot record - {} can only play".format(self.identify()["device_name"])

    def monitor(self):
        pass

    def config_socket(self, configparams):
        """Validates host address and settings. No connection is made here: smiSDR servers
        may accept only one connection per port, and the worker needs exactly that one."""
        host = str(configparams.get("HostAddress", "")).strip()
        if not host:
            self.SigError.emit("no IP address of the smiSDR / parlioSDR given")
            return False
        cfg = self._load_settings()
        if cfg is None:
            return False
        problem = self._check_settings(cfg)
        if problem:
            self.SigError.emit(problem)
            return False
        self.settings = cfg
        self.host = host
        self._ready = True
        self.SigMessage.emit("{}: target {}:{}".format(self.identify()["device_name"], host, cfg["data_port"]))
        return True

    def startssh(self, configparams):
        return False, ""

    def sshsendcommandseq(self, shcomm):
        return

    def sdrserverstart(self, configparams):
        """nothing to start; returns (errorstate, [message, process]) like the other drivers"""
        return False, ["", None]

    def sdrserverstop(self):
        self._ready = False
        return False, ""

    def RPShutdown(self, configuration=None):
        """There is no server to shut down. Called with the configuration dict by the
        shutdown button and with [command, worker] lists by the (inactive) watchdog."""
        return False, ""


class SmisdrLiveControlBase(SmisdrControlBase):
    """Adapter of the live drivers (smisdr_iq_universal, smisdr_raw_universal).

    The worker of these drivers is the one of stemlab_universal: it produces the signal (IQ file
    and / or audio carriers) and writes float32 I/Q to ``data_sock.sendall()``, like to the
    STEMLAB socket.  Here ``data_sock`` is the output stage (sinks.py), opened by config_socket()
    with the centre frequency and sample rate of the Player (ifreq incl. ppm correction, irate)."""

    SINK_CLASS = None            # IqSink / RawSink

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sink = None
        self.data_sock = None

    def _make_sink(self, host, cfg):
        raise NotImplementedError

    def config_socket(self, configparams):
        if not super().config_socket(configparams):
            return False
        name = self.identify()["device_name"]
        try:
            center = float(configparams["ifreq"]) * (1.0 + 1e-6 * float(configparams.get("icorr", 0) or 0))
            rate = float(configparams["irate"])
        except (KeyError, TypeError, ValueError) as exc:
            self.SigError.emit("{}: centre frequency / sample rate missing ({})".format(name, exc))
            return False
        self.close_sink(graceful=False)
        sink = self._make_sink(self.host, self.settings)
        try:
            sink.open(center, rate)
        except SinkError as exc:
            sink.close(graceful=False)
            logger.error("%s: %s", name, exc)
            self.SigError.emit("{}: {}".format(name, exc))
            return False
        self.sink = self.data_sock = sink
        self.SigMessage.emit("{}: output started (centre {} Hz, {} Hz)".format(name, int(center), int(rate)))
        return True

    def close_sink(self, graceful=True):
        sink, self.sink, self.data_sock = self.sink, None, None
        if sink is not None:
            sink.close(graceful)

    def abort_sink(self):
        """GUI thread (stop button): unblocks a send in the worker thread"""
        if self.sink is not None:
            self.sink.abort()

    def sdrserverstop(self):
        self.close_sink(graceful=False)
        return super().sdrserverstop()
