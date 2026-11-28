"""
smisdr_iq_universal/SDR_control.py
==================================
smiSDR / parlioSDR with DUC gateware, with live audio carriers: IQ file and / or stations
(audio overlay / audio_only) through the signal chain of stemlab_universal; output as baseband
I/Q with in-band signalling (see smisdr_iq).  Playback only.
"""
from dev_drivers.smisdr_common import protocol, settings
from dev_drivers.smisdr_common.control_base import SmisdrLiveControlBase
from dev_drivers.smisdr_common.sinks import IqSink


class SDR_control(SmisdrLiveControlBase):

    def identify(self):
        try:
            ref_clock = settings.load_settings()["ref_clock"]
        except settings.SettingsError:
            ref_clock = protocol.DEFAULT_REF_CLOCK_HZ       # the error is reported by config_socket
        return {
            "rates":           {rate: ix for ix, rate in enumerate(protocol.SUPPORTED_IQ_RATES_HZ)},
            "rate_type":       "discrete",
            # RX is True like for stemlab_universal: with RX False the LO / sample rate fields of
            # the recorder tab, which audio_only mode uses, are disabled. set_rec() refuses.
            "RX":              True,
            "TX":              True,
            "device_name":     "smisdr_iq_universal",
            "device_ID":       4,
            "max_IFREQ":       int(protocol.MAX_EDGE_OF_NYQUIST * ref_clock / 2.0),
            "min_IFREQ":       0,
            "resolutions":     [16, 32],       # what the worker of stemlab_universal reads correctly
            "connection_type": "ethernet",                  # enables the IP address field
            "server_boot":     False,                       # always on: no startup wait
            "volume_mode":     "mean",
            "watchdog":        False,
        }

    def _make_sink(self, host, cfg):
        return IqSink(host, cfg, idle_silence=True)
