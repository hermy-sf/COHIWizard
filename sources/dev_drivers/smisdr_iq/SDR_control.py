"""
smisdr_iq/SDR_control.py
========================
Adapter for smiSDR / parlioSDR with the DUC gateware (FPGA): baseband I/Q with in-band
signalling (NCO shift + input rate); the up-conversion to the RF carrier is done by the FPGA.
Playback only.  See smisdr_common/protocol.py for the wire protocol.
"""
from dev_drivers.smisdr_common import protocol, settings
from dev_drivers.smisdr_common.control_base import SmisdrControlBase


class SDR_control(SmisdrControlBase):

    def identify(self):
        try:
            ref_clock = settings.load_settings()["ref_clock"]
        except settings.SettingsError:
            ref_clock = protocol.DEFAULT_REF_CLOCK_HZ       # the error is reported by config_socket
        return {
            "rates":           {rate: ix for ix, rate in enumerate(protocol.SUPPORTED_IQ_RATES_HZ)},
            "rate_type":       "discrete",
            "RX":              False,
            "TX":              True,
            "device_name":     "smisdr_iq",
            "device_ID":       2,
            "max_IFREQ":       int(protocol.MAX_EDGE_OF_NYQUIST * ref_clock / 2.0),
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "ethernet",                  # enables the IP address field
            "server_boot":     False,                       # always on: no startup wait
            "volume_mode":     "mean",
            "watchdog":        False,
        }
