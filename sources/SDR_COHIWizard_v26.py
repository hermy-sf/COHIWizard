# -*- coding: utf-8 -*-logfile
# Um alle print messages auf logfile umzuleiten: Aktiviere am Ende des init-Teils: sys.stdout = self.logfile
#statt: self.menubar = File(MainWindow)
#self.menubar = QtWidgets.QMenuBar(MainWindow)
#pyinstaller --icon=COHIWizard_ico4.ico –F SDR_COHIWizard_v26.py
#pyuic5 -x  COHIWizard_GUI_v10.ui -o COHIWizard_GUI_v10.py
# For reducing to RFCorder: place the following just before the line with 
#check if sox is installed so as to throw an error message on resampling, if not
#        self.soxlink = "https://sourceforge.net/projects/sox/files/sox/14.4.2/"
#Bei Änderungen des Gridlayouts und Neuplazierung der canvas:
#self.generate_canvas(self,self.gui.gridLayout_5,[4,0,7,4],[-1,-1,-1,-1],self.Tabref["Resample"])
#in init_Tabref()
# in the GUI init method:

        # #THIS IS JUST A VERSION OF COHIWizard_v25; Here I disable all unnecessary tabs and functions
        # self.gui.tabWidget.removeTab(4)
        # self.gui.tabWidget.removeTab(3)
        # self.gui.tabWidget.removeTab(2)
        # self.gui.tabWidget.removeTab(1)
        # # Resampling only in direct mode without LO shifting
        # self.gui.lineEdit_resample_targetLO.textEdited.disconnect()
        # self.gui.lineEdit_resample_targetLO.setEnabled(False)
        # self.gui.actionOverwrite_header.setVisible(False)
# Start-Tab setzen:self.gui.tabWidget.setCurrentIndex(1) #TODO: avoid magic number, unidentified

"""
Created on Sa Dec 08 2023

#@author: scharfetter_admin
"""
import sys
import os
import time
import subprocess
import datetime as ndatetime
from datetime import datetime
from pathlib import Path, PureWindowsPath
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg,  NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import yaml
import logging
from COHIWizard_GUI_v10 import Ui_MainWindow as MyWizard
from auxiliaries import WAVheader_tools
from auxiliaries import auxiliaries as auxi
from auxiliaries import timer_worker as tw
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QMutex       #TODO: OBSOLETE
import resampler_module_v5 as rsmp
import view_spectra as vsp
import annotate as ann
import yaml_editor as yed
import waveditor as waved
from stemlab_control import StemlabControl
import playrec
#import configuration as conf

class starter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.gui= MyWizard()
        self.gui.setupUi(self)
        self.gui.tableWidget_basisfields.verticalHeader().setVisible(True)

class core_m(QObject):
    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["sample"] = 0
        self.mdl["_log"] = False
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
        self.logger.debug('Init logger in configuration method reached')


class core_c(QObject):
    """_view method
    """
    __slots__ = ["contvars"]

    SigAny = pyqtSignal()
    SigRelay = pyqtSignal(str,object)

    def __init__(self, core_m): #TODO: remove gui
        super().__init__()

        self.m = core_m.mdl
        self.logger = core_m.logger


    def recording_path_checker(self):
        """
        checks, if recording path exists in config_wizard.yaml and if the path exists in the system
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
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
        except:
            self.ismetadata = False
        recfail = False
        if "recording_path" not in self.m["metadata"]:
            recfail = True
            auxi.standard_infobox("recordingpath does not exist, please define later")
            return False
        elif not os.path.isdir(self.m["metadata"]["recording_path"]):
            recfail = True
        if recfail:
            options = QFileDialog.Options()
            options |= QFileDialog.ShowDirsOnly
            self.m["recording_path"] = ""
            while len(self.m["recording_path"]) < 1:
                try:
                    self.m["recording_path"] = QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Select Recording Directory", options=options)
                except:
                    return
                if len(self.m["recording_path"]) < 1:
                    auxi.standard_errorbox("Recording path must be defined, please define it by clicking OK !")
            self.logger.debug("playrec recording path: %s", self.m["recording_path"])
            self.m["metadata"]["recording_path"] = self.m["recording_path"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
        else:
            self.m["recording_path"] = self.m["metadata"]["recording_path"]
        self.logger.debug("playrec recording button recording path: %s", self.m["recording_path"])
        self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])
        self.SigRelay.emit("cexex_xcore",["updateConfigElements",0])

    def recording_path_setter(self):
        """
        checks, if recording path exists in config_wizard.yaml and if the path exists
        if not: ask for target pathname and store in config.wizard.yaml
        param: none
        type: none
        :raises [none]: [none]
        :return: none
        :rtype: none
        """         
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        self.m["recording_path"] = QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Select Recording Directory", options=options)
        self.logger.debug("playrec recording path: %s", self.m["recording_path"])
        self.m["metadata"]["recording_path"] = self.m["recording_path"]
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()
        self.m["recording_path"] = self.m["metadata"]["recording_path"] #TODO: check ? obsolete ?
        self.logger.debug("playrec recording button recording path: %s", self.m["recording_path"])
        #print("core_c send recordingpath to all")
        self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])        
        self.SigRelay.emit("cexex_xcore",["updateConfigElements",0])

class core_v(QObject):

    __slots__ = ["viewvars"]

    #TODO KIPP: 
    SigUpdateGUI = pyqtSignal(object)
    #SigUpdateGUI = pyqtSignal() #TODO KIPP: remove
    SigToolbar = pyqtSignal()
    SigGP = pyqtSignal()
    SigProgress = pyqtSignal()
    SigGUIReset = pyqtSignal()
    SigEOFStart = pyqtSignal()
    SigSyncTabs = pyqtSignal(object)
    SigUpdateOtherGUIs = pyqtSignal()
    SigRelay = pyqtSignal(str,object)

    def __init__(self, gui, core_c, core_m):
        super().__init__()
        print("Initializing GUI, please wait....")
        self.m = core_m.mdl
        self.core_c = core_c
        #self.OLD = True #TODO KIPP: remove
        self.TEST = True    # Test Mode Flag for testing the App, --> playloop  ##NOT USED #TODO:future system status
        #self.DATABLOCKSIZE = 1024*32 # für diverse Filereader/writer TODO: occurs in plot spectrum and ANN_Spectrum; must be shifted to the respective modules in future
        #self.PROMINENCE = 15 ######### minimum peak prominence in dB above baseline for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.bps = ['16', '24', '32'] #TODO:future system state
        self.standardLO = 1100 #TODO:future system state
        self.annotationdir_prefix = 'ANN_' ##################TODO:future system state
        self.position = 0 #TODO:future system state URGENT !!!!!!!!!!!!!!
        self.tab_dict = {}
        self.m["recording_path"] = ""

        self.GUIupdaterlist =[]
        # create method which inactivates all tabs except the one which is passed as keyword
        self.GUI_reset_status()
        self.gui = gui.gui

        self.tab_names = {}
        for index in range(self.gui.tabWidget.count()):
            self.tab_names[index] = self.gui.tabWidget.tabText(index)

        # self.gui = MyWizard()
        # self.gui.setupUi(self)
        # self.gui.tableWidget_basisfields.verticalHeader().setVisible(True)   
        self.gui.actionFile_open.triggered.connect(self.cb_open_file)
        #self.gui.actionfileopen_ref.triggered.connect(self.cb_open_file)
        self.SigGUIReset.connect(self.reset_GUI)


        #self.gui.pushButton_resample_GainOnly.setEnabled(False)
        #self.gui.tabwidget_ref.setCurrentIndex(1) #TODO: avoid magic number, make config issue
        #self.gui.lineEdit_IPAddress.setInputMask('000.000.000.000')
        #self.gui.lineEdit_IPAddress.setTabChangesFocus(True)  # Allow Tab key to change focus
        #self.gui.lineEdit_IPAddress.installEventFilter(self)  # Install event filter
        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.gui.tabWidget.setCurrentIndex(0) #TODO: avoid magic number, make config issue
        self.gui.playrec_comboBox_startuptab.setCurrentIndex(0)
        self.standardpath = os.getcwd()  #TODO: this is a core variable in core model
        self.m["metadata"] = {"last_path": self.standardpath}
        self.ismetadata = False
        self.gui.lineEdit_IPAddress.setInputMask('000.000.000.000')
        self.gui.lineEdit_IPAddress.setText("000.000.000.000")
        self.gui.lineEdit_IPAddress.setEnabled(False)
        self.gui.lineEdit_IPAddress.setReadOnly(True)
        self.gui.pushButton_IP.clicked.connect(self.editHostAddress)
        #self.gui.Conf_lineEdit_IPAddress.setEnabled(True)
        #self.gui.Conf_lineEdit_IPAddress.setReadOnly(False)
        #self.gui.pushButton_IP.clicked.connect(self.set_IP)
        self.gui.lineEdit_IPAddress.returnPressed.connect(self.set_IP)
        self.gui.pushButton_IP.setText("set IP Address")
        self.gui.pushButton_IP.adjustSize()

        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
            if "STM_IP_address" in self.m["metadata"]:
                self.gui.lineEdit_IPAddress.setText(self.m["metadata"]["STM_IP_address"])
            if "recording_path" in self.m["metadata"]:
                self.m["recording_path"] = self.m["metadata"]["recording_path"]
            if "startup_tab" in self.m["metadata"]:
                ###TODO: re-organize, there should be no access to gui elements of other modules
                #self.gui.playrec_comboBox_startuptab.setCurrentIndex(int(self.m["metadata"]["startup_tab"]))
                self.gui.tabWidget.setCurrentIndex(int(self.m["metadata"]["startup_tab"]))
                self.gui.playrec_comboBox_startuptab.setCurrentIndex(int(self.m["metadata"]["startup_tab"]))
        except:
            print("cannot get config_wizard.yaml metadata, write a new initial config file")
            self.m["metadata"]["last_path"] = os.getcwd()
            self.m["metadata"]["STM_IP_address"] = "000.000.000.000"
            self.m["metadata"]["recording_path"] = ""
            auxi.standard_infobox("configuration file does not yet exist, a basic file will be generated. Please configure the STEMLAB IP address before using the Player")
            
            #self.m["metadata"]["recording_path"] = self.m["recording_path"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()

        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text() #TODO: Remove after transfer of playrec
        self.m["sdr_configparams"] = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
                            "rates": self.m["rates"], "icorr":self.m["icorr"],
                            "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        #self.m["sdr_configparams"] = configparams
        self.m["f1"] = ""
        self.m["_log"] = False
        self.Tabref={}
        self.init_Tabref()
        self.timeref = datetime.now()    #TODO TODO TODO: remove, no 2 autoscaninstances !

        # Create a custom logger
        # Setze den Level des Root-Loggers auf DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        # Erstelle einen Logger mit dem Modul- oder Skriptnamen
        self.logger = logging.getLogger(__name__)
        # Create handlers
        warning_handler = logging.StreamHandler()
        debug_handler = logging.FileHandler("system_log.log","w")
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
            print(ex.stdout, file=sys.stdout, end='', flush=True)
            if len(ex.stderr) > 0: 
                self.soxnotexist = True
        self.logger.info("core_v Init logger in core reached")
        #self.core_c.SigRelay.connect(self.SigRelay.emit)        
        self.core_c.SigRelay.connect(self.rxhandler)
        #self.core_c.recording_path_checker()
        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.gui.playrec_radioButtonpushButton_write_logfile.clicked.connect(self.togglelogfilehandler)
        self.gui.playrec_radioButtonpushButton_write_logfile.setChecked(True)
        self.gui.playrec_pushButton_recordingpath.clicked.connect(self.core_c.recording_path_setter)
        #self.updateGUIelements()
        self.updateConfigElements()
        self.timethread = QThread()
        self.timertick = tw()
        self.timertick.moveToThread(self.timethread)
        self.timethread.started.connect(self.timertick.tick)
        self.timertick.SigFinished.connect(self.timethread.quit)
        self.timertick.SigFinished.connect(self.timertick.deleteLater)
        self.timethread.finished.connect(self.timethread.deleteLater)
        self.timertick.SigTick.connect(self.updatetimer)
        self.timethread.start()
        if self.timethread.isRunning():
            self.timethreaddActive = True #TODO:future system state

    # def eventFilter(self, source, event):
    #     if (event.type() == Qt.KeyPress and
    #         event.key() == Qt.Key_Tab and
    #         source is self.gui.lineEdit_IPAddress):
    #         cursor = self.gui.lineEdit_IPAddress.cursorPosition()
    #         if cursor == 3 or cursor == 7 or cursor == 11:  # Check if cursor is at the end of each field
    #             self.gui.lineEdit_IPAddress.setCursorPosition(cursor + 1)  # Move cursor to the next field
    #             return True  # Ignore default Tab key behavior
    #     return super().eventFilter(source, event)

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

        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text()

        print("setIP")
        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
        except:
            auxi.standard_errorbox("Cannot open Config File")
            self.logger.error("cannot get metadata")
            #print("cannot get metadata")
        self.m["metadata"]["STM_IP_address"] = self.m["HostAddress"]
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)

        self.gui.lineEdit_IPAddress.setReadOnly(True)
        self.gui.lineEdit_IPAddress.setEnabled(False)
        self.gui.pushButton_IP.clicked.connect(self.editHostAddress)
        self.gui.pushButton_IP.setText("Set IP Address")
        self.gui.pushButton_IP.adjustSize()
        self.SigRelay.emit("cm_xcore",["HostAddress",self.m["HostAddress"]])

    def connect_init(self):
        self.SigRelay.emit("cm_all_",["emergency_stop",False])
        self.SigRelay.emit("cm_all_",["fileopened",False])
        self.SigRelay.emit("cm_all_",["Tabref",self.Tabref])
        self.SigRelay.emit("cm_resample",["rates",self.m["rates"]])
        self.SigRelay.emit("cm_resample",["irate",self.m["irate"]])
        self.SigRelay.emit("cm_playrec",["rates",self.m["rates"]])
        self.SigRelay.emit("cm_playrec",["irate",self.m["irate"]])
        self.SigRelay.emit("cm_resample",["reslist_ix",self.m["reslist_ix"]]) #TODO check: maybe local in future !
        self.SigRelay.emit("cm_playrec",["Obj_stemlabcontrol",stemlabcontrol])
        self.SigRelay.emit("cm_configuration",["tablist",tab_dict["list"]])
        #self.SigRelay.emit("cexex_core",["updateGUIelements",0])
        self.SigRelay.emit("cm_playrec",["sdr_configparams",self.m["sdr_configparams"]])
        self.SigRelay.emit("cm_playrec",["HostAddress",self.m["HostAddress"]])
        self.core_c.m["QTMAINWINDOWparent"] = gui
        self.SigRelay.emit("cm_all_",["QTMAINWINDOWparent",gui])
        pass


    def togglelogfilehandler(self):
        if self.gui.playrec_radioButtonpushButton_write_logfile.isChecked():
            self.logger.setLevel(logging.NOTSET)
            self.SigRelay.emit("cexex_all_",["logfilehandler",False])
        else:
            self.logger.setLevel(logging.DEBUG)
            self.SigRelay.emit("cexex_all_",["logfilehandler",True])


    def updateGUIelements(self):
        """
        dummy method, not really used in the core module but pre-configured for sake of compatibility with the general module structure
        :param : none
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: none
        :rtype: none
        """
        pass

    def updateConfigElements(self):
        """
        updates some Configuration elements
        this method is connected in the __main__ of the core module
        :param : none
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        try:
            self.gui.playrec_lineEdit_recordingpath.setText(self.m["recording_path"])
        except:
            self.core_c.recording_path_checker()
            #self.configuration_c.recording_path_setter()
        # for count, ele in enumerate(self.m["tablist"]):
        #     self.gui.checkboxlist.append(QtWidgets.QCheckBox(self.gui.gridLayoutWidget_6))
        #     self.gui.checkboxlist[count].setObjectName("checkBox" + self.m["tablist"][count])
        #     self.gui.gridLayout_config.addWidget(self.gui.checkboxlist[count], count+2, 0, 1, 1)
        #     self.gui.checkboxlist[count].setText(self.m["tablist"][count])
        #     self.gui.checkboxlist[count].setChecked(True)
        #     #self.gui.checkboxlist[count].clicked.connect(self.manage_tabcheck(count))
        #     tabname = "tab_" + self.m["tablist"][count]
        #     page = self.gui.tabWidget.findChild(QWidget, tabname)
        #     self.tabindexdict[tabname] = self.gui.tabWidget.indexOf(page)
        #self.gui.DOSOMETHING
        
    def updatetimer(self):
        """
        updates timer functions
        shows date and time
        changes between UTC and local time
        manages recording timer
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        if self.gui.checkBox_UTC.isChecked():
            self.UTC = True #TODO:future system state
        else:
            self.UTC = False
        if self.gui.checkBox_TESTMODE.isChecked():
            self.TEST = True #TODO:future system state
        else:
            self.TEST = False

        if self.UTC:
            dt_now = datetime.now(ndatetime.timezone.utc)
            self.gui.label_showdate.setText(
                dt_now.strftime('%Y-%m-%d'))
            self.gui.label_showtime.setText(
                dt_now.strftime('%H:%M:%S'))
        else:
            dt_now = datetime.now()
            self.gui.label_showdate.setText(
                dt_now.strftime('%Y-%m-%d'))
            self.gui.label_showtime.setText(
                dt_now.strftime('%H:%M:%S'))
            
        self.SigRelay.emit("cexex_all_",["timertick",0])
        
    def GUI_reset_status(self):
        #self.m = {}
        self.m["my_filename"] = ""
        self.m["ext"] = ""
        self.m["annotation_prefix"] = 'ANN_' #TODO: not used anywhere
        #self.m["resampling_gain"] = 0
        self.m["emergency_stop"] = False
        self.m["timescaler"] = 0
        self.m["fileopened"] = False
        self.m["rates"] = {20000:0, 50000:1, 100000:2, 250000:3, 
                      500000:4, 1250000:5, 2500000:6}
        self.m["ifreq"] = 0
        self.m["irate"] = 0
        self.m["icorr"] = 0
        self.m["irates"] = ['2500', '1250', '500', '250', '100', '50', '20']
        self.m["gui_reference"] = self
        #self.m["actionlabel"] = ""
        self.m["LO_offset"] = 0
        self.m["playlist_ix"] = 0
        self.m["reslist_ix"] = 0
        self.m["list_out_files_resampled"] = []
        self.m["playthreadActive"] = False
        #self.m["playlist_active"] = False
        #self.m["progress"] = 0
        #self.m["temp_LOerror"] = False
        #self.m["starttrim"] = False
        #self.m["stoptrim"] = False

    def generate_canvas(self,dummy,gridref,gridc,gridt,Tabref): #TODO: remove unelegant dummy issue
        """
        --> VIEW or auxiliary
        eher AUXILIARY !
        initialize central Tab management dictionary Tabref
        :param: gridref
        :type: ui.gridLayout_# object from GUI, e.g. self.gui.gridLayout_4 given by QT-designer
        :param: gridc, position of canvas, list with 4 entries: row_index, col_index, line_span, col_span
        :type: list 
        :param: gridt, position and span of toolbar with 4 entries: row_index, col_index, line_span, col_span
                if gridt[0] < 0 --> no toolbar is being assigned
        :type: list
        :param: Tabref["name"], name = name of tab
        :type: dict["name"]
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        figure = Figure()
        canvas = FigureCanvasQTAgg(figure)
        gridref.addWidget(canvas,gridc[0],gridc[1],gridc[2],gridc[3])
        ax = figure.add_subplot(111)
        if gridt[0] >= 0:
            toolbar = NavigationToolbar(canvas, gui)
            gridref.addWidget(toolbar,gridt[0],gridt[1],gridt[2],gridt[3])
        Tabref["ax"] = ax
        Tabref["canvas"] = canvas
        Tabref["ax"].plot([], [])
        Tabref["canvas"].draw()
        
    def init_Tabref(self): #TODO:future system state
        """
        UNKLAR: Definition einer Referenztabelle für das Ansprechen verschiedener TABs und insb CANVAS-Zuweisung
        könnte auch im Datenmodul residieren
        initialize central Tab management dictionary Tabref
        :param: none
        :type: none
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        #TODO: Umbenennen der tab-Referenzen nach ordentlichem System, so wie bereits 'tab_resample', nicht 'tab_4'
        # Bei Erweiterungen: für jeden neuen Tab einen neuen Tabref Eintrag generieren, generate_canvas nur wenn man dort einen Canvas will
        #TODO:future system state
        self.Tabref["Player"] = {}
        self.Tabref["Player"]["tab_reference"] = self.gui.tab_playrec
        #Tab View spectra
        self.Tabref["View_Spectra"] = {}
        self.Tabref["View_Spectra"]["tab_reference"] = self.gui.tab_view_spectra
        self.generate_canvas(self,self.gui.gridLayout_4,[4,0,1,5],[2,2,2,1],self.Tabref["View_Spectra"])
        #generiert einen Canvas auf den man mit self.Tabref["View_Spectra"]["canvas"] und
        #self.Tabref["View_Spectra"]["ax"] als normale ax und canvas Objekte zugreifen kann
        #wie plot(...), show(), close()
        # Tab Resampler
        self.Tabref["Resample"] = {}
        self.Tabref["Resample"]["tab_reference"] = self.gui.tab_resample
        self.generate_canvas(self,self.gui.gridLayout_5,[6,0,6,4],[-1,-1,-1,-1],self.Tabref["Resample"])

    def setactivity_tabs(self,caller,statuschange,exceptionlist):
        """
        CORE VIEW METHOD
        activates or inactivaes all tabs except the caller
        caller can be any tab name
        statuschange: 'activate': activate all tabs except the caller
                        'inactivate' inactivate all tabs except the caller
        :param caller
        :type str
        :param statuschange
        :type str
        :param exceptionlist
        :type list        
        ...
        :raises [ErrorType]: none
        ...
        :return: success label: True, False
        :rtype: boolean
        """
        for i in range(self.gui.tabWidget.count()):
            if statuschange.find("inactivate") == 0:
                if (self.gui.tabWidget.tabText(i).find(caller) != 0) and (self.gui.tabWidget.tabText(i) not in exceptionlist):
                    self.gui.tabWidget.widget(i).setEnabled(False)
            elif statuschange.find("activate") == 0:
                if (self.gui.tabWidget.tabText(i).find(caller) != 0) and (self.gui.tabWidget.tabText(i) not in exceptionlist):
                    self.gui.tabWidget.widget(i).setEnabled(True)
            else:
                return False
        return True

    def reset_GUI(self):
        """
        CORE VIEW
        TODO: nach den einzelnen Tabs zerlegen
        reset GUI elements to their defaults, re-initialize important variables
        code is executed after new file open
        :param none
        :type: none
        :raises [ErrorType]: [ErrorDescription]TODO
        :return: True after completion, False if status-yaml not accessible
        :rtype: boolean
        """

        self.SigRelay.emit("cexex_waveditor",["activate_WAVEDIT",0])

#     def showfilename(self):
#         """_updates the name of currenly loaded data file in all instances of filename labels_
#         :param : none if old system, args[0] = string with filename to be displayed 
#         :type : none if old system, str else
#         '''
#         :raises [ErrorType]: [ErrorDescription]
#         '''
#         :return: none
#         :rtype: none
#         """ 
#         # self.SigRelay.emit("cexex_all_",["updateGUIelements",0])
#         # #TODO TODO TODO: remove the following after change to all new modules and Relay
#         # self.my_dirname = os.path.dirname(self.m["f1"])
#         # self.my_filename, self.ext = os.path.splitext(os.path.basename(self.m["f1"]))
#         # #self.gui.label_Filename_Annotate.setText(self.my_filename + self.ext)
#         # self.gui.label_Filename_WAVHeader.setText(self.my_filename + self.ext)
#         # self.gui.label_Filename_Player.setText(self.my_filename + self.ext)

# ############################## GENERAL MENU FUNCTIONS  ####################################

    def cb_open_file(self):
        """
        VIEW
        check conditions for proper opening of a new data file; if all conditions met:
        call FileOpen() for getting the file handling parameters
        conditions: playthread is not currently active

        returns: True if successful, False if condition not met.        
        """
        
        self.setactivity_tabs("all","activate",[])
        #self.SigRelay.emit("cm_playrec",["sdr_configparams",self.m["sdr_configparams"]])         #TODO TODO TODO TEST TEST TEST: configparams not initiated here any more; change 02-04-2024
        #TODO TODO TODO TEST TEST TEST: configparams not initiated here any more; change 02-04-2024
        #self.gui.checkBox_merge_selectall.setChecked(False)  #TODO TODO TODO TEST TEST TEST: configparams not initiated here any more; change 02-04-2024

        if self.m["playthreadActive"] == True:
            auxi.standard_errorbox("Player is currently active, no access to data file is possible; Please stop Player before new file access")
            return False
        try:
            stream = open("config_wizard.yaml", "r")
            self.m["metadata"] = yaml.safe_load(stream)
            stream.close()
            self.ismetadata = True
        except:
            self.ismetadata = False
            self.logger.error("cannot get wizard configuration metadata")
            auxi.standard_errorbox("cannot get wizard configuration metadata, quit file open")
            return False

        # TODO TODO TODO: Hostaddress is part of the config menu !
        #self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text()   ### TODO TODO TODO check if still necesary after transfer to modules playrec and config
        self.SigRelay.emit("cm_playrec",["HostAddress",self.m["HostAddress"]])
        # configparams = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
        #                     "rates": self.m["rates"], "icorr":self.m["icorr"],
        #                     "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        #self.m["sdr_configparams"] = configparams #TODO TODO TODO check after change 02-04-2024probably unused
        #self.gui.spinBoxminSNR_ScannerTab.setProperty("value", self.PROMINENCE)    #######TODO: replace or remove
        
        if self.m["fileopened"] is True:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("open new file")
            msg.setInformativeText("you are about o open another file. Current file will be closed; Do you want to proceed")
            msg.setWindowTitle("FILE OPEN")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.buttonClicked.connect(self.popup)
            msg.exec_()

            if self.yesno == "&Yes":
                if self.FileOpen() is False:
                    self.SigRelay.emit("cm_all_",["fileopened", False])
                    return False
        else:
            if self.FileOpen() is False:
                self.SigRelay.emit("cm_all_",["fileopened",False])
                return False
            else:
                self.SigRelay.emit("cm_all_",["fileopened",True])

    def popup(self,i):
        """
        """
        self.yesno = i.text()

    def setstandardpaths(self):  #TODO: shift to controller and general system module ? must be part of the system configuration procedure
        """
        CONTROLLER
        
        """
        #TODO TODO TODO: check if the selfs must be selfs !
        self.m["annotationpath"] = self.my_dirname + '/' + self.annotationdir_prefix + self.m["my_filename"]
        self.stations_filename = self.m["annotationpath"] + '/stations_list.yaml'
        self.status_filename = self.m["annotationpath"] + '/status.yaml'
        self.annotation_filename = self.m["annotationpath"] + '/snrannotation.yaml'
        self.SigRelay.emit("cm_annotate",["annotationpath",self.m["annotationpath"]])
        self.SigRelay.emit("cm_annotate",["stations_filename",self.stations_filename])
        self.SigRelay.emit("cm_annotate",["status_filename",self.status_filename])
        self.SigRelay.emit("cm_annotate",["annotation_filename",self.annotation_filename])
        self.SigRelay.emit("cm_annotate",["annotationdir_prefix",self.annotationdir_prefix])
        self.SigRelay.emit("cm_all_",["standardpath",self.standardpath])
        
        self.cohiradia_metadata_filename = self.m["annotationpath"] + '/cohiradia_metadata.yaml' #TODO: needs the variable be 'self' ?
        self.cohiradia_yamlheader_filename = self.m["annotationpath"] + '/cohiradia_metadata_header.yaml' #TODO: needs the variable be 'self' ?
        self.cohiradia_yamltailer_filename = self.m["annotationpath"] + '/cohiradia_metadata_tailer.yaml' #TODO: needs the variable be 'self' ?
        self.cohiradia_yamlfinal_filename = self.m["annotationpath"] + '/COHI_YAML_FINAL.yaml' #TODO: needs the variable be 'self' ?
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamlheader_filename",self.cohiradia_yamlheader_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamltailer_filename",self.cohiradia_yamltailer_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamlfinal_filename",self.cohiradia_yamlfinal_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_metadata_filename",self.cohiradia_metadata_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamlheader_filename",self.cohiradia_yamlheader_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamltailer_filename",self.cohiradia_yamltailer_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamlfinal_filename",self.cohiradia_yamlfinal_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_metadata_filename",self.cohiradia_metadata_filename])

    def set_startuptab(self):
        #schreib den Index ins File, der als key in tab_dict["tabname"] zu dem value gehört, der in self.tab_names als value vorkommt
        #besser: baue die combobox nach tab_dict auf !
        
        curix = self.gui.playrec_comboBox_startuptab.currentIndex()
        print(f"startuptab set: {curix}")
        #write to yaml
        self.m["metadata"]["startup_tab"] = str(curix)
        # self.m["metadata"]["STM_IP_address"] = self.m["HostAddress"]
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()
        pass

    #@njit
    def FileOpen(self):   #TODO: shift to controller, decompose in small submethods
        '''
        CONTROLLER ?
        Purpose: 
        If self.####### == True:
            (1) Open data file for read
            (2) call routine for extraction of recording parameters from filename
            (3) present recording parameters in info fields
        Returns: True, if successful, False otherwise
        '''
    
        #TODO: could be an update action of the resampler ?
        self.SigRelay.emit("cexex_resample",["enable_resamp_GUI_elements",True])
        self.SigRelay.emit("cm_all_",["ismetadata",self.ismetadata])
        self.SigRelay.emit("cm_all_",["metadata",self.m["metadata"]])
        # file selection menu
        filters = "SDR wav files (*.wav);;Raw IQ (*.dat *.raw )"
        selected_filter = "SDR wav files (*.wav)"
        if self.ismetadata == False:
            filename =  QtWidgets.QFileDialog.getOpenFileName(gui,
                                                            "Open data file"
                                                            , self.standardpath, filters, selected_filter)
        else:
            filename =  QtWidgets.QFileDialog.getOpenFileName(gui,
                                                            "Open data file"
                                                            ,self.m["metadata"]["last_path"] , filters, selected_filter)

        self.SigRelay.emit("cm_all_",["f1", filename[0]])
        if not self.m["f1"]:
            return False
        self.logger.info(f'FileOpen: core_v File opened: {self.m["f1"]}')

        #get file info and distribute to all modules
        self.my_dirname = os.path.dirname(self.m["f1"])
        self.m["ext"] = Path(self.m["f1"]).suffix
        self.m["my_filename"] = Path(self.m["f1"]).stem
        self.m["temp_directory"] = self.my_dirname + "/temp"
        self.SigRelay.emit("cm_all_",["my_dirname", self.my_dirname])
        self.SigRelay.emit("cm_all_",["ext",self.m["ext"]])
        self.SigRelay.emit("cm_all_",["my_filename",self.m["my_filename"]])
        self.SigRelay.emit("cm_all_",["temp_directory",self.my_dirname + "/temp"])
        self.setstandardpaths()

        #reset all modules
        self.SigRelay.emit("cexex_all_",["reset_GUI",0])

        if os.path.exists(self.m["temp_directory"]) == False:         #TODO: ? maybe settable in configuration ? create from yaml-editor
            os.mkdir( self.m["temp_directory"])

        #TODO FUTURE The following code prevents that a dat file can be directly resampled
        #This is not a dogma: The file could, in principle. be resampled as a wav header is generated anyway
        #Future releases could allow for direct resampling but then the 'fillplaylist' method of the resampler module needs to allow for the dat fuile to be included in the 
        #resampling playlist (reslist). This requires a re-design of this method
        #Priority is currently low, so dat files cannot be resampled directly at the moment
        #then dat File must be entered into the resampling list !

        if self.m["ext"] == ".dat" or self.m["ext"] == ".raw":
            filetype = "dat"
            self.SigRelay.emit("cexex_waveditor",["activate_insertheader",True])
            #TODO: TRIAL 15_04_2024: remove
            self.setactivity_tabs("Resample","inactivate",[])

        else:
            if self.m["ext"] == ".wav":
                filetype = "wav"
                self.SigRelay.emit("cexex_waveditor",["activate_insertheader",False])
                self.setactivity_tabs("Resample","activate",[])
            else:
                auxi.standard_errorbox("no valid data forma, neiter wav, nor dat nor raw !")
                return

        #Generate wavheader and distribute to all modules
        if filetype == "dat": # namecheck only if dat --> makes void all wav-related operation sin filenameextract
            if self.dat_extractinfo4wavheader() == False:
                auxi.standard_errorbox("Unexpected error, dat_extractinfo4wavheader() == False; ")
                return False
                #TODO: dat_extractinfo4wavheader() automatically asks for lacking wav header info, so this exit could be replaced alrady !
            auxi.standard_infobox("dat file cannot be resampled. If you wish to resample, please convert to wav file first (Tab WAV Header)")
        else:
            self.wavheader = WAVheader_tools.get_sdruno_header(self,self.m["f1"])
            if self.wavheader != False:
                pass
            else:
                auxi.standard_errorbox("File is not recognized as a valid IQ wav file (not auxi/rcvr compatible or not a RIFF file)")
                return False
        if self.wavheader['sdrtype_chckID'].find('auxi') > -1 or self.wavheader['sdrtype_chckID'].find('rcvr') > -1: #TODO: CHECK: is this obsolete because of the above quest ?
            pass
        else:
            auxi.standard_errorbox("cannot process wav header, does not contain auxi or rcvr ID")
            self.sdrtype = 'FALSE'
            return False
        self.SigRelay.emit("cm_waveditor",["filetype",filetype])
        self.SigRelay.emit("cm_all_",["wavheader",self.wavheader])

        # build up playlist selectors
        self.SigRelay.emit("cexex_playrec",["addplaylistitem",0])
        self.SigRelay.emit("cexex_playrec",["fillplaylist",0])      
        self.SigRelay.emit("cexex_resample",["addplaylistitem",0])
        self.SigRelay.emit("cexex_resample",["fillplaylist",0])
        self.logger.debug("core_v: wavheader extracted and sent to all modules")

        ### set readoffset and relay to modules: TODO TODO TODO: check if should be translated to modules (dangerous, may affect many instances)
        if self.wavheader['sdrtype_chckID'].find('rcvr') > -1:
            self.m["readoffset"] = 86
        else:
            self.m["readoffset"] = 216
            #TODO TODO: remove self.readoffset from init list after tests
        self.SigRelay.emit("cm_all_",["readoffset",self.m["readoffset"]])

        #TODO TODO TODO check for transfer to modules
        self.m["irate"] = self.wavheader['nSamplesPerSec'] #ONLY used in palyer, so shift

        # TODO FUTURE: check for append metadata instead of new write

        #save metadata
        self.m["metadata"]["last_path"] = self.my_dirname
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()

        self.m["timescaler"] = self.wavheader['nSamplesPerSec']*self.wavheader['nBlockAlign']
        self.m["fileopened"] = True #check if obsolete because f1 == "" would do the same
        self.SigRelay.emit("cm_all_",["fileopened",True])


        out_dirname = self.my_dirname + '/out'  #TODO TODO TODO should only be created if really necessary for resampling !
        if os.path.exists(out_dirname) == False:         #exist yaml file: create from yaml-editor
            os.mkdir(out_dirname)
        self.SigRelay.emit("cm_all_",["out_dirname",out_dirname])

        ##############TODO TODO TODO: intermediate hack for comm with scan worker
        self.SigRelay.emit("cexex_all_",["updateGUIelements",0])

        #TODO TODO TODO: track multiple calls of plot_spectrum: is that really necessary on each fileopen ? 
        return True

    def dat_extractinfo4wavheader(self): #TODO: muss in den controller !
        #TODO: erkennt COHIRADIA Namenskonvention nicht, wenn vor den _lo_r_c literalen noch andere _# Felder existieren.  shift to controller module
        """ 
        CONTROLLER !!!!!!!!!!!!!!!!
        extract control parameters from dat and raw files if existent (COHIRADIA nameconvention)
        and generates standard wavheader
        check for consistency with COHIRADIA file name convention
        if no wav information present: generate dummy entries for most wavheaderitems and ask for SR and LO

        :param [ParamName]: none
        :type [ParamName]: none
        :raises Filename error 1: center frequency offset not integer
        :raises Filename error 2: filename convention not met, cannot extractplayback/resording parameters
        :raises Filename error 3: center frequency not in range (0 - 62500000)
        :raises Filename error 4: sampling rate not in set 20000, 50000, 100000, 250000, 500000, 1250000, 2500000
        :raises Filename error 5: center frequency offset out of range +/- 100 ppm
        :raises warning 1: LO frequency not identifiable in wav-filename, default value 1250 kS/s is used
        :return: Returns: True, if successful, False otherwise (if error exception raised)
        :rtype: Boolean
        """
        loix = self.m["my_filename"].find('_lo')
        cix = self.m["my_filename"].find('_c')
        rateix = self.m["my_filename"].find('_r')
        icheck = True
        i_LO_bias = 0 ###TODO: remove, activate ???

        # #TODO: ACTIVATE LObias check code
        # if self.gui.radioButton_LO_bias.isChecked() is True:
        #     if (self.gui.lineEdit_LO_bias.text()).isnumeric() == False:
        #         auxi.standard_errorbox("invalid numeral in center frequency offset field, please enter valid integer value (kHz)")
        #         return False

        #     LObiasraw = self.gui.lineEdit_LO_bias.text()
        #     LObias_sign = 1

        #     if LObiasraw[0] == "-":
        #         LObias_sign = -1
        #     if LObiasraw.lstrip("-").isnumeric() is True:
        #         i_LO_bias = LObias_sign*int(LObiasraw.lstrip("-"))
        #     else:
        #         auxi.standard_errorbox("invalid numeral in center frequency offset field, please enter valid integer value (kHz)")
        #         return False

        if rateix == -1 or cix == -1 or loix == -1:
            icheck = False
        
        freq = self.m["my_filename"][loix+3:loix+7]
        freq = freq + '000'
        if freq.isdecimal() == False:
            icheck = False

        rate = self.m["my_filename"][rateix+2:cix]
        rate = rate + '000'
        if rate.isdecimal() == False:
            icheck = False            
        self.m["icorr"] = int(0)
        bps = 16
        
        #generate standard wavheader
        if icheck == False:

            freq, done0 = QtWidgets.QInputDialog.getInt(
                    gui, 'Input Dialog', 'Enter center frequency:', self.standardLO)
            rate_index = 1 #TODO: make system constant
            rate, done1 = QtWidgets.QInputDialog.getItem(
                    gui, 'Input Dialog', 'Bandwidth', self.m["irates"], rate_index)
            bps, done2 = QtWidgets.QInputDialog.getItem(
                    gui, 'Input Dialog', 'bits per sample', self.bps, 0)

            #TODO: validity check for freq, maybe warning if rate cancelled and no valid value, check done0, done1
            self.m["irate"] = 1000*int(rate)
            self.m["ifreq"] = int(1000*(int(freq) + self.m["LO_offset"]))
        else:
            self.m["irate"] = int(rate)
            self.m["ifreq"] = int(int(freq) + self.m["LO_offset"])  # TODO: LO_bias dazuzählrn self.m["LO_offset"]
        #TODO: ACTIVATE wav header generator
        ti_m = os.path.getmtime(self.m["f1"])
        file_mod = datetime.fromtimestamp(ti_m)
        file_stats = os.stat(self.m["f1"])
        self.wavheader = WAVheader_tools.basic_wavheader(self,self.m["icorr"],int(self.m["irate"]),int(self.m["ifreq"]),int(bps),file_stats.st_size,file_mod)

        return True

    def generate_GUIupdaterlist(self,item):
        self.GUIupdaterlist.append(item)

    def sendupdateGUIs(self):
        """  goes through the list of all registered Tabs and calls their GUI-Updatemethod
        :param : none
        :type : none
        :raises [ErrorType]: none
        :return: none
        :rtype: none
        """        
        for item in self.GUIupdaterlist:
            item()

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
        if _key.find("cm_core") == 0 or _key.find("cm_all_") == 0 or _key.find("cm_xcore") == 0:  #TODO: langfr remove core or xcore
            #set mdl-value
            self.m[_value[0]] = _value[1] 
        if _key.find("cui_core") == 0:
            _value[0](_value[1])    #can be dangerous !
        if _key.find("cexex_core") == 0 or _key.find("cexex_xcore") == 0  or _key.find("cexex_all_") == 0:
            # if  _value[0].find("GUIreset") == 0:
            #     self.SigGUIReset.emit()
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
            if  _value[0].find("updatetimer") == 0:
                self.updatetimer()
            if  _value[0].find("stoptick") == 0:
                self.timertick.stoptick()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("updateConfigElements") == 0:
                self.updateConfigElements()
                

if __name__ == '__main__':
    print("starting main, initializing GUI, please wait ... ")
    
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication([])
    gui = starter()
    gui.show()

    xcore_m = core_m()
    xcore_c = core_c(xcore_m)
    xcore_v = core_v(gui,xcore_c,xcore_m) # self.gui wird in xcore_v gestartet 

#    app.aboutToQuit.connect(win.stop_worker)    #graceful thread termination on app exit
    stemlabcontrol = StemlabControl()#TODO TODO TODO remove after transfer to playrec ??????????????????????
    tab_dict = {}
    tab_dict["list"] = ["xcore"]
    tab_dict["tabname"] = ["xcore"]

    if 'resampler_module_v5' in sys.modules:
        resample_m = rsmp.resample_m() #TODO: wird gui in _m jemals gebraucht ? ich denke nein !
        resample_c = rsmp.resample_c(resample_m) #TODO: replace sys_state
        resample_v = rsmp.resample_v(xcore_v.gui,resample_c, resample_m) #TODO: replace sys_state
        tab_dict["list"].append("resample")
        tab_dict["tabname"].append("Resample")
        resample_v.SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
        resample_c.SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)

    else:
        xcore_v.gui.tabWidget.setTabVisible('tab_resample',False)

    if 'view_spectra' in sys.modules:
        view_spectra_m = vsp.view_spectra_m()
        view_spectra_c = vsp.view_spectra_c(view_spectra_m)
        view_spectra_v = vsp.view_spectra_v(xcore_v.gui,view_spectra_c,view_spectra_m)
        tab_dict["list"].append("view_spectra")
        tab_dict["tabname"].append("View spectra")

    if 'annotate' in sys.modules:
        win_annOLD = False  #TODO KIPP: remove
        annotate_m = ann.annotate_m()
        annotate_c = ann.annotate_c(annotate_m)
        annotate_v = ann.annotate_v(xcore_v.gui,annotate_c,annotate_m)
        tab_dict["list"].append("annotate")
        tab_dict["tabname"].append("Annotate")
    else:  #TODO KIPP: remove
        win_annOLD = True  #TODO KIPP: remove

    if 'yaml_editor' in sys.modules:
        yamleditor_m = yed.yamleditor_m()
        yamleditor_c = yed.yamleditor_c(yamleditor_m)
        yamleditor_v = yed.yamleditor_v(xcore_v.gui,yamleditor_c,yamleditor_m)
        tab_dict["list"].append("yamleditor")
        tab_dict["tabname"].append("YAML editor")
    else:
        page = xcore_v.gui.tabWidget.findChild(QWidget, "tab_yamleditor")
        c_index = xcore_v.gui.tabWidget.indexOf(page)
        xcore_v.gui.tabWidget.setTabVisible(c_index,False)

    if 'waveditor' in sys.modules:
        waveditor_m = waved.waveditor_m()
        waveditor_c = waved.waveditor_c(waveditor_m)
        waveditor_v = waved.waveditor_v(xcore_v.gui,waveditor_c,waveditor_m)
        tab_dict["list"].append("waveditor")
        tab_dict["tabname"].append("WAV Header")
    else:
        page = xcore_v.gui.tabWidget.findChild(QWidget, "tab_waveditor")
        c_index = xcore_v.gui.tabWidget.indexOf(page)
        xcore_v.gui.tabWidget.setTabVisible(c_index,False)

    if 'configuration' in sys.modules:
        configuration_m = conf.configuration_m()
        configuration_c = conf.configuration_c(configuration_m)
        configuration_v = conf.configuration_v(xcore_v.gui,configuration_c,configuration_m)
        tab_dict["list"].append("configuration")
        tab_dict["tabname"].append("Configuration")
    else:
        page = xcore_v.gui.tabWidget.findChild(QWidget, "tab_configuration")
        c_index = xcore_v.gui.tabWidget.indexOf(page)
        xcore_v.gui.tabWidget.setTabVisible(c_index,False)
        pass

    if 'playrec' in sys.modules: #and win.OLD is False:
        playrec_m = playrec.playrec_m()
        playrec_c = playrec.playrec_c(playrec_m)
        playrec_v = playrec.playrec_v(xcore_v.gui,playrec_c,playrec_m)
        tab_dict["list"].append("playrec")
        playrec_v.SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
        playrec_c.SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
        tab_dict["tabname"].append("Player")
    # else:   #TODO: activate after all playrec tests
    #     page = win.gui.tabWidget.findChild(QWidget, "tab_playrec")
    #     c_index = win.gui.tabWidget.indexOf(page)
    #     win.gui.tabWidget.setTabVisible(c_index,False)

    #TODO TODO TODO: das muss für alle Tabs gemacht werden
    #view_spectra_v.SigSyncGUIUpdatelist.connect(win.generate_GUIupdaterlist)
    resample_v.SigUpdateOtherGUIs.connect(xcore_v.sendupdateGUIs)    #TODO TODO TODO schwer zu finden, sollte so nicht connected werden
    resample_c.SigUpdateGUIelements.connect(resample_v.updateGUIelements)
    xcore_v.SigUpdateOtherGUIs.connect(view_spectra_v.updateGUIelements)

    tabselector = [""] * len(tab_dict["tabname"])
    for _ct,_name in enumerate(tab_dict["tabname"]):
        try:
            _key = [k for k,v in xcore_v.tab_names.items() if v == _name][0]
            tabselector[_key] = _name 
        except:
            pass
    tabselector = list(filter(None, tabselector))

    xcore_v.gui.playrec_comboBox_startuptab.addItems(tabselector)
    xcore_v.gui.playrec_comboBox_startuptab.setEnabled(True)
    try:
        xcore_v.gui.playrec_comboBox_startuptab.setCurrentIndex(int(xcore_v.m["metadata"]["startup_tab"]))
    except:
        xcore_v.logger.error("startup Tab not defined in configuration file config_wizard.yaml")
    xcore_v.gui.playrec_comboBox_startuptab.currentIndexChanged.connect(xcore_v.set_startuptab)


    for tabitem1 in tab_dict["list"]:
        for tabitem2 in tab_dict["list"]:
            eval(tabitem1 + "_v.SigRelay.connect(" + tabitem2 + "_v.rxhandler)")
            #eval(tabitem1 + "_c.SigRelay.connect(" + tabitem2 + "_v.rxhandler)")
            xcore_v.logger.debug(f' {tabitem1 + "_v.SigRelay.connect(" + tabitem2 + "_v.rxhandler)"}')
    
    #######################TODO: CHECK IF STILL NECESSARY #######################
    for tabitem in tab_dict["list"]:     
        tab_dict[tabitem + "_m"] = eval(tabitem + "_m") #resample_m     
        tab_dict[tabitem + "_c"] = eval(tabitem + "_c") #resample_c     
        tab_dict[tabitem + "_v"] = eval(tabitem + "_v") #resample_v  
        #xcore_v.generate_GUIupdaterlist(eval(tabitem + "_v.updateGUIelements")) #necessary ????????????
    #make tab dict visible to core module
    xcore_v.tab_dict = tab_dict 
    xcore_v.m["tab_dict"] = tab_dict  ###TODO: check if double tabdict in xcore_v is necessary

    ###################CHECK IF STILL NECESSARY END ###########################

    #all tab initializations occur in connect_init() in core module
    xcore_v.connect_init() 
    #xcore_v.setstandardpaths()
    xcore_v.SigRelay.emit("cm_exex",["updateGUIelements",0])
    sys.exit(app.exec_())

#TODOs:
    # file open muss in den Controller
    #
    # shift access to xcore_v in __main__ ti special initializer method in xcore_v, which is started by a single call in __main__
    #
    # Access of GUI elements should be transferred to the respective modules
    #
    # fix error with SNR calculation: there seems to be no reaction to baselineshifts when calculating the SNR for praks and identifying those above threshold
    #
    # * // \\ Problem lösen: 2h: wahrscheinlich nur mehr in waveditor !!!! geht mit Path() und bei nextfile-Policy im Player
    #
    # * Windows Installer mit https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/ erstellen
    #
    #   zerlege plot_spectrum in einen view_spectra spezifischen Teil und einen generellen Spektralplotter, der in einen Canvas das Spektrum eines Datenstrings plottet
    #       spectrum(canvas_ref,data,*args) in auxiliary Modul
