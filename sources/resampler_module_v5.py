import numpy as np
import sys
import time
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtGui
import datetime as ndatetime
import logging
import os 
import subprocess
import shutil
from PyQt5 import QtWidgets
from matplotlib.patches import Rectangle
#from SDR_wavheadertools_v2 import WAVheader_tools
import system_module as wsys
from auxiliaries import auxiliaries as auxi
from auxiliaries import WAVheader_tools

#import auxiliaries as auxi


#TODO: define class resample_model()
#transfer most of 'system_state'  and respective class instance gui_state to internal dictionary 
#with the name mdl
#instead of         
#    system_state = self.sys_state.get_status()
#    self.sys_state.set_status(system_state)
#
# in __init__(self, gui, model) of view and controller: self.mdl = model.mdl   
# calling only as self.mdl
class resample_m(QObject):
    __slots__ = ["None"]
    SigModelXXX = pyqtSignal()

    #TODO: replace all gui by respective state references if appropriate
    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["_log"] = False
        self.mdl["sample"] = 0
        self.mdl["my_filename"] = ""
        self.mdl["ext"] = ""
        self.mdl["fileopened"] = False
        # Create a custom logger
        logging.getLogger().setLevel(logging.DEBUG)
        # Erstelle einen Logger mit dem Modul- oder Skriptnamen
        self.logger = logging.getLogger(__name__)
        # Create handlers
        # Create handlers
        warning_handler = logging.StreamHandler()
        debug_handler = logging.FileHandler("system_log.log")
        warning_handler.setLevel(logging.WARNING)
        debug_handler.setLevel(logging.DEBUG)

        # Create formatters and add it to handlers
        warning_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        debug_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        warning_handler.setFormatter(warning_format)
        debug_handler.setFormatter(debug_format)

        # Add handlers to the logger
        self.logger.addHandler(warning_handler)
        self.logger.addHandler(debug_handler)

        self.logger.debug('Init logger in resampler reached')
        pass


#TODO: TESTEN durch mal eine ausgewählte system_state Variable

class res_workers(QObject):
    """ worker class for data streaming thread from PC to STEMLAB
    object for playback and recording thread
    :param : no regular parameters; as this is a thread worker communication occurs via
        __slots__: Dictionary with entries:
        __slots__[0]: soxstring Type: str
        __slots__[1]: return string from sox execution, type : str
    '''
    :raises [ErrorType]: none
    '''
        :return: none
        :rtype: none
    """
    __slots__ = ["soxstring", "ret","tfname","expfs","progress","sfilename","readoffset","readsegmentfn","sSR","centershift","sBPS","tBPS","wFormatTag", "inputfilelist", "sttime_atrim", "merge_delorig","maxgap","starttrim","stoptrim"]

    SigFinished = pyqtSignal()
    SigPupdate = pyqtSignal()
    SigFinishedLOshifter = pyqtSignal()
    SigFinishedmerge2G = pyqtSignal()
    SigSoxerror = pyqtSignal(str)
    SigMergeerror = pyqtSignal(str)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.sys_state = wsys.status()
        #self.system_state = self.sys_state.get_status()
        #gui = self.system_state["gui_reference"]
        #self.system_state["Res_GUI_updatelabel"] = "none"
        self.stopix = False
        self.mutex = QMutex()
        self.CHUNKSIZE = int(1024**2)
        #self.sys_state.set_status(self.system_state)
 
    def set_soxstring(self,_value):
        self.__slots__[0] = _value
    def get_soxstring(self):
        return(self.__slots__[0])
    def set_ret(self,_value):
        self.__slots__[1] = _value
    def get_ret(self):
        return(self.__slots__[1])
    def set_tfname(self,_value):
        self.__slots__[2] = _value
    def get_tfname(self):
        return(self.__slots__[2])
    def set_expfs(self,_value):
        self.__slots__[3] = _value
    def get_expfs(self):
        return(self.__slots__[3])
    def set_progress(self,_value):
        self.__slots__[3] = _value
    def get_progress(self):
        return(self.__slots__[3])
    def set_sfname(self,_value):
        self.__slots__[4] = _value
    def get_sfname(self):
        return(self.__slots__[4])
    def set_readoffset(self,_value):
        self.__slots__[5] = _value
    def get_readoffset(self):
        return(self.__slots__[5])
    def set_readsegment(self,_value):
        self.__slots__[6] = _value
    def get_readsegment(self):
        return(self.__slots__[6])
    def set_sSR(self,_value):
        self.__slots__[7] = _value
    def get_sSR(self):
        return(self.__slots__[7])
    def set_centershift(self,_value):
        self.__slots__[8] = _value
    def get_centershift(self):
        return(self.__slots__[8])
    def set_sBPS(self,_value):
        self.__slots__[9] = _value
    def get_sBPS(self):
        return(self.__slots__[9])
    def set_tBPS(self,_value):
        self.__slots__[10] = _value
    def get_tBPS(self):
        return(self.__slots__[10])
    def set_wFormatTag(self,_value):
        self.__slots__[11] = _value
    def get_wFormatTag(self):
        return(self.__slots__[11])
    def set_inputfilelist(self,_value):
        self.__slots__[12] = _value
    def get_inputfilelist(self):
        return(self.__slots__[12])
    def set_sttime_atrim(self,_value):
        self.__slots__[13] = _value
    def get_sttime_atrim(self):
        return(self.__slots__[13])
    def set_merge_delorig(self,_value):
        self.__slots__[14] = _value
    def get_merge_delorig(self):
        return(self.__slots__[14])
    def set_maxgap(self,_value):
        self.__slots__[15] = _value
    def get_maxgap(self):
        return(self.__slots__[15])   
    def set_starttrim(self,_value):
        self.__slots__[16] = _value
    def get_starttrim(self):
        return(self.__slots__[16])   
    def set_stoptrim(self,_value):
        self.__slots__[17] = _value
    def get_stoptrim(self):
        return(self.__slots__[17])   

    def merge2G_worker(self):  # 2 GB in Bytes
        """worker for merging all files in system_state["list_out_files_resampled"]
        :param: input_file_list
        :type: none
        ...
        :raises none
        ...
        :return: none
        :rtype: none
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        #wavheader = system_state["t_wavheader"]

        self.stopix = False
        output_file_prefix = self.get_tfname()
        current_output_file_index = 1
        current_output_file_size = 0
        current_output_file_path = f"{output_file_prefix}_{current_output_file_index}.dat"
        MAX_TARGETFILE_SIZE = int(2**31)
        MAX_GAP = self.get_maxgap()
        input_file_list = self.get_inputfilelist()
        print("merge2G: start merging files")
        #self.logger.debug("merge2G: start merging files")

        maxprogress = 100
        lenlist = len(input_file_list)
        list_ix = 0
        time.sleep(5) #TODO: check if 5 s is necessary
        #TODO: Entrypoint für zu wählenden Ausgangsfilenamen über getter/setter, wie oben
        basename = self.get_ret()
        self.set_progress(1)
        print(f'merge2G init progress: {1}')
        #self.logger.debug("merge2G init progress: 1")
        self.SigPupdate.emit()


        with open(current_output_file_path, 'wb') as current_output_file:
            # Schreibe die ersten 216 Bytes mit Nullen
            print(f"merge2G: generate outputfile {current_output_file_path}")
            current_output_file.write(b'\x00' * 216)
            current_output_file_size = 216
            firstpass = True
            firstsource = True     ##########NEW AFTER GAPFIXING
            for input_file in input_file_list: #TODO: rewrite with enumerate for list index
                time.sleep(5)
                list_ix += 1
                progress = list_ix/lenlist*maxprogress
                self.set_progress(progress)
                print(f'merge2G progress: {progress}')
                self.SigPupdate.emit()
                #resample_v.updateprogress_resampling(self)
                time.sleep(0.1)
                WRITEGAP = False
                if firstpass:
                    wavheader = WAVheader_tools.get_sdruno_header(self,input_file)
                if firstsource:     ##########NEW AFTER GAPFIXING
                    wavheader = WAVheader_tools.get_sdruno_header(self,input_file)
                    prev_stoptime = wavheader['stoptime_dt']
                    prev_stoptime_ms = wavheader['stoptime'][7]
                    gap = 0
                else:
                    aux_wavheader = WAVheader_tools.get_sdruno_header(self,input_file)
                    aux_starttime = aux_wavheader['starttime_dt']
                    gap = (aux_starttime - prev_stoptime).seconds + (aux_wavheader['starttime'][7] - prev_stoptime_ms)/1000
                    prev_stoptime = aux_wavheader['stoptime_dt']
                    prev_stoptime_ms = aux_wavheader['stoptime'][7]
                #check if gap is positive and how many bytes that are
                if gap > 0:
                    #TODO: send signal for finishing !
                    if gap > MAX_GAP:
                        exitcount = 0
                        print(f"Merge2G: gap is greater than max tolreable amount, gap = {gap}")
                        #auxi.standard_errorbox(f"gap is greater than max tolreable amount !, gap = {gap}")
                        self.SigMergeerror.emit(f"Merge2G: gap is greater than max tolreable amount, gap = {gap}")
                        self.SigFinishedmerge2G.emit()
                        while True:
                            exitcount += 1
                            self.SigFinishedmerge2G.emit()
                            time.sleep(1)
                            print("endless loop finish gap > MAX_GAP")
                            if exitcount > 5:
                                print("mission impossible, give up")
                                return False
                        #return(False) ## TODO: stürzt ab, wenn return
                    gap_bytes = int(np.ceil(gap * wavheader["nAvgBytesPerSec"]/2)*2)
                    WRITEGAP = True
                elif gap < 0:
                    print(f"merge2G, gap is negative, error !, gap = {gap}")
                    auxi.standard_errorbox(f"Merge2G: gap is negative, error !, gap = {gap}")
                    return(False)

                with open(input_file, 'rb') as input_file:
                    print(f"next input file: {input_file} ")
                    fillchunk = bytes([0x00] * self.CHUNKSIZE)
                    while True:
                        if self.stopix is True:
                            print("***merge2G worker cancel merging process")
                            input_file.close()
                            time.sleep(1)
                            print("***merge2G worker input file closed")
                            self.SigFinishedmerge2G.emit()
                            return()

                        if WRITEGAP: #generate a byte array with CHINKSIZE zeros until gap_bytes is fully consumed    ##########NEW AFTER GAPFIXING
                            #write CHUNKSIZE of the current gap and deduct from gap budget
                            if gap_bytes > self.CHUNKSIZE:
                                gap_bytes -= self.CHUNKSIZE
                                data_chunk = fillchunk
                            elif gap_bytes == self.CHUNKSIZE:
                                data_chunk = fillchunk
                                WRITEGAP = False
                            else:
                                WRITEGAP = False
                                data_chunk = bytes([0x00] * gap_bytes)
                        else:
                            # read CHUNKSIZE bytes from source file
                            data_chunk = input_file.read(self.CHUNKSIZE)  # 1 MB in Bytes
                            #TODO: gain calculation: chunk needs to be reformatted to np array, multiplied and then written back to bytesequence
                            #data_chunk = gain * data_chunk
                            ##########################
                        # Überprüfe, ob die Eingabedatei vollständig gelesen wurde
                        #TODO: Stoppe weiteres Lesen, wenn Cutting Stopzeit erreicht 
                        if not data_chunk:
                            firstsource = False
                            if list_ix > (lenlist-1):
                                print(f"merge2G: last write file reached, ix = {lenlist}")
                                #write last wavheader
                                duration = (current_output_file_size - 216)/wavheader["nAvgBytesPerSec"]
                                #TODO: this is wrong except for the last file! must be the stoptime of the last output file
                                if firstpass:
                                    firstpass = False
                                    stt = stt = self.get_sttime_atrim()
                                    print(f"merge2G: last == first write file reached, ix = 0")
                                    wavheader['starttime_dt'] = stt
                                    wavheader['starttime'] = [stt.year, stt.month, 0, stt.day, stt.hour, stt.minute, stt.second, int(stt.microsecond/1000)] 
                                else:
                                    stt = wavheader["starttime_dt"]
                                spt = stt + ndatetime.timedelta(seconds = np.floor(duration)) + ndatetime.timedelta(milliseconds = 1000*(duration - np.floor(duration)))
                                wavheader['stoptime_dt'] = spt
                                wavheader['stoptime'] = [spt.year, spt.month, 0, spt.day, spt.hour, spt.minute, spt.second, int(spt.microsecond/1000)] 
                                wavheader['filesize'] = current_output_file_size
                                wavheader['data_nChunkSize'] = wavheader['filesize'] - 208
                                wavheader['nextfilename'] = ""
                                WAVheader_tools.write_sdruno_header(self,current_output_file.name,wavheader,True)
                                #TODO: rename to newfile
                                nametrunk, extension = os.path.splitext(current_output_file.name)
                                nametrunk = f"{os.path.dirname(current_output_file_path)}/{basename}_{str(current_output_file_index)}_"
                                aux = str(wavheader['starttime_dt'])
                                if aux.find('.') < 1:
                                    SDRUno_suff = aux
                                else:
                                    SDRUno_suff = aux[:aux.find('.')]
                                SDRUno_suff = SDRUno_suff.replace(" ","_")
                                SDRUno_suff = SDRUno_suff.replace(":","")
                                SDRUno_suff = SDRUno_suff.replace("-","")
                                new_name = nametrunk + str(SDRUno_suff) + '_' + str(int(np.round(wavheader["centerfreq"]/1000))) + 'kHz.wav'
                                current_output_file.close()
                                time.sleep(0.01)
                                jx = 0
                                while jx <1:
                                    try:
                                        print(f"merge2Gworker try shutil {current_output_file_path} to {new_name}")
                                        shutil.move(current_output_file_path, new_name)
                                    except:
                                        jx += 1
                                        print(f"merge2Gworker renamefile trial {str(jx)}")
                                        time.sleep(0.5)
                                # if jx == 10:
                                #     auxi.standard_errorbox("The output file was written, but the temp file could not be renamed for unknown reason . Please repeat the merging process")                                    
                            print("break merget2Gworker")
                            break

                        # check if output file exceeds maximum size
                        if current_output_file_size + len(data_chunk) > MAX_TARGETFILE_SIZE: #TEST: 50 * 1024**2: #TODO: zurückstellen nach Test self.MAX_TARGETFILE_SIZE:
                            #generate individual wavheaders, generate nextfilename
                            current_output_file.close()
                            #insert wav header
                            duration = (current_output_file_size - 216)/wavheader["nAvgBytesPerSec"]
                            if firstpass:
                                print(f"merge2G: first write file reached, ix = 0")
                                #TODO: write first starttime from cut_times
                                firstpass = False

                                stt = self.get_sttime_atrim()
                                wavheader['starttime_dt'] = stt
                                wavheader['starttime'] = [stt.year, stt.month, 0, stt.day, stt.hour, stt.minute, stt.second, int(stt.microsecond/1000)] 
                            else:
                                #TODO: 
                                #aktuell: wenn aktuelles Ausgabefile fertig, hole Startzeit vom Header des aktuellen
                                #Ausgabefiles, addiere Dauer und generiere daraus den nächsten wavheader
                                #beim ersten Listeneintrag hole Startzit von starttime after trim
                                stt = wavheader["starttime_dt"]
                            spt = stt + ndatetime.timedelta(seconds= np.floor(duration))  + ndatetime.timedelta(milliseconds = 1000*(duration - np.floor(duration)))
                            wavheader['stoptime_dt'] = spt
                            wavheader['stoptime'] = [spt.year, spt.month, 0, spt.day, spt.hour, spt.minute, spt.second, int(spt.microsecond/1000)] 
                            wavheader['filesize'] = current_output_file_size
                            wavheader['data_nChunkSize'] = wavheader['filesize'] - 208
                            nametrunk = f"{os.path.dirname(current_output_file_path)}/{basename}_{str(current_output_file_index)}_"
                            next_nametrunk = f"{basename}_{str(current_output_file_index + 1)}_" 
                            aux = str(wavheader['starttime_dt'])
                            if aux.find('.') < 1:
                                SDRUno_suff = aux
                            else:
                                SDRUno_suff = aux[:aux.find('.')]
                            SDRUno_suff = SDRUno_suff.replace(" ","_")
                            SDRUno_suff = SDRUno_suff.replace(":","")
                            SDRUno_suff = SDRUno_suff.replace("-","")
                            aux = str(wavheader['stoptime_dt'])
                            if aux.find('.') < 1:
                                next_suff = aux
                            else:
                               next_suff = aux[:aux.find('.')]
                            next_suff = next_suff.replace(" ","_")
                            next_suff = next_suff.replace(":","")
                            next_suff = next_suff.replace("-","")
                            next_name = next_nametrunk + str(next_suff) + '_' + str(int(np.round(wavheader["centerfreq"]/1000))) + 'kHz.wav'
                            new_name = nametrunk + str(SDRUno_suff) + '_' + str(int(np.round(wavheader["centerfreq"]/1000))) + 'kHz.wav'
                            wavheader['nextfilename'] = next_name
                            WAVheader_tools.write_sdruno_header(self,current_output_file.name,wavheader,True)

                            while True:
                                try:
                                    shutil.move(current_output_file_path, new_name)
                                    break
                                except:
                                    print("Warning 202 merge2Gworker: cannot access temp file, retry in 2 s")
                                    time.sleep(2)

                            # prepare next wavheader starttime
                            wavheader['starttime_dt'] = wavheader['stoptime_dt']
                            wavheader['starttime'] = wavheader['stoptime']
                            current_output_file_size = 0
                            current_output_file_index += 1
                            current_output_file_path = f"{output_file_prefix}_{current_output_file_index}.dat"
                            print(f"merge2G next outputfile {current_output_file_path}")
                            current_output_file = open(current_output_file_path, 'wb')
                            current_output_file.write(b'\x00' * 216)  # Schreibe die ersten 216 Bytes mit Nullen
                        # write data to target file: if last file: nextfile = ''
                        current_output_file.write(data_chunk)
                        current_output_file_size += len(data_chunk)
        print("merge2G: merge files done")
        self.SigFinishedmerge2G.emit()

    def sox_writer(self):

        print("#############sox_worker as sox_writer started##############")
        self.stopix = False
        soxstring = self.get_soxstring()
        self.ret = subprocess.Popen(soxstring, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = True)
        self.set_ret(self.ret)
        time.sleep(1)
        #print(f"sox return value: {process}")
        #print(f"sox return value: {self.ret}")
        targetfilename = self.get_tfname()
        expected_filesize = self.get_expfs()
        #print(f"soxwriter targetfilename: {targetfilename}, exp filesize: {expected_filesize}")
        #print(expected_filesize)
        #self.SigStarted.emit()
        if os.path.exists(targetfilename) == True:
            #print("soxwriter: temp file has been created")
            file_stats = os.stat(targetfilename)
            rf = np.floor(100*file_stats.st_size/expected_filesize)
            if np.isnan(rf):
                print("soxwriter ERROR ________________soxwriter progress exception, set progress zero")
                rel_finish = int(5)
            else:
                rel_finish = int(rf)
            #rel_finish = int(np.floor(100*file_stats.st_size/expected_filesize))
            progress_old = 0
            loop_ix = 0
            deltaold = 0
            #Bedingung: Delta size 
            #print(f"soxwriter: initial ret.poll output (sox acive on None ?): {self.ret.poll()}")

            while (file_stats.st_size < (expected_filesize)) and (loop_ix < 20) and (self.stopix is False):  #HACK TODO: analyze why expected filesize is by > 1000 smaller than the one produced by sox 
                delta = file_stats.st_size - expected_filesize
                # if sox has finished but expected filesize is not reached, wait 20 cycles and then terminate
                if (deltaold == delta) and file_stats.st_size >0:
                    loop_ix += 1
                    #print(f"soxwriter: ret.poll output (sox acive ?): {self.ret.poll()}")
                    #print(f"soxloop deltacount (break at 20): {loop_ix}")
                deltaold = delta
                try:
                    file_stats = os.stat(targetfilename)
                    rf = np.floor(100*file_stats.st_size/expected_filesize)
                    if np.isnan(rf):
                        #print("soxwriter ERROR ________________soxwriter progress exception, set progress zero")
                        rel_finish = int(5)
                    else:
                        rel_finish = int(rf)
                    #print("resampling process running")
                    time.sleep(0.5)
                    #print(f"soxwriter: bytes resampled: {file_stats.st_size} / {expected_filesize}, stopix: {self.stopix}, loopix: {loop_ix}")
                    progress = rel_finish
                    if not progress > 0:
                        progress = 5
                        self.set_progress(progress)
                        self.SigPupdate.emit()
                    #print(f"relative filesize in %: {progress}")
                    if progress - progress_old > 5:
                        #self.mutex.lock()
                        progress_old = progress
                        self.set_progress(progress)
                        self.SigPupdate.emit()
                        #print("NOW UPDATE STATUSBAR#############################################################################")
                        #self.mutex.unlock()
                except:
                    #print("soxwriter_ temp file not found, proceeding without progress update")
                    loop_ix = 3
                if self.stopix is True:
                    #self.ret.terminate()
                    while self.ret.poll() is None:
                        #print("***soxwriter>>>>>>>>>killing process")
                        self.ret.kill()
                        time.sleep(1)
                    #print("********_____________soxwriter: terminate sox process on cancel")

        else:
            print(f"ERROR: no file {targetfilename} created")
        #print("soxwriter: success")
        time.sleep(0.5)
        #print("#############sox_worker wait for termination of sox")
        if self.ret.poll() is None:
            stdout, stderr = self.ret.communicate()
        #print("#############sox_worker as sox_writer finished##############")
        self.SigFinished.emit()

    def soxworker_terminate(self):
        #self.stopix = False
        #print("********************* ______________ terminate sox process now")
        self.stopix = True


    def LO_shifter_worker(self):
        self.stopix = False
        DATABLOCKSIZE = 1024*4*256
        INCREMENT = 1000000
        #print("#############LOshifter_worker started##############")
        targetfilename = self.get_tfname()
        try:
            target_fileHandle = open(targetfilename, 'ab')
        except:
            #print("LOshifter worker: cannot open resampling temp file")
            return False
        sourcefilename = self.get_sfname()
        try:
            source_fileHandle = open(sourcefilename, 'rb')
        except:
            #print("LOshifter worker: cannot open resampling source file")
            return False
        startoffset = self.get_starttrim()
        #print(f"LOshifter worker startoffset (bytes): {startoffset}")
        readoffset = self.get_readoffset()
        source_fileHandle.seek(readoffset+startoffset, 1) #TODO: check if offset larger than filesize
        expected_filesize = self.get_expfs()
        readsegmentfn = self.get_readsegment()
        centershift = self.get_centershift()
        #print(f"centershift: <<<<<<<<<<<<<<<<<<<<<<<{centershift}>>>>>>>>>>>>>>>>>")
        sBPS = self.get_sBPS()
        tBPS = self.get_tBPS()
        wFormatTag = self.get_wFormatTag()
        position = 0
        #TODO: replace following by new readsegment call
        #ret = readsegmentfn(position,DATABLOCKSIZE) #TODO: transfer to auxiliary block
        #TODO: , define new readsegment-function, generalize to tBPS rather than 32 bit
        ret = readsegmentfn(self,sourcefilename,position,readoffset,DATABLOCKSIZE,sBPS,32,wFormatTag)
        #readsegment_new(self,filepath,position,readoffset,DATABLOCKSIZE,sBPS,tBPS,wFormatTag)
        sSR = self.get_sSR()
        # print(f"LOshifter worker sSR: {sSR} sBPS: {sBPS} expfilesz: {expected_filesize}")
        # print(f"LOshifter worker souce: {sourcefilename} target: {targetfilename} ")
        # print(f"LOshifter worker centershift: {centershift} readoffset: {readoffset} ")
  
        dt = 1/sSR
        segment_tstart = 0
        #print(f"LOshifter worker targetfilename: {targetfilename}, exp filesize: {expected_filesize}")
        #print(expected_filesize)
        if os.path.exists(targetfilename) == True:
            #print("LOshift worker: target file has been found")
            file_stats = os.stat(targetfilename)
            progress_old = 0
            fsize_old = 0
            while ret["size"] > 0:
                #TODO: implement cutstart/stop here
                # cutstartoffset = seconds(cutstart);
                ld = len(ret["data"])  #TODO: remove and replace [0:ld:2] by [0::2]
                y_sh = np.empty(len(ret["data"]), dtype=np.float32)
                if abs(centershift) > 1e-5:
                    #print("LOworker shifting active")
                    rp = ret["data"][0:ld-1:2]
                    ip = ret["data"][1:ld:2]
                    y = rp +1j*ip        
                    tsus = np.arange(segment_tstart, segment_tstart+len(y)*dt, dt)[:len(y)]
                    segment_tstart = tsus[len(tsus)-1] + dt
                    phasescaler = np.exp(2*np.pi*1j*centershift*tsus)
                    ys = np.multiply(y,phasescaler)
                    y_sh[0:ld:2] = (np.copy(np.real(ys)))
                    y_sh[1:ld:2] = (np.copy(np.imag(ys)))  
                else:   #if no frequency shift, just copy data to temp file as they are
                    #print("LOworker no shift, just dummy copy")
                    y_sh = np.copy(ret["data"])
                y_sh.tofile(target_fileHandle)
                #TODO: check if this is always meaningful (32 bit)
                if 2*ret["size"]/(sBPS/4) == DATABLOCKSIZE:
                    position = position + ret["size"]
                    ret = readsegmentfn(self,sourcefilename,position,readoffset,DATABLOCKSIZE,sBPS,32,wFormatTag)
                else:
                    ret["size"] = 0
                file_stats = os.stat(targetfilename)
                progress = int(np.floor(100*file_stats.st_size/expected_filesize))
                #print("LOshifting worker process running")
                time.sleep(0.001)

                delta = file_stats.st_size - fsize_old

                if delta > INCREMENT: 
                    progress_old = progress
                    fsize_old = file_stats.st_size
                    self.set_progress(progress)
                    self.SigPupdate.emit()
                if self.stopix is True:
                    break
        else:
            #print("LOshift worker: target file has not been found")
            rint(f"LOshift worker:ERROR: no file {targetfilename} created")
            #print("success")
            time.sleep(0.1)
        source_fileHandle.close()    
        target_fileHandle.close()
        print("#############Loshifter_worker finished##############")
        time.sleep(1)
        self.SigFinishedLOshifter.emit()

class resample_c(QObject):
    """_methods for resampling (= resampling controller)
    this class defines a state machine for variable sequences of tasks during several different modes of resampling
    the class methods communicate via the class variables of the central data class 'status' and via signalling.
    the state machine is defined via the scheduler method which needs to be configured and launched via a signal from the main thread (here the main GUI)
    """
    __slots__ = ["LOvars"]
    #SigUpdateGUI = pyqtSignal(str)
    SigGP = pyqtSignal()
    SigResample = pyqtSignal()
    SigAccomplish = pyqtSignal()
    SigLOshift = pyqtSignal()
    SigProgress = pyqtSignal()
    Sigincrscheduler = pyqtSignal()
    SigTerminate_Finished = pyqtSignal()
    SigCancel = pyqtSignal()
    SigResampGUIReset = pyqtSignal()
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    #SigSyncTabs = pyqtSignal(object)
    #SigUpdateGUI = pyqtSignal()
    SigUpdateGUIelements = pyqtSignal()
    SigDisconnectExternalMethods = pyqtSignal(str)
    SigConnectExternalMethods = pyqtSignal(str)
    SigRelay = pyqtSignal(str,object)

    #TODO: replace all gui by respective state references if appropriate
    def __init__(self, resample_m):
        super().__init__()
        self.m = resample_m.mdl
        self.MAX_GAP = 300 # seconds allowable between two subsequent source files
        self.CHUNKSIZE = 1024**2 # data chunk size for reading/writing files
        #TODO: check condition early
        self.TEST = True
        LOvars = {}
        self.set_LOvars(LOvars)
        #self.sys_state = wsys.status()   ###TEST 09-01-2024
        #self.sys_state = gui_state  ###TEST 09-01-2024
        #self.system_state = self.sys_state.get_status()
        #self.SigProgress.connect(lambda: resample_v.updateprogress_resampling(self))#TODO: untersuchen, ob Abonnieren besser vom GUI aus geschehen soll
        self.MAX_TARGETFILE_SIZE = 2 * 1024**3 #2GB max output filesize
        self.m["resampling_gain"] = 0
        self.m["last_system_time"] = time.time()
        self.m["clearlist"] = False
        self.logger = resample_m.logger
        self.logger.debug(f'__init__ resampler: {self.m["sample"]}')

    def set_LOvars(self,_value): #TODO seems unused, remove ?
        self.__slots__[0] = _value

    def get_LOvars(self): #TODO seems unused, remove ?
        return(self.__slots__[0])
    
    def resamp_configheader(self,wavheader,header_config):
        """inserts fields specified in header_config into wavheader
        :param: wavheader: dict of type wav_header (see main gui)
        :type: dict
        :param: header_config: list of fiels: wFormatTag; data_chkID, sdrtype_chckID, sdr_nChunksize, nBitsPerSample, nBlockalign, readoffset, centerfreq
        :type: dict
        ...
        :raises: none
        ...
        :return: mod_header (format wav_header)
        :rtype: dict
        """
        mod_header = wavheader
        mod_header['wFormatTag'] = header_config[0]
        mod_header['data_ckID'] = header_config[1]
        mod_header['sdrtype_chckID'] = header_config[2]
        mod_header['sdr_nChunkSize'] = header_config[3]
        mod_header["nBitsPerSample"] = header_config[4]
        mod_header['nBlockAlign'] = header_config[5]
        sizescaler = mod_header['nBlockAlign']/wavheader['nBlockAlign']
        mod_header['nAvgBytesPerSec'] = int(np.floor(mod_header['nAvgBytesPerSec'] * sizescaler))
        mod_header['filesize'] = int(np.floor((wavheader['filesize'] - header_config[6])*sizescaler + header_config[6]))
        mod_header['data_nChunkSize'] = mod_header['filesize'] - header_config[6] + 8
        mod_header['centerfreq'] = header_config[7]
        return mod_header
    
    def checkdiskspace(self,expected_filesize, _dir):
        """check if free diskspace is sufficient for writing expeczed_filesize bytes on directory _dir
        :param: expected_filesize
        :type: int
        :param: _dir
        :type: str
        ...
        :raises: none
        ...
        :return: True if enough space, False else
        :rtype: Boolean
        """
        total, used, free = shutil.disk_usage(_dir)
        if free < expected_filesize:
            self.logger.debug(f"not enough diskspace for this process, please free at least {expected_filesize - free} bytes")
            auxi.standard_errorbox(f"not enough diskspace for this process, please free at least {expected_filesize - free} bytes")
            return False
        else:
            return True


    def merge2G_new(self,input_file_list):  # 2 GB in Bytes
        """configures and starts worker for merging all files in system_state["list_out_files_resampled"]
        :param: input_file_list
        :type: list
        ...
        :raises none
        ...
        :return: True if successful
        :rtype: Boolean
        """

        self.SigActivateOtherTabs.emit("Resample","inactivate",["Resample"])
        #TODO: check if listempty:
        if len(input_file_list) == 0: #TODO: check, if necessary, normally the cb_split buttonfcn catches this case
            auxi.standard_errorbox("No files to be resampled have been selected; please drag items to the 'selected file' area")
            #self.SigUpdateGUI.emit("terminate")
            #gui.SigGUIReset.emit() #TODO solve with signalling to resample_c-view
            return False
        self.m["res_blinkstate"] = True
        output_file_prefix = self.m["out_dirname"] + self.m["mergeprefix"]
        #TODO: check necessary diskfile for the filelist: get filesize of listfiles, add up, check
        # if resampler.checkdiskspace(, system_state["out_dirname"]) is False:
        #     return(False)
        self.logger.debug("merge2G: configure merge2G_ thread et al")
        self.merge2G_thread = QThread(parent = self)
        self.merge2G_worker = res_workers()
        self.merge2G_worker.moveToThread(self.merge2G_thread)
        self.merge2G_worker.set_inputfilelist(input_file_list)
        self.merge2G_worker.set_tfname(output_file_prefix)
        self.merge2G_worker.set_maxgap(self.MAX_GAP)
        self.merge2G_worker.set_readsegment(auxi.readsegment_new)
        self.merge2G_worker.set_ret(self.m["basename"])
        self.merge2G_worker.set_sttime_atrim(self.m["starttime_after_trim"])
        self.merge2G_thread.started.connect(self.merge2G_worker.merge2G_worker)
        #self.merge2G_worker.SigPupdate.connect(lambda: resample_v.updateprogress_resampling(self)) #TODO: check if lambda call is appropriate.
        self.merge2G_worker.SigPupdate.connect(self.PupdateSignalHandler)
        self.merge2G_worker.SigMergeerror.connect(self.mergeerrorhandler)
        self.merge2G_worker.SigFinishedmerge2G.connect(self.merge2G_thread.quit)
        self.merge2G_worker.SigFinishedmerge2G.connect(lambda: print("#####>>>>>>>>>>>>>>>>>merge2Gworker SigFinished_arrived"))
        self.merge2G_worker.SigFinishedmerge2G.connect(self.merge2G_worker.deleteLater)
        self.merge2G_thread.finished.connect(self.merge2G_thread.deleteLater)
        self.merge2G_thread.finished.connect(lambda: self.merge2G_cleanup(input_file_list))

        self.m["calling_worker"] = self.merge2G_worker 
        self.m["progress_source"] = "sox"
        self.m["progress"] = 0
        self.m["blinkstate"] = True
        self.m["actionlabelbg"] ="cyan"
        self.m["actionlabel"] = "MERGE 2G"
        self.m["blinking"] = False
        self.SigUpdateGUIelements.emit() #TODO: replace by Relay method ?
        self.logger.debug("merge2G: set merge2G_ actionlabel and progress update params")
        #self.sys_state.set_status(system_state)
        time.sleep(0.0001)
        self.merge2G_thread.start()
        if self.merge2G_thread.isRunning():
            self.logger.debug("merge2G: merge2G_ thread started")
        time.sleep(0.01) # wait state for worker to start up
        #print("merge2G_ action method sleep over")
        self.SigProgress.emit()       
        return(True)
    
    def mergeerrorhandler(self,_str):
        auxi.standard_errorbox(_str)

    def merge2G_cleanup(self,input_file_list):
        """cleanup temp files after merge2G thread has finished
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none 
        :rtype: none
        """
        #system_state = self.sys_state.get_status()
        #gui = self.sys_state["gui_reference"]
        #self.SigSyncTabs.emit(["_test", "resample", "a", "_teststatus", True])
        #self.SigRelay.emit("cm_all_",["wavheader",self.wavheader])
        if self.m["merge2G_deleteoriginal"]:
            for input_file in input_file_list:
                self.logger.debug(f"remove {input_file} if exists")
                if os.path.exists(input_file) == True:
                    os.remove(input_file)
        self.m["clearlist"] = True
        #print("resampler merg2G_cleanup before SigUpdateGUIelements")
        self.logger.debug("resampler merg2G_cleanup before SigUpdateGUIelements")
        self.SigUpdateGUIelements.emit()
        # gui.ui.listWidget_playlist_2.clear() #TODO: shift to a resample.view method
        # gui.ui.listWidget_sourcelist_2.clear() #TODO: shift to a resample.view method
        # gui.clear_WAVwidgets() #TODO: shift to a view method
        #gui.ui.label_36.setStyleSheet("background-color: lightgray") #TODO: shift to a resample.view method
        #TODO: check if signalling is preferrable, see other instances !

        self.m["progress_source"] = "normal"
        self.m["progress"] = 0
        self.m["blinkstate"] = False
        self.m["actionlabel"] = "JOB DONE"
        self.m["actionlabelbg"] = "lightgray"
        #print("resampler merg2G_cleanup before SigProgress")
        self.logger.debug("resampler merg2G_cleanup before SigProgress")
        self.m["blinking"] = False
        self.SigProgress.emit()
        self.SigActivateOtherTabs.emit("Resample","activate",[])
        #Therefore send a signal Siginactivate_except("resample") with the parameter indicating which tab should not be inactivated
        #The inactivation of the rest should be done by core.view
        self.m["fileopened"] = False
        #print("resampler merg2G_cleanup before SigSyncTabs")
        self.logger.debug("resampler merg2G_cleanup before SigSyncTabs")
        #self.SigSyncTabs.emit(["test","resample","a","fileopened",False])
        self.SigRelay.emit("cm_all_",["fileopened",False])  #TODO TODO TODO: das geht nicht
        self.m["list_out_files_resampled"] = []
        self.SigResampGUIReset.emit()
        self.SigRelay.emit("cexex_resample",["relay_toall_reset_GUI",0])

    def LOshifter_new(self):
        """configures and starts LO shifting thread
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none 
        :rtype: none
        """
        
        self.logger.debug("configure LOshifter _new reached")
        schedule_objdict = self.m["schedule_objdict"]
        schedule_objdict["signal"]["LOshift"].disconnect(schedule_objdict["connect"]["LOshift"])
        #TODO: activate cancellation, once cancel_method has been adapted: 

        self.SigConnectExternalMethods.emit("cancel_resampling")
        #gui.ui.pushButton_resample_cancel.clicked.connect(self.cancel_resampling) #TODO: shift to a resample.view method
        source_fn = self.m["source_fn"]  #TODO: define im GUI_Hauptprogramm bzw. im scheduler
        target_fn = self.m["target_fn"]
        self.m["progress_source"] = "sox"  #TODO: muss geändert werden ist das überhaupt nötig ?
        self.m["res_blinkstate"] = True
        self.m["blinking"] = True
        #self.sys_state.set_status(system_state)
        expected_filesize = self.m["t_filesize"] #TODO: check: trim length if cutstart(cutend must be subtracted ??)
        #TODO: check space available on target memory for expected_filesize
        if self.checkdiskspace(expected_filesize, self.m["temp_directory"]) is False:
            return False
        self.logger.debug("configure LOshifter thread et al")
        self.LOshthread = QThread(parent = self)
        self.LOsh_worker = res_workers()
        self.LOsh_worker.moveToThread(self.LOshthread)
        #TODO: generate stop and starttrim read offsets if appropriate
        startcutoffset = 0 
        if self.m["starttrim"]:
            #TODO: check if offset larger than filesize
            startcutoffset = 216 + int(self.m["start_trim"].seconds*self.m["sSR"]*self.m["s_wavheader"]['nBlockAlign'])
            self.logger.debug(f'LOshifter: set starttrim = {self.m["start_trim"]} seconds to {startcutoffset} bytes ')
        
        self.LOsh_worker.set_starttrim(startcutoffset)
        self.LOsh_worker.set_ret("")
        self.LOsh_worker.set_tfname(target_fn )
        self.LOsh_worker.set_sfname(source_fn )
        #self.LOsh_worker.set_readoffset(gui.readoffset ) #TODO: reference to system state, not gui element
        self.LOsh_worker.set_readoffset(self.m["readoffset"])
        self.LOsh_worker.set_sSR(self.m["sSR"])
        self.LOsh_worker.set_sBPS(self.m["sBPS"])
        self.LOsh_worker.set_tBPS(self.m["tBPS"])
        self.LOsh_worker.set_wFormatTag(self.m["wFormatTag"])
        self.LOsh_worker.set_centershift(self.m["fshift"])
        self.LOsh_worker.set_expfs(expected_filesize)
        #self.LOsh_worker.set_readsegment(gui.readsegment_new)  #TODO: readsegment should be part of an aux module rather than gui (== core)
        self.LOsh_worker.set_readsegment(auxi.readsegment_new)
        self.LOsh_worker.set_sBPS(self.m["sBPS"])
        self.LOshthread.started.connect(self.LOsh_worker.LO_shifter_worker)
        self.Sigincrscheduler.connect(self.res_scheduler)
        self.LOsh_worker.SigFinishedLOshifter.connect(lambda: self.Sigincrscheduler.emit())
        #z.B. schreibe die Referenz auf signal_state, damit sie der Scheduler dort abholen kann, schedule[n].["startsignal"] = diese Referenz
        #self.LOsh_worker.SigPupdate.connect(lambda: resample_v.updateprogress_resampling(self)) #TODO: eher aus der Klasse view, könnte auch ausserhalb geschehen
        self.LOsh_worker.SigPupdate.connect(self.PupdateSignalHandler)
        self.LOsh_worker.SigFinishedLOshifter.connect(self.LOshthread.quit)
        self.LOsh_worker.SigFinishedLOshifter.connect(self.LOsh_worker.deleteLater)
        self.LOshthread.finished.connect(self.LOshthread.deleteLater)
        self.m["calling_worker"] = self.LOsh_worker 
        self.m["last_system_time"] = time.time()


        self.logger.debug("about to leave LOshifter actionmethod")
        #self.sys_state.set_status(system_state)
        time.sleep(0.0001)
        self.LOshthread.start()
        if self.LOshthread.isRunning():
            self.logger.debug("LOsh thread started")
        time.sleep(0.01) # wait state so that the soxworker has already opened the file
        self.logger.debug("LOshifter action method sleep over")


    def progressupdate_interface(self):

        #print(">>>>>>>>>>>>>>>>>>>>progressupdate_interface reached")
        progress = self.m["calling_worker"].get_progress()
        self.m["progress"] = progress
        self.m["progress_source"] = "normal"


    def cancel_resampling(self):
        #TODO check how to handle and delete after change to model
        #schedule_objdict = self.m["schedule_objdict"]
        for i in range(10):
            self.logger.debug("*********______________cancel_resamp reached")
        self.m["emergency_stop"] = True
        try:
            self.sox_worker.soxworker_terminate()
        except:
            pass
        try:
            self.LOsh_worker.soxworker_terminate()
        except:
            pass
        try:
            self.merge2G_worker.soxworker_terminate()
        except:
            pass
        #TODO: activate signalling method, but no success so far: schedule_objdict["signal"]["cancel"].emit()
        self.SigDisconnectExternalMethods.emit("cancel_resampling")
        #gui.ui.pushButton_resample_cancel.clicked.disconnect(self.cancel_resampling)  #TODO: shift to a resample.view method, probably via signalling


    def resample(self):
        """_generate soxstring from parameters
            configurates and starts sox execution thread
            generates wavheader for the target file to be generated            
            gui: reference to main window object (WizardGUI)
            target_fn: target filename
            source_fn: source filename
            s_wavheader: same type as wavheader produced by SDR_wavheadertools
            tSR: target sampling rate in S/s
            tLO: target center freqiency in Hz
            sys_state: communication dictionary of data class status; accessed only by get and set methods
        :param: none
        :type: none
        ...
        :raises
        ...
        :return: target_fn
        :rtype: string
        """
        #TODO delete after change to model
        #system_state = self.sys_state.get_status()        
        #gui = self.sys_state["gui_reference"]
        schedule_objdict = self.m["schedule_objdict"]
        schedule_objdict["signal"]["resample"].disconnect(schedule_objdict["connect"]["resample"])

        source_fn = self.m["source_fn"]  #TODO: define im GUI_Hauptprogramm bzw. im scheduler
        target_fn = self.m["target_fn"]  #TODO: define im GUI_Hauptprogramm bzw. im scheduler
        tSR = self.m["tSR"]  #TODO: define im GUI_Hauptprogramm bzw. im scheduler
        self.m["progress_source"] = "sox"  #TODO: solve double function in better datacommunication structure
        if self.m['wFormatTag'] == 1:
            wFormatTag_TYPE = "signed-integer"
        elif self.m['wFormatTag']  == 3:
            wFormatTag_TYPE = "floating-point"
        else:
            auxi.standard_errorbox("wFormatTag is neither 1 nor 3; unsupported Format, this file cannot be processed")
            return False

        my_filename, filetype = os.path.splitext(os.path.basename(source_fn))
        if filetype == '.dat':
            sox_filetype = 'raw'
        else:
            sox_filetype = 'wav'
        #soxstring = 'sox --norm=-3 -e ' + wFormatTag_TYPE + ' -t  ' + sox_filetype + ' -r ' + str(self.m["sSR"]) + ' -b '+ str(self.m["sBPS"]) + ' -c 2 ' + '"' + source_fn  + '"' + ' -e signed-integer -t raw -r ' + str(int(tSR)) + ' -b ' + str(self.m["tBPS"]) + ' -c 2 '  + '"' + target_fn  + '"' 
        soxstring = 'sox -e ' + wFormatTag_TYPE + ' -t  ' + sox_filetype + ' -r ' + str(self.m["sSR"]) + ' -b '+ str(self.m["sBPS"]) + ' -c 2 ' + '"' + source_fn  + '"' + ' -e signed-integer -t raw -r ' + str(int(tSR)) + ' -b ' + str(self.m["tBPS"]) + ' -c 2 '  + '"' + target_fn  + '"' + ' gain ' + str(self.m["resampling_gain"])
        trimextension =""
        #include trim command if self.m["starttrim"] or self.m["stoptrim"] are True
        if self.m["starttrim"]:
            trimextension = " trim " + str(self.m["start_trim"])
        if self.m["stoptrim"]:
            trimextension = " trim 0 " + str(self.m["stop_trim_duration"]) 
        if self.m["starttrim"] and self.m["stoptrim"]:
            trimextension = " trim " + str(self.m["start_trim"]) + " " + str(self.m["stop_trim_reduced_duration"])
        #soxstring = soxstring + trimextension
            #TODO: trim shift to LOSHIFTER et al before sox, sox is too complex
        
        self.logger.debug(f"method resample: <<<<resampler: soxstring: {soxstring}")
        expected_filesize = self.m["t_filesize"]
        if self.checkdiskspace(expected_filesize, self.m["temp_directory"]) is False:
            return False

        self.m["res_blinkstate"] = True
        self.m["blinking"] = True
        self.m["progress_source"] = "sox" #TODO rename sox reference to something more general: worker ?????
        self.logger.debug("method resample: set flags just before soxthread")
        self.soxthread = QThread(parent = self)
        self.sox_worker = res_workers()

        self.sox_worker.moveToThread(self.soxthread)
        self.sox_worker.set_soxstring(soxstring)
        self.sox_worker.set_ret("")
        self.sox_worker.set_tfname(target_fn )
        self.sox_worker.set_expfs(expected_filesize)
        self.soxthread.started.connect(self.sox_worker.sox_writer)
        ###############################
        #v_resamp.SigCancel.connect(self.sox_worker.soxworker_terminate)
        schedule_objdict["signal"]["cancel"].connect(lambda: self.sox_worker.soxworker_terminate())

        self.Sigincrscheduler.connect(self.res_scheduler)
        self.sox_worker.SigFinished.connect(lambda: self.Sigincrscheduler.emit())
        self.sox_worker.SigSoxerror.connect(self.Soxerrorhandler)
        #z.B. schreibe die Referenz auf signal_state, damit sie der Scheduler dort abholen kann, schedule[n].["startsignal"] = diese Referenz
        #self.sox_worker.SigPupdate.connect(lambda: resample_v.updateprogress_resampling(self)) #TODO: eher aus der Klasse view, könnte auch ausserhalb geschehen
        self.sox_worker.SigPupdate.connect(self.PupdateSignalHandler)
        self.sox_worker.SigFinished.connect(self.soxthread.quit)
        self.sox_worker.SigFinished.connect(self.sox_worker.deleteLater)
        self.soxthread.finished.connect(self.soxthread.deleteLater)

        self.m["calling_worker"] = self.sox_worker 
        self.logger.debug("method resample:soxthread starting now ###########################")
        self.soxthread.start()
        if self.soxthread.isRunning():
            self.logger.debug("method resample:soxthread started")
        time.sleep(1) # wait state so that the soxworker has already opened the file
        self.logger.debug("method resample: resampler 1s sleep phase over")
        self.logger.debug("method resample: about to leave resampler")
        #self.sys_state.set_status(self.m)

    def PupdateSignalHandler(self):
        progress = self.m["calling_worker"].get_progress()
        self.m["progress"] = progress
        self.m["progress_source"] = "normal"
        self.SigUpdateGUIelements.emit() #TODO replace by Relay method ?

    def Soxerrorhandler(self,errorstring):

        #self.m = self.sys_state.get_status()
        #gui = self.m["gui_reference"]
        self.m["emergency_stop"] = True

        self.logger.debug(f"soxerrorhandler errorstring: {errorstring}")
        #self.sys_state.set_status(self.m)
        self.Sigincrscheduler.emit()
        auxi.standard_errorbox("Error produced by SOX, probably due to inconsistent cutting times; process terminated")
        #TODO: push GUI into a safe state: leave scheduler process and reset GUI, resample_c GUI 
        
    def accomplish_resampling(self):
        """_after sox-resampling a wav_fileheader is inserted into the resampled dat-File.
        Afterwards  and temporary files are removed
        this method is called via a signal from the soxwriter worker function sox_writer() after finishing the process
        communication occurs only via state variables, as this function is called asynchronously on signal emission
                self.m["tgt_wavheader"]: wavheader to be inserted
                self.m["new_name"]: name to which the temporary targetfile (targetfilename) should be renamed after processing
                self.m["targetfilename"]: complete target file path
                self.m["file_to_be_removed"]: temporary file to be removed if it exists
        :param: none
        :type: none
        ...
        :raises
        ...
        :return: none
        :rtype: none
        """
        #system_state = self.sys_state.get_status()
        #gui = self.sys_state["gui_reference"]
        schedule_objdict = self.m["schedule_objdict"]
        schedule_objdict["signal"]["accomplish"].disconnect(schedule_objdict["connect"]["accomplish"])
        time.sleep(0.1)
        self.Sigincrscheduler.connect(self.res_scheduler)
        if self.m["accomp_label"] == True:
            self.logger.debug("accomplish reached twice: return without action")
            return
        self.m["accomp_label"] = True
        self.logger.debug("accomplish_resampling: soxstring thread finished")
        target_fn = self.m["source_fn"]  #TODO: define im GUI_Hauptprogramm bzw. im scheduler
        self.m["progress"] = 0
        self.SigUpdateGUIelements.emit() #TODO replace by Relay method ?
        #gui.ui.progressBar_resample.setProperty("value", 0) #TODO: shift to a resample.view method, replace by signalling ?
        #self.soxthreadActive = False  #TODO: check is obsolete
        self.logger.debug(f"accomplish reached, target_fn: {target_fn}")
        if os.path.exists(target_fn) == True:
            file_stats = os.stat(target_fn)
        else:
            auxi.standard_errorbox("Accomplish: File not found, severe error, terminate resampling procedure")
            return False
        tgt_wavheader = self.m["s_wavheader"]
        tgt_wavheader['filesize'] = file_stats.st_size
        tgt_wavheader['data_nChunkSize'] = tgt_wavheader['filesize'] - 208
        tgt_wavheader['nSamplesPerSec'] = int(self.m["tSR"])

        ###############TODOTODOTODO######################################################
        #entferne nextfilename und korrigiere nAvgBytesPerSec
        header_config = [int(1),"data","auxi",int(164),self.m["tBPS"],int(self.m["tBPS"]/4),int(self.m["readoffset"]),int(self.m["tLO"])] #TODO check obsolete ?
        tgt_wavheader = self.resamp_configheader(tgt_wavheader,header_config)
        tgt_wavheader['nAvgBytesPerSec'] = int(tgt_wavheader['nSamplesPerSec']*int(self.m["tBPS"]/4))
        ovwrt_flag = True
        time.sleep(1)
        WAVheader_tools.write_sdruno_header(self,target_fn,tgt_wavheader,ovwrt_flag)
        time.sleep(5)
        #if new_name exists --> delete
        newname = self.m["new_name"]
        if os.path.exists(newname) == True:  ## TODO CHECK IF TRY
            self.logger.debug("accomplish remove newname")
            os.remove(self.m["new_name"])
        self.logger.debug(f"accomplisher: new name: {newname}")
        self.logger.debug(f"accomplisher: target_fn: {target_fn}")
        # Renaming the file
        #TODO: make try ! and repeat if fail until temp file is accessible
        exitcount = 0
        while True:
            try:
                self.logger.debug ("accomplish: try shutil")
                shutil.move(target_fn, self.m["new_name"])
                break
            except:
                exitcount += 1
                time.sleep(2)
                self.logger.debug(f"accomplish_resampling: access to {target_fn} not possible retry after 2 s")
                if exitcount > 20:
                    self.logger.debug("accomplish impossible, give up")
                    return False
        #shutil.move(target_fn, self.m["new_name"]) #TODO. cannot shift last temp file to external directory (ext. harddisk)
        self.m["t_wavheader"] = tgt_wavheader
        #self.sys_state.set_status(system_state)
        self.logger.debug("accomplish leave after signalling to scheduler")   
        self.Sigincrscheduler.emit()

    
    def res_scheduler(self):
        #TODO: check if logsox.txt file contains error message
        #if yes: terminate running schedule and print error message

        #system_state = self.sys_state.get_status()
                            ###################AKTUELLER HALTEPUNKT
        #gui = self.sys_state["gui_reference"]
        cnt = self.m["r_sch_counter"]
        sch = self.m["res_schedule"]
            
        if self.m["emergency_stop"]:
            self.m["progress"] = 0
            self.m["progress_source"] = "normal"
            self.SigProgress.emit()
            sch[cnt]["action"] = 'terminate'
            #TODO: besser: cnt auf length(sch) setzen
            self.logger.debug(f"emergency exit, length (sch) = {len(sch)}")
            cnt = len(sch) - 1
            sch[cnt]["action"] = 'terminate'#Obsolete, remove after tests

        self.Sigincrscheduler.disconnect(self.res_scheduler)##############TODOTODOTODO
        self.logger.debug("res_scheduler: reached scheduler")
        tests = sch[cnt]["action"]
        self.logger.debug(f"res_scheduler: count: {cnt}, sch.action: {tests}")
        schedule_objdict = self.m["schedule_objdict"]
        self.m["actionlabel"] = sch[cnt]["actionlabel"]
        self.m["sSR"] = sch[cnt]["sSR"]
        self.m["tSR"] = sch[cnt]["tSR"]
        self.m["sBPS"] = sch[cnt]["sBPS"]
        self.m["tBPS"] = sch[cnt]["tBPS"]
        self.m["sfilesize"] = sch[cnt]["s_filesize"]
        self.m["wFormatTag"] = sch[cnt]["wFormatTag"]
        self.m["t_filesize"] = sch[cnt]["t_filesize"]
        self.m["target_fn"] = self.m["temp_directory"] + "/temp_" + str(cnt) + '.dat' #<<< NEW vs LOshifter : filename automatism

        fid = open(self.m["target_fn"], 'w')
        fid.close()
        if cnt == 0:
            self.m["accomp_label"] = False
        if cnt > 0:
            self.m["source_fn"] = self.m["temp_directory"] + "/temp_" + str(cnt-1) + '.dat' #<<< NEW vs LOshifter : filename automatism

        self.logger.debug(f'res_scheduler: targetfilename: {self.m["target_fn"]}')
        self.logger.debug(f'res_scheduler: sourcefilename: {self.m["source_fn"]}')
        if cnt > 1:
            remfile = self.m["temp_directory"] + "/temp_" + str(cnt-2) + '.dat'
            #remove old temp file
            if os.path.exists(remfile) == True:
                self.logger.debug("new accomplish: remfile: " + remfile)
                try:
                    os.remove(remfile)
                except:
                    self.logger.debug("cannot remove temp file on exception (maybe emergency exit)")

        if sch[cnt]["blinkstate"]:
            self.m["res_blinkstate"] = True
        else:
            self.m["res_blinkstate"] = False
            
        self.m["r_sch_counter"] += 1
        if sch[cnt]["action"].find('terminate') == 0:
            self.logger.debug("res_scheduler:  start termination")
            self.m["r_sch_counter"] = 0 #terminate schedule, reset counter
            #self.sys_state.set_status(system_state)
            # self.SigSyncTabs.emit(["resample","resample","u","actionlabelbg",'lightgray'])
            # self.SigSyncTabs.emit(["resample","resample","u","label36Font",'12'])
            # self.SigUpdateOtherGUIs.emit()
            self.m["actionlabelbg"] = "lightgray"
            self.m["label36Font"] = 12
            #gui.ui.label_36.setStyleSheet("background-color: lightgray") #TODO: shift to a resample.view method, treat in a different manner
            #gui.ui.label_36.setFont(QFont('arial',12)) #TODO: shift to a resample.view method, treat in a different manner
            #setze Signal ab, das GUI Update auslöst:
            #TODO: lade das letzte resampelte File ?? aber erst wenn ganze eventloop abgearbeitet
            #self.m["f1"] = self.m["new_name"] #TODO: CHEKC TESTEN 17-12-2023
            #self.SigUpdateGUI.connect(self.update_GUI) #TODO: check gui reference
            #self.SigUpdateGUI.emit("terminate") #TODO:  check gui reference
            time.sleep(0.01)
            #TODO TODO: check change 14-12-2023: self.SigUpdateGUI.disconnect(self.update_GUI) #TODO:  check gui reference
            self.SigActivateOtherTabs.emit("Resample","activate",[]) #TODO: why is that necessary ?
            #gui.activate_tabs(["View_Spectra","Annotate","Resample","YAML_editor","WAV_header","Player"])  #TODO: organiz in different manner; this class needs not know about other tabs !
            #Therefore send a signal Siginactivate_except("resample") with the parameter indicating which tab should not be inactivated
            #The inactivation of the rest should be done by core.view
            #self.sys_state.set_status(system_state)
            #TODO: lösche alle temp files, die evt hängengeblieben sind (garbage collection)'
            #temppath = os.getcwd() #TODO: check change on 12-01-2024
            temppath = self.m["temp_directory"]
            for x in os.listdir(temppath):
                if x.find("temp_") == 0:
                    try:
                        os.remove(x)
                    except:
                        self.logger.debug("res_scheduler terminate: file access to temp file refused")
            self.SigUpdateGUIelements.emit()
            #self.SigTerminate_Finished.connect(gui.cb_resample_new)  # TODO: muss resample_v.cb_resample_new sein
            self.SigTerminate_Finished.connect(self.m["_ref_cb_resample"])
            self.SigTerminate_Finished.emit() #general signal for e.g. cb_resampler
            #    gui.activate_tabs(["View_Spectra","Annotate","Resample","YAML_editor","WAV_header","Player"]) #TODO: organiz in different manner; this class needs not know about other tabs !
            #Therefore send a signal Siginactivate_except("resample") with the parameter indicating which tab should not be inactivated
            #The inactivation of the rest should be done by core.view
            return

        #self.sys_state.set_status(system_state)

        if sch[cnt]["action"].find('resample') == 0:
            self.logger.debug("res_scheduler: : resample rechaed, emit signal resample")
            schedule_objdict["signal"]["resample"].connect(schedule_objdict["connect"]["resample"])
            schedule_objdict["signal"]["resample"].emit()
            time.sleep(0.01)
            #schedule_objdict["signal"]["resample"].disconnect(schedule_objdict["connect"]["resample"])
            pass
        if sch[cnt]["action"].find('accomplish') == 0:
            #self.logger.debug("res_scheduler: accomplish rechaed, emit signal accomplish")
            #self.SigSyncTabs.emit(["resample","resample","u","label36text",'FINALIZE'])

            #gui.ui.label_36.setText('FINALIZE') #TODO: shift to a resample.view method, treat in a different manner: model variable change and then update signal
            #self.sys_state.set_status(self.m) #TODO: shift to a resample.view method, treat in a different manner: model variable change and then update signal
            #TODO: gleicher Aufruf wie in 'resample':
            schedule_objdict["signal"]["accomplish"].connect(schedule_objdict["connect"]["accomplish"])
            schedule_objdict["signal"]["accomplish"].emit()
            time.sleep(0.01)
            #schedule_objdict["signal"]["accomplish"].disconnect(schedule_objdict["connect"]["accomplish"])
        if sch[cnt]["action"].find('LOshift') == 0:
            self.logger.debug("res_scheduler: LOshift rechaed, emit signal LOshift")
            #TODO: gleicher Aufruf wie in 'resample':
            schedule_objdict["signal"]["LOshift"].connect(schedule_objdict["connect"]["LOshift"])
            schedule_objdict["signal"]["LOshift"].emit()
        if sch[cnt]["action"].find('progress') == 0:
            self.logger.debug("res_scheduler:  progressupdate rechaed, no action")

    def schedule_A(self):
        """_definition of schedule for simple resampling without LO shift
        :param: none, communication only via self.m
        :type: none
        ...
        :raises none
        ...
        :return: none
        :rtype: none
        """
        self.logger.debug("start define resampling schedule A, no LOshift, pure resampling")

        #system_state = self.sys_state.get_status()
        self.m["r_sch_counter"] = 0
        target_SR = self.m["target_SR"] 
        target_LO = self.m["target_LO"]
        schedule = []

        wavheader = self.m['s_wavheader']
        sch1 = {}
        sch1["action"] = "resample"
        sch1["blinkstate"] = True
        sch1["actionlabel"] = "RESAMPLE"
        sch1["sSR"] = wavheader['nSamplesPerSec']
        sch1["tSR"] = float(target_SR)*1000
        sch1["tBPS"] = 16   #TODO: tBPS flexibel halten !
        sch1["sBPS"] = wavheader['nBitsPerSample']
        sch1["s_filesize"] = wavheader['filesize'] # TODO: source filesize better determine from true filesize
        ##########TODO: remove after checking 2024-01-06
        #file_stats = os.stat(self.m["f1"])#TODO: replace by line below
        file_stats = os.stat(self.m["f1"])
        ##########EXPERIMENT file_stats = self.m["f1"]
        sch1["s_filesize"] = (file_stats.st_size - self.m["readoffset"])
        sch1["t_filesize"] = np.ceil(sch1["s_filesize"]*sch1["tSR"]/sch1["sSR"]*sch1["tBPS"]/sch1["sBPS"])
        sch1["wFormatTag"] = wavheader['wFormatTag'] #source formattag; no previous LOshifter,thus Format of sourcefile

        schedule.append(sch1)
        sch2 = {}
        sch2["action"] = "accomplish"
        sch2["blinkstate"] = False
        sch2["actionlabel"] = "ACCOMPLISH"
        sch2["sSR"] = float(target_SR)*1000 
        sch2["tSR"] = float(target_SR)*1000
        sch2["sBPS"] = 16 #Dummy , plays no role in terminate
        sch2["tBPS"] = 16 #Dummy , plays no role in terminate
        sch2["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["wFormatTag"] = 1 #source formattag
        schedule.append(sch2)
        sch3 = {}
        sch3["action"] = "terminate"
        sch3["blinkstate"] = False
        sch3["actionlabel"] = ""
        sch3["sSR"] = float(target_SR)*1000
        sch3["tSR"] = float(target_SR)*1000
        sch3["sBPS"] = 16 #Dummy , plays no role in terminate
        sch3["tBPS"] = 16 #Dummy , plays no role in terminate
        sch3["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["wFormatTag"] = 1 #source formattag
        schedule.append(sch3)

        self.m["res_schedule"] = schedule
        #self.sys_state.set_status(system_state)

    def schedule_B(self):
        """_definition of schedule for  resampling with previous LO shift
        do not use for files with BPS = 24bit; use version schedule_B24(self) in that case
        :param: none, communication only via self.m
        :type: none
        ...
        :raises none
        ...
        :return: none
        :rtype: none
        """
        self.logger.debug("start define resampling schedule B, with LOshift")

        #system_state = self.sys_state.get_status()
        self.m["r_sch_counter"] = 0
        target_SR = self.m["target_SR"] 
        target_LO = self.m["target_LO"]
        schedule = []

        wavheader = self.m['s_wavheader']
        sch0 = {}
        sch0["action"] = "LOshift"
        sch0["blinkstate"] = True
        sch0["actionlabel"] = "LO shifting"
        sch0["sSR"] = wavheader['nSamplesPerSec'] 
        sch0["tSR"] = sch0["sSR"]
        sch0["sBPS"] = wavheader['nBitsPerSample']
        sch0["tBPS"] = 32 # TODO check if this should be always so: always defined so for LOshifter
        sch0["wFormatTag"] = wavheader['wFormatTag']
        sch0["s_filesize"] = wavheader['filesize'] 
        #file_stats = os.stat(self.m["f1"]) #TODO: replace by line below
        file_stats = os.stat(self.m["f1"])
        sch0["s_filesize"] = (file_stats.st_size - self.m["readoffset"])

        sch0["t_filesize"] = int(sch0["s_filesize"]*sch0["tBPS"]/sch0["sBPS"])
        schedule.append(sch0)

        sch1 = {}
        sch1["action"] = "resample"
        sch1["blinkstate"] = True
        sch1["actionlabel"] = "RESAMPLE"
        sch1["sSR"] = wavheader['nSamplesPerSec']
        sch1["tSR"] = float(target_SR)*1000
        sch1["tBPS"] = 16   #TODO: tBPS flexibel halten !
        sch1["sBPS"] = sch0["tBPS"]
        sch1["s_filesize"] = sch0["t_filesize"]
        sch1["t_filesize"] = sch1["s_filesize"]*sch1["tSR"]/sch1["sSR"]*sch1["tBPS"]/sch1["sBPS"]
        sch1["wFormatTag"] = 3 #source formattag; the previous LOshifter has produced 32bit IEEE float 32

        schedule.append(sch1)
        sch2 = {}
        sch2["action"] = "accomplish"
        sch2["blinkstate"] = False
        sch2["actionlabel"] = "ACCOMPLISH"
        sch2["sSR"] = float(target_SR)*1000 
        sch2["tSR"] = float(target_SR)*1000
        sch2["sBPS"] = 16 #Dummy , plays no role in terminate
        sch2["tBPS"] = 16 #Dummy , plays no role in terminate
        sch2["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["wFormatTag"] = 1 #source formattag
        schedule.append(sch2)
        sch3 = {}
        sch3["action"] = "terminate"
        sch3["blinkstate"] = False
        sch3["actionlabel"] = ""
        sch3["sSR"] = float(target_SR)*1000
        sch3["tSR"] = float(target_SR)*1000
        sch3["sBPS"] = 16 #Dummy , plays no role in terminate
        sch3["tBPS"] = 16 #Dummy , plays no role in terminate
        sch3["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["wFormatTag"] = 1 #source formattag
        schedule.append(sch3)

        self.m["res_schedule"] = schedule
        #self.sys_state.set_status(system_state)

    def schedule_B24(self):
        """_definition of schedule for  resampling with previous LO shift
        do not use for files with BPS = 24bit; use version schedule_B24(self) in that case
        :param: none, communication only via self.m
        :type: none
        ...
        :raises none
        ...
        :return: none
        :rtype: none
        """
        self.logger.debug("start define resampling schedule B24, 24bit LOSHift with resampling")

        #system_state = self.sys_state.get_status()
        self.m["r_sch_counter"] = 0
        target_SR = self.m["target_SR"] 
        target_LO = self.m["target_LO"]
        schedule = []

        wavheader = self.m['s_wavheader']

        sch_m1 = {}
        sch_m1["action"] = "resample"
        sch_m1["blinkstate"] = True
        sch_m1["actionlabel"] = "RESAMPLE 24/32"
        sch_m1["sSR"] = wavheader['nSamplesPerSec'] 
        sch_m1["tSR"] = float(target_SR)*1000  # sch_m1["sSR"]
        sch_m1["sBPS"] = wavheader['nBitsPerSample']
        sch_m1["tBPS"] = 32
        sch_m1["wFormatTag"] = wavheader['wFormatTag']
        sch_m1["s_filesize"] = wavheader['filesize']
        #file_stats = os.stat(self.m["f1"]) #TODO remove line below
        file_stats = os.stat(self.m["f1"])
        sch_m1["s_filesize"] = (file_stats.st_size - self.m["readoffset"])

        sch_m1["t_filesize"] = np.ceil(sch_m1["s_filesize"]*sch_m1["tSR"]/sch_m1["sSR"]*sch_m1["tBPS"]/sch_m1["sBPS"])
        sch_m1["wFormatTag"] = wavheader['wFormatTag'] #source formattag; no previous LOshifter,thus Format of sourcefile
        schedule.append(sch_m1)

        sch0 = {}
        sch0["action"] = "LOshift"
        sch0["blinkstate"] = True
        sch0["actionlabel"] = "LO shifting"
        sch0["sSR"] = sch_m1["tSR"]
        sch0["tSR"] = sch0["sSR"]
        sch0["sBPS"] = 32
        sch0["tBPS"] = 32 # TODO check if this should be always so: always defined so for LOshifter
        sch0["wFormatTag"] = 1 #the previus resampler has produced integer values, resmpler prod always signed-integer
        sch0["s_filesize"] = sch_m1["t_filesize"] 
        sch0["t_filesize"] = sch0["s_filesize"]*sch0["tSR"]/sch0["sSR"]*sch0["tBPS"]/sch0["sBPS"]
        schedule.append(sch0)

        sch1 = {}
        sch1["action"] = "resample"
        sch1["blinkstate"] = True
        sch1["actionlabel"] = "RESAMPLE F"
        sch1["sSR"] = sch0["tSR"]
        sch1["tSR"] = sch1["sSR"] # float(target_SR)*1000
        sch1["tBPS"] = 16   #TODO: tBPS flexibel halten !
        sch1["sBPS"] = sch0["tBPS"]
        sch1["s_filesize"] = sch0["t_filesize"]
        sch1["t_filesize"] = sch1["s_filesize"]*sch1["tSR"]/sch1["sSR"]*sch1["tBPS"]/sch1["sBPS"]
        sch1["wFormatTag"] = 3 #source formattag; the previous LOshifter has produced 32bit IEEE float 32

        schedule.append(sch1)
        sch2 = {}
        sch2["action"] = "accomplish"
        sch2["blinkstate"] = False
        sch2["actionlabel"] = "ACCOMPLISH"
        sch2["sSR"] = float(target_SR)*1000 
        sch2["tSR"] = float(target_SR)*1000
        sch2["sBPS"] = 16 #Dummy , plays no role in terminate
        sch2["tBPS"] = 16 #Dummy , plays no role in terminate
        sch2["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch2["wFormatTag"] = 1 #source formattag
        schedule.append(sch2)
        sch3 = {}
        sch3["action"] = "terminate"
        sch3["blinkstate"] = False
        sch3["actionlabel"] = ""
        sch3["sSR"] = float(target_SR)*1000
        sch3["tSR"] = float(target_SR)*1000
        sch3["sBPS"] = 16 #Dummy , plays no role in terminate
        sch3["tBPS"] = 16 #Dummy , plays no role in terminate
        sch3["s_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["t_filesize"] = 0 #Dummy , plays no role in terminate
        sch3["wFormatTag"] = 1 #source formattag
        schedule.append(sch3)
        self.m["res_schedule"] = schedule
        #self.sys_state.set_status(system_state)


class resample_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["viewvars"]

    SigAny = pyqtSignal()
    SigUpdateList = pyqtSignal()
    SigCancel = pyqtSignal()
    #SigUpdateGUI = pyqtSignal(object)
    #SigSyncTabs = pyqtSignal(object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigUpdateOtherGUIs = pyqtSignal()
    SigRelay = pyqtSignal(str,object)

    def __init__(self, gui, resample_c, resample_m):
        super().__init__()

    # def __init__(self, *args, **kwargs): #TEST 09-01-2024
    #     super().__init__(*args, **kwargs)
        viewvars = {}
        self.set_viewvars(viewvars)
        self.m = resample_m.mdl
        self.resample_c = resample_c #resample_c can now be used as instance of the resampler controller for signallng
        #self.sys_state = wsys.status() #TEST: commented out 09-01-2024
        #self.sys_state = gui_state
        #system_state = self.sys_state.get_status()
        self.m["reslistdoubleemit_ix"] = False
        self.m["starttrim"] = False
        self.m["stoptrim"] = False
        self.m["actionlabelbg"] = "lightgray"
        self.m["label36Font"] = 12
        self.m["actionlabel"] = ""
        self.m["_ref_cb_resample"] = self.cb_resample #TODO: ckeck if really necessary
        self.m["progress"] = 0
        self.m["progress_source"] = "normal"
        self.m["my_filename"] = ""
        self.m["ext"] = ""
        self.m["res_blinkstate"] = False
        self.m["emergency_stop"] = False
        self.m["blinking"] = False
        self.m["position"] = 0
        self.logger = resample_m.logger
        self.resample_c.SigRelay.connect(self.rxhandler)
        self.resample_c.SigRelay.connect(self.SigRelay.emit)
        self.gui = gui #gui_state["gui_reference"]#system_state["gui_reference"]
        self.init_resample_ui() #TODO TODO TODO: activate after tests
        self.gui.radioButton_resgain.setChecked(False)
        self.gui.label_8.setEnabled(False)  #TODO: maybe remove, Unidentified
        self.gui.pushButton_resample_cancel.clicked.connect(self.resample_c.cancel_resampling) #TODO: shift to a resample.view method
        self.resample_c.SigDisconnectExternalMethods.connect(self.ext_meth_disconnect)
        self.resample_c.SigConnectExternalMethods.connect(self.ext_meth_connect)
        self.gui.listWidget_playlist_2.itemClicked.connect(self.reslist_itemselected) #TODO transfer to resemplar view
        self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
        self.gui.checkBox_merge_selectall.clicked.connect(self.toggle_mergeselectall)
        self.gui.checkBox_merge_selectall.setEnabled(False)
        #self.sys_state.set_status(system_state)
        self.DATABLOCKSIZE = 1024*32
        self.gui.pushButton_resample_cancel.clicked.connect(self.resample_c.cancel_resampling) #TODO: shift to a resample.view method
        #self.resample_c.SigUpdateGUI.connect(self.update_GUI)
        self.resample_c.SigResampGUIReset.connect(self.reset_resamp_GUI_elemets)
        self.resample_c.SigUpdateGUIelements.connect(self.updateGUIelements)

        #check if sox is installed so as to throw an error message on resampling, if not
        self.soxlink = "https://sourceforge.net/projects/sox/files/sox/14.4.2/"
        self.soxlink_altern = "https://sourceforge.net/projects/sox"
        self.soxnotexist = False

        try:
            subproc3 = subprocess.run('sox -h', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, check=True)
        except subprocess.CalledProcessError as ex:
            #print("sox FAIL")
            self.logger.error("sox FAIL")
            print(ex.stderr, file=sys.stderr, end='', flush=True)
            #print(ex.stdout, file=sys.stdout, end='', flush=True)
            if len(ex.stderr) > 0: 
                self.soxnotexist = True

        schedule_objdict = {}
        schedule_objdict["signal"] = {}
        schedule_objdict["signal"]["resample"] = resample_c.SigResample
        schedule_objdict["signal"]["accomplish"] = resample_c.SigAccomplish
        schedule_objdict["signal"]["LOshift"] = resample_c.SigLOshift
        #schedule_objdict["signal"]["updateGUI"] = resample_c.SigUpdateGUI
        schedule_objdict["connect"] = {}
        schedule_objdict["connect"]["resample"] = resample_c.resample
        schedule_objdict["connect"]["accomplish"] = resample_c.accomplish_resampling
        schedule_objdict["connect"]["LOshift"] = resample_c.LOshifter_new
        #schedule_objdict["connect"]["updateGUI"] = self.update_GUI
        schedule_objdict["signal"]["cancel"] = self.SigCancel
        self.m["schedule_objdict"] = schedule_objdict
        #self.updateGUIelements()

    def init_resample_ui(self):
        """
        Resampler VIEW initialization
        initializes all GUI elements of the Tab resampler
        TODO: all references are still 'self', check !
        :param: npne
        :type: none
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        self.gui.timeEdit_resample_stopcut.setEnabled(False)
        self.gui.timeEdit_resample_startcut.setEnabled(False)
        self.gui.pushButton_resample_resample.clicked.connect(self.cb_Butt_resample)
        self.gui.comboBox_resample_targetSR.setCurrentIndex(5)
        self.gui.comboBox_resample_targetSR.currentIndexChanged.connect(lambda: self.plot_spectrum_resample(self.m["position"]))
        self.gui.lineEdit_resample_targetLO.textChanged.connect(lambda: self.plot_spectrum_resample(self.m["position"]))
        self.gui.radioButton_advanced_sampling.clicked.connect(lambda: self.toggle_advanced_sampling())
        self.gui.radioButton_resgain.clicked.connect(lambda: self.toggle_gain())
        self.gui.lineEdit_resample_targetLO.textChanged.connect(lambda: self.reformat_targetLOpalette)
        self.gui.lineEdit_resample_targetLO.textEdited.connect(lambda: self.reformat_targetLOpalette)
        self.gui.lineEdit_resample_Gain.textChanged.connect(lambda: self.read_gain())
        #self.gui.lineEdit_resample_Gain.textChanged.connect(resample_v.read_gain)
        self.gui.lineEdit_resample_Gain.setText("0")
        self.gui.lineEdit_resample_Gain.setEnabled(True)
        self.gui.radioButton_resgain.setEnabled(True)
        self.gui.label_Filename_resample.setText('')
        self.gui.pushButton_resample_split2G.clicked.connect(self.cb_split2G_Button)
        #self.gui.checkBox_writelog.clicked.connect(self.togglelogmodus) #TODO TODO TODO: logfilemodus anders implementieren

    def rxhandler(self,_key,_value):
        """
        handles remote calls from other modules via Signal SigRX(_key,_value)
        :param : _key
        :type : str
        :param : _value
        :type : object
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        if _key.find("cm_resample") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
        if _key.find("cui_resample") == 0:
            _value[0](_value[1])   #TODO TODO: still unclear implementation
        if _key.find("cexex_resample") == 0  or _key.find("cexex_all_") == 0:
            # if  _value[0].find("plot_spectrum") == 0:
            #     self.plot_spectrum(0,_value[1])
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()    
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("enable_resamp_GUI_elements") == 0:
                self.enable_resamp_GUI_elemets(_value[1])
            if  _value[0].find("addplaylistitem") == 0:
                self.addplaylistitem()
            if  _value[0].find("fillplaylist") == 0:
                self.fillplaylist()      
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])
            if  _value[0].find("relay_toall_reset_GUI") == 0:
                self.SigRelay.emit("cexex_all_",["reset_GUI",0])

    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("resample: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.debug("resample: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)

    def reformat_targetLOpalette(self): #TODO: check, if this stays part of gui or should be shifted to resampler module
        """
        VIEW Element of Tab 'resample
        """
        self.ui.lineEdit_resample_targetLO.setStyleSheet("background-color: bisque1")

    def cb_Butt_resample(self):
        try:
            self.ui.listWidget_playlist_2.itemChanged.disconnect(self.reslist_update)
        except:
            pass
        self.cb_resample()
        self.gui.radioButton_advanced_sampling.setChecked(False)

    def ext_meth_disconnect(self,ctrl):
        if ctrl.find("cancel_resampling"):
            self.gui.pushButton_resample_cancel.clicked.disconnect(self.resample_c.cancel_resampling)
        else:
            #print("error in resample_v, ext_meth_disconnect ")
            self.logger.error("error in resample_v, ext_meth_disconnect ")

    def ext_meth_connect(self,ctrl):
        if ctrl.find("cancel_resampling"):
            self.gui.pushButton_resample_cancel.clicked.connect(self.resample_c.cancel_resampling)
        else:
            self.logger.debug("error in resample_v, ext_meth_connect ")
            self.logger.error("error in resample_v, ext_meth_connect ")

    def GUI_reset_status(self):
        self.m["resampling_gain"] = 0
        self.m["emergency_stop"] = False
        self.m["timescaler"] = 0
        self.m["fileopened"] = False
        #self.SigSyncTabs(["dum","resample","a","fileopened",False])
        self.SigRelay.emit("cm_all_",["fileopened",False])
        self.m["ifreq"] = 0  #TODO: chekc is that needed ???????????
        self.m["irate"] = 0
        self.m["icorr"] = 0
        self.m["actionlabel"] = ""
        self.m["LO_offset"] = 0
        self.m["playlist_ix"] = 0
        self.m["reslist_ix"] = 0
        self.m["list_out_files_resampled"] = []
        self.m["playlist_active"] = False
        self.m["progress"] = 0
        self.m["temp_LOerror"] = False
        self.m["starttrim"] = False
        self.m["stoptrim"] = False

    def updateGUIelements(self):
        """
        updates GUI elements , usually triggered by a Signal SigTabsUpdateGUIs to which 
        this method is connected in the __main__ of the core module
        :param : none
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        #print(f"resampler: updateGUIelements {self.m['progress']}")
        self.logger.debug("resampler: updateGUIelements progress: %f", self.m['progress'] )
        self.gui.label_Filename_resample.setText(self.m["my_filename"] + self.m["ext"])
        self.gui.label_36.setStyleSheet("background-color: " + self.m["actionlabelbg"])
        self.gui.label_36.setFont(QFont('arial',self.m["label36Font"]))
        self.gui.label_36.setText(self.m["actionlabel"])
        self.gui.lineEdit_resample_targetLO.setText(str((self.m["wavheader"]["centerfreq"]/1000)))

        self.gui.progressBar_resample.setProperty("value", self.m["progress"])
        if self.m["emergency_stop"]:
            self.GUI_reset_status()
            self.m["Tabref"]["Resample"]["ax"].clear()
            self.m["Tabref"]["Resample"]["canvas"].draw()
            self.m["clearlist"] = True
        if self.m["clearlist"]:
            self.gui.listWidget_playlist_2.clear()
            self.gui.listWidget_sourcelist_2.clear()
            #TODO TODO TODO: IMPLEMENT RESET OF wav-editor 
            # either: set wav_editor.mdl[clearwavwidgets] True via Signal, implement respective call to wav_editor_v.clear_WAVwidgets() in wav_editor_v.GUI-updatemethod and emit SigUpdateOtherGUIs 
            # or: dedicatet signal to address clear_WAVwidgets() method in wavheader editor
            #self.gui.clear_WAVwidgets() #TODO: shift to a view method
        self.m["clearlist"] = False
        #updateprogress_resampling
        self.updateprogress_resampling()
        self.gui.label_Filename_resample.setText(self.m["my_filename"] + self.m["ext"])
        #TODO TODO TODO: update plot spectrum
        self.plot_spectrum_resample(0)

    def reset_GUI(self):
        """
        VIEW
        TODO: nach den einzelnen Tabs zerlegen
        reset GUI elements to their defaults, re-initialize important variables
        code is executed after new file open
        :param none
        :type: none
        :raises [ErrorType]: [ErrorDescription]TODO
        :return: True after completion, False if status-yaml not accessible
        :rtype: boolean
        """
        self.m["actionlabelbg"] ="lightgray"
        self.m["label36Font"] = 12
        self.m["actionlabel"] = "READY"
        #self.updateGUIelements()
        self.m["Tabref"]["Resample"]["ax"].clear()
        self.m["Tabref"]["Resample"]["canvas"].draw()
        self.gui.label_Filename_resample.setText("")
        self.m["res_blinkstate"] = False
        self.gui.listWidget_playlist_2.clear()
        self.gui.listWidget_sourcelist_2.clear()
        self.gui.label_Filename_resample.setText('')
        self.gui.checkBox_merge_selectall.setChecked(False)
        self.gui.lineEdit_resample_targetnameprefix.setText('')
        self.gui.label_36.setText('')
        self.gui.label_36.setFont(QFont('arial',12))
        self.gui.label_36.setStyleSheet("background-color: lightgray")

    def addplaylistitem(self):
        item = QtWidgets.QListWidgetItem()
        self.gui.listWidget_sourcelist_2.addItem(item)

    def fillplaylist(self):
        playlist = []
        ix = 0
        for x in os.listdir(self.m["my_dirname"]):
            if x.endswith(".wav"):
                if True: #x != (self.m["my_filename"] + self.m["ext"]): #TODO: obsolete old form when automatically loading opened file to playlist
                    #resfilelist.append(x) #TODO: used ?????????
                    _item=self.gui.listWidget_sourcelist_2.item(ix)
                    _item.setText(x)
                    fnt = _item.font()
                    fnt.setPointSize(11)
                    _item.setFont(fnt)
                    item = QtWidgets.QListWidgetItem()
                    self.gui.listWidget_sourcelist_2.addItem(item)
                    ix += 1
        #erzeuge einen Eintrag in Playlist listWidget_playlist
        if self.m["f1"].endswith(".wav"):
            item = QtWidgets.QListWidgetItem()
            self.gui.listWidget_playlist_2.addItem(item)
            _item=self.gui.listWidget_playlist_2.item(0)
            _item.setText(self.m["my_filename"] + self.m["ext"])
            fnt = _item.font()
            fnt.setPointSize(11)
            _item.setFont(fnt)
            playlist.append(self.m["f1"])
            self.m["playlist"] = playlist
        self.gui.listWidget_playlist_2.setEnabled(False)
        self.gui.listWidget_sourcelist_2.setEnabled(False)


    def set_viewvars(self,_value):
        self.__slots__[0] = _value

    def get_viewvars(self):
        return(self.__slots__[0])


    # def update_GUI(self,_key): #TODO TODO: is this method still needed ? reorganize. gui-calls should be avoided, better only signalling and gui must call the routenes itself
    #     #print(" res_updateGUI: new updateGUI in resampler module reached")
    #     self.logger.debug(" res_updateGUI: new updateGUI in resampler module reached")
    #     self.SigUpdateGUI.disconnect(self.update_GUI)
    #     if _key.find("reset") == 0:
    #         #print("resampler reset all checked elements")
    #         self.logger.debug("resampler reset all checked elements")
    #         self.reset_resamp_GUI_elemets()
    #         self.gui.lineEdit_resample_targetnameprefix.setEnabled(True) #TODO: shift to a resample.view method        
    #     if _key.find("terminate") == 0:
    #         #print("termination GUI update not yet defined")
    #         self.logger.debug("termination GUI update not yet defined")
    #     if _key.find("ext_update") == 0:
    #         #update resampler gui with all elements
    #         #TODO: fetch model values and re-fill all tab fields
    #         pass
    #     #other key possible: "none"
    #     time.sleep(1)
    #     self.SigUpdateGUI.connect(self.update_GUI)

    def reslist_update(self): #TODO: list is only updated up to the just before list change dragged item,
        """
        VIEW
        updates resampler list whenever the playlist Widget is changed.
        (1) read self.m 
        (2) generate list of files 'reslist' to be resampled from the listWidget for with the files to be resampled (playlist_2)
        (3) write reslist to system state
        (4) set self.m["f1] (file currently operated on) to the first listentry
        (5) set cutting start and stoptimes from wavheaders of first and last files in the list
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        #print("#######!!!!!!!!!!!!!!    reslist_update !!!!!!!! ############")
        #print("reslist_update: resampling list updated")  
        self.logger.debug("reslist_update: resampling list updated")
        time.sleep(0.1)
        lw = self.gui.listWidget_playlist_2
        reslist = []
        for x in range(lw.count()):
            item = lw.item(x)
            reslist.append(item.text())
        self.m["reslist"] = reslist
        #print(f"reslist_update:reslist: {reslist}")
        self.logger.debug("reslist_update:reslist: %s", reslist)
        #system_state["f1"] = self.gui.my_dirname + '/' + reslist[0]  #TODO: replace by line below
        #self.m["f1"] = self.gui.my_dirname + '/' + reslist[0] #TODO: replace self.mydirname by status entry
        self.m["f1"] = self.m["my_dirname"] + '/' + reslist[0]
        #print(f'reslist_update:cb_resample: file: {system_state["f1"]}') #TODO: replace by line below
        #print(f'reslist_update:cb_resample: file: {self.m["f1"]}')
        self.logger.debug("reslist_update:cb_resample: file:  %s", self.m["f1"] )

        #self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,system_state["f1"]) #TODO: replace by line below
        ####################PROBLEM ??????????????????????????? wavheader in core aktivieren ?
        #self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"]) #TODO: why gui wavheader ?

        #self.gui.showfilename()
        ############SET CORRECT FILENAME
        self.gui.label_Filename_resample.setText(self.m["my_filename"] + self.m["ext"])
        #self.gui.label_Filename_resample.setText(self.my_filename + self.ext)

        self.plot_spectrum_resample(0)

        #TODO: fetch starttime of the first file and stoptime of the last file to copy the values to the starttime_cut and stoptime_cut windows of the GUI
        wavheader1 = WAVheader_tools.get_sdruno_header(self,(self.m["my_dirname"] + '/' + self.m["reslist"][0]))
        wavheader2 = WAVheader_tools.get_sdruno_header(self,(self.m["my_dirname"] + '/' + self.m["reslist"][-1]))
        if not wavheader1:
            auxi.standard_errorbox("This file does not have a known SDR wav header - cannot be loaded")
            #print("This file does not have a known SDR wav header - cannot be loaded")
            self.logger.warning("This file does not have a known SDR wav header - cannot be loaded")
            return(False)
              
        self.m["reslist_starttime1"] = wavheader1['starttime_dt']
        self.m["reslist_stoptime1"] = wavheader1['stoptime_dt']
        self.m["reslist_starttime2"] = wavheader2['starttime_dt']
        self.m["reslist_stoptime2"] = wavheader2['stoptime_dt']


        self.gui.timeEdit_resample_startcut.setDateTime(wavheader1['starttime_dt'])
        self.gui.timeEdit_resample_stopcut.setDateTime(wavheader2['stoptime_dt'])
        _valid,errortext = self.getCuttime()
        if not _valid:
            auxi.standard_errorbox(errortext)
            #self.sys_state.set_status(system_state)
            return(False)
        #print("reslist_update:resampler view reslist terminated")
        self.logger.debug("reslist_update:resampler view reslist terminated")
        #self.sys_state.set_status(system_state)


    def reslist_itemselected(self,item):
        """
        VIEW
        show clicked item in resampler list whenever an item is clicked
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        #print(f"reslist: item clicked, itemtext: {item.text()}")        
        #system_state["f1"] = self.gui.my_dirname + '/' + item.text() #TODO: replace by line below
        self.m["f1"] = self.m["my_dirname"] + '/' + item.text() #TODO: replace self.mydirname by status entry
        self.m["my_filename"], self.m["ext"] = os.path.splitext(item.text())
        #print(f'cb_resample: file: {system_state["f1"]}')
        #self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,system_state["f1"]) #TODO: replace by line below
        self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])

        #self.gui.showfilename()

        #################TODO: implement next line newly with Relay after tarnsfer of wavedit module 
        #self.gui.fill_wavtable()
        self.SigRelay.emit("cexex_waveditor",["updateGUIelements",0])
        ##################DONE
        self.update_resample_GUI()
        #TODO: update also spectra view
        self.SigRelay.emit("cm_all_",["my_filename",self.m["my_filename"]])
        self.SigRelay.emit("cm_all_",["ext",self.m["ext"]])
        self.SigRelay.emit("cm_all_",["f1",self.m["f1"]])
        self.SigRelay.emit("cm_all_",["wavheader",self.m["wavheader"]])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])      ####################RELAY PATTERN############


        #self.plot_spectrum_resample(0)

        
    def toggle_mergeselectall(self):
        """
        gets checkstatus of button for selecting all items of reslist and calls the respective handler
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        if self.gui.checkBox_merge_selectall.isChecked():
            self.selectall_reslist()
        else:
            self.unselectall_reslist()

    def selectall_reslist(self): #TODO: not yet used
        """
        selects all items of the resampling sourcelist_2 and moves to the resampling-list in playlist_2
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        self.gui.listWidget_playlist_2.clear()
        for row in range(self.gui.listWidget_sourcelist_2.count()-1):
            item = self.gui.listWidget_sourcelist_2.item(row)
            self.gui.listWidget_playlist_2.addItem(item.text())
        self.gui.listWidget_sourcelist_2.clear()

    def unselectall_reslist(self): #TODO: not yet used
        """
        unselects all items of the resampling playlist_2 and moves to the sourcelist_2
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """ 
        self.gui.listWidget_sourcelist_2.clear()
        for row in range(self.gui.listWidget_playlist_2.count()):
            item = self.gui.listWidget_playlist_2.item(row)
            self.gui.listWidget_sourcelist_2.addItem(item.text())
        item = QtWidgets.QListWidgetItem()
        self.gui.listWidget_sourcelist_2.addItem(item)
        self.gui.listWidget_playlist_2.clear()


    def plot_spectrum_resample(self,position):
        """assign a plot window and a toolbar to the tab 'resample' and plot data from currently loaded file at position 'position'
        :param : position
        :type : int
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        #TODO: define: ax_res, canvas_resample
        # gui.ui.lineEdit_resample_targetLO.setStyleSheet("background-color: white")
        # gui.ui.lineEdit_resample_Gain.setText('')
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        if self.m["fileopened"] == False:
            return(False)
        else:
            #data = self.readsegment() ##TODO: position ist die des scrollbars im View spectra tab, das ist etwas unschön. Man sollte auch hier einen scrollbar haben, der mit dem anderen synchronisiert wird
            pscale = self.m["wavheader"]['nBlockAlign']
            position = int(np.floor(pscale*np.round(self.m["wavheader"]['data_nChunkSize']*self.m["horzscal"]/pscale/1000)))
            #ret = self.gui.readsegment(position,self.DATABLOCKSIZE)  ##TODO: position ist die des scrollbars im View spectra tab, das ist etwas unschön. Man sollte auch hier einen scrollbar haben, der mit dem anderen synchronisiert wird
            #NEW 08-12-2023 #######################TODO###################### tBPS not yet clear
            #ret = self.gui.readsegment_new(system_state["f1"],position,self.DATABLOCKSIZE,self.m["wavheader"]["nBitsPerSample"],
            #                         32,self.m["wavheader"]["wFormatTag"]) #TODO: replace by line below
            ret = auxi.readsegment_new(self,self.m["f1"],position,self.m["readoffset"],self.DATABLOCKSIZE,self.m["wavheader"]["nBitsPerSample"],
                                      32,self.m["wavheader"]["wFormatTag"])
            ####################################################################################
            data = ret["data"]
            if 2*ret["size"]/self.m["wavheader"]["nBlockAlign"] < self.DATABLOCKSIZE:
                return False
            # TODO: replace by new invalidity condition
            # if len(data) == 10:
            #     if np.all(data == np.linspace(0,9,10)):
            #         return False
            #NEW: 
            # if len(data) < self.DATABLOCKSIZE
            #     return False
            self.m["Tabref"]["Resample"]["ax"].clear()
            realindex = np.arange(0,self.DATABLOCKSIZE,2)
            imagindex = np.arange(1,self.DATABLOCKSIZE,2)
            #calculate spectrum and shift/rescale appropriately
            spr = np.abs(np.fft.fft((data[realindex]+1j*data[imagindex])))
            N = len(spr)
            spr = np.fft.fftshift(spr)
            flo = self.m["wavheader"]['centerfreq'] - self.m["wavheader"]['nSamplesPerSec']/2
            fup = self.m["wavheader"]['centerfreq'] + self.m["wavheader"]['nSamplesPerSec']/2
            freq0 = np.linspace(0,self.m["wavheader"]['nSamplesPerSec'],N)
            freq = freq0 + flo
            datax = freq
            datay = 20*np.log10(spr)
            self.m["Tabref"]["Resample"]["ax"].plot(datax,datay, '-')
            self.m["Tabref"]["Resample"]["ax"].set_xlabel('frequency (Hz)')
            self.m["Tabref"]["Resample"]["ax"].set_ylabel('amplitude (dB)')                
            #plot bandlimits of resampling window
            target_SR = float(self.gui.comboBox_resample_targetSR.currentText())*1000
            #lineEdit_resample_targetLO          
            target_LO_test = self.gui.lineEdit_resample_targetLO.text()
            numeraltest = True
            if not target_LO_test[0].isdigit():
                numeraltest = False
            target_LO_test = target_LO_test.replace(".", "")
            if not target_LO_test[1:].isdigit():
                numeraltest = False
            if numeraltest == False:
                auxi.standard_errorbox("invalid characters, must be numeric float value !")
                return False
            try:
                target_LO = float(self.gui.lineEdit_resample_targetLO.text())*1000
            except TypeError:
                #print("plot_res_spectrum: wrong format of TARGET_LO")
                self.logger.error("plot_res_spectrum: wrong format of TARGET_LO")
                auxi.standard_errorbox("invalid characters, must be numeric float value !")
                #TARGET_LO = self.m["wavheader"]['centerfreq']
                return False
            except ValueError:
                #print("plot_res_spectrum: wrong format of TARGET_LO")
                self.logger.error("plot_res_spectrum: wrong format of TARGET_LO")
                auxi.standard_errorbox("invalid characters, must be numeric float value !")
                #TARGET_LO = self.m["wavheader"]['centerfreq']
                return False
            xlo = target_LO - target_SR/2
            xup = target_LO + target_SR/2
            self.m["Tabref"]["Resample"]["ax"].vlines(x=[target_LO], ymin = [min(datay)], ymax = [max(datay)], color = "C1")
            self.m["Tabref"]["Resample"]["ax"].add_patch(Rectangle((xlo, min(datay)), xup-xlo, max(datay)-min(datay),edgecolor='red',
                facecolor='none', fill = False,
                lw=4))
            self.m["Tabref"]["Resample"]["canvas"].draw()
        return(True)

    def updateprogress_resampling(self):
        """_duringr sox-resampling the progress of sox resampling is indicated in the progressbar.
        The active state is indicated by blinking of the label field label_36
        this method is called via a signal from the soxwriter worker function sox_writer() repetitively every second
        communication occurs only via state variables, as this function is called asynchronously on signal emission
                system_state["res_blinkstate"]
        :param: none
        :type: none
        ...
        :raises
        ...
        :return: none
        :rtype: none
        """
        #system_state = self.sys_state.get_status()
        #################################DO NOT REPLACE CURRENTLY !
        #gui = system_state["gui_reference"]  #TODO: gui cannot be easily replaced by self.gui because lambda calls from the resampler controller an dworker modules 
        # refer to 'self' as another self, unclean programming ; search for solution later !!!!!!!!!!!!!!!!!
        if self.m["blinking"] is False:
            return
        blink_free = False
        current_time = time.time()  
        if current_time - self.m["last_system_time"] >= 1:
            self.m["last_system_time"] = current_time
            blink_free = True

        if self.m["progress_source"].find('normal') > -1:  #TODO: solve double function in better datacommunication structure
            progress = self.m["progress"]
        elif self.m["progress_source"].find('sox') > -1:
            #change 26_11_2023: beforechange: progress = system_state["sox_worker"].get_progress() #TODO: dazu muss aber system_state["sox_worker"] erst einmal existieren 
            progress = self.m["calling_worker"].get_progress() #TODO: check wie gewährleistet (aktuell im action_method beim thread konfigurieren): dazu muss aber system_state["sox_worker"] erst einmal existieren 
        else:
            #print("update_progress_resamping: error, progress source system flag invalid")
            self.logger.error("update_progress_resamping: error, progress source system flag invalid")
            #self.sys_state.set_status(self.m)
            return False
        #self.SigUpdateGUIelements.emit()
        self.m["progress"] = progress
        #self.updateGUIelements()
        #self.gui.progressBar_resample.setProperty("value", progress)

        #print(f"statusbar updater sysflags_progress_source: {progress}")
        self.m["actionlabelbg"] = "lightgray"
        self.m["label36Font"] = 12
        #self.gui.label_36.setText(self.m["actionlabel"])
        #self.gui.label_36.setFont(QFont('arial',12))
        #print(f'statusbar updater actionlabel: {system_state["actionlabel"]}')
        if blink_free:
            if self.m["res_blinkstate"]:
                self.m["actionlabelbg"] = "yellow"
                #self.gui.label_36.setStyleSheet("background-color: yellow")
            else:
                self.m["actionlabelbg"] = "orange"
                #self.gui.label_36.setStyleSheet("background-color: orange")
            self.m["res_blinkstate"] = not self.m["res_blinkstate"]
        #print(f" updateprogress_resampling res blinkstate: {self.m['res_blinkstate']} color: {self.m['actionlabelbg']}")
        #self.sys_state.set_status(system_state)
        #self.updateGUIelements()
        #self.SigUpdateGUIelements.emit()

    def update_resample_GUI(self): #wurde ins resampler-Modul verschoben
        """fills the control elements of the resample GUI with parameters from the wav header
        RESAMPLER VIEW !!
        :param [ParamName]: none
        :type [ParamName]: none
        ...
        :raises [ErrorType]: [ErrorDescription]TODO
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        #self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])

        self.gui.timeEdit_resample_startcut.setDateTime(self.m["wavheader"]['starttime_dt']) #TODO check access to core, necessary ?
        self.gui.timeEdit_resample_stopcut.setDateTime(self.m["wavheader"]['stoptime_dt'])#TODO check access to core, necessary ?
        self.gui.lineEdit_resample_targetLO.setText(str((self.m["wavheader"]['centerfreq']/1000)))#TODO check access to core, necessary ?

        #self.gui.lineEdit_resample_Gain.setText(str(0))
        #self.gui.comboBox_resample_targetSR.setCurrentIndex(5)
        try:
            self.plot_spectrum_resample(self.m["spectrum_position"])
        except:
            self.plot_spectrum_resample(0)
        self.gui.label_Filename_resample.setText(self.m["my_filename"] + self.m["ext"]) #TODO: take over list name
        #self.gui.showfilename() # TODO: in future versions check if this should be a gui-method
        #print("cb_resample reached")
        if not(self.m["wavheader"]['wFormatTag'] in [1,3]): #TODO:future system state
            auxi.standard_errorbox("wFormatTag is neither 1 nor 3; unsupported Format, this file cannot be processed")
            #self.sys_state.set_status(system_state)
            return False
        #TODO: check if rates, irate can be deduced internally or must be imported from core
        signtab = list(np.sign(list(self.m["rates"].keys())-self.m["irate"]*np.ones(len(self.m["rates"]))))
        #print(signtab)
        try:
            sugg_index = signtab.index(0.0) # index of SR == irate, if exists
        except:
            try:
                sugg_index = signtab.index(1.0) # else index of first positive outcome = index of SR slightly above irate
            except:
                auxi.standard_errorbox("unsupported sampling rate in filename, this file cannot be processed")
                #self.sys_state.set_status(system_state)
                return False
        #set selection of SR to suggested value
        #self.gui.comboBox_resample_targetSR.setCurrentIndex(sugg_index)
        #self.sys_state.set_status(system_state)
        #print("#######!!!!!!!!!!!!!!    update resample GUI !!!!!!!! ############")
        self.logger.debug("#######!!!!!!!!!!!!!!    update resample GUI !!!!!!!! ############")

    def getCuttime(self):
        """calculate trimming values for trimming self.m["stop_trim"] from the beginning of the first reslist file 
        and stopcut seconds from the beginning of the last reslist file to be passed to the soxstring synthesis
        (1) get wavheader of the first file and display it on all Tabs
        (2) get starttime from timeEdit_resample_startcut  and write to self.m["starttrim"]
        (3) get stoptime from timeEdit_resample_stopcut and write to self.m["stoptrim"]
        function is called by cb_resample in the reslist-handler both at the first listelement and the last list element.
        Function calculates the trimming information for soxstring generation and stores it in          
        self.m["stop_trim_duration"] and self.m["start_trim"] 
        :param [ParamName]: none
        :type [ParamName]: none
        ...
        :raises [ErrorType]: [ErrorDescription]TODO
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        startcut = self.gui.timeEdit_resample_startcut.dateTime().toPyDateTime() #datetime object
        stopcut = self.gui.timeEdit_resample_stopcut.dateTime().toPyDateTime()

        self.m["stop_trim_duration"] = (stopcut - self.m["reslist_starttime2"])
        if self.m["starttrim"] and self.m["stoptrim"]:
            self.m["stop_trim_reduced_duration"] = (stopcut - startcut)
            #TODO: rename, can be confuse with self.m["starttrim"]
        self.m["start_trim"] = (startcut - self.m["reslist_starttime1"])
        self.m["starttime_after_trim"] = startcut

        if startcut > self.m["reslist_stoptime1"]:
            return(False, f'start cut time must be less than {self.m["reslist_stoptime1"]}')
        if startcut < self.m["reslist_starttime1"]:
            return(False, f'start cut time must be > {self.m["reslist_starttime1"]}')              
        if self.m["stop_trim_duration"].seconds < 0:
            return(False, f'stop cut time must be less than {self.m["reslist_stoptime2"]}')
        if stopcut < self.m["reslist_starttime2"]:
            return(False, f'stop cut time must be greater than or equal to {self.m["reslist_starttime2"]}')   
        #print(f"get Cuttime: cutstart datetime: {startcut} cutstop datetime: {stopcut}")
        self.logger.debug("get Cuttime: cutstart datetime: %s cutstop datetime: %s", startcut, stopcut)
        #self.sys_state.set_status(system_state)
        return(True,"")


    def toggle_advanced_sampling(self):
        """
        :param [ParamName]: none
        :type [ParamName]: none
        ...
        :raises [ErrorType]: [ErrorDescription]TODO
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        if self.gui.radioButton_advanced_sampling.isChecked():
            self.gui.listWidget_sourcelist_2.setEnabled(True)
            self.gui.listWidget_playlist_2.setEnabled(True)
            self.gui.listWidget_playlist_2.clear()
            #self.gui.timeEdit_resample_stopcut.setEnabled(True)
            #self.gui.timeEdit_resample_startcut.setEnabled(True)
            self.gui.checkBox_merge_selectall.setEnabled(True)
            self.gui.lineEdit_resample_targetnameprefix.setEnabled(True)
            # gui.ui.lineEdit_resample_Gain.setEnabled(True)
            # gui.ui.radioButton_resgain.setEnabled(True)
        else:
            self.gui.listWidget_sourcelist_2.setEnabled(False)
            self.gui.listWidget_playlist_2.setEnabled(False)
            self.gui.timeEdit_resample_stopcut.setEnabled(False)
            self.gui.timeEdit_resample_startcut.setEnabled(False)
            self.gui.lineEdit_resample_Gain.setEnabled(True)
            self.gui.checkBox_merge_selectall.setEnabled(False)
            #self.gui.lineEdit_resample_targetnameprefix.setEnabled(False)
            # gui.ui.radioButton_resgain.setChecked(False)
            # gui.ui.radioButton_resgain.setEnabled(False)


    def reset_resamp_GUI_elemets(self):
        """
        reset GUI elements depending which have been checked
        :param [ParamName]: status
        :type [ParamName]: Boolean
        ...
        :raises [ErrorType]: none
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        self.gui.listWidget_sourcelist_2.clear()
        self.gui.listWidget_playlist_2.clear()
        self.gui.lineEdit_resample_Gain.setText("0")
        self.gui.radioButton_advanced_sampling.setChecked(False)
        self.gui.checkBox_merge_selectall.setChecked(False)
        self.gui.radioButton_resgain.setChecked(False)
        self.gui.checkBox_AutoMerge2G.setChecked(False)
        self.enable_resamp_GUI_elemets(True)
        self.gui.lineEdit_resample_targetnameprefix.setEnabled(True)
        self.gui.lineEdit_resample_targetnameprefix.setText("")
        #self.gui.progressBar_resample.setProperty("value", 0)
        self.m["progress"]
        self.m["actionlabelbg"] ="lightgray"
        self.m["label36Font"] = 12
        self.m["actionlabel"] = "READY"
        self.updateGUIelements()


    def enable_resamp_GUI_elemets(self,status):
        """
        enables or disables resampling GUI elements depending on 'status': True or False
        :param [ParamName]: status
        :type [ParamName]: Boolean
        ...
        :raises [ErrorType]: none
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        self.gui.listWidget_sourcelist_2.setEnabled(status)
        self.gui.listWidget_playlist_2.setEnabled(status)
        #self.gui.timeEdit_resample_stopcut.setEnabled(status)
        #self.gui.timeEdit_resample_startcut.setEnabled(status)
        self.gui.lineEdit_resample_Gain.setEnabled(status)
        self.gui.lineEdit_resample_targetLO.setEnabled(status)
        self.gui.comboBox_resample_targetSR.setEnabled(status)
        self.gui.radioButton_advanced_sampling.setEnabled(status)
        self.gui.pushButton_resample_resample.setEnabled(status)
        self.gui.pushButton_resample_split2G.setEnabled(status)
        
        #self.gui.pushButton_resample_GainOnly.setEnabled(status)
        self.gui.lineEdit_resample_targetnameprefix.setEnabled(status)

    def toggle_gain(self):
        """
        :param [ParamName]: none
        :type [ParamName]: none
        ...
        :raises [ErrorType]: [ErrorDescription]TODO
        ...
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """
        self.logger.debug("resampler_module_5 toggle_gain reached")
        #system_state = self.sys_state.get_status() #TODO: --> self.gui
        #gui = system_state["gui_reference"]
        if self.gui.radioButton_resgain.isChecked():
            pass
            #self.m["resampling_gain"] = 0
        else:
            self.m["resampling_gain"] = 0

            self.gui.lineEdit_resample_Gain.setText("0") #TODO: --> self.gui
            #self.sys_state.set_status(system_state)

    def read_gain(self):
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"]
        gain = self.gui.lineEdit_resample_Gain.text()
        numeraltest = True
        #TODO: check for negative sign
        if not gain.replace(".", "").isnumeric():
            numeraltest = False
        #gain = gain.replace(".", "")
        # if not gain[1:].isdigit():
        #     numeraltest = False
        if numeraltest == False:
            auxi.standard_errorbox("invalid characters, must be numeric float value !")
            return False
        try:
            fgain = float(gain)
        except TypeError:
            #print("resampling gain: wrong format of manual gain")
            self.logger.error("resampling gain: wrong format of manual gain")
            auxi.standard_errorbox("invalid characters, must be numeric float value !")
            #TARGET_LO = self.m["wavheader"]['centerfreq']
            return False
        except ValueError:
            #print("resampling gain: wrong format of manual gain")
            self.logger.error("resampling gain: wrong format of manual gain")
            auxi.standard_errorbox("invalid characters, must be numeric float value !")
            #TARGET_LO = self.m["wavheader"]['centerfreq']
            return False
        self.m["resampling_gain"] = fgain
        #ctrlist = ["view_spectra", "resample", "u", "resampling_gain", fgain]
        #self.SigSyncTabs.emit(ctrlist)
        self.SigRelay.emit("cm_view_spectra",["resampling_gain",fgain])   ####################RELAY PATTERN############
        #self.sys_state.set_status(system_state)
        #self.gui.plot_spectrum(self,0) #TODO: --> self.gui
        #self.SigRelay.emit(self,0)
        self.SigRelay.emit("cexex_view_spectra",["plot_spectrum",0])      ####################RELAY PATTERN############
        
        #print("emit SigRelay with 1 argument")
        #self.SigRelay.emit(0,0)

        #TODO: Gain wird nicht nachgezogen: core Methode die Gain nachzieht !
        #TODO: alternativ: Gain wird als neuer Parameter bei plot spectrum eingeführt
        #TODO: Scrollbar des plot_spectrum wird aktuell mit Position nicht nachgezogen: core_methode die selbes Signal abonniert und nachzieht

    def cb_split2G_Button(self):
        #system_state = self.sys_state.get_status()
        #gui = system_state["gui_reference"] #TODO: --> self.gui
        self.enable_resamp_GUI_elemets(False)

        reslist_len = self.gui.listWidget_playlist_2.count()
        self.gui.pushButton_resample_split2G.clicked.disconnect(self.cb_split2G_Button) #TODO: --> self.gui
        reslist = []
        for ix in range(reslist_len):
            lw = self.gui.listWidget_playlist_2 #TODO: --> self.gui
            item = lw.item(ix)
            reslist.append(self.m["my_dirname"] + '/' + item.text()) #TODO: --> self.gui
        #print(f"cb_split2G_Button {reslist}")
        self.logger.debug("cb_split2G_Button %s ", reslist)
        self.m["mergeprefix"] = "/temp_split_"
        #TODO_create separate out directory
        #self.m["out_dirname"] = self.m["out_dirname"] + "_split"
        if len(reslist) == 0:
            auxi.standard_errorbox("No files to be resampled have been selected; please drag items to the 'selected file' area")
            self.gui.pushButton_resample_split2G.clicked.connect(self.cb_split2G_Button)
            #self.resample_c.SigUpdateGUI.emit("reset")
            #self.gui.SigGUIReset.emit() #TODO solve with signalling to resample_c-view
            return False

        self.m["t_wavheader"] = WAVheader_tools.get_sdruno_header(self,reslist[0])

        #TODO: trage hier die Startzeit vom Cuttingstart ein
        #TODO: beim merge only sollten aber dann die start/stoptime Felder inaktiv sein
        self.gui.timeEdit_resample_stopcut.setEnabled(False)
        self.gui.timeEdit_resample_startcut.setEnabled(False)

        self.m["starttime_after_trim"] = self.m["t_wavheader"]["starttime_dt"]
        self.m["last_system_time"] = time.time()    
        self.m["res_blinkstate"] = True
        self.m["merge2G_deleteoriginal"] = False
        self.m["merge2G_gainenable"] = True
        self.m["resampling_gain"] = 0

        #self.sys_state.set_status(system_state)
        #self.resample_c.merge2G_files(reslist) #TODO: remove/restore tests: 17-01-2024
        #TODO: check new worker based implementation
        self.gui.lineEdit_resample_targetnameprefix.setEnabled(False)
        self.m["basename"] = self.gui.lineEdit_resample_targetnameprefix.text()
        self.resample_c.merge2G_new(reslist)

    def cb_resample(self):
        """_summary_
        VIEW: cb of Tab resampler
        :return: _description_
        :rtype: _type_
        """
        #inactivate all tabs except own and View spectra
        self.SigActivateOtherTabs.emit("Resample","inactivate",["Resample"])
        try:
            self.gui.listWidget_playlist_2.itemChanged.disconnect(self.reslist_update)
        except:
            pass
        try:
            self.resample_c.SigTerminate_Finished.disconnect()
        except:
            pass
        # update GUI elements
        self.gui.pushButton_resample_GainOnly.setEnabled(False)
        self.enable_resamp_GUI_elemets(False)
        #stop if exception (e.g. cancellation)
        if self.m["emergency_stop"] is True:
            self.m["emergency_stop"] = False
            #print("emergency stop in cb_resample")
            self.logger.warning("emergency stop in cb_resample")
            self.m["reslist_ix"] = 0
            self.logger.debug("resamle list has been terminated, reset counter and exit event loop")
            self.gui.listWidget_playlist_2.clear()
            self.gui.listWidget_sourcelist_2.clear()
            time.sleep(0.1)
            self.m["fileopened"] = False
            self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
            self.gui.SigGUIReset.emit()
            self.m["list_out_files_resampled"] = []
            return False
        #check for sox as a prerequisite
        if self.soxnotexist:
            infotext = "<font size = 12> You must install sox before being able to resample; <br> Download from: <br><a href='%s'>sox version 14.2.2 </a> <br><br>Either install sox to RFCorder directory or set the system path to the sox installation directory. <br> See also RFCorder user manual; </font>" % self.soxlink
            msg = QMessageBox()
            msg.information(self, 'Message', infotext, QMessageBox.Ok, QMessageBox.Ok)
            self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
            return False
        #check if filepath has been defined
        if not self.m["fileopened"]:
            auxi.standard_errorbox("You must open a file before resampling")
            self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
            return False
        #define path for temporary files
        self.m["mergeprefix"] = "/temp_resized_"
        self.m["r_sch_counter"] = 0
        self.m["blinking"] = False
        #define final targetfilename
        target_SR = self.gui.comboBox_resample_targetSR.currentText()
        try:
            target_LO = float(self.gui.lineEdit_resample_targetLO.text())
        except TypeError:
            auxi.standard_errorbox("LO Type error, please correct; must be integer value")
            return False
        self.m["target_SR"] = target_SR
        self.m["target_LO"] = target_LO
        self.m["starttrim"] = False
        self.m["stoptrim"] = False

        #loop through file list to be resampled
        reslist_len = self.gui.listWidget_playlist_2.count()
        if reslist_len > 0: #file list has at least one entry
            if self.m["reslist_ix"] < reslist_len:    #file list not yet finished
                self.logger.debug(f"cb_resample: reslist index: {self.m['reslist_ix']}")
                lw = self.gui.listWidget_playlist_2
                self.logger.debug("cb_resample: fetch next reslist file")
                item = lw.item(self.m["reslist_ix"])
                item.setBackground(QtGui.QColor("lightgreen"))  #TODO: shift to resampler view
                self.m["my_filename"], self.m["ext"] = os.path.splitext(item.text())
                #TODO: entrypoint f cutstop, cutstart:
                #(1) cut first file: copy from fseek (cutstart) to cutstop
                self.m["f1"] = self.m["my_dirname"] + '/' + item.text()
                self.logger.debug(f'cb_resample: file: {self.m["f1"]}')
                self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])
                #set filename in all other tabs: CHECK: maybe necessary in view spectra but not necessarily in others ?
                #self.SigSyncTabs.emit(["dum","resample","a","my_filename",self.m["my_filename"]])
                #self.SigSyncTabs.emit(["dum","resample","a","ext",self.m["ext"]])
                self.SigRelay.emit("cm_all_",["my_filename",self.m["my_filename"]])
                self.SigRelay.emit("cm_all_",["ext",self.m["ext"]])
                
                self.SigUpdateOtherGUIs.emit()

                # TODO: check for cutting information
                if self.m["reslist_ix"] == 0:
                    self.m["starttrim"] = True
                    _valid,errortext = self.getCuttime()
                if self.m["reslist_ix"] == reslist_len-1:
                    self.m["stoptrim"] = True
                    _valid,errortext = self.getCuttime()
                #TODO: check must be done wrt complementary ime (stop, start) of the same file, in a list they are different --> wavheadr info important
            else: #file list has been finished finished
                self.m["reslist_ix"] = 0
                self.logger.debug("resamle list has been terminated, reset counter and exit event loop")
                #TODO TODO TODO: reset GUI and set bg of listelements from green away 
                time.sleep(0.1)
                # start mege2G if checked 
                if self.gui.checkBox_AutoMerge2G.isChecked():
                    if not self.m["emergency_stop"]:
                        self.m["merge2G_deleteoriginal"] = True
                        self.m["merge2G_gainenable"] = False
                        #TODO: check new worker based implementation
                        self.gui.lineEdit_resample_targetnameprefix.setEnabled(False)
                        self.m["basename"] = self.gui.lineEdit_resample_targetnameprefix.text()
                        self.m["progress"] = 0
                        self.m["actionlabelbg"] ="cyan"
                        self.m["actionlabel"] = "MERGE2G"
                        self.updateGUIelements()
                        #call resample_c method for merging
                        self.resample_c.merge2G_new(self.m["list_out_files_resampled"])
                #regardless whether automerge or not, enable GUI, reset GUI, disable fileopened, update other GUIs
                self.enable_resamp_GUI_elemets(True)
                self.m["fileopened"] = False
                #self.SigSyncTabs.emit(["dum", "resample", "a", "fileopened", False])
                self.SigRelay.emit("cm_all_",["fileopened", self.m["fileopened"]])
                self.SigUpdateOtherGUIs.emit()
                self.SigActivateOtherTabs.emit("Resample","activate",[])
                self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
                if not self.gui.checkBox_AutoMerge2G.isChecked():
                    self.reset_GUI()
                self.m["list_out_files_resampled"] = []
                self.SigRelay.emit("cexex_all_",["reset_GUI",0])
                #self.resample_c.SigTerminate_Finished.disconnect(self.cb_resample_new)
                return
        else: #file list is empty
            auxi.standard_errorbox("No files to be resampled have been selected; please drag items to the 'selected file' area")
            #self.sys_state.set_status(system_state)
            self.gui.listWidget_playlist_2.itemChanged.connect(self.reslist_update)
            self.enable_resamp_GUI_elemets(True)
            return False

        self.m["reslist_ix"] += 1

        #check for invalid File formats
        if not(self.m["wavheader"]['wFormatTag'] in [1,3]): #TODO:future system state
            auxi.standard_errorbox("wFormatTag is neither 1 nor 3; unsupported Format, this file cannot be processed")
            return False

        #generate SDRUno TimeDate suffix in Filename
        SDRUno_suffix = str(self.m["wavheader"]['starttime_dt'])
        SDRUno_suffix = SDRUno_suffix.replace(" ","_")
        SDRUno_suffix = SDRUno_suffix.replace(":","")
        SDRUno_suffix = SDRUno_suffix.replace("-","")
        #TODO: OBSOLETE ?:
        targetfilename = self.m["my_dirname"] + "/" + self.m["f1"] + "_rspli16_" + str(SDRUno_suffix) + '_' + str(int(np.round(self.m["wavheader"]["centerfreq"]/1000))) + 'kHz.dat'
        # get info on frequency shifting, and target parameters:
        self.m["tLO"] = target_LO*1000 #TODO: define im scheduler ??
        self.m["fshift"] = self.m["wavheader"]["centerfreq"] - self.m["tLO"]
        self.m["tSR"] = float(target_SR)*1000 # tSR #TODO: define im scheduler ??
        self.m["s_wavheader"] = self.m["wavheader"]  #TODO: define im scheduler ?
        self.m["source_fn"] = self.m["f1"] #TODO: define im scheduler ?
        self.m["target_fn"] = targetfilename #TODO: obsolete ? define im scheduler ?

        #TODO TODO TODO: Abfragen, ob genug Speicherplatz für temp und Zielfiles
        if self.m["wavheader"]['sdrtype_chckID'].find('auxi') == -1:
            self.logger.debug("resampling of rcvr and dat format not yet fully tested, may be problematic")
            #TODO: untersuchen, wie rcvr hier zu machen ist; an sich sollte das kein Problem sein, da ja der wavheader ohnehin bereits auf auxi umgeschrieben ist
            #return False          
        #self.SigActivateOtherTabs.emit("Resample","inactivate",["View spectra"]) #TODO: necessary ? has been done at the beginning already
        
        time.sleep(0.01)

            ####TODO CHECK !!!!!!!!!!!!!!!!!!!!! filesize wird hier falsch ermittelt, wenn rcvr files o.ä.

        #Generate schedules for the scheduler event loop
        #CASE 1: normal resampling without LOshift, LOshift is ignored
        if abs(self.m["fshift"]) > 1e-5: #LOShift wanted
            if self.m["wavheader"]['nBitsPerSample'] == 24:
                self.resample_c.schedule_B24()
                self.logger.debug("generate schedule for 24 LOshifting")
            else:
                if self.m["tSR"] > self.m["wavheader"]["nSamplesPerSec"]:
                    self.logger.debug("generate schedule for 32/16 LOshifting with upsampling")
                    self.resample_c.schedule_B24()
                else:
                    self.logger.debug("generate schedule for 32/16 LOshifting with downsampling")
                    self.resample_c.schedule_B()
        else: #no LOShift
            self.resample_c.schedule_A()
            self.logger.debug("generate schedule for simple resampling")

        #generate intermediate names for the resampled files (raw size)
        new_name = self.m["out_dirname"] + '/' + self.m["my_filename"] +'_resamp_' + str(SDRUno_suffix) + '_' + str(int(self.m["tLO"]/1000)) + 'kHz.wav'
        self.m["new_name"] = new_name
        self.m["list_out_files_resampled"].append(new_name)
        self.m["res_blinkstate"] = True
        time.sleep(0.001)
        #activate and trigger scheduler
        self.resample_c.Sigincrscheduler.connect(self.resample_c.res_scheduler)
        self.resample_c.Sigincrscheduler.emit()
        self.gui.lineEdit_resample_targetnameprefix.setEnabled(True) #TODO TODO: is that appropriate ?
        #TODO TODO: Lade letztes resampelte File ins generelle GUI
