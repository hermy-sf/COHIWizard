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
import pytz
from pathlib import Path
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import QtGui
import importlib
#from scipy import signal as sig
import yaml
import shutil
import pyqtgraph as pg
import logging
import subprocess
from auxiliaries import auxiliaries as auxi
from auxiliaries import WAVheader_tools
from datetime import datetime
import datetime as ndatetime
from player import stemlab_control
from auxiliaries import ffmpeg_installtools as ffinst
import platform
#from dev_drivers.fl2k import cohi_playrecworker



class playrec_m(QObject):
    __slots__ = ["None"]
    SigModelXXX = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["fileopened"] = False
        self.mdl["imported_device_modules"] = []
        self.mdl["imported_sdr_controllers"] = []
        self.mdl["currentSDRindex"] = -1
        self.mdl["playlist_active"] = False
        self.mdl["sample"] = 0
        self.mdl["LO_offset"] = 0
        self.mdl["UTC"] = False
        self.mdl["TEST"] = False
        self.mdl["Buttloop_pressed"] = False
        self.mdl["playthreadActive"] = False
        self.mdl["errorf"] = False
        self.mdl["icorr"] = 0
        self.mdl["gain"] = 1
        self.mdl["curtime"] = 0
        self.mdl["pausestate"] = False
        self.mdl["stopstate"] = False
        self.mdl["timechanged"] = False
        self.mdl["SPECDEBUG"] = True 
        # Create a custom logger
        logging.getLogger().setLevel(logging.DEBUG)
        self.logger = logging.getLogger(__name__)
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
        self.logger.debug('Init logger in playrec  reached')
        self.mdl["devicelist"] = os.listdir(os.path.join(os.getcwd(), "dev_drivers"))
        self.mdl["SDRcontrol"] = None
        self.mdl["device_ID_dict"] = {}
        #os.path.isdir(os.getcwd)

class playrec_c(QObject):
    """_view method
    """
    __slots__ = ["contvars"]

    SigAny = pyqtSignal()
    SigRelay = pyqtSignal(str,object)
    SigEOFStart = pyqtSignal()
    SigActivateOtherTabs = pyqtSignal(str,str,object)

    def __init__(self, playrec_m): 
        super().__init__()

        self.m = playrec_m.mdl
        #TODO: change for general devicedrivers
        self.stemlabcontrol = stemlab_control.StemlabControl()
        self.m["playlist_ix"] = 0
        self.logger = playrec_m.logger
        self.RecBitsPerSample = 16 #Default 16 bit recording, may be changed in the future
        self.TESTFILELISTCONTINUOUS = True
        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
        except:
            self.ismetadata = False
        try:
            self.default_directory = self.m["metadata"]["last_audiosource_path"]
        except:
            self.default_directory = ""
        try:
            self.m["rootpath"] = self.m["metadata"]["rootpath"]
        except:
            self.m["rootpath"] = os.getcwd()
        try:
            #search for ffmpeg path in metadata; if not found the install checker will be called
            #TODO This is a weak point: in case the ffmpeg path is not in the config yaml, the auto-install procedure will be called
            #TODO: this should be changed to a more general solution
            self.m["ffmpeg_path"] = self.m["metadata"]["ffmpeg_path"]
        except:
            self.m["ffmpeg_path"] = os.path.join(os.getcwd(),"ffmpeg-master-latest-win64-gpl-shared","bin")

        self.m["ffmpeg_autocheck"] = False
        #self.checkffmpeg_install()
        
        #self.SigRelay.connect()

    def popup(self,i):
        """
        """
        self.yesno = i.text()

    def query(self,query):
        """Query for automatic installation
 
        :param query: string with the query
        :type query: str
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Question")
        msg.setInformativeText(query)
        msg.setWindowTitle("autoinstall ffmpeg")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.buttonClicked.connect(self.popup)
        msg.exec_()

        if self.yesno == "&Yes":
            return True
        else:
            return False

    def checkffmpeg_install(self):
        errorstatus = False
        value = None
        errorstatus, value = ffinst.is_ffmpeg_installed(self.m["ffmpeg_path"]) 
        if not errorstatus:
            #returns new installpath for ffmpeg
            self.m["ffmpeg_path"] = value
            errorstatus = False
            value = ""
            return(errorstatus,value)
        querystr = "ffmpeg is not installed on this computer. \n This 3rd party software is required for running the modules synthesizer and resampler as well as some device drivers. \n \n Would you like it to be installed now by COHIWizard ? If not, you can also install manually and skip this procedure now. However the mentioned modules will not work unless ffmpeg has been installed."
        if self.query(querystr):
            self.logger.debug("try to install ffmpeg")
            errorstatus, value = self.ffmpeg_install_handler()
            if errorstatus:
                #installation failure
                self.SigActivateOtherTabs.emit("Player","inactivate",["View Spectra","Wavheader Editor", "Annotator","Yaml Editor"])
                #self.activate_control_elements(False)
                self.errorhandler("NOCLEAR \n" + value)
            else:
                #ffmpeg_exepath = value[0]
                #return new installpath for ffmpeg
                self.m["ffmpeg_path"] = value[1]
            #save ffmpeg path in configuration yaml
            self.m["metadata"]["ffmpeg_path"] = self.m["ffmpeg_path"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
        else:
            ffmpeg_link = "https://www.ffmpeg.org/download.html"
            #ffmpeg_link = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            #TODO TODO TODO: place this URL in a more general place like config_wizard.yaml for easy exchange
            #pathinfo = os.path.join(os.getcwd(), "ffmpeg-master-latest-win64-gpl")
            infotext = "<font size = 8> Synthesizer and resampler require ffmpeg to be installed on your computer; <br> Please install ffmpeg manually in folder  <br> ~rootpath/ffmpeg-master-latest-win64-gpl-shared/ <br> Download from: <a href='%s'>ffmpeg </a> <br> <br> Synthesizer will be inactivated until ffmpeg is available. </font>" % ffmpeg_link
            self.logger.error(infotext)
            #self.logger.error(pathinfo)
            auxi.standard_errorbox(infotext)
            #self.activate_control_elements(False)
            self.SigActivateOtherTabs.emit("Player","inactivate",["View Spectra","Wavheader Editor", "Annotator","Yaml Editor"])
            errorstatus = True
            value = infotext
        return(errorstatus,value)
    
    def ffmpeg_install_handler(self):
        #self.m["ffmpeg_path"]
        #root_dir = os.path.dirname(os.path.abspath(__file__))
        errorstatus = False
        value = ""
        ffmpeg_dir = os.getcwd()        
        system = platform.system().lower()
        
        if system == "linux" >= 0:
            errorstatus, value = ffinst.install_ffmpeg_linux(ffinst,ffmpeg_dir)
        elif system == "windows":
            errorstatus, value = ffinst.install_ffmpeg_windows(ffinst,ffmpeg_dir)
        else:
            print("This OS is not being supported")
            errorstatus = True
            value = "This OS is not being supported"
            return(errorstatus, value)
        
        print("Installation has been completed.")
        return(errorstatus, value)

    
    def instantiate_SDRcontrol(self,SDRindex):
        #self.stemlabcontrol = getattr(self.m["imported_device_modules"][self.m["currentSDRindex"]],'playrec_worker')(self.stemlabcontrol)
        self.m["SDRcontrol"] = getattr(self.m["imported_sdr_controllers"][SDRindex],'SDR_control')()
        #TODO: Überbrückungslösung f erste Tests:
        self.stemlabcontrol = self.m["SDRcontrol"]
        ######################################################
        pass

    def checkSTEMLABrates(self):        # TODO: this is rather a controller method than a GUI method. Transfer to other module
        """
        CONTROLLER
        _checks if the items ifreq, irate and icorr in system_state have the proper values acc. to RFCorder filename convention
        checks if system_state["irate"] has a value out of the values defined for the STEMLAB in system_state["rates"] 
        standard errorhandling via errorstate (True, False) and value (errormessage or '')
        :param: none
        :type: none

        :return: errorstate, value
        :rtype: bool, str
        """
        device_ID_dict =self.stemlabcontrol.identify()

        errorstate = False
        value = ""
        self.m["errorf"] = False
        if self.m["ifreq"] < device_ID_dict["min_IFREQ"] or self.m["ifreq"] > device_ID_dict["max_IFREQ"]:
        #TODO CHECK CHECK CHECK:
            value = "center frequency not in range " + str(device_ID_dict["min_IFREQ"]) + " - " + str(device_ID_dict["max_IFREQ"]) + "\n \n Please check if it is an SDR wav File (not audio) and what TX device it is meant for."
            errorstate = True
        if device_ID_dict["rate_type"] == "discrete":
            if self.m["irate"] not in device_ID_dict["rates"]:
            #TODO Device replace by: if self.m["irate"] not in device_ID_dict["rates"]:
                value = "The sample rate of this file is inappropriate for the device " + device_ID_dict["device_name"] + "\n \n Please check if it is an SDR wav File (not audio) and what TX device it is meant for. \n \n" + \
                "YOU MAY USE THE 'Resample' TAB TO CREATE A PLAYABLE FILE ! \n \n " + \
                "SR must be in the set " + str(list(device_ID_dict["rates"].keys()))
                errorstate = True
        elif device_ID_dict["rate_type"] == "continuous":
            if self.m["irate"] < list(device_ID_dict["rates"].keys())[0] or self.m["irate"] > list(device_ID_dict["rates"].keys())[1]:
                value = "The sample rate of this file is inappropriate for the device " + device_ID_dict["device_name"] + "\n \n Please check if it is an SDR wav File (not audio) and what TX device it is meant for. \n \n" + \
                "YOU MAY USE THE 'Resample' TAB TO CREATE A PLAYABLE FILE ! \n\n" + \
                "SR must be in the interval:" + str(list(device_ID_dict["rates"].keys())[0]) + " - " + str(list(device_ID_dict["rates"].keys())[1])
                errorstate = True
        else:
            errorstate = True
            value = f"Error in device identification, please check device driver SDR_control.py, rate type = {device_ID_dict['rate_type']}"

        if self.m["icorr"] < -100 or self.m["icorr"] > 100:
            value = "frequency correction min ppm must be in \
                      the interval (-100 - 100) after _c \n \
                      Probably not a COHIRADIA File "
            errorstate = True

        if self.m["device_ID_dict"]["device_name"] == "DONOTUSE":
            errorstate = True
            value = f"THIS DEVICE DRIVER IS NOT YET AVAILABLE (still under development)"  

        return(errorstate, value)
        
    def stemlabcontrol_errorhandler(self,errorstring):
        """handler for error signals from stemlabcontrol class
            display error in standard errormessagebox
            NOT YET IMPLEMENTED: reset playerbuttongroup and GUI
        VIEW
        :param: errorstring
        :type: str
        :raises [none]: [none]
        :return: none
        :rtype: none
        """     
        self.errorhandler(errorstring)
        #auxi.standard_errorbox(errorstring)
        #self.logger.error(errorstring)

    def display_status(self,messagestring): #shows connection status messages from stemlabcontrol
        """handler for message signals from stemlabcontrol class
            display message in GUI status field, if exists
            currently not used, reserved function
        :param: messaagestring
        :type: str
        :raises [none]: [none]
        :return: none
        :rtype: none
        """         
        #print(f"display status of stemlabcontrol, status = {messagestring}") #TODO: define displaystatus in more elaborate form


    def play_manager(self):
        """Callback function for Play Button; Calls file_open
           starts data streaming to STEMLAB sdr server via method play_tstarter
        VIEW
        :raises [none]: [none]
        :return: False if IP address not set, File could not be opened
                 False if STEMLAB socket cannot be started
                 False if playback thread cannot be started
                 True if player can be started successfully
        :rtype: Boolean
        """        
        errorstate = False
        value = ""

        if self.m["playthreadActive"]:
            self.logger.debug("playthread is active, no action") 
            return(errorstate,value)
        self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
        if self.m["f1"] == "":
            errorstate = True
            value = "No file opened, cannot proceed" 
            return(errorstate,value)
            #return False
    ######################  TODO: change for general devicedrivers
        self.stemlabcontrol.SigError.connect(self.stemlabcontrol_errorhandler)
        self.stemlabcontrol.SigMessage.connect(self.display_status) #currently not activem activate by re-writing display_status(message)
        errorstate, value = self.stemlabcontrol.set_play()
        if errorstate:
            self.playrec_c.errorhandler(value)
        self.m["modality"] = "play"
    ######################  END change for general devicedrivers
    
        #generate List of files if nextfile present in wavheader:
        self.contingent_file_list = []
        self.contingent_file_list.append(self.m["f1"])
        self.m["wavheader"]['nextfilename'] = self.m["wavheader"]['nextfilename'].rstrip("\x00")
        curr_nextfilestem = Path(self.m["wavheader"]['nextfilename'].rstrip()).stem
        while True:
            if len(curr_nextfilestem) > 0:
                nextfilename = self.m["my_dirname"] + "/" + curr_nextfilestem + ".wav"
                if (os.path.isfile(nextfilename)) and not self.contingent_file_list.__contains__(nextfilename):
                    #TODO TODO TODO: if filename already in continget_file_list, then skip !
                    self.contingent_file_list.append(nextfilename)
                    nextwavheader = WAVheader_tools.get_sdruno_header(WAVheader_tools,nextfilename)
                    curr_nextfilestem = Path(nextwavheader['nextfilename'].rstrip()).stem
                else:
                    break #no special errorhandling so far, though file not existent; do not want to interrupt playing up to here
            else:
                break 

        # start server unless already started
        self.m["rates"] = self.m["device_ID_dict"]["rates"]
        
        self.m["sdr_configparams"] = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
                "rates": self.m["rates"], "icorr":self.m["icorr"],
                "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        
    ######################  TODO: change for general devicedrivers
        # call respective driver here:

        # dev_driver#(self.m["configparams"],)
        # e.g. for fl2k: start fl2k_tcp and then launch connected data_messenger
        # in self.SDR#control.sdrserverstart(self.m["sdr_configparams"])
        # statt stemlabcontrol wird eine generelle Instanz SDRcontrol  gestartet

        if self.m["TEST"] is False:
            errorstate, process = self.stemlabcontrol.sdrserverstart(self.m["sdr_configparams"])
            time.sleep(5)
            #stdout, stderr = process.communicate()
            #print(stderr.decode())
            if errorstate: #TODO TODO TODO: errorhandling: generate errormsg in function instead of True/False
                #self.SigRelay.emit("cexex_playrec",["reset_GUI",0]) #TODO remove after tests
                self.SigRelay.emit("cexex_playrec",["reset_playerbuttongroup",0])
                #errorstate = True
                value = "SDR Server could not be started, please check if STEMLAB is connected correctly."
                return(errorstate,value)
            self.logger.info(f'play_manager configparams: {self.m["sdr_configparams"]}')
            if self.stemlabcontrol.config_socket(self.m["sdr_configparams"]): #TODO TODO TODO: better errorhandling and messaging with errorstate, value and errorhandler
                self.logger.info("config_socket now activated in play_manager")
                errorstate,value = self.play_tstarter() 
            else:
                errorstate = True  #TODO TODO TODO: better errorhandling and messaging with errorstate, value and errorhandler
                value = "Cannot configure SDR socket. Please check your STEMLAB connection."
        else:
            errorstate,value = self.play_tstarter()
                #return(errorstate,value)
            # if not self.play_tstarter():
            #     return False
    ######################  END: change for general devicedrivers

            self.logger.info("stemlabcontrols activated")
        # errorstate = True
        # value = "dummy error for testing"
        self.SigRelay.emit("cexex_playrec",["listhighlighter",0])
        return(errorstate,value)

    def errorhandler(self,value):
        """handles errors when methods return errormessages on errorstate == True
        (1) displays errormessage conveyed in 'value' and writes error to logfile
        (2) if 'value' contains the keyword 'ERRORSP' at the initial position, some special actions are performed

        :param value: error description which is to be displayed in the errormessage
        :type value: str
        """
        self.logger.error(str(value))
        self.m["playthreadActive"] = False
        try: 
            if value.find("ERRORSSP") == 0:
                #do something special here:
                #
                #
                self.logger.error(str(value[7:]))
                auxi.standard_errorbox(str(value[7:]))
                self.cb_Butt_STOP()
            else:
                self.logger.error(str(value))
                auxi.standard_errorbox(str(value))
                self.cb_Butt_STOP()
        except:
            if str(value) == "None":
                value = "unknown error, maybe the internet connection was required and could not be established. Please check."
            auxi.standard_errorbox(str(value))
            self.logger.error(str(value))
            self.cb_Butt_STOP()

        
    def play_tstarter(self):
        """_start playback via data stream to STEMLAB sdr server
        starts thread 'playthread' for data streaming to the STEMLAB
        instantiates thread worker method
        initializes signalling_

        : Signals handled :
        - SigFinished: emitted by: thread worker on end of stream thread termination, activate slot function for Stop button
        - thread.finished:thread termination
        - thread.started: start worker method streaming loop
        - SigIncrementCurTime: emitted by thread worker every second
                increment playtime counter by 1 second
        - SigError(errorstring): emitted by thread worker on error, invokes errormessager

        :return: _False if error, True on succes_
        :rtype: _Boolean_
        """        
        errorstate = False
        value = ""
        device_ID_dict =self.stemlabcontrol.identify()
        device_ID_dict ["resolutions"]
        #print("file opened in playloop thread starter")
        if self.m["wavheader"]['nBitsPerSample'] in device_ID_dict ["resolutions"]:
        #if self.m["wavheader"]['nBitsPerSample'] == 16 or self.m["wavheader"]['nBitsPerSample'] == 24 or self.m["wavheader"]['nBitsPerSample'] == 32:
            if self.m["wavheader"]['nBitsPerSample'] == 24:
                auxi.standard_infobox("In 24 bit mode the volume control probably does not work !")
            #TODO: Anpassen an andere Fileformate, Einbau von Positionen 
        # elif self.m["wavheader"]['nBitsPerSample'] == 8: #TODO TODO: specify supported bitdepth in driver specification
        #     print("8 bit file, cannot be played with stemlab")
        else:
            #auxi.standard_errorbox("dataformat not supported, only 16, 24 and 32 bits per sample are possible")
            errorstate = True
            value = f"dataformat not supported, only {device_ID_dict ["resolutions"]} bits per sample are possible"
            return(errorstate,value)
                
        self.m["timescaler"] = self.m["wavheader"]['nSamplesPerSec']*self.m["wavheader"]['nBlockAlign']
        #TODO TODO TODO: generate list of playlengths in case of nextfile-chain !
        true_filesize = os.path.getsize(self.m["f1"]) ########
        self.m["playlength"] = true_filesize/self.m["wavheader"]['nAvgBytesPerSec'] ##########
        #self.m["playlength"] = self.m["wavheader"]['filesize']/self.m["wavheader"]['nAvgBytesPerSec'] #TODO test OLD: before 22-12-2024
        self.playthread = QThread()
######################  TODO: change for general devicedrivers
# instead of self.stemlabcontrol --> self.SDRcontrol
# instead of class playrec_worker --> class cohi_playrecworker
        #TODO TODO TODO: check ob diese Implementierung nun die stemlab-Workerfunktionen richtig bedient
        #self.playrec_tworker = playrec_worker(self.stemlabcontrol)

        
        self.playrec_tworker = getattr(self.m["imported_device_modules"][self.m["currentSDRindex"]],'playrec_worker')(self.stemlabcontrol)
######################  END: change for general devicedrivers

        self.playrec_tworker.moveToThread(self.playthread)
        self.playrec_tworker.set_timescaler(self.m["timescaler"])
        self.playrec_tworker.set_TEST(self.m["TEST"])
        self.playrec_tworker.set_pause(False)
        #self.playrec_tworker.set_modality(self.m["modality"])
        self.playrec_tworker.set_gain(self.m["gain"])
        ################## TODO CHECK: was changed for general devicedrivers
        self.playrec_tworker.set_configparameters(self.m["sdr_configparams"]) # = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],"rates": self.m["rates"], "icorr":self.m["icorr"],"HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        self.logger.debug("set tworker gain to: %f",self.m["gain"])
        #print(f"gain: {self.m['gain']}")
        format = [self.m["wavheader"]["wFormatTag"], self.m["wavheader"]['nBlockAlign'], self.m["wavheader"]['nBitsPerSample']]
        self.playrec_tworker.set_formattag(format)
        
        #self.prfilehandle = self.playrec_tworker.get_fileHandle() #TODO CHECK IF REQUIRED test output, no special other function
        if self.m["modality"] == "play": #TODO: activate
            if not self.TESTFILELISTCONTINUOUS: # This is obsolete , test after 01-01-2025
                self.playrec_tworker.set_filename(self.m["f1"])
                self.playthread.started.connect(self.playrec_tworker.play_loop16)
            else:
                self.playrec_tworker.set_filename(self.contingent_file_list)
                self.playthread.started.connect(self.playrec_tworker.play_loop_filelist) #TODO TODO TODO TODO: activate for nextfile list
        else:
            self.playrec_tworker.set_filename(self.m["f1"])
            self.playthread.started.connect(self.playrec_tworker.rec_loop)

        self.playrec_tworker.SigFinished.connect(self.EOF_manager)
        self.playrec_tworker.SigInfomessage.connect(self.infosigmanager)
        self.playrec_tworker.SigFinished.connect(self.recloopmanager)
        self.playrec_tworker.SigError.connect(self.errorsigmanager)
        self.playrec_tworker.SigNextfile.connect(self.nextfilemanager)
        self.SigEOFStart.connect(self.EOF_manager)
        self.playrec_tworker.SigFinished.connect(self.playrec_tworker.deleteLater)

        self.playthread.finished.connect(self.playthread.deleteLater)
        self.playrec_tworker.SigIncrementCurTime.connect(
                                                lambda: self.SigRelay.emit("cexex_playrec",["updatecurtime",1]))
        #self.SigRelay.emit("cexex_playrec",["updatecurtime",1])
        self.playrec_tworker.SigIncrementCurTime.connect(lambda: self.SigRelay.emit("cexex_playrec",["showRFdata",0]))
        if self.m["modality"] == "rec":        
            self.playrec_tworker.SigBufferOverflow.connect(
                                         lambda: self.SigRelay.emit("cexex_playrec",["indicate_bufoverflow",0])) #TODO reactivate
        self.playthread.start()
        if self.playthread.isRunning():
            self.m["playthreadActive"] = True
            self.SigRelay.emit("cm_all_",["playthreadActive",self.m["playthreadActive"]])  ###TODO: geht nicht
            self.logger.info("playthread started in playthread_threadstarter = play_tstarter() (threadstarter)")
            # TODO replace playthreadflag by not self.playthread.isFinished()
            errorstate = False
            value = ""
            
            #return True
        else:
            #auxi.standard_errorbox("STEMLAB data transfer thread could not be started")
            errorstate = True
            value = "STEMLAB data transfer thread could not be started, please check if STEMLAB is connected correctly"
        return(errorstate,value)

    def nextfilemanager(self,filename):
        """sets parameters for the currently opened file in list of files played by tworker in case of liwt in nextfile chain
            reads new wavheader
            resets the time updater via signalling

        :param filename: name of the currently opened file
        :type filename: str
        """
        self.m["f1"] = filename
        self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])
        self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
        self.SigRelay.emit("cexex_playrec",["showFilename", filename])
        

    def infosigmanager(self,message):
        auxi.standard_infobox(message)
        print(message)

    def errorsigmanager(self,message):
        auxi.standard_errorbox(message)

    def recordingsequence(self,expected_seconds):
        """handle recordig of a file:
        (1) check for sufficient diskspace

        :param expected_seconds: expected duration of the recording in seconds
        :type expected_seconds: int
        """
        #CHECK FOR SUFFICIENT DISK SPACE ON VOLUME
        errorstate = False
        value = ""
        self.stemlabcontrol.SigError.connect(self.stemlabcontrol_errorhandler)
        expected_filesize = expected_seconds * self.m["irate"] * self.RecBitsPerSample/4 #2**31
        #TODO TODO TODO: not correct !
        errorstate, value = self.checkdiskspace(expected_filesize, self.m["recording_path"])
        if errorstate:
            return(errorstate,value)
        ovwrt_flag = False
        WAVheader_tools.write_sdruno_header(self,self.m["f1"],self.m["wavheader"],ovwrt_flag) ##TODO TODO TODO Linux conf: self.m["f1"],self.m["wavheader"] must be in Windows format
        self.m["sdr_configparams"] = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
                    "rates": self.m["rates"], "icorr":self.m["icorr"],
                    "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        if self.m["TEST"] is False:
            if not self.stemlabcontrol.sdrserverstart(self.m["sdr_configparams"]):
                self.cb_Butt_STOP()
                errorstate = False
                value = ""
                return(errorstate, value)
            errorstate, value = self.stemlabcontrol.set_rec()
            if errorstate:
                return(errorstate, value)
            # configparams = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
            #         "rates": self.m["rates"], "icorr":self.m["icorr"],
            #         "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
            if self.stemlabcontrol.config_socket(self.m["sdr_configparams"]):
                errorstate,value = self.play_tstarter()
                if errorstate:
                    return(errorstate, value)
            else:
                errorstate = True
                value = "Cannot configure STEMLAB socket, please check the connection to STEMLAB."
                return(errorstate, value)
        else:
            errorstate,value = self.play_tstarter()
            if errorstate:
                return(errorstate, value)
        self.m["recstate"] = True
        self.m["stopstate"] = False
        return(errorstate, value)

    def checkdiskspace(self,expected_filesize, _dir): #TODO: transfer to auxiliary module 
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
        errorstate = False
        value = ""
        total, used, free = shutil.disk_usage(_dir)
        if free < expected_filesize:
            #print(f"not enough diskspace for this process, please free at least {expected_filesize - free} bytes")
            #auxi.standard_errorbox(f"not enough diskspace for this process, please free at least {expected_filesize - free} bytes")
            errorstate = True
            value = f"not enough diskspace for this process, please free at least {expected_filesize - free} bytes"
        return(errorstate, value)


    def generate_recfilename(self):
        """generate filename for recording file from:
        recording_path/cohiwizard_datestring_Ttimestring_LOfrequency.dat
        :return: False if STEMLAB socket cannot be started
                 False if playback thread cannot be started 
        :rtype: Boolean
        """
        try:
            dt_now = datetime.now()
            dt_now = dt_now.astimezone(pytz.utc)

            filenamestem = "cohiwizard_" + dt_now.strftime('%Y%m%d') +"_" + dt_now.strftime('%H%M%S')  +"Z"
            filenamestem += "_" + str(int(self.m["ifreq"]/1000)) + "kHz.wav"
            filepath = os.path.join(self.m["recording_path"],filenamestem)

            # self.m["f1"] = self.m["recording_path"] + "/cohiwizard_" + dt_now.strftime('%Y%m%d') +"_" + dt_now.strftime('%H%M%S')  +"Z"
            # self.m["f1"] += "_" + str(int(self.m["ifreq"]/1000)) + "kHz.wav"
            #self.RecBitsPerSample
            creation_date = datetime.now()
            creation_date = creation_date.astimezone(pytz.utc)
            self.playrec_tworker = getattr(self.m["imported_device_modules"][self.m["currentSDRindex"]],'playrec_worker')(self.stemlabcontrol)

            #self.DATABLOCKSIZE = playrec_worker(self).DATABLOCKSIZE
            self.DATABLOCKSIZE = self.playrec_tworker.DATABLOCKSIZE
            #calculate expected filesize
            filesize = int(2*self.DATABLOCKSIZE*(2**31//(self.DATABLOCKSIZE*2)))
            self.m["wavheader"] = WAVheader_tools.basic_wavheader(self,self.m["icorr"],self.m["irate"],self.m["ifreq"],self.RecBitsPerSample,filesize,creation_date)
            self.m["wavheader"]["starttime"] = [creation_date.year, creation_date.month, 0, creation_date.day, creation_date.hour, creation_date.minute, creation_date.second, int(creation_date.microsecond/1000)]  
            self.m["wavheader"]["starttime_dt"] = creation_date
            errorstate = False
            value = filepath
        except:
            errorstate = True
            value = "Unknown error, cannot generate output filename, procedure is being aborted."
        return(errorstate, value)
        
    def recloopmanager(self):
        #print("playrec recloop next loop")
        if self.m["modality"] == "play":
            return
        prfilehandle = self.playrec_tworker.get_fileHandle()
        prfilehandle.close()
        self.playthread.quit()
        self.playthread.wait()
        #time.sleep(0.1)
        self.SigRelay.emit("cm_all_",["fileopened",False])   ####TODO geht nicht
        if self.m["stopstate"]:
            self.logger.info("EOF-manager: player has been stopped")
            file_stats = os.stat(self.m["f1"])
            self.m["wavheader"]['filesize'] = file_stats.st_size
            self.m["wavheader"]['data_nChunkSize'] = self.m["wavheader"]['filesize'] - 208
        spt = datetime.now()
        spt = spt.astimezone(pytz.utc)
        self.m["wavheader"]['stoptime_dt'] = spt
        self.m["wavheader"]['stoptime'] = [spt.year, spt.month, 0, spt.day, spt.hour, spt.minute, spt.second, int(spt.microsecond/1000)] 
        self.m["ovwrt_flag"] = True
        WAVheader_tools.write_sdruno_header(self,self.m["f1"],self.m["wavheader"],self.m["ovwrt_flag"]) ##TODO TODO TODO Linux conf: self.m["f1"],self.m["wavheader"] must be in Windows format
        if not self.m["stopstate"]:
            f1old = self.m["f1"]
            wavheader_old = self.m["wavheader"]
            #print("fire up next recloop #########################")
            self.logger.debug("playrec recloopmanager fire up next recloop ")
            errorstate, value = self.generate_recfilename()
            if errorstate:
                self.errorhandler(value)
            else:
                self.m["f1"] = value
            #wavheader_old['nextfilename'] = self.m["f1"]
            wavheader_old['nextfilename'] = Path(self.m["f1"]).name
            WAVheader_tools.write_sdruno_header(self,f1old,wavheader_old,self.m["ovwrt_flag"]) ##TODO TODO TODO Linux conf: self.m["f1"],self.m["wavheader"] must be in Windows format
            errorstate, value = self.recordingsequence()
            if errorstate:
                self.errorhandler(value)

    def EOF_manager(self):
        """_target of SigFinished from playloop. If signal is received, a decision is made whether 
            to stop the player completely, 
            continue with next file if 'nextfile' in wavheader exists
            continue restarting the same file as long as in endless mode_

        :param : none
        :type : none
        '''
        :raises [ErrorType]: [ErrorDescription]
        '''
        :return:
        :rtype:
        """ 
        if self.m["modality"] == "rec":
            return
        #TODO: check why this sequence incl file close needs to be outside the playthred worker; causes some problems
        
        #prfilehandle = self.playrec_tworker.get_fileHandle() ###TODO TODO TODO: obsolete, file is closed by tworker
        self.playthread.quit()
        self.playthread.wait()
        time.sleep(0.05)
        #prfilehandle.close() ###TODO TODO TODO: obsolete, file is closed by tworker
        self.m["fileopened"] = False #OBSOLETE ?
        #self.SigRelay.emit("cm_all_",["fileopened",False]) ####TODO geht nicht
        self.m["wavheader"]['nextfilename'] = self.m["wavheader"]['nextfilename'].rstrip() ###TODO TODO TODO: obsolete, file is closed by tworker
        if self.m["stopstate"] == True:
            self.logger.info("EOF-manager: player has been stopped")
            time.sleep(0.5)
            return
        #if (os.path.isfile(self.m["my_dirname"] + '/' + self.m["wavheader"]['nextfilename']) == True and self.m["wavheader"]['nextfilename'] != "" ): #TODO delete after tests 23-12-2024: 
        ###TODO TODO TODO: remove after testing 26-12-2024r
        #if False:
        #if (os.path.isfile(os.path.join(self.m["my_dirname"], self.m["wavheader"]['nextfilename'])) and self.m["wavheader"]['nextfilename'] != "" ):
            # if not self.TESTFILELISTCONTINUOUS:
            #     ###TODO TODO TODO: obsolete, nextfile is handled by tworker
            #     # play next file in nextfile-list
            #     #self.m["f1"] = self.m["my_dirname"] + '/' + self.m["wavheader"]['nextfilename'] TODO: delete after tests 23-12-2024
            #     self.m["f1"] = os.path.join(self.m["my_dirname"], self.m["wavheader"]['nextfilename'])
            #     self.m["my_filename"] = Path(self.m["f1"]).stem
            #     ####TODO geht nicht
            #     #self.SigRelay.emit("cm_all_",["f1",self.m["my_dirname"] + '/' + self.m["wavheader"]['nextfilename']])
            #     #self.SigRelay.emit("cm_all_",["my_filename",self.m["my_filename"]])####TODO geht nicht
            #     self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])
            #     self.m["wavheader"]['nextfilename'] = self.m["wavheader"]['nextfilename'].rstrip()
            #     time.sleep(0.02)
            #     errorstate,value = self.play_tstarter()
            #     if errorstate:
            #         self.errorhandler(value)
            #     time.sleep(0.02)
            #     self.m["fileopened"] = True
            #     #self.SigRelay.emit("cm_all_",["fileopened",True])####TODO geht nicht
            #     #TODO: self.my_filename + self.ext müssen updated werden, übernehmen aus open file
            #     #self.SigRelay.emit("cexex_all_",["updateGUIelements",0])####TODO geht nicht
            #     self.SigRelay.emit("cexex_playrec",["updateotherGUIelements",0])
            #     self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
            #     #self.logger.info("fetch nextfile")
            #     print(f"playrec namechange after nextfile test, filename: {self.m['my_filename']}")
            # else:
            #     print("automatic nextfile treatment, no nextfilehandling necessary")
            #    pass
        
        if self.m["Buttloop_pressed"]:
            time.sleep(0.1)
            #("restart same file in endless loop")
            self.logger.debug("restart same file in endless loop")
            #no next file, but endless mode active, replay current system_state["f1"]
            errorstate,value = self.play_tstarter()
            if errorstate:
                self.errorhandler(value)
            time.sleep(0.1)
            self.logger.info("playthread active: %s", self.m["playthreadActive"])
            self.m["fileopened"] = True
            self.SigRelay.emit("cm_all_",["fileopened",True])####TODO geht nicht
            self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
        elif self.m["playlist_len"] > 0:
            if self.m["playlist_ix"] == 0:
                self.SigRelay.emit("cexex_playrec",["listhighlighter",self.m["playlist_ix"]])
                self.m["playlist_ix"] += 1 #TODO: aktuell Hack, um bei erstem File keine Doppelabspielung zu triggern
            if self.m["playlist_ix"] < self.m["playlist_len"]: #TODO check if indexing is correct
                self.m["playthreadActive"] = False
                #self.SigRelay.emit("cm_all_",["playthreadActive",self.m["playthreadActive"]])####TODO geht nicht
                self.SigRelay.emit("cexex_playrec",["listhighlighter",self.m["playlist_ix"]])
                self.logger.debug("EOF manager: playlist index: %i", self.m['playlist_ix'])
                self.logger.info("fetch next list file")
                Formatcheck_False = True
                while Formatcheck_False:
                    item_valid = False
                    while (not item_valid) and (self.m["playlist_ix"] < self.m["playlist_len"]):
                        item = self.m["playlist"][self.m["playlist_ix"]]
                        self.m["my_filename"] = item
                        self.m["f1"] = self.m["my_dirname"] + '/' + item 
                        #self.SigRelay.emit("cm_all_",["f1",self.m["my_dirname"] + '/' + item]) #TODO: geht nicht
                        self.logger.info("EOF manager file in loop: %s", self.m["f1"])
                        self.logger.debug("EOF manager file in loop: %s , index: %i", item, self.m["playlist_ix"])
                        self.m["wavheader"] = WAVheader_tools.get_sdruno_header(self,self.m["f1"])

                        self.m["wavheader"]['nextfilename'] = self.m["wavheader"]['nextfilename'].rstrip("\x00")
                        self.m["wavheader"]['nextfilename'] = self.m["wavheader"]['nextfilename'].rstrip()
                        #self.SigRelay.emit("cm_all_",["wavheader",self.m["wavheader"]])#TODO: geht nicht
                        #self.SigRelay.emit("cm_all_",["my_filename",self.m["my_filename"]])#TODO: geht nicht
                        ####TODO: maybe the following is obsolete:
                        #self.SigRelay.emit("cm_all_",["fileopened",True])#TODO: geht nicht
                        self.SigRelay.emit("cexex_all_",["updateGUIelements",0])

                        item_valid = True
                        if not self.m["wavheader"]:
                            self.logger.warning("EOF_manager: wrong wav file, skip to next listentry")
                            self.m["playlist_ix"] += 1
                            item_valid = False

                    if not (self.m["playlist_ix"] < self.m["playlist_len"]):
                        self.m["playlist_ix"] = 0
                        self.logger.info("EOF_manager: end of list, stop player")
                        time.sleep(0.5)
                        self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
                        self.cb_Butt_STOP()
                        self.SigRelay.emit("cexex_playrec",["reset_GUI",0]) #TODO remove after tests
                        self.SigRelay.emit("cexex_playrec",["reset_playerbuttongroup",0])
                        return()
                    if self.m["wavheader"]['sdrtype_chckID'].find('rcvr') > -1:
                        self.m["readoffset"] = 86
                    else:
                        self.m["readoffset"] = 216
                    self.m["playlist_ix"] += 1                #TODO: self.m Eintragung von icorr etc erfolgt an mehreren STellen, fileopen, extract dat header und hier. Könnte an einer Stelle passieren, immer, sobald ein wav-header extrahiert wird
                    self.m["ifreq"] = self.m["wavheader"]['centerfreq'] + self.m["LO_offset"]
                    self.m["irate"] = self.m["wavheader"]['nSamplesPerSec']
                    self.m["icorr"] = 0
                    self.m["timescaler"] = self.m["wavheader"]['nSamplesPerSec']*self.m["wavheader"]['nBlockAlign']
                    self.logger.debug("EOF manager new wavheader: %i", self.m["wavheader"]["nSamplesPerSec"])
                    #TODO: write new header to wav editor is this necessary ?
                    #TODO TODO TODO TODO: check for correct SDR-settings already during buildup fo the playlist
                    errorstate, value = self.checkSTEMLABrates()
                    Formatcheck_False = False
                    if errorstate:
                        Formatcheck_False = True
                        #self.errorhandler(value)
                        print(f"invalid STEMLABRATES, skip file in list: {self.m["f1"]}")
                    self.SigRelay.emit("cexex_playrec",["listhighlighter",self.m["playlist_ix"]])
                    time.sleep(0.1)
                
                #TODO: rplace by os.path.join:
                self.m["my_filename"], self.m["ext"] = os.path.splitext(os.path.basename(self.m["f1"]))
                self.logger.debug("EOF manager new file before playing: %s", self.m["my_filename"])
                if not self.m["TEST"]:
                    self.stemlabcontrol.sdrserverstop()
                    self.logger.info("EOF manager start play_manager")
                errorstatus, value = self.play_manager()
                if errorstatus:
                    self.errorhandler(value)
                self.m["fileopened"] = True
                self.SigRelay.emit("cm_all_",["fileopened",True])
                self.SigRelay.emit("cexex_all_",["updateGUIelements",0])
                time.sleep(0.5) #necessary because otherwise file may not yet have been opened by playloopworker and then updatecurtime crashes because of invalid filehandel 
                #may be solved by updatecurtime not accessing the filehandle returned from playworker but directly from self.m["f1"]
                #self.updatecurtime(0) #TODO: true datetime from record
                self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
            else:
                #reset playlist_ix
                self.m["playlist_ix"] = 0
                self.logger.info("EOF_manager: stop player")
                time.sleep(0.5)
                self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
                self.cb_Butt_STOP()
                #self.SigRelay.emit("cexex_playrec",["reset_GUI",0]) #TODO remove after tests
                self.SigRelay.emit("cexex_playrec",["reset_playerbuttongroup",0])
        else:
            #no next file,no endless loop --> stop player
            #print("stop player")
            self.logger.info("EOF_manager: stop player 2")
            time.sleep(0.5)
            self.cb_Butt_STOP()
            ##TODO: introduce separate stop_manager

    def cb_Butt_STOP(self):
        """
        Callback function for Stop Button; 
        sets stopstate flag True
        stops playrec_thread
        stops sdrserver if running --> stops data streaming to STEMLAB sdr server
        resets all player buttons to initial state
        set all tabs which 
        :raises [none]: [none]
        :return: none
        :rtype: none
        """        
        #TODO: activate for player
        #print("STOP PRESSED R")
        self.m["stopstate"] = True
        self.m["recstate"] = False
        self.m["pausestate"] =False
        if self.m["playthreadActive"] is False:
            self.m["fileopened"] = False ###CHECK
            self.SigRelay.emit("cm_all_",["fileopened",False]) #TODO: funktioniert nicht
            #self.SigRelay.emit("cexex_playrec",["reset_GUI",0]) #TODO remove after tests
            #self.SigRelay.emit("cexex_playrec",["reset_playerbuttongroup",0])
            #return
        else:
            self.playrec_tworker.stop_loop()
        if self.m["TEST"] is False:
            self.stemlabcontrol.sdrserverstop()
        self.SigRelay.emit("cexex_playrec",["updatecurtime",0])
        self.SigRelay.emit("cexex_playrec",["reset_playerbuttongroup",0])
        #self.SigRelay.emit("cexex_all_",["reset_GUI",0]) #TODO: probably doesnt work
        self.SigRelay.emit("cexex_playrec",["reset_GUI",0])
        #TODO TODO TODO: activate other tabs
        self.SigActivateOtherTabs.emit("Player","activate",[])
        #self.SigRelay.emit("cexex_win",["reset_GUI",0]) #TODO remove after tests, may not be connected with _c
        #print("STOP pressed")

    def jump_1_byte(self):             #increment current time in playtime window and update statusbar
        """
        _increments file reading position by +1 byte for manually correcting for sample jumps 
        which deviate from integer multiples of sample size (4, 8); possible needs to be repeated several times
        this is an emergency method for exceptional usecases and not for regular operation
        if self.modality == "play":
            - update position slider
            - set file read pointer to new position, |if increment| > 1
        :param : none
        :type : int
        '''
        :raises [ErrorType]: [ErrorDescription]
        '''
        :return: True/False on successful/unsuccesful operation
        :rtype: bool
        """ 
        self.logger.debug("tracking: jump 1 byte")
        if self.m["modality"] == 'play' and not self.m["pausestate"]:
            if self.m["fileopened"]:
                self.prfilehandle = self.playrec_tworker.get_fileHandle()
                self.prfilehandle.seek(1,1) #TODO: ##OPTION from current position## 0 oder 1 ?
        # TODO: not yet safe, because increment may happen beyond EOF, check for EOF
                

    def jump_to_position_c(self):
        """
        :param : none
        :type : none
        '''
        :raises [ErrorType]: [ErrorDescription]
        '''
        :return: none
        :rtype: none
        """ 
        self.logger.debug("jumptoposition reached")
        ####################################################################
        #sbposition = self.ui.ScrollBar_playtime.value() #TODO: already in updatecurtime(...)        
        #ERSETZE DURCH: ####################################################
        sbposition = self.m["playprogress"]
        ####################################################################
        self.m["curtime"] = int(np.floor(sbposition/1000*self.m["playlength"]))  # seconds
        timestr = str(self.m["wavheader"]['starttime_dt'] + ndatetime.timedelta(seconds=self.m["curtime"]))
        self.SigRelay.emit("cexex_playrec",["setplaytimedisplay",timestr])
        position_raw = self.m["curtime"]*self.m["timescaler"]  #timescaler = bytes per second
        # TODO: check, geändert 09-12-2023: byte position mit allen Blockaligns auch andere als 4(16 bits); 
        # TODO: adapt for other than header 216
        position = min(max(216, position_raw-position_raw % self.m["wavheader"]['nBlockAlign']),
                            self.m["wavheader"]['data_nChunkSize']+216) # guarantee reading from integer multiples of 4 bytes, TODO: change '4', '216' to any wav format ! 
        if self.m["fileopened"] is True:
            self.logger.debug("jumptoposition reached")
            self.logger.debug("system_state['fileopened']: %s",self.m["fileopened"])
            self.prfilehandle = self.playrec_tworker.get_fileHandle()
            self.prfilehandle.seek(int(position), 0) #TODO: Anpassen an andere Fileformate
        #calculate corresponding position in the record file; value = 216 : 1000
        #jump to the targeted position with integer multiple of wavheader["nBitsPerSample"]/4

    def LO_bias_checkbounds(self):
        """ Purpose: checks if LO bias setting is within valid bounds; 
        :param [ParamName]: none
        :type [ParamName]: none
        :raises none
        :return: True if successful, otherwise False
        :rtype: Boolean
        """
        eff_ifreq = self.m["LO_offset"] + self.m["ifreq"]
        if not self.update_LO_bias():
            return False                 
        if (eff_ifreq <= 0):
            auxi.standard_errorbox("invalid negative center frequency offset, magnitude greater than LO frequency of the record, please correct value")
            self.SigRelay.emit("cexex_playrec",["resetLObias",0])
            self.cb_Butt_STOP()
            return False
        if (eff_ifreq > 60000000):
            auxi.standard_errorbox("invalid  center frequency offset, sum of record LO and offset must be < 60000 kHz, please correct value")
            self.SigRelay.emit("cexex_playrec",["resetLObias",0])
            self.cb_Butt_STOP()
            return False
        return True


class playrec_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["viewvars"]

    SigCancel = pyqtSignal()    # TODO: not used so far
    #SigUpdateGUI = pyqtSignal(object) # TODO: remove after checks
    SigSyncGUIUpdatelist = pyqtSignal(object)
    SigGUIReset =pyqtSignal()
    SigRelay = pyqtSignal(str,object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)

    def __init__(self, gui, playrec_c, playrec_m):
        super().__init__()

        self.m = playrec_m.mdl
        self.DATABLOCKSIZE = 1024*32
        self.GAINOFFSET = 40
        self.gui = gui
        self.playrec_c = playrec_c
        #self.norepeat = False
        self.m["UTC"] = False
        self.m["TEST"] = False
        self.LO_LOW = 0
        self.LO_HIGH = 50000
        self.m["stopstate"] = True
        self.m["wavheader"] = {}
        self.m["wavheader"]['centerfreq'] = 0
        self.m["icorr"] = 0
        self.lastupdatecurtime = datetime.now()
        
        self.logger = playrec_m.logger
        self.init_playrec_ui()
        self.playrec_c.SigRelay.connect(self.rxhandler)
        #self.playrec_c.SigRelay.connect(self.SigRelay.emit)  ##TODO TODO TODO: das ist sehr gefährlich ! CHECK !
        self.CURTIMEINCREMENT = 5
        self.m["pausestate"] = False
        self.blinkstate = False
        self.m["recstate"] = False
        self.m["recording_path"] = ""
        self.m["recstate"] = False
        self.m["modality"] = ""
        self.m["pausestate"] = False
        self.gui.lineEdit_playrec_LO.setText("1125")


    def init_playrec_ui(self):

        self.gui.playrec_radioButtonpushButton_write_logfile.clicked.connect(self.togglelogfilehandler)
        self.gui.playrec_radioButtonpushButton_write_logfile.setChecked(True)

        self.gui.pushButton_Loop.setChecked(False)
        self.gui.pushButton_Loop.clicked.connect(self.Buttloopmanager)
        #self.gui.listWidget_playlist.model().rowsInserted.connect(self.playlist_update)
        #self.gui.listWidget_playlist.model().rowsRemoved.connect(self.playlist_update) 

        self.gui.pushButton_Shutdown.clicked.connect(self.shutdown)
        self.gui.pushButton_FF.clicked.connect(
            lambda: self.updatecurtime(self.CURTIMEINCREMENT))
        self.gui.pushButton_REW.clicked.connect(
                    lambda: self.updatecurtime(-self.CURTIMEINCREMENT))
        self.gui.pushButton_adv1byte.clicked.connect(
                    lambda: self.playrec_c.jump_1_byte())          ########### INACTIVATE if 1 byte correction should be disabled
        self.gui.pushButton_adv1byte.setEnabled(False)  #TODO: rename: manual tracking
        self.gui.verticalSlider_Gain.valueChanged.connect(self.cb_setgain)
        self.gui.ScrollBar_playtime.sliderReleased.connect(self.jump_to_position)
        #self.gui.ScrollBar_playtime.mousePressEvent = self.gui.scrollbar_mousePressEvent

        self.gui.lineEdit_LO_bias.setFont(QFont('arial',12))
        self.gui.lineEdit_LO_bias.setEnabled(False)
        self.gui.lineEdit_LO_bias.setText("0000")
        self.gui.radioButton_LO_bias.setEnabled(True)
        self.gui.lineEdit_LO_bias.textChanged.connect(lambda: self.update_LO_bias("verbose","nochange"))
        self.gui.radioButton_LO_bias.clicked.connect(self.activate_LO_bias)
        #self.gui.pushButton_Play.setIcon(QIcon("./core/ressources/icons/play_v4.PNG"))
        self.gui.pushButton_Play.clicked.connect(self.cb_Butt_toggleplay)
        self.gui.pushButton_Stop.clicked.connect(self.playrec_c.cb_Butt_STOP)
        self.gui.pushButton_REC.clicked.connect(self.cb_Butt_REC)        
        self.gui.pushButton_act_playlist.clicked.connect(self.cb_Butt_toggle_playlist)
        self.gui.lineEdit_IPAddress.returnPressed.connect(self.set_IP)
        #self.gui.lineEdit_IPAddress.setInputMask('000.000.000.000')
        #self.gui.lineEdit_IPAddress.setText("000.000.000.000")
        self.gui.lineEdit_IPAddress.setEnabled(False)
        self.gui.lineEdit_IPAddress.setReadOnly(True)
        #####INFO: IP address validator from Trimmal Software    
        #rx = QRegExp('^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])|rp-[0-9A-Fa-f]{6}\.local$')
        #                                                          self.addrValue.setValidator(QRegExpValidator(rx, self.addrValue))
        #pushButton->setIcon(QIcon(":/on.png"));
        self.gui.pushButton_IP.clicked.connect(self.editHostAddress) #TODO: Remove after transfer
        #self.gui.lineEdit_IPAddress.returnPressed.connect(self.set_IP) #TODO: Remove after transfer
        self.gui.listWidget_playlist.setEnabled(False)
        self.gui.listWidget_sourcelist.setEnabled(False)
        self.gui.ScrollBar_playtime.setEnabled(False)
        self.gui.Label_Recindicator.setEnabled(False)
        self.gui.comboBox_playrec_targetSR.setCurrentIndex(5)
        self.gui.comboBox_playrec_targetSR_2.setCurrentIndex(1) #TODO: rename to playrec_Bandpreset
        self.gui.comboBox_playrec_targetSR_2.currentIndexChanged.connect(self.preset_SR_LO)
        #self.gui.playrec_RECSTART_dateTimeEdit.setText
        self.gui.playrec_RECSTART_dateTimeEdit.setDateTime(datetime.now())
        self.gui.playrec_radioButton_RECAUTOSTART.clicked.connect(self.toggleRecAutostart)
        self.gui.label_Filename_Player.setText('')

        self.gui.comboBox_stemlab.clear()
        #self.mdl["devicelist"] = os.listdir(os.path.join(os.getcwd(), "dev_drivers"))
        boxix = 0
        auxl = len(self.m["devicelist"])
        for ix, cf in enumerate(self.m["devicelist"]):
            if not cf.find("__") == 0:
                self.gui.comboBox_stemlab.addItem(str(cf))
                #import playrec_worker classes
                full_module_path = f"dev_drivers.{cf}.cohi_playrecworker"
                #module_path = os.path.join("dev_drivers",cf)
                #full_module_path = f"{module_path}.cohi_playrecworker"
                #print(f"vvvvvvvvvvvvvvvvvvvvvvvvvvv    full_module_path: {full_module_path}")
                try:
                    self.m["imported_device_modules"].append(importlib.import_module(full_module_path))
                    #print(f"vvvvvvvvvvvvvvvvvvvvvvvvvvv    imported device module: {self.m['imported_device_modules']}")
                    # import SDRcontrol classes
                    full_module_path = f"dev_drivers.{cf}.SDR_control"
                    self.m["imported_sdr_controllers"].append(importlib.import_module(full_module_path))
                    #text = self.gui.comboBox_playrec_targetSR_2.currentText()
                    #set SDR choice combobox to stemlab 125-14
                    if cf.find("stemlab_125_14") == 0:
                        self.m["currentSDRindex"] = boxix
                        self.m["standardSDRindex"] = boxix
                    boxix += 1
                except:
                    print(f"module {cf} not in driver list, will be ignored")
        self.gui.comboBox_stemlab.setCurrentIndex(self.m["currentSDRindex"])

        #instantiate stemlab control
        #self.playrec_c.instantiate_SDRcontrol(self.m["currentSDRindex"])
        self.gui.comboBox_stemlab.currentIndexChanged.connect(self.sdrdevice_changehandler)
        self.sdrdevice_changehandler()
        # now self.m["SDRcontrol"] is the same as stemlab_control
            #cohi_playrecworker
            #from dev_drivers.fl2k import cohi_playrecworker

            #self.dynamic_import(self.m["devicelist"][ix])
        #self.gui.comboBox_stemlab.
        #self.mdl["devicelist"] # comboBox_stemlab
        
        self.gui.checkBox_TESTMODE.clicked.connect(self.toggleTEST)
        preset_time = QTime(00, 30, 00) 
        self.gui.playrec_RECLENGTH_timeEdit.setTime(preset_time)
        ###########TODO TODO TODO: remove after transfer to config Tab
        try:
            stream = open("config_wizard.yaml", "r")
            self.metadata = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
            if 'STM_IP_address' in self.metadata.keys():
                self.gui.lineEdit_IPAddress.setText(self.metadata["STM_IP_address"]) #TODO: Remove after transfer of playrec
                self.m["STM_IP_address"] = self.metadata["STM_IP_address"] #TODO: Remove after transfer of playrec
        except:
            self.m["STM_IP_address"] = self.gui.lineEdit_IPAddress.text()
            self.logger.error("reset_gui: cannot get metadata")
            pass

        # try:
        #     stream = open("config_wizard.yaml", "r")
        #     self.metadata = yaml.safe_load(stream)
        #     if 'STM_IP_address' in self.metadata.keys():
        #         self.gui.lineEdit_IPAddress.setText(self.metadata["STM_IP_address"]) #TODO: Remove after transfer of playrec
        #         self.gui.Conf_lineEdit_IPAddress.setText(self.metadata["STM_IP_address"]) #TODO TODO TODO: reorganize and shift to config module
        #         self.SigRelay.emit("cm_playrec",["STM_IP_address",self.metadata["STM_IP_address"]]) #TODO: Remove after transfer of playrec
        #     stream.close()
        # except:
        #     self.logger.error("reset_gui: cannot get metadata")
        # return True

    # def dynamic_import(self,devicelist):
    # # sub_module = "modules"
    # # mod_base = {'player':'playrec'}
    # # config['modules'] = {**mod_base, **config['modules']}
    # # #print(f"config file content: {config}")
    # # widget_base = {'player': 'Player'}
    # # config['module_names'] = {**widget_base, **config['module_names']}
    # # loaded_modules = dynamic_import_from_config(config,sub_module,xcore_v.logger)

    #     #self.mdl["devicelist"] = os.listdir(os.path.join(os.getcwd(), "dev_drivers"))
    #     module = dev_drivers.fl2k import cohi_playrecworker

    #     try:
    #         # create path <directory>.<module>
    #         full_module_path = f"{directory}.{module}"
    #         # Importmodule dynamically
    #         imported_module = importlib.import_module(full_module_path)
    #         imported_modules[module] = imported_module
    #         logger.debug(f"dynamic import: Successfully imported {module} from {full_module_path}.")
    #         #print(f"Successfully imported {module} from {full_module_path}.")
    #     except ModuleNotFoundError as e:
    #         print(f"dynamic import Error importing {module} from {directory}: {e}")
    #         logger.debug(f"dynamic import: Error importing {module} from {directory}: {e}")


    def togglelogfilehandler(self):
        if self.gui.playrec_radioButtonpushButton_write_logfile.isChecked():  #TODO TODO: should be task of the playrec module ??
            self.logger.setLevel(logging.DEBUG)
            self.SigRelay.emit("cexex_all_",["logfilehandler",True])
        else:
            self.logger.setLevel(logging.NOTSET)
            self.SigRelay.emit("cexex_all_",["logfilehandler",False])

    def sdrdevice_changehandler(self):
        QTimer.singleShot(0, self.process_combobox_change)

    def playgroup_activate(self,value):
        """activates or inactivates GUI elements of the Playback functions based on
        value (True,False)
        
        :param: value: True or False
        :type: bool
        ...
        :raises: none
        ...
        :return: none
        """
        self.gui.pushButton_Play.setEnabled(value)
        self.gui.pushButton_REW.setEnabled(value)
        self.gui.pushButton_FF.setEnabled(value)
        self.gui.pushButton_Loop.setEnabled(value)
        self.gui.pushButton_adv1byte.setEnabled(value)

    def recordinggroup_activate(self,value):
        """activates or inactivates GUI elements of the Recording functions based on
        value (True,False)
        
        :param: value: True or False
        :type: bool
        ...
        :raises: none
        ...
        :return: none
        """
        self.gui.comboBox_playrec_targetSR.setEnabled(value)
        self.gui.lineEdit_playrec_LO.setEnabled(value)
        self.gui.comboBox_playrec_targetSR_2.setEnabled(value)
        self.gui.lineEdit_LO_bias.setEnabled(value)
        self.gui.playrec_RECLENGTH_timeEdit.setEnabled(value)
        self.gui.pushButton_REC.setEnabled(value)
        self.gui.playrec_radioButton_RECAUTOSTART.setEnabled(value)
        self.gui.playrec_RECSTART_dateTimeEdit.setEnabled(value)
        self.gui.label_BW_2.setEnabled(value)
        self.gui.label_BW.setEnabled(value)
        self.gui.label_LO.setEnabled(value)
        self.gui.lineEdit_LO_bias.setEnabled(value)
        self.gui.playrec_label_RECSTART.setEnabled(value)
        self.gui.playrec_label_REC_duration.setEnabled(value)
        self.gui.label_35.setEnabled(value)

    def process_combobox_change(self):
        """handles change of SDR device in combobox
        (1) sets currentSDRindex to the index of the selected device
        (2) instantiates the SDR control object
        (3) identifies the device
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: errorstate, value; in case of error, value contains error message, else device ID dict
        :rtype: bool, str
        """
        errorstate = False
        value = ""
        self.logger.debug("sdrdevice_changehandler")
        self.m["currentSDRindex"] = self.gui.comboBox_stemlab.currentIndex()
        #comboBox_stemlab = self.playrec_c.instantiate_SDRcontrol(self.m["currentSDRindex"])
        if self.m["currentSDRindex"] < 0:
            return(errorstate, value)   

        try:
            self.playrec_c.instantiate_SDRcontrol(self.m["currentSDRindex"])
            self.m["device_ID_dict"] = self.playrec_c.stemlabcontrol.identify()
            errorstate = False
            value = self.m["device_ID_dict"]

            if not self.m["device_ID_dict"]["TX"]:
                self.playgroup_activate(False)
            else:
                self.playgroup_activate(True)
            if not self.m["device_ID_dict"]["RX"]:
                self.recordinggroup_activate(False)
            else:
                self.recordinggroup_activate(True)
            if self.m["device_ID_dict"]["connection_type"] == "USB":
                self.gui.lineEdit_IPAddress.setEnabled(False)
                self.gui.pushButton_IP.setEnabled(False)
                #self.gui.lineEdit_IPAddress.setReadOnly(True)
            elif self.m["device_ID_dict"]["connection_type"] == "ethernet":
                self.gui.lineEdit_IPAddress.setEnabled(True)
                self.gui.pushButton_IP.setEnabled(True)
                #TODO: in later implementations write host address to device driver SDRcontrol file
                self.gui.lineEdit_IPAddress.setText(self.m["HostAddress"])
                #self.gui.lineEdit_IPAddress.setReadOnly(False)
            elif self.m["device_ID_dict"]["connection_type"] == "USB_Vethernet":
                self.gui.lineEdit_IPAddress.setEnabled(False)
                self.gui.pushButton_IP.setEnabled(False)
                self.gui.lineEdit_IPAddress.setText("127.0.0.1")
                #self.gui.lineEdit_IPAddress.setReadOnly(False)
                                       
            else:
                errorstate = True
                value = f"unknown connection type in SDR device driver: {self.m["device_ID_dict"]["connection_type"]}"

        except:
            self.logger.error("sdrdevice_changehandler: cannot identify SDR device")    
            errorstate = True
            value = "cannot identify SDR device"
            return(errorstate, value)
        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text()
        if self.m["device_ID_dict"]["device_name"] == "DONOTUSE":
            errorstate = True
            value = f"THIS DEVICE DRIVER IS NOT YET AVAILABLE (still under development)"  
        if errorstate:
            auxi.standard_errorbox(value) #TODO TODO TODO: good errorhandling with errorstate, value; errorhandler
            self.gui.comboBox_stemlab.setCurrentIndex(self.m["standardSDRindex"])
        return(errorstate, value) 


    def preset_SR_LO(self):
        text = self.gui.comboBox_playrec_targetSR_2.currentText()
        if text.find("LW") == 0:
            self.gui.lineEdit_playrec_LO.setText("220")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(3)
        if text.find("MW") == 0:
            self.gui.lineEdit_playrec_LO.setText("1125")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(5)
        if text.find("SW 49m") == 0:
            self.gui.lineEdit_playrec_LO.setText("6050")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(4)
        if text.find("SW 41m") == 0:
            self.gui.lineEdit_playrec_LO.setText("7325")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(3)
        if text.find("SW 31m") == 0:
            self.gui.lineEdit_playrec_LO.setText("9650")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(4)
        if text.find("SW 25m") == 0:
            self.gui.lineEdit_playrec_LO.setText("11850")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(4)
        if text.find("SW 19m") == 0:
            self.gui.lineEdit_playrec_LO.setText("15450")
            self.gui.comboBox_playrec_targetSR.setCurrentIndex(5)
        pass

    def toggleRecAutostart(self):
        if self.gui.playrec_radioButton_RECAUTOSTART.isChecked():
            self.m["autostart"] = True
            self.gui.playrec_label_RECSTART.setEnabled(True)
            self.gui.playrec_label_RECSTART.setStyleSheet("background-color : yellow")
            font = self.gui.playrec_label_RECSTART.font()
            font.setPointSize(12)
            self.gui.playrec_label_RECSTART.setFont(font)
            font.setBold(True)
            self.gui.playrec_label_RECSTART.setFont(font)
            self.gui.playrec_RECSTART_dateTimeEdit.setEnabled(True)
            self.gui.playrec_RECSTART_dateTimeEdit.setDateTime(datetime.now() + ndatetime.timedelta(minutes=15))
        else:
            self.m["autostart"] = False
            self.gui.playrec_label_RECSTART.setEnabled(False)
            self.gui.playrec_label_RECSTART.setStyleSheet("background-color : lightgray")
            font = self.gui.playrec_label_RECSTART.font()
            font.setPointSize(12)
            self.gui.playrec_label_RECSTART.setFont(font)
            font.setBold(False)
            self.gui.playrec_label_RECSTART.setFont(font)
            self.gui.playrec_RECSTART_dateTimeEdit.setEnabled(False)

    def countdown(self):
        """
        updates countdown in play time indicator, if playrec_radioButton_RECAUTOSTART is enabled 
        starts recording if countdown drops < 0
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        if self.m["recstate"]:
            current_datetime = QDateTime.currentDateTime()    
            # Zeit aus dem QTimeEdit-Objekt
            #qtimeedit = self.gui.playrec_RECLENGTH_timeEdit
            #time_from_qtimeedit = qtimeedit.time()       
            # Zeit aus dem QTimeEdit-Objekt zu aktuellen Datum hinzufügen
            #hours = time_from_qtimeedit.hour()
            #minutes = time_from_qtimeedit.minute()
            #seconds = time_from_qtimeedit.second()
            #target_datetime = current_datetime.addSecs(hours * 3600 + minutes * 60 + seconds)
            # Differenz berechnen
            remaining_time = current_datetime.secsTo(self.target_datetime)
            self.gui.lineEditCurTime.setText(str(time.strftime("%H:%M:%S", time.gmtime(remaining_time))))
            
            #print(f"playrec countdown residual time : {remaining_time}")
            if remaining_time == 0:
                self.playrec_c.cb_Butt_STOP()
            return
        countdown =  self.gui.playrec_RECSTART_dateTimeEdit.dateTime().toPyDateTime() - datetime.now()
        if self.gui.playrec_radioButton_RECAUTOSTART.isChecked():
            print(countdown.total_seconds())
            if countdown.total_seconds() <= 0:
                self.gui.lineEditCurTime.setText("")
                self.cb_Butt_REC()
                self.gui.playrec_radioButton_RECAUTOSTART.setChecked(False)
                self.gui.playrec_label_REC_duration.setStyleSheet("background-color : yellow")
                #self.gui.playrec_label_REC_duration.setStyleSheet("background-color : lightgray")
                font = self.gui.playrec_label_REC_duration.font()
                font.setPointSize(14)
                self.gui.playrec_label_REC_duration.setFont(font)
                self.toggleRecAutostart()
            else:
                self.gui.lineEditCurTime.setText(str(countdown).split('.')[0])

            
            
    def blinkrec(self):
        if self.m["recstate"] == False:
            self.gui.Label_Recindicator.setEnabled(False)
            self.gui.Label_Recindicator.setStyleSheet(('background-color: rgb(255,255,255)'))
            self.gui.label_32.setStyleSheet("background-color : lightgrey")
            self.gui.label_32.setEnabled(False)
            return
        self.gui.Label_Recindicator.setEnabled(True)
        if self.blinkstate:
            self.blinkstate = False
            self.gui.Label_Recindicator.setStyleSheet(('background-color: rgb(255,50,50)'))
            self.gui.label_32.setStyleSheet("background-color : lightgrey")
            self.gui.label_32.setEnabled(False)
        else:
            self.blinkstate = True
            self.gui.Label_Recindicator.setStyleSheet(('background-color: rgb(0,255,255)'))

    def Buttloopmanager(self):
        if self.gui.pushButton_Loop.isChecked() == True:
            self.m["Buttloop_pressed"] = True
            self.gui.pushButton_Loop.setIcon(QIcon("./core/ressources/icons/loopactive_v4.png"))
        else:
            self.m["Buttloop_pressed"] = False
            self.gui.pushButton_Loop.setIcon(QIcon("./core/ressources/icons/loop_v4.png"))

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
        self.gui.checkBox_UTC.clicked.connect(self.toggleUTC)
        self.gui.checkBox_TESTMODE.clicked.connect(self.toggleTEST)
        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text()
        #self.gui.lineEdit_IPAddress.setText(self.m["metadata"]["STM_IP_address"])
        self.logger.debug(f"update filename in display: {self.m['my_filename']}")
        self.gui.label_Filename_Player.setText(self.m["my_filename"] + self.m["ext"])

    def reset_GUI(self):
        self.gui.listWidget_playlist.clear()
        self.gui.listWidget_sourcelist.clear()
        self.gui.label_Filename_Player.setText("")
        self.SigRelay.emit("cexex_view_spectra",["reset_GUI",0])
        self.SigRelay.emit("cexex_resample",["reset_GUI",0])
        self.gui.label_Filename_Player.setText('')

        if self.m["playlist_active"] == True:
        #     self.gui.pushButton_act_playlist.setChecked(True)
        #     self.gui.listWidget_sourcelist.setEnabled(True)
        #     self.gui.listWidget_playlist.setEnabled(True)
        #     self.m["playlist_active"] = True
        # else:
            self.gui.pushButton_act_playlist.setChecked(False)
            self.gui.listWidget_sourcelist.setEnabled(False)
            self.gui.listWidget_playlist.setEnabled(False)
            self.m["playlist_active"] = False

        #self.SigActivateOtherTabs.emit("Player","activate",[])
  
    def addplaylistitem(self):
        item = QtWidgets.QListWidgetItem()
        self.gui.listWidget_sourcelist.addItem(item)

    def fillplaylist(self):
        playlist = []
        #resfilelist = [] #TODO: obsolete ?
        ix = 0
        for x in os.listdir(self.m["my_dirname"]):
            if x.endswith(".wav"):
                if True: #x != (self.m["my_filename"] + self.m["ext"]): #TODO: obsolete old form when automatically loading opened file to playlist
                    #resfilelist.append(x) #TODO: used ?????????
                    _item=self.gui.listWidget_sourcelist.item(ix)
                    _item.setText(x)
                    fnt = _item.font()
                    fnt.setPointSize(11)
                    _item.setFont(fnt)
                    item = QtWidgets.QListWidgetItem()
                    self.gui.listWidget_sourcelist.addItem(item)
                    ix += 1
        #erzeuge einen Eintrag in Playlist listWidget_playlist
        if self.m["f1"].endswith(".wav"):
            item = QtWidgets.QListWidgetItem()
            self.gui.listWidget_playlist.addItem(item)
            _item=self.gui.listWidget_playlist.item(0)
            _item.setText(self.m["my_filename"] + self.m["ext"])
            fnt = _item.font()
            fnt.setPointSize(11)
            _item.setFont(fnt)
            playlist.append(self.m["f1"])
            self.m["playlist"] = playlist

        self.gui.listWidget_playlist.setEnabled(False)
        self.gui.listWidget_sourcelist.setEnabled(False)



    def rxhandler(self,_key,_value):
        """
        handles remote calls from other modules via Signal SigRX(_key,_value)
        :param : _key
        :type : str
        :param : _value
        :type : object
        :raises [ErrorType]: [ErrorDescription]
        :return: none
        :rtype: none
        """
        #self.logger.debug("rxhandler playrec key: %s , value: %s", _key,_value)
        #reftime = datetime.now()
        if _key.find("cm_playrec") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
        if _key.find("cui_playrec") == 0:
            _value[0](_value[1]) #STILL UNCLEAR
        if _key.find("cexex_playrec") == 0  or _key.find("cexex_all_") == 0:
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
            if  _value[0].find("reset_playerbuttongroup") == 0:
                self.reset_playerbuttongroup()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("setplaytimedisplay") == 0:
                self.gui.lineEditCurTime.setText(_value[1])
            if  _value[0].find("resetLObias") == 0:
                self.reset_LO_bias()
            if  _value[0].find("updatecurtime") == 0:
                #self.reset_LO_bias()
                #evaltime = datetime.now() - reftime
                #print(f"reached updatecurtime call @ {evaltime}")
                self.updatecurtime(_value[1])
                #evaltime = datetime.now() - reftime
                #print(f"left updatecurtime call @ {evaltime}")
                #print(f"UPDATECURTIME: {_value[1]}")
            if  _value[0].find("showRFdata") == 0:
                if self.gui.core_checkBox_show_spectrum.isChecked():
                    self.showRFdata()
            if  _value[0].find("showFilename") == 0:
                self.gui.label_Filename_Player.setText(Path(_value[1]).name)
            if  _value[0].find("listhighlighter") == 0:
                try:
                    self.listhighlighter(_value[1])
                except:
                    pass
            if  _value[0].find("updateotherGUIelements") == 0:
                self.SigRelay.emit("cexex_all_",["updateGUIelements",0])
            if  _value[0].find("timertick") == 0:
                if self.m["recstate"]:
                    self.blinkrec()
                self.countdown()
                if not self.m["ffmpeg_autocheck"]:
                    #print(f"timertick: value of self.m['ffmpeg_autocheck'] {self.m["ffmpeg_autocheck"]}")
                    self.m["ffmpeg_autocheck"] = True
                    self.playrec_c.checkffmpeg_install()
                    pass
            if  _value[0].find("indicate_bufoverflow") == 0:
                self.indicate_bufoverflow()
            if  _value[0].find("addplaylistitem") == 0:
                self.addplaylistitem()
            if  _value[0].find("fillplaylist") == 0:
                self.fillplaylist()            
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])
            if  _value[0].find("canvasbuild") == 0 and self.m["SPECDEBUG"]:
                self.canvasbuild(_value[1])
            #evaltime = datetime.now() - reftime
            #print(f"rxhandler: within function evaltime from entry to finish: {evaltime}")

    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("playrec: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.debug("playrec: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)

    def jump_to_position(self):
        """
        jump to next player file position
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        self.m["playprogress"] = self.gui.ScrollBar_playtime.value()
        self.playrec_c.jump_to_position_c()
        #self.m["QTMAINWINDOWparent"]
        #self.gui.ScrollBar_playtime.mousePressEvent = self.m["QTMAINWINDOWparent"].scrollbar_mousePressEvent

    def toggleUTC(self):
        if self.gui.checkBox_UTC.isChecked():
            self.m["UTC"] = True #TODO: check if is needed in view, otherwise make local or ebven just pass to 
        else:
            self.m["UTC"] = False
    
    def toggleTEST(self):
        if self.gui.checkBox_TESTMODE.isChecked():
            self.m["TEST"] = True 
        else:
            self.m["TEST"] = False

    def cb_Butt_toggle_playlist(self):
        #system_state = sys_state.get_status()
        if self.m["playlist_active"] == False:
            self.gui.pushButton_act_playlist.setChecked(True)
            self.gui.listWidget_sourcelist.setEnabled(True)
            self.gui.listWidget_playlist.setEnabled(True)
            self.m["playlist_active"] = True
        else:
            self.gui.pushButton_act_playlist.setChecked(False)
            self.gui.listWidget_sourcelist.setEnabled(False)
            self.gui.listWidget_playlist.setEnabled(False)
            self.m["playlist_active"] = False

    def playlist_update(self): #TODO: list is only updated up to the just before list change dragged item,
        """
        updates playlist whenever the playlist Widget is changed
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        #print("playlist updated")

        self.logger.info("playlist_update: playlist updated")
        time.sleep(0.001)
        #system_state = sys_state.get_status()
        #get all items of playlist Widget and write them to system_state["playlist"]
        lw = self.gui.listWidget_playlist
        # let lw haven elements in it.
        self.m["playlist"] = []
        for x in range(lw.count()):
            item = lw.item(x)
            #playlist.append(lw.item(x))
            self.m["playlist"].append(item.text())
        #self.m["playlist"] = self.m["playlist"]
        self.m["playlist_len"] = self.gui.listWidget_playlist.count()
        #self.SigRelay.emit("cm_playrec",["playlist",self.m["playlist"]])

    def cb_setgain(self):
        '''
        Descr
        #TODO
        '''
        if self.m["playthreadActive"] is False:
            return False
        self.m["gain"] = 10**((self.gui.verticalSlider_Gain.value() - self.GAINOFFSET)/20)
        self.logger.debug("cb_setgain, gain: %f",self.m["gain"])
        self.playrec_c.playrec_tworker.set_gain(self.m["gain"])   #############TODO ?? what ?
        #print(f"cab_set gain gain: {self.m['gain']}")

    def popup(self,i):
        """    
        """
        self.yesno = i.text()

    def listhighlighter(self,_index): 
            lw = self.gui.listWidget_playlist
            item = lw.item(_index)
            item.setBackground(QtGui.QColor("lightgreen"))  #TODO: shift to resampler view ???? why ???
    #item.setBackground(QtGui.QColor("lightgreen"))

    def cb_Butt_toggleplay(self):
        """ 
        toggles the play button between play and pause states


        .. image:: ../../source/images/cb_Butt_toggleplay.svg

        :param: none
        :type: none
        """
        self.playlist_update()
        self.update_LO_bias()
        #TODO TODO TODO: inactivate other tabs
        self.SigActivateOtherTabs.emit("Player","inactivate",["View spectra"])
        if self.gui.pushButton_Play.isChecked():
            if not self.m["fileopened"]:
                if self.gui.radioButton_LO_bias.isChecked():
                    #TODO TODO TODO: replace by query method
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Question)
                    msg.setText("Apply LO offset")
                    msg.setInformativeText("center frequency offset is activated, the LO will be shifted by "
                        + str(int(self.m["LO_offset"]/1000)) + " kHz. Do you want to proceed ? If no, please inactivate center frequency offset")
                    msg.setWindowTitle("Apply LO offset")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.buttonClicked.connect(self.popup)
                    msg.exec_()
                    if self.yesno == "&No":
                        ###RESET playgroup
                        self.reset_playerbuttongroup()
                        self.reset_LO_bias()
                        #sys_state.set_status(system_state)
                        return False

                self.gui.radioButton_LO_bias.setEnabled(False)
                #TODO TODO TODO. HOW TO CALL A CORE FUNCTION ?
                #if self.cb_open_file() is False: #TODO TODO: check if works equally as before, 
                # now the quest is for fileopened and not, if open file returned True
                if not self.m["fileopened"]:
                    auxi.standard_errorbox("file must be opened before playing") #TODO TODO TODO: good errorhandling with errorstate, value; errorhandler
                    #TODO TODO TODO: OBSOLETE ? check if this is ever reached ? self.m["fileopened" is False is a condition that this branch is reched !
                    # restore automatic call of fileopen in this case
                    self.reset_playerbuttongroup()
                    #sys_state.set_status(system_state)
                    return False
                if not self.playrec_c.LO_bias_checkbounds():
                    self.reset_playerbuttongroup()
                    return False
                self.gui.lineEdit_LO_bias.setEnabled(False)
                ######Setze linedit f LO_Bias inaktiv
            self.m["ifreq"] = self.m["wavheader"]['centerfreq'] + self.m["LO_offset"]
            self.m["irate"] = self.m["wavheader"]['nSamplesPerSec']
            self.m["timescaler"] = self.m["wavheader"]['nSamplesPerSec']*self.m["wavheader"]['nBlockAlign']

            errorstate, value = self.playrec_c.checkSTEMLABrates()
            #if not self.playrec_c.checkSTEMLABrates():
            if errorstate:
                self.playrec_c.errorhandler(value)
                #self.reset_playerbuttongroup() #TODO: probably obsolete because done by errorhandler
                self.SigRelay.emit("cexex_all_",["reset_GUI",0])
                return False
            self.gui.pushButton_Play.setIcon(QIcon("./core/ressources/icons/pause_v4.PNG"))
            self.gui.pushButton_REC.setEnabled(False)
            self.gui.lineEdit_LO_bias.setEnabled(False)
            if self.m["playthreadActive"] == True:
                #self.playrec_c.playrec_tworker.pausestate = False
                self.playrec_c.playrec_tworker.set_pause(False)
            errorstate, value = self.playrec_c.play_manager()
            if errorstate:
                self.playrec_c.errorhandler(value)
            self.m["pausestate"] = False
            self.m["stopstate"] = False
            self.gui.ScrollBar_playtime.setEnabled(True)
            self.gui.pushButton_adv1byte.setEnabled(True)
        else:
            self.gui.pushButton_Play.setIcon(QIcon("./core/ressources/icons/play_v4.PNG"))
            self.m["pausestate"] = True ##TODO CHECK: necessary ? es gibt ja self.playrec_c.playrec_tworker.pausestate
            if self.m["playthreadActive"] == True:
                #self.playrec_c.playrec_tworker.pausestate = True
                self.playrec_c.playrec_tworker.set_pause(True)
        if self.m["errorf"]:
            #auxi.standard_errorbox(self.m["errortxt"])
            return False
        else:
            return True

    def shutdown(self):
        '''
        Returns: nothing
        '''
        #system_state = sys_state.get_status()
        self.playrec_c.cb_Butt_STOP()
        #self.timertick.stoptick()
        self.SigRelay.emit("cexex_xcore",["stoptick",0])
        self.playrec_c.stemlabcontrol.RPShutdown(self.m["sdr_configparams"])
        #TODO TODO TODO: check if it would also be fine to instantiate the stemlabcontrol object only here in the player
        #it is certainly not used in other modules

    def recording_path_checker(self):
        """
        checks, if recording path exists in config_wizard.yaml and if the path exists
        if not: ask for target pathname and store in config.wizard.yaml
        param: none
        type: none
        :raises [none]: [none]
        :return: none
        :rtype: none
        """         
        self.standardpath = os.getcwd()  #TODO: this is a core variable in core model
        try:
            stream = open("config_wizard.yaml", "r")
            self.metadata = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
        except:
            self.ismetadata = False
        recfail = False
        if "recording_path" not in self.metadata:
            recfail = True
        elif not os.path.isdir(self.metadata["recording_path"]):
            recfail = True
        if recfail:
            options = QFileDialog.Options()
            options |= QFileDialog.ShowDirsOnly
            self.m["recording_path"] = ""
            while len(self.m["recording_path"]) < 1:
                self.m["recording_path"] = QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Select Recording Directory", options=options)
                if len(self.m["recording_path"]) < 1:
                    auxi.standard_errorbox("Recording path must be defined, please define it by clicking OK !")
            self.logger.debug("playrec recording path: %s", self.m["recording_path"])
            self.metadata["recording_path"] = self.m["recording_path"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.metadata, stream)
            stream.close()
        else:
            self.m["recording_path"] = self.metadata["recording_path"]
        self.logger.debug("playrec recording button recording path: %s", self.m["recording_path"])
        self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])
        self.SigRelay.emit("cexex_xcore",["updateConfigElements",0])


    def numeraltest(self,_item,lo_bound,hi_bound,errortextsource):
        """
        checks, if _item is a numeral and if it obeys certain criteria
        criteria:  <lo_bound, >hi bound, 
        param: _item: text to be checked
        type: str
        param: lo_bound: lowest valid value
        type: int
        param: hi_bound: highest valid value
        type: int
        param: errortextsource: text describing the source of the _item
        type: str
        :raises [none]: [none]
        :return: True if succesful, False else
        :rtype: Boolean
        """   
        numeraltest = True
        if not _item.isnumeric():
            numeraltest = False
        _item = _item.replace(".", "")
        if not _item[1:].isdigit(): #TODO: necessary ?
            numeraltest = False
        if numeraltest == False:
            auxi.standard_errorbox(errortextsource + "invalid characters, must be numeric float value !")
            return False
        try:
            tester = float(_item)
        except TypeError:
            #print("plot_res_spectrum: wrong format of TARGET_LO")
            self.logger.error("playrec numeraltest, wrong format")
            auxi.standard_errorbox(errortextsource + "invalid characters, must be numeric float value !")
            return False
        except ValueError:
            #print("plot_res_spectrum: wrong format of TARGET_LO")
            self.logger.error("plot_res_spectrum: wrong format of TARGET_LO")
            auxi.standard_errorbox(errortextsource +"invalid characters, must be numeric float value !")
            #TARGET_LO = self.m["wavheader"]['centerfreq']
            return False
        if (tester < lo_bound) or (tester > hi_bound):
            self.logger.error("plot_res_spectrum: wrong format of TARGET_LO")
            auxi.standard_errorbox(errortextsource + "value exceeds valid bounds !")
            return False
        return True

    def cb_Butt_REC(self):
        """
        Callback function for REC Button; 
        #######################so far dummy, as not yet implemented
        :raises [none]: [none]
        :return: none
        :rtype: none
        """
        self.SigActivateOtherTabs.emit("Player","inactivate",["View spectra"])
        self.recording_path_checker()
        #   self.gui.pushButton_REC.setIcon(QIcon("pause_v4.PNG"))
        # if len(self.m["recording_path"]) == 0:
        #     print("playrec recorderbutton: no rec path defined")
        #     ##TODO TODO TODO: recording path abfragen
        #     return False
        errorstate, value = self.playrec_c.stemlabcontrol.set_rec()
        if errorstate:
            self.playrec_c.errorhandler(value)
        self.m["modality"] = "rec"
        self.gui.checkBox_UTC.setEnabled(False)
        # if self.gui.radioButton_timeract.isChecked():
            # # TODO: activate self.recordingsequence in timerupdate
            #     self.recording_wait = True
            #     return
            #else:
        if self.numeraltest(self.gui.lineEdit_playrec_LO.text(),self.LO_LOW,self.LO_HIGH,"LO value in recorder tab"):
            self.m["ifreq"] = int(1000*int(self.gui.lineEdit_playrec_LO.text()))
            self.m["irate"] = int(1000*int(self.gui.comboBox_playrec_targetSR.currentText()))
        else:
            return False

        errorstate, value = self.playrec_c.generate_recfilename()
        if errorstate:
            self.playrec_c.errorhandler(value)
        # if not self.playrec_c.generate_recfilename():
        #     return False
        else:
            self.m["f1"] = value
        self.updatecurtime(0)
        self.gui.pushButton_FF.setEnabled(False)
        self.gui.pushButton_REW.setEnabled(False)
        self.gui.pushButton_Loop.setEnabled(False)
        self.gui.pushButton_Play.setEnabled(False)
        self.gui.verticalSlider_Gain.setEnabled(False)
        #TODO TODO TODO warning if host not reachable
        

        current_datetime = QDateTime.currentDateTime()    
        # Zeit aus dem QTimeEdit-Objekt
        qtimeedit = self.gui.playrec_RECLENGTH_timeEdit
        time_from_qtimeedit = qtimeedit.time()       
        # Zeit aus dem QTimeEdit-Objekt zu aktuellen Datum hinzufügen
        hours = time_from_qtimeedit.hour()
        minutes = time_from_qtimeedit.minute()
        seconds = time_from_qtimeedit.second()
        expected_seconds = hours * 3600 + minutes * 60 + seconds
        self.target_datetime = current_datetime.addSecs(expected_seconds)
        self.gui.playrec_label_REC_duration.setStyleSheet("background-color : yellow")
        font = self.gui.playrec_label_REC_duration.font()
        font.setPointSize(14)
        self.gui.playrec_label_REC_duration.setFont(font)
        errorstate, value = self.playrec_c.recordingsequence(expected_seconds)
        if errorstate:
            self.playrec_c.errorhandler(value)
        self.reftime = datetime.now()
        
        #self.m["recstate"] = True

    def reset_playerbuttongroup(self):
        """

        """
        #system_state = sys_state.get_status()
        self.gui.pushButton_Play.setIcon(QIcon("./core/ressources/icons/play_v4.PNG"))
        self.gui.pushButton_Play.setChecked(False)
        self.gui.pushButton_Loop.setChecked(False)
        self.gui.pushButton_REC.setIcon(QIcon("./core/ressources/icons/rec_v4.PNG"))
        self.gui.Label_Recindicator.setEnabled(False)
        self.gui.Label_Recindicator.setStyleSheet(('background-color: rgb(255,255,255)'))
        self.m["playthreadActive"] = False
        self.SigRelay.emit("cm_all_",["playthreadActive",self.m["playthreadActive"]])
        #self.activate_tabs(["View_Spectra","Annotate","Resample","YAML_editor","WAV_header"])
        #self.setactivity_tabs("Player","activate",[])
        self.SigActivateOtherTabs.emit("Player","activate",[])
        self.m["fileopened"] = False ###CHECK
        self.SigRelay.emit("cm_all_",["fileopened",False])
        self.gui.radioButton_LO_bias.setEnabled(True)
        self.gui.lineEdit_LO_bias.setEnabled(True)
        self.gui.ScrollBar_playtime.setEnabled(False)
        self.gui.pushButton_adv1byte.setEnabled(False)
        self.gui.pushButton_act_playlist.setChecked(False)
        self.gui.listWidget_sourcelist.setEnabled(False)
        self.gui.listWidget_playlist.setEnabled(False)
        self.gui.pushButton_Play.setEnabled(True)
        self.gui.pushButton_FF.setEnabled(True)
        self.gui.pushButton_REW.setEnabled(True)
        self.gui.pushButton_Loop.setEnabled(True)
        self.gui.pushButton_Stop.setEnabled(True)
        self.gui.pushButton_REC.setEnabled(True)
        self.gui.verticalSlider_Gain.setEnabled(True)
        self.gui.playrec_label_REC_duration.setStyleSheet("background-color : lightgray")
        font = self.gui.playrec_label_REC_duration.font()
        font.setPointSize(14)
        self.gui.playrec_label_REC_duration.setFont(font)
        self.gui.checkBox_UTC.setEnabled(True)
        self.gui.label_32.setStyleSheet("background-color : lightgrey")
        self.gui.label_32.setEnabled(False)
        self.m["playlist_active"] = False
        self.gui.lineEditCurTime.setText("")

    def indicate_bufoverflow(self):
        """_indicate if during recording a buffer underflow occurred
        :return: none
        :rtype: none
        """        
        print("playrec RECORDING: bufferoverflow")
        self.gui.label_32.setStyleSheet("background-color : red")
        self.gui.label_32.setEnabled(True)

    def canvasbuild(self,gui):
        """
        sets up a canvas to which graphs can be plotted
        Use: calls the method auxi.generate_canvas with parameters self.gui.gridlayoutX to specify where the canvas 
        should be placed, the coordinates and extensions in the grid and a reference to the QMainwidget Object
        generated by __main__ during system startup. This object is relayed via signal to all modules at system initialization 
        and is automatically available (see rxhandler method)
        the reference to the canvas object is written to self.cref
        :param : gui
        :type : QMainWindow
        :raises [ErrorType]: [ErrorDescription]
        :return: none
        :rtype: none
        """
        # self.cref = auxi.generate_canvas(self,self.gui.gridLayout_10,[13,11,1,2],[-1,-1,-1,-1],gui)
        # self.cref["ax"].tick_params(axis='both', which='major', labelsize=6)
        self.plot_widget = pg.PlotWidget()
        self.gui.gridLayout_10.addWidget(self.plot_widget,13,11,1,2)
        self.plot_widget.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 6))
        self.plot_widget.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 6))
        self.plot_widget.setBackground('w')
        self.xdata = np.linspace(0, 10, 100)
        self.ydata = np.sin(self.xdata)
        ymin = -120
        ymax = 0
        self.plot_widget.setYRange(ymin, ymax)
        self.curve = self.plot_widget.plot(self.xdata, self.ydata)
        #xdata = np.linspace(0, 10, 100)
        #ydata = np.sin(xdata)

        # Plot the data in the PlotWidget
        #plot_widget.plot(xdata, ydata)
        #self.gui.gridLayout_10,[13,11,1,2],[-1,-1,-1,-1]
        #layout.addWidget(plot_widget, 0, 0)

    def showRFdata(self):
        """_take over datasegment from player loop worker and caluclate from there the signal volume and present it in the volume indicator
        read gain value and present it in the player Tab on the 'progressbar' Widget 'progressBar_volume'
        Parameters: a = length form top to 0dB tick
        b = length between -80 and 0 dB ticks
        c = length between bottom and -80dB tick
        a+b+c = total length of the indicator and hence of the progress-bar volume 
        GUI Element
        :return: _False if error, True on succes_
        :rtype: _Boolean_
        """
        scal_NEW = True
        # geometry scaling; absolute numbers are not relevant, only relative lengths
        #a = #10/139.5 #7/86  
        c = 11/89 #16.5/139.5 #8/86
        b = 72/89 #(139.5 - 10 -16.5)/139.5 #(86 -7 -8)/86
        # if self.m["TEST"]:
        #     return
        self.m["gain"] = self.playrec_c.playrec_tworker.get_gain()
        #print(f"get gain in showRFdata gain: {self.m['gain']}")
        self.logger.debug("get from tworker gain to showRFdata: %f",self.m["gain"])
        data = self.playrec_c.playrec_tworker.get_data()
        if len(data) < 256: # skip data monitoring if len(data) < 8, coding for the need of extra fast processing
            #print(f"showRDdata: len(data) = {len(data)} < 256, no data shown")
            return
        #tracking error detector removed, appears in old main module
        s = len(data)
        #time.sleep(1)
        #print(f"############### playrec recloop data: {data[0]}")
        nan_ix = [i for i, x in enumerate(data) if np.isnan(x)]
        if np.any(np.isnan(data)):
            self.m["stopstate"] = True
            #time.sleep(1)
            data[nan_ix] = np.zeros(len(nan_ix))
            self.logger.error("show RFdata: NaN found in data, length: %i ,maxval: %f , avg: %f" , len(nan_ix),  np.max(data), np.median(data))
            #sys_state.set_status(system_state)
            return(False)
        cv = (data[0:s-1:2].astype(np.float32) + 1j * data[1:s:2].astype(np.float32))*self.m["gain"]
        if self.m["wavheader"]['wFormatTag'] == 1:
            normfactor = int(2**int(self.m["wavheader"]['nBitsPerSample']-1))-1
        elif self.m["wavheader"]['wFormatTag']  == 3:
            normfactor = 1 #TODO:future system state
        else:
            auxi.standard_errorbox("wFormatTag is neither 1 nor 3; unsupported Format, this file cannot be processed")
            #sys_state.set_status(system_state)
            return False
        
        ####TODO: check spectrum for debugging
      
        if self.m["SPECDEBUG"]:
            spr = np.abs(np.fft.fft(cv))
            N = len(spr)
            spr = np.fft.fftshift(spr)/N/normfactor
            flo = self.m["wavheader"]['centerfreq'] - self.m["wavheader"]['nSamplesPerSec']/2
            freq0 = np.linspace(0,self.m["wavheader"]['nSamplesPerSec'],N)
            freq = freq0 + flo
            datax = (np.floor(freq/1000))
            datay = 20*np.log10(spr)
            self.curve.setData(datax, datay)

        if self.m["TEST"]:
            return
        if scal_NEW:
            span = 80
            refvol = 0.71
            vol = 1.5*np.std(cv)/normfactor/refvol
            dBvol = 20*np.log10(vol)
            rawvol = c + b + dBvol/span*b
            if dBvol > 0:
              dispvol = min(100, rawvol*100)
            elif (dBvol < 0) and (dBvol > -span):
              dispvol = rawvol*100
            elif dBvol < -span:
              dispvol = c*0.8*100
            if np.any(np.isnan(dispvol)):
                return
            #print(f"vol: {vol} dB: {dBvol} std: {np.std(cv)/normfactor} dispvol: {dispvol} rv: {np.std(cv)/normfactor}")
            self.gui.progressBar_volume.setValue(int(np.floor(dispvol*10))) 
            if dBvol > -7:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: red;"
                        "}")
            elif dBvol < -70:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: yellow;"
                        "}")           
            else:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: green;"
                        "}")
        else:
            av = np.abs(cv)/normfactor  #TODO rescale according to scaler from formattag
            refvol = 0.5
            vol = np.mean(av)/refvol
            # make vol a dB value and rescale to 1000
            # 900 = 0 dB
            # 1000 = overload und mache Balken rot
            # min Anzeige = 1 entspricht -100 dB
            dBvol = 20*np.log10(vol)
            dispvol = min(dBvol + 80, 100)
            if np.any(np.isnan(dispvol)):
                return
            self.gui.progressBar_volume.setValue(int(np.floor(dispvol*10))) 
            if dispvol > 80:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: red;"
                        "}")
            elif dispvol < 30:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: yellow;"
                        "}")           
            else:
                self.gui.progressBar_volume.setStyleSheet("QProgressBar::chunk "
                        "{"
                            "background-color: green;"
                        "}")




    def updatecurtime(self,increment):             #TODO: check if can be implemented with less ressources need
        """
        _increments time indicator by value in increment, except for 0. 
        With increment == 0 the indicator is reset to 0
        if self.modality == "play":
            - update position slider
            - set file read pointer to new position, |if increment| > 1
        :param : increment
        :type : int
        '''
        :raises [ErrorType]: [ErrorDescription]
        '''
        :return: True/False on successful/unsuccesful operation
        :rtype: bool
        """ 
        #TODO: remove after tests:
        #reftime = datetime.now()
        if not self.m["fileopened"]:
            return
        if increment == 0:
            timestr = str(ndatetime.timedelta(seconds=0))
            self.m["curtime"] = 0
            self.gui.lineEditCurTime.setText(timestr)
        delta =  datetime.now() - self.lastupdatecurtime
        #print(f"updateurtime microsec: {delta}")
        if delta.microseconds < 10000:
            return
        #print(f"updatecurtime UPDATECURTIME: {increment}")
        #self.m["timescaler"] = self.m["wavheader"]['nSamplesPerSec']*self.m["wavheader"]['nBlockAlign'] #TODO: TEST after 04-02-2025; can be shifted to the instant where the wav ehader is opened
        self.m["playprogress"] = 0 #TODO: always ?
        #time.sleep(0.00001) #TODO why so long ?
        timestr = str(self.m["wavheader"]['starttime_dt'] + ndatetime.timedelta(seconds=self.m["curtime"]))
        #print(f">>>>>>>>>>>>> updatecurtime: wavheaderstarttime: {self.m['wavheader']['starttime_dt']} curtime: {self.m['curtime']}")
        true_filesize = os.path.getsize(self.m["f1"]) #TODO: can be calculated outside on file opening in the play thread
        playlength = true_filesize/self.m["wavheader"]['nAvgBytesPerSec']
        #print(f"updatecurtime playlength: {playlength}, filesize: {true_filesize}, bytespersec: {self.m["wavheader"]['nAvgBytesPerSec']}") #TODO: can be calculated outside on file opening
        if self.m["modality"] == 'play' and self.m["pausestate"] is False:
            if self.m["curtime"] > 0 and increment < 0:
                self.m["curtime"] += increment
            if self.m["curtime"] < playlength and increment > 0:
                self.m["curtime"] += increment
            if playlength > 0:
                self.m["playprogress"] = int(np.floor(1000*(self.m["curtime"]/playlength)))
            else:
                return False
            position_raw = self.m["curtime"]*self.m["timescaler"]
            # TODO: check, geändert 09-12-2023: byte position mit allen Blockaligns auch andere als 4(16 bits); 
            # TODO: adapt for other than header 216
            position = min(max(216, position_raw-position_raw % self.m["wavheader"]['nBlockAlign']),
                           self.m["wavheader"]['data_nChunkSize'])
            # guarantee integer multiple of nBlockalign, > 0, <= filesize
            if increment != -1 and increment != 1 or self.m["timechanged"] == True:
                if self.m["fileopened"] and self.m["playthreadActive"] is True:
                    #print(f'increment curtime cond seek cur file open: {system_state["f1"]}')
                    try:
                        self.prfilehandle = self.playrec_c.playrec_tworker.get_fileHandle()
                        
                    except:
                         #TODO: intro standard errorhandling
                         auxi.standard_errorbox("Cannot activate background thread (tworker), maybe SDR device (STEMLAB ?) is not connected")
                         self.SigRelay.emit("cexex_all_",["reset_GUI",0])
                         self.SigRelay.emit("cm_all_",["fileopened",False]) ###TODO: Test after 09-04-2024 !
                         print("updatecurtime playrec tworker.get4() not callable")
                         return False
                    try:
                        self.prfilehandle.seek(int(position), 0) #TODO: Anpassen an andere Fileformate
                    except:
                        self.logger.error("playrec.updatecurtimer: seek in closed file error")
        else:
            self.m["curtime"] += increment
            timestr = str(ndatetime.timedelta(seconds=0) + ndatetime.timedelta(seconds=self.m["curtime"]))
        if not self.gui.playrec_radioButton_RECAUTOSTART.isChecked():
            self.gui.lineEditCurTime.setText(timestr)
            #TODO TODO TODO: display true time since start of recording in hours!
        self.gui.ScrollBar_playtime.setProperty("value", self.m["playprogress"])
        #self.lastupdatecurtime = datetime.now()
        #elapsed_time = datetime.now() - reftime
        #TODO: remove after tests:
        #print(f"updatecurtime elapsed time: {elapsed_time}")
        return True
    
    
    def reset_LO_bias(self):
        """ Purpose: reset LO bias setting to 0; 
        :param [ParamName]: none
        :type [ParamName]: none
        :raises none
        :return: none
        :rtype: none
        """
        self.gui.radioButton_LO_bias.setChecked(False)
        self.gui.radioButton_LO_bias.setEnabled(True)
        self.m["LO_offset"] = 0
        self.gui.lineEdit_LO_bias.setText("0")
        self.gui.lineEdit_LO_bias.setStyleSheet("background-color: white")

    def update_LO_bias(self,*args):
        """ Purpose: update LO bias setting; 
        check validity of offset value: isnumeric, integer
        *args: optional first argument "verbose": then an errormessage is displayed if LO cannot be changed
               optional second argument "change" or "unchanged": change means that the buttobgroup checkstatus is not changed in case of an error
        :param [ParamName]: args
        :type [ParamName]: str
        :raises none
        :return: True if successful, otherwise False
        :rtype: Boolean
        """

        if len(args) > 0:
            errormode = args[0]
            try:
                changemod = args[1]
            except:
                changemod = "nochange"
                pass
            if self.m["playthreadActive"]: # and (not self.norepeat):
                if errormode.find("verbose") == 0: 
                    auxi.standard_errorbox("LO bias cannot be changed while file is playing")
                if changemod.find("change") == 0:
                    #leave current buttonstate unchanged, because action was triggered by change of checkstatus
                    #self.norepeat = True
                    self.toggle_LO_bias()
                return False
            # else:
            #     self.norepeat = False   
        LObiasraw = self.gui.lineEdit_LO_bias.text().lstrip(" ")
        if len(LObiasraw) < 1:
            return False
        LObias_sign = 1
        if LObiasraw[0] == "-":
            LObias_sign = -1
            LObias_test = LObiasraw.lstrip("-")
            if len(LObias_test)<1:
                return False
        else:
            LObias_test = LObiasraw
        if LObias_test.isnumeric() == True: 
            i_LO_bias = LObias_sign*int(LObias_test)
        else:
            auxi.standard_errorbox("invalid numeral in center frequency offset field, please enter valid integer value (kHz)")
            self.reset_LO_bias()
            return False
        #transfer to systemstate
        if self.gui.radioButton_LO_bias.isChecked() is True:
            self.m["LO_offset"] = int(i_LO_bias*1000)
            self.m["ifreq"] = int(self.m["wavheader"]['centerfreq'] + self.m["LO_offset"])
        else:
            self.m["LO_offset"] = 0
            self.m["ifreq"] = int(self.m["wavheader"]['centerfreq'] + self.m["LO_offset"])
        return True
    
    def activate_LO_bias(self):
        """ Purpose: handle radiobutton for LO bias setting; 
        (1) highlight LO_lineEdit window
        (2) call update of offset value
        :param [ParamName]: none
        :type [ParamName]: none
        :raises none
        :return: none
        :rtype: none
        """
        #i_LO_bias = 0 ###TODO: activate ???
        self.gui.lineEdit_LO_bias.setStyleSheet("background-color: white")
        #TODO: ACTIVATE LObias check code
        if self.gui.radioButton_LO_bias.isChecked() is True:
            self.gui.lineEdit_LO_bias.setEnabled(True)
            self.gui.lineEdit_LO_bias.setStyleSheet("background-color: yellow")
        else:
            self.gui.lineEdit_LO_bias.setEnabled(False)
            self.gui.lineEdit_LO_bias.setStyleSheet("background-color: white")
        self.update_LO_bias("verbose","change")

    def toggle_LO_bias(self):
        """ Purpose: toggle status of the radiobuttongoup for LO bias setting; 
        (1) highlight/unhighligt LO_lineEdit
        (2) check/uncheck Radiobutton
        (3) enable/disable LO_lineEdit
        :param [ParamName]: none
        :type [ParamName]: none
        :raises none
        :return: none
        :rtype: none
        """
        if self.gui.radioButton_LO_bias.isChecked() is True:
            self.gui.radioButton_LO_bias.setChecked(False)
            self.gui.lineEdit_LO_bias.setEnabled(False)
            self.gui.lineEdit_LO_bias.setStyleSheet("background-color: white")
        else:
            self.gui.radioButton_LO_bias.setChecked(True)
            self.gui.lineEdit_LO_bias.setEnabled(True)
            self.gui.lineEdit_LO_bias.setStyleSheet("background-color: yellow")


    def editHostAddress(self):     #TODO Check if this is necessary, rename to cb_.... ! 
        ''' 
        Purpose: Callback for edidHostAddress Lineedit item
        activate Host IP address field and enable saving mode
        Returns: nothing
        '''
        self.gui.lineEdit_IPAddress.setEnabled(True)
        self.gui.lineEdit_IPAddress.setReadOnly(False)
        self.gui.pushButton_IP.clicked.connect(self.set_IP)
        self.gui.pushButton_IP.setText("save IP Address")
        self.gui.pushButton_IP.adjustSize()
        self.IP_address_set = False

    def set_IP(self):
        """ 
        set IP Address and save to config yaml
            disable IP address line
            enable Button for editing address 
        :param: none
        :type: none
        ...
        :raises warning message: Read error if config_wizard.yaml does not exist
        ...
        :return: none
        :rtype: none
        """
        #system_state = sys_state.get_status()
        #self.HostAddress = self.gui.Conf_lineEdit_IPAddress.text()
        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text()
        #print("IP address read")
        try:
            stream = open("config_wizard.yaml", "r")
            self.metadata = yaml.safe_load(stream)
            stream.close()
        except:
            auxi.standard_errorbox("Cannot open Config File")
            self.logger.error("cannot get metadata")
            #print("cannot get metadata")
        self.metadata["STM_IP_address"] = self.m["HostAddress"]
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.metadata, stream)

        self.gui.lineEdit_IPAddress.setReadOnly(True)
        self.gui.lineEdit_IPAddress.setEnabled(False)
        self.gui.pushButton_IP.clicked.connect(self.editHostAddress)
        self.gui.pushButton_IP.setText("Set IP Address")
        self.gui.pushButton_IP.adjustSize()
        self.SigRelay.emit("cm_xcore",["HostAddress",self.m["HostAddress"]])





    # def play_loop16(self):
    #     """
    #     worker loop for sending data to STEMLAB server
    #     data format i16; 2xi16 complex; FormatTag 1
    #     sends signals:     
    #         SigFinished = pyqtSignal()
    #         SigIncrementCurTime = pyqtSignal()
    #         SigBufferOverflow = pyqtSignal()

    #     :param : no regular parameters; as this is a thread worker communication occurs via
    #     class slots __slots__[i], i = 0...8
    #     __slots__[0]: filename = complete file path pathname/filename Type: str TODO TODO TODO: --> NEW: list
    #     __slots__[1]: timescaler = bytes per second  TODO: rescaling to samples per second would probably be more logical, Type int
    #     __slots__[2]: TEST = flag for test mode Type: bool
    #     __slots__[3]: pause : if True then do not send data; Boolean
    #     __slots__[4]: filehandle: returns current filehandle to main thread Type: filehandle
    #     __slots__[5]: data segment to be returned every second
    #     __slots__[6]: gain, scaling factor for playback
    #     __slots__[7]: formatlist: [formattag blockalign bitpsample]
    #     __slots__[8]: datablocksize
    #     __slots__[9]: fileclose: set to True after closing a file, info to main Thread
    #     """
    #     #print("reached playloopthread")
    #     filename = self.get_filename()
    #     timescaler = self.get_timescaler()
    #     TEST = self.get_TEST()
    #     gain = self.get_gain()
    #     #TODO: self.fmtscl = self.__slots__[7] #scaler for data format        
    #     self.stopix = False
    #     fileHandle = open(filename, 'rb')
    #     self.set_fileclose(False)
    #     #print(f"filehandle for set_4: {fileHandle} of file {filename} ")
    #     self.set_fileHandle(fileHandle)
    #     format = self.get_formattag()
    #     self.set_datablocksize(self.DATABLOCKSIZE)
    #     #print(f"Filehandle :{fileHandle}")

    #     fileHandle.seek(216, 1)  #TODO: other formats than wav SDRUno not supported !
    #     #TODO: if format[0] == 1 and format[2] == 16 
    #     #data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
    #     #TODO: if format[0] == 1 and format[2] == 32
    #     if format[2] == 16:
    #         data = np.empty(self.DATABLOCKSIZE, dtype=np.int16)
    #     else:
    #         data = np.empty(self.DATABLOCKSIZE, dtype=np.float32) #TODO: check if true for 32-bit wavs wie Gianni's

    #     #print(f"playloop: BitspSample: {format[2]}; wFormatTag: {format[0]}; Align: {format[1]}")
    #     if format[0] == 1:
    #         normfactor = int(2**int(format[2]-1))-1
    #     else:
    #         normfactor = 1
    #     #print(f"normfactor = {normfactor}")
    #     if format[2] == 16 or format[2] == 32:
    #         size = fileHandle.readinto(data)
    #     elif format[2] == 24:
    #         data = self.read24(format,data,fileHandle)
    #         size = len(data)

    #     self.set_data(data)
    #     junkspersecond = timescaler / self.JUNKSIZE
    #     count = 0
    #     # print(f"Junkspersec:{junkspersecond}")
    #     while size > 0 and not self.stopix:
    #         if not TEST:
    #             if not self.get_pause():
    #                 try:
    #                     self.stemlabcontrol.data_sock.send(
    #                                             gain*data[0:size].astype(np.float32)
    #                                             /normfactor)  # send next DATABLOCKSIZE samples
    #                 except BlockingIOError:
    #                     print("Blocking data socket error in playloop worker")
    #                     time.sleep(0.1)
    #                     self.SigError.emit("Blocking data socket error in playloop worker")
    #                     self.SigFinished.emit()
    #                     time.sleep(0.1)
    #                     return
    #                 except ConnectionResetError:
    #                     print("Diagnostic Message: Connection data socket error in playloop worker")
    #                     time.sleep(0.1)
    #                     self.SigError.emit("Diagnostic Message: Connection data socket error in playloop worker")
    #                     self.SigFinished.emit()
    #                     time.sleep(0.1)
    #                     return
    #                 except Exception as e:
    #                     print("Class e type error  data socket error in playloop worker")
    #                     print(e)
    #                     time.sleep(0.1)
    #                     self.SigError.emit(f"Diagnostic Message: Error in playloop worker: {str(e)}")
    #                     self.SigFinished.emit()
    #                     time.sleep(0.1)
    #                     return
    #                 if format[2] == 16 or format[2] == 32:
    #                     size = fileHandle.readinto(data)
    #                 elif format[2] == 24:
    #                     data = self.read24(format,data,fileHandle)
    #                     size = len(data)

    #                 #  read next 2048 samples
    #                 count += 1
    #                 if count > junkspersecond:
    #                     self.SigIncrementCurTime.emit()
    #                     count = 0
    #                     #self.mutex.lock()
    #                     gain = self.get_gain()
    #                     #print(f"diagnostic: gain in worker: {gain}")
    #                     self.set_data(data)
    #                     #self.mutex.unlock()
    #             else:
    #                 #print("Pause, do not do anything")
    #                 time.sleep(0.1)
    #                 if self.stopix is True:
    #                     break
    #         else:
    #             if not self.get_pause():
    #                 #print("test reached")
    #                 if format[2] == 16 or format[2] == 32:
    #                     size = fileHandle.readinto(data)
    #                 elif format[2] == 24:
    #                     data = self.read24(format,data,fileHandle)
    #                     size = len(data)
    #                 #print(f"size read: {size}")
    #                 #print(data[1:10])
    #                 #size = fileHandle.readinto(data)
    #                 time.sleep(0.0001)
    #                 #  read next 2048 bytes
    #                 count += 1
    #                 if count > junkspersecond and size > 0:
    #                     #print('timeincrement reached')
    #                     self.SigIncrementCurTime.emit()
    #                     gain = self.get_gain()
    #                     #print(f"diagnostic: gain in worker: {gain}")
    #                     #print(f"maximum: {np.max(data)}")
    #                     #self.set_data(gain*data)
    #                     self.set_data(data)
    #                     count = 0
    #             else:
    #                 time.sleep(1)
    #                 if self.stopix is True:
    #                     break
    #     #print('worker  thread finished')
    #     self.set_fileclose(True)
    #     self.SigFinished.emit()
    #     #print("SigFinished from playloop emitted")
