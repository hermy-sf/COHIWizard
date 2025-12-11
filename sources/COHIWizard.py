#Version 2.1.4
# -*- coding: utf-8 -*-logfile
# For reducing to RFCorder: disable all modules except resample in the config_modules.yaml file
#
#Important: When re-translating the Core-UI from QTdesigner to py-File, run the method 'core/autocorrect_ui_file.py'.
#otherwise there will be a line 'from file import File' which cannot be found by Python. As a consequence
#the line self.menubar = QtWidgets.QMenuBar(File) must be replaced by self.menubar = QtWidgets.QMenuBar(MainWindow)
#In addition the icons for the buttons cannot be found unless their paths are set correctly in the widget file.


"""
#@author: Hermann Scharfetter


Core code with the purpose to 
- instantiate all GUI widgets and modules
- build basic connections between system signals and modules
- setup the relaying mechanism for the exchange of variables between modules
"""
import sys
import os
import datetime as ndatetime
from datetime import datetime
from pathlib import Path
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QHBoxLayout, QLabel, QSizePolicy, QDesktopWidget
# from PyQt5.QtGui import QFont, QFontMetrics

from PyQt5.QtCore import QTimer, QObject, QThread, pyqtSignal, QSize, Qt
from PyQt5.QtGui import QFont, QIcon, QFont, QFontMetrics
import time
import yaml
import importlib
from PyQt5.QtWidgets import *
import logging
import platform
from icons import Logos
from zeroconf import Zeroconf, ServiceBrowser

class starter(QMainWindow):
    """instantiates the MainWindow, instantiates a auxiliary gui object for the
    core GUI and calls its setupUI method; The latter contains all derived structures such as centralwidget, Scrollarea, TabWidget etc.
    :type : QMainwindow

    :param: none
    """
    SigResize = pyqtSignal(str,object)

    def __init__(self,skinindex):
        """instantiates SplashScreen object and then instantiates the central GUI as self.gui. 
        Then setupUi of the central GUI is called which sets up the Mainwindow and the central 
        widget of the player Tab.
        :param: none
        :type: none
        :raises: none
        :return: none
        :type: none
        """
        super().__init__()
        self.splash = SplashScreen()
        self.splash.setFocus()
        self.splash.show()
        self.INACTIVATE_RESIZE = False
        #from core import COHIWizard_GUI_v10_reduced #alternative main GUI without scrollbars
        #self.gui = COHIWizard_GUI_v10_reduced.Ui_MainWindow()
        #from core import COHIWizard_GUI_v10_scroll #alternative main GUI with only vertical scrollbar
        #self.gui = COHIWizard_GUI_v10_scroll.Ui_MainWindow()
        #from core import COHIWizard_GUI_v10_scrollhv
        #self.gui = COHIWizard_GUI_v10_scrollhv.Ui_MainWindow()
        #TODO: import correct skin, use dynamic import
        if skinindex == 0:
            from core import COHIWizard_GUI_v10_scrollhv_skin_0
            self.gui = COHIWizard_GUI_v10_scrollhv_skin_0.Ui_MainWindow()
        else:
            from core import COHIWizard_GUI_v10_scrollhv_skin_1
            self.gui = COHIWizard_GUI_v10_scrollhv_skin_1.Ui_MainWindow()
            
        self.gui.setupUi(self)
        self.iconButtons = []
        self.widgets_with_font = []
        self.find_widgets_with_font()
        screen = QDesktopWidget().availableGeometry()
        aspectratio_opt =1024/857
        screen_aspr =  int(screen.width())/int(screen.height())
        if screen_aspr >= 1:
            hnew = int(screen.height() * 0.9)
            wnew = int(hnew * aspectratio_opt)
        else:
            wnew = int(screen.width() * 0.9)
            hnew = int(wnew / aspectratio_opt)

        self.resize(wnew, hnew)

    def resizeEvent(self, event):
        """resize event handler for the main window, handles resizing widgets based on size of MainWindow
        Sends a Signal SigResize (label,size) while size is the size of the MainWindow
        label is a MainWindow ID as information for the receiver of the signal
        Signal is intended to be received by all 'view_' methods of alls tab modules and 'size' to be handled by their 
        resizehandler method. 
        :param: event
        :type: object  
        :raises: none
        :return: none
        :rtype: none
        """
        width = self.width()
        size = self.size()
        # font_size = max(10, width // 25)  # Mindestgröße von 10 pt
        # font = QFont("Arial", font_size)
        #elf.button.setFont(font)
        # Standardverhalten beibehalten
        super().resizeEvent(event)
        self.SigResize.emit("cenralwidget",size)
        #print(f"resize event caught, Signal sent, size: {size}")
        QTimer.singleShot(0, self.resize_actor)
        #self.resize_actor()

    def resize_initialize(self):
        """initialize resize actor, finds all icon buttons and widgets with font and sets their size
        :param: none
        :type: none
        :raises: none
        :return: none
        :rtype: none
        """
        #print("initial window resizing")
        # QTimer.singleShot(100,self.find_widgets_with_font)
        # QTimer.singleShot(100,self.find_icon_buttons)
        # QTimer.singleShot(100,self.resize_actor)
        self.find_widgets_with_font()
        self.find_icon_buttons()
        self.resize_actor()

    def trigger_resize_event(self):
        #print("################>>>>>>>>>>>>>>>trigger resize<<<<<<<<<<<<<<<####################")
        old_size = self.size()
        self.resize(old_size.width() + 1, old_size.height())
        self.resize(old_size)

    def resize_actor(self):
        if self.INACTIVATE_RESIZE:
            return
        for button in self.iconButtons:
            w = button.width()
            h = button.height()
            icon_size = QSize(int(w * 0.8), int(h * 0.8))
            button.setIconSize(icon_size)
            #print("resize icon in button called")

        
        for widget in self.widgets_with_font:
            # Schriftgröße als Anteil der Widget-Höhe
            # h = widget.height()
            # font_size = max(10, int(h * 0.55))  # Mindestgröße 10px

            # font = widget.font()
            # font.setPixelSize(font_size)
            # widget.setFont(font)
            min_size=11
            max_size=20
            self.fit_font_to_widget(widget, min_size, max_size)

    def fit_font_to_widget(self, widget, min_size=8, max_size=100):
        if self.INACTIVATE_RESIZE:
            return
        text = getattr(widget, "text", lambda: "")()
        if not text:
            return

        best_size = min_size
        low, high = min_size, max_size

        while low <= high:
            mid = (low + high) // 2
            font = widget.font()
            font.setPixelSize(mid)
            fm = QFontMetrics(font)
            rect = fm.boundingRect(widget.rect(), Qt.TextWordWrap, text)

            if rect.width() <= widget.width() and rect.height() <= widget.height():
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1

        # Final anwenden
        font = widget.font()
        if widget.objectName().find("playrec_lineEdit_recordingpath") >= 0:
            h = widget.height()
            font_size = max(min_size, int(h * 0.5))
            font.setPixelSize(font_size)
        else:
            font.setPixelSize(best_size)
        widget.setFont(font)

    def find_icon_buttons(self):
        if self.INACTIVATE_RESIZE:
            return
        """Suche rekursiv nach allen QPushButtons mit Icon"""
        self.iconButtons.clear()
        for button in self.findChildren(QPushButton):
            if not button.icon().isNull():
                self.iconButtons.append(button)


    def find_widgets_with_font(self):
        if self.INACTIVATE_RESIZE:
            return
        """Finde alle Widgets, die einen Font haben und Text anzeigen"""
        # Optional: nur bestimmte Klassen einbeziehen
        font_classes = (QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox, QRadioButton,QTimeEdit, QTableWidgetItem, QProgressBar)

        self.widgets_with_font = [
            w for w in self.findChildren(QWidget)
            if isinstance(w, font_classes) and hasattr(w, "font")
        ]



class core_m(QObject):
    """core model class, holds all common module variables as a dictionary self.mdl
    initializes a logger and a few variables

    :param: none
    :type: QObject
    """
    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["sample"] = 0
        self.mdl["_log"] = False
        self.mdl["rootpath"] = os.getcwd()
        # Create a custom logger
        logging.getLogger().setLevel(logging.DEBUG)
        # Erstelle einen Logger mit dem Modul- oder Skriptnamen
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
        self.logger.debug('Init logger in configuration method reached')


class core_c(QObject):
    """core control class, implements controller methods for core module

    :param: none
    :type: QObject
    """
    #__slots__ = ["contvars"]

    SigRelay = pyqtSignal(str,object)
    """signal for relaying data and messages to other module's rxhandler method; emitted as SigRelay(_key,_value)

    :param: _key
    :type: str
    :param: _value
    :type: object 
    """

    def __init__(self, core_m):
        """establishes a reference to core_m.mdl as self.m and to core_m.logger as self.logger

        :param core_m: reference to instance of model object core_m
        :type core_m: QObject
        :return: none
        :type: none
        """
        super().__init__()

        self.m = core_m.mdl
        self.logger = core_m.logger


    def recording_path_checker(self):
        """_checks, if recording path exists in config_wizard.yaml and if the path exists in the system
        if not: ask for target pathname and store in config.wizard.yaml

        :param: none
        :type: none
        :raises: none
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
            options = QtWidgets.QFileDialog.Options()
            options |= QtWidgets.QFileDialog.ShowDirsOnly
            self.m["recording_path"] = ""
            while len(self.m["recording_path"]) < 1:
                try:
                    self.m["recording_path"] = QtWidgets.QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Select Recording Directory", options=options)
                except:
                    return
                if len(self.m["recording_path"]) < 1:
                    auxi.standard_errorbox("Recording path must be defined, please define it by clicking OK !")
            self.logger.debug("playrec recording path: %s", self.m["recording_path"])
            self.m["metadata"]["recording_path"] = self.m["recording_path"]
            self.m["metadata"]["rootpath"] = self.m["rootpath"]
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
        else:
            self.m["recording_path"] = self.m["metadata"]["recording_path"]
        self.logger.debug("playrec recording button recording path: %s", self.m["recording_path"])
        self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])
        self.SigRelay.emit("cexex_xcore",["updateConfigElements",0])

    def recording_path_setter(self):
        """checks, if recording path exists in config_wizard.yaml and if the path exists 
        if not: ask for target pathname and store in config.wizard.yaml

        :param: none
        :type: none
        :raises: none
        :return: none
        :rtype: none
        """         
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.ShowDirsOnly
        self.m["recording_path"] = QtWidgets.QFileDialog.getExistingDirectory(self.m["QTMAINWINDOWparent"], "Select Recording Directory", options=options)
        self.logger.debug("playrec recording path: %s", self.m["recording_path"])
        self.m["metadata"]["recording_path"] = self.m["recording_path"] #TODO: check ? obsolete ?
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()
        self.m["recording_path"] = self.m["metadata"]["recording_path"] #TODO: check ? obsolete ?
        self.logger.debug("playrec recording button recording path: %s", self.m["recording_path"])
        #print("core_c send recordingpath to all")
        self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])   #does not work !!!!   because all other modules are not yet instantiated !
        self.SigRelay.emit("cexex_xcore",["updateConfigElements",0])

class core_v(QObject):
    """core view class, implements communication with the GUI elements and with controller module
    holds all common module variables as a dictionary self.m

    :param: none
    :type: QObject
    """
    SigUpdateOtherGUIs = pyqtSignal()     #TODO: check if this signal is ever used ! is connected but never emitted
    SigRelay = pyqtSignal(str,object)
    #signal for relaying data and messages to other module's rxhandler method; emitted as SigRelay(_key,_value)
    #:param: _key
    #:type: str
    #:param: _value
    #:type: object 

    def __init__(self, gui, core_c, core_m):
        super().__init__()
        print("Initializing GUI, please wait....")
        self.m = core_m.mdl
        self.core_c = core_c
        self.bps = ['16', '24', '32'] #TODO:future system state
        self.standardLO = 1125 #TODO:future system state
        self.annotationdir_prefix = 'ANN_' #TODO:future system state
        default_recordingpath = os.path.join(self.m["rootpath"], "out")
        if not os.path.exists(default_recordingpath):
            os.makedirs(default_recordingpath)
        self.m["recording_path"] = default_recordingpath
        print(f"initialize recording path to {default_recordingpath}")

        # create method which inactivates all tabs except the one which is passed as keyword
        self.GUI_reset_status()
        self.gui = gui.gui
        self.gui.Mainwindowreference = gui
        self.gui.actionFile_open.triggered.connect(self.cb_open_file)
        self.gui.actionOverwrite_header.triggered.connect(self.send_overwrite_header)

        #
        self.gui.Mainwindowreference.SigResize.connect(self.resizehandler)
        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.gui.tabWidget.setCurrentIndex(0) #is being overridden later from config file core_v.__init__
        self.gui.playrec_comboBox_startuptab.setCurrentIndex(0)
        self.standardpath = os.getcwd()  #TODO: this is a core variable in core model
        self.m["metadata"] = {"last_path": self.standardpath}
        self.ismetadata = False
        self.gui.lineEdit_IPAddress.setInputMask('000.000.000.000')
        self.gui.lineEdit_IPAddress.setText("000.000.000.000")
        self.gui.lineEdit_IPAddress.setEnabled(False)
        self.gui.lineEdit_IPAddress.setReadOnly(True)
        self.gui.pushButton_IP.clicked.connect(self.editHostAddress)
        self.gui.lineEdit_IPAddress.returnPressed.connect(self.set_IP)
        self.gui.pushButton_IP.setText("set IP Address")
        self.gui.pushButton_IP.adjustSize()
        no_ffmpeg_path = False
        
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
                self.m["startup_tab"] = int(self.m["metadata"]["startup_tab"])
            if "rootpath" in self.m["metadata"]:
                self.m["rootpath"] = self.m["metadata"]["rootpath"]
            else:
                self.m["rootpath"] = os.getcwd()
                self.m["metadata"]["recording_path"] = self.m["rootpath"]
            if not "ffmpeg_path" in list(self.m["metadata"].keys()):
                no_ffmpeg_path = True
        except:
            print("cannot get config_wizard.yaml metadata, write a new initial config file")
            self.m["metadata"] = {"last_path": self.standardpath}
            self.m["metadata"]["rootpath"] = os.getcwd()
            self.m["metadata"]["STM_IP_address"] = "000.000.000.000"
            #auxi.standard_infobox("configuration file does not yet exist, a basic file will be generated. Please configure the STEMLAB IP address before using the Player")
            self.m["metadata"]["recording_path"] = os.path.join(self.m["metadata"]["rootpath"], "out")
            self.m["metadata"]["skinindex"] = 1
            self.m["metadata"]["HIRES_ffmpeg"] = True 
            self.m["metadata"]["REC_AGC"] = False 
            self.m["metadata"]["AGC_targetvolume"] = 0.4
            no_ffmpeg_path = True
            if not os.path.exists(default_recordingpath):
                os.makedirs(default_recordingpath)
            default_recordingpath = os.path.join(self.m["rootpath"],"out")

        if no_ffmpeg_path:
            system = platform.system().lower()
            if system == "linux":
                self.m["metadata"]["ffmpeg_path"] = ""
            elif system == "windows":    
                self.m["metadata"]["ffmpeg_path"] = os.path.join(self.m["rootpath"],"ffmpeg-master-latest-win64-gpl-shared/bin")
            else:
                self.m["metadata"]["ffmpeg_path"] = ""
                auxi.standard_infobox("Your OS is neither linux nor windows. Therefore COHIWizard or at least some of its features may not work properly. The ffmpeg path has not been set. Please make sure that ffmpeg is installed and set the path to the ffmpeg binary it in the configuration file config_wizard.yaml. Otherwise e.g. resampler and synthesizer will not work at all.")
            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
            no_ffmpeg_path = False

        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.m["HostAddress"] = self.gui.lineEdit_IPAddress.text() #TODO: Remove after transfer of playrec
        self.m["sdr_configparams"] = {"ifreq":self.m["ifreq"], "irate":self.m["irate"],
                            "rates": self.m["rates"], "icorr":self.m["icorr"],
                            "HostAddress":self.m["HostAddress"], "LO_offset":self.m["LO_offset"]}
        self.m["f1"] = ""
        self.m["_log"] = False

        # Create a custom logger
        # set level of Root-Logger to DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
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
        self.logger.info("core_v Init logger in core reached")
        self.core_c.SigRelay.connect(self.rxhandler)
        ###TODO: re-organize, there should be no access to gui elements of other modules
        self.gui.playrec_pushButton_recordingpath.clicked.connect(self.core_c.recording_path_setter)
        self.updateConfigElements()
        self.firsttick = True
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

    #TODO: make IP address editor easier to handle, test method
    # def eventFilter(self, source, event):
    #     if (event.type() == Qt.KeyPress and
    #         event.key() == Qt.Key_Tab and
    #         source is self.gui.lineEdit_IPAddress):
    #         cursor = self.gui.lineEdit_IPAddress.cursorPosition()
    #         if cursor == 3 or cursor == 7 or cursor == 11:  # Check if cursor is at the end of each field
    #             self.gui.lineEdit_IPAddress.setCursorPosition(cursor + 1)  # Move cursor to the next field
    #             return True  # Ignore default Tab key behavior
    #     return super().eventFilter(source, event)

    def resizehandler(self, label, size):
        """resize handler for the main window, handles resizing widgets based on size of MainWindow
        :param: label
        :type: str
        :param: size
        :type: object
        :raises: none
        :return: none
        :rtype: none
        """
        #print(f"###### RECEIVED BY playrec: resizehandler called, label {label}, size {size}")


    def send_overwrite_header(self):
        self.SigRelay.emit("cexex_waveditor",["overwrite_header",0])
        pass

    def editHostAddress(self):     #TODO Check if this is necessary, rename to cb_.... ! 
        ''' 
        Purpose: slot function for the edidHostAddress Lineedit item
        activate Host IP address field and enable saving mode
        Returns: nothing
        '''
        ## ## Bevore toggling IP editing, scan for existing STEMLAB, run arp query
        ## redpitaya_ouis = ["00:26:32", "3c:2c:30", "b8:27:eb"]

        ## # initialize UDP-Broadcast-Packet, in order to cause ARP-Requests
        ## auxi().trigger_linklocal_arp()
        ## # identify connected STEMLABs
        ## devices = auxi().discover_linklocal_devices(filter_oui=redpitaya_ouis)

        ## if devices:
        ##     print("Gefundene Red Pitayas:")
        ##     for ip, mac in devices:
        ##         print(f"{ip}  →  {mac}")
        ## else:
        ##     print("Keine Red Pitayas gefunden.")

        # Find connected red pitaya and return its IP/MAC
        # zeroconf = Zeroconf()
        # listener = RPListener()
        # browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
        # time.sleep(2)  # kurze Wartezeit für Antworten
        # zeroconf.close()
        #print("Gefundene Red Pitayas:", listener.devices)
        
        self.gui.lineEdit_IPAddress.setEnabled(True)
        self.gui.lineEdit_IPAddress.setReadOnly(False)
        self.gui.pushButton_IP.clicked.connect(self.set_IP) ####TODO: send identified IP to self.set_IP for auto-preset
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
        #self.SigRelay.emit("cm_all_",["Tabref",self.Tabref])
        self.SigRelay.emit("cm_resample",["rates",self.m["rates"]])
        self.SigRelay.emit("cm_resample",["irate",self.m["irate"]])
        self.SigRelay.emit("cm_playrec",["rates",self.m["rates"]])
        self.SigRelay.emit("cm_playrec",["irate",self.m["irate"]])
        self.SigRelay.emit("cm_resample",["reslist_ix",self.m["reslist_ix"]]) #TODO check: maybe local in future !
        self.SigRelay.emit("cm_configuration",["tablist",tab_dict["list"]])
        #self.SigRelay.emit("cexex_core",["updateGUIelements",0])
        self.SigRelay.emit("cm_playrec",["sdr_configparams",self.m["sdr_configparams"]])
        self.SigRelay.emit("cm_playrec",["HostAddress",self.m["HostAddress"]])
        self.core_c.m["QTMAINWINDOWparent"] = gui
        self.SigRelay.emit("cm_all_",["QTMAINWINDOWparent",gui])
        self.SigRelay.emit("cm_all_",self.m["rootpath"])
        pass

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
            self.gui.playrec_lineEdit_recordingpath.setText(self.m["recording_path"])    #TODO TODO TODO should be part of the playrec module ?
            self.SigRelay.emit("cm_all_",["recording_path",self.m["recording_path"]])
            #self.SigRelay.emit("cm_all_",["QTMAINWINDOWparent",self.m["QTMAINWINDOWparent"]])
        except:
            self.core_c.recording_path_checker()
            #self.configuration_c.recording_path_setter()
        
    def updatetimer(self):
        """
        updates timer functions, shows date and time, changes between UTC and local time

        :param: none
        :type: none
        :return: none
        :rtype: none
        """
        if self.gui.checkBox_UTC.isChecked():
            self.UTC = True #TODO:future system state
        else:
            self.UTC = False

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
            
        if self.firsttick:
            self.firsttick = False
            print("first tick, initialize GUI")
            #gui.resize_initialize()
            self.m["Mainwindowreference"].trigger_resize_event()
            
        self.SigRelay.emit("cexex_all_",["timertick",0])
        
    def GUI_reset_status(self):
        """reset status of all GUI elements to initial state

        :param: none
        :return: none
        """
        #self.m = {}
        self.m["my_filename"] = ""
        self.m["ext"] = ""
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


    def setactivity_tabs(self,caller,statuschange,exceptionlist):
        """
        activates or inactivaes all tabs except the caller.\n
        caller: calling Tab corresponding to TabName of the caller module as defined in gui.gui.tabWidget.TabText 
        (currently set in  __main__ for each module by gui.gui.tabWidget.setTabText)
        
        statuschange: string indicating if other Tabs should be activated or inactivated:

        - 'activate': activate all tabs except the caller
        - 'inactivate' inactivate all tabs except the caller

        exceptionlist: list of all Tab names the status of which should not be changed

        :param: caller
        :type: str
        :param: statuschange
        :type: str
        :param: exceptionlist
        :type: list        
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
        activates waveditor via Relay signalling ##TODO: unclear why this method is called reset_GUI; seems very strange

        :param: none
        :return: True after completion, False if status-yaml not accessible
        :rtype: boolean
        """
        self.SigRelay.emit("cexex_waveditor",["activate_WAVEDIT",0])

    def cb_open_file(self):
        """ slot function for the File Open action in the Menubar of the Main GUI. It checks some conditions for proper opening of a new data file; 
        if all conditions are met FileOpen() is called which does the detailed work
        returns without action if a playthread is currently active; 
        if a file is open, the method asks if a new file should be opened (yes/no); returns on 'No'
        The method relays the variable m["fileopened"] via the SigRelay signal to all other modules
        
        .. image:: ../../source/images/cb_open_file.svg

        :param: none
        :returns: True if successful, False if condition not met.
        :type: Boolean
        """
        
        self.setactivity_tabs("all","activate",[])

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

        self.SigRelay.emit("cm_playrec",["HostAddress",self.m["HostAddress"]])
        
        if self.m["fileopened"] is True:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("open new file")
            msg.setInformativeText("you are about to open another file. Current file will be closed; Do you want to proceed")
            msg.setWindowTitle("FILE OPEN")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.buttonClicked.connect(self.popup)
            msg.exec_()

            if self.yesno == "&Yes":
                if self.fileOpen() is False:
                    self.SigRelay.emit("cm_all_",["fileopened", False])
                    return False
        else:
            if self.fileOpen() is False:
                self.SigRelay.emit("cm_all_",["fileopened",False])
                return False
            else:
                self.SigRelay.emit("cm_all_",["fileopened",True])

    def popup(self,i):
        """
        """
        self.yesno = i.text()

    def setstandardpaths(self):  #TODO: shift to controller and general system module ? must be part of the system configuration procedure
        """set standard paths for intermedite files and configuration files for the modules 
        annotation and yaml_editor (for the auxiliary annotation files and the final annotation yaml) 
        The pathnames are then relayed via SigRelay to the respective modules. This method is called by fileOpen() after a file has been opened
        
        :TODO: check if some of the operations can be shifted to the respective modules
        :TODO: should be shifted to the controller class
        ------------------------------------------------------
        
        :parameters: none
        :returns: none
        """
        self.m["annotationpath"] = self.my_dirname + '/' + self.annotationdir_prefix + self.m["my_filename"]
        #suggestion: shift definition of annotationpathprefix to annotator and define all pathnames there

        stations_filename = self.m["annotationpath"] + '/stations_list.yaml'
        status_filename = self.m["annotationpath"] + '/status.yaml'
        annotation_filename = self.m["annotationpath"] + '/snrannotation.yaml'
        self.SigRelay.emit("cm_annotate",["annotationpath",self.m["annotationpath"]])
        self.SigRelay.emit("cm_annotate",["stations_filename",stations_filename])
        self.SigRelay.emit("cm_annotate",["status_filename",status_filename])
        self.SigRelay.emit("cm_annotate",["annotation_filename",annotation_filename])
        self.SigRelay.emit("cm_annotate",["annotationdir_prefix",self.annotationdir_prefix])
        self.SigRelay.emit("cm_all_",["standardpath",self.standardpath])
        
        cohiradia_metadata_filename = self.m["annotationpath"] + '/cohiradia_metadata.yaml'
        cohiradia_yamlheader_filename = self.m["annotationpath"] + '/cohiradia_metadata_header.yaml'
        cohiradia_yamltailer_filename = self.m["annotationpath"] + '/cohiradia_metadata_tailer.yaml'
        cohiradia_yamlfinal_filename = self.m["annotationpath"] + '/COHI_YAML_FINAL.yaml'
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamlheader_filename",cohiradia_yamlheader_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamltailer_filename",cohiradia_yamltailer_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_yamlfinal_filename",cohiradia_yamlfinal_filename])
        self.SigRelay.emit("cm_yamleditor",["cohiradia_metadata_filename",cohiradia_metadata_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamlheader_filename",cohiradia_yamlheader_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamltailer_filename",cohiradia_yamltailer_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_yamlfinal_filename",cohiradia_yamlfinal_filename])
        self.SigRelay.emit("cm_annotate",["cohiradia_metadata_filename",cohiradia_metadata_filename])

    def set_startuptab(self):
        """writes intex of current Tab in Startuptab-combobox to configwizard.yaml

        :param: none
        :returns: none
        """
        curix = self.gui.playrec_comboBox_startuptab.currentIndex()
        print(f"startuptab set: {curix}")
        #write to yaml
        self.m["metadata"]["startup_tab"] = str(curix) 
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()
        pass

    #@njit
    def fileOpen(self):   #TODO: shift to controller

        '''
        
        acquires info about file to be opened and relays the following information to all other modules

        - ["ismetadata"]
        - ["metadata"]
        - ["f1"]
        - ["my_dirname"]
        - ["ext"]
        - ["my_filename"]
        - ["temp_directory"]
        - ["wavheader"]
       	- ["readoffset"]
        - ["fileopened"]
        - ["out_dirname"]

        :TODO shift to controller module  !!!!!:

        :params: none
        :type: none
        :returns: True, if successful, False otherwise
        :type: Boolean

        .. image:: ../../source/images/fileopen.svg

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

        st = time.time()
        self.SigRelay.emit("cm_all_",["f1", filename[0]])
        if not self.m["f1"]:
            return False
        self.logger.info(f'fileOpen: core_v File opened: {self.m["f1"]}')

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
        et = time.time()
        print(f"first segment etime: {et-st} s: process prompt and signalling to rest")
        self.logger.debug(f">>>>>> open file TIMING, first segment: {et-st} s: make out directory")


        if self.m["ext"] == ".dat" or self.m["ext"] == ".raw":
            filetype = "dat"
            self.SigRelay.emit("cexex_waveditor",["activate_insertheader",True])

        else:
            if self.m["ext"] == ".wav":
                filetype = "wav"
                self.SigRelay.emit("cexex_waveditor",["activate_insertheader",False])
                self.setactivity_tabs("Resample","activate",[])
            else:
                auxi.standard_errorbox("no valid data forma, neiter wav, nor dat nor raw !")
                return
        st = et
        et = time.time()
        #print(f"second segment etime: {et-st} s")

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
        st = et
        et = time.time()
        #print(f"3rd segment etime: {et-st} s: wav header read")

        # build up playlist selectors
        self.SigRelay.emit("cexex_playrec",["addplaylistitem",0])
        self.SigRelay.emit("cexex_playrec",["fillplaylist",0])      
        self.SigRelay.emit("cexex_resample",["addplaylistitem",0])
        self.SigRelay.emit("cexex_resample",["fillplaylist",0])
        self.logger.debug("core_v: wavheader extracted and sent to all modules")

        st = et
        et = time.time()
        #print(f"4th segment etime: {et-st} s: signalling 2")

        ### set readoffset and relay to modules: TODO: check if should be translated to modules (dangerous, may affect many instances)
        if self.wavheader['sdrtype_chckID'].find('rcvr') > -1:
            self.m["readoffset"] = 86
        else:
            self.m["readoffset"] = 216

        self.SigRelay.emit("cm_all_",["readoffset",self.m["readoffset"]])

        #TODO TODO TODO check for transfer to modules
        self.m["irate"] = self.wavheader['nSamplesPerSec'] #ONLY used in player, so shift

        # TODO FUTURE: check for append metadata instead of new write

        #save metadata
        self.m["metadata"]["last_path"] = self.my_dirname
        stream = open("config_wizard.yaml", "w")
        yaml.dump(self.m["metadata"], stream)
        stream.close()

        st = et
        et = time.time()
        #print(f"5th segment etime: {et-st} s: dump config yaml")

        self.m["timescaler"] = self.wavheader['nSamplesPerSec']*self.wavheader['nBlockAlign']
        self.m["fileopened"] = True #check if obsolete because f1 == "" would do the same
        self.SigRelay.emit("cm_all_",["fileopened",True])

        st = et
        et = time.time()
        #print(f"6A segment etime: {et-st} s: only relaying")

        out_dirname = self.my_dirname + '/out'  #TODO TODO TODO should only be created if really necessary for resampling !
        if os.path.exists(out_dirname) == False:         #exist yaml file: create from yaml-editor
            os.mkdir(out_dirname)
        self.SigRelay.emit("cm_all_",["out_dirname",out_dirname])

        st = et
        et = time.time()
        #print(f"6B segment etime: {et-st} s: make out directory")
        self.logger.debug(f"6B segment etime: {et-st} s: make out directory")


        ##############TODO TODO TODO: intermediate hack for comm with scan worker
        self.SigRelay.emit("cexex_all_",["updateGUIelements",0])
        st = et
        et = time.time()
        self.logger.debug(f"6C segment etime: {et-st} s: relay and updateGUIs of all modules")
        print(f"6C segment etime: {et-st} s: relay and updateGUIs of all modules")

        #TODO TODO TODO: track multiple calls of plot_spectrum: is that really necessary on each fileopen ? 
        return True

    def dat_extractinfo4wavheader(self): #TODO: should be shifted to the controller !
        #TODO: erkennt COHIRADIA Namenskonvention nicht, wenn vor den _lo_r_c literalen noch andere _# Felder existieren.  shift to controller module
        """ 
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
            self.m["ifreq"] = int(int(freq) + self.m["LO_offset"]) 

        ti_m = os.path.getmtime(self.m["f1"])
        file_mod = datetime.fromtimestamp(ti_m)
        file_stats = os.stat(self.m["f1"])
        self.wavheader = WAVheader_tools.basic_wavheader(self,self.m["icorr"],int(self.m["irate"]),int(self.m["ifreq"]),int(bps),file_stats.st_size,file_mod)
        return True

    def rxhandler(self,_key,_value):
        """
        handles the exchange of variables between modules and remote calls of specific standard methods 
        from other modules via Signal SigRX(_key,_value). Also communication between module_c and module_v 
        needs to be relayed via this hadler, because module_c cannot access methods of module_v directly. 
        On reception of this signal _key is interpreted and if it contains a specific prefix an action is carried out:
    
        (1): Prefix = 'cm_all_': copy _value [1] to the model variable m['_value[0]']. Example: Another module sends 
        SigRelay('cm_all_',['myvar',self.m['myvar']]), then the current module takes over this variable into the own 
        model, i.e. the variable self.m['myvar] exists from that moment or is overwritten. Caution: Use with care. model 
        variables with the same name as in other modules may be overwritten, If this is to be avoided , the the 
        respective names should not be used(listed in aa dictionary of reserved names).

        :param: _key
        :type: str
        :param: _value
        :type: object
        :raises: [ErrorDescription]
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
                self.logger.debug("call updateGUIelements")
            if  _value[0].find("updatetimer") == 0:
                self.updatetimer()
            if  _value[0].find("stoptick") == 0:
                self.timertick.stoptick()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("updateConfigElements") == 0:
                self.updateConfigElements()
            if  _value[0].find("resizeaction") == 0:
                #print("resize action triggered in core")
                _value[1].resize_initialize()
                

class SplashScreen(QWidget):
    """This class provides a simple splash screen for the application.
    It shows the logo of the application for 2 seconds and then closes itself.
    """
    def __init__(self):
        super().__init__()
        #logger.debug("Showing Splash Screen")

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0) 
        logopath = Path(os.getcwd()) / "logos"
        self.logo = Logos.Logo_full(logopath)
        self.logo_label = QLabel()
        if self.logo.availableSizes() == []:
            print(f"Could not load splashscreen icon")
        else:
            self.logo_label.setPixmap(self.logo.pixmap(self.logo.availableSizes()[0]))
        self.logo_label.setStyleSheet("border: 0px solid green")

        self.main_layout.addWidget(self.logo_label)
        self.setLayout(self.main_layout)

        self.timer = QTimer()
        self.timer.singleShot(4000, self.close)
        
        # Set window properties


def load_config_from_yaml(file_path):
    """load module configuration from yaml file"""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except:
        return (None)


def dynamic_import_from_config(config,sub_module,logger):
    """Dynamic import of modules based on module configuration"""
    #DUMMY LINE
    imported_modules = {}
    for directory, module in config[sub_module].items():
        try:
            # create path <directory>.<module>
            full_module_path = f"{directory}.{module}"
            # Importmodule dynamically
            imported_module = importlib.import_module(full_module_path)
            imported_modules[module] = imported_module
            logger.debug(f"dynamic import: Successfully imported {module} from {full_module_path}.")
            #print(f"Successfully imported {module} from {full_module_path}.")
        except ModuleNotFoundError as e:
            print(f"dynamic import Error importing {module} from {directory}: {e}")
            logger.debug(f"dynamic import: Error importing {module} from {directory}: {e}")
    return imported_modules

if __name__ == '__main__':
    """_summary_
    - instantiate app
    - call starter for creating central GUI
    - gui is then an object of type QMainWindow and has the GUI gui.gui = MyWizard = class UIMainWindow in COHIWitard_GUI_v10
    - import auxiliary packages and modules
    - instantiate core methods and player module/widget
    - instantiate all GUI widgets and modules listed in config_modules.yaml
    - build all possible connections between SigRelay-Signals and rxhandlers of all modules
    - setup the relaying mechanism for the exchange of variables between modules
    """


    print("starting main, initializing GUI, please wait ... ")
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    #print("v13")
    app = QApplication([])
    wiz_config = load_config_from_yaml("config_wizard.yaml")
    
    if wiz_config == None:
        skinindex = 1
    else:    
        skinindex = wiz_config["skinindex"] ##########TODO CHECK
    gui = starter(skinindex)
    #print(f"__main__: gui = {gui} gui.gui = {gui.gui}")
    from auxiliaries import WAVheader_tools
    from auxiliaries import auxiliaries as auxi
    from auxiliaries import timer_worker as tw
    from auxiliaries import RPListener
    
    #instantiate core module
    xcore_m = core_m()
    xcore_c = core_c(xcore_m)
    xcore_v = core_v(gui,xcore_c,xcore_m) # self.gui wird in xcore_v gestartet 

    config = load_config_from_yaml("config_modules.yaml")
    #TODO TODO TODO: generalize: get from config !

    sub_module = "modules"
    mod_base = {'player':'playrec'}
    config['modules'] = {**mod_base, **config['modules']}
    #print(f"config file content: {config}")
    widget_base = {'player': 'Player'}
    config['module_names'] = {**widget_base, **config['module_names']}
    loaded_modules = dynamic_import_from_config(config,sub_module,xcore_v.logger)
    #print(f"__main__ first if NEW: {loaded_modules}")

    gui.show()

    list_mvct_directories = list(config['modules'].keys())
    #get list of corresponding mvct modules
    list_mvct_modules = list(config['modules'].values())
    #add dict of widget modules to config
    aux_dict = {}
    for ix in range(len(list_mvct_directories)):

        aux_dict[list_mvct_directories[ix]] = list_mvct_directories[ix] + "_widget_skin_" + str(skinindex)
    config["widget"] = aux_dict
    #print(f"__main__ 2nd if NEW: config, aux_dict: {config['widget']}")
    
    #get list of corresponding widget modules
    list_widget_modules = list(config['widget'].values())

    loaded_widget_modules = dynamic_import_from_config(config,"widget",xcore_v.logger)
    #print(loaded_widget_modules)

    tabui = []
    tab_widget = []
    for ix in range(len(list_mvct_directories)):
        try:
            mod_name = config["module_names"][list_mvct_directories[ix]]

            if mod_name == "Player":    #TODO: future versions should be more general and treat Player as a normal module
                #dummy operation, because Player UI already exists
                tab_widget.append([])
                tabui.append([])
                pass
            else:
                #generate new Widget, name it, label it , carry out its setupUi method, except for player,
                #  whose UI already exists in form of xcore.gui and whose Tab also already exists
                tabui.append(getattr(loaded_widget_modules[list_widget_modules[ix]], "Ui_" + list_widget_modules[ix].replace("_skin_" + str(skinindex),""))())
                tab_widget.append(QtWidgets.QWidget())
                tab_widget[ix].setWindowTitle(mod_name)
                tab_widget[ix].setObjectName("tab_" + mod_name)
                tab_widget[ix].setWindowIconText(mod_name)
                tabui[ix].setupUi(tab_widget[ix])
                a = gui.gui.tabWidget.addTab(tab_widget[ix], "")
                gui.gui.tabWidget.setTabText(a,mod_name)
            #print(f"Successfully created tab for {mod_name}.")
        except AttributeError as e:
            #print(f"Error creating tab for {mod_name}: {e}")
            xcore_v.logger.error(f"__main__: Error creating tab for {mod_name}: {e}")

    #access elements of tabUI_Player via tabUI_Player instance ! not gui.gui.
    #app.aboutToQuit.connect(win.stop_worker)    #graceful thread termination on app exit
    tab_dict = {}
    tab_dict["list"] = ["xcore"]
    tab_dict["tabname"] = ["xcore"]

    tab_m = []
    tab_c = []
    tab_v = []
    #instantiate modules
    for ix in range(len(list_mvct_directories)):
        try:
            mod_name = config["module_names"][list_mvct_directories[ix]]
            tab_m.append(getattr(loaded_modules[list_mvct_modules[ix]], list_mvct_modules[ix] + "_m")())
            tab_c.append(getattr(loaded_modules[list_mvct_modules[ix]], list_mvct_modules[ix] + "_c")(tab_m[ix]))
            if mod_name == "Player":  ##TODO nach tests durch allgemeine Fassung: loaded_modules[list_mvct_modules[ix]] = xcore_v.gui
                tab_v.append(getattr(loaded_modules[list_mvct_modules[ix]], list_mvct_modules[ix] + "_v")(xcore_v.gui, tab_c[ix], tab_m[ix]))
            else:
                tab_v.append(getattr(loaded_modules[list_mvct_modules[ix]], list_mvct_modules[ix] + "_v")(tabui[ix], tab_c[ix], tab_m[ix]))
            tab_dict["list"].append(list_mvct_modules[ix])
            tab_dict["tabname"].append(mod_name)
            tab_v[ix].SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
            tab_c[ix].SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
            #print(f"Successfully created model, control, view for {mod_name}.")
        except AttributeError as e:
            #print(f"Error creating model, control, view for {mod_name}: {e}")
            xcore_v.logger.error(f"__main__: Error creating model, control, view for {mod_name}: {e}")

    # #TODO TODO TODO TODO TODO TODO TODO difficult to find, poor programming style, look for other connection (via relaying ?)
    #tab_c[list_mvct_modules.index("resample")].SigUpdateGUIelements.connect(tab_v[list_mvct_modules.index("resample")].updateGUIelements)
    # replaced by         self.resample_c.SigUpdateGUIelements.connect(self.updateGUIelements) in resample_v
# TODO Test after 21-11-2024
    if 'view_spectra' in list_mvct_modules:
        xcore_v.SigUpdateOtherGUIs.connect(tab_v[list_mvct_modules.index("view_spectra")].updateGUIelements)
        #xcore_v.SigUpdateOtherGUIs.emit()
        #TODO TODO TODO: SigupdateotherGUIs is not yetconnected to anything
        #replace by: xcore_v.SigUpdateOtherGUIs.connect(view_spectra_v.updateGUIelements)
        #difficult to replace, because view_spectra does not know xcore
        #xcore must be relayed to view spectra module, try:
        xcore_v.SigRelay.emit("cm_all_",["reference_xcore_v",xcore_v])
        #then signal updater request via GUI update routine
        #and in spectral viewer, views_pectra_v: self.m["reference_xcore_v"].SigUpdateOtherGUIs.connect(self.updateGUIelements)
    tab_v[list_mvct_modules.index("resample")].SigUpdateOtherGUIs.connect(xcore_v.updateGUIelements)

    #TODO: check what to do if tab_names do not exist any more because tabWidget is empty or rudimentary ?
    tab_names = {}
    for index in range(gui.gui.tabWidget.count()):
        tab_names[index] = gui.gui.tabWidget.tabText(index)

    tabselector = [""] * len(tab_dict["tabname"])
    for _ct,_name in enumerate(tab_dict["tabname"]):
        try:
            _key = [k for k,v in tab_names.items() if v == _name][0] #xcore_v.
            tabselector[_key] = _name 
        except:
            pass
    tabselector = list(filter(None, tabselector))

    # set startup Tab
    xcore_v.gui.playrec_comboBox_startuptab.addItems(tabselector)
    xcore_v.gui.playrec_comboBox_startuptab.setEnabled(True)
    try: ###TODO TODO TODO: check if this call can be removed because it is repeated at the end of __main__
        xcore_v.gui.playrec_comboBox_startuptab.setCurrentIndex(int(xcore_v.m["metadata"]["startup_tab"]))
        xcore_v.gui.tabWidget.setCurrentIndex(int(xcore_v.m["metadata"]["startup_tab"]))
    except:
        xcore_v.logger.debug("startup Tab not defined in configuration file config_wizard.yaml")
    xcore_v.gui.playrec_comboBox_startuptab.currentIndexChanged.connect(xcore_v.set_startuptab)

    # build connections for interpackage-Relaying system
    xcore_v.SigRelay.connect(xcore_v.rxhandler)
    for ix1 in range(len(tab_dict["list"])-1):
        tab_v[ix1].SigRelay.connect(xcore_v.rxhandler)
        xcore_v.SigRelay.connect(tab_v[ix1].rxhandler)
        xcore_v.logger.debug(f' {"xcore_v.SigRelay.connect(" + tab_dict["list"][ix1+1] + "_v.rxhandler)"}')
        xcore_v.logger.debug(f' {tab_dict["list"][ix1+1] + ".SigRelay" + "(xcore_v.rxhandler)"}')
        #print(f' {tab_dict["list"][ix1+1] + ".SigRelay" + "(xcore_v.rxhandler)"}')
        #print(f' {"xcore_v.SigRelay.connect(" + tab_dict["list"][ix1+1] + "_v.rxhandler)"}')

        for ix2 in range(len(tab_dict["list"])-1):
            tab_v[ix1].SigRelay.connect(tab_v[ix2].rxhandler)
            
            #tab_c[ix].SigActivateOtherTabs.connect(xcore_v.setactivity_tabs)
            xcore_v.logger.debug(f' {tab_dict["list"][ix1+1] + "_v.SigRelay.connect(" + tab_dict["list"][ix2+1] + "_v.rxhandler)"}')

    #make tab dict visible to core module
    xcore_v.tab_dict = tab_dict 
    xcore_v.m["tab_dict"] = tab_dict  ###TODO: check if double tabdict in xcore_v is necessary

    #all tab initializations occur in connect_init() in core module
    xcore_v.connect_init()
    # enable relaying startup settings to all modules if required
    xcore_v.updateConfigElements() 
    xcore_v.SigRelay.emit("cexex_all_",["canvasbuild",gui])   # communicate reference to gui instance to all modules which instanciate a canvas with auxi.generate_canvas(self,gridref,gridc,gridt,gui)
    xcore_v.SigRelay.emit("cm_all_",xcore_v.m["rootpath"])
    xcore_v.SigRelay.emit("cm_all_",["Mainwindowreference",gui])
    xcore_v.SigRelay.emit("cexex_all_",["resizeaction",gui])
    #gui.resize_initialize()
    # gui.find_widgets_with_font()
    # gui.find_icon_buttons()
    #gui.resize_actor()
    QTimer.singleShot(0, gui.resize_actor)
    for ix, value in enumerate(tab_dict["tabname"]):
        xcore_v.gui.tabWidget.setCurrentIndex(ix)
        QTimer.singleShot(0, gui.trigger_resize_event)  # trigger resize event for each tab
    try: ###TODO TODO TODO: check if the first previous call can be removed above !
        xcore_v.gui.playrec_comboBox_startuptab.setCurrentIndex(int(xcore_v.m["metadata"]["startup_tab"]))
        xcore_v.gui.tabWidget.setCurrentIndex(int(xcore_v.m["metadata"]["startup_tab"]))
    except:
        xcore_v.logger.debug("startup Tab not defined in configuration file config_wizard.yaml")
        xcore_v.gui.tabWidget.setCurrentIndex(0)
    print("COHIWIzard Version 2.1.4 , 05-12-2025, (C) Hermann Scharfetter")
    sys.exit(app.exec_())
    ###############TODO: zeroconf muss nun importiert werden !
