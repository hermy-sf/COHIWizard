"""Download of station lists (extended m3u) from the COHIRADIA web page into the local
folder m3u_lists (next to sources/, like IQ_files).

The lists are offered as a plain directory listing:
    <M3U_INDEX>                 index page with one link per m3u file
    <M3U_INDEX><file name>      the m3u file
"""
import html
import os
import re
import urllib.parse
import urllib.request

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

M3U_INDEX = "https://cohiradia.radiomuseum.org/download/data/juke/m3u/"
USER_AGENT = "COHIWizard"
TIMEOUT = 30

# <a href="name.m3u">name.m3u</a>   25-Nov-2026 13:37   3435
_ENTRY_RE = re.compile(r'<a href="([^"?/]+\.m3u8?)">[^<]*</a>\s*(\S+\s+\S+)?\s*(\d+|-)?', re.IGNORECASE)


def _open(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def fetch_index():
    """m3u files offered on the web page: list of dicts name, url, date, size (bytes or None)"""
    with _open(M3U_INDEX) as resp:
        page = resp.read().decode("utf-8", errors="replace")
    files = []
    for href, date, size in _ENTRY_RE.findall(page):
        name = urllib.parse.unquote(html.unescape(href))
        files.append({"name": name, "url": urllib.parse.urljoin(M3U_INDEX, href),
                      "date": date or "", "size": int(size) if size and size.isdigit() else None})
    return sorted(files, key=lambda f: f["name"].lower())


def fetch_file(url):
    with _open(url) as resp:
        return resp.read()


def local_state(entry, folder):
    """'' (not present), 'present' or 'present, modified' (size differs from the web page)"""
    path = os.path.join(folder, entry["name"])
    if not os.path.isfile(path):
        return ""
    if entry["size"] is not None and os.path.getsize(path) != entry["size"]:
        return "present, modified"
    return "present"


class M3uDialog(QDialog):
    """list of the station lists on the COHIRADIA web page; the user checks the files to be
    downloaded"""

    def __init__(self, files, folder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download station lists (m3u) from COHIRADIA")
        self.resize(760, 420)
        self.files = files
        self.choice = []
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Check the station lists to be downloaded. They are stored in the folder\n{folder}"))
        self.table = QTableWidget(len(files), 4)
        self.table.setHorizontalHeaderLabels(["File", "Date", "Size", "Local copy"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for row, f in enumerate(files):
            item = QTableWidgetItem(f["name"])
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(f["date"]))
            size = f"{f['size'] / 1024:.1f} kB" if f["size"] is not None else ""
            self.table.setItem(row, 2, QTableWidgetItem(size))
            self.table.setItem(row, 3, QTableWidgetItem(local_state(f, folder)))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # a click into a row toggles its check box
        self.table.cellClicked.connect(self.toggle_row)
        lay.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        btn_all = QPushButton("Select all")
        btn_all.clicked.connect(lambda: self.set_all(Qt.Checked))
        btn_none = QPushButton("Select none")
        btn_none.clicked.connect(lambda: self.set_all(Qt.Unchecked))
        btn_ok = QPushButton("Download")
        btn_ok.clicked.connect(self.accept_choice)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        for b in (btn_all, btn_none):
            buttons.addWidget(b)
        buttons.addStretch(1)
        for b in (btn_ok, btn_cancel):
            buttons.addWidget(b)
        lay.addLayout(buttons)

    def toggle_row(self, row, column):
        if column == 0:
            return      # the check box itself toggles already
        item = self.table.item(row, 0)
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def set_all(self, state):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def accept_choice(self):
        self.choice = [f for row, f in enumerate(self.files)
                       if self.table.item(row, 0).checkState() == Qt.Checked]
        if self.choice:
            self.accept()
