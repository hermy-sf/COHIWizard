"""
Created on Feb 24 2024

#@author: scharfetter_admin
"""
#from pickle import FALSE, TRUE #intrinsic
import time
#from datetime import timedelta
#from socket import socket, AF_INET, SOCK_STREAM
from struct import unpack
import numpy as np
# import os
# import pytz
# from pathlib import Path
# from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
# from PyQt5 import QtGui
# #from scipy import signal as sig
# import yaml
# import shutil
# import pyqtgraph as pg
# import logging
# import subprocess
# from auxiliaries import auxiliaries as auxi
# from auxiliaries import WAVheader_tools
# from datetime import datetime
# import datetime as ndatetime
# from player import stemlab_control

class playrec_worker(QObject):
    """ worker class for data streaming thread from PC to STEMLAB
    object for playback and recording thread
    :param : no regular parameters; as this is a thread worker communication occurs via
        __slots__: Dictionary with entries:
        __slots__[0]: filename = complete file path pathname/filename Type: str
        __slots__[1]: timescaler = bytes per second  TODO: rescaling to samples per second would probably be more logical, Type int
        __slots__[2]: TEST = flag for test mode Type: bool
        __slots__[3]: pause = flag if stream should be paused (True) or not (False)
        __slots__[4]: filehandle
        __slots__[5]: data segment to be returned every second
        __slots__[6]: gain, scaling factor for playback
        __slots__[7]: formatlist: [formattag blockalign bitpsample]
    :type : dictionary
    '''
    :raises [ErrorType]: none
    '''
        :return: none
        :rtype: none
    """

    __slots__ = ["filename", "timescaler", "TEST", "pause", "fileHandle", "data", "gain" ,"formattag" ,"datablocksize","fileclose","configparameters"]

    SigFinished = pyqtSignal()
    SigIncrementCurTime = pyqtSignal()
    SigBufferOverflow = pyqtSignal()
    SigError = pyqtSignal(str)
    SigNextfile = pyqtSignal(str)

    def __init__(self, stemlabcontrolinst,*args,**kwargs):

        super().__init__(*args, **kwargs)
        self.stopix = False
        #self.pausestate = False
        self.JUNKSIZE = 2048*4
        self.DATABLOCKSIZE = 1024*4
        self.mutex = QMutex()
        self.stemlabcontrol = stemlabcontrolinst

    def set_filename(self,_value):
        self.__slots__[0] = _value
    def get_filename(self):
        return(self.__slots__[0])
    def set_timescaler(self,_value):
        self.__slots__[1] = _value
    def get_timescaler(self):
        return(self.__slots__[1])
    def set_TEST(self,_value):
        self.__slots__[2] = _value
    def get_TEST(self):
        return(self.__slots__[2])
    def set_pause(self,_value):
        self.__slots__[3] = _value
    def get_pause(self):
        return(self.__slots__[3])
    def get_fileHandle(self):
        return(self.__slots__[4])
    def set_fileHandle(self,_value):
        self.__slots__[4] = _value
    def get_data(self):
        return(self.__slots__[5])
    def set_data(self,_value):
        self.__slots__[5] = _value
    def get_gain(self):
        return(self.__slots__[6])
    def set_gain(self,_value):
        self.__slots__[6] = _value
    def get_formattag(self):
        return(self.__slots__[7])
    def set_formattag(self,_value):
        self.__slots__[7] = _value
    def get_datablocksize(self):
        return(self.__slots__[8])
    def set_datablocksize(self,_value):
        self.__slots__[8] = _value
    def get_fileclose(self):
        return(self.__slots__[9])
    def set_fileclose(self,_value):
        self.__slots__[9] = _value
    def get_configparameters(self):
        return(self.__slots__[10])
    def set_configparameters(self,_value):
        self.__slots__[10] = _value

    def play_loop_filelist(self):
        """
        worker loop for sending data to STEMLAB server
        data format i16; 2xi16 complex; FormatTag 1
        sends signals:     
            SigFinished = pyqtSignal()
            SigIncrementCurTime = pyqtSignal()
            SigBufferOverflow = pyqtSignal()

        :param : no regular parameters; as this is a thread worker communication occurs via
        class slots __slots__[i], i = 0...8
        __slots__[0]: filename = complete file path pathname/filename Type: list
        __slots__[1]: timescaler = bytes per second  TODO: rescaling to samples per second would probably be more logical, Type int
        __slots__[2]: TEST = flag for test mode Type: bool
        __slots__[3]: pause : if True then do not send data; Boolean
        __slots__[4]: filehandle: returns current filehandle to main thread methods on request 
        __slots__[5]: data segment to be returned every second
        __slots__[6]: gain, scaling factor for playback
        __slots__[7]: formatlist: [formattag blockalign bitpsample]
        __slots__[8]: datablocksize
        __slots__[9]: file_close
        __slots__[10]: sampling_parameters
        """
        #print("reached playloopthread")
        filenames = self.get_filename()
        timescaler = self.get_timescaler()
        TEST = self.get_TEST()
        gain = self.get_gain()
        #TODO: self.fmtscl = self.__slots__[7] #scaler for data format      ? not used so far  
        self.stopix = False
        self.set_fileclose(False)
        for ix,filename in enumerate(filenames):
            fileHandle = open(filename, 'rb')
            self.SigNextfile.emit(filename)
            #print(f"filehandle for set_4: {fileHandle} of file {filename} ")
            self.set_fileHandle(fileHandle)
            format = self.get_formattag()
            self.set_datablocksize(self.DATABLOCKSIZE)
            #print(f"Filehandle :{fileHandle}")
            fileHandle.seek(216, 1)
            if format[2] == 16:
                data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
            else:
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32) #TODO: check if true for 32-bit wavs wie Gianni's
            #print(f"playloop: BitspSample: {format[2]}; wFormatTag: {format[0]}; Align: {format[1]}")
            if format[0] == 1:
                normfactor = int(2**int(format[2]-1))-1
            else:
                normfactor = 1
            if format[2] == 16 or format[2] == 32:
                size = fileHandle.readinto(data)
            elif format[2] == 24:
                data = self.read24(format,data,fileHandle)
                size = len(data)
            self.set_data(data)
            junkspersecond = timescaler / self.JUNKSIZE
            count = 0
            # print(f"Junkspersec:{junkspersecond}")
            while size > 0 and not self.stopix:
                if not TEST:
                    if not self.get_pause():
                        try:
                            self.stemlabcontrol.data_sock.send(
                                                    gain*data[0:size].astype(np.float32)
                                                    /normfactor)  # send next DATABLOCKSIZE samples
                        except BlockingIOError:
                            print("Blocking data socket error in playloop worker")
                            time.sleep(0.1)
                            self.SigError.emit("Blocking data socket error in playloop worker")
                            self.SigFinished.emit()
                            time.sleep(0.1)
                            return
                        except ConnectionResetError:
                            print("Diagnostic Message: Connection data socket error in playloop worker")
                            time.sleep(0.1)
                            self.SigError.emit("Diagnostic Message: Connection data socket error in playloop worker")
                            self.SigFinished.emit()
                            time.sleep(0.1)
                            return
                        except Exception as e:
                            print("Class e type error  data socket error in playloop worker")
                            print(e)
                            time.sleep(0.1)
                            self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
                            self.SigFinished.emit()
                            time.sleep(0.1)
                            return
                        if format[2] == 16 or format[2] == 32:
                            size = fileHandle.readinto(data)
                        elif format[2] == 24:
                            data = self.read24(format,data,fileHandle)
                            size = len(data)

                        #  read next 2048 samples
                        count += 1
                        if count > junkspersecond:
                            self.SigIncrementCurTime.emit()
                            count = 0
                            #self.mutex.lock()
                            gain = self.get_gain()
                            #print(f"diagnostic: gain in worker: {gain}")
                            self.set_data(data)
                            #self.mutex.unlock()
                    else:
                        #print("Pause, do not do anything")
                        time.sleep(0.1)
                        if self.stopix is True:
                            break
                else:
                    if not self.get_pause():
                        #print("test reached")
                        if format[2] == 16 or format[2] == 32:
                            size = fileHandle.readinto(data)
                        elif format[2] == 24:
                            data = self.read24(format,data,fileHandle)
                            size = len(data)
                        #print(f"size read: {size}")
                        #print(data[1:10])
                        #size = fileHandle.readinto(data)
                        time.sleep(0.0001)
                        #  read next 2048 bytes
                        count += 1
                        if count > junkspersecond and size > 0:
                            #print('timeincrement reached')
                            self.SigIncrementCurTime.emit()
                            gain = self.get_gain()
                            #print(f"diagnostic: gain in worker: {gain}")
                            #print(f"maximum: {np.max(data)}")
                            #self.set_data(gain*data)
                            self.set_data(data)
                            count = 0
                    else:
                        time.sleep(1)
                        if self.stopix is True:
                            break
            self.set_fileclose(True)
            fileHandle.close()
            #self.set_fileclose(True)
        #print('worker  thread finished')
        self.SigFinished.emit()
        #print("SigFinished from playloop emitted")


    def stop_loop(self):
        self.stopix = True

    def read24(self,format,data,filehandle):
       for lauf in range(0,self.DATABLOCKSIZE):
        d = filehandle.read(3)
        if d == None:
            data = []
        else:
            dataraw = unpack('<%ul' % 1 ,d + (b'\x00' if d[2] < 128 else b'\xff'))
            #formatlist: [formattag blockalign bitpsample]
            if format[0] == 1:
                data[lauf] = np.float32(dataraw[0]/8388608)
            else:
                data[lauf] = dataraw[0]
        return data
       
    def rec_loop(self):
        """
        worker loop for receiving data from STEMLAB server
        data is written to file
        loop runs until EOF or interruption by stopping
        loop cannot be paused
        data format i16; 2xi16 complex; FormatTag 1
        sends signals:     
            SigFinished = pyqtSignal()
            SigIncrementCurTime = pyqtSignal()
            SigBufferOverflow = pyqtSignal()

        :param : no regular parameters; as this is a thread worker communication occurs via
        class slots __slots__[i], i = 0...3
        __slots__[0]: filename = complete file path pathname/filename Type: list
        __slots__[1]: timescaler = bytes per second  TODO: rescaling to samples per second would probably be more logical, Type int
        __slots__[2]: TEST = flag for test mode Type: bool
        __slots__[3]: pause : if True then do not send data; Boolean
        __slots__[4]: filehandle: returns current filehandle to main thread methods on request 
        __slots__[5]: data segment to be returned every second
        __slots__[6]: gain, scaling factor for playback
        __slots__[7]: formatlist: [formattag blockalign bitpsample]
        __slots__[8]: datablocksize

        :type : none

        :return: none
        :rtype: none
        """
        size2G = 2**31
        self.stopix = False
        filename = self.get_filename()
        self.timescaler = self.get_timescaler()
        RECSEC = self.timescaler*2 #TODO only true for complex 32 format (2x i16); in case of format change this has to be adapted acc to Bytes per sample (nBytesAlign)
        self.TEST = self.get_TEST()
        #TODO: self.fmtscl = self.get_formattag() #scaler for data format        
        fileHandle = open(filename, 'ab') #TODO check if append mode is appropriate
        #print(f"filehandle for set_4: {fileHandle} of file {filename} ")
        self.set_fileHandle(fileHandle)
        self.format = self.get_formattag()
        self.set_datablocksize(self.DATABLOCKSIZE)
        data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
        self.BUFFERFULL = self.DATABLOCKSIZE * 4
        if hasattr(self.stemlabcontrol, 'data_sock'):
            size = self.stemlabcontrol.data_sock.recv_into(data)
        else:
            size = 1
        self.set_data((data[0:size//4] * 32767).astype(np.int16))        
        #junkspersecond = self.timescaler / (self.JUNKSIZE)
        self.count = 0
        readbytes = 0
        totbytes = 0
        while size > 0 and self.stopix is False:
            if self.TEST is False:
                self.mutex.lock()             
                fileHandle.write((data[0:size//4] * 32767).astype(np.int16))
                # size is the number of bytes received per read operation
                # from the socket; e.g. DATABLOCKSIZE samples have
                # DATABLOCKSIZE*8 bytes, the data buffer is specified
                # for DATABLOCKSIZE float32 elements, i.e. 4 bit words
                size = self.stemlabcontrol.data_sock.recv_into(data)
                if size >= self.BUFFERFULL:
                    #self.SigBufferOverflow.emit()
                    pass
                    #print(f"size: {size} buffersize: {self.BUFFERFULL}")
                #  write next BUFFERSIZE bytes
                # TODO: check for replacing clock signalling by other clock
                readbytes = readbytes + size
                if readbytes > RECSEC:
                    self.set_data((data[0:size//4] * 32767).astype(np.int16))
                    self.SigIncrementCurTime.emit()
                    totbytes += int(readbytes/2)
                    readbytes = 0
                    #print(f"totbytes {totbytes}")
                if totbytes > size2G - self.DATABLOCKSIZE*4:
                    #print(f">>>>>>>>>>>>>>>>>>>rec_loop eof reached totbytes: {totbytes} ref: {size2G - self.DATABLOCKSIZE}")
                    self.stopix = True 
                self.mutex.unlock()
            else:           # Dummy operations for testing without SDR
                time.sleep(1)
                self.SigBufferOverflow.emit()  #####TEST ONLY
                self.count += 1
                self.SigIncrementCurTime.emit()
                self.mutex.lock()
                data[0] = 0.05
                data[1] = 0.0002
                data[2] = -0.0002
                a = (data[0:2] * 32767).astype(np.int16)
                #print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>> testrun recloop a: {a}")
                fileHandle.write(a)
                self.set_data(a)
                self.mutex.unlock()
                time.sleep(0.1)
        self.SigFinished.emit()