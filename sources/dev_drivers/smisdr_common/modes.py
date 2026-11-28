"""
smisdr_common/modes.py
======================
Operating mode of parlioSDR on the control port (port 5000), see its README:

    "mode"       -> "mode raw" | "mode duc"         query
    "mode duc"   -> "mode duc"                      ESP32 mixes up in software (replaces the FPGA);
                                                    expects the I/Q stream with in-band commands
    "mode raw"   -> "mode raw"                      passes the stream 1:1 to the DAC (finished RF
                                                    samples, or I/Q with in-band signalling for an
                                                    FPGA behind the ESP32); may take up to 3 s when
                                                    a software DUC session has to end first
    "duc width 8|16", "duc offset on|off", "duc gain auto|<x>", ...   settings of the soft DUC

The mode switch ends a running data connection and is a no-op if the mode is already set, so
it is sent before the data connection is opened.  A plain smiSDR (Raspberry Pi) does not know
these commands and does not answer: the query then returns ``None`` and nothing else is sent.
"""
import logging
import re

from dev_drivers.smisdr_common import net

logger = logging.getLogger("smisdr")

QUERY_TIMEOUT_S = 0.3         # a device that knows 'mode' answers at once
SWITCH_TIMEOUT_S = 6.0        # 'mode raw' waits up to 3 s for the end of a DUC session
EXTRA_TIMEOUT_S = 1.0

_REPLY = re.compile(r"^mode\s+(raw|duc)\b", re.IGNORECASE)


class ModeError(Exception):
    """message meant for the user"""


def query_mode(host, port):
    """-> 'raw' | 'duc' | None (the device does not know the command, e.g. smiSDR); raises
    ModeError if the control port cannot be reached."""
    reachable, reply = net.control_request(host, port, "mode\n", QUERY_TIMEOUT_S)
    if not reachable:
        raise ModeError("the control port {}:{} is not reachable".format(host, port))
    match = _REPLY.match(reply)
    return match.group(1).lower() if match else None


def switch_mode(host, port, mode):
    """'raw' | 'duc'; waits for the answer, which comes after the switch has been completed."""
    reachable, reply = net.control_request(host, port, "mode {}\n".format(mode), SWITCH_TIMEOUT_S)
    if not reachable:
        raise ModeError("the control port {}:{} is not reachable".format(host, port))
    match = _REPLY.match(reply)
    if not match or match.group(1).lower() != mode:
        raise ModeError("the device did not switch to mode {} (answer: {!r})".format(mode, reply))
    logger.info("smisdr: device is in mode %s now", mode)


def send_extra(host, port, command):
    """one 'duc ...' setting; a refusal is logged and returned as a message (no exception: the
    device keeps its previous setting and plays on)"""
    reachable, reply = net.control_request(host, port, command.strip() + "\n", EXTRA_TIMEOUT_S)
    if not reachable:
        raise ModeError("the control port {}:{} is not reachable".format(host, port))
    if reply.lower().startswith(("fehler", "error", "duc status |")):
        logger.warning("smisdr: %r was refused: %s", command, reply)
        return "{!r} was refused by the device: {}".format(command, reply)
    return None
