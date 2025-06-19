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

    # def __init__(self, *args,**kwargs):

    #     super().__init__(*args, **kwargs)
    #     self.stopix = False
    #     #self.pausestate = False
    #     self.DATABLOCKSIZE = 1024*4*256
    #     #self.JUNKSIZE = 2*self.DATABLOCKSIZE
    #     self.JUNKSIZE = self.DATABLOCKSIZE
    #     self.mutex = QMutex()
    #     # if len(args) > 0: #TODO: check for more general formulation
    #     #     self.stemlabcontrol = args[0]

    def __init__(self, stemlabcontrolinst,*args,**kwargs):

        super().__init__(*args, **kwargs)
        self.stopix = False
        #self.pausestate = False
        #self.JUNKSIZE = 2048*4
        self.DATABLOCKSIZE = 1024*1*256
        self.DATASHOWSIZE = 1024
        self.JUNKSIZE = self.DATABLOCKSIZE
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



    def send_data_over_tcp(file_path, host="127.0.0.1", port=1234, block_size=1024 * 1024):
        """
        Liest 16-Bit-Integer-Daten aus einer Datei, wandelt sie in 8-Bit signed um,
        und sendet sie blockweise über TCP an fl2k_tcp, falls dieser gestartet ist

        :param file_path: Pfad zur Eingabedatei mit 16-Bit-Integer-Daten.
        :param host: IP-Adresse des fl2k_tcp-Servers (Standard: localhost).
        :param port: Port des fl2k_tcp-Servers (Standard: 1234).
        :param block_size: Größe der Blöcke (in Bytes), die gesendet werden.
        """
        # Verbindung zum fl2k_tcp-Server herstellen
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.connect((host, port))
            print(f"Verbunden mit fl2k_tcp auf {host}:{port}")

            with open(file_path, "rb") as f:
                while True:
                    # Blockweise Daten auslesen
                    data = f.read(block_size)
                    if not data:  # Datei zu Ende gelesen
                        break
                    
                    # 16-Bit-Daten in numpy-Array laden
                    int16_data = np.frombuffer(data, dtype=np.int16)
                    
                    # Umwandlung in 8-Bit signed (clipping bei Überläufen)
                    int8_data = np.clip(int16_data / 256, -128, 127).astype(np.int8)
                    
                    # Daten über TCP senden
                    sock.sendall(int8_data.tobytes())
                    print(f"{len(int8_data)} Bytes gesendet")

            print("Datenübertragung abgeschlossen.")



    def send_data_over_tcp(file_path, host="127.0.0.1", port=1234, block_size=1024 * 1024):
        """
        Liest 16-Bit-Integer-Daten aus einer Datei, wandelt sie in 8-Bit signed um,
        und sendet sie blockweise über TCP an fl2k_tcp, falls dieser gestartet ist

        :param file_path: Pfad zur Eingabedatei mit 16-Bit-Integer-Daten.
        :param host: IP-Adresse des fl2k_tcp-Servers (Standard: localhost).
        :param port: Port des fl2k_tcp-Servers (Standard: 1234).
        :param block_size: Größe der Blöcke (in Bytes), die gesendet werden.
        """
        # Verbindung zum fl2k_tcp-Server herstellen
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.connect((host, port))
            print(f"Verbunden mit fl2k_tcp auf {host}:{port}")

            with open(file_path, "rb") as f:
                while True:
                    # Blockweise Daten auslesen
                    data = f.read(block_size)
                    if not data:  # Datei zu Ende gelesen
                        break
                    
                    # 16-Bit-Daten in numpy-Array laden
                    int16_data = np.frombuffer(data, dtype=np.int16)
                    
                    # Umwandlung in 8-Bit signed (clipping bei Überläufen)
                    int8_data = np.clip(int16_data / 256, -128, 127).astype(np.int8)
                    
                    # Daten über TCP senden
                    sock.sendall(int8_data.tobytes())
                    print(f"{len(int8_data)} Bytes gesendet")

            print("Datenübertragung abgeschlossen.")

            # Man wird das Treiberprogramms fl2k_tcp nehmen können.
            # Ähnlich dem Stemlab kann man hier eine IP und einen Port angeben.

            # "fl2k_tcp, a spectrum client for FL2K VGA dongles\n\n"
            # "Usage:\t[-a server address]\n"
            # "\t[-d device index (default: 0)]\n"
            # "\t[-p port (default: 1234)]\n"
            # "\t[-s samplerate in Hz (default: 100 MS/s)]\n"
            # "\t[-b number of buffers (default: 4)]\n"

            # Bei mir läuft der D\A Wandler über den lokalen USB Bus, daher muss ich die Daten an den lokalen Recher der immer die IP 127.0.0.1 hat senden. Bei der Samplerate wähle ich 10000000 (10MS/s) da 100 MS/s meinen PC überlastet. Mit 10MS/s kommt man bis 5 MHz. Für Aufnahmen des 49m Bandes müsste ich einen höheren Eintrag wählen aber auch das geht. Für Langwelle und Mittelwelle reichen 10MS/s aus. Werte Unter 10 MS/s gibt es nur och einen krummen was beim Resampling womöglich zuviele Zwischenrechnungen verursacht.
            # Das Resampling und verschieben auf die Bandmitte was Gnu Radio macht müsste das Cohiradia Programm selbst erledigen.
            # Eine Datenkonvertierung und Aussteuerung auf 8 Bit Wertebereich ebenfalls. Auch das wird im Moment in Gnu Radio erledigt.



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
        __slots__[9]: file_close
        __slots__[10]: sampling_parameters
        """
        #print("reached playloopthread")
        filenames = self.get_filename()
        timescaler = self.get_timescaler() #bytes per second
        TEST = self.get_TEST()
        gain = self.get_gain()
        #TODO: self.fmtscl = self.__slots__[7] #scaler for data format      ? not used so far  
        self.stopix = False
        self.set_fileclose(False)
        configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        sampling_rate = configuration["irate"] #TODO TODO TODO: check if correctly scaled (true frequ in S/s, not kS/s)
        lo_shift = configuration["LO_offset"] #TODO check if this is really the LO frequency !!!
        # start fl2k_file with reading from stdin
        #TODO TODO: target samplingrate von aussen übernehm,en
        print(f"play_loop_filelist, sampling_rate: {sampling_rate}")
        #sampling_rate = sSR
        fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k/osmo-fl2k-64bit-20250105", "fl2k_file.exe")
        #print(f"cohi_playrecworker fl2k_file_path exists: {os.path.exists(fl2k_file_path)}")
        if not TEST:
            if os.name.find("posix") >= 0:
                try:
                    process = subprocess.Popen(
                        ["fl2k_file", "-s", str(sampling_rate), "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0
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

                try:
                    process = subprocess.Popen(
                        [fl2k_file_path, "-s", str(sampling_rate), "-r", "0", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0
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
            psutil.Process(process.pid).nice(psutil.IDLE_PRIORITY_CLASS)
        else:
            print("fl2k worker TEST condition , no fl2k_file process started <<<<<<<<<<<<<<<<")

        for ix,filename in enumerate(filenames):
            fileHandle = open(filename, 'rb')
            self.SigNextfile.emit(filename)
            self.set_fileHandle(fileHandle)
            format = self.get_formattag()
            data_blocksize = self.DATABLOCKSIZE
            self.set_datablocksize(data_blocksize)
            fileHandle.seek(216, 1)
            data = np.empty(data_blocksize, dtype=np.int8)
            if format[0] == 1:
                normfactor = int(2**int(format[2]-1))-1
            else:
                normfactor = 1
            size = fileHandle.readinto(data)
            #print(f"data fetched, size = {size}")
            self.set_data(data)
            #print(f"filehandle: {fileHandle}")
            junkspersecond = timescaler / self.JUNKSIZE
            count = 0
            # print(f"Junkspersec:{junkspersecond}")
            dt = 1/sampling_rate
            segment_tstart = 0
            while size > 0 and not self.stopix:
                #reftime = time.time() ###DISTINCT
                if not TEST:
                    if not self.get_pause():
                        try:
                            #scale data with gain and normfactor
                            aux1 = gain*data[0:size]/normfactor
                            # Skalieren, damit die Werte in den Bereich von int8 passen (-128 bis 127)
                            scaled_array = np.clip(150*aux1, -128, 127)
                            #print("send junk to fl2k_file")
                            #write aux4 to fl2k_file via stdin
                            process.stdin.write(scaled_array.astype(np.int8))
                            process.stdin.flush()
                            #print("written to stdin")
                            # gain*data[0:size].astype(np.int8)
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
                        QThread.usleep(30) #sleep 30 us for keeping main GUI responsive
                        size = fileHandle.readinto(data)
                        #print(f"data fetched, size = {size}")
                        count += 1
                        if count > junkspersecond:
                            cv = np.zeros(2*self.DATASHOWSIZE)
                            cv[0:2*self.DATASHOWSIZE-1:2] = data[0:self.DATASHOWSIZE] #write only real part
                            self.set_data(cv)
                            #print(f"DATASHOWSIZE: {self.DATASHOWSIZE}")
                            #print("increment emit, modified")
                            #TODO TODO TODO inactivated:check for timing !!!
                            self.SigIncrementCurTime.emit()
                            #Dieser Aufruf blockiert das weitere Streaming immer für einige Zeit
                            count = 0
                            gain = self.get_gain()
                            #self.set_data(data)
                    else:
                        #print("sleep a while")
                        process.stdin.flush()
                        time.sleep(0.1)
                        if self.stopix is True:
                            break
                else:
                    if not self.get_pause():
                        print(" SDR_control fl2k test reached")
                        size = fileHandle.readinto(data)
                        #print("sleep a bit ##########################")
                        #time.sleep(0.0001)
                        #i reality: 
                        time.sleep(self.DATABLOCKSIZE/timescaler)
                        #QThread.usleep(30)
                        #  read next junk
                        count += 1
                        if count > junkspersecond and size > 0:
                            self.set_data(data[0:self.DATASHOWSIZE-1])
                            #print(f"DATASHOWSIZE: {self.DATASHOWSIZE}")
                            self.SigIncrementCurTime.emit()
                            gain = self.get_gain()
                            count = 0
                    else:
                        time.sleep(1)
                        if self.stopix is True:
                            break
                #proc_time = time.time() - reftime ###DISTINCT
                #print(f"process time: {proc_time}")       ###DISTINCT          
        print("close file ")
        self.set_fileclose(True)
        fileHandle.close()

        if not TEST:
            # terminate fl2k_file process and wait for actual termination
            process.stdin.close()
            process.terminate
            while process.poll() == None:

                print("poll and close")
                QThread.msleep(1)
                #time.sleep(1)
            print("close process ")
            
            stdout, stderr = process.communicate() ### TODO TODO TODO: Timeout ???
            # Report result
            print("cohi_playrecworker: fl2k_file output:")
            print(stdout.decode())
            if stderr:
                print("cohi_playrecworker: fl2k_file errors:")
                self.SigError.emit(f"error when terminating fl2k_file: {stderr.decode()}")
        self.SigFinished.emit()
        return()

    def fastsine_check(self,loshift,sampling_rate,t_DATABLOCKSIZE):
        """check if fast sine calculation is possible and return optimized blocksize

        :param loshift: _description_
        :type loshift: _type_
        :param sampling_rate: _description_
        :type sampling_rate: _type_
        """
        errorstate = False
        value = None
        #t_DATABLOCKSIZE = 1024*4*256 #specify as constant elsewhere
        psc_locker = False
        DATABLOCKSIZE = t_DATABLOCKSIZE
        x = sampling_rate/loshift # number of datapoints per period of centershifte
        found_m = False
        rangestop = int(np.floor(DATABLOCKSIZE/2/x))
        rangestart = int(rangestop - max(1,np.floor(10000/x)))
        for k in range(rangestart, rangestop):  # Testen verschiedener k-Werte
            m = round(k * x)  # number of datapoints for k periods = total number of datapoints
            #target: test condition for k-values near max datablock size
            #dtatblocksize = 2*m = 2*k*x; m =ca DATABLOCKSIZE --> k = m/x, endk = DATABLOCKSIZE/2/x
            #k range = np.floor(DATABLOCKSIZE/2/x) - 1000
            #m = k*x is the number of samples needed for being sampling_rate a near integer multiple of the centershift period
            product = m / x # total number of periods
            rounded_product = round(product, 3) # deviation of rounded # periods from integer
            if abs(rounded_product - round(rounded_product)) <= 0.01:
                found_m = True
                break
        if found_m and (2*m < t_DATABLOCKSIZE) and (m > 0):
            #n = m * x
            #fractmin = t_DATABLOCKSIZE /(2*m)
            DATABLOCKSIZE = int(m*2)
            psc_locker = True
            #print(f"fl2k LOshifter: set fixed phasescaler for acceleration, turn to fast mode, m = {m}, psc_locker: {psc_locker}, DATABLOCKSIZE: {DATABLOCKSIZE}")
        else:
            #print("fl2k LOshifter cannot find optimum DATABLOCKSIZE for acceleration, turn to slow mode")
            pass
        value = [psc_locker, DATABLOCKSIZE]
        return(errorstate,value)

    def stop_loop(self):
        self.stopix = True

    def read24(self,format,data,filehandle,data_blocksize):
       """probably not applicable"""
       for lauf in range(0,data_blocksize):
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
        not applicable
        """
        return()


#     # if __name__ == "__main__":
#     #     # Beispielaufruf
#     #     input_file = "input_data.bin"  # Ersetzen Sie dies durch den Pfad zu Ihrer Eingabedatei
#     #     send_data_over_tcp(input_file)


#             # Man wird das Treiberprogramms fl2k_tcp nehmen können.
#             # Ähnlich dem Stemlab kann man hier eine IP und einen Port angeben.

#             # "fl2k_tcp, a spectrum client for FL2K VGA dongles\n\n"
#             # "Usage:\t[-a server address]\n"
#             # "\t[-d device index (default: 0)]\n"
#             # "\t[-p port (default: 1234)]\n"
#             # "\t[-s samplerate in Hz (default: 100 MS/s)]\n"
#             # "\t[-b number of buffers (default: 4)]\n"

#             # Bei mir läuft der D\A Wandler über den lokalen USB Bus, daher muss ich die Daten an den lokalen Recher der immer die IP 127.0.0.1 hat senden. Bei der Samplerate wähle ich 10000000 (10MS/s) da 100 MS/s meinen PC überlastet. Mit 10MS/s kommt man bis 5 MHz. Für Aufnahmen des 49m Bandes müsste ich einen höheren Eintrag wählen aber auch das geht. Für Langwelle und Mittelwelle reichen 10MS/s aus. Werte Unter 10 MS/s gibt es nur och einen krummen was beim Resampling womöglich zuviele Zwischenrechnungen verursacht.
#             # Das Resampling und verschieben auf die Bandmitte was Gnu Radio macht müsste das Cohiradia Programm selbst erledigen.
#             # Eine Datenkonvertierung und Aussteuerung auf 8 Bit Wertebereich ebenfalls. Auch das wird im Moment in Gnu Radio erledigt.


#     def check_fl2k_devices():
#         """
#         Führt fl2k_probe aus und prüft, ob FL2K-Geräte angeschlossen sind.
#         Gibt eine Liste der erkannten Geräte zurück.
#         """
#         try:
#             # fl2k_probe ausführen und Ausgabe erfassen
#             result = subprocess.run(
#                 ["fl2k_probe"], capture_output=True, text=True, check=True
#             )
#             output = result.stdout
            
#             # Geräte aus der Ausgabe extrahieren
#             if "Found 0 devices" in output:
#                 return []  # Keine Geräte gefunden
#             else:
#                 devices = []
#                 for line in output.splitlines():
#                     if line.startswith("Device"):
#                         devices.append(line.strip())
#                 return devices
        
#         except FileNotFoundError:
#             raise RuntimeError("fl2k_probe wurde nicht gefunden. Ist es installiert?")
#         except subprocess.CalledProcessError as e:
#             raise RuntimeError(f"fl2k_probe Fehler: {e.stderr.strip()}")

# # if __name__ == "__main__":
# #     devices = check_fl2k_devices()
# #     if devices:
# #         print(f"Gefundene Geräte: {devices}")
# #     else:
# #         print("Keine FL2K-Geräte gefunden.")

# #WINDOWS VARIANTE über stdin funktioniert nur, wenn eine RAMdisk eingerichtet ist, bei LINUX ist das wurscht
#     def process_and_send_fl2k(file_path, block_size=1024 * 1024):
#         """
#         Liest 16-Bit-Integer-Daten aus einer Datei, wandelt sie in 8-Bit-signed um,
#         und sendet sie blockweise an fl2k-file über stdin.

#         :param file_path: Pfad zur Eingabedatei mit 16-Bit-Integer-Daten.
#         :param block_size: Größe der Blöcke (in Bytes), die verarbeitet werden.
#         """
#         # Öffnen der Datei
#         with open(file_path, "rb") as f:
#             while True:
#                 # Blockweise Daten auslesen
#                 data = f.read(block_size)
#                 if not data:  # Datei zu Ende gelesen
#                     break
                
#                 # 16-Bit-Daten in numpy-Array laden
#                 int16_data = np.frombuffer(data, dtype=np.int16)
                
#                 # Umwandlung in 8-Bit signed (clipping bei Überläufen)
#                 int8_data = np.clip(int16_data / 256, -128, 127).astype(np.int8)
                
#                 # fl2k-file über stdin aufrufen
#                 #TODO: take sampling rate from configparams currently read by  
#                 process = subprocess.Popen(
#                     ["fl2k-file.exe", "-s", "20000000", "-"],  # '-' bedeutet stdin
#                     stdin=subprocess.PIPE
#                 )
                
#                 # Daten in den stdin-Stream schreiben
#                 process.stdin.write(int8_data.tobytes())
#                 process.stdin.close()
                
#                 # Warten, bis fl2k-file beendet ist
#                 process.wait()

#             #LINUX VARIANTE

#     def process_and_send_fl2k_lx(file_path, block_size=1024 * 1024):
#         """
#         Liest 16-Bit-Integer-Daten aus einer Datei, wandelt sie in 8-Bit-signed um,
#         und sendet sie blockweise an fl2k-file über stdin.

#         :param file_path: Pfad zur Eingabedatei mit 16-Bit-Integer-Daten.
#         :param block_size: Größe der Blöcke (in Bytes), die verarbeitet werden.
#         """
#         # Öffnen der Datei
#         with open(file_path, "rb") as f:
#             while True:
#                 # Blockweise Daten auslesen
#                 data = f.read(block_size)
#                 if not data:  # Datei zu Ende gelesen
#                     break
                
#                 # 16-Bit-Daten in numpy-Array laden
#                 int16_data = np.frombuffer(data, dtype=np.int16)
                
#                 # Umwandlung in 8-Bit signed (clipping bei Überläufen)
#                 int8_data = np.clip(int16_data / 256, -128, 127).astype(np.int8)
                
#                 # fl2k-file über stdin aufrufen
#                 process = subprocess.Popen(
#                     ["fl2k-file", "-s", "20000000", "-"],  # '-' bedeutet stdin
#                     stdin=subprocess.PIPE
#                 )
                
#                 # Daten in den stdin-Stream schreiben
#                 process.stdin.write(int8_data.tobytes())
#                 process.stdin.close()
                
#                 # Warten, bis fl2k-file beendet ist
#                 process.wait()

#OLD VERSION !
    # def play_loop_filelist(self):
    #     """
    #     worker loop for sending data to STEMLAB server
    #     data format i16; 2xi16 complex; FormatTag 1
    #     sends signals:     
    #         SigFinished = pyqtSignal()
    #         SigIncrementCurTime = pyqtSignal()
    #         SigBufferOverflow = pyqtSignal()

    #     :param : no regular parameters; as this is a thread worker communication occurs via
    #     class slots __slots__[i], i = 0...8
    #     __slots__[0]: filename = complete file path pathname/filename Type: list
    #     __slots__[1]: timescaler = bytes per second  TODO: rescaling to samples per second would probably be more logical, Type int
    #     __slots__[2]: TEST = flag for test mode Type: bool
    #     __slots__[3]: pause : if True then do not send data; Boolean
    #     __slots__[4]: filehandle: returns current filehandle to main thread methods on request 
    #     __slots__[5]: data segment to be returned every second
    #     __slots__[6]: gain, scaling factor for playback
    #     __slots__[7]: formatlist: [formattag blockalign bitpsample]
    #     __slots__[9]: file_close
    #     __slots__[10]: sampling_parameters
    #     """
    #     #print("reached playloopthread")
    #     filenames = self.get_filename()
    #     timescaler = self.get_timescaler()
    #     TEST = self.get_TEST()
    #     gain = self.get_gain()
    #     #TODO: self.fmtscl = self.__slots__[7] #scaler for data format      ? not used so far  
    #     self.stopix = False
    #     self.set_fileclose(False)
    #     configuration = self.get_configparameters() # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
    #     sSR = configuration["irate"] #TODO TODO TODO: check if correctly scaled (true frequ in S/s, nod kS/s)
    #     lo_shift = configuration["LO_offset"] #TODO check if this is really the LO frequency !!!
    #     # start fl2k_file with reading from stdin
    #     #TODO TODO: target samplingrate von aussen übernehm,en
    #     sampling_rate = 10000000
    #     fl2k_file_path = os.path.join(os.getcwd(),"dev_drivers/fl2k/osmo-fl2k-64bit-20250105", "fl2k_file.exe")
    #     print(f"cohi_playrecworker fl2k_file_path exists: {os.path.exists(fl2k_file_path)}")
    #     if os.name.find("posix") >= 0:
    #         try:
    #             process = subprocess.Popen(
    #                 ["fl2k_file", "-s", str(sampling_rate), "-"],
    #                 stdin=subprocess.PIPE,
    #                 stdout=subprocess.PIPE,
    #                 stderr=subprocess.PIPE,
    #                 bufsize=0
    #             )
    #         except FileNotFoundError:
    #             self.SigError.emit(f"Input file not found")
    #             self.SigFinished.emit()
    #             return()
    #         except subprocess.SubprocessError as e:
    #             self.SigError.emit(f"Error when executing fl2k_file: {e}")
    #             self.SigFinished.emit()
    #             return()
    #         except Exception as e:
    #             self.SigError.emit(f"Unexpected error: {e}")
    #             print("unexpected error in play_loop_filelist for fl2k")
    #             self.SigFinished.emit()
    #             return()
    #     else:

    #         try:
    #             process = subprocess.Popen(
    #                 [fl2k_file_path, "-s", str(sampling_rate), "-r", "0", "-"],
    #                 stdin=subprocess.PIPE,
    #                 stdout=subprocess.PIPE,
    #                 stderr=subprocess.PIPE,
    #                 bufsize=0
    #             )

    #         except FileNotFoundError:
    #             self.SigError.emit(f"Input file not found")
    #             self.SigFinished.emit()
    #             return()
    #         except subprocess.SubprocessError as e:
    #             self.SigError.emit(f"Error when executing fl2k_file: {e}")
    #             self.SigFinished.emit()
    #             return()
    #         except Exception as e:
    #             self.SigError.emit(f"Unexpected error: {e}")
    #             print("unexpected error in play_loop_filelist for fl2k")
    #             self.SigFinished.emit()
    #             return()

    #     for ix,filename in enumerate(filenames):
    #         fileHandle = open(filename, 'rb')
    #         self.SigNextfile.emit(filename)
    #         #print(f"filehandle for set_4: {fileHandle} of file {filename} ")
    #         self.set_fileHandle(fileHandle)
    #         format = self.get_formattag()
    #         ################# for testing here one could start a direct streaming to fl2k_file ############################

    #         #TEST: stream_to_fl2k_file(input_file, sampling_rate, fl2k_file_path="fl2k_file", buffer_size=data_blocksize)

    #         ######################## start streaming plus loshift plus resampling ############################
    #         #check fast_sine_check, psc locker !!!
    #         #errorstate, value = self.fastsine_check(lo_shift,sSR,self.DATABLOCKSIZE)
    #         #psc_locker = value[0]
    #         #data_blocksize = value[1] 
    #         data_blocksize = self.DATABLOCKSIZE
    #         self.set_datablocksize(data_blocksize)
    #         #print(f"Filehandle :{fileHandle}")
    #         fileHandle.seek(216, 1)
    #         data = np.empty(data_blocksize, dtype=np.int8)
    #         # if format[2] == 16:
    #         #     data = np.empty(data_blocksize, dtype=np.int16)
    #         # else:
    #         #     data = np.empty(data_blocksize, dtype=np.float32) #TODO: check if true for 32-bit wavs wie Gianni's
    #         #print(f"playloop: BitspSample: {format[2]}; wFormatTag: {format[0]}; Align: {format[1]}")
    #         if format[0] == 1:
    #             normfactor = int(2**int(format[2]-1))-1
    #         else:
    #             normfactor = 1
    #         # if format[2] == 16 or format[2] == 32:
    #         #     size = fileHandle.readinto(data)
    #         # elif format[2] == 24:
    #         #     data = self.read24(format,data,fileHandle,data_blocksize)
    #         #     size = len(data)
    #         size = fileHandle.readinto(data)
    #         print(f"data fetched, size = {size}")
    #         self.set_data(data)
    #         print(f"filehandle: {fileHandle}")
    #         junkspersecond = timescaler / self.JUNKSIZE
    #         count = 0
    #         # print(f"Junkspersec:{junkspersecond}")
    #         dt = 1/sSR
    #         segment_tstart = 0
    #         while size > 0 and not self.stopix:
    #             reftime = time.time()
    #             if not TEST:
    #                 if not self.get_pause():
    #                     try:
    #                         #scale data with gain and normfactor
    #                         aux1 = gain*data[0:size]/normfactor
    #                         # #####################################################
    #                         # aux2 = 1*aux1 #TODO TODO TODO: resample to 10MS/s 
    #                         # #####################################################
    #                         # ld = len(aux2)  #TODO ??? /2 ???
    #                         # aux3 = np.empty(ld, dtype=np.float32)
    #                         # if abs(lo_shift) > 1e-5:  #if frequency shift is needed
    #                         #     #splt into re and im
    #                         #     #rp = aux1[0:ld-1:2]
    #                         #     #ip = aux1[1:ld:2]
    #                         #     y = aux2[0:ld-1:2] +1j*aux2[1:ld:2]        
    #                         #     tsus = np.arange(segment_tstart, segment_tstart+len(y)*dt, dt)[:len(y)]
    #                         #     segment_tstart = tsus[len(tsus)-1] + dt
    #                         #     # try to calculate this vector only once and measure time #TODO TODO TODO: implement accelerator for single calculation of phasescaler
    #                         #     if not psc_locker:
    #                         #         phasescaler = np.exp(2*np.pi*1j*lo_shift*tsus)
    #                         #     elif first_lock_pass:
    #                         #         print("psc_locker, only one template loaded")
    #                         #         phasescaler = np.exp(2*np.pi*1j*lo_shift*tsus)
    #                         #         first_lock_pass = False
    #                         #     #multiply complex with exp(1j*w_LO*t)
    #                         #     ys = np.multiply(y,phasescaler)
    #                         #     #TODO TODO TODO: check if necessary if afterwards resampling is done; maybe can be done in 2 separate channels
    #                         #     aux3[0:ld:2] = (np.copy(np.real(ys)))
    #                         #     aux3[1:ld:2] = (np.copy(np.imag(ys)))  
    #                         # else:   #if no frequency shift, just copy data to temp file as they are
    #                         #     aux3 = np.copy(ys)
    #                         #####################################################
    #                         #aux3 = 1*aux2 #wron here: resample to 10MS/s 
    #                         #####################################################
    #                         # Skalieren, damit die Werte in den Bereich von int8 passen (-128 bis 127)
    #                         scaled_array = np.clip(150*aux1, -128, 127)
    #                         print("send junk to fl2k_file")
    #                         # print(f"scaled array, max: {max(scaled_array)}, max(aux1): {max(aux1)}")
    #                         # print(f"aux1[100:150]: {aux1[100:150]}")
    #                         # print(f"data[100:150]: {data[100:150]}")
    #                         # print(f"scaled_array[100:150]: {scaled_array[100:150]}")
    #                         ####TODO TODO TODO AGC block
    #                         # Casten zu int8
    #                         #aux4 = scaled_array.astype(np.int8) #TODO TODO TODO: check correct scaling or do AGC
    #                         #write aux4 to fl2k_file via stdin
    #                         process.stdin.write(scaled_array.astype(np.int8))
    #                         process.stdin.flush()
    #                         print("written to stdin")
    #                         # gain*data[0:size].astype(np.int8)
    #                         ###########################################TODO: new sending routine via fl2k_file
    #                     except BlockingIOError:
    #                         print("Blocking data socket error in playloop worker")
    #                         time.sleep(0.1)
    #                         self.SigError.emit("Blocking data socket error in playloop worker")
    #                         self.SigFinished.emit()
    #                         time.sleep(0.1)
    #                         return
    #                     except ConnectionResetError:
    #                         print("Diagnostic Message: Connection data socket error in playloop worker")
    #                         time.sleep(0.1)
    #                         self.SigError.emit("Diagnostic Message: Connection data socket error in playloop worker")
    #                         self.SigFinished.emit()
    #                         time.sleep(0.1)
    #                         return
    #                     except Exception as e:
    #                         print("Class e type error  data socket error in playloop worker")
    #                         print(e)
    #                         time.sleep(0.1)
    #                         self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
    #                         self.SigFinished.emit()
    #                         time.sleep(0.1)
    #                         return
    #                     # if format[2] == 16 or format[2] == 32:
    #                     #     size = fileHandle.readinto(data)
    #                     # elif format[2] == 24:
    #                     #     data = self.read24(format,data,fileHandle,data_blocksize)
    #                     #     size = len(data)
    #                     #  read next data_blocksize samples
    #                     #print("fetch next data")
    #                     #print(f"filehandle: {fileHandle}")
    #                     size = fileHandle.readinto(data)
    #                     print(f"data fetched, size = {size}")
    #                     count += 1
    #                     if count > junkspersecond:
    #                         print("increment emit, modified")
    #                         #TODO TODO TODO inactivated:check for timing !!!self.SigIncrementCurTime.emit()
    #                         #Dieser Aufruf blockiert das weitere Streaming immer für einige Zeit
    #                         count = 0
    #                         #self.mutex.lock()
    #                         gain = self.get_gain()
    #                         #print(f"diagnostic: gain in worker: {gain}")
    #                         self.set_data(data)
    #                         #self.mutex.unlock()
    #                 else:
    #                     #print("Pause, do not do anything")
    #                     print("sleep a while")
    #                     time.sleep(0.1)
    #                     if self.stopix is True:
    #                         break
    #             else:
    #                 if not self.get_pause():
    #                     print(" SDR_control fl2k test reached")
    #                     # if format[2] == 16 or format[2] == 32:
    #                     #     size = fileHandle.readinto(data)
    #                     # elif format[2] == 24:
    #                     #     data = self.read24(format,data,fileHandle,data_blocksize)
    #                     #     size = len(data)
    #                     size = fileHandle.readinto(data)
    #                     #print(f"size read: {size}")
    #                     #print(data[1:10])
    #                     #size = fileHandle.readinto(data)
    #                     time.sleep(0.0001)
    #                     #  read next 2048 bytes
    #                     count += 1
    #                     if count > junkspersecond and size > 0:
    #                         #print('timeincrement reached')
    #                         self.SigIncrementCurTime.emit()
    #                         gain = self.get_gain()
    #                         #print(f"diagnostic: gain in worker: {gain}")
    #                         #print(f"maximum: {np.max(data)}")
    #                         #self.set_data(gain*data)
    #                         self.set_data(data)
    #                         count = 0
    #                 else:
    #                     time.sleep(1)
    #                     if self.stopix is True:
    #                         break
    #             proc_time = time.time() - reftime
    #             print(f"process time: {proc_time}")                
    #     print("close file ")
    #     self.set_fileclose(True)
    #     fileHandle.close()
    #         #self.set_fileclose(True)
    #     #print('worker  thread finished')
    #     # terminate fl2k_file process and wait for actual termination
    #     process.stdin.close()
    #     process.terminate
    #     while process.poll() == None:

    #         print("poll and close")
    #         time.sleep(1)
    #     print("close process ")
        
    #     stdout, stderr = process.communicate() ### TODO TODO TODO: Timeout ???
    #     # Report result
    #     print("cohi_playrecworker: fl2k_file output:")
    #     print(stdout.decode())
    #     if stderr:
    #         print("cohi_playrecworker: fl2k_file errors:")
    #         self.SigError.emit(f"error when terminating fl2k_file: {stderr.decode()}")
    #     self.SigFinished.emit()
    #     #print("SigFinished from playloop emitted")
