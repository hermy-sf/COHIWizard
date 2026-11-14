"""Station Editor: creates and edits the station lists (extended m3u) of the audio
modulator of the player (modulator types 'IQ band and audio modulator' and
'audio modulator only'). The format is described in dev_drivers/playlist_paths.py.

Built after abstract_module.py (model / controller / view).
"""
import logging
import os
from pathlib import Path

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from auxiliaries import auxiliaries as auxi
from dev_drivers.playlist_paths import (read_station_m3u_raw, write_station_m3u, entry_path,
                                        parse_frequency, is_url, PARAM_KEYS)

AUDIO_FILTER = ("Audio files (*.mp3 *.wav *.flac *.ogg *.oga *.opus *.m4a *.aac *.wma *.aiff *.aif);;"
                "All files (*)")
M3U_FILTER = "station list m3u (*.m3u *.m3u8)"
COL_FREQ, COL_BW, COL_NAME, COL_PLAYLIST = range(4)
COL_TITLE, COL_ENTRY = range(2)
PARAM_FIELDS = {"BW": "lineEdit_bw", "FILEPREFIX": "lineEdit_prefix", "LOFREQ": "lineEdit_lo",
                "SAMPLERATE": "lineEdit_sr", "SILENCE": "lineEdit_silence",
                "MODDEPTH": "lineEdit_moddepth", "RECLENGTH": "lineEdit_reclength",
                "OUTPUTFILE": "lineEdit_outputfile"}
BAD = QColor(255, 200, 200)


def title_from_entry(entry):
    """title for #EXTINF from a file name or URL: 'R_Mey_Annabelle.mp3' -> 'R Mey Annabelle'"""
    name = entry.rstrip("/").replace("\\", "/").split("/")[-1] or entry
    if not is_url(entry) or "." in name:
        name = os.path.splitext(name)[0]
    return name.replace("_", " ").replace("%20", " ").strip() or entry


class station_editor_m(QObject):

    def __init__(self):
        super().__init__()

        ######################  Mandatory part, do not remove: ###############
        self.mdl = {}
        logging.getLogger().setLevel(logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        warning_handler = logging.StreamHandler()
        debug_handler = logging.FileHandler("system_log.log")
        warning_handler.setLevel(logging.WARNING)
        debug_handler.setLevel(logging.DEBUG)
        warning_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        debug_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        warning_handler.setFormatter(warning_format)
        debug_handler.setFormatter(debug_format)
        self.logger.addHandler(warning_handler)
        self.logger.addHandler(debug_handler)
        self.logger.debug('Init logger in station_editor reached')
        #####################################################################

        self.mdl["se_path"] = ""          # file of the station list, "" = not yet saved
        self.mdl["se_params"] = {}        # {KEY: text} of the global #EXTPARAM lines
        self.mdl["se_stations"] = []      # [{"name", "freq", "bw", "titles": [[title, entry]]}]
        self.mdl["se_dirty"] = False      # unsaved changes


class station_editor_c(QObject):

    ########## mandatory Signals, do not remove ####################
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)
    ################################################################

    def __init__(self, station_editor_m):
        super().__init__()
        self.m = station_editor_m.mdl
        self.logger = station_editor_m.logger

    def base_dir(self):
        """folder for relative entries: that of the station list, before the first save
        the folder of the last station list"""
        if self.m["se_path"]:
            return os.path.dirname(os.path.abspath(self.m["se_path"]))
        err, last = auxi.fetch_configyaml("last_station_editor_path")
        return last if not err and os.path.isdir(str(last)) else os.getcwd()

    def load(self, path):
        params, stations, problems = read_station_m3u_raw(path)
        if not params and not stations and problems:
            return problems
        self.m["se_path"], self.m["se_params"], self.m["se_stations"] = path, params, stations
        self.m["se_dirty"] = False
        return problems

    def save(self, path):
        """writes the station list; files below the folder of the list are stored with
        relative paths, so that the folder can be moved as a whole"""
        base = os.path.dirname(os.path.abspath(path))
        stations = []
        for sta in self.m["se_stations"]:
            titles = []
            for title, entry in sta["titles"]:
                if not is_url(entry) and os.path.isabs(entry):
                    try:
                        rel = os.path.relpath(entry, base)
                        if not rel.startswith(".."):
                            entry = rel.replace("\\", "/")
                    except ValueError:      # other drive (Windows)
                        pass
                titles.append([title, entry])
            stations.append(dict(sta, titles=titles))
        write_station_m3u(path, self.m["se_params"], stations)
        self.m["se_stations"], self.m["se_path"], self.m["se_dirty"] = stations, path, False

    def check(self):
        """problems of the station list for the user -> (messages, bad station rows,
        {row: missing title rows})"""
        msgs, bad_rows, missing = [], set(), {}
        p = self.m["se_params"]
        prefix, base = p.get("FILEPREFIX", ""), self.base_dir()

        def number(text, what, unit=1e3):
            try:
                return parse_frequency(text, unit) if str(text).strip() else None
            except ValueError:
                msgs.append(f"{what}: cannot read '{text}'")
                return None

        bw_default = number(p.get("BW", ""), "Audio bandwidth") or 9000.0
        lo, sr = number(p.get("LOFREQ", ""), "LO frequency"), number(p.get("SAMPLERATE", ""), "Sample rate")
        used = {}
        for row, sta in enumerate(self.m["se_stations"]):
            name = sta["name"] or f"station {row + 1}"
            freq = number(sta["freq"], f"'{name}': frequency")
            bw = number(sta["bw"], f"'{name}': bandwidth") or bw_default
            if freq is None:
                if not str(sta["freq"]).strip():
                    msgs.append(f"'{name}': no frequency")
                bad_rows.add(row)
            elif freq in used:
                msgs.append(f"'{name}': {freq / 1e3:g} kHz is already used by '{used[freq]}'")
                bad_rows.add(row)
            else:
                used[freq] = name
                if lo is not None and sr is not None and (freq - bw / 2 < lo - sr / 2 or freq + bw / 2 > lo + sr / 2):
                    msgs.append(f"'{name}': {freq / 1e3:g} kHz lies outside LO +- sample rate/2 "
                                f"({(lo - sr / 2) / 1e3:g} - {(lo + sr / 2) / 1e3:g} kHz)")
                    bad_rows.add(row)
            if not sta["titles"]:
                msgs.append(f"'{name}': no titles")
                bad_rows.add(row)
            gone = [i for i, (_, e) in enumerate(sta["titles"])
                    if not is_url(entry_path(e, prefix, base)) and not os.path.isfile(entry_path(e, prefix, base))]
            if gone:
                missing[row] = gone
                msgs.append(f"'{name}': {len(gone)} file(s) not found")
                bad_rows.add(row)
        return msgs, bad_rows, missing


class station_editor_v(QObject):

    ########## mandatory Signals, do not remove ####################
    SigUpdateGUI = pyqtSignal(object)
    SigActivateOtherTabs = pyqtSignal(str,str,object)
    SigRelay = pyqtSignal(str,object)
    ################################################################

    def __init__(self, gui, station_editor_c, station_editor_m):
        super().__init__()

        ######################  Mandatory part, do not remove: ###############
        self.m = station_editor_m.mdl
        self.station_editor_c = station_editor_c
        self.gui = gui # is assigned by core ! mandatory
        self.logger = station_editor_m.logger
        self.station_editor_c.SigRelay.connect(self.rxhandler)
        self.station_editor_c.SigRelay.connect(self.SigRelay.emit)
        ######################################################################
        self._filling = False          # tables are being filled: no itemChanged handling
        self.init_station_editor_ui()

    # ------------------------------------------------------------------ setup
    def init_station_editor_ui(self):
        g = self.gui
        for table, widths in ((g.tableWidget_stations, (170, 160, 260)), (g.tableWidget_titles, (380,))):
            for col, w in enumerate(widths):
                table.setColumnWidth(col, w)
        g.pushButton_new.clicked.connect(self.cb_new)
        g.pushButton_open.clicked.connect(self.cb_open)
        g.pushButton_save.clicked.connect(self.cb_save)
        g.pushButton_saveas.clicked.connect(self.cb_saveas)
        g.pushButton_toplayer.clicked.connect(self.cb_toplayer)
        g.pushButton_addstation.clicked.connect(self.cb_addstation)
        g.pushButton_removestation.clicked.connect(self.cb_removestation)
        g.pushButton_addfiles.clicked.connect(self.cb_addfiles)
        g.pushButton_addurl.clicked.connect(self.cb_addurl)
        g.pushButton_removetitle.clicked.connect(self.cb_removetitle)
        g.pushButton_up.clicked.connect(lambda: self.cb_movetitle(-1))
        g.pushButton_down.clicked.connect(lambda: self.cb_movetitle(1))
        g.tableWidget_stations.currentCellChanged.connect(lambda *a: self.fill_titles())
        g.tableWidget_stations.itemChanged.connect(self.station_item_changed)
        g.tableWidget_titles.itemChanged.connect(self.title_item_changed)
        for key, name in PARAM_FIELDS.items():
            getattr(g, name).textEdited.connect(lambda text, key=key: self.param_changed(key, text))
        # files from the file manager can be dropped onto the titles
        self._drop_target = g.tableWidget_titles.viewport()
        self._drop_target.setAcceptDrops(True)
        self._drop_target.installEventFilter(self)
        self.fill_all()

    # ------------------------------------------------------------------ display
    def selected_station(self):
        row = self.gui.tableWidget_stations.currentRow()
        return row if 0 <= row < len(self.m["se_stations"]) else None

    @staticmethod
    def playlist_summary(sta):
        n = len(sta["titles"])
        if n == 1:
            return sta["titles"][0][1]
        return f"{n} titles" if n else "(empty)"

    def fill_all(self, select=0):
        self._filling = True
        g = self.gui
        for key, name in PARAM_FIELDS.items():
            getattr(g, name).setText(self.m["se_params"].get(key, ""))
        t = g.tableWidget_stations
        t.setRowCount(len(self.m["se_stations"]))
        for row, sta in enumerate(self.m["se_stations"]):
            for col, text in ((COL_FREQ, sta["freq"]), (COL_BW, sta["bw"]), (COL_NAME, sta["name"]),
                              (COL_PLAYLIST, self.playlist_summary(sta))):
                it = QTableWidgetItem(text)
                if col == COL_PLAYLIST:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    it.setToolTip("titles: see the list below")
                t.setItem(row, col, it)
        self._filling = False
        if self.m["se_stations"]:
            t.setCurrentCell(min(max(select, 0), len(self.m["se_stations"]) - 1), COL_NAME)
        self.fill_titles()
        self.show_file()

    def fill_titles(self, select=None):
        self._filling = True
        t = self.gui.tableWidget_titles
        row = self.selected_station()
        titles = self.m["se_stations"][row]["titles"] if row is not None else []
        t.setRowCount(len(titles))
        for i, (title, entry) in enumerate(titles):
            t.setItem(i, COL_TITLE, QTableWidgetItem(title))
            t.setItem(i, COL_ENTRY, QTableWidgetItem(entry))
        self._filling = False
        self.gui.groupBox_titles.setEnabled(row is not None)
        if select is not None and titles:
            t.setCurrentCell(min(max(select, 0), len(titles) - 1), COL_ENTRY)
        self.show_check()

    def show_file(self):
        p = self.m["se_path"]
        self.gui.label_file.setText((Path(p).name if p else "(new station list)") + (" *" if self.m["se_dirty"] else ""))
        self.gui.label_file.setToolTip(p)

    def show_check(self):
        """problems in the label below, bad stations and missing files in red"""
        msgs, bad_rows, missing = self.station_editor_c.check()
        self._filling = True
        st = self.gui.tableWidget_stations
        for row in range(st.rowCount()):
            for col in range(st.columnCount()):
                it = st.item(row, col)
                if it is not None:
                    it.setBackground(BAD if row in bad_rows else QBrush())
            sum_item = st.item(row, COL_PLAYLIST)
            if sum_item is not None and row < len(self.m["se_stations"]):
                sum_item.setText(self.playlist_summary(self.m["se_stations"][row]))
        sel = self.selected_station()
        tt = self.gui.tableWidget_titles
        for i in range(tt.rowCount()):
            it = tt.item(i, COL_ENTRY)
            if it is not None:
                gone = sel is not None and i in missing.get(sel, [])
                it.setBackground(BAD if gone else QBrush())
                it.setToolTip("file not found" if gone else "")
        self._filling = False
        n = len(self.m["se_stations"])
        if msgs:
            more = f"\n... and {len(msgs) - 8} more" if len(msgs) > 8 else ""
            self.gui.label_check.setText("Check:\n- " + "\n- ".join(msgs[:8]) + more)
        else:
            self.gui.label_check.setText(f"Check: {n} station(s), no problems found." if n else "")
        self.show_file()

    def changed(self):
        self.m["se_dirty"] = True
        self.show_check()

    # ------------------------------------------------------------------ edits
    def station_item_changed(self, item):
        if self._filling or item.row() >= len(self.m["se_stations"]):
            return
        key = {COL_FREQ: "freq", COL_BW: "bw", COL_NAME: "name"}.get(item.column())
        if key:
            self.m["se_stations"][item.row()][key] = item.text().strip()
            self.changed()

    def title_item_changed(self, item):
        row = self.selected_station()
        if self._filling or row is None:
            return
        titles = self.m["se_stations"][row]["titles"]
        if item.row() < len(titles):
            titles[item.row()][item.column()] = item.text().strip()
            self.changed()

    def param_changed(self, key, text):
        self.m["se_params"][key] = text.strip()
        self.changed()

    def cb_addstation(self):
        self.m["se_stations"].append({"name": "new station", "freq": "", "bw": "", "titles": []})
        self.m["se_dirty"] = True
        row = len(self.m["se_stations"]) - 1
        self.fill_all(select=row)
        self.gui.tableWidget_stations.editItem(self.gui.tableWidget_stations.item(row, COL_FREQ))

    def cb_removestation(self):
        row = self.selected_station()
        if row is None:
            return
        del self.m["se_stations"][row]
        self.m["se_dirty"] = True
        self.fill_all(select=row)

    def add_titles(self, entries):
        row = self.selected_station()
        if row is None:
            auxi.standard_infobox("Please add or select a station first.")
            return
        titles = self.m["se_stations"][row]["titles"]
        titles += [[title_from_entry(e), e] for e in entries]
        self.m["se_dirty"] = True
        self.fill_titles(select=len(titles) - 1)

    def cb_addfiles(self):
        err, last = auxi.fetch_configyaml("last_station_editor_audio_path")
        start = last if not err and os.path.isdir(str(last)) else self.station_editor_c.base_dir()
        files, _ = QFileDialog.getOpenFileNames(self.gui.tableWidget_titles.window(), "Add audio files",
                                                start, AUDIO_FILTER)
        if files:
            auxi.update_configyaml("last_station_editor_audio_path", os.path.dirname(files[0]))
            self.add_titles([os.path.abspath(f) for f in files])

    def cb_addurl(self):
        url, ok = QInputDialog.getText(self.gui.tableWidget_titles.window(), "Add URL",
                                       "Web stream or file on a web server (http://, https://):")
        if ok and url.strip():
            self.add_titles([url.strip()])

    def cb_removetitle(self):
        row, i = self.selected_station(), self.gui.tableWidget_titles.currentRow()
        if row is None or not 0 <= i < len(self.m["se_stations"][row]["titles"]):
            return
        del self.m["se_stations"][row]["titles"][i]
        self.m["se_dirty"] = True
        self.fill_titles(select=i)

    def cb_movetitle(self, step):
        row, i = self.selected_station(), self.gui.tableWidget_titles.currentRow()
        if row is None:
            return
        titles = self.m["se_stations"][row]["titles"]
        j = i + step
        if 0 <= i < len(titles) and 0 <= j < len(titles):
            titles[i], titles[j] = titles[j], titles[i]
            self.m["se_dirty"] = True
            self.fill_titles(select=j)

    def eventFilter(self, obj, event):
        """files and URLs dropped from the file manager onto the titles"""
        # compared with the stored reference: at program exit the table may already be deleted
        if obj is self._drop_target:
            if event.type() in (QEvent.DragEnter, QEvent.DragMove) and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            if event.type() == QEvent.Drop and event.mimeData().hasUrls():
                entries = [u.toLocalFile() if u.isLocalFile() else u.toString() for u in event.mimeData().urls()]
                self.add_titles([e for e in entries if e])
                event.acceptProposedAction()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------ files
    def discard_ok(self):
        if not self.m["se_dirty"]:
            return True
        answer = QMessageBox.question(self.gui.tableWidget_titles.window(), "Station Editor",
                                      "The station list has unsaved changes. Discard them?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def cb_new(self):
        if not self.discard_ok():
            return
        self.m["se_path"], self.m["se_params"], self.m["se_stations"], self.m["se_dirty"] = "", {}, [], False
        self.fill_all()

    def cb_open(self):
        if not self.discard_ok():
            return
        path, _ = QFileDialog.getOpenFileName(self.gui.tableWidget_titles.window(), "Open station list",
                                              self.station_editor_c.base_dir(), M3U_FILTER)
        if not path:
            return
        problems = self.station_editor_c.load(path)
        auxi.update_configyaml("last_station_editor_path", os.path.dirname(path))
        if problems:
            auxi.standard_infobox(f"{Path(path).name}:\n\n- " + "\n- ".join(problems[:15]))
        self.fill_all()

    def cb_save(self):
        if not self.m["se_path"]:
            return self.cb_saveas()
        return self.save_to(self.m["se_path"])

    def cb_saveas(self):
        start = self.m["se_path"] or os.path.join(self.station_editor_c.base_dir(), "stations.m3u")
        path, _ = QFileDialog.getSaveFileName(self.gui.tableWidget_titles.window(), "Save station list",
                                              start, M3U_FILTER)
        if not path:
            return False
        if not path.lower().endswith((".m3u", ".m3u8")):
            path += ".m3u"
        return self.save_to(path)

    def save_to(self, path):
        try:
            self.station_editor_c.save(path)
        except OSError as exc:
            auxi.standard_errorbox(f"Cannot save {path}: {exc.strerror or exc}")
            return False
        auxi.update_configyaml("last_station_editor_path", os.path.dirname(path))
        self.fill_all(select=self.gui.tableWidget_stations.currentRow())
        return True

    def cb_toplayer(self):
        """save (if necessary) and load the station list into the player"""
        if (self.m["se_dirty"] or not self.m["se_path"]) and not self.cb_save():
            return
        self.SigRelay.emit("cexex_xcore", ["load_station_list", self.m["se_path"]])

    # ------------------------------------------------------------------ standard
    def rxhandler(self,_key,_value):
        """handles remote calls from other modules via Signal SigRX(_key,_value)"""
        if _key.find("cm_station_editor") == 0 or _key.find("cm_all_") == 0:
            self.m[_value[0]] = _value[1]
        if _key.find("cui_station_editor") == 0:
            _value[0](_value[1]) #still unused, reserved for future applications
        if _key.find("cexex_station_editor") == 0  or _key.find("cexex_all_") == 0:
            if  _value[0].find("updateGUIelements") == 0:
                self.updateGUIelements()
            if  _value[0].find("reset_GUI") == 0:
                self.reset_GUI()
            if  _value[0].find("logfilehandler") == 0:
                self.logfilehandler(_value[1])

    def logfilehandler(self,_value):
        if _value is False:
            self.logger.debug("station_editor: INACTIVATE LOGGING")
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.debug("station_editor: REACTIVATE LOGGING")
            self.logger.setLevel(logging.DEBUG)

    def updateGUIelements(self):
        return

    def reset_GUI(self):
        # the station list is independent of the IQ file: nothing to reset
        return
