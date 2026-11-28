"""
smisdr_iq/cohi_playrecworker.py
===============================
Playback worker for smiSDR / parlioSDR with DUC gateware (baseband I/Q, in-band signalling).

Per track (file) whose centre frequency or sample rate differs from the running connection,
the output stage (smisdr_common/sinks.py: IqSink) is reconfigured as COHI-Player-Universal does:
    control port: "width 16", "rate <2 x I/Q rate in MSps>"   (optional, see settings)
    data port:    new connection, then the in-band commands 'S' (NCO) and 'R' (input rate),
                  then 16 bit words: 14 bit I and Q samples with tags
Files with the same parameters follow gapless on the same connection.  The output is paced
to the I/Q sample rate (the FPGA consumes at that rate; TCP alone would run ahead).
"""
from dev_drivers.smisdr_common.sinks import IqSink, SinkError
from dev_drivers.smisdr_common.worker_base import SmisdrWorkerBase


class playrec_worker(SmisdrWorkerBase):
    DEVICE_NAME = "smisdr_iq"

    def __init__(self, sdrcontrol, *args, **kwargs):
        super().__init__(sdrcontrol, *args, **kwargs)
        self._sink = None

    def _open_output(self, center_freq, sample_rate):
        if self._sink is None:
            self._sink = IqSink(self.sdrcontrol.host, self.sdrcontrol.settings)
        try:
            self._sink.open(center_freq, sample_rate)
        except SinkError as exc:
            self.SigError.emit("{}: {}".format(self.DEVICE_NAME, exc))
            return False
        return True

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
