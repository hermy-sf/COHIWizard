import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
#from PyQt5 import QtGui
from scipy import signal as sig
from scipy.ndimage.filters import median_filter
#from SDR_wavheadertools_v2 import WAVheader_tools
#from auxiliaries import WAVheader_tools
import time
from auxiliaries import auxiliaries as auxi
import logging
#from numba import njit

class view_spectra_m(QObject):
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
        self.mdl["resampling_gain"] = 0
        self.mdl["my_filename"] = ""
        self.mdl["ext"] = ""
        self.mdl["deltaf"] = 5000 #minimum peak distance in Hz for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.mdl["peakwidth"] = 10 # minimum peak width in Hz for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.mdl["prominence"] = 15 # minimum peak prominence in dB above baseline for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        #self.mdl["FILTERKERNEL"] =15 # length of the moving median filter kernel in % of the spectral span #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        #TODO: make this a config item, also initialized in annotator !
        self.mdl["filterkernel"] = 15
        self.mdl["baselineoffset"] = 0
        self.mdl["position"] = 0
        self.mdl["Mainwindowreference"] = None

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

        self.logger.debug('Init logger in view_spectra reached')

class view_spectra_c(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["contvars"]

    SigAny = pyqtSignal()
    SigCancel = pyqtSignal()
    SigRelay = pyqtSignal(str,object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    #SigDisplaySpectrum = pyqtSignal(object,object)

    def __init__(self, view_spectra_m):
        super().__init__()

    # def __init__(self, *args, **kwargs): #TEST 09-01-2024
    #     super().__init__(*args, **kwargs)
        viewvars = {}
        #self.set_viewvars(viewvars)
        self.m = view_spectra_m.mdl
        self.logger = view_spectra_m.logger



class view_spectra_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["viewvars"]

    SigAny = pyqtSignal()
    SigCancel = pyqtSignal()
    SigSyncGUIUpdatelist = pyqtSignal(object)
    SigUpdateOtherGUIs = pyqtSignal() #TODO: used for anything ?
    SigRX = pyqtSignal(str,object)
    SigRelay = pyqtSignal(str,object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)

    def __init__(self, gui, view_spectra_c, view_spectra_m):
        super().__init__()

        #viewvars = {}
        #self.set_viewvars(viewvars)
        self.m = view_spectra_m.mdl
        self.logger = view_spectra_m.logger
        self.DATABLOCKSIZE = 1024*32
        #self.sys_state = wsys.status() #TEST: commented out 09-01-2024
        #self.sys_state = gui_state
        #system_state = self.sys_state.get_status()
        self.m["reslistdoubleemit_ix"] = False
        self.m["starttrim"] = False
        self.m["stoptrim"] = False
        self.m["spectrum_position"] = 0
        self.gui = gui #gui_state["gui_reference"]#system_state["gui_reference"]
        #self.SigUpdateGUI.connect(self.update_GUI) #TODO: remove after tests
        self.SigRX.connect(self.rxhandler)
        self.init_view_spectra_ui()
        #print(f"self: {self}, gui: {gui}")
        #cref = auxi.generate_canvas(self,self.gui.gridLayout_4,[4,0,1,5],[2,2,2,1],gui) ##gui must be the starter object

    def init_view_spectra_ui(self):
        self.gui.spinBoxminPeakwidth.valueChanged.connect(self.minPeakwidthupdate)
        self.gui.spinBoxminPeakDistance.valueChanged.connect(self.minPeakDistanceupdate)
        self.gui.spinBoxminSNR_ScannerTab.valueChanged.connect(self.minSNRupdate_ScannerTab)
        self.gui.spinBoxKernelwidth.valueChanged.connect(self.setkernelwidth)
        self.gui.spinBoxKernelwidth.setEnabled(True)
        self.gui.spinBoxKernelwidth.setProperty("value", self.m["filterkernel"])
        self.gui.spinBoxminBaselineoffset.setProperty("value", 0)#TODO: avoid magic number
        self.gui.spinBoxminBaselineoffset.valueChanged.connect(self.set_baselineoffset)
        self.gui.horizontalScrollBar_view_spectra.sliderReleased.connect(self.cb_plot_spectrum)
        self.gui.radioButton_plotraw.clicked.connect(self.cb_plot_spectrum)
        #self.SigToolbar.connect(lambda: self.plot_spectrum(self,self.position)) #TODO Remove ???
        #TODO: replace by signalling 

        #self.gui.spinBoxNumScan.setProperty("value", 10) #TODO: avoid magic number
        self.gui.label_Filename_ViewSpectra.setText('')
        self.setkernelwidth()
        self.minPeakwidthupdate()
        self.minPeakDistanceupdate()
        self.minSNRupdate_ScannerTab()


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

        
    # def connector(self):
    #     self.SigSyncGUIUpdatelist.emit(self.updateGUIelements)

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
        #self.logger.debug("key: %s , value: %s", _key,_value)

        if _key.find("cm_view_spectra") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
            if _value[0].find("Mainwindowreference") >= 0: #These commands are not yet used, just for testing. Usually the Mainwindowreference is not used inside the Tab-widgets
                         self.m["Mainwindowreference"].SigResize.connect(self.resizehandler)
                         #print(f"spectralviewer: Mainwindowreference: {self.m["Mainwindowreference"]}")

        if _key.find("cui_view_spectra") == 0:
            _value[0](_value[1])    #TODO TODO: still unclear implementation
        if _key.find("cexex_view_spectra") == 0:
            if  _value[0].find("plot_spectrum") == 0:
                self.plot_spectrum(0,_value[1])
        if _key.find("cexex_view_spectra") == 0 or _key.find("cexex_all_") == 0:
            if  _value[0].find("plot_spectrum") == 0:
                self.plot_spectrum(0,_value[1])
                self.logger.debug("call plot spectrum")
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
                self.logger.debug("call updateGUIelements")
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])
            if  _value[0].find("canvasbuild") == 0:
                self.canvasbuild(_value[1])
            if  _value[0].find("enablescrollbar") == 0:
                self.gui.horizontalScrollBar_view_spectra.setEnabled(_value[1])

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

        self.cref = auxi.generate_canvas(self,self.gui.gridLayout_4,[4,0,1,5],[3,1,1,2],gui)

    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("view spectra: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.debug("view spectra: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)


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
        st = time.time()

        #print("view spectra: updateGUIelements")
        self.gui.spinBoxminSNR_ScannerTab.valueChanged.disconnect(self.minSNRupdate_ScannerTab)
        self.gui.spinBoxminSNR_ScannerTab.setProperty("value",self.m["prominence"])
        self.gui.spinBoxminSNR_ScannerTab.valueChanged.connect(self.minSNRupdate_ScannerTab)
        self.logger.debug("view spectra: updateGUIelements")
        self.gui.label_Filename_ViewSpectra.setText(self.m["my_filename"] + self.m["ext"])
        dummy = 0
        self.plot_spectrum(dummy,self.m["spectrum_position"])
        self.logger.debug("view spectra: emit baselineoffset %i", self.m["baselineoffset"])
        self.SigRelay.emit("cm_xcore",["baselineoffset",self.m["baselineoffset"]])
        et = time.time()
        self.logger.debug(f"view spectra update gui segment etime: {et-st} s: ")


    def reset_GUI(self):
        #clear canvas
        # self.m["Tabref"]["View_Spectra"]["ax"].clear()
        # self.m["Tabref"]["View_Spectra"]["canvas"].draw()
        # self.gui.label_Filename_ViewSpectra.setText("")
        # self.gui.lineEdit_evaltime.setText("")
        self.cref["ax"].clear()
        self.cref["canvas"].draw()
        self.gui.label_Filename_ViewSpectra.setText("")
        self.gui.lineEdit_evaltime.setText("")
        
        pass

    def cb_plot_spectrum(self):
        position = self.gui.horizontalScrollBar_view_spectra.value()
        self.SigRelay.emit("cm_resample",["spectrum_position",position])
        self.SigRelay.emit("cm_view_spectra",["position",position])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])
        self.SigRelay.emit("cexex_resample",["updateGUIelements",0])
        self.plot_spectrum(0,position)
        self.logger.debug("cb_plot_spectrum in module view_spectra reached")

    def plot_spectrum(self,dummy,position):
        """
        plot a segment at position 'position' of the spectrum or raw data from file f1. posiion is a fraction of the filesize between 0 and 1
        The filepath f1 must be set as self.m["f1 before in another module (typically core)
        :param : dummy
        :type : none
        :param : position
        :type : float
        :raises [ErrorType]: [ErrorDescription]
        :return: flag False or True, False on unsuccessful execution
        :rtype: Boolean
        """
        self.logger.debug("view_spectra plot_spectum reached")
        if self.m["fileopened"] is False:
            return(False)
        else:
            self.m["horzscal"] = position
            # read datablock corresponding to current sliderposition
            #TODO TODO TODO: correct 32 bit case if wFormatTag != 3
            #print("plot spectrum reached, start readsegment")
            pscale = self.m["wavheader"]['nBlockAlign']
            position = int(np.floor(pscale*np.round(self.m["wavheader"]['data_nChunkSize']*self.m["horzscal"]/pscale/1000)))
            if self.m["wavheader"]['sdrtype_chckID'].find('rcvr') > -1:
                self.readoffset = 86
            else:
                self.readoffset = 216
            ret = auxi.readsegment_new(self,self.m["f1"],position,self.readoffset,self.DATABLOCKSIZE,self.m["wavheader"]["nBitsPerSample"],
                                      32,self.m["wavheader"]["wFormatTag"])
            data = ret["data"]
            if 2*ret["size"]/self.m["wavheader"]["nBlockAlign"] < self.DATABLOCKSIZE:
                return False

            self.cref["ax"].clear()
            if self.gui.radioButton_plotraw.isChecked() is True:
                realindex = np.arange(0,self.DATABLOCKSIZE,2)
                imagindex = np.arange(1,self.DATABLOCKSIZE,2)
                #calculate spectrum and shift/rescale appropriately
                trace = np.real(data[realindex]+1j*data[imagindex])
                trace = trace * np.power(10,self.m["resampling_gain"]/20)
                N = len(trace)
                deltat = 1/self.m["wavheader"]['nSamplesPerSec']
                time_ = np.linspace(0,N*deltat,N)
                self.cref["ax"].plot(time_,trace, '-')
                self.cref["ax"].set_xlabel('time (s)')
                self.cref["ax"].set_ylabel('RFCorder amplitude (V)')

            else:
                pdata = self.ann_spectrum(0,data)
                #TODO: make function for plotting data , reuse in autoscan
                datax = pdata["datax"]
                datay = pdata["datay"] + self.m["resampling_gain"]
                basel = pdata["databasel"] + self.m["baselineoffset"]
                peaklocs = pdata["peaklocs"]
                peakprops = pdata["peakprops"]
                # create axis, clear old one and plot data

                self.cref["ax"].plot(datax,datay, '-')
                self.cref["ax"].plot(datax[peaklocs], datay[peaklocs], "x")
                self.cref["ax"].plot(datax,basel, '-', color = "C2")
                self.cref["ax"].set_xlabel('frequency (Hz)')
                self.cref["ax"].set_ylabel('amplitude (dB)')
                #     ymax = datay[peaklocs], color = "C1")
                self.cref["ax"].vlines(x=datax[peaklocs], ymin = basel[peaklocs],
                    ymax = datay[peaklocs], color = "C1")
                self.cref["ax"].hlines(y=peakprops["width_heights"], xmin=datax[peakprops["left_ips"].astype(int)],
                    xmax=datax[peakprops["right_ips"].astype(int)], color = "C1")
            self.cref["canvas"].mpl_connect('button_press_event', self.on_click)
            self.cref["canvas"].draw()
            #display ev<luation time
            displtime = str(self.m["wavheader"]['starttime_dt'] + (self.m["wavheader"]['stoptime_dt']-self.m["wavheader"]['starttime_dt'])*self.m["horzscal"]/1000)
            self.gui.lineEdit_evaltime.setText('Evaluation time: '+ displtime + ' UTC')
        return(True)
    
    def on_click(self, event):
        """
        TODO for Walter: new method for data readout by clicking on CANVAS
        :param event
        :type: ??
        :raises [ErrorType]: [ErrorDescription]
        :return:
        :rtype:
        """
        if event.button == 1:  # Check if left mouse button is pressed
            x, y = event.xdata, event.ydata
            print(f'Clicked at x={x}, y={y}')

    #@njit
    def ann_spectrum(self,dummy,data,displaymode = "complex"):      #TODO: This is a controller method, should be transferred to an annotation module
        """
        generate a single spectrum from complex data
        scale x-axis as frequencies in the recorded AM band
        scale y-axis in dB
        calculate baseline basel from moving median filtering
        find spectral peaks (= transmitters) and calculate the corresponding properties
        requires the following properties to exist:
            self.DATABLOCKSIZE
        :param self: An instance of the class containing attributes such as header information and filtering parameters.
        :type self: object
        :param dummy: A dummy variable not used in the function.
        :type dummy: any
        :param data: A numpy array containing the complex data IQ data read from wav file
        :type data: numpy.ndarray of float32, even entries = real odd entries = imaginary
                part of the IQ signal
        :raises [ErrorType]: [ErrorDescription]
        :return: A dictionary containing various arrays related to the spectral analysis:
                - datax: The frequency data.type: float32
                - datay: The amplitude data.type: float32
                - datay_filt: The filtered amplitude data.type: float32
                - peaklocs: The indices of the identified peaks in the amplitude data.type: float32
                - peakprops: Properties of the identified peaks, such as their height and width. type: dict
                - databasel: The baseline data used in the filtering process.type: float32
        :rtype: dict
        """
        #print(f">>>>>>>>> @@@@@@@@@@@@ displaymode = : {displaymode}")
        self.logger.debug("view_spectra ann_spectum reached")
        st = time.time()
        if self.m["wavheader"]["nChannels"] == 1:
            print(f"display real spectrum")
            spr = np.abs(np.fft.fft(data))
            N = len(spr)
            spr = np.fft.fftshift(spr)/N
            freq = np.linspace(-self.m["wavheader"]['nSamplesPerSec']/2,self.m["wavheader"]['nSamplesPerSec']/2,N)
        else:
        # extract imaginary and real parts from complex data 
            realindex = np.arange(0,self.DATABLOCKSIZE,2)
            imagindex = np.arange(1,self.DATABLOCKSIZE,2)
            #calculate spectrum and shift/rescale appropriately
            spr = np.abs(np.fft.fft((data[realindex]+1j*data[imagindex])))
            N = len(spr)
            spr = np.fft.fftshift(spr)/N
            flo = self.m["wavheader"]['centerfreq'] - self.m["wavheader"]['nSamplesPerSec']/2
            fup = self.m["wavheader"]['centerfreq'] + self.m["wavheader"]['nSamplesPerSec']/2
            freq0 = np.linspace(0,self.m["wavheader"]['nSamplesPerSec'],N)
            freq = freq0 + flo
        datax = freq
        datay = 20*np.log10(spr)
        # filter out all data below the baseline; baseline = moving median
        # filter kernel is self.FILTERKERNEL % of the spectral span
        datay_filt = datay
        kernel_length = int(N*self.m["filterkernel"]/100)
        # kernel length must be odd integer
        if (kernel_length % 2) == 0:
            kernel_length += 1
        
        #databasel = sig.medfilt(datay,kernel_length)
        et = time.time()
        self.logger.debug(f"ann_spectrum segment plotting FFT etime: {et-st} s: update GUI")

        databasel = median_filter(datay,kernel_length, mode = 'constant')
        datay_filt[datay_filt < databasel] = databasel[datay_filt < databasel]
        # find all peaks which are self.PROMINENCE dB above baseline and 
        # have a min distance of self.DELTAF and a min width of self.PEAKWIDTH
        dist = np.floor(np.maximum(self.m["deltaf"]/self.m["wavheader"]['nSamplesPerSec']*N,100))
        wd = np.floor(self.m["peakwidth"]/self.m["wavheader"]['nSamplesPerSec']*N)
        #print(f"peakwidth: {wd}")
        peaklocs, peakprops = sig.find_peaks(datay_filt,
                        prominence=(self.m["prominence"],None), distance=dist, width = wd)
        ret = {"datax": datax, "datay": datay, "datay_filt": datay_filt,
                "peaklocs": peaklocs, "peakprops": peakprops, "databasel": databasel}
        et = time.time()
        self.logger.debug(f"ann_spectrum segment baseline and peakextract etime: {et-st} s: update GUI")
        return ret

    def minSNRupdate_ScannerTab(self):
        self.m["prominence"] = self.gui.spinBoxminSNR_ScannerTab.value()
        #TODO: this is an access to a function of another module; very dangerous, because it must be exactly known how to call that function
        #should this option be offered by the rxhandlers anyway ?
        ########TODO TODO TODO: urgent, close this access as soon as possible
        #self.SigRelay.emit("cui_annotate",[self.gui.spinBoxminSNR.setProperty,["value",self.m["prominence"]]])
        #####################
        #print("######################## minSNRupdate_ScannerTab reached")
        self.SigRelay.emit("cm_all_",["prominence", self.m["prominence"]])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])
        self.SigRelay.emit("cexex_annotate",["updateGUIelements",0])

    def set_baselineoffset(self):        
        #print("######################## set_baselineoffset reached")
        baselineoffset = self.gui.spinBoxminBaselineoffset.value()
        self.SigRelay.emit("cm_all_",["baselineoffset",baselineoffset])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])
        self.SigRelay.emit("cexex_annotate",["updateGUIelements",0])

    def setkernelwidth(self):              
        #print("######################## setkernelwidth reached") 
        filterkernel = self.gui.spinBoxKernelwidth.value()
        self.SigRelay.emit("cm_all_",["filterkernel",filterkernel])
        #self.SigRelay.emit("cm_view_spectra",["position",self.position])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])

    def minPeakwidthupdate(self):
        #print("######################## minPeakwidthupdate reached")
        peakwidth = self.gui.spinBoxminPeakwidth.value()
        #position = self.gui.horizontalScrollBar_view_spectra.value()
        self.SigRelay.emit("cm_all_",["peakwidth",peakwidth])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])
        self.SigRelay.emit("cexex_annotate",["updateGUIelements",0]) #TODO: not necessary ?

    def minPeakDistanceupdate(self):
        #print("######################## minPeakDistanceupdate reached")
        deltaf = self.gui.spinBoxminPeakDistance.value()
        self.SigRelay.emit("cm_all_",["deltaf",deltaf])
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])
        self.SigRelay.emit("cexex_annotate",["updateGUIelements",0]) #TODO: not necessary ?