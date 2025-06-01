"""
Created on Feb 25 2024

#@author: scharfetter_admin
"""

import os
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import yaml
import logging
import time
#from auxiliaries import WAVheader_tools
from auxiliaries import auxiliaries as auxi

class  yaml_editor_m(QObject):
    __slots__ = ["None"]

    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigModelXXX = pyqtSignal()

    #TODO: replace all gui by respective state references if appropriate
    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["sample"] = 0
        self.mdl["_log"] = False
        self.mdl["annotationdir_prefix"] = 'ANN_'
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
        self.logger.debug('Init logger in abstract method reached')

class  yaml_editor_c(QObject):
    """_view method
    """
    __slots__ = ["contvars"]

    SigAny = pyqtSignal()
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)

    def __init__(self, yaml_editor_m): #TODO: remove gui
        super().__init__()
        self.cohiradia_yamlheader_filename = 'dummy' #TODO:future system state
        self.cohiradia_yamltailer_filename = 'dummy' #TODO:future system state
        self.cohiradia_yamlfinal_filename = 'dummy' #TODO:future system state
        viewvars = {}
        #self.set_viewvars(viewvars)
        self.m =  yaml_editor_m.mdl
        self.logger = yaml_editor_m.logger

class  yaml_editor_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["viewvars"]

    #SigAny = pyqtSignal() #TODO: remove after tests
    #SigUpdateGUI = pyqtSignal(object) #TODO: remove after tests
    SigSyncGUIUpdatelist = pyqtSignal(object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)
    
    def __init__(self, gui,  yaml_editor_c,  yaml_editor_m):
        super().__init__()

        self.m =  yaml_editor_m.mdl
        self.DATABLOCKSIZE = 1024*32
        self.gui = gui #gui_state["gui_reference"]#system_state["gui_reference"]
        self.yaml_editor_c = yaml_editor_c
        self.logger = yaml_editor_m.logger
        self.gui.pushButton_Writeyamlheader.setEnabled(False) # activate after completion of the annotation procedure
        self.gui.pushButton_Writeyamlheader.clicked.connect(self.yaml_header_buttonfcn)

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
        if _key.find("cm_yamleditor") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
        if _key.find("cui_yamleditor") == 0:
            _value[0](_value[1])    #TODO TODO: still unclear implementation
        if _key.find("cexex_yamleditor") == 0 or _key.find("cexex_all_") == 0:   
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
                self.logger.debug("call updateGUIelements")
            if  _value[0].find("setWriteyamlButton") == 0:
                self.gui.pushButton_Writeyamlheader.setEnabled(_value[1])
            if  _value[0].find("resizeaction") == 0:
                print("resize action triggered in yaml_editor")
                _value[1].resize_initialize()


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
        self.logger.debug(" yamleditor: updateGUIelements")
        self.read_yaml_header()
        et = time.time()
        self.logger.debug(f"yaml editor segment etime: {et-st} s: update GUI")

    def yaml_header_buttonfcn(self):
        """
        VIEW
        """
        self.write_yaml_header()
        #TODO: write yaml_directory on demand ?

    def read_yaml_header(self):
        """
        VIEW
        ###DESCRIPTION
        :param : dummy
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: none
        :rtype: none
        """

        # if self.flag_ann_completed == False:
        #     return
        nofile_flag = False
        #print('read info from existing yaml-headerfile to editor table')
        self.logger.debug("yamlheader path: %s", self.m["cohiradia_yamlheader_filename"])
        self.gui.pushButton_Writeyamlheader.setEnabled(True)
        try:
            stream = open(self.m["cohiradia_yamlheader_filename"], "r", encoding="utf8")
            self.yamlheader_ = yaml.safe_load(stream)
            stream.close()
            self.gui.tableWidget_YAMLHEADER.item(0, 0).setText(str(self.yamlheader_['content']))
            self.gui.tableWidget_YAMLHEADER.item(1, 0).setText(str(self.yamlheader_['remark']))
            self.gui.tableWidget_YAMLHEADER.item(2, 0).setText(str(self.yamlheader_['band']))
            self.gui.tableWidget_YAMLHEADER.item(3, 0).setText(str(self.yamlheader_['antenna']))
            self.gui.tableWidget_YAMLHEADER.item(4, 0).setText(str(self.yamlheader_['recording-type']))
            prefix = self.yamlheader_['uri'].split('/')[0]
            self.gui.tableWidget_YAMLHEADER.item(12, 0).setText(str(prefix))
        except:
            self.reset_GUI()
            #return False        
        try:
            stream = open(self.m["cohiradia_yamltailer_filename"], "r", encoding="utf8")
            self.yamltailer_ = yaml.safe_load(stream)
            stream.close()
            self.gui.tableWidget_YAMLHEADER.item(5, 0).setText(str(self.yamltailer_['filters']))
            self.gui.tableWidget_YAMLHEADER.item(6, 0).setText(str(self.yamltailer_['preamp-settings']))
            self.gui.tableWidget_YAMLHEADER.item(7, 0).setText(str(self.yamltailer_['location-longitude']))
            self.gui.tableWidget_YAMLHEADER.item(8, 0).setText(str(self.yamltailer_['location-latitude']))
            self.gui.tableWidget_YAMLHEADER.item(9, 0).setText(str(self.yamltailer_['location-qth']))  ## location-qth ist das noch nie verwendete Keyword
            self.gui.tableWidget_YAMLHEADER.item(10, 0).setText(str(self.yamltailer_['location-country']))                
            self.gui.tableWidget_YAMLHEADER.item(11, 0).setText(str(self.yamltailer_['location-city']))
            self.gui.tableWidget_YAMLHEADER.item(12, 0).setText(str(self.yamltailer_['upload-user-fk']))
        except:
            self.reset_GUI()
        #TODO: write yaml_directory on demand only



    def reset_GUI(self):
        self.gui.pushButton_Writeyamlheader.setEnabled(True)
        item = self.gui.tableWidget_YAMLHEADER.item(0, 0)
        item.setText("### Title of the recording as it appears in the COHIRADIA list")
        item = self.gui.tableWidget_YAMLHEADER.item(1, 0)
        item.setText("### Notable details in the spectrum ")
        item = self.gui.tableWidget_YAMLHEADER.item(2, 0)
        item.setText("### LW - MW - SW - others")
        item = self.gui.tableWidget_YAMLHEADER.item(3, 0)
        item.setText("### brand/type of antenna")
        item = self.gui.tableWidget_YAMLHEADER.item(4, 0)
        item.setText("### SDR type or other devices")
        item = self.gui.tableWidget_YAMLHEADER.item(5, 0)
        item.setText("### used filters between antenna and recorder")
        item = self.gui.tableWidget_YAMLHEADER.item(6, 0)
        item.setText("### preamplifiers: type and settings")
        item = self.gui.tableWidget_YAMLHEADER.item(7, 0)
        item.setText("### RX coordinate")
        item = self.gui.tableWidget_YAMLHEADER.item(8, 0)
        item.setText("## RX coordinate")
        item = self.gui.tableWidget_YAMLHEADER.item(9, 0)
        item.setText("### alternative to RX coordinates")
        item = self.gui.tableWidget_YAMLHEADER.item(10, 0)
        item.setText("### RX Country")
        item = self.gui.tableWidget_YAMLHEADER.item(11, 0)
        item.setText("### RX CITY")
        item = self.gui.tableWidget_YAMLHEADER.item(12, 0)
        item.setText("### RM ID if any")
        item = self.gui.tableWidget_YAMLHEADER.item(13, 0)
        item.setText("### Folder name in data directory of COHIRADIA server")
        self.gui.pushButton_Writeyamlheader.setEnabled(False)


    def popup(self,i):
        """
        VIEW or CONTROLLER ??
        
        """
        self.yesno = i.text()

    def  write_yaml_header(self):
        """
        ###DESCRIPTION
        :param : dummy
        :type : none
        :raises [ErrorType]: [ErrorDescription]
        :return: True/False on successful/unsuccesful operation
        :rtype: Boolean
        """
        # treat yaml header
        #if self.flag_ann_completed == False:  #TODO: check if this should only be available if annotation is completed or already before
        #    return
        if len(self.m["cohiradia_yamlheader_filename"]) >=256:
            auxi.standard_errorbox("file path/name is longer than 256 characters, cannot proceed with yaml headers. This may cause significant problems when using the annotator. Please use less deeply nested paths for your files")
            self.reset_GUI() # not essentially necessary 
            #TODO: close file reset GU totally
            #Relay to others ?
            return False

        if os.path.exists(self.m["cohiradia_yamlheader_filename"]) == True:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("overwrite file")
            msg.setInformativeText("you are about to overwrite the existing yaml header file. Do you want to proceed")
            msg.setWindowTitle("FILE OPEN")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.buttonClicked.connect(self.popup)
            msg.exec_()
            if self.yesno == "&No":
                #sys_state.set_status(system_state)
                return False

        if os.path.exists(self.m["cohiradia_yamlheader_filename"]) == False:         #exist yaml file: create from yaml-editor
            self.cohiradia_yamlheader_dirname = self.m["my_dirname"] + '/' + self.m["annotationdir_prefix"] + self.m["my_filename"]
            if os.path.exists(self.cohiradia_yamlheader_dirname) == False:
                os.mkdir(self.cohiradia_yamlheader_dirname)

            
        with open(self.m["cohiradia_yamlheader_filename"], 'w', encoding='utf-8') as f:
            prefix = self.gui.tableWidget_YAMLHEADER.item(13, 0).text()
            uri_string = 'uri: "{}"\n'.format(prefix + '/' + self.m["my_filename"] + '.wav')
            dt_now = self.m["wavheader"]['starttime_dt']
            recdatestr = str(dt_now.strftime('%Y-%m-%d')) + 'T'  + str(dt_now.strftime('%H:%M:%S')) + '+###UTC OFFSET###'  #TODO: automatci UTC offset ?
            recdate = 'recording-date: "{}"\n'.format(recdatestr) ###TODO take from wav-header
            duration = np.round(self.m["wavheader"]['data_nChunkSize']/self.m["wavheader"]['nAvgBytesPerSec'])
            flow = np.round((self.m["wavheader"]["centerfreq"] - self.m["wavheader"]["nSamplesPerSec"]/2)/1000,decimals = 2)
            fhigh = np.round((self.m["wavheader"]["centerfreq"] + self.m["wavheader"]["nSamplesPerSec"]/2)/1000,decimals = 2)
            bandstr = self.gui.tableWidget_YAMLHEADER.item(2, 0).text()
            band = 'band: "{}"\n'.format(bandstr)
            frequnit = 'frequency-unit: "{}"\n'.format('kHz')
            enc = 'encoding: "{}"\n'.format('ci16')
            cfreq = np.round(self.m["wavheader"]["centerfreq"]/1000,decimals = 2)
            bw = self.m["wavheader"]["nSamplesPerSec"]/1000
            antennastr = self.gui.tableWidget_YAMLHEADER.item(3, 0).text()
            antenna = 'antenna: "{}"\n'.format(antennastr)         
            rectypestr = self.gui.tableWidget_YAMLHEADER.item(4, 0).text()
            rectype = 'recording-type: "{}"\n'.format(rectypestr)
            remarkstr = self.gui.tableWidget_YAMLHEADER.item(1, 0).text()
            remark = 'remark: "{}"\n'.format(remarkstr)
            contentstr = self.gui.tableWidget_YAMLHEADER.item(0, 0).text()
            content = 'content: "{}"\n'.format(contentstr)

            f.write('---\n')
            f.write('id: \n')
            f.write(uri_string)
            f.write(recdate)
            f.write('duration: ' + str(duration) + '\n')
            f.write(band)
            f.write(frequnit)
            f.write('frequency-low: ' + str(flow) + '\n')
            f.write('frequency-high: ' + str(fhigh) + '\n')
            f.write('frequency-correction: 0.0' + '\n')
            f.write(enc)
            f.write('center-frequency: ' + str(cfreq) + '\n')
            f.write('bandwidth: ' + str(bw) + '\n')
            f.write(antenna)
            f.write(rectype)
            f.write(remark)
            f.write(content)
            f.write('radio-stations:\n')
            f.close()

        # treat yaml tailer
        #if os.path.exists(self.cohiradia_yamltailer_filename) == False:         #if not exist yaml file: create from yaml-editor
        with open(self.m["cohiradia_yamltailer_filename"], 'w', encoding='utf-8') as f:
            RXlongitudestr = self.gui.tableWidget_YAMLHEADER.item(7, 0).text()
            RXlongitude = 'location-longitude: "{}"\n'.format(RXlongitudestr)     
            RXlatitudestr = self.gui.tableWidget_YAMLHEADER.item(8, 0).text()
            RXlatitude = 'location-latitude: "{}"\n'.format(RXlatitudestr)
            if "\"" in RXlatitudestr or "\"" in RXlongitudestr:
                auxi.standard_errorbox("\' \" \' is not allowed in the yaml file. Please replace by two single quotes, i.e.:  \'\'")
                #sys_state.set_status(system_state)
                return
            RXQTHstr = self.gui.tableWidget_YAMLHEADER.item(9, 0).text()
            RXQTH = 'location-qth: "{}"\n'.format(RXQTHstr)
            RXcountrystr = self.gui.tableWidget_YAMLHEADER.item(10, 0).text()
            RXcountry = 'location-country: "{}"\n'.format(RXcountrystr)
            RXcitystr = self.gui.tableWidget_YAMLHEADER.item(11, 0).text()
            RXcity = 'location-city: "{}"\n'.format(RXcitystr)
            memberstr = self.gui.tableWidget_YAMLHEADER.item(12, 0).text()
            member_ = 'upload-user-fk: "{}"\n'.format(memberstr)
            filtersstr = self.gui.tableWidget_YAMLHEADER.item(5, 0).text()
            filters = 'filters: "{}"\n'.format(filtersstr)
            preampsetstr = self.gui.tableWidget_YAMLHEADER.item(6, 0).text()
            preampset = 'preamp-settings: "{}"\n'.format(preampsetstr)                
            f.write(RXlongitude)
            f.write(RXlatitude)
            f.write(RXQTH)
            f.write(RXcountry)
            f.write(RXcity)
            f.write(member_)
            f.write(filters)
            f.write(preampset)
            f.close()

        if os.path.exists(self.m["cohiradia_metadata_filename"]) == True:
        #TODO: alternative, more strict only after completion of annotation if self.flag_ann_completed = True
            #concatenate files
            filenames = [self.m["cohiradia_yamlheader_filename"], self.m["cohiradia_metadata_filename"] , self.m["cohiradia_yamltailer_filename"]]
            with open(self.m["cohiradia_yamlfinal_filename"], 'w', encoding='utf-8') as outfile:   
                for fname in filenames:
                    with open(fname, 'r', encoding='utf-8') as infile:
                        for line in infile:
                            outfile.write(line)
