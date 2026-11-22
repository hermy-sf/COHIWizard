"""Download of IQ recordings from the COHIRADIA archive (cohiradia.org, hosted by
radiomuseum.org) into the local folder IQ_files.

The archive web page (https://www.cohiradia.org/en/archiv/) fills its table from the
same JSON interface that is used here:
    <ARCHIVE_BASE>/api/metadata            list of all recordings
    <ARCHIVE_BASE>/api/metadata/<id>       details of one recording
    <ARCHIVE_BASE>/view/recordings/<id>    page with the wav parts (2 GB each)
    <ARCHIVE_BASE>/files/wav/<id>?part=<n> wav part n (supports HTTP Range -> resume)
"""
import json
import os
import re
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QDialog, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QVBoxLayout)

ARCHIVE_BASE = "https://cohiradia.radiomuseum.org"
ARCHIVE_PAGE = "https://www.cohiradia.org/en/archiv/"
DETAIL_PAGE = "https://www.cohiradia.org/en/archiv/detail/?id={}"
USER_AGENT = "COHIWizard"
TIMEOUT = 30
CHUNK = 1024 * 1024
SPEED_TEST_BYTES = 4 * 1024 * 1024

_PART_RE = re.compile(r'<a href="\.\./\.\./files/wav/(\d+)\?part=(\d+)">([^<]+)</a>\s*\(([\d.]+)\s*GB\)')


def _open(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def fetch_json(url):
    with _open(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_recordings():
    """all IQ recordings of the archive (without the synthetic ones), newest first"""
    recs = [r for r in fetch_json(f"{ARCHIVE_BASE}/api/metadata") if r.get("type") != "synthetic"]
    recs.sort(key=lambda r: r.get("startTimestamp") or "", reverse=True)
    return recs


def fetch_parts(rec_id):
    """wav parts of a recording: list of dicts name, url, size_gb (from the download page)"""
    with _open(f"{ARCHIVE_BASE}/view/recordings/{rec_id}") as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parts = []
    for rid, part, name, size in _PART_RE.findall(html):
        parts.append({"name": name.strip(), "size_gb": float(size),
                      "url": f"{ARCHIVE_BASE}/files/wav/{rid}?part={part}"})
    return parts


def measure_speed(url):
    """download rate in bytes/s from a short range request (None if not measurable)"""
    try:
        t0 = time.time()
        with _open(url, {"Range": f"bytes=0-{SPEED_TEST_BYTES - 1}"}) as resp:
            n = len(resp.read())
        dt = time.time() - t0
        return n / dt if dt > 0 and n > 0 else None
    except Exception:
        return None


def safe_dirname(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")[:60] or "recording"


def format_duration(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h} h {m:02d} min" if h else (f"{m} min {s:02d} s" if m else f"{s} s")


class DownloadWorker(QObject):
    """downloads the files [(url, destination)] one after the other; an interrupted file
    (<destination>.part) is continued with an HTTP Range request, complete files are skipped"""
    SigProgress = pyqtSignal(object, object, str)   # bytes done, bytes total, current file name
    SigFinished = pyqtSignal(bool, str)             # success, message

    def __init__(self, files):
        super().__init__()
        self.files = files
        self.cancel = False

    def run(self):
        try:
            sizes = []
            for url, _dest in self.files:
                with _open(url, {"Range": "bytes=0-0"}) as resp:
                    rng = resp.headers.get("Content-Range", "")
                    sizes.append(int(rng.rsplit("/", 1)[1]) if "/" in rng
                                 else int(resp.headers.get("Content-Length", 0)))
            total = sum(sizes)
            done = 0
            for (url, dest), size in zip(self.files, sizes):
                name = os.path.basename(dest)
                if os.path.isfile(dest) and os.path.getsize(dest) == size:
                    done += size
                    self.SigProgress.emit(done, total, name)
                    continue
                part = dest + ".part"
                have = os.path.getsize(part) if os.path.isfile(part) else 0
                if have > size:
                    have = 0
                headers = {"Range": f"bytes={have}-"} if have else {}
                with _open(url, headers) as resp, open(part, "ab" if have else "wb") as out:
                    if have and resp.status != 206:      # server ignored the range: start again
                        out.seek(0)
                        out.truncate()
                        have = 0
                    done += have
                    while True:
                        if self.cancel:
                            self.SigFinished.emit(False, "Download cancelled. Already loaded data are "
                                                         "kept and continued at the next download.")
                            return
                        block = resp.read(CHUNK)
                        if not block:
                            break
                        out.write(block)
                        done += len(block)
                        self.SigProgress.emit(done, total, name)
                if os.path.getsize(part) != size:
                    self.SigFinished.emit(False, f"{name}: incomplete download "
                                                 f"({os.path.getsize(part)} of {size} bytes), please try again.")
                    return
                os.replace(part, dest)
            self.SigFinished.emit(True, "")
        except Exception as exc:
            self.SigFinished.emit(False, f"Download error: {exc}")


class ArchiveDialog(QDialog):
    """list of the archive recordings; the user selects one and whether the first file only
    or the complete recording is to be downloaded"""

    def __init__(self, recordings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download IQ recording from the COHIRADIA archive")
        self.resize(900, 560)
        self.recordings = recordings
        self.parts = {}            # id -> parts (loaded on selection)
        self.details = {}          # id -> metadata
        self.choice = None         # (recording, parts to download)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Select a recording. The files are stored in the folder IQ_files "
                             "of the COHIWizard installation."))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("filter (e.g. 2006, MW, Graz) ...")
        self.filter.textChanged.connect(self.fill)
        lay.addWidget(self.filter)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date/Time", "Content", "Band", "Country", "Recording device"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.show_selection)
        lay.addWidget(self.table, 1)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.info)
        buttons = QHBoxLayout()
        self.btn_web = QPushButton("Archive web page ...")
        self.btn_web.clicked.connect(self.open_web)
        self.btn_first = QPushButton("Download first file")
        self.btn_first.clicked.connect(lambda: self.accept_choice(False))
        self.btn_all = QPushButton("Download complete recording")
        self.btn_all.clicked.connect(lambda: self.accept_choice(True))
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_web)
        buttons.addStretch(1)
        for b in (self.btn_first, self.btn_all, btn_cancel):
            buttons.addWidget(b)
        lay.addLayout(buttons)
        self.fill()
        self.show_selection()

    def fill(self):
        words = self.filter.text().lower().split()
        self.shown = []
        for r in self.recordings:
            text = " ".join(str(r.get(k, "")) for k in ("startTimestamp", "content", "band", "country", "city", "type")).lower()
            if all(w in text for w in words):
                self.shown.append(r)
        self.table.setRowCount(len(self.shown))
        for row, r in enumerate(self.shown):
            try:
                when = datetime.fromisoformat(r["startTimestamp"]).strftime("%Y-%m-%d %H:%M")
            except (KeyError, ValueError):
                when = str(r.get("startTimestamp", ""))
            place = f"{r.get('country') or ''} ({r['city']})" if r.get("city") else (r.get("country") or "")
            for col, val in enumerate((when, r.get("content", ""), r.get("band", ""), place, r.get("type", ""))):
                self.table.setItem(row, col, QTableWidgetItem(str(val or "")))
        self.table.resizeColumnToContents(0)

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.shown[rows[0].row()] if rows else None

    def show_selection(self):
        rec = self.selected()
        for b in (self.btn_first, self.btn_all):
            b.setEnabled(False)
        if rec is None:
            self.info.setText("No recording selected.")
            return
        rid = rec["id"]
        if rid not in self.parts:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.details[rid] = fetch_json(f"{ARCHIVE_BASE}/api/metadata/{rid}")
                self.parts[rid] = fetch_parts(rid)
            except Exception as exc:
                self.info.setText(f"Details cannot be loaded: {exc}")
                return
            finally:
                QApplication.restoreOverrideCursor()
        d, parts = self.details[rid], self.parts[rid]
        if not parts:
            self.info.setText("No wav files are offered for this recording.")
            return
        total = sum(p["size_gb"] for p in parts)
        unit = d.get("frequency-unit", "kHz")
        self.info.setText(
            f"<b>{d.get('content', '')}</b><br>"
            f"Center frequency {d.get('center-frequency', '?')} {unit}, bandwidth {d.get('bandwidth', '?')} {unit}, "
            f"duration {format_duration(d.get('duration') or 0)}, "
            f"{d.get('location-city') or ''} {d.get('location-country') or ''}<br>"
            f"{len(parts)} wav file(s), together {total:.2f} GB; first file: {parts[0]['name']} "
            f"({parts[0]['size_gb']:.2f} GB)")
        self.btn_first.setEnabled(True)
        self.btn_all.setEnabled(len(parts) > 1)

    def open_web(self):
        rec = self.selected()
        QDesktopServices.openUrl(QUrl(DETAIL_PAGE.format(rec["id"]) if rec else ARCHIVE_PAGE))

    def accept_choice(self, complete):
        rec = self.selected()
        if rec is None:
            return
        parts = self.parts[rec["id"]]
        self.choice = (rec, parts if complete else parts[:1])
        self.accept()


def download_folder(rec, base):
    """IQ_files/<id>_<content>: one folder per recording (the nextfilename chain of the
    wav headers needs all parts in the same folder)"""
    return os.path.join(base, f"{int(rec['id']):03d}_{safe_dirname(rec.get('content', ''))}")


def free_space(path):
    p = Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free


def start_thread(worker):
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.SigFinished.connect(thread.quit)
    thread.start()
    return thread
