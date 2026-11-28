"""Fake smiSDR / parlioSDR for the tests: a control port (one short connection per command)
and a data port (one long connection), both on localhost, recording everything they receive."""
import socket
import threading
import time


class FakeSmisdr:
    """parlio=False: plain smiSDR - the control port only takes commands and answers nothing.
    parlio=True: behaves like the control server of parlioSDR with software DUC (main.c):
    'mode' query / 'mode duc' / 'mode raw' answer with one line, a mode change ends the data
    connection, 'duc ...' settings are answered, 'rate' / 'width' are answered in duc mode."""

    def __init__(self, with_control=True, parlio=False, mode="raw", raw_switch_delay=0.0, refuse_duc=False):
        self.parlio = parlio
        self.refuse_duc = refuse_duc
        self.mode = mode
        self.raw_switch_delay = raw_switch_delay
        self.queries = []                   # pure 'mode' queries (not counted as commands)
        self.commands = []                  # control commands in order of arrival
        self.connections = []               # one bytearray per data connection
        self.connect_times = []
        self._conns = []
        self._lock = threading.Lock()
        self._stop = False
        self.data_srv = self._listen()
        self.data_port = self.data_srv.getsockname()[1]
        self._threads = [threading.Thread(target=self._data_loop, daemon=True)]
        self.control_port = None
        if with_control:
            self.ctrl_srv = self._listen()
            self.control_port = self.ctrl_srv.getsockname()[1]
            self._threads.append(threading.Thread(target=self._ctrl_loop, daemon=True))
        for t in self._threads:
            t.start()

    @staticmethod
    def _listen():
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        srv.settimeout(0.2)
        return srv

    def _ctrl_loop(self):
        while not self._stop:
            try:
                conn, _ = self.ctrl_srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(1.0)
                try:
                    data = conn.recv(256)
                except OSError:
                    data = b""
                text = data.decode("ascii", "replace")
                reply = self._handle(text)
                if reply:
                    try:
                        conn.sendall(reply.encode("ascii"))
                    except OSError:
                        pass

    def _handle(self, text):
        """record the command, -> answer line or ''"""
        stripped = text.strip().lower()
        with self._lock:
            if stripped == "mode":
                self.queries.append(text)
            else:
                self.commands.append(text)
        if not self.parlio:
            return ""
        if stripped == "mode":
            return "mode {}\n".format(self.mode)
        if stripped.startswith("mode"):
            wanted = stripped[4:].strip()
            if self.refuse_duc and wanted == "duc":
                return "mode {}\n".format(self.mode)
            if wanted in ("duc", "raw") and wanted != self.mode:
                if wanted == "raw":
                    time.sleep(self.raw_switch_delay)
                self.mode = wanted
                self.drop_connections()              # kick_data_client()
            return "mode {}\n".format(self.mode)
        if stripped.startswith("duc"):
            parts = stripped.split()
            ok = (len(parts) >= 3 and parts[1] in ("width", "offset", "gain", "cores", "maxrate")) \
                or stripped == "duc status"
            return "ok (wirkt ab der naechsten Verbindung)\n" if ok else \
                "duc status | width 8|16 | offset on|off | gain auto|<0.01..4> | cores auto|1|2 | maxrate <MHz>\n"
        if self.mode == "duc" and (stripped.startswith("rate ") or stripped.startswith("width ")):
            return "ok (duc: ignoriert)\n"
        return ""

    def _data_loop(self):
        while not self._stop:
            try:
                conn, _ = self.data_srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            buf = bytearray()
            with self._lock:
                self._conns.append(conn)
                self.connections.append(buf)
                self.connect_times.append(time.monotonic())
            threading.Thread(target=self._reader, args=(conn, buf), daemon=True).start()

    def _reader(self, conn, buf):
        conn.settimeout(0.5)
        try:
            while not self._stop:
                try:
                    chunk = conn.recv(1 << 16)
                except socket.timeout:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                with self._lock:
                    buf.extend(chunk)
        finally:
            conn.close()

    def drop_connections(self):
        """simulate a device that resets the data connection"""
        import struct
        with self._lock:
            conns = list(self._conns)
        for conn in conns:
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def data(self, index=0):
        with self._lock:
            return bytes(self.connections[index])

    def close(self):
        self._stop = True
        for srv in (self.data_srv, getattr(self, "ctrl_srv", None)):
            if srv is not None:
                try:
                    srv.close()
                except OSError:
                    pass
