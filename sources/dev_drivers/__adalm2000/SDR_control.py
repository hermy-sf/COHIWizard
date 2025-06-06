"""
Created on June 02 2025

#@author: scharfetter_admin
"""
from PyQt5.QtCore import *
#from pickle import FALSE, TRUE #intrinsic
import time
#from datetime import timedelta
from socket import socket, AF_INET, SOCK_STREAM
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from scipy import signal as sig
import subprocess

class SDR_control(QObject):
    """  Class for SDR identification and , if required, general SDR ssh connection, server start and stop,
    data stream socket control and shutdown of the SDR
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
        device_ID_dict = {"rates": {0:0, 3500000:1},
                          "rate_type": "continuous",
                          "RX": False,
                          "TX": True,
                          "device_name": "adalm_2000",
                          "device_ID": 0,
                          "max_IFREQ": 3500000,
                          "min_IFREQ": 0,
                          "resolutions": [16, 24, 32],
                          "connection_type": "USB"}
                #connection type USB_Vethernet is virtual, as the device in reality is USB but communication occurs via TCP to IP 127.0.0.1
        return(device_ID_dict)

    def set_play(self):
        self.modality = "play"
        errorstate = False
        value = ""
        # if no play mode available, return error and respective message
        return(errorstate, value)

    def set_rec(self):
        self.modality = "rec"
        errorstate = True
        value = "cannot record, no RX mode available in this device"
        # if no rec mode available, return error and respective message
        return(errorstate, value)

    def monitor(self):
        # print(f"Stemlabcontrol modality: {self.modality}")
        pass

    def config_socket(self,configparams):     ##TODO: make modality a slot rather than a method 
        '''
        initialize stream socket for communication to sdr_transceiver_wide on
        returns as errorflag 'False' if an error occurs, else it returns 'True'
        In case of unsuccessful socket setup popup error messages are sent
        param: configparams
        type: dict
        Returns:
            True if socket can be configures, False in case of error
            requires self.modality to have been set by set_play() or set_rec()
        '''
        errorstate = True
        value = "sdrserver and socket communication not available for ADALM2000"
        return(errorstate,value)


    def startssh(self,configparams):
        '''
        DUMMY, not used in ADALM2000   
        '''
        errorstate = True
        value = "sdrserver and ssh commands not available for ADALM2000"
        # start SDR server here (e.g. fl2k_tcp)
        return(errorstate, value)

    def sshsendcommandseq(self, shcomm):
        '''
        DUMMY, not used in ADALM2000
        '''
        errorstate = True
        value = "sdrserver and ssh commands not available for ADALM2000"
        return(errorstate,value)
    
    def sdrserverstart(self,configparams):
        '''
        Purpose: start server on the SDR if this applies.
        Stop potentially running server instance before so as to prevent
        undefined communication
        '''
        errorstate = False
        value = "sdrserver not available for ADALM2000"
        return(errorstate,value)


    def sdrserverstop(self):
        '''
        Purpose: stop server on the SDR.
        '''
        errorstate = False
        value = "sdrserver not available for ADALM2000"
        return(errorstate,value)

        

    def RPShutdown(self,configparams):
        '''
        not applicable for fl2k
        '''
        errorstate = False
        value = ""
        return(errorstate, value)
