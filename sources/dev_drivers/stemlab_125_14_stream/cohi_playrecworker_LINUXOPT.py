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

class TextInputDialog(QDialog):
    def __init__(self, parent=None, *args, **kwargs):
        super(TextInputDialog, self).__init__(parent)

        self.setWindowTitle("Input dialogue")
        if len(args) > 0:
            self.inputfields = args[0]

        layout = QVBoxLayout()

        # Eingabefelder
        for key, value in self.inputfields.items():
            setattr(self, f'line_edit_{key}', QLineEdit(self))
            getattr(self, f'line_edit_{key}').setText(str(value))
            layout.addWidget(QLabel(f"{key}:"))
            layout.addWidget(getattr(self, f'line_edit_{key}'))
        # self.line_edit1 = QLineEdit(self)
        # self.line_edit2 = QLineEdit(self)

        # Buttons
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)

        # Layouts
#        layout.addWidget(QLabel("carier freqency:"))
#        layout.addWidget(self.line_edit1)

 #       layout.addWidget(QLabel("Eingabe 2:"))
 #       layout.addWidget(self.line_edit2)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Signals
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def getInputs(self):

        """Returns the text from the input fields."""
        # return self.line_edit1.text(), self.line_edit2.text()
        for key in self.inputfields.keys():
            line_edit = getattr(self, f'line_edit_{key}', None)
            if line_edit:
                self.inputfields[key] = line_edit.text()
        return self.inputfields

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
        self.JUNKSIZE = 2048*4
        self.DATABLOCKSIZE = 1024*4
        self.mutex = QMutex()
        self.stemlabcontrol = stemlabcontrolinst

        self.output_chunks = []
        self.chunk_queue = queue.Queue(maxsize=50)  # Buffer size = 10 blocks
        configpath = os.path.join(os.getcwd(), "config_wizard.yaml")
        try:
            stream = open(configpath, "r")
            metadata = yaml.safe_load(stream)
            stream.close()
            self.ffmpeg_path = metadata["ffmpeg_path"]
        except FileNotFoundError:
            print(f"cohi_playrecworker initialization failed: Configuration file {configpath} not found, using default ffmpeg path")
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

    # def _read_exact(self, pipe, size): ########FIX CHATGPT 19-07-25

    #     buffer = bytearray()
    #     while len(buffer) < size:
    #         part = pipe.read(size - len(buffer))
    #         if not part:
    #             break
    #         buffer.extend(part)
    #     return bytes(buffer) if buffer else None

    def pipe_reader_thread(self, stdout_pipe, buffer_size):
        try:
            buffer = bytearray()
            while True:
                chunk = stdout_pipe.read(buffer_size - len(buffer)) #TRANSFERRED
                if not chunk:
                    break  # EOF
                buffer.extend(chunk)

                # While we have enough data, push fixed-size chunks
                while len(buffer) >= buffer_size:
                    self.chunk_queue.put(bytes(buffer[:buffer_size]))  # safe slice
                    buffer = buffer[buffer_size:]  # remove sent chunk

            # Push remainder if there's still clean partial buffer
            if len(buffer) > 0 and len(buffer) % 2 == 0:
                self.chunk_queue.put(bytes(buffer))

        except Exception as e:
            print(f"Reader thread error: {e}")
        finally:
            self.chunk_queue.put(None)

    # def pipe_reader_thread(self, stdout_pipe, buffer_size):
    #     """Thread to read data from stdout_pipe and put it into a queue.
    #     :param stdout_pipe: Pipe to read data from
    #     :type stdout_pipe: file-like object
    #     :param buffer_size: Size of the buffer to read from the pipe
    #     :type buffer_size: int
    #     """
    #     try:
    #         while True:
    #             #chunk = stdout_pipe.read(buffer_size)
    #             chunk = self._read_exact(stdout_pipe, buffer_size) ########FIX CHATGPT 19-07-25

    #             if not chunk:
    #                 break
    #             #self.chunk_queue.put(chunk)  # non-blocking push into queue
    #             try: ########FIX CHATGPT 19-07-25
    #                 self.chunk_queue.put(chunk, timeout=1.0)
    #             except queue.Full:
    #                 print("Reader thread warning: chunk_queue is full; dropping data")
    #                 #Optionally, use put_nowait() to avoid blocking and just drop frames if real-time is critical.  ########FIX CHATGPT 19-07-25
    #     except Exception as e:
    #         print(f"Reader thread cannot read further data, probably EOF: {e}")
    #     finally:
    #         self.chunk_queue.put(None)  # Signal: EOF

    def pusher_thread(self):
        """Thread to read data from the queue and push it to the STEMLAB socket.
        """
        if not self.get_TEST():
            try:
                while True:
                    chunk = self.chunk_queue.get()
                    #if chunk is None:
                    if chunk is None or len(chunk) == 0: ########FIX CHATGPT 19-07-25 TRANSFERRED
                        break  # EOF
                    #print(f"Received chunk of size: {len(chunk)}") 
                    if len(chunk) % 2 != 0:
                        print("🔥 Error: Chunk size not multiple of 2!")
                    #samples = np.frombuffer(chunk, dtype=np.float32).tolist()
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
                    if self.monitoring:
                        #print("send data for monitoring from pusherthread")
                        self.set_data(samples.copy())
                        self.monitoring = False
                    #self.ffmpeg_process.stdout.flush()
            except Exception as e:
                print(f"Pusher thread error: {e}; check if you are in TEST mode; no SDR connected ?")
                self.SigError.emit(f"Pusher thread error: {e}; check if you are in TEST mode; no SDR connected ?")
        else:
            try:
                while True:
                    chunk = self.chunk_queue.get()
                    if chunk is None:
                        break  # EOF
                    samples = np.frombuffer(chunk, dtype=np.int16)
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
            

    # def showDialog(self, Mainwindowreference=None, inputfields=None):
    #     """Shows a dialog to get user input for a number of editable input fields.
    #     The input fields are defined in the inputfields dictionary.
    #     If the dialog is accepted, the values are returned as a dictionary.
    #     :param Mainwindowreference: Reference to the main window for dialog parent
    #     :type Mainwindowreference: QMainWindow
    #     :param inputfields: Dictionary of input fields with their current values
    #     :type inputfields: dict
    #     """
    #     errorstate = False
    #     value = []
    #     dialog = TextInputDialog(Mainwindowreference, inputfields)
    #     if dialog.exec_() == QDialog.Accepted:
    #         # Get the input values from the dialog
    #         value = dialog.getInputs()
    #     else:
    #         errorstate = True

    #     return errorstate, value        

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
        formatstring = "s16le"
        modulation_depth = 0.8 #TODO: Potentially make configurable in future versions
        a = (np.tan(np.pi * target_lo_shift / sampling_rate) - 1) / (np.tan(np.pi * target_lo_shift / sampling_rate) + 1)
        sinus_sign = np.sign(target_lo_shift)  
        pregain = 10 * self.get_gain() #TODO: check if this is still reasonable
        ########TODO: TEST Nullsetzen Audiosignal
        pregain = 5



        # ffmpeg_cmd1 = [
        #     os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
        #     "-ss", "0", "-i", audiosource # TODO: replace by streaming audio source
        # ]

        ffmpeg_cmd1 = [
            os.path.join(ffmpeg_path, "ffmpeg"), "-y", #"-loglevel", "error", "-hide_banner",
            "-thread_queue_size", "512", "-i", audiosource # TODO: replace by streaming audio source

            #########FIX CHATGPT 19-07-25
            #-thread_queue_size 512 TRANSFERRED
        ]
        #mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]highpass=f=1000[filtered_input1];[filtered_input1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
        # mixterm = "[outre][outim]amerge=inputs=2[merged];[merged]volume=volume=1[merged1];[1:a][merged1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
        # mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]volume=volume=" + str(10 - pregain) + "[merged1];[merged1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"

        #FIX CHATGPT 19-07-25 :::
        mixterm = "[outre][outim]amerge=inputs=2[merged];[merged]volume=volume=1[merged1];[1:a]afifo[pipe_input];[pipe_input][merged1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
        mixterm = "[outre][outim]amerge=inputs=2[merged];[1:a]afifo[pipe_input];[pipe_input]volume=volume=" + str(10 - pregain) + "[merged1];[merged1][merged]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[udated_iq_out]"
        #
        #  [0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=1250000,afifo[resampled];
        # [resampled]pan=mono|c0=.5*c0+.5*c1,volume=1.0[mono_lp];

        # [1:a]afifo[pipe_input];
        # [pipe_input]volume=5[merged1];

        ffmpeg_cmd2 = [
            "-filter_complex",
            # FILTERCHAIN
            # 1. Downmix zu Mono, Resampling, Normalisierung
            #"[0:a]aformat=sample_fmts=s16:channel_layouts=stereo,aresample=osr=" + str(sampling_rate) +
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
   
        #ffmpeg_inta = ["-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"] #########FIX CHATGPT 19-07-25 TRANSFERRED
        ffmpeg_inta = ["-thread_queue_size", "512", "-analyzeduration", "0", "-probesize", "32", "-f", "s16le", "-ar",  str(sampling_rate), "-ac",  "2", "-i", "pipe:0"]
        #-thread_queue_size 512 -f s16le -ar 1250000 -ac 2 -i pipe:0
        #-analyzeduration 0 -probesize 32 -f s16le -ar 1250000 -ac 2 -i pipe:0
        ffmpeg_intb = ["-map", "[udated_iq_out]"
        ]
        ffmpeg_cmd = ffmpeg_cmd1+ ffmpeg_inta + ffmpeg_cmd2 + ffmpeg_intb + ffmpeg_cmd3

###############
        # ffmpeg_cmd = [
        #     os.path.join(ffmpeg_path, "ffmpeg"), '-f', 's16le', '-ar', '1250000', '-ac', '2', 
        #     "-i", "pipe:0", "[0:a]highpass=f=1000[filtered_input1]",
        #     "-map", "[filtered_input1]", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"
        # ]

        return ffmpeg_cmd


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

        filenames = self.get_filename()
        timescaler = self.get_timescaler()
        TEST = self.get_TEST()
        gain = self.get_gain()
        #TODO: self.fmtscl = self.__slots__[7] #scaler for data format      ? not used so far  
        self.stopix = False
        self.set_fileclose(False)

        # ======================= get formatstring and preset volume ========================
        format = self.get_formattag()
        #system = platform.system().lower()
        ffmpeg_path = self.ffmpeg_path
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"], "QMAINWINDOWparent": self.m["QMAINWINDOWparent"]}
        sampling_rate = configuration["irate"]
        lo_shift = configuration["ifreq"]# - configuration["LO_offset"]
        #QMAINWINDOWparent = configuration["QMAINWINDOWparent"]
        filters = "audio files (*.wav, *.mp3);;all files (*)"
        selected_filter = "audio files (*.wav, *.mp3)"
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog  # Verwende das Qt-eigene Dialogfenster
        standardpath = os.getcwd()  #TODO TODO: take from core module via rxh; on file open core sets that to:
        ################TODO: Dialogue query for getting target frequency
        #target_lo_shift = 100000 #TODO: calculate reasonable value from targetfrequency and lo_shift
        ##################### generate dictionary of input fields for dialogue; their values contain the values asked for
        #self.mutex.lock()
        target_lo_shift = configuration["SDR_control_returns"]["target_lo_shift"]# 200000
        #TODO: validation should be done already in dialogue treatment in SDR_control
        print(f"target_lo_shift from config: {target_lo_shift}, type: {type(target_lo_shift)}")
        target_lo_shift = int(target_lo_shift)  # ensure it is an integer
        # inputfields = {
        #     "target_lo_shift": target_lo_shift
        # }
        # errorstate, inputvalues = self.showDialog(QMAINWINDOWparent, inputfields)
        # if not errorstate:
        #     try:
        #         target_lo_shift = int(inputvalues["target_lo_shift"])
        #     except ValueError:
        #         print(f"Invalid input for target LO shift: {inputvalues['target_lo_shift']}")
        #         self.SigError.emit(f"Invalid input for target LO shift: {inputvalues['target_lo_shift']}")
        #         return
        # print(f"target_lo_shift from inoutdialog: {target_lo_shift}, mutex unlock")
        # self.mutex.unlock()
        time.sleep(0.5)
        #self.mutex.lock()
        #print("mutex lock,query for audio source")
        file_name = "/home/scharfetter/cohiradia/01-So tinha de ser com voce.wav"
        # file_name, _ = QFileDialog.getOpenFileName(QMAINWINDOWparent, 
        #                                         "Open project File", 
        #                                         standardpath,
        #                                         filters,  # Filter für Dateitypen
        #                                         selected_filter,
        #                                         #"all files (*)",
        #                                         options=options)
        #self.mutex.unlock()
        print(f"filename from dialogue: {file_name}")
        audiosource = file_name #TODO: adapt to actual needs
        preset_volume = 10 #TODO:adapt to actual needs
        #checkk how to set preset_volume
        #========================== generate ffmpeg command and start ffmpeg subprocess ==========================
        try:
            ffmpeg_cmd = self.gen_ffmpeg_cmd(ffmpeg_path, sampling_rate , target_lo_shift , preset_volume, audiosource)
            #print(f"<<<<<<<<<<<<<<< stemlab125 stream: ffmpeg_command: {ffmpeg_cmd}")
            # start ffmpeg Process
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT
            )
            self.ffmpeg_process = ffmpeg_process
            print(f"<<<<<<<<<<<<<<< stemlab125 stream: ffmpeg_command: {ffmpeg_cmd}")
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
            while size > 0 and not self.stopix:
                if not TEST:
                    if not self.get_pause():
                        if self.ffmpeg_process.poll() is not None:
                            print("############## ⚠️ ffmpeg process has exited unexpectedly")
                            break
                        else:
                            #print("############# ffmpeg process is alive")
                            pass
                        try:
                            #ffmpeg_process.stdin.write(aux1.astype(np.int16))
                            self.gain = gain
                            self.normfactor = normfactor
                            #ffmpeg_process.stdin.write(data[0:size].astype(np.int16))

                            #print("write to ffmpeg")
                            ffmpeg_process.stdin.write(data[0:size].astype(np.int16).tobytes()) ########FIX CHATGPT 19-07-25 TRANSFERRED



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
                            break
                else:
                    if not self.get_pause():
                        try:
                            #ffmpeg_process.stdin.write(aux1.astype(np.int16))
                            self.gain = gain
                            self.normfactor = normfactor
                            #ffmpeg_process.stdin.write(data[0:size].astype(np.int16))
                            ffmpeg_process.stdin.write(data[0:size].astype(np.int16).tobytes()) ########FIX CHATGPT 19-07-25

                        except Exception as e:
                            print("Class e type error  data socket error in playloop worker")
                            print(e)
                            time.sleep(0.1)
                            self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
                            self.SigFinished.emit()
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
                        if count > junkspersecond and size > 0:
                            print('timeincrement reached')
                            self.monitoring = True
                            self.SigIncrementCurTime.emit()
                            gain = self.get_gain()
                            #print(f"diagnostic: gain in worker: {gain}")
                            #print(f"maximum: {np.max(data)}")
                            #self.set_data(gain*data)
                            ############################# TODO TEST: self.set_data(data)
                            count = 0
                    else:
                        time.sleep(1)
                        if self.stopix is True:
                            break
            print("close filehandle in cohi_playrecworker-->play_loop_filelist")
            self.set_fileclose(True)
            fileHandle.close()
        print("close file list in cohi_playrecworker-->play_loop_filelist, do reader.join(), pusher.join()")
        configuration["SDR_control_returns"]["dialog_ref"].close() # close the input dialogue
        ffmpeg_process.stdin.close()  # close stdin
        reader.join()
        pusher.join()
        ffmpeg_process.stdout.close()  # close stdout

        ffmpeg_process.terminate()  # stop process gently
        ffmpeg_process.wait()  # wait for process termination


            #self.set_fileclose(True)
        print('worker  thread finished')
        self.SigFinished.emit()
        print("SigFinished from playloop emitted")


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