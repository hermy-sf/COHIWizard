"""
smisdr_common/net.py
====================
Network helpers shared by smisdr_iq and smisdr_raw (blocking sockets, no Qt).
"""
import logging
import socket
import time

logger = logging.getLogger(__name__)

CONTROL_TIMEOUT_S = 0.5
DATA_CONNECT_TIMEOUT_S = 3.0
SETTLE_AFTER_CONTROL_S = 0.05
# A small kernel send buffer keeps the lag between player and DAC short (pause, stop):
# 512 KiB are ~40 ms at 12.5 MByte/s.
SEND_BUFFER_BYTES = 512 * 1024


def send_control_command(address, port, command):
    """One short connection per command (protocol of the smisdr control port).
    Returns True on success; the reason of a failure is logged."""
    try:
        with socket.create_connection((address, port), timeout=CONTROL_TIMEOUT_S) as ctrl:
            ctrl.settimeout(CONTROL_TIMEOUT_S)
            ctrl.sendall(command.encode("ascii"))
    except OSError as exc:
        logger.error("smisdr: control command %r to %s:%s failed: %s",
                     command.strip(), address, port, exc)
        return False
    logger.info("smisdr: control command sent: %s", command.strip())
    return True


def control_request(address, port, command, reply_timeout=0.3):
    """One short connection per command, and the answer is read (parlioSDR answers every
    'mode' / 'duc' command with one line; smiSDR on the Raspberry sends nothing).
    -> (reachable, reply): reachable False if the connection failed; reply is the first line
    without the line end, '' if the device sent nothing within ``reply_timeout`` seconds."""
    chunks = b""
    try:
        with socket.create_connection((address, port), timeout=CONTROL_TIMEOUT_S) as ctrl:
            ctrl.sendall(command.encode("ascii"))
            end = time.monotonic() + reply_timeout
            while b"\n" not in chunks:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                ctrl.settimeout(remaining)
                try:
                    data = ctrl.recv(256)
                except (socket.timeout, OSError):
                    break
                if not data:
                    break
                chunks += data
    except OSError as exc:
        logger.error("smisdr: control command %r to %s:%s failed: %s",
                     command.strip(), address, port, exc)
        return False, ""
    reply = chunks.decode("ascii", "replace").splitlines()[0].strip() if chunks else ""
    logger.info("smisdr: control command %r -> %r", command.strip(), reply)
    return True, reply


def open_data_socket(address, port):
    """The long data connection. Raises OSError if the port is not reachable."""
    sock = socket.create_connection((address, port), timeout=DATA_CONNECT_TIMEOUT_S)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUFFER_BYTES)
    return sock


def close_socket(sock):
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass
