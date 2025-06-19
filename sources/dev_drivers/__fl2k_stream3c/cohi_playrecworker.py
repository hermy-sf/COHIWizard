"""
Created on Feb 24 2024

#@author: scharfetter_admin
"""
#from pickle import FALSE, TRUE #intrinsic
import time
#from datetime import timedelta
from socket import socket, AF_INET, SOCK_STREAM
from struct import unpack
import numpy as np
import os
import signal 
import psutil
import subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


class playrec_worker(QObject):
    """ worker class for data streaming thread from PC to a SDR device
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
        __slots__[9]: file_close
        __slots__[10]: sampling_parameters
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
    SigInfomessage = pyqtSignal(str)

    def __init__(self, stemlabcontrolinst,*args,**kwargs):

        super().__init__(*args, **kwargs)
        self.stopix = False
        self.DATABLOCKSIZE_BASIC = 1024*64
        self.DATASHOWSIZE = 1024
        
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
        __slots__[1]: timescaler = bytes per second Type: int
        __slots__[2]: TEST = flag for test mode Type: bool
        __slots__[3]: pause : if True then do not send data; Boolean
        __slots__[4]: filehandle: returns current filehandle to main thread methods on request 
        __slots__[5]: data segment to be returned every second
        __slots__[6]: gain, scaling factor for playback
        __slots__[7]: formatlist: [formattag blockalign bitpsample]
        __slots__[9]: file_close
        __slots__[10]: sampling_parameters
        """
        #print("reached playloopthread")
        filenames = self.get_filename()
        TEST = self.get_TEST()
        gain = self.get_gain()
        self.stopix = False
        self.set_fileclose(False)
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        sampling_rate = configuration["irate"]
        lo_shift = configuration["ifreq"]# - configuration["LO_offset"]
        tSR = 10000000*(1 + np.floor((lo_shift+sampling_rate/2)*2/10000000)) #TODO: investigate more thoroughly and optimize !
        tSR = min(100000000,tSR)
        format = self.get_formattag()
        a = (np.tan(np.pi * lo_shift / tSR) - 1) / (np.tan(np.pi * lo_shift / tSR) + 1)
        fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k/osmo-fl2k-64bit-20250105", "fl2k_file.exe")
        ffmpeg_file_path = os.path.join(os.getcwd(),"ffmpeg-master-latest-win64-gpl-shared/bin", "ffmpeg.exe")
        #TODO: check evaluation criterion if appropriate
        stability_criterion = (np.mod(np.log2(tSR/sampling_rate),1) == 0) or sampling_rate < 500001
        print(f"stability criterion: {stability_criterion}")
        if not stability_criterion:
            self.SigInfomessage.emit(f"""The ratio between target sampling rate and
                                     source sampling rate ({tSR/sampling_rate}) is not a power of 2: 
                                     This may cause issues with playback quality and stability. 
                                     In case the sampling rate is > 500kS/s the playback may 
                                     not work at all in such cases and the program may crash. 
                                     To be on the safe side re-sample the recording to an appropriate SR so that 
                                     The ratio between target sampling rate and 
                                     source sampling rate ({tSR/sampling_rate}) is something like 2, 4, 8, 16, ...""")
        # else:
        #     self.SigInfomessage.emit("Teststring from SigInfoMessage, SR criterion is fullfilled")
        
        print("checking for fl2k")
        #self.mutex.lock()
        errorstate, value = self.check_ready_fl2k()
        print("MUTEX")
        # if errorstate:
        #     print("no fl2k present")
        #     self.SigError.emit(value)
        #     self.SigFinished.emit()
        #     return()
        #self.mutex.unlock()
        print("past MUTEX")
        if format[0] == 1:  #PCM
            if format[2] == 16:
                formatstring = "s16le"
                preset_volume = 2
            elif format[2] == 24:   #24 bit PCM
                formatstring = "f32le"
                formatstring = "s24le"
                preset_volume = 20
            elif format[2] == 32:
                formatstring = "s32le"  #32 bit PCM 
                preset_volume = 2
            else:
                self.SigError.emit(f"Format not supported: {format[2]}")
                self.SigFinished.emit()
                return()
        else: #IEEE float   
            if format[2] == 32:
                formatstring = "f32le"
                preset_volume = 2
            elif format[2] == 16:   #16 bit float
                formatstring = "f16le"
                preset_volume = 2
            else:
                self.SigError.emit(f"Format not supported: {format[2]}")
                self.SigFinished.emit()
                return()

        if not TEST:
            #Start ffmpeg Process:
            #preset_volume = 2
            try:
                #TODO: simplify this part
                if os.name.find("posix") >= 0:
                    ffmpeg_cmd = [
                    "ffmpeg", "-y", "-loglevel", "error", "-hide_banner",  
                    "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
                    "-filter_complex",
                    "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
                    "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
                    "[sine_base] asplit=2[sine_sin1][sine_sin2];"
                    "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
                    "[re][sine_cos]amultiply[mod_re];"
                    "[im][sine_sin1]amultiply[mod_im];"
                    "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];"
                    "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
                    "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
                    "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
                    ]
                else:
                    ffmpeg_cmd = [
                    ffmpeg_file_path, "-y", "-loglevel", "error", "-hide_banner",  
                    "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
                    "-filter_complex",
                    "[0:a]aresample=osr=" + str(tSR) + ",channelsplit=channel_layout=stereo [re][im];"
                    "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(tSR) + "[sine_base];"
                    "[sine_base] asplit=2[sine_sin1][sine_sin2];"
                    "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
                    "[re][sine_cos]amultiply[mod_re];"
                    "[im][sine_sin1]amultiply[mod_im];"
                    "[mod_im]volume=volume=" + str(preset_volume) + "[part_im];"
                    "[mod_re]volume=volume=" + str(preset_volume) + "[part_re];"
                    "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
                    "-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
                    ]
                # Prozess starten
                ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    bufsize=10**8)
                print(f"ffmpeg_command: {ffmpeg_cmd}")
            except FileNotFoundError:
                print(f"Input file not found, probably ffmpeg path is wrong")
                return()
            except subprocess.SubprocessError as e:
                print(f"Error when executing fl2k_file: {e}")
                return()    
            except Exception as e:
                print(f"Unexpected error: {e}")
                return()    
            
            if os.name.find("posix") >= 0:
                pass
            else:
                psutil.Process(ffmpeg_process.pid).nice(psutil.HIGH_PRIORITY_CLASS)
                pass

            if os.name.find("posix") >= 0:
                try:
                    fl2k_process = subprocess.Popen(
                        ["fl2k_file", "-s", str(tSR), "-r", "0", "-"],
                        stdin=ffmpeg_process.stdout,  # Hier kommt der FFmpeg-Stream an
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=10**8
                    )
                    
                except FileNotFoundError:
                    self.SigError.emit(f"Input file not found")
                    self.SigFinished.emit()
                    return()
                except subprocess.SubprocessError as e:
                    self.SigError.emit(f"Error when executing fl2k_file: {e}")
                    self.SigFinished.emit()
                    return()
                except Exception as e:
                    self.SigError.emit(f"Unexpected error: {e}")
                    print("unexpected error in play_loop_filelist for fl2k")
                    self.SigFinished.emit()
                    return()
            else:

                # Starten von fl2k_file mit den entsprechenden Parametern
                try:
                    fl2k_process = subprocess.Popen(
                        [fl2k_file_path, "-s", str(tSR), "-r", "0", "-"],
                        stdin=ffmpeg_process.stdout,  # Hier kommt der FFmpeg-Stream an
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=10**8
                    )

                except FileNotFoundError:
                    self.SigError.emit(f"Input file not found")
                    self.SigFinished.emit()
                    return()
                except subprocess.SubprocessError as e:
                    self.SigError.emit(f"Error when executing fl2k_file: {e}")
                    self.SigFinished.emit()
                    return()
                except Exception as e:
                    self.SigError.emit(f"Unexpected error: {e}")
                    self.SigFinished.emit()
                    return()
                psutil.Process(fl2k_process.pid).nice(psutil.HIGH_PRIORITY_CLASS)

        else:
            print("fl2k worker TEST condition , no fl2k_file process started <<<<<<<<<<<<<<<<")

        print(f"<<<<<<<<<<<<< oooooo >>>>>>>>>>>> format: {format}")
        if format[0] == 1: #PCM              
            if format[2] == 16:
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
            elif format[2] == 32:
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
            elif format[2] == 24:
                self.DATABLOCKSIZE = 1024*48
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
        else:
            if format[2] == 16:
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float16)
            elif format[2] == 32:
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32) #TODO: check if true for 32-bit wavs wie Gianni's
            elif format[2] == 24:
                self.DATABLOCKSIZE = 1024*48
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
        print(f"playloop: BitspSample: {format[2]}; wFormatTag: {format[0]}; Align: {format[1]}")
        self.JUNKSIZE = self.DATABLOCKSIZE/2
        for ix,filename in enumerate(filenames):
            fileHandle = open(filename, 'rb')
            if format[2] == 24:
                fileHandle.seek(212, 1)
                print(f"set read offset to 24 bit 216")
                #fileHandle.seek(bit24offset, 1)
            else:
                fileHandle.seek(216, 1)
            count = 0

            #fileHandle.seek(212)

            if format[0] == 1:
                normfactor = int(2**int(format[2]-1))-1
            else:
                normfactor = 1
            if format[2] == 16 or format[2] == 32:
                size = fileHandle.readinto(data)
            elif format[2] == 24: #TODO: not yet supported or tested
                #data = self.read_24bit_block_np(fileHandle, self.DATABLOCKSIZE)
                data = fileHandle.read(self.DATABLOCKSIZE * 3)
                #data = self.read24(format,data,fileHandle,self.DATABLOCKSIZE)
                #print(f"datasample read24 200 - 220: {data[200:220]}")
                size = len(data)
                if format[2] == 24:
                    print(f"++++++ DATASHOWSIZE: {self.DATASHOWSIZE} len(showdata):   {len(data[0:int(6*np.floor(self.DATASHOWSIZE/6))])}")
                    showdata = self.convert24_32(data[5:int(6*np.floor(self.DATASHOWSIZE/6))+5])
                    if not np.isnan(showdata).any():
                        self.set_data(showdata)
                    else:
                        print("############# NaN NaN NaN NaN in showdata ################")
                else:
                    self.set_data(data[0:self.DATASHOWSIZE])
            #self.set_data(data)
            junkspersecond = sampling_rate / self.JUNKSIZE
            self.SigNextfile.emit(filename)
            true_filesize = os.stat(filename).st_size
            bit24offset = int(true_filesize - int(np.floor(true_filesize/6))*6)
            print(f"24 bit fileoffset calculated from end {bit24offset} <----------------------------")
            self.set_fileHandle(fileHandle)
            format = self.get_formattag()
            data_blocksize = self.DATABLOCKSIZE
            self.set_datablocksize(data_blocksize)

            while size > 0 and not self.stopix:
                if not TEST:
                    self.mutex.lock()
                    if ffmpeg_process.poll() != None:
                        self.SigError.emit(f"ffmpeg process terminated unexpectedly, pipe broken")
                        print("Error: ffmpeg process terminated")
                        break
                    if fl2k_process.poll() != None:
                        self.SigError.emit(f"fl2k process terminated unexpectedly, pipe broken; Please check if the USB-VGA dongle is connected")
                        print("Error: fl2k process terminated")
                        break
                    self.mutex.unlock()
                    if not self.get_pause():
                        try:
                            #TODO: AGC pending
                            
                            if formatstring == "s16le":
                                aux1 = gain*data[0:size]
                                ffmpeg_process.stdin.write(aux1.astype(np.int16))
                            elif formatstring == "s32le":
                                aux1 = gain*data[0:size]
                                ffmpeg_process.stdin.write(aux1.astype(np.int32))
                            elif formatstring == "f32le":
                                aux1 = gain*data[0:size]
                                ffmpeg_process.stdin.write(aux1.astype(np.float32))
                            elif formatstring == "s24le":
                                ffmpeg_process.stdin.write(data)
                            else :   #16 bit float	
                                aux1 = gain*data[0:size]
                                ffmpeg_process.stdin.write(aux1.astype(np.float16))

                            ffmpeg_process.stdin.flush()
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
                        except BrokenPipeError:
                            time.sleep(0.1)
                            self.SigError.emit(f"Broken Pipe: FFMPEG-Prozess beendet oder Pipe geschlossen. Neustart erforderlich.")
                            self.SigFinished.emit()
                            time.sleep(0.1)
                            print("FFMPEG-Prozess beendet oder Pipe geschlossen. Neustart erforderlich.")
                            return

                        QThread.usleep(1) #sleep 5 us for keeping main GUI responsive
                        if format[2] == 24:
                            data = fileHandle.read(self.DATABLOCKSIZE * 3)
                            #data = self.read_24bit_block_np(fileHandle, self.DATABLOCKSIZE)
                            #print(f"datasample read24 200 - 220: {data[200:220]}, type(data: {type(data)})")
                            size = len(data)
                        else:
                            size = fileHandle.readinto(data)

                        count += 1
                        if count > junkspersecond:
                            #cv = np.zeros(2*self.DATASHOWSIZE)
                            #cv[0:2*self.DATASHOWSIZE-1:2] = data[0:self.DATASHOWSIZE] #write only real part
                            if format[2] == 24:
                                print(f"++++++ DATASHOWSIZE: {self.DATASHOWSIZE} len(showdata):   {len(data[0:int(6*np.floor(self.DATASHOWSIZE/6))])}")
                                showdata = self.convert24_32(data[5:int(6*np.floor(self.DATASHOWSIZE/6))+5])
                                if not np.isnan(showdata).any():
                                    self.set_data(showdata)
                                else:
                                    print("############# NaN NaN NaN NaN in showdata ################")
                            else:
                                self.set_data(data[0:self.DATASHOWSIZE])
                            self.SigIncrementCurTime.emit()
                            count = 0
                            gain = self.get_gain()
                    else:
                        aux1 = 0*data[0:size]
                        ffmpeg_process.stdin.write(aux1)
                        ffmpeg_process.stdin.flush()
                        time.sleep(0.1)
                        if self.stopix is True:
                            break
                else:
                    if not self.get_pause():
                        print(" SDR_control fl2k test reached")
                        if format[2] == 24:
                            data = fileHandle.read(self.DATABLOCKSIZE * 3)
                            #data = self.read_24bit_block_np(fileHandle, self.DATABLOCKSIZE)
                            #print(f"datasample read24 200 - 220: {data[200:220]}, type(data: {type(data)})")
                            size = len(data)
                        else:
                            size = fileHandle.readinto(data)
                        time.sleep(self.DATABLOCKSIZE/2/sampling_rate)
                        count += 1
                        if count > junkspersecond and size > 0:
                            if format[2] == 24:
                                print(f"++++++ DATASHOWSIZE: {self.DATASHOWSIZE} len(showdata):   {len(data[0:int(6*np.ceil(self.DATASHOWSIZE/6))])}")
                                showdata = self.convert24_32(data[0:int(6*np.ceil(self.DATASHOWSIZE/6))])
                                if not np.isnan(showdata).any():
                                    self.set_data(showdata)
                                else:
                                    print("############# NaN NaN NaN NaN in showdata ################")
                            else:
                                self.set_data(data[0:self.DATASHOWSIZE])
                            self.SigIncrementCurTime.emit()
                            gain = self.get_gain()
                            count = 0
                    else:
                        time.sleep(1)
                        if self.stopix is True:
                            break
        print("close file ")
        self.set_fileclose(True)
        fileHandle.close()

        if not TEST:
            # terminate fl2k_file process and wait for actual termination
            ffmpeg_process.stdin.close()  # close stdin
            ffmpeg_process.stdout.close()  # close stdout
            ffmpeg_process.terminate()  # stop process gently
            ffmpeg_process.wait()  # wait for process termination
            stdout, stderr = fl2k_process.communicate()  # wait for the end of fl2k_file
            # report result
            print("fl2k output:")
            print(stdout.decode())
            if stderr:
                print("fl2k_file errors:")
                print(stderr.decode())

        self.SigFinished.emit()
        return()


    def check_ready_fl2k(self):
        """check if fl2k device is connected and ready for use
        """
        errorstate = False
        value = ""
        tSR = 10000000
        if os.name.find("posix") >= 0:#["fl2k_file", "-s", str(tSR), "-r", "0", "-"],
            try:
                fl2k_process = subprocess.Popen(
                    ["fl2k_file", "-s", str(tSR), "-r", "0", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid
                )
                
            except FileNotFoundError:
                value = (f"Input file not found")
                errorstate = True
                return(errorstate, value)
            except subprocess.SubprocessError as e:
                value = (f"Error when executing fl2k_file: {e}")
                errorstate = True
                return(errorstate, value)
            except Exception as e:
                value = (f"unexpected error in play_loop_filelist for fl2k {e}")
                errorstate = True
                return(errorstate, value)    
        else:
            print("check_ready_fl2k: WINDOWS: try popen fl2k")
            try:
                fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k/osmo-fl2k-64bit-20250105", "fl2k_file.exe")
                fl2k_process = subprocess.Popen(
                    [fl2k_file_path, "-s", str(tSR), "-r", "0", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )

            except FileNotFoundError:
                value = (f"Input file not found")
                errorstate = True
                return(errorstate, value)
            except subprocess.SubprocessError as e:
                value = (f"Error when executing fl2k_file: {e}")
                errorstate = True
                return(errorstate, value)
            except Exception as e:
                value = (f"unexpected error in play_loop_filelist for fl2k {e}")
                errorstate = True
                return(errorstate, value)
        time.sleep(0.2)
        print(f"check_ready_fl2k: poll: {fl2k_process.poll()}")
        if fl2k_process.poll() != None:
            errorstate = True
            value = "check_ready_fl2k: fl2k device not ready"
        else:
            print("fl2k_file is ready, terminate test process")
            value = "check_ready_fl2k: fl2k device ready"

            fl2k_process.terminate()
            try:
                fl2k_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print("Process did not terminate, forcefully killing it")
                if os.name == "posix":
                    os.killpg(os.getpgid(fl2k_process.pid), signal.SIGKILL)  # Linux/macOS
                else:
                    fl2k_process.kill()  # Windows

            # Ensure the process is reaped properly
            try:
                fl2k_process.wait()
            except Exception as e:
                print(f"Error during wait(): {e}")

        print("leave check_ready_fl2k")
        return(errorstate, value)

    def stop_loop(self):
        self.stopix = True

    def read_24bit_block_np(self, file, blocksize):
        """read BLOCKSIZE 24-Bit-Samples and returns as float32"""
        raw_data = file.read(blocksize * 3)  # 3 Bytes pro Sample
        if len(raw_data) < 3:
            return np.array([], dtype=np.int32)  # Leeres Array bei Dateiende
        # Bytes als numpy array laden (dtype uint8)
        raw_array = np.frombuffer(raw_data, dtype=np.uint8)
        # Zu 24-Bit Werten umformen
        raw_array = raw_array.reshape(-1, 3)  # Jede Zeile = ein Sample [b1, b2, b3]
        # 24-Bit Little Endian zu 32-Bit signed konvertieren
        samples = raw_array[:, 0] | (raw_array[:, 1] << 8) | (raw_array[:, 2] << 16)
        # Vorzeichenkorrektur für negative Werte
        samples = samples.astype(np.int32)  # Umwandlung in 32-Bit Signed Integer
        samples[samples >= (1 << 23)] -= (1 << 24)  # Negative Werte korrigieren
        samples = samples.astype(np.float32)# / (1 << 23) # auf Wertebereich +/- 1 reskalieren
        return samples
    
    def convert24_32(self,raw_data):
        "convert raw 24 bit binary array to 32 float array"
        if len(raw_data) < 3:
            return np.array([], dtype=np.int32)  # Leeres Array bei Dateiende
        # Bytes als numpy array laden (dtype uint8)
        raw_array = np.frombuffer(raw_data, dtype=np.uint8)
        # Zu 24-Bit Werten umformen
        raw_array = raw_array.reshape(-1, 3)  # Jede Zeile = ein Sample [b1, b2, b3]
        # 24-Bit Little Endian zu 32-Bit signed konvertieren
        samples = raw_array[:, 0] | (raw_array[:, 1] << 8) | (raw_array[:, 2] << 16)
        # Vorzeichenkorrektur für negative Werte
        samples = samples.astype(np.int32)  # Umwandlung in 32-Bit Signed Integer
        samples[samples >= (1 << 23)] -= (1 << 24)  # Negative Werte korrigieren
        samples = samples.astype(np.float32) *256# / (1 << 23) # auf Wertebereich +/- 1 reskalieren
        return samples



    def read24(self,format,data,filehandle,data_blocksize):
       """probably not applicable"""
       for lauf in range(0,data_blocksize):
        print(f"datasample read24: size(data): {len(data)} blocksize: {data_blocksize}")
        d = filehandle.read(3)
        if d == None:
            print(f"datasample read24: ERROR data empty")
            data = []
        else:
            dataraw = unpack('<%ul' % 1 ,d + (b'\x00' if d[2] < 128 else b'\xff'))
            #formatlist: [formattag blockalign bitpsample]
            if format[0] == 1:
                data[lauf] = np.float32(dataraw[0]/8388608)
                print(f"dataraw: {dataraw[0]} lauf: {lauf}")
            else:
                data[lauf] = dataraw[0]
        return data
       
    def rec_loop(self):
        """
        not applicable
        """
        return()
