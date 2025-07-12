"""
Created on Feb 24 2024

#@author: scharfetter_admin
"""
from PyQt5.QtCore import *
#from pickle import FALSE, TRUE #intrinsic
import time
#from datetime import timedelta
from socket import socket, AF_INET, SOCK_STREAM
from struct import pack, unpack
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from scipy import signal as sig
from auxiliaries import auxiliaries as auxi
from auxiliaries import TextInputDialog

import paramiko

# class TextInputDialog(QDialog):
#     def __init__(self, parent=None, *args, **kwargs):
#         super(TextInputDialog, self).__init__(parent)

#         self.setWindowTitle("Input dialogue")
#         if len(args) > 0:
#             self.inputfields = args[0]

#         layout = QVBoxLayout()

#         # Eingabefelder
#         for key, value in self.inputfields.items():
#             setattr(self, f'line_edit_{key}', QLineEdit(self))
#             getattr(self, f'line_edit_{key}').setText(str(value))
#             layout.addWidget(QLabel(f"{key}:"))
#             layout.addWidget(getattr(self, f'line_edit_{key}'))
#         # self.line_edit1 = QLineEdit(self)
#         # self.line_edit2 = QLineEdit(self)

#         # Buttons
#         self.ok_button = QPushButton("OK", self)
#         self.cancel_button = QPushButton("Cancel", self)

#         # Layouts
# #        layout.addWidget(QLabel("carier freqency:"))
# #        layout.addWidget(self.line_edit1)

#  #       layout.addWidget(QLabel("Eingabe 2:"))
#  #       layout.addWidget(self.line_edit2)

#         button_layout = QHBoxLayout()
#         button_layout.addWidget(self.ok_button)
#         button_layout.addWidget(self.cancel_button)

#         layout.addLayout(button_layout)
#         self.setLayout(layout)

#         # Signals
#         self.ok_button.clicked.connect(self.accept)
#         self.cancel_button.clicked.connect(self.reject)

class SDR_control(QObject):
    """     Class for STEMLAB ssh connection, server start and stop,
    data stream socket control and shutdown of the STEMLAB LINUX
    some methods emit a pyqtSignal(str) named SigMessage(messagestring) with argument messagestring 
    two settings are called via methods, i.e. set_play() and set_rec() for selecting play or rec
    :param : no regular parameters; communication occurs via
        __slots__: Dictionary with entries:
        __slots__[0]: irate, Type: int
        __slots__[1]: ifreq = LO, Type integer
        __slots__[2]: icorr Type: integer
        __slots__[3]: rates Type: list
    :raises [ErrorType]: none
    :return: none
    :rtype: none
    """
    __slots__ = ["irate", "ifreq", "icorr", "rates", "HostAddress"]

    SigError = pyqtSignal(str)
    SigMessage = pyqtSignal(str)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # self.HostAddress = self.get_HostAddress()
        # print(f"init stemlabcontrol Hostaddress: {self.HostAddress}")

    def identify(self):
        """return important device characteristics:
        (1) allowed samplingrates as a dict: if discrete: give values, if continuous: give lower and upper bound
        (2) rate_type: discrete or continuous
        (3) RX, TX, or RX & TX
        (3) device name
        (4) device ID
        (5) max_IFREQ
        (6) min IFREQ
        (7) possible resolutions (bits): list
        (8) connection type: ethernet, USB, USB_Vethernet
        
        : param: none

        : return: device_ID_dict
        : rtype: dict
        """
        device_ID_dict = {"rates": {20000:0, 50000:1, 100000:2, 250000:3, 
                      500000:4, 1250000:5, 2500000:6},
                          "rate_type": "discrete",
                          "RX": False, #TODO: set true after tests
                          "TX": True, #TODO: set true after tests
                          "device_name": "STEMlab 125-14 stream",
                          "device_ID": 0,
                          "max_IFREQ": 62500000,
                          "min_IFREQ": 0,
                          "resolutions": [16, 24, 32],
                          "connection_type": "ethernet"}
        return(device_ID_dict)

    def showDialog(self, Mainwindowreference=None, inputfields=None):
        """Shows a dialog to get user input for a number of editable input fields.
        The input fields are defined in the inputfields dictionary.
        If the dialog is accepted, the values are returned as a dictionary.
        :param Mainwindowreference: Reference to the main window for dialog parent
        :type Mainwindowreference: QMainWindow
        :param inputfields: Dictionary of input fields with their current values
        :type inputfields: dict
        """
        errorstate = False
        value = []
        dialog = TextInputDialog(Mainwindowreference, inputfields)
        if dialog.exec_() == QDialog.Accepted:
            # Get the input values from the dialog
            value = dialog.getInputs()
        else:
            errorstate = True

        return errorstate, value     
    
    def build_dialogue(self,configparams):
        print("build dialogue window for streaming STEMLAB control")
        target_lo_shift = 200000
        inputfields = {
            "target_lo_shift": target_lo_shift
        }
        QMAINWINDOWparent = configparams["QMAINWINDOWparent"]
        errorstate, inputvalues = self.showDialog(QMAINWINDOWparent, inputfields)
        if not errorstate:
            try:
                target_lo_shift = int(inputvalues["target_lo_shift"])
            except ValueError:
                print(f"Invalid input for target LO shift: {inputvalues['target_lo_shift']}")
                self.SigError.emit(f"Invalid input for target LO shift: {inputvalues['target_lo_shift']}")
                return
        # print(f"target_lo_shift from inoutdialog: {target_lo_shift}, mutex unlock")
        # self.mutex.unlock()
        time.sleep(0.5)

    def set_play(self):
        self.modality = "play"
        errorstate = False
        value = ""
        return(errorstate, value)  

    def set_rec(self):
        self.modality = "rec"
        errorstate = False
        value = ""
        return(errorstate, value)   

    def monitor(self):
        # print(f"Stemlabcontrol modality: {self.modality}")
        pass

    def config_socket(self,configparams):     ##TODO: make modality a slot rather than a method 
        '''
        initialize stream socket for communication to sdr_transceiver_wide on
        the STEMLAB
        returns as errorflag 'False' if an error occurs, else it returns 'True'
        In case of unsuccessful socket setup popup error messages are sent
        param: configparams
        type: dict
        Returns:
            True if socket can be configures, False in case of error
            requires self.modality to have been set by set_play() or set_rec()
        '''
        print(f'configparams ifreq: {configparams["ifreq"]} , HostAddress: {configparams["HostAddress"]}')
        print(f'configparams irate: {configparams["irate"]} , icorr: {configparams["icorr"]}')
        print(f'configparams rates: {configparams["rates"]} , LO_offset: {configparams["LO_offset"]}')
        #system_state = sys_state.get_status() #TODO replace             
        ifreq = configparams["ifreq"]
        irate = configparams["irate"]
        rates = configparams["rates"]
        icorr = configparams["icorr"]
        LO_offset = configparams["LO_offset"]

        self.build_dialogue(configparams)

        #LO_offset = system_state["LO_offset"] ##replace later

        self.ctrl_sock = socket(AF_INET, SOCK_STREAM)
        self.ctrl_sock.settimeout(5)
        try:
            self.ctrl_sock.connect((configparams["HostAddress"], 1001))
        except:
            self.SigError.emit("Cannot establish socket connection for streaming to the STEMLAB")
            return False
            #self.ctrl_sock.settimeout(None)
        self.data_sock = socket(AF_INET, SOCK_STREAM)
        self.data_sock.settimeout(5)
        try:
            self.data_sock.connect((configparams["HostAddress"], 1001))
        except:  #TODO: replace errormessages by parameterized signals connected to errorbox-calls, par = errormessage
            self.SigError.emit("Cannot establish socket connection for streaming to the STEMLAB")
            return False
        #self.data_sock.settimeout(None) ######FFFFFFFFFFFFF
        if (self.modality != "play") and (self.modality != "rec"):
            # TODO remove after tests 13-12-2023: auxi.standard_errorbox("Error , self.modality must be rec or play")
            self.SigError.emit("Error , self.modality must be rec or play")
            return False

        # send control parameters to ctrl_sock:
        if self.modality == "play":
            self.ctrl_sock.send(pack('<I', 2))
            self.ctrl_sock.send(pack('<I', 0 << 28
                                     | int((1.0 + 1e-6 * icorr)
                                           * ifreq + 0*LO_offset)))     # TODO: replace win references with local vars and **kwargs from self.sdrparameters

            # TODO: check replacement 13-12-2023: print(f'effective LO: {int((1.0 + 1e-6 * win.icorr)* win.ifreq + system_state["LO_offset"])}')
            print(f'effective LO: {int((1.0 + 1e-6 * icorr)* ifreq + 0*LO_offset)}')
            self.ctrl_sock.send(pack('<I', 1 << 28 | rates[irate]))
            self.data_sock.send(pack('<I', 3))
        else:
            self.ctrl_sock.send(pack('<I', 0))
            # self.ctrl_sock.send(pack('<I', 0 << 28
            #                          | int((1.0 + 1e-6 * win.icorr)
            #                                * win.ifreq)))
            # self.ctrl_sock.send(pack('<I', 0 << 28
            #                          | int((1.0 + 1e-6 * [system_state["icorr"]])
            #                                * [system_state["ifreq"]])))
            self.ctrl_sock.send(pack('<I', 0 << 28
                                     | int((1.0 + 1e-6 * icorr)
                                           * ifreq)))
            #self.ctrl_sock.send(pack('<I', 1 << 28 | win.rates[win.irate])) FFFFFFFFFFFFFFFFFFFFFFFFFFFF
            
            #TODO: ckech change 13-12-2023
            #self.ctrl_sock.send(pack('<I', 1 << 28 | win.rates[system_state["irate"]])) TODO: last working version
            #self.ctrl_sock.send(pack('<I', 1 << 28 | system_state["rates"][system_state["irate"]]))
            self.ctrl_sock.send(pack('<I', 1 << 28 | rates[irate]))
            self.data_sock.send(pack('<I', 1))

        # TODO in further versions: diagnostic output to status message window: send signal
        # ("socket started")
        self.SigMessage.emit("socket started")
        return True

    def startssh(self,configparams):
        '''
        login to Host and start ssh session with STEMLAB
        Returns False if a connection error occurs, returns True if
        successful
        '''
        print(f'configparams ifreq: {configparams["ifreq"]} , HostAddress: {configparams["HostAddress"]}')

        port = 22
        username = "root"
        password = "root"
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.SigMessage.emit("trying to start ssh connection with STEMLAB")
        try:
            self.ssh.connect(configparams["HostAddress"], port, username, password)
            self.SigMessage.emit("ssh connection successful")
            return True
        except:
            self.SigError.emit("Cannot connect to Host " + configparams["HostAddress"])
            return False

    def sshsendcommandseq(self, shcomm):
        '''
        send ssh command string sequence via command string list shcomm
        '''
        count = 0
        while (count < len(shcomm)):  #TODO REM FIN check list, only diagnostic    TODO: rewrite loop more pythonian
            try:
                self.ssh.exec_command(shcomm[count])
            except:
                print("stemlab control sshsendcommandseq, command cannot be sent")
            count = count + 1
            time.sleep(0.1)
        self.SigMessage.emit("ssh command sent")

    def sdrserverstart(self,configparams):
        '''
        Purpose: start server sdr-transceiver-wide on the STEMLAB.
        Stop potentially running server instance before so as to prevent
        undefined communication
        '''
        errorstate = False
        value = ["",None]
        # TODO: future versions could send diagnostic output to status message indicator
        shcomm = []
        shcomm.append('/bin/bash /sdrstop.sh &')
        shcomm.append('/bin/bash /sdrstart.sh &')
        # connect to remote server via ssh
        if self.startssh(configparams) is False:
            value[0] = "SDR Server could not be started, please check if STEMLAB is connected correctly."
            return(errorstate, value)
        self.sdrserverstop()  #TODO ?is this necessary ?
        time.sleep(0.2)     # wait state for letting the server react before it is being accessed; issue after tetst unter LINUX Debian 12 
        self.sshsendcommandseq(shcomm)
        time.sleep(0.2)     # wait state for letting the server react before it is being accessed; issue after tetst unter LINUX Debian 12
        self.SigMessage.emit("transmit ssh command for ssh start")
        return(errorstate, value)

    def sdrserverstop(self):
        '''
        Purpose: stop server sdr-transceiver-wide on the STEMLAB.
        '''
        shcomm = []
        shcomm.append('/bin/bash /sdrstop.sh &')
        self.sshsendcommandseq(shcomm)
        

    def RPShutdown(self,configparams):
        '''
        Purpose: Shutdown the LINUX running on the STEMLAB
        Sequence:   (1) stop server sdr-transceiver-wide on the STEMLAB.
                    (2) send 'halt' command via ssh, track result via stdout
                    (3) communicate steps and progress via popup messages
        '''
        if self.startssh(configparams) is False:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("ignoring command")
            msg.setInformativeText(
                              "No Connection to STEMLAB or STEMLAB OS is down")
            msg.setWindowTitle("MISSION IMPOSSIBLE")
            msg.exec_()
            return
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("SHUTDOWN")
        msg.setInformativeText(
                              "Shutting down the STEMLAB !"
                              "Please wait until heartbeat stops flashing")
        msg.setWindowTitle("SHUTDOWN")
        msg.exec_()
        self.sdrserverstop()
        #stdin, stdout, stderr = self.ssh.exec_command("/sbin/halt >&1 2>&1")
        stdin, stdout, stderr = self.ssh.exec_command("/sbin/poweroff >&1 2>&1")
        #TODO check schnellere Variante mit poweroff statt halt
        chout = stdout.channel
        textout = ""
        while True:
            bsout = chout.recv(1)
            textout = textout + bsout.decode("utf-8")
            if not bsout:
                break

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("POWER DOWN")
        msg.setInformativeText("It is now safe to power down the STEMLAB")
        msg.setWindowTitle("SHUTDOWN")
        msg.exec_()
