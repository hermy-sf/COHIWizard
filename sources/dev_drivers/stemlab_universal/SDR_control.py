"""
stemlab_universal/SDR_control.py
Adapter for STEMlab 125-14 with support for IQ-only, IQ+Audio, and Audio-only modes.
Extends stemlab_125_14/SDR_control.py with the new 4-layer adapter interface
(setup / teardown / is_ready) alongside legacy methods.
"""

from PyQt5.QtCore import *
import time
from socket import socket, AF_INET, SOCK_STREAM
from struct import pack, unpack
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from scipy import signal as sig
from auxiliaries import auxiliaries as auxi
import paramiko


class SDR_control(QObject):
    """Adapter for STEMlab 125-14 (universal: IQ-only, IQ+Audio, Audio-only).

    New 4-layer interface: setup() / teardown() / is_ready()
    Legacy interface retained: sdrserverstart / config_socket / sdrserverstop
    """

    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError   = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------ identify
    def identify(self):
        device_ID_dict = {
            "rates": {
                20000: 0, 50000: 1, 100000: 2, 250000: 3,
                500000: 4, 1250000: 5, 2500000: 6,
            },
            "rate_type":       "discrete",
            "RX":              True,
            "TX":              True,
            "device_name":     "stemlab_universal",
            "device_ID":       0,
            "max_IFREQ":       62500000,
            "min_IFREQ":       0,
            "resolutions":     [16, 24, 32],
            "connection_type": "ethernet",
            "volume_mode":     "mean",
            "modulator":       "P",   # show both IQ-file and audio-playlist GUI elements
            "watchdog":        False,
        }
        return device_ID_dict

    # ---------------------------------------------------------- new adapter API
    def setup(self, configparams) -> bool:
        """New unified adapter interface. Wraps sdrserverstart + boot-wait + config_socket."""
        err, _ = self.sdrserverstart(configparams)
        if err:
            return False
        time.sleep(5)   # STEMLAB server boot time
        result = self.config_socket(configparams)
        # config_socket returns True on success, False on failure
        return bool(result)

    def teardown(self) -> None:
        """New unified adapter interface. Stops the STEMLAB server."""
        self.sdrserverstop()

    def is_ready(self) -> bool:
        """Check if STEMLAB TCP socket is open."""
        try:
            return hasattr(self, "data_sock") and self.data_sock is not None
        except Exception:
            return False

    # --------------------------------------------------------- legacy interface
    def set_play(self):
        self.modality = "play"
        return False, ""

    def set_rec(self):
        self.modality = "rec"
        return False, ""

    def monitor(self):
        pass

    def config_socket(self, configparams):
        print(f'configparams ifreq: {configparams["ifreq"]} , HostAddress: {configparams["HostAddress"]}')
        print(f'configparams irate: {configparams["irate"]} , icorr: {configparams["icorr"]}')
        print(f'configparams rates: {configparams["rates"]} , LO_offset: {configparams["LO_offset"]}')

        ifreq      = configparams["ifreq"]
        irate      = configparams["irate"]
        rates      = configparams["rates"]
        icorr      = configparams["icorr"]
        LO_offset  = configparams["LO_offset"]

        self.ctrl_sock = socket(AF_INET, SOCK_STREAM)
        self.ctrl_sock.settimeout(5)
        try:
            self.ctrl_sock.connect((configparams["HostAddress"], 1001))
        except Exception:
            self.SigError.emit("Cannot establish control socket connection to STEMLAB")
            return False

        self.data_sock = socket(AF_INET, SOCK_STREAM)
        self.data_sock.settimeout(5)
        try:
            self.data_sock.connect((configparams["HostAddress"], 1001))
        except Exception:
            self.SigError.emit("Cannot establish data socket connection to STEMLAB")
            return False

        if self.modality not in ("play", "rec"):
            self.SigError.emit("Error: self.modality must be 'rec' or 'play'")
            return False

        if self.modality == "play":
            self.ctrl_sock.send(pack('<I', 2))
            self.ctrl_sock.send(pack('<I', 0 << 28 | int((1.0 + 1e-6 * icorr) * ifreq + 0 * LO_offset)))
            print(f'effective LO: {int((1.0 + 1e-6 * icorr) * ifreq + 0 * LO_offset)}')
            self.ctrl_sock.send(pack('<I', 1 << 28 | rates[irate]))
            self.data_sock.send(pack('<I', 3))
        else:
            self.ctrl_sock.send(pack('<I', 0))
            self.ctrl_sock.send(pack('<I', 0 << 28 | int((1.0 + 1e-6 * icorr) * ifreq)))
            self.ctrl_sock.send(pack('<I', 1 << 28 | rates[irate]))
            self.data_sock.send(pack('<I', 1))

        self.SigMessage.emit("socket started")
        return True

    def startssh(self, configparams):
        print(f'configparams ifreq: {configparams["ifreq"]} , HostAddress: {configparams["HostAddress"]}')
        port     = 22
        username = "root"
        password = "root"
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.SigMessage.emit("trying to start ssh connection with STEMLAB")
        try:
            self.ssh.connect(configparams["HostAddress"], port, username, password)
            self.SigMessage.emit("ssh connection successful")
            return True
        except Exception:
            self.SigError.emit("Cannot connect to Host " + configparams["HostAddress"])
            return False

    def sshsendcommandseq(self, shcomm):
        count = 0
        while count < len(shcomm):
            try:
                self.ssh.exec_command(shcomm[count])
            except Exception:
                print("stemlab_universal sshsendcommandseq: command cannot be sent")
            count += 1
            time.sleep(0.1)
        self.SigMessage.emit("ssh command sent")

    def sdrserverstart(self, configparams):
        errorstate = False
        value      = ["", None]
        shcomm     = ["/bin/bash /sdrstop.sh &", "/bin/bash /sdrstart.sh &"]
        if self.startssh(configparams) is False:
            value[0] = "SDR Server could not be started – check STEMLAB connection."
            return errorstate, value
        self.sdrserverstop()
        time.sleep(0.2)
        self.sshsendcommandseq(shcomm)
        time.sleep(0.2)
        self.SigMessage.emit("transmit ssh command for sdr start")
        return errorstate, value

    def sdrserverstop(self):
        shcomm = ["/bin/bash /sdrstop.sh &"]
        self.sshsendcommandseq(shcomm)

    def RPShutdown(self, configparams):
        if self.startssh(configparams) is False:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("ignoring command")
            msg.setInformativeText("No Connection to STEMLAB or STEMLAB OS is down")
            msg.setWindowTitle("MISSION IMPOSSIBLE")
            msg.exec_()
            return
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("SHUTDOWN")
        msg.setInformativeText("Shutting down the STEMLAB! Please wait until heartbeat stops flashing")
        msg.setWindowTitle("SHUTDOWN")
        msg.exec_()
        self.sdrserverstop()
        stdin, stdout, stderr = self.ssh.exec_command("/sbin/poweroff >&1 2>&1")
        chout   = stdout.channel
        textout = ""
        while True:
            bsout   = chout.recv(1)
            textout += bsout.decode("utf-8")
            if not bsout:
                break
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("POWER DOWN")
        msg.setInformativeText("It is now safe to power down the STEMLAB")
        msg.setWindowTitle("SHUTDOWN")
        msg.exec_()
