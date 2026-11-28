"""
smisdr_raw/SDR_control.py
=========================
Adapter for smiSDR / parlioSDR with finished RF samples (RAW HF): the host converts the
I/Q recording to the RF band with cohi_native_upconverter (C++, tested tool of
COHI-Player-Universal) and sends the samples to the device (5 / 10 / 12.5 MSps, 8 bit or
8/10/12/14 bit in 16 bit).  Playback only.
"""
from dev_drivers.smisdr_common import protocol, settings
from dev_drivers.smisdr_common.control_base import SmisdrControlBase
from dev_drivers.smisdr_common import rawlink as link


class SDR_control(SmisdrControlBase):

    def identify(self):
        try:
            cfg = settings.load_settings()
            rate = cfg["sample_rate"]
        except settings.SettingsError:
            rate = protocol.RATE_AUTO                       # the error is reported by config_socket
        top = protocol.SMISDR_RATES_HZ[-1] if rate == protocol.RATE_AUTO else rate
        return {
            # any recording rate up to the output rate can be interpolated by the upconverter
            "rates":           {1_000: 0, 10_000_000: 1},
            "rate_type":       "continuous",
            "RX":              False,
            "TX":              True,
            "device_name":     "smisdr_raw",
            "device_ID":       3,
            "max_IFREQ":       int(protocol.MAX_EDGE_OF_NYQUIST * top / 2.0),
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "ethernet",                  # enables the IP address field
            "server_boot":     False,                       # always on: no startup wait
            "volume_mode":     "mean",
            "watchdog":        False,
        }

    def _check_settings(self, cfg):
        problem = settings.raw_problem(cfg)
        if problem:
            return problem
        if link.resolve_tool_path(cfg["upconverter_path"]) is None:
            where = cfg["upconverter_path"] or "dev_drivers/smisdr_common/upconverter or PATH"
            return ("{} not found ({}). Build it with 'make' in dev_drivers/smisdr_common/upconverter or set "
                    "smisdr_upconverter_path in config_wizard.yaml.".format(link.TOOL_NAME, where))
        return None
