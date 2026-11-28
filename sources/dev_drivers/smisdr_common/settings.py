"""
smisdr_common/settings.py
=========================
Driver settings for smisdr_iq / smisdr_raw from config_wizard.yaml (current working directory,
like the rest of COHIWizard).  All keys are optional; the defaults match the tested setup of
COHI-Player-Universal and the key names are the same as in its config_sdr.yaml:

    smisdr_data_port:      1234      # TCP data port
    smisdr_control_port:   5000      # TCP control port; 0 / off = no control commands are sent
    smisdr_iq_ref_clock:   50000000  # smisdr_iq: reference clock of the DUC gateware in Hz
    smisdr_sample_rate:    auto      # smisdr_raw: output rate 5 / 10 / 12.5 (MSps) or auto
    smisdr_format:         8         # smisdr_raw: 8, 816 (8 bit in 16 bit), 10, 12, 14
    smisdr_offset:         false     # smisdr_raw: 8 bit unsigned (offset binary)
    smisdr_upconverter_path: ""      # smisdr_raw: path of cohi_native_upconverter
    smisdr_limiter:        true      # peak limiter in front of the DAC stage (see below)
    smisdr_mode_switch:    true      # parlioSDR: switch the mode on the control port (see below)
    smisdr_iq_dsp:         auto      # smisdr_iq*: auto | soft | fpga (see below)
    smisdr_duc_commands:   []        # smisdr_iq*: extra settings for the soft DUC, e.g.
                                     #   ["duc width 8", "duc offset on", "duc gain auto"]

Peak limiter: COHIWizard's AVC regulates the gain to a volume figure that lies 10-14 dB above
digital full scale for a typical band signal, i.e. the DAC stage would clip a quarter of the
samples. The limiter scales such blocks down instead (and the log shows the level); set it to
false only for measurements.

Mode switching (parlioSDR, control port): smisdr_raw* sends "mode raw" if the device is in the
software DUC mode. smisdr_iq* with smisdr_iq_dsp auto / soft sends "mode duc" (the ESP32 replaces
the FPGA) and skips width / rate, which the soft DUC ignores; with fpga it keeps the device in
"mode raw", where the in-band signalling is passed on to an FPGA. A device that does not answer
the query "mode" (smiSDR on the Raspberry Pi) is left alone: auto and fpga behave as before, soft
reports an error.

The host address is not a setting: it is the IP address field of the Player tab.
Invalid values do not abort anything silently: ``load_settings`` raises SettingsError with a
message naming the key, which the drivers pass on to the usual error box.
"""
import os

from . import protocol

CONFIG_FILE = "config_wizard.yaml"

_cache = {}     # path -> (mtime, settings)


class SettingsError(ValueError):
    pass


def _defaults():
    return {
        "data_port": 1234,
        "control_port": 5000,
        "ref_clock": protocol.DEFAULT_REF_CLOCK_HZ,
        "sample_rate": protocol.RATE_AUTO,
        "format": protocol.FORMAT_8,
        "offset": False,
        "upconverter_path": "",
        "limiter": True,
        "mode_switch": True,
        "iq_dsp": "auto",
        "duc_commands": [],
    }


def _read_yaml(path):
    try:
        import yaml
    except ImportError as exc:                          # PyYAML is a COHIWizard requirement
        raise SettingsError("PyYAML is not installed: {}".format(exc)) from exc
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, yaml.YAMLError) as exc:
        raise SettingsError("cannot read {}: {}".format(path, exc)) from exc
    return data if isinstance(data, dict) else {}


def parse_settings(raw):
    """dict from config_wizard.yaml -> validated settings dict (see module docstring)."""
    out = _defaults()

    try:
        out["data_port"] = int(raw.get("smisdr_data_port", out["data_port"]))
        if not 1 <= out["data_port"] <= 65535:
            raise ValueError("out of range 1..65535")
    except (TypeError, ValueError) as exc:
        raise SettingsError("smisdr_data_port in {}: {}".format(CONFIG_FILE, exc)) from exc

    try:
        out["control_port"] = protocol.parse_control_port(raw.get("smisdr_control_port", 5000))
    except (TypeError, ValueError) as exc:
        raise SettingsError("smisdr_control_port in {}: {}".format(CONFIG_FILE, exc)) from exc

    try:
        out["ref_clock"] = float(raw.get("smisdr_iq_ref_clock", out["ref_clock"]))
        if out["ref_clock"] <= 0:
            raise ValueError("must be > 0")
    except (TypeError, ValueError) as exc:
        raise SettingsError("smisdr_iq_ref_clock in {}: {}".format(CONFIG_FILE, exc)) from exc

    rate = protocol.parse_rate_setting(raw.get("smisdr_sample_rate", protocol.RATE_AUTO))
    if rate is None:
        raise SettingsError("smisdr_sample_rate in {}: value {!r} is not valid "
                            "(5, 10, 12.5, auto)".format(CONFIG_FILE, raw.get("smisdr_sample_rate")))
    out["sample_rate"] = rate

    fmt = raw.get("smisdr_format", protocol.FORMAT_8)
    try:
        fmt = int(fmt)
    except (TypeError, ValueError):
        fmt = None
    if fmt not in protocol.FORMATS:
        raise SettingsError("smisdr_format in {}: value {!r} is not valid {}".format(
            CONFIG_FILE, raw.get("smisdr_format"), protocol.FORMATS))
    out["format"] = fmt

    out["offset"] = bool(raw.get("smisdr_offset", False)) and fmt == protocol.FORMAT_8
    out["upconverter_path"] = str(raw.get("smisdr_upconverter_path") or "").strip()

    limiter = raw.get("smisdr_limiter", True)
    if not isinstance(limiter, bool):
        raise SettingsError("smisdr_limiter in {}: value {!r} is not valid (true / false)"
                            .format(CONFIG_FILE, limiter))
    out["limiter"] = limiter

    switch = raw.get("smisdr_mode_switch", True)
    if not isinstance(switch, bool):
        raise SettingsError("smisdr_mode_switch in {}: value {!r} is not valid (true / false)"
                            .format(CONFIG_FILE, switch))
    out["mode_switch"] = switch

    dsp = str(raw.get("smisdr_iq_dsp", "auto")).strip().lower()
    if dsp not in ("auto", "soft", "fpga"):
        raise SettingsError("smisdr_iq_dsp in {}: value {!r} is not valid (auto, soft, fpga)"
                            .format(CONFIG_FILE, raw.get("smisdr_iq_dsp")))
    out["iq_dsp"] = dsp

    commands = raw.get("smisdr_duc_commands") or []
    if isinstance(commands, str):
        commands = [commands]
    if not isinstance(commands, list) or not all(
            isinstance(c, str) and c.strip().lower().startswith("duc ") for c in commands):
        raise SettingsError("smisdr_duc_commands in {}: must be a list of commands that start with "
                            "'duc ', e.g. [\"duc width 8\", \"duc offset on\"]".format(CONFIG_FILE))
    out["duc_commands"] = [c.strip() for c in commands]

    return out


def raw_problem(cfg):
    """Rules that only apply to smisdr_raw (smisdr_iq does not use smisdr_sample_rate):
    -> message or None"""
    if cfg["sample_rate"] == protocol.RATE_AUTO and cfg["control_port"] is None:
        return ("smisdr_sample_rate: 'auto' needs the control port, because the rate has to be "
                "sent to the hardware - set smisdr_sample_rate to 5, 10 or 12.5 or switch the "
                "control port on")
    return None


def load_settings(path=None):
    """Settings from ``path`` (default: config_wizard.yaml in the working directory); re-read
    only if the file changed (identify() is called often)."""
    path = path or CONFIG_FILE
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    cached = _cache.get(path)
    if cached is not None and cached[0] == mtime:
        return dict(cached[1])
    settings = parse_settings(_read_yaml(path))
    _cache[path] = (mtime, settings)
    return dict(settings)
