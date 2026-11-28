"""
smisdr_raw_universal/SDR_control.py
===================================
smiSDR / parlioSDR with finished RF samples (RAW HF), with live audio carriers: IQ file and / or
stations through the signal chain of stemlab_universal; the host converts the I/Q signal to the
RF band with cohi_native_upconverter (see smisdr_raw).  Playback only.
"""
from dev_drivers.smisdr_common import protocol, rawlink, settings
from dev_drivers.smisdr_common.control_base import SmisdrLiveControlBase
from dev_drivers.smisdr_common.sinks import RawSink


class SDR_control(SmisdrLiveControlBase):

    def identify(self):
        try:
            rate = settings.load_settings()["sample_rate"]
        except settings.SettingsError:
            rate = protocol.RATE_AUTO                       # the error is reported by config_socket
        top = protocol.SMISDR_RATES_HZ[-1] if rate == protocol.RATE_AUTO else rate
        return {
            "rates":           {1_000: 0, 10_000_000: 1},
            "rate_type":       "continuous",
            "RX":              True,           # see smisdr_iq_universal; set_rec() refuses
            "TX":              True,
            "device_name":     "smisdr_raw_universal",
            "device_ID":       5,
            "max_IFREQ":       int(protocol.MAX_EDGE_OF_NYQUIST * top / 2.0),
            "min_IFREQ":       0,
            "resolutions":     [16, 32],
            "connection_type": "ethernet",
            "server_boot":     False,
            "volume_mode":     "mean",
            "watchdog":        False,
        }

    def _check_settings(self, cfg):
        problem = settings.raw_problem(cfg)
        if problem:
            return problem
        if rawlink.resolve_tool_path(cfg["upconverter_path"]) is None:
            where = cfg["upconverter_path"] or "dev_drivers/smisdr_common/upconverter or PATH"
            return ("{} not found ({}). Build it with 'make' in dev_drivers/smisdr_common/upconverter or set "
                    "smisdr_upconverter_path in config_wizard.yaml.".format(rawlink.TOOL_NAME, where))
        return None

    def _make_sink(self, host, cfg):
        return RawSink(host, cfg, idle_silence=True)
