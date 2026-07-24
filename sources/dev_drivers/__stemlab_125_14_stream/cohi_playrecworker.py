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
import os
# import pytz
# from pathlib import Path
# from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import threading
import queue
import yaml
# from PyQt5.QtWidgets import (
#     QDialog, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
#     QLabel, QApplication, QMainWindow
# )
# import logging
import subprocess
# from auxiliaries import auxiliaries as auxi
# from auxiliaries import WAVheader_tools
# from datetime import datetime
# import datetime as ndatetime
# from player import stemlab_control
import sys
import platform


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
    SigInfomessage = pyqtSignal(str)

    def __init__(self, stemlabcontrolinst,*args,**kwargs):

        super().__init__(*args, **kwargs)
        self.stopix = False
        #self.pausestate = False
        self.JUNKSIZE = 2048*4*16
        self.DATABLOCKSIZE = 1024*4*16
        self.mutex = QMutex()
        self.stemlabcontrol = stemlabcontrolinst

        self.output_chunks = []
        self.qmaxsize = 10
        self.chunk_queue = queue.Queue(maxsize=self.qmaxsize)  # Buffer size = 10 blocks
        configpath = os.path.join(os.getcwd(), "config_wizard.yaml")
        try:
            stream = open(configpath, "r")
            metadata = yaml.safe_load(stream)
            stream.close()
            self.ffmpeg_path = metadata["ffmpeg_path"]
        except FileNotFoundError:
            print(f"cohi_playrecworker initialization failed: Configuration file {configpath} not found, using default ffmpeg path")
            self.ffmpeg_path = "ffmpeg"
        self.IQfilegain = int(1) 
        

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

    def pipe_reader_thread(self, stdout_pipe, buffer_size):
        if True:
            try:
                buffer = bytearray()
                while True:# and not self.stopix:
                    try:
                        chunk = stdout_pipe.read(buffer_size - len(buffer))
                    except:
                        print("⚠️ Pipe read error, check for EOF, close reader thread \n")
                        time.sleep(0.1)
                        break
                    if not chunk:
                        break  # EOF
                    buffer.extend(chunk)

                    # While we have enough data, push fixed-size chunks
                    while len(buffer) >= buffer_size:
                        #make sure that only integer multiple of 4 bytes are sent
                        aligned_size = (buffer_size // 4) * 4  # enforce multiple of 4 bytes
                        chunk_to_send = bytes(buffer[:aligned_size])
                        assert len(chunk_to_send) % 4 == 0, "Chunk size not aligned!"
                        try:
                            self.chunk_queue.put(chunk_to_send)
                            buffer = buffer[aligned_size:]  # remove from buffer
                        except queue.Full as e:
                            print(f"Queue is full: Dropping chunk or delaying. {e}")

                # Push remainder if there's still clean partial buffer
                if buffer:
                    aligned_tail = (len(buffer) // 4) * 4
                    if aligned_tail > 0:
                        self.chunk_queue.put(bytes(buffer[:aligned_tail]))
                    # Drop the trailing misaligned bytes (shouldn't happen, but be safe)
                    if len(buffer) % 4 != 0:
                        print(f"⚠️ Dropping {len(buffer) % 4} leftover bytes (not 4-byte aligned)")

            except Exception as e:
                print(f"Reader thread error: {e}")
                return()
            finally:
                self.chunk_queue.put(None)
                print(f"reader thread while loop exited, stopix: {self.stopix} \n")
        try:
            self.chunk_queue.put(None)
            print("Reader thread exited.")
        except:
            pass

    def pusher_thread(self):
        """Thread to read data from the queue and push it to the STEMLAB socket.
        """
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"], "QMAINWINDOWparent": self.m["QMAINWINDOWparent"]}
        sampling_rate = configuration["irate"]
        __tdelay = self.DATABLOCKSIZE/sampling_rate/4
        MONI = False
        #__tdelay = 0.1
        
        if not self.get_TEST():
            try:
                while True: #and not self.stopix:
                    #TODO TODO TODO: check for qsize and send only self.DATABLOCKSIZE byte, i.e. run get only if qsize is >= self.DATABLOCKSIZE
                    #in that case only get(self.DATABLOCKSIZE)
                    chunk = self.chunk_queue.get()
                    current_qsize = self.chunk_queue.qsize()
                    if current_qsize > self.qmaxsize/2 and MONI is True:
                        print("⚠️ Queue is running full – producer is too fast or consumer is too slow.")
                    if current_qsize == 0 and MONI is True:
                        print("⚠️ Queue is EMPTY – producer is too slow or consumer is too fast.")
                    elif current_qsize < 5 and MONI is True:
                        print(f"⚠️ Queue running low: {current_qsize} items remaining.")
                    #if chunk is None:
                    if chunk is None or len(chunk) == 0: ########FIX CHATGPT 19-07-25
                        break  # EOF
                    #print(f"Received chunk of size: {len(chunk)}") 
                    if len(chunk) % 2 != 0:
                        print("🔥 Error: Chunk size not multiple of 2!")
                    #samples = np.frombuffer(chunk, dtype=np.float32).tolist()
                    assert len(chunk) % 4 == 0, "Pusher thread error: Chunk size not aligned!"
                    if len(chunk) % 4 != 0:
                        # Log, drop, or attempt recovery
                        continue
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    #print(f"type of samples: {type(samples)}")
                    #gain*data[0:size].astype(np.int16)/normfactor
                    # self.stemlabcontrol.data_sock.send(
                    #                         gain*data[0:size].astype(np.float32)
                    #                         /normfactor)  # send next DATABLOCKSIZE samples
                    try:
                        #self.stemlabcontrol.data_sock.send(self.gain*samples.astype(np.float32)/self.normfactor)  # send next DATABLOCKSIZE samples
                        packet = (self.gain * samples.astype(np.float32) / self.normfactor).astype(np.float32).tobytes() #########FIX CHATGPT 19-07-25 TRANSFERRED
                        self.stemlabcontrol.data_sock.sendall(packet)

                    except BlockingIOError:
                        print("Blocking data socket error in playloop worker")
                        time.sleep(0.1)
                        self.SigError.emit("Blocking data socket error in playloop worker")
                        #self.SigFinished.emit()
                        time.sleep(0.1)
                        return
                    except ConnectionResetError:
                        print("Diagnostic Message: Connection data socket error in playloop worker/pusher thread")
                        time.sleep(0.00001)
                        self.SigError.emit("Diagnostic Message: Connection data socket error in playloop worker/pusher thread")
                        #self.SigFinished.emit()
                        time.sleep(0.00001)
                        return
                    if self.monitoring:
                        #print("send data for monitoring from pusherthread")
                        self.set_data(samples.copy())
                        self.monitoring = False
                        print(f"self.gain/self.normfactor: {self.gain/self.normfactor}, IQ_factor: {self.IQfilegain}")
                    #self.ffmpeg_process.stdout.flush()
            except Exception as e:
                print(f"Pusher thread error: {e}; check if you are in TEST mode; no SDR connected ?")
                self.SigError.emit(f"Pusher thread error: {e}; check if you are in TEST mode; no SDR connected ?")
            finally:
                print(f"pusher thread while loop exited in if, stopix: {self.stopix}")
        else:
            try:
                while True:# and not self.stopix:
                    current_qsize = self.chunk_queue.qsize()
                    #TODO TODO TODO: check for qsize and send only self.DATABLOCKSIZE byte, i.e. run get only if qsize is >= self.DATABLOCKSIZE
                    #in that case only get(self.DATABLOCKSIZE)
                    chunk = self.chunk_queue.get()
                    if current_qsize > 50 and MONI is True:
                        print("⚠️ Queue is running full – producer is too fast or consumer is too slow.")
                    if current_qsize == 0:
                        print("⚠️ Queue is EMPTY – producer is too slow or consumer is too fast.")
                    elif current_qsize < 5 and MONI is True:
                        print(f"⚠️ Queue running low: {current_qsize} items remaining.")
                    #if chunk is None:
                    if chunk is None or len(chunk) == 0: ########FIX CHATGPT 19-07-25
                        break  # EOF
                    #print(f"Received chunk of size: {len(chunk)}") 
                    if len(chunk) % 2 != 0:
                        print("🔥 Error: Chunk size not multiple of 2!")
                    #samples = np.frombuffer(chunk, dtype=np.float32).tolist()
                    assert len(chunk) % 4 == 0, "Pusher thread error: Chunk size not aligned!"
                    if len(chunk) % 4 != 0:
                        # Log, drop, or attempt recovery
                        continue
                    samples = np.frombuffer(chunk, dtype=np.int16)

                    #print(f"dummy delay of {__tdelay} = DATABLOCKSIZE/bytes_per_second, for simulating socket write")
                    time.sleep(__tdelay)  # Simulate processing delay, if needed
#######################

                    # chunk = self.chunk_queue.get()
                    # if chunk is None:
                    #     break  # EOF
                    # samples = np.frombuffer(chunk, dtype=np.int16)
                    #print(f"type of samples: {type(samples)}")
                    #print(f"20 first testsamples: {self.gain*samples[0:20].astype(np.float32)/self.normfactor}")
                    if self.monitoring:
                        #print("send data for monitoring from pusherthread")
                        self.set_data(samples.copy())
                        self.monitoring = False
                    #self.ffmpeg_process.stdout.flush()
            except:
                print("Pusher thread error: probably no data received from pipe")
                #self.SigError.emit("Pusher thread error: probably no data received from pipe")
            finally:
                print(f"pusher thread while loop exited in else, stopix: {self.stopix}")


    def gen_ffmpeg_cmd_LINUX(self, ffmpeg_path, sampling_rate = 1250000 , target_lo_shift = 10000, preset_volume = 1, audiosource = ""):
        """generates LINUX variant of ffmpeg command for reading from stdin, complex modulation to target RF band
        and writing to stdout.

        :param ffmpeg_path: path to the ffmpeg executable
        :type ffmpeg_path: str
        :param SRAdalm: effective Sampling rate of transfer to the ADALM2000
        :type SRDdalm: int
        :param sampling_rate: sampling rate of the IQ file to be processed
        :type sampling_rate: int
        :param target_lo_shift: local oscillator shift for streamingaudio target frequency
        :type lo_shift: int
        :param preset_volume: preset volume level
        :type preset_volume: int        
        :return: ffmpeg command as a list of strings
        :rtype: list[str]
        """
        formatstring = "s16le"
        modulation_depth = 0.8 #TODO: Potentially make configurable in future versions
        a = (np.tan(np.pi * target_lo_shift / sampling_rate) - 1) / (np.tan(np.pi * target_lo_shift / sampling_rate) + 1)
        sinus_sign = np.sign(target_lo_shift)  
        pregain = 10 * self.get_gain() #TODO: check if this is still reasonable
        ########TODO: TEST Nullsetzen Audiosignal
        pregain = 5

        ffmpeg_cmd1 = [
            os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
            "-thread_queue_size", "512", "-i", audiosource # TODO: replace by streaming audio source

        ]
        #FIX CHATGPT 19-07-25 :::
        mixterm = "[outre][outim]amerge=inputs=2[merged];[merged]volume=volume=1[merged1];[1:a]afifo[pipe_input];[pipe_input][merged1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
        mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]afifo[pipe_input];[pipe_input]volume=volume=" + str(10 - pregain) + "[merged1];[merged1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"

        ffmpeg_cmd2 = [
            "-filter_complex",
            # FILTERCHAIN
            # 1. Downmix zu Mono, Resampling, Normalisierung
            "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) + #FIX CHATGPT 19-07-25
            ",afifo[resampled];" + "[resampled]" + #FIX CHATGPT 19-07-25
            #",pan=mono|c0=.5*c0+.5*c1" +
            "pan=mono|c0=.5*c0+.5*c1" + #FIX CHATGPT 19-07-25
            ",volume=1.0" +
            "[mono_lp];"
            # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
            "sine=frequency=" + str(abs(target_lo_shift)) + ":sample_rate=" + str(sampling_rate) + "[sine_base];"
            "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
            "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
            ##DEBUG##"[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
            "[sine_sin_raw]asplit=2[sine_sin][carrier_sin];"
            "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
            ##DEBUG##"[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
            "[sine_cos_base]asplit=2[sine_cos][carrier_cos];"
            # # 3. Modulation (1 + modulation_factor * Y)
            # modulation part:
            "[mono_lp]volume=volume=" + str(modulation_depth) + "[modsig];"
            "[modsig]asplit=2[modsig1][modsig2];"
            "[modsig1][sine_cos]amultiply[mod_re_component];"
            "[modsig2][sine_sin]amultiply[mod_im_component];"
            # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

            "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
            "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
            ##DEBUG##"[carrier_cos_deb]anullsink;"
            ##DEBUG##"[carrier_sin_deb]anullsink;"
            # 5. apply Pregain anwenden
            "[modre]volume=volume=" + str(pregain) + "[outre];"
            "[modim]volume=volume=" + str(pregain) + "[outim];" + str(mixterm)
        ]

        ffmpeg_cmd3 = [       
            #"-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
            #DEBUG LINES
            #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"
        ]
   
        #########FIX CHATGPT 19-07-25 TRANSFERRED
        ffmpeg_inta = ["-thread_queue_size", "512", "-analyzeduration", "0", "-probesize", "32", "-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"]
        ffmpeg_intb = ["-map", "[udated_iq_out]"
        ]
        ffmpeg_cmd = ffmpeg_cmd1+ ffmpeg_inta + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

        return ffmpeg_cmd
    
    def gen_ffmpeg_cmd(self, ffmpeg_path, sampling_rate = 1250000 , target_lo_shift = 10000, preset_volume = 1, audiosource = ""):
        """generates ffmpeg command for reading from stdin, complex modulation to target RF band
        and writing to stdout.

        :param ffmpeg_path: path to the ffmpeg executable
        :type ffmpeg_path: str
        :param SRAdalm: effective Sampling rate of transfer to the ADALM2000
        :type SRDdalm: int
        :param sampling_rate: sampling rate of the IQ file to be processed
        :type sampling_rate: int
        :param target_lo_shift: local oscillator shift for streamingaudio target frequency
        :type lo_shift: int
        :param preset_volume: preset volume level
        :type preset_volume: int        
        :return: ffmpeg command as a list of strings
        :rtype: list[str]
        """
        OLDVERSION = False
        formatstring = "s16le"
        modulation_depth = 0.8 #TODO: Potentially make configurable in future versions
        a = (np.tan(np.pi * target_lo_shift / sampling_rate) - 1) / (np.tan(np.pi * target_lo_shift / sampling_rate) + 1)
        sinus_sign = np.sign(target_lo_shift)  
        pregain = 10 * self.get_gain() #TODO: check if this is still reasonable
        ########TODO: TEST Nullsetzen Audiosignal
        pregain = 8

        # ffmpeg_cmd1 = [
        #     os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
        #     "-ss", "0", "-i", audiosource # TODO: replace by streaming audio source
        # ]

        if OLDVERSION:
            ffmpeg_cmd1 = [
                os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
                "-thread_queue_size", "512", "-i", audiosource # TODO: replace by streaming audio source
            ]
            ffmpeg_inta = ["-thread_queue_size", "512", "-analyzeduration", "0", "-probesize", "32", "-fflags", "nobuffer", "-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"]
            mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]volume=volume=" + str(10 - pregain) + "[merged1];[merged1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
            ffmpeg_cmd2 = [
                "-filter_complex",
                # FILTERCHAIN
                # 1. Downmix zu Mono, Resampling, Normalisierung
                "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) + ":async=1"
    #            "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) +
                ",pan=mono|c0=.5*c0+.5*c1" +
                ",volume=1.0" +
                "[mono_lp];"
                # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
                "sine=frequency=" + str(abs(target_lo_shift)) + ":sample_rate=" + str(sampling_rate) + "[sine_base];"
                "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
                "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
                ##DEBUG##"[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
                "[sine_sin_raw]asplit=2[sine_sin][carrier_sin];"
                "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
                ##DEBUG##"[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
                "[sine_cos_base]asplit=2[sine_cos][carrier_cos];"
                # # 3. Modulation (1 + modulation_factor * Y)
                # modulation part:
                "[mono_lp]volume=volume=" + str(modulation_depth) + "[modsig];"
                "[modsig]asplit=2[modsig1][modsig2];"
                "[modsig1][sine_cos]amultiply[mod_re_component];"
                "[modsig2][sine_sin]amultiply[mod_im_component];"
                # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

                "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
                "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
                ##DEBUG##"[carrier_cos_deb]anullsink;"
                ##DEBUG##"[carrier_sin_deb]anullsink;"
                # 5. apply Pregain anwenden
                "[modre]volume=volume=" + str(pregain) + "[outre];"
                "[modim]volume=volume=" + str(pregain) + "[outim];" + str(mixterm)
            ]
        else:
            #alternative with interchanged order of the input streams:
            ffmpeg_cmd1 = [
                os.path.join(ffmpeg_path, "ffmpeg"), "-y",
                "-thread_queue_size", "512", "-analyzeduration", "0", "-probesize", "32", "-fflags", "nobuffer",
                "-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"
            ]
            ffmpeg_inta = ["-thread_queue_size", "512", "-i", audiosource]
            mixterm = "[outre][outim]amerge=inputs=2[merged];[0:a]volume=volume=" + str(10 - pregain) + "[merged1];[merged1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
            ffmpeg_cmd2 = [
                "-filter_complex",
                # FILTERCHAIN
                # 1. Downmix zu Mono, Resampling, Normalisierung
                "[1:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) + ":async=1"
    #            "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) +
                ",pan=mono|c0=.5*c0+.5*c1" +
                ",volume=1.0" +
                "[mono_lp];"
                # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
                "sine=frequency=" + str(abs(target_lo_shift)) + ":sample_rate=" + str(sampling_rate) + "[sine_base];"
                "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
                "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
                ##DEBUG##"[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
                "[sine_sin_raw]asplit=2[sine_sin][carrier_sin];"
                "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
                ##DEBUG##"[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
                "[sine_cos_base]asplit=2[sine_cos][carrier_cos];"
                # # 3. Modulation (1 + modulation_factor * Y)
                # modulation part:
                "[mono_lp]volume=volume=" + str(modulation_depth) + "[modsig];"
                "[modsig]asplit=2[modsig1][modsig2];"
                "[modsig1][sine_cos]amultiply[mod_re_component];"
                "[modsig2][sine_sin]amultiply[mod_im_component];"
                # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

                "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
                "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
                ##DEBUG##"[carrier_cos_deb]anullsink;"
                ##DEBUG##"[carrier_sin_deb]anullsink;"
                # 5. apply Pregain anwenden
                "[modre]volume=volume=" + str(pregain) + "[outre];"
                "[modim]volume=volume=" + str(pregain) + "[outim];" + str(mixterm)
            ]


        ffmpeg_cmd3 = [       
            #"-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"
            "-c:a", "pcm_s16le",  '-flush_packets', '1', "-f", "s16le", "pipe:1"
            #DEBUG LINES
            #"-map", "[mod_debug_stereo]", "-c:a", "pcm_s16le", "-f", "wav", "debug_modre_modim.wav"
        ]
   
        #ffmpeg_inta = ["-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"]

        ffmpeg_intb = ["-map", "[udated_iq_out]"
        ]
        ffmpeg_cmd = ffmpeg_cmd1+ ffmpeg_inta + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

        return ffmpeg_cmd

    def gen_ffmpeg_cmd_onlycarrier(self, ffmpeg_path, sampling_rate = 1250000 , target_lo_shift = 10000, preset_volume = 1, audiosource = ""):
        """generates ffmpeg command for reading from stdin, complex modulation to target RF band
        and writing to stdout.

        :param ffmpeg_path: path to the ffmpeg executable
        :type ffmpeg_path: str
        :param SRAdalm: effective Sampling rate of transfer to the ADALM2000
        :type SRDdalm: int
        :param sampling_rate: sampling rate of the IQ file to be processed
        :type sampling_rate: int
        :param target_lo_shift: local oscillator shift for streamingaudio target frequency
        :type lo_shift: int
        :param preset_volume: preset volume level
        :type preset_volume: int        
        :return: ffmpeg command as a list of strings
        :rtype: list[str]
        """
        modulation_depth = 0.8 #TODO: Potentially make configurable in future versions
        a = (np.tan(np.pi * target_lo_shift / sampling_rate) - 1) / (np.tan(np.pi * target_lo_shift / sampling_rate) + 1)
        sinus_sign = np.sign(target_lo_shift)  

        ffmpeg_cmd1 = [
            os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
            "-thread_queue_size", "512", "-i", audiosource # TODO: replace by streaming audio source
        ]
        mixterm = "[outre][outim]amerge=inputs=2[udated_iq_out]"
        ffmpeg_cmd2 = [
            "-filter_complex",
            # FILTERCHAIN
            # 1. Downmix zu Mono, Resampling, Normalisierung
            "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) + ":async=1"
#            "[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) +
            ",pan=mono|c0=.5*c0+.5*c1" +
            ",volume=1.0" +
            "[mono_lp];"
            # 2. Sinus-Generator, Cosinus über Allpassfilter (biquad)
            "sine=frequency=" + str(abs(target_lo_shift)) + ":sample_rate=" + str(sampling_rate) + "[sine_base];"
            "[sine_base]asplit=2[sine_for_sin][sine_for_cos];"
            "[sine_for_sin]volume=volume=" + str(sinus_sign) + "[sine_sin_raw];"
            ##DEBUG##"[sine_sin_raw]asplit=3[sine_sin][carrier_sin][carrier_sin_deb];"
            "[sine_sin_raw]asplit=2[sine_sin][carrier_sin];"
            "[sine_for_cos]biquad=b0=" + str(a) + ":b1=1:b2=0:a0=1:a1=" + str(a) + ":a2=0[sine_cos_base];"
            ##DEBUG##"[sine_cos_base]asplit=3[sine_cos][carrier_cos][carrier_cos_deb];"
            "[sine_cos_base]asplit=2[sine_cos][carrier_cos];"
            # # 3. Modulation (1 + modulation_factor * Y)
            # modulation part:
            "[mono_lp]volume=volume=" + str(modulation_depth) + "[modsig];"
            "[modsig]asplit=2[modsig1][modsig2];"
            "[modsig1][sine_cos]amultiply[mod_re_component];"
            "[modsig2][sine_sin]amultiply[mod_im_component];"
            # 4. Add carrier part = sin/cos-Anteil (1 * sin(t) bzw. 1 * cos(t))

            "[mod_re_component][carrier_cos]amix=inputs=2:duration=shortest[modre];"
            "[mod_im_component][carrier_sin]amix=inputs=2:duration=shortest[modim];"
            ##DEBUG##"[carrier_cos_deb]anullsink;"
            ##DEBUG##"[carrier_sin_deb]anullsink;"
            # 5. apply Pregain anwenden
            "[modre]volume=volume=" + str(1) + "[outre];"
            "[modim]volume=volume=" + str(1) + "[outim];" + str(mixterm)
        ]

        ffmpeg_cmd3 = [       
            #"-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"
            "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
        ]
   
        ffmpeg_intb = ["-map", "[udated_iq_out]"
        ]
        ffmpeg_cmd = ffmpeg_cmd1 + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

        return ffmpeg_cmd

    def dialog_handler(self, value):
        """Handler for managing values transferred via a Signal SigRelay with argument 'value' to which the worker is connected.
        SigRelay is sent by the related SDR_control instance when receiving a signal from the control dialog.
        In this special driver the value is the gain value from the slider in the control dialog and has type int.
        --> Updates the IQgain value in the playloop.
        :param value: here: The new gain value from the slider
        :type value: int
        :return: none
        """
        #self.set_gain(value)
        print("************+++++++++++++++++++++++++++++++++++++++++**************")
        print("************+++++++++++++++++++++++++++++++++++++++++**************")
        print("************+++++++++++++++++++++++++++++++++++++++++**************")
        
        print(f"########>>>>>>>>>>>>>>>>>>><<<<<<<<<<<<<<<############### Dialog slider handler called with value: {value}")
        self.IQfilegain = value/100# int(np.ceil(value))

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
        #m.["Mainwindowreference"] müsste übergeben werden, um hier einen Dialog aufzubauen

        configuration = self.get_configparameters()
        #print(f"configuration dialog-ref: {configuration['SDR_control_returns']['dialog_ref']}, Slider Signal ref: {configuration['SDR_control_returns']['dialog_ref'].SigSlidergain}")
        #configuration["SDR_control_returns"]["dialog_ref"].SigSlidergain.connect(self.dialog_handler)
        #configuration["SDR_control_returns"]["dialog_ref"].Testbutton_handler()

        print("****************************************************************************")
        print("****************************************************************************")
        print("****************************************************************************")


        time.sleep(0.1)
        filenames = self.get_filename()
        timescaler = self.get_timescaler()
        TEST = self.get_TEST()
        gain = self.get_gain()
        #TODO: self.fmtscl = self.__slots__[7] #scaler for data format      ? not used so far  
        self.stopix = False
        self.set_fileclose(False)
        system = platform.system().lower()
        # ======================= get formatstring and preset volume ========================
        format = self.get_formattag()
        #system = platform.system().lower()
        ffmpeg_path = self.ffmpeg_path
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"], "QMAINWINDOWparent": self.m["QMAINWINDOWparent"]}
        sampling_rate = configuration["irate"]
        #lo_shift = configuration["ifreq"]# - configuration["LO_offset"]
        #QMAINWINDOWparent = configuration["QMAINWINDOWparent"]
        standardpath = os.getcwd()  #TODO TODO: take from core module via rxh; on file open core sets that to:
        ##################### generate dictionary of input fields for dialogue; their values contain the values asked for
        target_lo_shift = configuration["SDR_control_returns"]["target_lo_shift"]# 200000
        target_lo_shift += configuration["ifreq"] #
        #TODO: validation should be done already in dialogue treatment in SDR_control
        print(f"target_lo_shift from config: {target_lo_shift}, type: {type(target_lo_shift)}")
        target_lo_shift = int(target_lo_shift)  # ensure it is an integer
        time.sleep(0.5)

        audiosource = configuration["SDR_control_returns"]["source"]
        print(f"Audio filename from dialogue: {audiosource}")
        #audiosource = file_name #TODO: adapt to actual needs
        preset_volume = 50 #TODO:adapt to actual needs
        #checkk how to set preset_volume
        #========================== generate ffmpeg command and start ffmpeg subprocess ==========================
        try:
            if system == "linux":
                ffmpeg_cmd = self.gen_ffmpeg_cmd_LINUX(ffmpeg_path, sampling_rate , target_lo_shift , preset_volume, audiosource)
            elif system == "windows":
                ffmpeg_cmd = self.gen_ffmpeg_cmd(ffmpeg_path, sampling_rate , target_lo_shift , preset_volume, audiosource)
                #ffmpeg_cmd = self.gen_ffmpeg_cmd_onlycarrier(ffmpeg_path, 250000 , target_lo_shift , preset_volume, audiosource)
            else:
                print("This OS is not being supported, playback is being abortet")

                return()
            print(f"<<<<<<<<<<<<<<< stemlab125 stream: ffmpeg_command: {ffmpeg_cmd}")
            # start ffmpeg Process
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                creationflags=subprocess.HIGH_PRIORITY_CLASS if system == "windows" else 0,
                bufsize=0
            )
            self.ffmpeg_process = ffmpeg_process
            #print(f"<<<<<<<<<<<<<<< stemlab125 stream: ffmpeg_command: {ffmpeg_cmd}")
        except FileNotFoundError:
            print(f"Input file not found, probably ffmpeg path is wrong")
            if not TEST:
                pass #TODO: check if exit closing (maybe of the socket) is necessary
            return()
        except subprocess.SubprocessError as e:
            print(f"Error when executing ADALM ffmpeg: {e}")
            if not TEST:
                pass #TODO: check if exit closing (maybe of the socket) is necessary
            return()    
        except Exception as e:
            print(f"Unexpected error: {e}")
            if not TEST:
                pass #TODO: check if exit closing (maybe of the socket) is necessary
            return()    

        #================================ start reader and pusher threads ================
#        print(f"datablocksize: {self.DATABLOCKSIZE} formatstring: {formatstring} gain: {gain}")
        reader = threading.Thread(target=self.pipe_reader_thread, args=(ffmpeg_process.stdout, self.DATABLOCKSIZE))
        reader.start()
        pusher = threading.Thread(target=self.pusher_thread, args=())
        pusher.start()

        #=============================== loop through files in filelist and send data to stdin of ffmpeg ================
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
            self.monitoring = False
            if self.stopix:
                print("playrecworker playloop stopix found")
            while size > 0 and not self.stopix:
                if not TEST:
                    if not self.get_pause():
                        try:
                            #ffmpeg_process.stdin.write(aux1.astype(np.int16))
                            self.gain = gain
                            self.normfactor = normfactor
                            #ffmpeg_process.stdin.write(self.IQfilegain*data[0:size].astype(np.int16))
                            data_float = data[0:size].astype(np.float32)
                            scaled_data = self.IQfilegain * data_float
                            #ffmpeg_process.stdin.write(self.IQfilegain*data[0:size].astype(np.int16).tobytes())
                            ffmpeg_process.stdin.write(np.clip(np.rint(scaled_data), -32768, 32767).astype(np.int16).tobytes())
                            #time.sleep(self.DATABLOCKSIZE / (8 * sampling_rate))
                            #ffmpeg_process.stdin.write(int(np.ceil(self.IQfilegain/100*data[0:size])).astype(np.int16).tobytes()) ########FIX CHATGPT 19-07-25

                            ###TODO: formatanpassung bei f32
                            ########### TODO TODO TODO carry over to pusher thread
                            # self.stemlabcontrol.data_sock.send(
                            #                         gain*data[0:size].astype(np.float32)
                            #                         /normfactor)  # send next DATABLOCKSIZE samples
                            ######################################
                            #ffmpeg_process.stdin.flush()
                        except Exception as e:
                            print("Class e type error  data socket error in playloop worker")
                            print(e)
                            time.sleep(0.1)
                            self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
                            #self.SigFinished.emit() #TODO TODO TODO CHECK
                            time.sleep(0.1)
                            return
                        if format[2] == 16 or format[2] == 32:
                            size = fileHandle.readinto(data)
                        elif format[2] == 24:
                            data = self.read24(format,data,fileHandle)
                            size = len(data)

                        #  read next 2048 samples
                        count += 1
                        if count > junkspersecond/2:
                            self.SigIncrementCurTime.emit()
                            self.monitoring = True
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
                            print("play_loop_filelist: stopix is True, break")
                            break
                else:
                    if not self.get_pause():
                        try:
                            #ffmpeg_process.stdin.write(aux1.astype(np.int16))
                            self.gain = gain
                            self.normfactor = normfactor
                            data_float = data[0:size].astype(np.float32)
                            scaled_data = self.IQfilegain * data_float
                            #ffmpeg_process.stdin.write(self.IQfilegain*data[0:size].astype(np.int16).tobytes())
                            ffmpeg_process.stdin.write(np.clip(np.rint(scaled_data), -32768, 32767).astype(np.int16).tobytes())
                            #                            #ffmpeg_process.stdin.write(self.IQfilegain*data[0:size].astype(np.float32).tobytes())
                            #ffmpeg_process.stdin.write(int(np.ceil(self.IQfilegain/100*data[0:size])).astype(np.int16).tobytes()) ########FIX CHATGPT 19-07-25

                        except Exception as e:
                            print("Class e type error  data socket error in playloop worker")
                            print(e)
                            time.sleep(0.1)
                            self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
                            #self.SigFinished.emit() #TODO TODO TODO CHECK
                            time.sleep(0.1)
                            return

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
                        if count > junkspersecond/2 and size > 0:
                            #print('timeincrement reached')
                            self.monitoring = True
                            self.SigIncrementCurTime.emit()
                            gain = self.get_gain()
                            #print(f"diagnostic: gain in worker: {gain}, IQgain: {self.IQfilegain}")
                            #print(f"maximum: {np.max(data)}")
                            #self.set_data(gain*data)
                            ############################# TODO TEST: self.set_data(data)
                            count = 0
                    else:
                        time.sleep(1)
                        if self.stopix is True:
                            print("play_loop_filelist: stopix is True, break")
                            break
            print("close filehandle in cohi_playrecworker-->play_loop_filelist")
            ffmpeg_process.stdin.flush()
            self.set_fileclose(True)
            fileHandle.close()
            #TODO TODO TODO: shift closing of control dialog to playrec loop management via signalling
            # print("close file list in cohi_playrecworker-->play_loop_filelist, do reader.join(), pusher.join()")
            # configuration["SDR_control_returns"]["dialog_ref"].SigSlidergain.disconnect(self.dialog_handler)
            # configuration["SDR_control_returns"]["dialog_ref"].close() # close the input dialogue
            # try:
            #     self.set_fileclose(True)
            #     fileHandle.close()
            # except:
            #     pass
        print("close all processes in cohi_playrecworker-->play_loop_filelist")
        #self.mutex.lock()
        ffmpeg_process.stdin.flush()
        ffmpeg_process.stdout.flush()
        ffmpeg_process.stdin.close()  # close stdin
        ffmpeg_process.stdout.close()  # close stdout
        print("close reached")
        ffmpeg_process.wait()  # wait for process termination
        print("wait reached")
        reader.join()
        print("join reader")
        pusher.join()
        print("join pusher")
        #ffmpeg_process.stdout.close()  # close stdout
        print("stdout closed")
        ffmpeg_process.kill()  # stop process gently
        print(f"check closing ffmpeg poll: {ffmpeg_process.poll()}")
        #self.mutex.unlock()
            #self.set_fileclose(True)
        while ffmpeg_process.poll() is None:
            print(f"trying to close ffmpeg process, poll: {ffmpeg_process.poll()}")
            time.sleep(0.5)
        print('worker  thread finished')
        # try:
        #     configuration["SDR_control_returns"]["dialog_ref"].SigSlidergain.disconnect(self.dialog_handler)
        # except:
        #     print("cannot disconnect Slidergain, dialogref: {configuration['SDR_control_returns']['dialog_ref']}")
        #     pass
        # try:
        #     print(f"closing dialog_ref: {configuration['SDR_control_returns']['dialog_ref']}")
        #     configuration["SDR_control_returns"]["dialog_ref"].close() # close the input dialogue
        # except:
        #     print(f"cannot close dialog_ref: {configuration['SDR_control_returns']['dialog_ref']}")     
        self.stopix is False
        print("playrecworker: play_loop_filelist finished, setting fileclose to True")
        self.SigFinished.emit()
        print("SigFinished from playloop emitted")

    def stop_loop(self):
        print("playrecworker: stop_loop stopix is being set")
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
        self.stopix is False