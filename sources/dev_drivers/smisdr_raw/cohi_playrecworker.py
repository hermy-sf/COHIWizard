"""
smisdr_raw/cohi_playrecworker.py
================================
Playback worker for smiSDR / parlioSDR with finished RF samples (RAW HF).

I/Q blocks of the recording go (scaled by the gain, as int16) into cohi_native_upconverter;
its output (RF samples at 5 / 10 / 12.5 MSps) is forwarded to the data port by a pump thread
(smisdr_common/rawlink.py, RawSink).  Files with the same centre frequency and sample rate
follow gapless on the same chain, otherwise the chain is rebuilt for the new file.
"""
from dev_drivers.smisdr_common.sinks import RawSink, SinkError
from dev_drivers.smisdr_common.worker_base import SmisdrWorkerBase


class playrec_worker(SmisdrWorkerBase):
    DEVICE_NAME = "smisdr_raw"

    def __init__(self, sdrcontrol, *args, **kwargs):
        super().__init__(sdrcontrol, *args, **kwargs)
        self._sink = None

    def _open_output(self, center_freq, sample_rate):
        if self._sink is None:
            self._sink = RawSink(self.sdrcontrol.host, self.sdrcontrol.settings,
                                 on_error=self._link_error)
        try:
            self._sink.open(center_freq, sample_rate)
        except SinkError as exc:
            self.SigError.emit("{}: {}".format(self.DEVICE_NAME, exc))
            return False
        return True

    def _link_error(self, message):
        """called from a link thread; a broken chain also makes the next write fail"""
        if not self.stopix:
            self._emit_error_once("{}: {}".format(self.DEVICE_NAME, message))

    def _write_block(self, iq, gain):
        self._sink.send_iq(iq, gain)

    def _write_silence(self, frames):
        self._sink.send_silence(frames)

    def _abort_output(self):
        if self._sink is not None:
            self._sink.abort()

    def _close_output(self, graceful):
        sink, self._sink = self._sink, None
        if sink is not None:
            sink.close(graceful)
