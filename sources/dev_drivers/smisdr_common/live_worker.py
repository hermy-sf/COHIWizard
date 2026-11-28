"""
smisdr_common/live_worker.py
============================
Worker of the live drivers smisdr_iq_universal / smisdr_raw_universal.

It IS the worker of stemlab_universal (IQ file and / or audio carriers: ffmpeg per station ->
UDP -> libdspflmod NCO engine -> mixer -> float32 I/Q -> ``data_sock.sendall()``), so station
lists (csv / extended m3u), modulation depth, mix level, the Mixer slider, AGC, audio_only
mode etc. behave exactly as with the other universal drivers.  Only the destination differs:
``data_sock`` is the output stage of the smiSDR / parlioSDR (sinks.py).

What this subclass adds around the inherited loop:
  * the output stage is closed (silence first) when the worker finishes, also after errors
  * stop: the output is aborted, because a blocking send cannot be interrupted otherwise
  * nextfile chain: a file with a different centre frequency / sample rate reconfigures the
    device (like smisdr_iq / smisdr_raw); with an audio overlay this is refused, because the
    carriers of the overlay engine are fixed to the parameters of the first file
Note: the log lines of the inherited code say "[stemlab_universal]".
"""
import logging

from dev_drivers.smisdr_common import iqfile
from dev_drivers.smisdr_common.sinks import SinkError
from dev_drivers.stemlab_universal.cohi_playrecworker import playrec_worker as _UniversalWorker

logger = logging.getLogger("smisdr")


class SmisdrLiveWorker(_UniversalWorker):
    DEVICE_NAME = "smisdr_universal"

    def __init__(self, sdrcontrol, *args, **kwargs):
        super().__init__(sdrcontrol, *args, **kwargs)
        self._files_seen = 0
        # direct connections: they run in the worker thread, before the slots of the GUI
        self.SigFinished.connect(self._on_finished)
        self.SigNextfile.connect(self._on_nextfile)

    def stop_loop(self):
        super().stop_loop()
        try:
            self.stemlabcontrol.abort_sink()
        except Exception:                                  # must never break the stop button
            logger.exception("%s: abort of the output failed", self.DEVICE_NAME)

    def _on_finished(self):
        try:
            self.stemlabcontrol.close_sink(graceful=not self.stopix)
        except Exception:
            logger.exception("%s: closing the output failed", self.DEVICE_NAME)

    def _on_nextfile(self, filename):
        self._files_seen += 1
        if self._files_seen == 1:
            return                  # the first file: config_socket() has configured the device for it
        sink = getattr(self.stemlabcontrol, "sink", None)
        if sink is None:
            return
        try:
            info = iqfile.read_info(filename)
        except Exception:
            return                  # the worker reports unreadable files itself
        cfg = self.get_configparameters()
        icorr = float(cfg.get("icorr", 0) or 0)
        center = info.center_freq
        center = cfg.get("ifreq") if center is None else center + float(cfg.get("LO_offset", 0) or 0)
        rate = info.sample_rate or cfg.get("irate")
        center = float(center) * (1.0 + 1e-6 * icorr)
        before = sink.params
        try:
            sink.open(center, float(rate))
        except SinkError as exc:
            self._refuse("{}: {}".format(self.DEVICE_NAME, exc))
            return
        if sink.params != before and self._ffmpeg_procs:
            self._refuse("{}: the files of this chain have different centre frequencies / sample rates, "
                         "which cannot be combined with an audio overlay (the carriers are fixed to "
                         "the first file). Play them one by one, or use the mode 'IQ band only'."
                         .format(self.DEVICE_NAME))

    def _refuse(self, message):
        self.SigError.emit(message)
        self.stopix = True
