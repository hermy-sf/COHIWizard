from struct import pack, unpack
import numpy as np
import time
import os
#import system_module as wsys
#from SDR_wavheadertools_v2 import WAVheader_tools
from datetime import datetime
from datetime import timedelta
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg,  NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import subprocess
import platform
import urllib.request
import zipfile
import tarfile
import yaml
from core import wavchunks
#import shutil #### Nicht nötig ??
import sys
import re
#import ipaddress  #### Nicht nötig ??
#import socket
from zeroconf import Zeroconf, ServiceBrowser



class ffmpeg_installtools():
    """contains many auxiliariy methods fo the COHIWizard
    :return: _description_
    :rtype: _type_
    """


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dummy = True
        # import platform
        # import urllib.request
        # import zipfile
        # import tarfile
        # Constants
        #self.status = {}    # Test Mode Flag for testing the App without a



    def is_ffmpeg_installed(ffmpeg_path):
        """check if ffmpeg is available on the system"""
        try:
            #check for global installation with PATH set in the OS
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            value = ""
            errorstate = False
            return(errorstate, value)
        except FileNotFoundError:
            #check for local installation in ffmpeg standardpath of the COHIWIzard filesystem
            #ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg-master-latest-win64-gpl", "bin")
            
            #self.logger.debug(f"__init_ m check for ffmpeg_path: {self.mdl["ffmpeg_path"]}, file not found")
            try:
                subprocess.run([os.path.join(ffmpeg_path, "ffmpeg"), "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                errorstate = False
                value = ffmpeg_path
                return(errorstate, value)
            except FileNotFoundError:
                errorstate = True
                value = "Cannot find ffmpeg path in the system. Please install ffmpeg."
                return(errorstate,value)

    def download_ffmpeg(url, output_path):
        """downloads ffmpeg from specified URL and copies to output_path"""
        print(f"Download ffmpeg from {url} ...")
        urllib.request.urlretrieve(url, output_path)
        print("Download accomplished.")


    def install_ffmpeg_linux(self, destination):
        """Installs ffmpeg under Linux."""
        errorstatus = False
        value = ""
        os.makedirs(destination, exist_ok=True)

        ffmpeg_url = "https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz"
        archive_path = os.path.join(destination, "ffmpeg.tar.xz")
        try:
            self.download_ffmpeg(ffmpeg_url, archive_path)
        except:
            errorstatus = True
            value = f"cannot download installation files from {ffmpeg_url}. Please check internet connection and retry after restarting the COHIWizard"
            return(errorstatus,value)
        print("unzip ffmpeg...")
        with tarfile.open(archive_path, "r:xz") as tar:
            tar.extractall(destination)
        
        ffmpeg_dir = next((d for d in os.listdir(destination) if d.startswith("ffmpeg")), None)
        if ffmpeg_dir:
            ffmpeg_path = os.path.join(destination, ffmpeg_dir)
            #self.logger.debug(f"ffmpeg unzipped successfully to {ffmpeg_path} .")
            print(f"ffmpeg unzipped successfully to {ffmpeg_path} .")
            value = [os.path.join(ffmpeg_path, "bin", "ffmpeg"), os.path.join(ffmpeg_path, "bin")]
        else:
            errorstatus = True
            value = "Error when unzipping ffmpeg."
            #raise RuntimeError("Error when unzipping ffmpeg.")
        
        os.remove(archive_path)  # Lösche die Archivdatei
        errorstatus = False
        return(errorstatus,value)

    def install_ffmpeg_windows(self,destination):
        """Installis ffmpeg under Windows."""
        errorstatus = False
        value = ""
        os.makedirs(destination, exist_ok=True)
        ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"
        #ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        archive_path = os.path.join(destination, "ffmpeg.zip")
        #TODO TODO TODO: make progress bar
        try:
            self.download_ffmpeg(ffmpeg_url, archive_path)
        except:
            errorstatus = True
            value = f"cannot download installation files from {ffmpeg_url}. \n \n Please check internet connection and retry after restarting the COHIWizard"
            return(errorstatus,value)
        print("unzip ffmpeg...")
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(destination)
        
        ffmpeg_dir = next((d for d in os.listdir(destination) if "ffmpeg" in d), None)
        if ffmpeg_dir:
            ffmpeg_path = os.path.join(destination, ffmpeg_dir)
            #self.logger.debug(f"ffmpeg unzipped successfully to {ffmpeg_path} .")
            print(f"ffmpeg unzipped successfully to {ffmpeg_path} .")
            value = [os.path.join(ffmpeg_path, "bin", "ffmpeg.exe"), os.path.join(ffmpeg_path, "bin")]
        else:
            errorstatus = True
            value = "Error when unzipping ffmpeg."
            #raise RuntimeError("Error when unzipping ffmpeg.")
        
        os.remove(archive_path)  # Lösche die Archivdatei
        errorstatus = False
        return(errorstatus,value)

    def configure_path(ffmpeg_path):
        """Setting ffmpeg-Pfad in environment variables."""
        os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
        print(f"Path for ffmpeg was set to {os.path.dirname(ffmpeg_path)}.")
        
class WIZ_auxiliaries():
    """contains many auxiliariy methods fo the COHIWizard
    :return: _description_
    :rtype: _type_
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dummy = True
        # Constants
        #self.status = {}    # Test Mode Flag for testing the App without a

    def standard_errorbox(errortext):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText(errortext)
        msg.setWindowTitle("Error")
        msg.exec_()

    def standard_infobox(infotext):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("ATTENTION")
        msg.setInformativeText(infotext)
        msg.setWindowTitle("ATTENTION")
        msg.exec_()

class timer_worker(QObject):
    """_generates time signals for clock and recording timer_

    :param [ParamName]: [ParamDescription], defaults to [DefaultParamVal]
    :type [ParamName]: [ParamType](, optional)
    ...
    :raises [ErrorType]: [ErrorDescription]TODO
    ...
    :return: [ReturnDescription]
    :rtype: [ReturnType]
    """
    SigTick = pyqtSignal()
    SigFinished = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tick(self):
        """send a signal self.SigTick every second
        :param : none
        :type : none
        :raises: none
        :return: none
        :rtype: none
        """
        while True:
            time.sleep(1 - time.monotonic() % 1)
            self.SigTick.emit()

    def stoptick(self):
        self.SigFinished.emit()        

class _ElideFilter(QObject):
    """event filter of labels with middle-elided text (see auxiliaries.set_elided_text):
    shortens the text again after every size or font change"""
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.FontChange):
            _elide_label(obj)
        return False


_elide_filter = None


def _elide_label(label):
    full = label.property("elide_full_text") or ""
    width = max(10, label.width() - 6)
    label.setText(label.fontMetrics().elidedText(full, Qt.ElideMiddle, width))


class auxiliaries():

    @staticmethod
    def set_elided_text(label, text):
        """show text in label shortened in the middle ('abc…xyz') if it is too long, so
        that start and end of a file name (date, frequency) stay visible; the full text
        is the tooltip. The label is shortened again on every resize/font change.
        :param label: QLabel
        :param text: full text
        """
        global _elide_filter
        if _elide_filter is None:
            _elide_filter = _ElideFilter()
        if not label.property("elide_filter_installed"):
            label.installEventFilter(_elide_filter)
            label.setProperty("elide_filter_installed", True)
        text = text or ""
        label.setProperty("elide_full_text", text)
        label.setToolTip(text)
        _elide_label(label)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Constants
        self.TEST = True

    def readsegment_new(self,filepath,position,readoffset,DATABLOCKSIZE,sBPS,tBPS,wFormatTag):
        """
        opens file filepath and reads a data segment from position 216 + position #TODO: check if 216 is universal !
        the segment has length DATABLOCKSIZE
        segment is read according to format specified in wFormattag (int, float) and sBPS(16, 32, 24)
        segment is returned as float array of complex numbers, even entries = real, odd entries = imaginary
        output format is 16 or 32bit according to value specified in tBPS. No other BPS (e.g. 8) are allowed.
        24 Bit mode is not recommended for frequent calling, because inefficient (slow !)
        :param self: An instance of the class containing attributes such as header information and filtering parameters.
        :type self: object
        :param: position
        :type position: int
        :param: DATABLOCKSIZE: size of bytes to be read
        :type position: int
        :param: sBPS: Bits per sample of source file 
        :type sBPS: int
        :param: tBPS: Bits per sample of target file 
        :type tBPS: int
        :param: wFormatTag: 1 or 3, wav-Format of source file 
        :type wFormatTag: int
        :raises [ErrorType]: [ErrorDescription]
        :return: ret = dictionary with fields: ret["data"], ret["size]; size is either the number of bytes read or -1 in case of invalid file formats
        :rtype: dictionary; type of field "data": np.float32 array of size self.DATABLOCKSIZE ; type of field "size": int
        """
        ##print(f"read segment reached, position: {position}")
        #data = np.empty(DATABLOCKSIZE, dtype=np.int16) #TODO: DATABLOCKSIZE dynamisch anpassen !
        ret = {}
        fid = open(filepath, 'rb')
        if wFormatTag == 1:
            scl = int(2**int(sBPS-1))-1   #if self.wavheader['nBitsPerSample'] 2147483648 8388608 32767 127
        else:
            scl = 1
        if sBPS == 16:
            fid.seek(readoffset+position, 0)
            if wFormatTag == 3: # read 16bit float
                dataraw = np.empty(DATABLOCKSIZE, dtype=np.float16)
                size = fid.readinto(dataraw)
                if tBPS == 32: #write 32 bit float
                    data = dataraw.astype(np.float32)
                else: # write to 16bit float
                    data = dataraw.astype(np.float16)
            elif wFormatTag == 1: # read int16
                dataraw = np.empty(DATABLOCKSIZE, dtype=np.int16)
                size = fid.readinto(dataraw)
                if tBPS == 32:
                    data = dataraw.astype(np.float32)/scl
                else:
                    data = dataraw.astype(np.float16)/scl
            else:
                WIZ_auxiliaries.standard_errorbox("unsupported Format Tag (wFormatTag): value other than 1 or 3 encountered")
                size = -1
            fid.close()
        elif sBPS == 32:
            fid.seek(216+position, 0) #TODO: ist 216 allgemein oder self.readoffset+position, 0)
            if  wFormatTag == 3: #read float32
                dataraw = np.empty(DATABLOCKSIZE, dtype=np.float32)
                size = fid.readinto(dataraw)
                if tBPS == 32: # write to float32
                    data = dataraw.astype(np.float32)
                else:
                    data = (dataraw>>16).astype(np.float16)# check ob das für float gilt oder nur für INT !!TODO 
                size = fid.readinto(data)
            elif  wFormatTag == 1: #read int32
                dataraw = np.empty(DATABLOCKSIZE, dtype=np.int32)
                size = fid.readinto(dataraw)
                if tBPS == 32:
                    data = dataraw.astype(np.float32)/scl
                else:
                    data = ((dataraw/scl)>>16).astype(np.float16)
                size = fid.readinto(dataraw)
            else:
                WIZ_auxiliaries.standard_errorbox("Unsupported FormatTag (wFormatTag): value other than 1 or 3 encountered")
                size = -1
            fid.close()
        elif sBPS == 24:   #This mode is useful ONLY for general short reading purposes (plotting) NOT for LOshifting !
            #localize data identifier
            fid.seek(readoffset+position, 0)
            data = np.empty(DATABLOCKSIZE, dtype=np.float32)
            size = 0
            for lauf in range(0,DATABLOCKSIZE):
                d = fid.read(3)
                if d == None:
                    fid.close()
                    size = 3*(lauf-1)
                else:
                    dataraw = unpack('<%ul' % 1 ,d + (b'\x00' if d[2] < 128 else b'\xff'))
                    if  wFormatTag == 1:
                        data[lauf] = np.float32(dataraw[0]/8388608)
                    else:
                        data[lauf] = dataraw[0]
                    size += 3
        elif sBPS == 8:
            fid.seek(readoffset+position, 0)
            if wFormatTag == 3: # read 16bit float
                WIZ_auxiliaries.standard_errorbox("unsupported Format Tag 3 with 8 bit data")
                size = -1
                ret["data"] = []
                ret["size"] = size
                return(ret)
                # dataraw = np.empty(DATABLOCKSIZE, dtype=np.float16)
                # size = fid.readinto(dataraw)
                # if tBPS == 32: #write 32 bit float
                #     data = dataraw.astype(np.float32)
                # else: # write to 16bit float
                #     data = dataraw.astype(np.float16)
            elif wFormatTag == 1: # read int8
                dataraw = np.empty(DATABLOCKSIZE, dtype=np.uint8)
                size = fid.readinto(dataraw)
                if tBPS == 32:
                    data = dataraw.astype(np.float32)/scl
                else:
                    data = dataraw.astype(np.float16)/scl
            else:
                WIZ_auxiliaries.standard_errorbox("unsupported Format Tag (wFormatTag): value other than 1 or 3 encountered")
                size = -1
            fid.close()
        else:
            WIZ_auxiliaries.standard_errorbox("no encodings except 8 (integer), 16, 24 and 32 bits are supported")
            #return invalid
            size = -1
            ret["data"] = []
            ret["size"] = size
            return(ret)
        fid.close()
        ret["data"] = data
        ret["size"] = size
        # duration = wavheader['data_nChunkSize']/pscale/wavheader['nSamplesPerSec']
        # ret["duration"] = duration
        #return data
        return ret
    
    def update_configyaml(key,dvalue):
        """
        open config_wizard.yaml, read metadata, update the entry with key 'key' with the value 'value'
        :param : key: metadata dict key
        :type : str
        :param : dvalue: value of 'key' ind the metadata dict
        :type : any
        :raises : none
        :return: errorstate
        :rtype: Boolean
        :return: value: metadata
        :rtype : dicht
        """
        errorstate = False
        value =[]
        try:
            stream = open("config_wizard.yaml", "r")
            metadata = yaml.safe_load(stream)
            stream.close()
            metadata[key] = dvalue
        except:
            errorstate = True
            value = "could not load config_wizard.yaml"
        try:
            stream = open("config_wizard.yaml", "w")
            yaml.dump(metadata, stream)
            stream.close()
        except:
            errorstate = True
            value = "could not write config_wizard.yaml"            
        return errorstate, value

    def fetch_configyaml(key):
        """
        open config_wizard.yaml, read metadata, 
        determine the entry with key 'key' with the value 'value' and return value
        :param : key: metadata dict key
        :type : str
        :raises : none
        :return: errorstate
        :rtype: Boolean
        :return: value: requested metadata or errormessage
        :rtype : any
        """
        errorstate = False
        value =[]
        try:
            stream = open("config_wizard.yaml", "r")
            metadata = yaml.safe_load(stream)
            stream.close()
            value = metadata[key]
        except:
            errorstate = True
            value = f"could not load key {key} from config_wizard.yaml"
        return errorstate, value

    def modulator_playlist_mode():
        """format of the station list of the audio modulator: 'csv' or 'm3u'
        (config_wizard.yaml, key modulator_playlist_mode; 'm3u' if missing or invalid)"""
        errorstate, value = auxiliaries.fetch_configyaml("modulator_playlist_mode")
        value = str(value).strip().lower() if not errorstate else ""
        return value if value in ("csv", "m3u") else "m3u"


    def show_infobox_withcheck(messagetext, checkboxtext):
        """
        QMessageBox which displays an info text 'messagetext' and adds a checkbox with explaining text 'checkboxtext'
        The state of the ok_button and the checkbox are returned
        
        :param messagetext : text which shall be displayed as message text
        :type : str
        :param checkboxtext : text for the checkbox
        :type : str
        :returns : ok_pressed
        :type : Boolean
        :returns: dont_show_again
        :type : Boolean 
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Information")
        msg.setText(messagetext)
        

        # OK-Button
        msg.setStandardButtons(QMessageBox.Ok)

        # Checkbox
        checkbox = QCheckBox(checkboxtext)
        msg.setCheckBox(checkbox)

        # Dialog anzeigen (modal)
        result = msg.exec_()   # PyQt6: msg.exec()

        # Rückgabewerte
        ok_pressed = (result == QMessageBox.Ok)
        dont_show_again = checkbox.isChecked()

        return ok_pressed, dont_show_again


    def standard_errorbox(errortext):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText(errortext)
        msg.setWindowTitle("Error")
        msg.exec_()

    def standard_infobox(infotext):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("ATTENTION")
        msg.setInformativeText(infotext)
        msg.setWindowTitle("ATTENTION")
        msg.exec_()


    def waiting_effect(function):
        """decorator for changing cursor to hourglass
        :param : function to be decorated
        :type : function
        :raises : none
        :return: none
        :rtype: none
        """
        def new_function(*args, **kwargs):
            print(f"args: {args})")
            QApplication.setOverrideCursor(Qt.BusyCursor)
            try:
                retval = function(*args, **kwargs)
                return retval
            except Exception as e:
                print("Error {}".format(e.args[0]))
                raise e
            finally:
                QApplication.restoreOverrideCursor()
        return new_function
    
    def generate_canvas(self,gridref,gridc,gridt,gui): #TODO: remove unelegant dummy issue
        """
        initialize plot canvas
        :param: gridref
        :type: ui.gridLayout_# object from GUI, e.g. self.gui.gridLayout_4 given by QT-designer
        :param: gridc, position of canvas, list with 4 entries: row_index, col_index, line_span, col_span
        :type: list 
        :param: gridt, position and span of toolbar with 4 entries: row_index, col_index, line_span, col_span
                if gridt[0] < 0 --> no toolbar is being assigned
        :type: list
        :param: gui
        :type: Ui_MainWindow (MyWizard) object instantiated by starter method in core program
        ...
        :raises: none
        ...
        :return: none
        :rtype: none
        """
        cref = {}
        figure = Figure()
        canvas = FigureCanvasQTAgg(figure)
        gridref.addWidget(canvas,gridc[0],gridc[1],gridc[2],gridc[3])
        ax = figure.add_subplot(111)
        if gridt[0] >= 0:
            #toolbar = NavigationToolbar(canvas, gui)  
            ##TODO TODO TODO: in case of transfer to auxi: gui must be reference to the instance of the gui in the class starter
            #gridref.addWidget(toolbar,gridt[0],gridt[1],gridt[2],gridt[3])
            toolbar = NavigationToolbar(canvas, gui)
            # toolbar.setFixedHeight(30)
            toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            gridref.addWidget(toolbar, gridt[0], gridt[1], gridt[2], gridt[3])
            #gridref.setColumnStretch(gridt[1], 1)

        cref["ax"] = ax
        cref["canvas"] = canvas
        cref["ax"].plot([], [])
        cref["canvas"].draw()
        return cref

# --- Auto-detection of the Red Pitaya (STEMlab) IP address ---
# Two independent methods, run in parallel by find_red_pitayas():
# 1. mDNS/zeroconf: Red Pitayas announce themselves as rp-xxxxxx.local
#    (works with Link-Local, but often fails in a router LAN: firewall on
#    UDP 5353, many other mDNS services, routers filtering multicast)
# 2. LAN scan: every host of the own IPv4 subnets gets one UDP packet, which
#    makes the OS resolve its MAC address; the ARP table is then searched for
#    the Red Pitaya MAC prefix. Needs no root/admin and no open port.

RP_MAC_PREFIXES = ("00:26:32",)   # Instrumentation Technologies d.d. (Red Pitaya)
RP_SCAN_MAX_HOSTS = 1024          # larger subnets (e.g. Link-Local /16) are not scanned


class RPListener:
    """zeroconf listener, only collects the service names; they are resolved
    after browsing, so that slow services of other devices cannot delay
    the Red Pitaya entries"""
    def __init__(self):
        self.services = []

    def remove_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        self.services.append((type, name))


def _valid_mac(mac):
    """Check if MAC is valid and not all zeros"""
    if mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"):
        return False
    return bool(re.match(r"([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac))


def _read_arp_table():
    """returns list of (ip, mac) from the OS ARP table, mac lower case with ':'"""
    results = []
    if platform.system() == "Linux":
        try:
            with open("/proc/net/arp") as f:
                next(f)  # skip header
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4:
                        results.append((parts[0], parts[3].lower()))
        except (OSError, StopIteration):
            pass
    else:
        # Windows and macOS: 'arp -a' works without admin rights
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            out = subprocess.check_output(["arp", "-a"], text=True, errors="ignore",
                                          timeout=5, creationflags=flags)
        except (OSError, subprocess.SubprocessError):
            return results
        pattern = r"(\d+\.\d+\.\d+\.\d+)\D+?((?:[0-9a-f]{1,2}[:-]){5}[0-9a-f]{1,2})\b"
        for ip, mac in re.findall(pattern, out, re.IGNORECASE):
            # macOS prints e.g. 0:26:32:f0:1:2 -> pad each byte to 2 digits
            mac = ":".join(b.zfill(2) for b in re.split("[:-]", mac.lower()))
            results.append((ip, mac))
    return [(ip, mac) for ip, mac in results if _valid_mac(mac)]


def _local_ipv4_networks():
    """IPv4 networks of all active interfaces except loopback and Link-Local
    with at most RP_SCAN_MAX_HOSTS hosts. Returns list of (own_ip, network)"""
    import ipaddress
    try:
        import psutil
    except ImportError:
        return []
    import socket
    nets = []
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
    except Exception:
        return []
    for ifname, alist in addrs.items():
        if ifname in stats and not stats[ifname].isup:
            continue
        for a in alist:
            if a.family != socket.AF_INET or not a.netmask:
                continue
            try:
                iface = ipaddress.ip_interface(f"{a.address}/{a.netmask}")
            except ValueError:
                continue
            if iface.ip.is_loopback or iface.ip.is_link_local:
                continue
            if iface.network.num_addresses > RP_SCAN_MAX_HOSTS + 2:
                continue
            nets.append((str(iface.ip), iface.network))
    return nets


def _probe_subnets(nets):
    """send one UDP packet to every host so that the OS fills its ARP table"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    try:
        for own_ip, net in nets:
            for host in net.hosts():
                ip = str(host)
                if ip == own_ip:
                    continue
                try:
                    sock.sendto(b"\0", (ip, 9))  # port 9 = discard
                except OSError:
                    # send buffer full or host unreachable: short pause, go on
                    time.sleep(0.002)
    finally:
        sock.close()


def _rp_name_from_mac(mac):
    """Red Pitaya host names are rp-<last 3 bytes of the MAC>"""
    return "rp-" + mac.replace(":", "")[-6:]


def _mdns_search(zc, listener):
    """resolve the collected mDNS services, keep the rp-xxxxxx devices"""
    from zeroconf import ServiceInfo, IPVersion
    found = []
    for stype, name in listener.services:
        if not name.lower().startswith("rp-"):
            continue
        info = ServiceInfo(stype, name)
        if not info.request(zc, 1500):
            continue
        for ip in info.parsed_addresses(IPVersion.V4Only):
            hostname = (info.server or name).split(".")[0]
            found.append((hostname, ip))
    return found


def find_red_pitayas(timeout=3.0):
    """
    Search connected Red Pitaya STEMlabs by mDNS and by LAN scan (see above).
    :param timeout: search duration in seconds
    :type timeout: float
    :returns: list of (hostname, ip) tuples without duplicates, mDNS results first
    :rtype: list
    """
    found = []
    zc = None
    try:
        zc = Zeroconf()
        listener = RPListener()
        ServiceBrowser(zc, ["_http._tcp.local.", "_ssh._tcp.local."], listener)
    except Exception as e:
        print(f"find_red_pitayas: mDNS not available: {e}")
        zc = None
    t0 = time.time()
    nets = _local_ipv4_networks()
    print(f"find_red_pitayas: scanning {[str(n) for _, n in nets]}")
    _probe_subnets(nets)
    # leave time for mDNS answers and ARP replies
    time.sleep(max(0.0, timeout - (time.time() - t0)))
    if zc is not None:
        try:
            found += _mdns_search(zc, listener)
        except Exception as e:
            print(f"find_red_pitayas: mDNS resolve failed: {e}")
        finally:
            zc.close()
    for ip, mac in _read_arp_table():
        if mac.startswith(RP_MAC_PREFIXES):
            found.append((_rp_name_from_mac(mac), ip))
    result = []
    for name, ip in found:
        if ip not in [r[1] for r in result]:
            result.append((name, ip))
    return result


#methods for wavheader manipulations 
class WAVheader_tools():

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Constants
        self.TEST = True    # Test Mode Flag for testing the App without a

    def basic_wavheader(self,icorr,irate,ifreq,bps,fsize,file_mod):
        """generate standard wavheader 
        Important: no check for the right datatypes in wavheader; if incorrect --> program crashes
        :param : icorr: icorr value for dat file
        :type : int
        :param : irate: irate value for dat file
        :type : int
        :param : ifreq: ifreq value for dat file
        :type : int
        :param : bps: bits per sample
        :type : int
        :param : fsize: file size in bytes
        :type : int
        :param : file_mod: file modification date/time as datetime object
        :type : datetime.datetime
        :raises : none
        :return: wavheader
        :rtype: dictionary
        """
        wavheader = {}
        wavheader['riff_chckID'] = str('RIFF')
        wavheader['filesize'] = fsize 
        wavheader['wave_string'] = str('WAVE')
        wavheader['fmt_chckID'] = str('fmt ')
        wavheader['fmt_nChunkSize'] = 16
        wavheader['wFormatTag'] = int(1)
        wavheader['nChannels'] = int(2)
        wavheader['nSamplesPerSec'] = int(irate)
        wavheader['nBitsPerSample'] = int(bps)
        wavheader['nBlockAlign'] = int(wavheader['nBitsPerSample']/8*2)
        wavheader['nAvgBytesPerSec'] = int(wavheader['nSamplesPerSec']*wavheader['nBitsPerSample']/4)
        wavheader['sdr_nChunkSize'] = 164
        wavheader['sdrtype_chckID'] = 'auxi'
        playtime = (fsize)/wavheader['nAvgBytesPerSec']
        starttime = [2000, 1, 1, 1, 0, 0, 0, 0]
        wavheader['starttime'] = starttime
        stoptime = [2000, 1, 1, 1, 0, 0, 0, 0]
        stoptime = [file_mod.year, file_mod.month, 0, file_mod.day, file_mod.hour, file_mod.minute, file_mod.second, int(1000*(playtime - np.floor(playtime)))]  
        
        wavheader['stoptime'] = stoptime
        wavheader['stoptime_dt'] =  datetime(stoptime[0],stoptime[1],stoptime[3],stoptime[4],stoptime[5],stoptime[6]) + timedelta(seconds = np.floor(playtime))
        wavheader['starttime_dt'] = wavheader['stoptime_dt'] - timedelta(seconds = np.floor(playtime))
        stt = wavheader['starttime_dt']
        if int(1000*(playtime - np.floor(playtime))) > 0:
            starttime = [stt.year, stt.month, 0, stt.day, stt.hour, stt.minute, stt.second - 1, int(1000*(1 - playtime + np.floor(playtime)))]  
        else:
            starttime = [stt.year, stt.month, 0, stt.day, stt.hour, stt.minute, stt.second, 0]  
        wavheader['starttime'] = starttime
        wavheader['centerfreq'] = ifreq
        wavheader['ADFrequency'] = 0
        wavheader['IFFrequency'] = 0
        wavheader['Bandwidth'] = 0
        wavheader['IQOffset'] = 0
        wavheader['nextfilename'] = ''
        wavheader['data_ckID'] = 'data'
        #aus filezize extrahieren
        wavheader['data_nChunkSize'] = wavheader['filesize'] - 208
        return(wavheader)


    def get_sdruno_header(self,*argv):
        """
        opens a file with name self.f1
        extracts meta information from SDR-wav-header_
        recognized formats: SDRUno, PERSEUS, SpectraVue
        closes file after headerreading

        :param : argv: tuple of parameters, the first one is mandatory: filename
        :general: (filename, wav type, )
        : option wav type: 'sdr','audio'. If set to 'audio' check for auxi/riff is skipped and an audio file is assumed
        :     then the header info is only valid until the sdrtype-field
        :type : tuple
        :return: dictionary wavheader containing the individual metadata items or False if unsuccessful
        :rtype: dictionary or Boolean
        """
        filename = argv[0]

        self.fileHandle = open(filename, 'rb')#TODO:replace self.f1 durch f1 als Übergabeparamezet
        wavheader={}
        wavheader['riff_chckID'] = str(self.fileHandle.read(4))
        if wavheader['riff_chckID'].find('RIFF') < 0:
            return False
        wavheader['filesize'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        wavheader['wave_string'] = str(self.fileHandle.read(4))
        wavheader['fmt_chckID'] = str(self.fileHandle.read(4))
        wavheader['fmt_nChunkSize'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        wavheader['wFormatTag'] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
        wavheader['nChannels'] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
        wavheader['nSamplesPerSec'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        wavheader['nAvgBytesPerSec'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        wavheader['nBlockAlign'] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
        wavheader['nBitsPerSample'] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
        bbb = (self.fileHandle.read(4)).decode('utf-8')
        wavheader['sdrtype_chckID'] = bbb
        if len(argv) > 1:
            if argv[1].find('audio') > -1 and not((wavheader['sdrtype_chckID'].find('auxi') > -1) or (wavheader['sdrtype_chckID'].find('rcvr') > -1)):
                return wavheader
            else:
                return False
        # exact chunk positions: fmt may be longer than 16 bytes, size fields may be wrong
        # (e.g. auxi with 164 bytes but sdr_nChunkSize = 172), see core/wavchunks.py
        try:
            chunkinfo = wavchunks.scan(filename)
        except wavchunks.WavChunkError as exc:
            print(f"get_sdruno_header: {exc}")
            self.fileHandle.close()
            return False
        for sdrtag in ("auxi", "rcvr"):
            if sdrtag in chunkinfo["chunks"]:
                self.fileHandle.seek(chunkinfo["chunks"][sdrtag][0])
                wavheader['sdrtype_chckID'] = (self.fileHandle.read(4)).decode('utf-8')
                break
        #####TODO: if sdrtype == 'auxi' do the next, else if 'rcvr' do PERSEUS, else error
        wavheader['sdr_nChunkSize'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        if  wavheader['sdrtype_chckID'].find('auxi') > -1:
            starttime=[0, 0, 0, 0, 0, 0, 0, 0]
            for i in range(8):
                starttime[i] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
            stoptime=[0, 0, 0, 0, 0, 0, 0, 0]
            for i in range(8):
                stoptime[i] = int.from_bytes(self.fileHandle.read(2), byteorder='little')
            wavheader['starttime'] = starttime
            wavheader['stoptime'] = stoptime
            wavheader['centerfreq'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
            wavheader['ADFrequency'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
            wavheader['IFFrequency'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
            wavheader['Bandwidth'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
            wavheader['IQOffset'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
            self.fileHandle.read(16) #dummy read, unused fields
            aaa = (self.fileHandle.read(96)).decode('utf-8')
            wavheader['nextfilename'] = aaa.replace('\\\\','\\')
            wavheader['starttime_dt'] =  datetime(starttime[0],starttime[1],starttime[3],starttime[4],starttime[5],starttime[6])
            try:
                wavheader['stoptime_dt'] =  datetime(stoptime[0],stoptime[1],stoptime[3],stoptime[4],stoptime[5],stoptime[6])
            except:
                #TODO: Hack for SDRangel files, where stoptime frequently is set to 0
                wavheader['stoptime_dt'] = wavheader['starttime_dt']
            ccc = (self.fileHandle.read(4)).decode('utf-8')
            wavheader['diff'] = 0
            wavheader['data_ckID'] = ccc
            wavheader['data_nChunkSize'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
        else:
            if wavheader['sdrtype_chckID'].find('rcvr') > -1:
                ##print('rcvr reached in wavheader reader')
                wavheader['centerfreq'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
                wavheader['SamplingRateIdx'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
                wavheader['starttime_epoch'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
                startt = datetime.fromtimestamp(wavheader['starttime_epoch'])
                wavheader['starttime_dt'] = startt
                wavheader['wAttenId'] = int.from_bytes(self.fileHandle.read(2), byteorder='little', signed=False)
                wavheader['bAdcPresel'] = str(self.fileHandle.read(1))
                wavheader['bAdcPreamp'] = str(self.fileHandle.read(1))
                wavheader['bAdcDither'] = str(self.fileHandle.read(1))
                wavheader['bSpare'] = str(self.fileHandle.read(1))
                wavheader['rsrvd'] = str(self.fileHandle.read(16))
                ccc = (self.fileHandle.read(4)).decode('utf-8')
                wavheader['data_ckID'] = ccc
                wavheader['data_nChunkSize'] = int.from_bytes(self.fileHandle.read(4), byteorder='little')
                
                if wavheader['SamplingRateIdx'] == 0:
                    wavheader['samplingrate'] = 125000
                elif wavheader['SamplingRateIdx'] == 1:
                    wavheader['samplingrate'] = 250000
                elif wavheader['SamplingRateIdx'] == 2:
                    wavheader['samplingrate'] = 500000
                elif wavheader['SamplingRateIdx'] == 3:
                    wavheader['samplingrate'] = 1000000
                elif wavheader['SamplingRateIdx'] == 4:
                    wavheader['samplingrate'] = 2000000
                else:
                    print('Wrong samplingrate in fileheader')
                # write dummy entries for wavtable
                wavheader['ADFrequency'] = 0
                wavheader['IFFrequency'] = 0
                wavheader['Bandwidth'] = 0
                wavheader['IQOffset'] = 0
                wavheader['nextfilename'] = ''
                #modify field to auxi format
                ## calculate stoptime from SR, headersize, #samples, bytespersample and starttime
                playseconds = wavheader['data_nChunkSize']/wavheader['nAvgBytesPerSec']
                stoptt = startt + timedelta(seconds= np.round(playseconds))
                wavheader['stoptime_dt'] =  stoptt
                # recode starttime and stoptime to auxi format
                wavheader['starttime'] = [startt.year, startt.month, 0, startt.day, startt.hour, startt.minute, startt.second, 0]
                wavheader['stoptime'] = [stoptt.year, stoptt.month, 0, stoptt.day, stoptt.hour, stoptt.minute, stoptt.second, 0]
                wavheader['nextfilename'] = ('')    
            else:
                #TODO: implement raw format if wanted
                ##print('unrecognized SDR')
                return False
            #self.check_wavheader_timeconsistency(filename, wavheader)
        # data chunk as located by wavchunks.scan (not the bytes following the fixed-size fields)
        wavheader['data_ckID'] = 'data'
        wavheader['data_nChunkSize'] = chunkinfo['data_nChunkSize']
        wavheader['data_offset'] = chunkinfo['data_offset']
        if chunkinfo['repaired']:
            print(f"get_sdruno_header {os.path.basename(filename)}: " + "; ".join(chunkinfo['repaired']))
        #checking informatio for timestamps
        diff = (wavheader['stoptime_dt']-wavheader['starttime_dt']).seconds + (wavheader['stoptime'][7] - wavheader['starttime'][7])/1000
        diff *= wavheader['nSamplesPerSec']
        wavheader['diff'] = int(np.ceil(diff) * wavheader['nBlockAlign'])
        wavheader['true_datachunksize'] = os.stat(filename).st_size - wavheader['data_offset']

        self.fileHandle.close()
        return(wavheader)

    def check_wavheader_timeconsistency(self, wavheader):
        """check if the difference between starttime and stoptime in the wavheader is consistent with the filesize
        the tolerance is currently 1s of discrepancy; usually the discrepancy is caused by slightly wrong entries in the
        fields for stop and starttimes of the recording; frequently the milliseconds entry is questionable

        :parameters: wavheader
        :type: dict
        :returns: True if consistent, False if inconsistent
        :rtype: Boolean
        """
        tolerance = np.ceil((wavheader['nSamplesPerSec'] * wavheader['nBlockAlign']))
        discrepancy = np.abs(wavheader['diff']  - wavheader['true_datachunksize'])
        if discrepancy > tolerance:
            print("filezize is inconsistent with headertimes; some functions will be blocked")
            return False
        return True

    def write_sdruno_header(self,wavfilename,wavheader,ovwrt_flag):       
        """write auxi wavheader to the beginning of the current file 'wavfilename'
        if ovwrt_flag == True: 
            overwrite the first 216 bytes of an existing file with wavheader
        else:
            write a new file with the wavheader only; size is always 216 bytes
        
        Important: no check for the right datatypes in wavheader; if incorrect --> program crashes
        only auxi Format can be written. rcvr is not supported
        The Formattag is preserved

        :param : wavtargetfilename
        :type : str
        :param : wavheader
        :type : dictionary
        :param : ovwrt_flag
        :type : boolean
        :raises : none
        :return: none
        """
        ###print("wavheader writer reached")
        if wavheader['filesize'] > 2147483647:
            wavheader['filesize'] = int(2147483647)
            wavheader['data_nChunkSize'] = int(wavheader['filesize'] - 208)
            #print(wavheader['fmt_nChunkSize'])
        
        # This writer always writes a 16-byte fmt chunk and the 164 bytes of auxi fields.
        # When overwriting the header of an existing file, the samples must stay where they
        # are: the auxi chunk is padded up to the existing start of the data (see core/wavchunks.py).
        auxi_content = 164
        if ovwrt_flag == True:
            try:
                old_offset = wavchunks.data_offset(wavfilename)
            except (wavchunks.WavChunkError, OSError):
                old_offset = wavchunks.STANDARD_DATA_OFFSET    # header still reserved/empty
            auxi_content = old_offset - 52    # RIFF 12 + fmt 24 + auxi 8 + data 8 = 52
            if auxi_content < 164:
                auxiliaries.standard_errorbox(f"Cannot overwrite the header of {os.path.basename(wavfilename)}: "
                                              f"its data start at byte {old_offset}, an auxi header needs at least 216 bytes. "
                                              "The file was not changed.")
                return False
        wavheader['fmt_nChunkSize'] = 16
        wavheader['sdr_nChunkSize'] = auxi_content
        if ovwrt_flag == True:
            fid = open(wavfilename, 'r+b')
            fid.seek(0)
        else:
            fid = open(wavfilename, 'wb')
        riff = "RIFF"
        wav = "WAVE"
        fmt = "fmt "
        fid.write(pack("<4sL4s", riff.encode('ascii'), wavheader['filesize'], wav.encode('ascii')))
        fid.write(pack("<4sI", fmt.encode('ascii'), wavheader['fmt_nChunkSize']))
        fid.write(pack("<hhllhh", wavheader['wFormatTag'], wavheader['nChannels'], wavheader['nSamplesPerSec'], 
                       wavheader['nAvgBytesPerSec'], wavheader['nBlockAlign'], wavheader['nBitsPerSample']))
        fid.write(pack("<4sl", wavheader['sdrtype_chckID'][0:4].encode('ascii'), wavheader['sdr_nChunkSize']))

        fid.write(pack("<16h", wavheader['starttime'][0], wavheader['starttime'][1], wavheader['starttime'][2], 
                       wavheader['starttime'][3], wavheader['starttime'][4], wavheader['starttime'][5], 
                       wavheader['starttime'][6], wavheader['starttime'][7], wavheader['stoptime'][0], 
                       wavheader['stoptime'][1], wavheader['stoptime'][2], wavheader['stoptime'][3], 
                       wavheader['stoptime'][4], wavheader['stoptime'][5], wavheader['stoptime'][6], wavheader['stoptime'][7]))
        fid.write(pack("<l", wavheader['centerfreq']))
        # Write ADFrequency, IFFrequency, Bandwidth, and IQOffset as long integers
        fid.write(pack('<l', wavheader['ADFrequency']))
        fid.write(pack('<l', wavheader['IFFrequency']))
        fid.write(pack('<l', wavheader['Bandwidth']))
        fid.write(pack('<l', wavheader['IQOffset']))

        # Write Unused array as four long integers
        dum = 0
        for i in range(4):
            fid.write(pack('<l', dum))

        # Write up to 96 characters of nextfilename as ASCII characters
        for i in range(min(96, len(wavheader['nextfilename']))):
            fid.write(pack('<c', bytes(wavheader['nextfilename'][i], 'ascii')))

        # Write spaces to fill up to 96 characters if nextfilename is shorter
        if len(wavheader['nextfilename']) < 96:
            for i in range(len(wavheader['nextfilename']), 96):
                fid.write(pack('<c', b' '))

        # zero padding of the auxi chunk up to the existing data start (overwrite mode)
        if auxi_content > 164:
            fid.write(b'\x00' * (auxi_content - 164))

        # Write data_ckID and data_nChunkSize
        wavheader['data_ckID'] = 'data'
        fid.write(pack("<4sl", wavheader['data_ckID'][0:4].encode('ascii'), wavheader['data_nChunkSize']))
        fid.close()



class TextInputDialog(QDialog):
    """A dialog for entering text input with multiple fields."""

    __slots__ = ["parameters"]

    SigButtonpressed = pyqtSignal(str)
    SigSlidergain = pyqtSignal(int)

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
        self.test_button = QPushButton("Test", self)
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
        button_layout.addWidget(self.test_button)
        
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Signals
        # self.ok_button.clicked.connect(self.accept)
        # self.cancel_button.clicked.connect(self.reject)
        self.ok_button.clicked.connect(self.OKbutton_handler)
        self.cancel_button.clicked.connect(self.reject)
        self.test_button.clicked.connect(self.Testbutton_handler)

        # add slidergain widget
        self.slider_gain = QSlider(Qt.Horizontal, self)
        layout.addWidget(QLabel("Gain:"))
        layout.addWidget(self.slider_gain)
        self.slider_gain.setRange(0, 100)  # Set range from -50 to 50
        self.slider_gain.setTickPosition(QSlider.TicksBelow)
        self.slider_gain.setValue(80)  # Set default value to 100
        self.slider_gain.setTickInterval(5)
        self.slider_gain.valueChanged.connect(self.slider_gain_changed)

    def slider_gain_changed(self, value):
        """Slot for handling changes to the gain slider."""
        #print(f"Gain slider value changed: {value}")
        self.SigSlidergain.emit(value)  


    def Testbutton_handler(self):
        """Testbutton handler for debugging purposes."""
        print("Test button clicked")
        self.SigButtonpressed.emit("Test")

    def OKbutton_handler(self):
        """OK button handler to return the input values."""
        print("OK button clicked")
        self.SigButtonpressed.emit("OK")
        # self.accept()  # Close the dialog and return QDialog.Accepted
        #self.done(QDialog.Accepted)

    def getInputs(self):

        """Returns the text from the input fields."""
        # return self.line_edit1.text(), self.line_edit2.text()
        for key in self.inputfields.keys():
            line_edit = getattr(self, f'line_edit_{key}', None)
            if line_edit:
                self.inputfields[key] = line_edit.text()
        return self.inputfields