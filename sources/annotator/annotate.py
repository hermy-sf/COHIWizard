# -*- coding: utf-8 -*-
"""
Created on Mar 25 2023
#@author: scharfetter_admin
"""
import sys
import time
import os
import datetime as ndatetime
from datetime import datetime
from pathlib import Path, PureWindowsPath
import numpy as np
import matplotlib.pyplot as plt
#from PyQt5.QtCore import QTimer
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
#import matplotlib.pyplot as plt
from scipy import signal as sig
from scipy.ndimage.filters import median_filter
import pandas as pd  #TODO: check, not installed under this name
import yaml
import logging
from auxiliaries import auxiliaries as auxi
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QMutex       #TODO: OBSOLETE
#import system_module as wsys


class statlst_gen_worker(QtCore.QThread):
    __slots__ = ["continue","T","freq","closed","stations_filename","rectime","stichtag","locs_union","annotation","progressvalue","statusfilename","logger"]
    
    SigProgressBar = pyqtSignal()
    SigFinished = pyqtSignal()


    def set_continue(self,_value):
        self.__slots__[0] = _value
    def get_continue(self):  ##TODO: obsolete ??
        return(self.__slots__[0])
    def set_T(self,_value):
        self.__slots__[1] = _value
    def get_T(self):
        return(self.__slots__[1])  
    def set_freq(self,_value):
        self.__slots__[2] = _value
    def get_freq(self):
        return(self.__slots__[2])
    def set_closed(self,_value):
        self.__slots__[3] = _value
    def get_closed(self):
        return(self.__slots__[3])            
    def set_stations_filename(self,_value):
        self.__slots__[4] = _value  
    def get_stations_filename(self):
        return(self.__slots__[4])    
    def set_rectime(self,_value):
        self.__slots__[5] = _value  
    def get_rectime(self):  
        return(self.__slots__[5])    
    def set_stichtag(self,_value):
        self.__slots__[6] = _value  
    def get_stichtag(self):  
        return(self.__slots__[6])    
    def set_locs_union(self,_value):
        self.__slots__[7] = _value  
    def get_locs_union(self):  
        return(self.__slots__[7])    
    def set_annotation(self,_value):
        self.__slots__[8] = _value  
    def get_annotation(self):  
        return(self.__slots__[8])    
    def set_progressvalue(self,_value):
        self.__slots__[9] = _value  
    def get_progressvalue(self):  
        return(self.__slots__[9])
    def set_status_filename(self,_value):
        self.__slots__[10] = _value  
    def get_status_filename(self):  
        return(self.__slots__[10])
    def set_logger(self,_value):
        self.__slots__[11] = _value  
    def get_logger(self):  
        return(self.__slots__[11]) 
    
    def __init__(self, host_window):
        super(statlst_gen_worker, self).__init__()
        self.host = host_window
        self.__slots__[2] = []
        self.__slots__[3] = []
        self.mutex = QtCore.QMutex()
        #self.logger = self.get_logger()

    #@njit
    def stationsloop(self):
        """[Summary]TODO
        reads the 
        :param [ParamName]: [ParamDescription], defaults to [DefaultParamVal]
        :type [ParamName]: [ParamType](, optional)
        :raises [ErrorType]: [ErrorDescription]
        :return: [ReturnDescription]
        :rtype: [ReturnType]
        """

        locs_union = self.get_locs_union()
        rectime = self.get_rectime()
        stichtag = self.get_stichtag()
        annotation = self.get_annotation()
        self.logger = self.get_logger()

        try:
            f = open(self.get_stations_filename(), 'w', encoding='utf-8')
            # Laufe durch alle Peak-Frequenzen des Spektrums mit index ix
            # make this a thread
            #self.logger.debug(f"stationsloop: statslist gen worker: stations_loop reached, write file: {self.get_stations_filename()}, fileref: {f}")
            #print(f"stationsloop: statslist gen worker: stations_loop reached, write file: {self.get_stations_filename()}, fileref: {f}")
            for ix in range(len(locs_union)):
                progress = np.floor(100*ix/len(locs_union))
                self.set_progressvalue(int(progress))
                #self.logger.debug(f"peak index during annotation:{ix}")
                #print(f"peak index during annotation:{ix}")
                f.write('- frequency: "{}"\n'.format(annotation["FREQ"][ix]))
                f.write('  snr: "{}"\n'.format(round(annotation["MSNR"][ix])))
                # locs union enthält nur Frequenzindices, nicht Frequenzen ! ggf. umrechnen !
                # suche für jede freq ix alle MWtabellen-Einträge mit der gleichen Frequenz und sammle die entspr Tabellenindices im array ixf
                ixf = [i for i, x in enumerate(self.__slots__[2]) if np.abs((x - annotation["FREQ"][ix])) < 1e-6]
                _T = self.get_T()
                if np.size(ixf) > 0:
                    #self.logger.debug("stationsloop: npsize>0 reached")
                    #print("stationsloop: npsize>0 reached")
                    # wenn ixf nicht leer setze Landeszähler ix_c auf 0, initialisiere flag cs auf 'none'
                    cs = [] # memory for current country
                    sortedtable = [] #Setze sortedtable zurück
                    yaml_ix = 0
                    for ix2 in ixf:
                        #self.logger.debug(f"stationsloop: annotate worker: ix2: {ix2}, ixf: {ixf}")
                        # für jeden index ix2 in ixf zum Peak ix prüfe ob es den String 'ex ' in der Stationsspalte der MWTabelle gibt
                        if type(_T.station.iloc[ix2]) != str:    
                            curr_station = 'No Name'
                        else:
                            curr_station = _T.station.iloc[ix2]
                        #self.logger.debug(f"stationsloop: Hurraa 1, current station: {curr_station}")
                        if type(_T.programme.iloc[ix2]) != str:
                            #self.logger.debug("stationsloop: typecheck A")
                            curr_programme = 'No Name'
                        else:
                            #self.logger.debug("stationsloop: typecheck B")
                            curr_programme = _T.programme.iloc[ix2]
                            #self.logger.debug("stationsloop: typecheck B")
                        #self.logger.debug(f"stationsloop: Hurraa 1, current programme: {curr_programme}")
                        if type(_T.tx_site.iloc[ix2]) != str:
                            curr_tx_site = 'No Name'
                        else:
                            curr_tx_site = _T.tx_site.iloc[ix2]
                        #self.logger.debug(f"stationsloop: Hurraa 1, current tx site: {curr_tx_site}")
                        if curr_station.find("ex ") == 0:
                            stdcheck = True
                        else:
                            stdcheck = False
                        #self.logger.debug(f"stationsloop: Hurraa 1, stdcheck: {stdcheck}")
                        # für jeden index ix2 in ixf zum Peak ix prüfe ob es den String 'INACTI' in der Stationsspalte der MWTabelle gibt
                        inactcheck = 'INACTI' in curr_station
                        #a = inactcheck + curr_station
                        # logisches label falls ()'ex ' oder 'INACT') und recording-time > Stichtag der MWTabellen-Erstellung
                        # kennzeichnet, wenn ein Sender sicher zum Zeitpunkt der Aufnahme geschlossen war
                        auto_closedlabel = (stdcheck or inactcheck) and (rectime >= stichtag)
                        #print(f"potential: freq: {str(annotation['FREQ'][ix])}; curr_station {curr_station} ; ## stdcheck: {str(stdcheck)} ; ## auto_closedlabel: {str(auto_closedlabel)} ;## days from stichtag: {str((self.__slots__[3][ix2] - rectime).days)}")
                        #self.logger.debug("dummy")
                        #self.logger.debug(f"potential: freq: {str(annotation['FREQ'][ix])}; curr_station {curr_station} ; ## stdcheck: {str(stdcheck)} ; ## auto_closedlabel: {str(auto_closedlabel)} ;## days from stichtag: {str((self.__slots__[3][ix2] - rectime).days)}")
                        # self.logger.debug(curr_station + ";## stcheck : " + str(stdcheck) + "; ##autoclosedlabel: " + str(auto_closedlabel) + ";## daydiff :" + str((self.__slots__[3][ix2] - rectime).days))
                        if not ((self.__slots__[3][ix2] - rectime).days < 0 or auto_closedlabel):
                            #print(f"accepted: curr_station {curr_station} ; ## stdcheck: {str(stdcheck)} ; ## auto_closedlabel: {str(auto_closedlabel)} ;## days from stichtag: {str((self.__slots__[3][ix2] - rectime).days)}")                        #self.logger.debug(f"stationsloop: auto_closedlabel: {auto_closedlabel}")
                            #self.logger.debug(f"potential: freq: {str(annotation['FREQ'][ix])}; curr_station {curr_station} ; ## stdcheck: {str(stdcheck)} ; ## auto_closedlabel: {str(auto_closedlabel)} ;## days from stichtag: {str((self.__slots__[3][ix2] - rectime).days)}")
                            #self.logger.debug("ifnot case Hurraa 2")
                            #wenn NICHT (geschlossen oder recording-time >= explizite Schließzeit in der Spalte closed) --> Sender ist Kandidat
                            # Progeamm und Station aus MWTabelle übernehmen
                            # Land country aus MWTabelle übernehmen
                            station = '{}{}'.format(curr_programme, curr_station)
                            tx_site = curr_tx_site
                            country = self.__slots__[1].country.iloc[ix2]
                            if country in cs:  # falls cs bereits das aktuelle Land innerhalb der aktuellen Liste ixf der Einträge zu Frequenz ix beinhaltet 
                                cix = [i for i,x in enumerate(cs) if x == country][0]
                                sortedtable[cix]['station' + str(cix)] += station + '; '
                                sortedtable[cix]['tx_site' + str(cix)] += tx_site + '; '
                            else:
                            # Trag ins dictionary sortedtable die Felder Station, Tx-site und country 
                            # als neuen Block ein
                                sortedtable.append({'station' + str(yaml_ix): station + '; ',
                                                'tx_site' + str(yaml_ix): tx_site + '; ',
                                                'country' + str(yaml_ix): country})
                                cs.append(country)  # memorize the entered country
                                yaml_ix += 1
                    # for this ixf (i.e. this peak frequency) write all entries of the sorted table
                            #self.logger.debug("stationsloop: end of ifnot case quest reached")
                    #self.logger.debug(f"stationsloop: annotate after first loop: ix2: {ix2}")
                    #print(f"stationsloop: annotate after first loop: ix2: {ix2}")
                        else:
                            #self.logger.debug(f"rejected: freq: {str(annotation['FREQ'][ix])}; curr_station {curr_station} ; ## stdcheck: {str(stdcheck)} ; ## auto_closedlabel: {str(auto_closedlabel)} ;## days from closing: {str((self.__slots__[3][ix2] - rectime).days)}")
                            #self.logger.debug(f"diffcheck rectime: {str(rectime)}, stichtag: {stichtag}, slots: {self.__slots__[3][ix2]}")
                            pass
                    ix2 = -1
                    for ix2 in range(len(sortedtable)):
                        
                        country_string = '  country' +str(ix2) + ': "{}"\n'.format(sortedtable[ix2]['country' + str(ix2)])
                        programme_string = '  programme' +str(ix2) + ': "{}"\n'.format(sortedtable[ix2]['station' + str(ix2)])
                        tx_site_string = '  tx-site' +str(ix2) + ': "{}"\n'.format(sortedtable[ix2]['tx_site' + str(ix2)])
                        f.write(country_string)
                        f.write(programme_string)
                        f.write(tx_site_string)
                        time.sleep(0.01)

                    # write dummy entry for own editing
                    dum_cstr = 'OTHER COUNTRY, Please enter manually'
                    dum_pstr = 'OTHER STATION, Please enter manually'
                    dum_txstr = 'OTHER TX SITE, Please enter manually'
                    ix2 = ix2 + 1
                    country_string = '  country' +str(ix2) + ': "{}"\n'.format(dum_cstr)
                    programme_string = '  programme' +str(ix2) + ': "{}"\n'.format(dum_pstr)
                    tx_site_string = '  tx-site' +str(ix2) + ': "{}"\n'.format(dum_txstr)
                    f.write(country_string)
                    f.write(programme_string)
                    f.write(tx_site_string)
                    time.sleep(0.01)
                else:
                    f.write('  country0: "not identified"\n')
                    f.write('  programme0: "not identified"\n')
                    f.write('  tx-site0: "not identified"\n')
        except:
            #self.logging.info("annotation file not yet existent")
            print("annotation file not yet existent")
            return False

        status = {}
        status["freqindex"] = 0
        status["annotated"] = False
        stream = open(self.get_status_filename(), "w")
        yaml.dump(status, stream)
        stream.close()
        self.set_continue(False)
        self.set_progressvalue(int(progress))
        self.SigProgressBar.emit()
        # wait for confirmation from Progress bar updating
        while self.get_continue() == False:
            time.sleep(0.001)
        self.SigFinished.emit()

class autoscan_worker(QtCore.QThread):
    """worker for the thread which performs the automatic scanning through the spectrum for finding spectral peaks and their SNR

    :Signalling : 

    * SigScandeactivate: inactivate SCAN button

    * SigUpdateUnions: calls annotate_c.annupdateunions to prepare info for method ann_stations:

    * SigUpdateGUI: update GUI

    * SigProgressBar: advance progressbar via progressvalue - setter/getter

    * SigStatustable: publish additional status information

    * SigPlotdata: plot spectral data for diagnostic purposes if activated in GUI

    * SigAnnSpectrum (data): ann_spectrum(self,data): calls ann_spectrum to generate a single spectrum from complex datasignals, calculates peak info and conveys this info to [annotate_c.locs_union,annotate_c.freq_union] for further processing in stations list assignment

    * SigError (object): so far unused

    * SigAnnotation: convey info to annotate_c: annotate_c.annotation = autoscan_worker.get_annotation(), trigger continuation of worker: autoscan_worker.set_continue(True)

    * SigFinished: return to thread control, --> finish thread
    """
    __slots__ = ["GUI_parameters", "continue","pdata","progressvalue","horzscal",
             "filepath","readoffset","wavheader","datablocksize","baselineoffset",
             "unions","annotation_filename","annotation","errormsg", "datasnaps", "round_digits", "BW_peaklock"]

    SigUpdateUnions = pyqtSignal()
    SigUpdateGUI = pyqtSignal()
    SigScandeactivate = pyqtSignal()
    SigFinished = pyqtSignal()
    SigProgressBar = pyqtSignal()
    SigStatustable = pyqtSignal()
    SigPlotdata = pyqtSignal()
    SigAnnSpectrum = pyqtSignal(object)
    SigError = pyqtSignal(object)
    SigAnnotation = pyqtSignal()


    def __init__(self, host_window):
        super(autoscan_worker, self).__init__()
        self.host = host_window
        self.locs_union = []
        self.freq_union = []
        self.peakvals_union = []
        self.slot_0 = []
        self.slot_1 = [False]
        self.slot_2 = {}

    def set_GUI_parameters(self,_value):
        """
        __slots__[0] has entries: NUMSNAPS, prominence
        """
        self.__slots__[0] = _value
    def get_GUI_parameters(self):
        return(self.__slots__[0])
    def set_continue(self,_value):
        self.__slots__[1] = _value
    def get_continue(self):
        return(self.__slots__[1])
    def set_pdata(self,_value):
        self.__slots__[2] = _value
    def get_pdata(self):
        return(self.__slots__[2])
    def set_progressvalue(self,_value):
        self.__slots__[3] = _value
    def get_progressvalue(self):
        return(self.__slots__[3])
    def set_horzscal(self,_value):
        self.__slots__[4] = _value
    def get_horzscal(self):
        return(self.__slots__[4])
    def set_filepath(self,_value):
        self.__slots__[5] = _value
    def get_filepath(self):
        return(self.__slots__[5])
    def set_readoffset(self,_value):
        self.__slots__[6] = _value
    def get_readoffset(self):
        return(self.__slots__[6])
    def set_wavheader(self,_value):
        self.__slots__[7] = _value
    def get_wavheader(self):
        return(self.__slots__[7])
    def set_datablocksize(self,_value):
        self.__slots__[8] = _value
    def get_datablocksize(self):
        return(self.__slots__[8])
    def set_baselineoffset(self,_value):
        self.__slots__[9] = _value
    def get_baselineoffset(self):
        return(self.__slots__[9])
    def set_unions(self,_value):
        self.__slots__[10] = _value
    def get_unions(self):
        return(self.__slots__[10])
    def set_annotation_filename(self,_value):
        self.__slots__[11] = _value
    def get_annotation_filename(self):
        return(self.__slots__[11])
    def set_annotation(self,_value):
        self.__slots__[12] = _value
    def get_annotation(self):
        return(self.__slots__[12])
    def set_errormsg(self,_value):
        self.__slots__[13] = _value
    def get_errormsg(self):
        return(self.__slots__[13])
    def set_datasnaps(self,_value):
        self.__slots__[14] = _value
    def get_datasnaps(self):
        return(self.__slots__[14])
    def set_round_digits(self,_value):
        self.__slots__[15] = _value
    def get_round_digits(self):
        return(self.__slots__[15])
    def set_BW_peaklock(self,_value): #currently unused
        self.__slots__[16] = _value
    def get_BW_peaklock(self):
        return(self.__slots__[16])

    #@njit
    def autoscan_fun(self):
        """
        scan through the recording over self.NUMSNAPS time points
        for each time point calculate mean peak info and SNR and optionally plot spectrum 
        send progressbar-Signal for updating progressbar
        identifies vectors locs_union of peak indices and freq_union of corresponding peak frequencies 
        signals those vectors to [annotate_c.locs_union,annotate_c.freq_union] for further processing in stations list assignment --> TODO check consequences.
        
        Now 2 tasks are performed: 

            1. assign found peaks to standard frequencies in a grid of allowed values (rounded to within a certain grid resolution)

            2. averaging of peak data corresponding to individual grid frequencies over NUMSnaps points. 
            Small jitter of the peak frequencies over time must be filtered before assigning them to a grid frequency
            i.e. peaks within a certain bandwidth around the grid frequencies are identified and treated as identical

        SNR values are the calculated from all values at 'identical' grid frequencies

        finally write corresponding filtered FREQ and SNR information to intermediate yaml file snrannotation.yaml

        :param : none

        :raises : none

        :returns : none
        """
        round_digits = self.get_round_digits()
        #BW_peaklock = self.get_BW_peaklock()

        locs_union = []
        freq_union = []
        self.SigUpdateGUI.emit()
        # inactiavate SCAN button and prepare GUI for next steps
        self.SigScandeactivate.emit()
        self.NUMSNAPS = self.get_GUI_parameters()[0]
        self.prominence = self.get_GUI_parameters()[1]
        ann_master = [dict() for x in range(self.NUMSNAPS)]
        #print(f"annotate autoscan fu reached, GUI params: {self.get_GUI_parameters()}")
        wavheader = self.get_wavheader()
        pscale = wavheader['nBlockAlign']
        BPS = wavheader["nBitsPerSample"]
        for ix in range(self.NUMSNAPS):
            position = int(np.floor(ix/self.NUMSNAPS*100))
            self.set_progressvalue(position)
            self.set_continue(False)
            self.SigProgressBar.emit()
            # wait for confirmation from Progress bar updating
            #print(f"annotate autoscan fu reached, position: {position}")
            while self.get_continue() == False:
                #print("waitloop")
                time.sleep(0.01)
            #print("post waitloop")
            file_stats = os.stat(self.get_filepath()) #TODO: move out of loop
            corrchunksize = min(wavheader['data_nChunkSize'],file_stats.st_size - self.get_readoffset()) #TODO: drag out of the loop
            file_readix = int(np.floor(pscale*np.round(corrchunksize*position/pscale/100)))
            #print(f'pre readsegment: fp: {self.get_filepath()},p: {position},ro: {self.get_readoffset()}, dbs: {self.get_datablocksize()},bps: {BPS},whfmttg: {wavheader["wFormatTag"]}')
            ret = auxi.readsegment_new(self,self.get_filepath(),file_readix,self.get_readoffset(), self.get_datablocksize(),BPS,BPS,wavheader["wFormatTag"])#TODO: replace by slots communication
            data = ret["data"]
            if 2*ret["size"]/wavheader["nBlockAlign"] < self.get_datablocksize():
                print(f"size false condition: retsize: {ret['size']}, bBlockAlign: {wavheader['nBlockAlign']}, datablocksize: {self.get_datablocksize()}")
                self.SigError.emit("wavheader error")
                self.SigFinished.emit()
                return False
            self.set_continue(False)
            self.SigAnnSpectrum.emit(data)
            #print("sleep before continue 1")
            while self.get_continue() == False:
                time.sleep(0.001)
            # start spectrumn analysis and get spectral as well as peak data:        
            # pdata = {"datax": datax, "datay": datay, "datay_filt": datay_filt,"peaklocs": peaklocs, "peakprops": peakprops, "databasel": databasel}
            self.SigAnnSpectrum.emit(data)  #TODO check why Signal needs to be sent twice
            pdata = self.get_pdata()
            self.set_continue(False)
            #optional plotting if activated
            self.SigPlotdata.emit()
            # wait until plot has been carried out
            while self.get_continue() == False:
                time.sleep(0.001)
            ann_master[ix]["FREQ"] = pdata["datax"] 
            ann_master[ix]["PKS"] = pdata["peaklocs"]
            peaklocs = pdata["peaklocs"]
            #datay = pdata["datay"]
            basel = pdata["databasel"] + self.get_baselineoffset()
            ann_master[ix]["SNR"] = pdata["datay"][peaklocs] - basel[peaklocs]
            ann_master[ix]["PEAKVALS"] = pdata["datay"][peaklocs]
            #create union of all peaklocs found so far (collect all peaks occurring at least once in the series of NSnaps timepoints)
            locs_union = np.union1d(locs_union, ann_master[ix]["PKS"])

            #collect all frequencies with round_digits resolution (round_digits = # of digits after the kHz-comma)
            freq_union = np.union1d(freq_union, np.round(ann_master[ix]["FREQ"][ann_master[ix]["PKS"]],round_digits))
        # purge self.locs.union and remove elements the frequencies of which are within X kHz span 
        # print(f"length freq_union: {len(freq_union)}, length locs_union: {len(locs_union)}")
        self.set_unions([locs_union,freq_union])
        self.SigUpdateUnions.emit() #TODO: what is this for ?
        #This signal calls annotate_c.annupdateunions to prepare info for method ann_stations: [annotate_c.locs_union,annotate_c.freq_union] = annotate_c.autoscaninst.get_unions()
        #
        meansnr = np.zeros(len(locs_union))
        meanpeakval = np.zeros(len(locs_union))
        minsnr = 1000*np.ones(len(locs_union))
        maxsnr = -1000*np.ones(len(locs_union))
        reannot = {}
        datasnaps = {}
        datasnaps["PEAKVALS"] = []
        datasnaps["SNR"] = []

        for ix in range(self.NUMSNAPS):
            # find indices of current LOCS in the unified LOC vector locs_union and assign index to a reann array where each identified peak is assigned to the correct locs union location
            sharedvals, ix_un, ix_ann = np.intersect1d(locs_union, ann_master[ix]["PKS"], return_indices=True)
            # write current SNR to the corresponding places of the self.reannot matrix
            reannot["SNR"] = np.zeros(len(locs_union))
            reannot["SNR"][ix_un] = ann_master[ix]["SNR"][ix_ann]
            reannot["PEAKVALS"] = np.zeros(len(locs_union))
            reannot["PEAKVALS"][ix_un] = ann_master[ix]["PEAKVALS"][ix_ann]
            datasnaps["PEAKVALS"].append(reannot["PEAKVALS"])
            datasnaps["SNR"].append(reannot["SNR"])
            #Global Statistics, without consideration whether some peaks vanish or
            #appear when running through all values of ix
            meansnr = meansnr + reannot["SNR"]
            meanpeakval = meanpeakval + reannot["PEAKVALS"]
            #min and max SNR data are currently not being used.
            minsnr = np.minimum(minsnr, reannot["SNR"])
            maxsnr = np.maximum(maxsnr, reannot["SNR"])
            #print("annotate worker findpeak")
        
        #round all found peak frequencies to within a certain resolution and create a vector of unique rounded frequencies (each value occurs only once !)   
        uniquefreqs = pd.unique(np.round(freq_union/1000,round_digits))
        # contract all 
        #BW_peaklock = self.get_BW_peaklock()  ##TODO: make this collection BW flexible; might be larger than the peak identification resolution
        #TODO TODO TODO: implement GUI element for chosing BW_round_digits with default value = round_digits
        #(1): implement GUI element (2) define element readout slot (3) pass value from worker caller to worker via getter
        #TODO TODO TODO: find other BW-search algorithm
        BW_round_digits = round_digits
        xyi, x_ix, y_ix = np.intersect1d(uniquefreqs, np.round(freq_union/1000,BW_round_digits), return_indices=True)
        #x_ix: kompakter Vektor [0 1 2 3 4]
        #y_ix: disperser Vektor mit z.B. [0,2,4,5,6]
        #contract all columns of the matrix between subsequent col indices in y_ix
        #print(f"intersect products ix: {x_ix}, iy: {y_ix}")
        _res1 = np.zeros((np.shape(datasnaps["PEAKVALS"])[0],len(x_ix)))
        _res2 = _res1
        A = np.array(datasnaps["SNR"])
        B = np.array(datasnaps["PEAKVALS"])
        #print(f"shape of _res: {np.shape(_res)}")
        #print(f"A: {A}")
        #sum up all columns within the selected bandwidth
        for ix in x_ix:
            if ix < len(x_ix)-1:
                #print("########################################")
                #print(f"ix: {ix}, section: {A[:,y_ix[ix]:y_ix[ix+1]]}")
                _res1[:,ix] = (A[:,y_ix[ix]:y_ix[ix+1]]).sum(axis=1)#/(y_ix[ix+1]-y_ix[ix])
                _res2[:,ix] = (B[:,y_ix[ix]:y_ix[ix+1]]).sum(axis=1)#/(y_ix[ix+1]-y_ix[ix])
                #print(f"_res[:,ix]: {_res[:,ix]}, _res: {_res}")
        datasnaps["SNR_contracted"] = _res1
        datasnaps["PEAKVALS_contracted"] = _res2
        #print(f"length reannot[PEAKVALS]: {len(reannot['PEAKVALS'])}")
        self.set_datasnaps(datasnaps)
        # collect cumulative info in a dictionary and write the info to the annotation yaml file 
        ann_dict = {}
        ann_dict["MSNR"] = meansnr/self.NUMSNAPS
        ann_dict["PEAKVALS"] = meanpeakval/self.NUMSNAPS
        ann_dict["FREQ"] = np.round(freq_union/1000,round_digits) # signifikante Stellen
        #print(f"length ann_dict[FREQ]: {len(ann_dict['FREQ'])}")
        yamldata = [dict() for x in range(len(ann_dict["FREQ"]))]

        for ix in range(len(ann_dict["FREQ"])):
            yamldata[ix]["FREQ:"] = str(ann_dict["FREQ"][ix])
            yamldata[ix]["SNR:"] = str(np.floor(ann_dict["MSNR"][ix]))
        #TODO: check if file exists
        try:
            stream = open(self.get_annotation_filename(), "w")
            yaml.dump(yamldata, stream)
            stream.close()
        except:
            print("cannot write annotation yaml")
            pass
        self.set_annotation(ann_dict)
        self.SigAnnotation.emit()
        self.SigStatustable.emit()
        self.set_continue(False)
        while self.get_continue() == False:
                time.sleep(0.001)
        self.SigFinished.emit()
        print("++    leave autoscan thread")


class annotate_m(QObject):
    __slots__ = ["None"]
    SigModelXXX = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Constants
        self.CONST_SAMPLE = 0 # sample constant
        self.mdl = {}
        self.mdl["sample"] = 0
        self.mdl["_log"] = False
        self.mdl["baselineoffset"] = 0
        self.mdl["round_digits"] = 0
        self.mdl["export_xlsx"] = False
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


class annotate_c(QObject):
    """_view method
    """
    __slots__ = ["contvars"]

    SigAny = pyqtSignal()
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)

    def __init__(self, annotate_m): #TODO: remove gui
        super().__init__()
        self.m = annotate_m.mdl
        self.logger = annotate_m.logger
        self.DATABLOCKSIZE = 1024*32
        self.m["deltaf"] = 5000 #minimum peak distance in Hz for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.m["peakwidth"] = 10 # minimum peak width in Hz for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.m["prominence"] = 15 # minimum peak prominence in dB above baseline for peak detector #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.m["filterkernel"] = 2 # length of the moving median filter kernel in % of the spectral span #TODO:occurs in ann-module; values also used in spectrum view; ; must be shifted to the respective modules in future
        self.STICHTAG = datetime(2023,2,25,0,0,0)
        self.m["scanerror"] = False

    def autoscan(self):
        """
        slot function for Button 'Scan': configures thread for scanning the spectrum and annotating the peaks and SNR values
        starts thread with autoscan_worker with autoscan_worker.autoscan_fun
        On receiving the SigFinished Signal from worker thread --> terminate thread and trigger next annotation task: interactive stations annotation
        via self.ann_stations()

        :params:  none

        :exceptions: none
        
        :returns: none
        """
        #create directory for yaml file
        self.logger.debug("autoscan reached")
        if os.path.exists(self.m["cohiradia_yamlheader_filename"]) == False:         #exist yaml file: create from yaml-editor
            self.m["cohiradia_yamlheader_dirname"] = self.m["my_dirname"] + '/' + self.m["annotationdir_prefix"] + self.m["my_filename"]
            if os.path.exists(self.m["cohiradia_yamlheader_dirname"]) == False:
                os.mkdir(self.m["cohiradia_yamlheader_dirname"])

        #intantiate scanning thread
        self.autoscanthread = QThread()
        self.autoscaninst = autoscan_worker(self)
        self.autoscaninst.moveToThread(self.autoscanthread)
        self.SigRelay.emit("cexex_annotate",["getGUIvalues",0])  
        time.sleep(0.001)
        self.autoscaninst.set_GUI_parameters([self.m["NumScan"],self.m["minSNR"],[]])
        self.autoscaninst.set_filepath(self.m["f1"])
        self.autoscaninst.set_readoffset(self.m["readoffset"])
        self.autoscaninst.set_wavheader(self.m["wavheader"])
        self.autoscaninst.set_datablocksize(self.DATABLOCKSIZE)
        self.autoscaninst.set_baselineoffset(self.m["baselineoffset"])
        self.autoscaninst.set_round_digits(self.m["round_digits"])
        #self.autoscaninst.set_BW_peaklock(self.m["BW_peaklock"])
        self.autoscaninst.set_annotation_filename(self.m["annotation_filename"])
        self.autoscanthread.started.connect(self.autoscaninst.autoscan_fun)
        self.autoscaninst.SigError.connect(self.errorsigtoannstations)
        self.autoscaninst.SigFinished.connect(self.ann_stations)
        self.autoscaninst.SigFinished.connect(self.autoscanthread.quit)
        self.autoscaninst.SigFinished.connect(self.autoscaninst.deleteLater)
        self.autoscanthread.finished.connect(self.autoscanthread.deleteLater)
        self.autoscaninst.SigUpdateUnions.connect(self.annupdateunions)
        self.autoscaninst.SigAnnSpectrum.connect(self.annspectrumhandler)
        self.autoscaninst.SigAnnotation.connect(self.annotationset)
        # connect autoscaninst signals with annotate_v methods (GUI updates, displays ...)
        self.SigRelay.emit("cexex_annotate",["connect_autoscan",0])
        time.sleep(0.001)
        self.autoscanthread.start()
        if self.autoscanthread.isRunning():
            self.autoscanthreadActive = True
            #print("scanthread started")

    def errorsigtoannstations(self):
        self.m["scanerror"] = True

    def annotationset(self):
        self.annotation = self.autoscaninst.get_annotation()
        self.autoscaninst.set_continue(True)

    def annupdateunions(self):
        #print("annupdate unions")
        #[self.locs_union,self.freq_union, self.peakvals_union] = self.autoscaninst.get_unions()
        [self.locs_union,self.freq_union] = self.autoscaninst.get_unions()

    def annspectrumhandler(self,data):
        #print("annspectrumhandler reached")
        pdata = self.ann_spectrum(data)
        self.autoscaninst.set_pdata(pdata)
        self.autoscaninst.set_continue(True)
        pass

    def ann_spectrum(self,data):
        """ generate a single spectrum from complex data
        scale x-axis as frequencies in the recorded AM band
        scale y-axis in dB
        calculate baseline basel from moving median filtering
        find spectral peaks (= transmitters) and calculate the corresponding properties
        requires the following properties to exist: self.DATABLOCKSIZE

        :param self: An instance of the class containing attributes such as header information and filtering parameters.
        :type self: object
        :param dummy: A dummy variable not used in the function.
        :type dummy: any
        :param data: A numpy array containing the complex data IQ data read from wav file
        :type data: numpy.ndarray of float32, even entries = real odd entries = imaginary part of the IQ signal
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
        # extract imaginary and real parts from complex data 
        realindex = np.arange(0,self.DATABLOCKSIZE,2)
        imagindex = np.arange(1,self.DATABLOCKSIZE,2)
        #calculate spectrum and shift/rescale appropriately
        spr = np.abs(np.fft.fft((data[realindex]+1j*data[imagindex])))
        N = len(spr)
        spr = np.fft.fftshift(spr)/N
        flo = self.m["wavheader"]['centerfreq'] - self.m["wavheader"]['nSamplesPerSec']/2#TODO: drag somehwere outside ?
        fup = self.m["wavheader"]['centerfreq'] + self.m["wavheader"]['nSamplesPerSec']/2#TODO: drag somehwere outside ?
        freq0 = np.linspace(0,self.m["wavheader"]['nSamplesPerSec'],N)#TODO: drag somehwere outside ?
        freq = freq0 + flo
        datax = freq
        datay = 20*np.log10(spr)
        # filter out all data below the baseline; baseline = moving median
        # filter kernel is self.m["filterkernel"] % of the spectral span
        datay_filt = datay
        kernel_length = int(N*self.m["filterkernel"]/100)
        # kernel length must be odd integer
        if (kernel_length % 2) == 0:
            kernel_length += 1
        
        databasel = median_filter(datay,kernel_length, mode = 'constant')
        datay_filt[datay_filt < databasel] = databasel[datay_filt < databasel]
        # find all peaks which are self.prominence dB above baseline and 
        # have a min distance of self.["DELTAF"] and a min width of self.["peakwidth"]
        dist = np.floor(np.maximum(self.m["deltaf"]/self.m["wavheader"]['nSamplesPerSec']*N,100)) # drag somewhere outside ?
        
        wd = np.floor(self.m["peakwidth"]/self.m["wavheader"]['nSamplesPerSec']*N) # drag somewhere outside ?

        peaklocs, peakprops = sig.find_peaks(datay_filt,
                        prominence=(self.m["prominence"],None), distance=dist, width = wd)
        ret = {"datax": datax, "datay": datay, "datay_filt": datay_filt,
               "peaklocs": peaklocs, "peakprops": peakprops, "databasel": databasel}
        return ret

    #@auxi.waiting_effect
    def mwlistread(self,MWlistname):
        T = pd.read_excel(MWlistname)
        return T

    def ann_stations(self):
        """read MWLIST and collect stations info in dictionary, initialize yamlheader, starts statlst_gen_worker for stationslist generation, 
        finally calls interactive_station_select()
        depends on: statlst_gen_worker, Progressbarupdate(), csan_completed(), write_yaml_header(), interactive_station_select(), annotation_completed()

        :param: none
        :type: none
        :raises: [ErrorType]: [ErrorDescription]
        :return: flag False on unsuccessful execution if stations list or status file non-existent
        :rtype: Boolean
        """

        time.sleep(0.1)
        if self.m["scanerror"]:
            auxi.standard_errorbox("Error during scan procedure, maybe wav header of file is corrupt or wrong entire (chunksize ?)")
            return False
        self.stations_filename = self.m["annotationpath"] + '/stations_list.yaml'

        if self.m["export_xlsx"]:
            #write xls file with peak traces
            datasnaps = self.autoscaninst.get_datasnaps()
            uniquefreqs = pd.unique(np.round(self.freq_union/1000,self.m["round_digits"]))
            self.freq_union = uniquefreqs
            #A = np.array(datasnaps["SNR_contracted"])
            A = np.array(datasnaps["PEAKVALS_contracted"])
            B = {}
            for ix in range(len(self.freq_union)):
                B[str(np.round(self.freq_union[ix],self.m["round_digits"]))] = A[:,ix]
            C = np.zeros((1,len(self.freq_union)))
            C[0,:] = np.round(self.freq_union,self.m["round_digits"])
            B = np.concatenate((C,A))  #ERROR in exe occurs here in concatenatealong dimension 1 the array at index 0 has size 1 and the array at index 1 has size 8
            duration = (self.m["wavheader"]["stoptime_dt"] - self.m["wavheader"]["starttime_dt"]).seconds
            deltat = duration/np.shape(B)[0]
            xax = np.zeros((np.shape(B)[0],1))
            xax[1:,0] = np.linspace(0,duration,num = np.shape(B)[0]-1)
            D = np.concatenate((xax,B),1)
            try:
                plt.cla()
                plt.clf()
            except:
                pass
            plt.plot(xax[1:],B[1:,:])
            plt.legend((np.round(self.freq_union,self.m["round_digits"])).astype('str'), loc="lower right")
            plt.xlabel("time (s)")
            plt.ylabel("peak value (dB)")
            plt.title("time evolution of identified carriers, frequencies are in kHz")
            plt.show()
            df = pd.DataFrame(D)
            peaktracexls_filename = self.m["annotationpath"] + "/peaktrace.xlsx"
            try:
                df.to_excel(excel_writer = peaktracexls_filename)
            except:
                print("annotate: no access to test peakamplitude excel file")
                pass
        if os.path.exists(self.stations_filename) == False:
            # read Annotation_basis table from mwlist.org   
            self.SigRelay.emit("cexex_annotate",["annotatestatusdisplay","Status: read MWList table for annotation"])
            filters ="MWList files (*.xlsx)"
            selected_filter = "MWList files (*.xlsx)"
            filename=""
            MWlistpath = Path(self.m["standardpath"] + "/annotator/ressources")
            if self.m["ismetadata"] == False:
                filename =  QtWidgets.QFileDialog.getOpenFileName(self.m["QTMAINWINDOWparent"],
                                                                    "Open new stations list (e.g. MWList) file"
                                                                    , MWlistpath.__str__(), filters, selected_filter)
            else:
                #print('open file with last path')
                if "last_MWlist" in self.m["metadata"]:
                    filters =  "MWList files (*.xlsx)"
                    selected_filter = filters
                    filename =  QtWidgets.QFileDialog.getOpenFileName(self.m["QTMAINWINDOWparent"],
                                                                    "Open stations list (e.g. MWList) file (last used is selected)"
                                                                    ,self.m["metadata"]["last_MWlist"] , filters, selected_filter)
                else:
                    filename =  QtWidgets.QFileDialog.getOpenFileName(self.m["QTMAINWINDOWparent"],
                                                    "Open new stations list (e.g. MWList) file"
                                                    , MWlistpath.__str__(), filters, selected_filter)
            if len(filename[0]) == 0:
                return False
            list_selection = filename[0]   
            self.m["metadata"]["last_MWlist"] = list_selection

            stream = open("config_wizard.yaml", "w")
            yaml.dump(self.m["metadata"], stream)
            stream.close()
            MWlistname = list_selection
            self.logger.debug("read MWlist file")
            time.sleep(0.01)
            T = self.mwlistread(MWlistname)
            # @auxi.waiting_effect
            # T = pd.read_excel(MWlistname)

            self.logger.debug("generate annotation basis")
            self.SigRelay.emit("cexex_annotate",["annotatestatusdisplay","Status: Generate annotation basis"])

            freq = [] # column with all tabulated frequencies in MWtabelle
            closed = [] # column with dates of corresponding closure times if available (if element in table is type datetime)
            for ix in range(len(T)):
                testclosed = T.closed.iloc[ix]
                dummytime = datetime(5000,1,1,1,1,1)
                if type(testclosed) == datetime:
                    closed.append(datetime.strptime(str(testclosed), '%Y-%m-%d %H:%M:%S'))
                    #stations which are not closed must have dummy entries where no datetime
                else:
                    closed.append(datetime.strptime(str(dummytime), '%Y-%m-%d %H:%M:%S'))
                freq.append(float(T.freq.iloc[ix]))
            self.SigRelay.emit("cexex_annotate",["annotatestatusdisplay","Status: annotate peaks and write stations list to yaml file"])
            #start generation of stations list as a separate thread
            starttime = self.m["wavheader"]['starttime']
            stoptime = self.m["wavheader"]['stoptime']
            self.rectime = datetime(starttime[0],starttime[1],starttime[3],starttime[4],starttime[5],starttime[6])
            self.recstop = datetime(stoptime[0],stoptime[1],stoptime[3],stoptime[4],stoptime[5],stoptime[6]) #TODO: seems to be unused
            #self.m["scan_completed_ref"]()
            self.statlst_genthread = QThread()
            self.statlst_geninst = statlst_gen_worker(self)
            self.statlst_geninst.moveToThread(self.statlst_genthread)
            self.statlst_geninst.set_continue(True)
            self.statlst_geninst.set_T(T)
            self.statlst_geninst.set_freq(freq)
            self.statlst_geninst.set_closed(closed)
            self.statlst_geninst.set_stations_filename(self.stations_filename)
            self.statlst_geninst.set_locs_union(self.locs_union)
            self.statlst_geninst.set_rectime(self.rectime)
            self.statlst_geninst.set_stichtag(self.STICHTAG)
            self.statlst_geninst.set_annotation(self.annotation)
            self.statlst_geninst.set_logger(self.logger)
            self.statlst_geninst.set_status_filename(self.m["status_filename"])
            self.statlst_genthread.started.connect(self.statlst_geninst.stationsloop)
            self.statlst_geninst.SigProgressBar.connect(self.m["Progressbarupdate2_ref"])  #TODO: unsaubere Lösung; controller funs should not access GUI functions
            self.statlst_geninst.SigFinished.connect(self.m["scan_completed_ref"])  #TODO: unsaubere Lösung; controller funs should not access GUI functions
            self.statlst_geninst.SigFinished.connect(self.statlst_genthread.quit)
            self.statlst_geninst.SigFinished.connect(lambda: print("statlst_geninst is being terminated###############!!!!!!!!!!!!!!!!#######################!!!!!!!!!!!!!!!!!!!!!!!!#################"))
            self.statlst_geninst.SigFinished.connect(self.statlst_geninst.deleteLater)
            self.statlst_genthread.finished.connect(self.statlst_genthread.deleteLater)
            self.statlst_genthread.start()
            if self.statlst_genthread.isRunning():
                self.statlst_genthreadActive = True
            pass

        else:
            self.m["scan_completed_ref"]()  #TODO TODO TODO: unsaubere Lösung; controller funs should not access GUI functions
            try:
                stream = open(self.m["status_filename"], "r")
                status = yaml.safe_load(stream)
                stream.close()
            except:
                self.logger.debug("cannot get status")
                return False 
            if status["annotated"] == True:
                self.m["scan_completed_ref"]()  #TODO TODO TODO: unsaubere Lösung; controller funs should not access GUI functions
            else:
                freq_ix = status["freqindex"]
                try:
                    stream = open(self.stations_filename, "r", encoding="utf8")
                    self.stations = yaml.safe_load(stream)
                    stream.close()
                except:
                    self.logger.debug("cannot get stations list")
                    return False
                self.SigRelay.emit("cexex_annotate",["labelFrequencySetText",'Frequency: ' + str(self.stations[freq_ix]['frequency'] + ' kHz')])
                self.SigRelay.emit("cexex_annotate",["ann_upd_GUI",0])

            self.SigRelay.emit("cexex_annotate",["pushButtonENTERdisable",0])
            self.SigRelay.emit("cexex_annotate",["interactive_station_select",0])

    def cb_backinfrequency(self):
        self.gui.annotate_pushButtonBack.setEnabled(False)
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get status")
            return False
        
        freq_ix = status["freqindex"]
        if freq_ix > -1:
            freq_ix -= 1
        else:
            return
        status["freqindex"] = freq_ix
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        self.gui.progressBar_2.setProperty("value", (freq_ix + 1)/len(self.stations)*100) #############################
        self.gui.Annotate_listWidget.clear() ####################################################
        self.gui.annotate_pushButtonBack.setEnabled(False)


    def enterlinetoannotation(self):
        """
        CONTROLLER
        read yaml stations_list.yaml

        """
        #self.gui.lineEdit.setEnabled(False)
        #print('Editline copy to metadata file')
        #self.gui.pushButtonENTER.setEnabled(False) ##############################################################################################
        self.SigRelay.emit("cexex_annotate",["pushButtonENTERdisable",0])
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get status")
            return False
        
        freq_ix = status["freqindex"]
        programstr = self.gui.lineEdit.text() ##############################################################################################
        txstr = self.gui.lineEdit_TX_Site.text() ##############################################################################################
        countrystr = self.gui.lineEdit_Country.text() ##############################################################################################

        country_string = '  country: "{}"\n'.format(countrystr)
        programme_string = '  programme: "{}"\n'.format(programstr)
        tx_site_string = '  tx-site: "{}"\n'.format(txstr)
        freq_ix = self.current_freq_ix
        with open(self.cohiradia_metadata_filename, 'a+', encoding='utf-8') as f: #######################################
            f.write('- frequency: "{}"\n'.format(self.stations[freq_ix]['frequency']))
            f.write('  snr: "{}"\n'.format(self.stations[freq_ix]['snr']))
            f.write(country_string)
            f.write(programme_string)
            f.write(tx_site_string)
        freq_ix += 1
        status["freqindex"] = freq_ix
        status["annotated"] = False
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        self.gui.progressBar_2.setProperty("value", (freq_ix + 1)/len(self.stations)*100) ##############################################################################################
        self.gui.Annotate_listWidget.clear() ##############################################################################################
        self.SigRelay.emit("cexex_annotate",["interactive_station_select",0])
        self.gui.annotate_pushButtonBack.setEnabled(True)
        #self.interactive_station_select()

    def discard_annot_line(self):
        """
        CONTROLLER
        read yaml stations_list.yaml

        """
        #print("discard reached")
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("discard cannot write to yaml")
            return False 
        freq_ix = status["freqindex"] # read last frequency index which was treated in interactive list checking
        #Discard this frequency, advance freq counter, do not write to cohiradia annotation
        freq_ix += 1
        status["freqindex"] = freq_ix
        status["annotated"] = False
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        #self.interactive_station_select()
        self.SigRelay.emit("cexex_annotate",["interactive_station_select",0])
        self.gui.progressBar_2.setProperty("value", (freq_ix + 1)/len(self.stations)*100) ##############################################################################################
        return False


class annotate_v(QObject):
    """_view methods for resampling module
    TODO: gui.wavheader --> something less general ?
    """
    __slots__ = ["viewvars"]

    SigAny = pyqtSignal()
    SigCancel = pyqtSignal()
    SigUpdateGUI = pyqtSignal(object)
    SigSyncGUIUpdatelist = pyqtSignal(object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)

    def __init__(self, gui, annotate_c, annotate_m):
        super().__init__()

        #viewvars = {}
        #self.set_viewvars(viewvars)
        self.m = annotate_m.mdl
        self.annotate_c = annotate_c
        self.gui = gui #gui_state["gui_reference"]#self.m["gui_reference"]
        self.logger = annotate_m.logger
        self.annotate_c.SigRelay.connect(self.rxhandler)
        self.init_annotate_ui()
        self.annotate_c.SigRelay.connect(self.SigRelay.emit)
        self.NUMSNAPS = 5 #number of segments evaluated for annotation 
        self.STICHTAG = datetime(2023,2,25,0,0,0) #TODO: only used in stationsloop of statslist_gen_worker as self.host.STICHTAG, Move to module annotation
        self.autoscanthreadActive = False
        self.m["scan_completed_ref"] = self.scan_completed
        self.m["Progressbarupdate_ref"] = self.Progressbarupdate
        self.m["Progressbarupdate2_ref"] = self.Progressbarupdate2


    def init_annotate_ui(self):
        #preset ui elements of annotator
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButtonAnnotate.setStyleSheet("background-color : rgb(220, 220, 220)")
        self.gui.pushButtonAnnotate.setEnabled(False)
        self.gui.pushButton_Scan.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButton_Scan.setStyleSheet("background-color : rgb(220, 220, 220)")
        self.gui.pushButton_Scan.setEnabled(False)
        self.gui.lineEdit.setText('')
        self.gui.lineEdit.setAlignment(QtCore.Qt.AlignLeft)
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        self.gui.label_Filename_Annotate.setText('')
        self.gui.pushButtonDiscard.setEnabled(False)
        self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButtonENTER.setEnabled(False)
        self.gui.progressBar_2.setProperty("value", 0)
        self.gui.Annotate_listWidget.clear()
        self.m["NumScan"] = self.gui.spinBoxNumScan.value()
        self.m["minSNR"] = self.gui.spinBoxminSNR.value()

        #connect ui element events with annotator methods
        #self.gui.ann_spinBox_peakBW.setEnabled(False) ##TODO: enable once BW_peaklock method has been implemented in a clear manner
        #self.gui.spinBox_res_digits.setVisible(False)
        self.gui.pushButton_Scan.clicked.connect(self.annotate_c.autoscan)
        self.gui.pushButtonAnnotate.clicked.connect(self.annotatehandler) 
        self.gui.pushButtonDiscard.clicked.connect(self.discard_annot_line) ####TODO TODO TODO in future must be the controller method
        self.gui.spinBoxminSNR.valueChanged.connect(self.minSNRupdate) 
        self.gui.pushButtonENTER.clicked.connect(self.enterlinetoannotation) ####TODO TODO TODO in future must be the controller method
        self.gui.Annotate_listWidget.itemClicked.connect(self.cb_ListClicked)
        self.gui.spinBoxNumScan.valueChanged.connect(self.cb_numscanchange)
        # self.gui.spinBox_res_digits.valueChanged.connect(self.cb_res_digits_change)
        # self.gui.ann_spinBox_peakBW.valueChanged.connect(self.cb_ann_spinBox_peakBW)
        self.gui.peakBW_comboBox.currentIndexChanged.connect(self.cb_peakBW_comboBox)
        #self.gui.spinBoxminSNR.valueChanged.connect(self.cb_minSNRchange) #TODO: wozu ?
        self.gui.annotate_pushButtonBack.setEnabled(False)
        self.gui.annotate_pushButtonBack.clicked.connect(self.cb_backinfrequency)  ####TODO TODO TODO in future must be the controller method
        self.gui.radioButton_export_xlsx.setChecked(False)
        self.gui.radioButton_export_xlsx.clicked.connect(self.cb_Butt_export)
        #self.gui.lineEdit.returnPressed.connect(self.enterlinetoannotation)
        #self.gui.pushButton_ScanAnn.clicked.connect(self.listclick_test)

                
        #TODO: reade info on spinbox settings MF kernel etc from status file if it exists
        #self.gui.spinBoxKernelwidth.setProperty("value", 15)
        #self.gui.spinBoxNumScan.setProperty("value", 10)
        #self.gui.spinBoxminBaselineoffset.setProperty("value", 5)

    def annotatehandler(self):
        self.m["export_xlsx"] = False
        self.annotate_c.ann_stations()
        self.m["export_xlsx"] = self.gui.radioButton_export_xlsx.isChecked()

    def cb_Butt_export(self):
        self.m["export_xlsx"] = self.gui.radioButton_export_xlsx.isChecked()

    # def cb_res_digits_change(self):
    #     """
    #     slot function for resolution digits spinbox
    #     :param : none
    #     :return: none
    #     """
    #     self.m["round_digits"] = self.gui.spinBox_res_digits.value()
    #     self.SigRelay.emit("cm_annotate_",["round_digits",self.m["round_digits"]])
    #     self.gui.ann_spinBox_peakBW.setValue(int(1000/(10**self.m["round_digits"])))
        
    def cb_peakBW_comboBox(self):
        """
        slot function for resolution digits spinbox
        :param : none
        :return: none
        """
        self.m["round_digits"] = self.gui.peakBW_comboBox.currentIndex()
        self.SigRelay.emit("cm_annotate_",["round_digits",self.m["round_digits"]])

    # def cb_ann_spinBox_peakBW(self):
    #     """
    #     slot function for changes of the spinbox ann_spinBox_peakBW (Bandwidth within which peak frequencies scattered around a found peak value is assigned to a unique peak frequency)
    #     :param : none
    #     :return: none
    #     """
    #     self.m["BW_peaklock"] = self.gui.ann_spinBox_peakBW.value()
    #     self.SigRelay.emit("cm_annotate_",["BW_peaklock",self.m["BW_peaklock"]])

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
#        print(f"####################annotate rxhandler: key: {_key}, value: {_value}")
        if _key.find("cm_annotate") == 0 or _key.find("cm_all_") == 0:
            #set mdl-value
            self.m[_value[0]] = _value[1]
        if _key.find("cui_annotate") == 0:
            _value[0](*_value[1])
        if _key.find("cexex_annotate") == 0  or _key.find("cexex_all_") == 0:
            if  _value[0].find("updateGUIelements") == 0:

                self.updateGUIelements()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("getGUIvalues") == 0:
                self.getGUIvalues()
            if  _value[0].find("connect_autoscan") == 0:
                self.connect_autoscan()
            if  _value[0].find("annotatestatusdisplay") == 0:
                self.annotatestatusdisplay(_value[1])
            if  _value[0].find("interactive_station_select") == 0:
                self.interactive_station_select()
            if  _value[0].find("labelFrequencySetText") == 0:
                self.gui.labelFrequency.setText(_value[1])
            if  _value[0].find("pushButtonENTERdisable") == 0:
                self.gui.pushButtonENTER.setEnabled(False)
            if  _value[0].find("annotation_deactivate") == 0:
                self.annotation_deactivate()
            if  _value[0].find("scan_deactivate") == 0:
                self.scan_deactivate()
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])
            if  _value[0].find("ann_upd_GUI") == 0:
                self.ann_upd_GUI()
            if  _value[0].find("resizeaction") == 0:
                #print("resize action triggered in annotator")
                _value[1].resize_initialize()

            #handle method
            # if  _value[0].find("plot_spectrum") == 0: #EXAMPLE
            #     self.plot_spectrum(0,_value[1])   #EXAMPLE
                
    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("annotate: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
            self.logger.debug("view spectra: INACTIVATE LOGGING after NOTSET")
        else:
            self.logger.debug("annotate: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)

                
    def annotatestatusdisplay(self,dispstring):
        self.gui.label.setText(dispstring)

    def connect_autoscan(self):
        self.annotate_c.autoscaninst.SigFinished.connect(self.autoscan_finished)
        self.annotate_c.autoscaninst.SigProgressBar.connect(self.Progressbarupdate)
        self.annotate_c.autoscaninst.SigPlotdata.connect(self.scanplot)
        self.annotate_c.autoscaninst.SigScandeactivate.connect(self.scan_deactivate)
        self.annotate_c.autoscaninst.SigUpdateGUI.connect(self.scanupdateGUI)
        self.annotate_c.autoscaninst.SigStatustable.connect(self.status_writetableread)


    def getGUIvalues(self):
                self.m["NumScan"] = self.gui.spinBoxNumScan.value()
                self.m["minSNR"] = self.gui.spinBoxminSNR.value()
                #self.m["round_digits"] = self.gui.spinBox_res_digits.value()
                #self.m["BW_peaklock"] = self.gui.ann_spinBox_peakBW.value()
                self.m["round_digits"] = self.gui.peakBW_comboBox.currentIndex()


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
        print("annotate: updateGUIelements")
        ### TODO: CHECK  if is working correctlydisconnect spinBox from Signalling to updateGUIelements if next line is called;; should only be done in spinbox callback
        self.gui.spinBoxminSNR.valueChanged.disconnect(self.minSNRupdate) 
        self.gui.spinBoxminSNR.setProperty("value",self.m["prominence"])
        self.gui.spinBoxminSNR.valueChanged.connect(self.minSNRupdate) 
        if self.m["fileopened"]:
            self.gui.label_Filename_Annotate.setText(self.m["my_filename"] + self.m["ext"])
        self.gui.label_6.setText("Baseline Offset:" + str(self.m["baselineoffset"]))
        try:
            if (os.path.exists(self.stations_filename) == True):
                self.scan_completed()
                try:
                    stream = open(self.status_filename, "r")
                    status = yaml.safe_load(stream)
                    stream.close()
                except:
                    return False 
                if status["annotated"] == True:
                    self.annotation_completed()
                    self.SigRelay.emit("cexex_yamleditor",["setWriteyamlButton",True])
                else:
                    self.annotation_activate()
            elif self.m["fileopened"]:
                self.scan_activate()
            else:
                pass
        except:
            pass

        #self.gui.DOSOMETHING


    def reset_GUI(self):
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.lineEdit.setText('')
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.Annotate_listWidget.clear()
        self.gui.pushButtonDiscard.setEnabled(False)
        self.gui.labelFrequency.setText("Freq:")
        self.gui.label_Filename_Annotate.setText('')

        self.annotation_deactivate()
        self.scan_deactivate()
        try:
            self.stations_filename = self.m["annotationpath"] + '/stations_list.yaml'
        except:
            #print("no annotationspath, ignore")
            return False
        if (os.path.exists(self.stations_filename) == True) and self.m["fileopened"]:
            self.scan_completed()
            try:
                stream = open(self.status_filename, "r")
                status = yaml.safe_load(stream)
                stream.close()
            except:
                #print("reset GUI: cannot get status")
                return False 
            if status["annotated"] == True:
                self.annotation_completed()
                #self.ui.pushButton_Writeyamlheader.setEnabled(True) ####TODO TODO TODO send by relaying yaml
                self.SigRelay.emit("cexex_yamleditor",["setWriteyamlButton",True])
            else:
                self.annotation_activate()
        elif self.m["fileopened"]:
            self.scan_activate()
        else:
            pass


    def cb_numscanchange(self):
        self.m["NumScan"] = self.gui.spinBoxNumScan.value()

    def cb_minSNRchange(self):  #TODO: obsolete ?
        self.m["minSNR"] = self.gui.spinBoxminSNR.value()

    def annotation_completed(self):
        """_summary_
        VIEW, gehört zum Tab Annotate
        """
        self.gui.pushButtonAnnotate.setStyleSheet("background-color : rgb(170, 255, 127)")
        self.gui.pushButtonAnnotate.setEnabled(False)
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButtonDiscard.setEnabled(False)
        self.gui.progressBar_2.setProperty("value", 100)
        self.gui.lineEdit.setText('Record has already been annotated. For re-annotation delete annotation folder')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        self.SigRelay.emit("cexex_yamleditor",["setWriteyamlButton",True])
        #self.gui.pushButton_Writeyamlheader.setEnabled(True) ##### replace by relaying !
        self.flag_ann_completed = True

    def annotation_activate(self):
        """_summary_
        VIEW, gehört zum Tab Annotate
        """
        self.gui.pushButtonAnnotate.setStyleSheet("background-color : rgb(220,220,220)")
        self.gui.pushButtonAnnotate.setEnabled(True)
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButtonDiscard.setEnabled(False)
        self.gui.lineEdit.setText('annotation can be started or continued')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))

    def annotation_deactivate(self):
        """_summary_

        """        
        self.gui.pushButtonAnnotate.setStyleSheet("background-color : rgb(220,220,220)")
        self.gui.pushButtonAnnotate.setEnabled(False)
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))

    def scan_completed(self):
        """_summary_

        """
        self.gui.pushButton_Scan.setStyleSheet("background-color : rgb(170, 255, 127)")
        self.gui.pushButton_Scan.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButton_Scan.setEnabled(False)
        self.gui.pushButtonAnnotate.setEnabled(True)
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.lineEdit.setText('autoscan has been completed, peaks and SNRs identified')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        #TODO: save settings for MF Kernel, SNR baselineoffset min peak width min peak distance to status file
        #TODO: write spinbox values to status file
        ####################TODO TODO TODO:CHECK:DONE urgent no direct access of GUI replace by signalling 
        #peakwidth = self.gui.spinBoxminPeakwidth.value()
        peakwidth = self.m["peakwidth"] #TODO: necessary or could be used directly ?
        #filterkernel = self.gui.spinBoxKernelwidth.value()
        filterkernel = self.m["filterkernel"] #TODO: necessary or could be used directly ?
        ##############TODO urgent 
        #self.m["baselineoffset"] = self.gui.spinBoxminBaselineoffset.value()  ##########TODO: introduce separate GUI element because this one belongs to view_spectra
        #minSNR = self.gui.spinBoxminSNR_ScannerTab.value()
        minSNR = self.m["prominence"] #TODO: necessary or could be used directly ?
        #minPeakDist = self.gui.spinBoxminPeakDistance.value()
        minPeakDist = self.m["deltaf"] #TODO: necessary or could be used directly ?
        ###################################################################################
        self.m["NumScan"] = self.gui.spinBoxNumScan.value()
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
            status["peakwidth"] = peakwidth
            status["filterkernel"] = filterkernel
            status["baselineoffset"] = self.m["baselineoffset"]
            status["minSNR"] = minSNR
            status["minPeakDist"] = minPeakDist
            status["NumScan"] = self.m["NumScan"]       
            stream = open(self.m["status_filename"], "w")
            yaml.dump(status, stream)
            stream.close()
        except:
            #print("cannot get/put status")
            self.logger.error("scan_completed: cannot get/put status")

    def scan_activate(self):
        """_summary_
        """
        self.gui.pushButton_Scan.setStyleSheet("background-color : rgb(220,220,220)")
        self.gui.pushButton_Scan.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButton_Scan.setEnabled(True)
        self.gui.pushButtonAnnotate.setEnabled(False)
        self.gui.pushButtonAnnotate.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.lineEdit.setText('autoscan can be started (search for TX peaks and SNR values)')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))

    def scan_deactivate(self):
        """_summary_
        """
        self.gui.pushButton_Scan.setStyleSheet("background-color : rgb(220,220,220)")
        self.gui.pushButton_Scan.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.pushButton_Scan.setEnabled(False)
        self.gui.lineEdit.setText('')
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))

    def minSNRupdate(self):
        """_summary_
        """
        self.m["prominence"] = self.gui.spinBoxminSNR.value()
        self.m["minSNR"] = self.gui.spinBoxminSNR.value()  #TODO: why assinment to 2 different variables ?
        ####################TODO TODO TODO: urgent no direct access of GUI replace by signalling
        #self.gui.spinBoxminSNR_ScannerTab.setProperty("value", self.m["prominence"])
        ####################################################################
        self.SigRelay.emit("cm_all_",["prominence",self.m["prominence"]])##############################################################
        #TODO TODO TODO: interrupt endless elsf calling loop by emitting this only, if the SNR-buttons are pressed (here and in view spectra) and not if the value is only changed by 
        #################################################
        #code in updateGUIelements
        self.SigRelay.emit("cexex_view_spectra",["updateGUIelements",0])

    def activate_WAVEDIT(self):
        self.show()
        if self.gui.radioButton_WAVEDIT.isChecked() is True:
                    self.gui.tableWidget_basisfields.setEnabled(True)
                    self.gui.tableWidget_starttime.setEnabled(True)
                    self.gui.tableWidget_3.setEnabled(True)      
        else:
                    self.gui.tableWidget_basisfields.setEnabled(False)
                    self.gui.tableWidget_starttime.setEnabled(False)
                    self.gui.tableWidget_3.setEnabled(False)

    def scanupdateGUI(self):
        """_summary_
        """
        self.gui.label.setText("Status: Scan spectra for prominent TX peaks")
        self.gui.pushButton_Scan.setEnabled(False)
        ### TODO: urgent access of foreign GUI element
        self.gui.horizontalScrollBar_view_spectra.setEnabled(False)
        ###########################
        self.gui.lineEdit.setText('Please wait while spectra are analyzed for peaks')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))

    def Progressbarupdate(self):
        """
        _updates progress bar value
        """
        #print("Progressbarupdate")
        self.gui.progressBar_2.setProperty("value", int(self.annotate_c.autoscaninst.get_progressvalue()))
        #send continue flag to autoscan task
        if self.annotate_c.autoscanthreadActive == True:
            self.annotate_c.autoscaninst.set_continue(True)

    def Progressbarupdate2(self):
        """
        _summary_
        """
        self.gui.progressBar_2.setProperty("value", int(self.annotate_c.statlst_geninst.get_progressvalue()))
        #send continue flag to autoscan task
        if self.annotate_c.statlst_genthreadActive == True:
            self.annotate_c.statlst_geninst.set_continue(True)

    def status_writetableread(self):
        """
        _summary_
        """
        self.gui.progressBar_2.setProperty("value", int(0))
        self.gui.label.setText("Status: read MWList table for annotation")
        #send continue flag to autoscan task
        if self.autoscanthreadActive == True:
            self.annotate_c.autoscaninst.set_continue(True)

    def autoscan_finished(self):
        """
        _summary_
        """
        ### TODO: urgent access of foreign GUI element
        #self.gui.horizontalScrollBar_view_spectra.setEnabled(True)
        self.SigRelay.emit("cexex_view_spectra",["enablescrollbar",True])
        ##############################################
        self.gui.lineEdit.setText('')
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        self.autoscanthreadActive = True
        if self.gui.radioButton_plotpreview.isChecked() is True:
            plt.close()

    def scanplot(self):
        """
        VIEW
        _summary_
        """
        #TODO: only execute if Preview_plot == True   radioButton_plotpreview
        if self.gui.radioButton_plotpreview.isChecked() is True:
            plt.close()
            plt.cla()
            pdata = self.autoscaninst.get_pdata()
            #pdata = autoscan_ret[2]
            #self.__slots__[0][2] = pdata
            plt.plot(pdata["datax"],pdata["datay"])
            plt.xlabel("frequency (Hz)")
            plt.ylabel("peak amplitude (dB)")
            plt.show()
            plt.pause(1)
        #send continue flag to autoscan task
        if self.autoscanthreadActive == True:
            self.annotate_c.autoscaninst.set_continue(True)


#########################????????????????????????####################

        # self.autoscanthread = QThread()
        # self.autoscaninst = autoscan_worker(self)
        # self.autoscaninst.moveToThread(self.autoscanthread)
        # #TODO: Implement further slot communicationa shown here
        # self.autoscaninst.set_0([self.m["Numscan"],self.gui.spinBoxminSNR.value(),[]])

        # TODO: urgent: no access of foreign GUI
        #self.gui.tab_view_spectra.setEnabled(True)

        #self.gui.label_8.setEnabled(False)
        #self.gui.label_36.setText('READY')
        #self.gui.label_36.setFont(QFont('arial',12))
        #self.gui.label_36.setStyleSheet("background-color: lightgray")


    def scanupdateGUI(self):
        """_summary_
        VIEW
        """
        self.gui.label.setText("Status: Scan spectra for prominent TX peaks")
        self.gui.pushButton_Scan.setEnabled(False)
        #TODO urgent access of foreign GUI element
        #self.gui.horizontalScrollBar_view_spectra.setEnabled(False)
        self.SigRelay.emit("cexex_view_spectra",["enablescrollbar",False])
        self.gui.lineEdit.setText('Please wait while spectra are analyzed for peaks')
        self.gui.lineEdit.setStyleSheet("background-color : yellow")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))

    def ann_upd_GUI(self):
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
        self.gui.lineEdit.setText('')
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.lineEdit.setFont(QFont('MS Shell Dlg 2', 12))
            

    #@njit
    def interactive_station_select(self):
        """
        TODO: write text
        read yaml stations_list.yaml

        """
        #print("interactive station select annotator module")
        #self.gui.lineEdit.setStyleSheet("background-color : white")
        self.gui.Annotate_listWidget.clear()
        self.gui.lineEdit.setText('')
        self.gui.lineEdit_TX_Site.setText('')
        self.gui.lineEdit_Country.setText('')
        ### reading again the yaml is inefficient: could be passed from ann_stations
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get status")
            return False 
        try:
            stream = open(self.stations_filename, "r", encoding="utf8")
            self.stations = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get stations list")
            return False
        
        freq_ix = status["freqindex"] # read last frequency index which was treated in interactive list checking
        if freq_ix >= len(self.stations):
            self.annotation_completed()
            status["annotated"] = True
            stream = open(self.m["status_filename"], "w")
            yaml.dump(status, stream)
            stream.close()
            return False
        plen = int((len(self.stations[freq_ix])-2)/3) #number of station candidates
        self.gui.labelFrequency.setText('f: ' + str(self.stations[freq_ix]['frequency'] + ' kHz'))
        self.gui.progressBar_2.setProperty("value", freq_ix/len(self.stations)*100)
        #self.gui.lineEdit.setText('Frequency: ' + str(self.stations[freq_ix]['frequency'] + ' kHz'))
        time.sleep(0.01)
        
        for ix2 in range(plen):
            country_string = self.stations[freq_ix]['country' + str(ix2)]
            programme_string = self.stations[freq_ix]['programme' + str(ix2)]
            tx_site_string = self.stations[freq_ix]['tx-site' + str(ix2)]
            item = QtWidgets.QListWidgetItem()
            self.gui.Annotate_listWidget.addItem(item)
            item = self.gui.Annotate_listWidget.item(ix2)
            item.setText(country_string.strip('\n') + ' | ' + programme_string.strip('\n') + ' | ' + tx_site_string.strip('\n'))
            time.sleep(0.01)
        #add dummy line in list for selecting own entry
        # item = QtWidgets.QListWidgetItem()
        # self.gui.Annotate_listWidget.addItem(item)
        # item = self.gui.Annotate_listWidget.item(ix2+1)
        # dum_cstr = 'OTHER COUNTRY, Please enter manually'
        # dum_pstr = 'OTHER STATION, Please enter manually'
        # dum_txstr = 'OTHER TX SITE, Please enter manually'
        # item.setText(dum_cstr.strip('\n') + ' | ' + dum_pstr.strip('\n') + ' | ' + dum_txstr.strip('\n'))
        # time.sleep(0.01)
        self.gui.pushButtonDiscard.setEnabled(True)


    def cb_ListClicked(self,item):
        """
        CONTROLLER
        read yaml stations_list.yaml

        """
        #memorize status and advance freq_ix
        #print("list clicked annotator module")
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get status")
            return False 
        freq_ix = status["freqindex"] # read last frequency index which was treated in interactive list checking
        if freq_ix < len(self.stations):
            #read index of clicked row and fetch associated content from stations list
            cr_ix = self.gui.Annotate_listWidget.currentRow()
            Ecountry_string = self.stations[freq_ix]['country' + str(cr_ix)]
            Eprogramme_string = self.stations[freq_ix]['programme' + str(cr_ix)]
            Etx_site_string = self.stations[freq_ix]['tx-site' + str(cr_ix)]
            self.gui.labelFrequency.setText('f: ' + str(self.stations[freq_ix]['frequency']) + ' kHz')

            self.gui.lineEdit.setText(Eprogramme_string)
            self.gui.lineEdit.setAlignment(QtCore.Qt.AlignLeft)
            self.gui.lineEdit.home(True)
            self.gui.lineEdit_TX_Site.setText(Etx_site_string)
            self.gui.lineEdit_TX_Site.setAlignment(QtCore.Qt.AlignLeft)
            self.gui.lineEdit_TX_Site.home(True)
            self.gui.lineEdit_Country.setText(Ecountry_string)
            self.gui.lineEdit_Country.setAlignment(QtCore.Qt.AlignLeft)
            self.gui.lineEdit_Country.home(True)
            self.current_freq_ix = freq_ix

        # end of stationslist reached
            self.gui.pushButtonENTER.setEnabled(True)
        else:
            status["freqindex"] = freq_ix
            status["annotated"] = True
            stream = open(self.m["status_filename"], "w")
            yaml.dump(status, stream)
            stream.close()
            self.gui.progressBar_2.setProperty("value", 100)
            self.annotation_completed()

    def cb_backinfrequency(self):
        """
        CONTROLLER TODO TODO TODO
        read yaml stations_list.yaml

        """
        self.gui.annotate_pushButtonBack.setEnabled(False)
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("cannot get status")
            return False
        
        freq_ix = status["freqindex"]
        self.current_freq_ix = freq_ix
        if freq_ix > -1:
            freq_ix -= 1
        else:
            return
        status["freqindex"] = freq_ix
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        #self.gui.progressBar_2.setProperty("value", (freq_ix + 1)/len(self.stations)*100) 
        self.gui.Annotate_listWidget.clear()
        self.interactive_station_select()


    def enterlinetoannotation(self):
        """
        CONTROLLER TODO TODO TODO
        read yaml stations_list.yaml

        """
        #self.gui.lineEdit.setEnabled(False)
        #print('Editline copy to metadata file, module annotator')
        self.gui.pushButtonENTER.setEnabled(False)
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("enterlineannotation cannot get status")
            return False
        
        freq_ix = status["freqindex"]
        programstr = self.gui.lineEdit.text()
        txstr = self.gui.lineEdit_TX_Site.text()
        countrystr = self.gui.lineEdit_Country.text()

        country_string = '  country: "{}"\n'.format(countrystr)
        programme_string = '  programme: "{}"\n'.format(programstr)
        tx_site_string = '  tx-site: "{}"\n'.format(txstr)
        freq_ix = self.current_freq_ix
        with open(self.m["cohiradia_metadata_filename"], 'a+', encoding='utf-8') as f:
            f.write('- frequency: "{}"\n'.format(self.stations[freq_ix]['frequency']))
            f.write('  snr: "{}"\n'.format(self.stations[freq_ix]['snr']))
            f.write(country_string)
            f.write(programme_string)
            f.write(tx_site_string)
        freq_ix += 1
        status["freqindex"] = freq_ix
        status["annotated"] = False
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        #print(f"forward progressbar enterline_annotation, value: {(freq_ix + 1)/len(self.stations)*100}")
        self.gui.Annotate_listWidget.clear()
        self.interactive_station_select()
        self.gui.annotate_pushButtonBack.setEnabled(True)

    def discard_annot_line(self):
        """
        CONTROLLER
        read yaml stations_list.yaml

        """
        #print("DISCARD annotatemodule")
        try:
            stream = open(self.m["status_filename"], "r")
            status = yaml.safe_load(stream)
            stream.close()
        except:
            #print("stream not iopened DISCARD annotatemodule")
            return False 
        freq_ix = status["freqindex"] # read last frequency index which was treated in interactive list checking
        #Discard this frequency, advance freq counter, do not write to cohiradia annotation
        freq_ix += 1
        status["freqindex"] = freq_ix
        status["annotated"] = False
        stream = open(self.m["status_filename"], "w")
        yaml.dump(status, stream)
        stream.close()
        self.interactive_station_select()
        #print(f"forward progressbar discard annot line , value: {(freq_ix + 1)/len(self.stations)*100}")
        return False

 
