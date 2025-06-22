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
import platform
import libm2k
import threading
import queue
import yaml

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

#from dev_drivers.fl2k_stream.test_fl2kstreaming_from_file_tofl2k_file_outputfile import gen_ffmpeg_cmd


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
        self.DATABLOCKSIZE_BASIC = 4096*256#4096*256*32
        self.DATASHOWSIZE = 1024
        
        self.mutex = QMutex()
        self.stemlabcontrol = stemlabcontrolinst
        self.output_chunks = []
        self.chunk_queue = queue.Queue(maxsize=10)  # Buffer size = 10 blocks
        configpath = os.path.join(os.getcwd(), "config_wizard.yaml")
        try:
            stream = open(configpath, "r")
            metadata = yaml.safe_load(stream)
            stream.close()
            self.ffmpeg_path = metadata["ffmpeg_path"]
        except FileNotFoundError:
            print(f"cohi_playrecworker for ADALM initialization failed: Configuration file {configpath} not found, using default ffmpeg path")
            self.ffmpeg_path = "ffmpeg"


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
    def get_datablocksize(self): #never used here !
        return(self.__slots__[8])
    def set_datablocksize(self,_value): #never used here !
        self.__slots__[8] = _value
    def get_fileclose(self):
        return(self.__slots__[9])
    def set_fileclose(self,_value):
        self.__slots__[9] = _value
    def get_configparameters(self):
        return(self.__slots__[10])
    def set_configparameters(self,_value):
        self.__slots__[10] = _value


    def pipe_reader_thread(self, stdout_pipe, buffer_size):
        try:
            while True:
                chunk = stdout_pipe.read(buffer_size)
                if not chunk:
                    break
                self.chunk_queue.put(chunk)  # non-blocking push into queue
        except Exception as e:
            print(f"Reader thread cannot read further data, probably EOF: {e}")
        finally:
            self.chunk_queue.put(None)  # Signal: EOF

    def pusher_thread(self, ao):
        try:
            while True:
                chunk = self.chunk_queue.get()
                if chunk is None:
                    break  # EOF
                samples = np.frombuffer(chunk, dtype=np.float32).tolist()
                if ao == None:
                    #TODO TODO TODO: throw error and return to caller
                    print(f"pusher thread chunk begin: {chunk[:10]}... end: {chunk[-10:]}")
                else:
                    ao.push(0, samples)
        except Exception as e:
            print(f"Pusher thread error: {e}")


    def gen_ffmpeg_cmd(self, ffmpeg_path, SRAdalm = 2500000, sampling_rate = 1250000 , lo_shift = 1125000, preset_volume = 1):
        """generates ffmpeg command for reading from stdin, complex modulation to target RF band
        and writing to stdout.

        :param ffmpeg_path: path to the ffmpeg executable
        :type ffmpeg_path: str
        :param SRAdalm: effective Sampling rate of transfer to the ADALM2000
        :type SRDdalm: int
        :param sampling_rate: sampling rate of the IQ file to be processed
        :type sampling_rate: int
        :param lo_shift: local oscillator shift
        :type lo_shift: int
        :param preset_volume: preset volume level
        :type preset_volume: int        
        :return: ffmpeg command as a list of strings
        :rtype: list[str]
        """
        formatstring = "s16le"
        #SRAdalm = 7500000 #maximum DAC SR of Adalm
    
        a = (np.tan(np.pi * lo_shift / SRAdalm) - 1) / (np.tan(np.pi * lo_shift / SRAdalm) + 1)

        ffmpeg_cmd = [
            os.path.join(str(ffmpeg_path),"ffmpeg"), "-y", "-loglevel", "error", "-hide_banner",
            "-f", formatstring, "-ar", str(sampling_rate), "-ac", "2", "-i", "-",  # Lese von stdin
            "-filter_complex",
            "[0:a]aresample=osr=" + str(SRAdalm) + ",channelsplit=channel_layout=stereo [re][im];"
            "sine=frequency=" + str(lo_shift) + ":sample_rate="  + str(SRAdalm) + "[sine_base];"
            "[sine_base] asplit=2[sine_sin1][sine_sin2];"
            "[sine_sin2]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos];"
            "[re][sine_cos]amultiply[mod_re];"
            "[im][sine_sin1]amultiply[mod_im];"
            "[mod_im]volume=volume="  + str(preset_volume) + "[part_im];"
            "[mod_re]volume=volume="  + str(preset_volume) + "[part_re];"
            "[part_re][part_im]amix=inputs=2:duration=shortest[out]",
            #"-map", "[out]", "-c:a", "pcm_s8", "-f", "caf", "-"
            #"-map", "[out]", "-c:a", "pcm_f32le", "-f", "caf", str(outfile)
            "-map", "[out]", "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"  # Schreibe in die Standardausgabe (stdout)
            ]

        return ffmpeg_cmd

    def maximize_OSR(self, SRDAC, lo_shift, sampling_rate):
        """Calculate oversampling OSR from SRDAC and required Nyquist frequency
        f_nyquist = (lo_shift+sampling_rate/2))
        OSR is tha value which divides SRDAC such that 
        (1) SRDAC/OSR >= 2 * f_nyquist
        (2) r = SRDAC/OSR is integer, ideally r is an integer multiple of sampling_rate 

        :param SRDAC: sampling rate of the ADALM DAC (clock)
        :type SRDAC: int
        :param lo_shift: central frequency f the band plus offset (LO frequency)
        :type lo_shift: int
        :param sampling_rate: bandwidth of the complex IQ signal == sampling rate of IQ file
        :type sampling_rate: int
        
        :return: oversampling rate OSR

        """
        f_nyquist = lo_shift+sampling_rate/2
        r_max = SRDAC / (2 *f_nyquist) # maximum allowable OSR
        for OSR in np.arange(int(np.floor(r_max)),1,-1):
            r = SRDAC / OSR
            if SRDAC % r == 0:
                break
            print(f"lo_shift: {lo_shift}, sampling_rate: {sampling_rate}, f_nyquist: {f_nyquist}")
        return OSR


    def play_loop_filelist(self):
        """
        worker loop for sending data to ADALM2000
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

        # =============== get parameters from slots ================
        #print("reached playloopthread")
        filenames = self.get_filename()
        TEST = self.get_TEST()
        gain = self.get_gain()
        self.stopix = False
        self.set_fileclose(False)
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        sampling_rate = configuration["irate"]
        lo_shift = configuration["ifreq"]# - configuration["LO_offset"]

        # ==== initialize ADALM2000 / check for readyness ====
        #TODO TODO TODO ADALM: adapt to ADALM needs: check if 75MS/s is appropriate for data transfer over USB - maybe too fast
        SRDAC = 75000000 # max DAC SR of Adalm for max oversampling
        ################TODO TODO TODO: test/check calculated OSR
        #OSR must be such that SRDAC/highestfreq = nearest integer
        #OSR = 30
        OSR = self.maximize_OSR(SRDAC, lo_shift, sampling_rate)
        print(f"checking for ADALM2000")
        self.mutex.lock()
        errorstate = False
        errorstate, value = self.check_ready_ADALM()
        ctx = value
        print(f"playrecworker init called, ctx: {ctx}")
        self.mutex.unlock()
        ao = None
        if not errorstate and not TEST:
            print(f"plyercworker: ctx: {ctx}")
            channel = 0  # DAC-Kanal für Ausgabe
            ao = ctx.getAnalogOut()
            ao.setSampleRate(channel, SRDAC)
            print(f" >>>>>> ADALM2000 OSR: {OSR}")
            ao.setOversamplingRatio(channel, int(OSR)) ### TODO: set oversampling ratio according band requirements; 
            #For MW we could live with a value between 15 and 20 
            ao.enableChannel(channel, True)
            ao.setKernelBuffersCount(0, 32)
            ao.setCyclic(False)

        elif not TEST:
            print("no ADALM2000 present")
            self.SigError.emit(value)
            self.SigFinished.emit()
            return()


        # ======================= get formatstring and preset volume ========================
        format = self.get_formattag()
        #system = platform.system().lower()

        ffmpeg_path = self.ffmpeg_path

        # ======================= set formatstring, DATABLOCKSIZE and preset volume ========================
        #TODO TODO TODO: correct preset_volume
        if format[0] == 1:  #PCM
            if format[2] == 16:
                formatstring = "s16le"
                preset_volume = 10
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
            elif format[2] == 24:   #24 bit PCM
                #formatstring = "f32le"
                formatstring = "s24le"
                preset_volume = 200
                self.DATABLOCKSIZE = 4096*256*24 #former 1024*48
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
            elif format[2] == 32:
                formatstring = "s32le"  #32 bit PCM 
                preset_volume = 1
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32)
            else:
                self.SigError.emit(f"Format not supported: {format[2]}")
                self.SigFinished.emit()
                if not TEST:
                    libm2k.contextClose(ctx)
                return()
        else: #IEEE float   
            if format[2] == 32:
                formatstring = "f32le"
                preset_volume = 1
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float32) #TODO: check if true for 32-bit wavs wie Gianni's
            elif format[2] == 16:   #16 bit float
                formatstring = "f16le"
                preset_volume = 200
                self.DATABLOCKSIZE = self.DATABLOCKSIZE_BASIC
                data = np.empty(self.DATABLOCKSIZE, dtype=np.float16)
            else:
                self.SigError.emit(f"Format not supported: {format[2]}")
                self.SigFinished.emit()
                if not TEST:
                    libm2k.contextClose(ctx)
                return()
        #ADALM_blocksize = self.DATABLOCKSIZE 

        print(f"ADALM2000 <<<<<<<<<<<<< oooooo >>>>>>>>>>>> format: {format}")
        print(f"playloop: BitspSample: {format[2]}; wFormatTag: {format[0]}; Align: {format[1]}")
        self.JUNKSIZE = self.DATABLOCKSIZE/2

        if True: #not TEST:
            # ======================= ffmpeg command generation and start ffmpeg process ========================
            try:
                ffmpeg_cmd = self.gen_ffmpeg_cmd(ffmpeg_path, SRDAC/OSR, sampling_rate , lo_shift , preset_volume )

                # start ffmpeg Process
                ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
                    stdin=subprocess.PIPE, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT
                )  
                print(f"<<<<<<<<<<<<<<< ADALM 2000: ffmpeg_command: {ffmpeg_cmd}")
            except FileNotFoundError:
                print(f"Input file not found, probably ffmpeg path is wrong")
                if not TEST:
                    libm2k.contextClose(ctx)
                return()
            except subprocess.SubprocessError as e:
                print(f"Error when executing ADALM ffmpeg: {e}")
                if not TEST:
                    libm2k.contextClose(ctx)
                return()    
            except Exception as e:
                print(f"Unexpected error: {e}")
                if not TEST:
                    libm2k.contextClose(ctx)
                return()    
            
            # if os.name.find("posix") >= 0:
            #     pass
            # else:
            #     #psutil.Process(ffmpeg_process.pid).nice(psutil.HIGH_PRIORITY_CLASS)
            #     pass

        #================================ start reader and pusher threads ================
        print(f"datablocksize: {self.DATABLOCKSIZE} formatstring: {formatstring} gain: {gain}")
        reader = threading.Thread(target=self.pipe_reader_thread, args=(ffmpeg_process.stdout, self.DATABLOCKSIZE))
        reader.start()
        pusher = threading.Thread(target=self.pusher_thread, args=(ao,))
        pusher.start()

        # ======================= read files blockwise and send data to ffmpeg | reader | pusher | ADALM2000 ctx ========================

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
                #print(f"iteration loop entered play_loop_filelist: size: {size} junkspersecond: {junkspersecond} count: {count}")
                self.mutex.lock()
                if ffmpeg_process.poll() != None:
                    self.SigError.emit(f"ffmpeg process terminated unexpectedly, pipe broken")
                    print("Error: ffmpeg process terminated")
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
                        # write block to ffmpeg stdin which processes and sends to further processing pipe via stdout
                        ffmpeg_process.stdin.flush()

                    except BlockingIOError:
                        print("Blocking data socket error in playloop worker")
                        time.sleep(0.1)
                        self.SigError.emit("Blocking data socket error in playloop worker")
                        self.SigFinished.emit()
                        time.sleep(0.1)
                        if not TEST:
                            libm2k.contextClose(ctx)
                        return
                    except ConnectionResetError:
                        print("Diagnostic Message: Connection data socket error in playloop worker")
                        time.sleep(0.1)
                        self.SigError.emit("Diagnostic Message: Connection data socket error in playloop worker")
                        self.SigFinished.emit()
                        time.sleep(0.1)
                        if not TEST:
                            libm2k.contextClose(ctx)
                        return
                    except Exception as e:
                        print("Class e type error data transfer error in playloop worker")
                        print(e)
                        time.sleep(0.1)
                        self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
                        self.SigFinished.emit()
                        time.sleep(0.1)
                        if not TEST:
                            libm2k.contextClose(ctx)
                        return
                    except BrokenPipeError:
                        time.sleep(0.1)
                        self.SigError.emit(f"Broken Pipe: FFMPEG-Prozess terminated or pipe closed. Please restart procedure.")
                        self.SigFinished.emit()
                        time.sleep(0.1)
                        print(" FFMPEG-Prozess terminated or pipe closed. Please restart procedure.")
                        if not TEST:
                            libm2k.contextClose(ctx)
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
        print("close file ")
        self.set_fileclose(True)
        fileHandle.close()

        if True: #not TEST:
            # terminate ADALM_file process and wait for actual termination
            ffmpeg_process.stdin.close()  # close stdin
            ffmpeg_process.stdout.close()  # close stdout
            ffmpeg_process.terminate()  # stop process gently
            ffmpeg_process.wait()  # wait for process termination
            reader.join()
            pusher.join()
            if ao is not None:
                try:
                    print("close ADALM ao object")
                    ao.push(0, [0.0] * 5000)  # send a final block of zero data
                    time.sleep(0.01)
                    ao.enableChannel(0, False)
                    ao.setSampleRate(0, 0)
                except Exception as e:
                    print("Error closing ADALM2000 context or disabling channel:", e)

            self.SigFinished.emit()
            print("playrecworker >>>>>>>>>> close ctx")
            if not TEST:
                libm2k.contextClose(ctx)
            return()

    def check_ready_ADALM(self):
        """check if ADALM device is connected and ready for use
        """
        errorstate = False
        value = ""
        try:
            ctx = libm2k.m2kOpen()
            ctx.calibrateDAC()
            value = ctx
        except FileNotFoundError:
            value = (f"Input file not found")
            errorstate = True
            return(errorstate, value)
        except Exception as e:
            value = (f"unexpected error in play_loop_filelist for ADALM , please check if the system is connected and ready {e}")
            errorstate = True
            return(errorstate, value)    
 
        print("leave check_ready_ADALM")
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
