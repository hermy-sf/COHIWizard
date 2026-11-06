#!/usr/bin/env python3
"""
cohi_setup.py  -  installer / module manager for COHIWizard

Stage 1 (bootstrap, standard library only, any Python 3.10 - 3.13):
    - asks for the installation directory (default ~/COHIWizard)
    - creates <target>/venv and installs requirements.txt of the chosen branch
    - restarts itself inside the venv (stage 2)

Stage 2 (inside the venv, PyQt5 available):
    - GUI for selecting the optional modules (tabs) and the device drivers
    - downloads only the selected parts from GitHub (no git needed); files that
      are already up to date (same git blob sha) are skipped
    - removes deselected modules (directory and a .info placeholder remain)
      and deselected drivers (directory and unused libs in dev_drivers/libs)
    - rewrites config_modules.yaml
    - installs 3rd party software after confirmation: ffmpeg, osmo-fl2k (Linux),
      libm2k (+ udev rule / ADI USB driver), Zadig (Windows, fl2k)
    - creates launchers and a desktop shortcut

Usage:
    python3 cohi_setup.py                      first installation (GUI)
    python3 cohi_setup.py --target DIR         install / modify DIR
    python3 cohi_setup.py --no-gui --modules synthesizer,annotator \
            --drivers fl2k_universal --yes     unattended
    python3 cohi_setup.py --dry-run            only show what would be done

From the COHIWizard menu (Setup) it is started in stage 2 with the running
interpreter.  In a git checkout (developer tree) nothing is downloaded or
deleted unless --allow-git-tree is given; the tool then runs as dry run.
"""
import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

REPO = "hermy-sf/COHIWizard"
DEFAULT_BRANCH = "main"
PY_MIN = (3, 10)
PY_MAX = (3, 13)
STATE_FILE = ".cohi_setup_state.json"
INFO_FILE = ".info"

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
# Mandatory parts. Every file at the top level of sources/ is also mandatory,
# except config_modules.yaml, which is generated.
CORE_FILES = ["requirements.txt", "LICENSE", "README.md",
              "documentation/UserManual_COHIWizard.pdf",
              "sources/dev_drivers/__init__.py"]
CORE_DIRS = ["sources/core/", "sources/player/", "sources/resampler/",
             "sources/logos/"]
GENERATED_FILES = ["sources/config_modules.yaml"]
# C++ sources of the shared DSP libs are always installed (small)
LIBS_DIR = "sources/dev_drivers/libs/"
LIBS_SOURCE_EXT = (".cpp", ".h")

# Optional tabs in tab order: (directory, module, tab name). The resampler is
# mandatory but keeps its position in the tab order.
MODULES = [
    ("spectralviewer", "view_spectra", "View Spectra"),
    ("resampler", "resample", "Resampler"),
    ("wavheader_editor", "wavheader_editor", "Wavheader Editor"),
    ("yaml_editor", "yaml_editor", "Yaml Editor"),
    ("annotator", "annotate", "Annotator"),
    ("synthesizer", "synthesizer", "Synthesizer"),
]
MANDATORY_MODULES = ["resampler"]

_FL2K_WIN_DLLS = ["libosmo-fl2k.dll", "libusb-1.0.dll", "libwinpthread-1.dll"]
DRIVERS = {
    "fl2k_universal": {
        "label": "FL2K USB-VGA dongle (universal)",
        "group": "universal",
        "libs": {"linux": ["libdspfl2k.so", "libdspflmod.so"],
                 "windows": ["libdspfl2k.dll", "libdspflmod.dll"] + _FL2K_WIN_DLLS},
        "needs": ["osmo_fl2k", "zadig"],
    },
    "stemlab_universal": {
        "label": "STEMLAB 125-14 (universal)",
        "group": "universal",
        # libdspflmod also links libosmo-fl2k
        "libs": {"linux": ["libdspflmod.so"],
                 "windows": ["libdspflmod.dll"] + _FL2K_WIN_DLLS},
        "needs": ["osmo_fl2k"],
    },
    "ADALM2000_universal": {
        "label": "ADALM2000 (universal)",
        "group": "universal",
        "libs": {},
        "needs": ["libm2k"],
    },
    "fl2k_stream": {
        "label": "FL2K USB-VGA dongle (reference driver)",
        "group": "reference",
        "libs": {},
        "extra_dirs": {"windows": ["sources/dev_drivers/__osmo-fl2k-64bit-20250105/"]},
        "needs": ["osmo_fl2k_tools", "zadig"],
    },
    "stemlab_125_14": {
        "label": "STEMLAB 125-14 (reference driver)",
        "group": "reference",
        "libs": {},
        "needs": [],
    },
    "ADALM2000": {
        "label": "ADALM2000 (reference driver)",
        "group": "reference",
        "libs": {},
        "needs": ["libm2k"],
    },
}
DEFAULT_DRIVERS = ["fl2k_universal"]

FL2K_VID_PID = ("1D5C", "2000")
M2K_UDEV_RULE = (
    "# ADALM2000 Active Learning Module (installed by COHIWizard setup)\n"
    'SUBSYSTEM=="usb", ATTRS{idVendor}=="0456", ATTRS{idProduct}=="b673", MODE="0666", GROUP="plugdev"\n'
    'SUBSYSTEM=="usb", ATTRS{idVendor}=="0456", ATTRS{idProduct}=="b674", MODE="0666", GROUP="plugdev"\n'
)
M2K_UDEV_PATH = "/etc/udev/rules.d/53-adi-m2k-usb.rules"
FFMPEG_WIN_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
                  "ffmpeg-master-latest-win64-gpl-shared.zip")
FFMPEG_WIN_DIR = "ffmpeg-master-latest-win64-gpl-shared"   # default path of COHIWizard.py
LIBM2K_FALLBACK_TAG = "v0.9.1"
ZADIG_FALLBACK_URL = "https://github.com/pbatard/libwdi/releases/download/v1.5.1/zadig-2.9.exe"
M2K_USB_DRIVER_URL = ("https://github.com/analogdevicesinc/plutosdr-m2k-drivers-win/"
                      "releases/latest/download/PlutoSDR-M2k-USB-Drivers.exe")
PY_WIN_INSTALLER = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"

ZADIG_HINT = (
    "Zadig installs the USB driver for the FL2K dongle:\n"
    "  1. plug in the FL2K dongle\n"
    "  2. Options -> List All Devices\n"
    "  3. select the device with USB ID 1D5C 2000 (often shown as 'FL2000' or 'Interface 0')\n"
    "  4. choose driver 'WinUSB' and press 'Install Driver' / 'Replace Driver'"
)


def os_key():
    return "windows" if platform.system() == "Windows" else "linux"


def is_arm():
    return platform.machine().lower() in ("aarch64", "arm64", "armv7l", "armv6l")


def py_tag(version_info=None):
    v = version_info or sys.version_info
    return f"cp{v[0]}{v[1]}"


# ---------------------------------------------------------------------------
# HTTP / GitHub
# ---------------------------------------------------------------------------
_UA = {"User-Agent": "COHIWizard-setup"}


def http_get(url, headers=None, timeout=60, retries=3):
    hdr = dict(_UA)
    hdr.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 416):
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        time.sleep(1.5 * (attempt + 1))
    raise last


def http_download(url, dest, progress=None, timeout=120):
    """Download url to dest (streaming); progress(done, total) optional."""
    req = urllib.request.Request(url, headers=_UA)
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(tmp, dest)
    return dest


def api_json(path):
    return json.loads(http_get("https://api.github.com/repos/" + REPO + path,
                               {"Accept": "application/vnd.github+json"}))


def raw_url(commit, path):
    return f"https://raw.githubusercontent.com/{REPO}/{commit}/{urllib.parse.quote(path)}"


def list_branches():
    try:
        names = [b["name"] for b in api_json("/branches?per_page=100")]
        return [n for n in names if n != "gh-pages"]
    except Exception:
        return [DEFAULT_BRANCH]


def resolve_branch(branch):
    """Return (commit sha, {path: (blob sha, size, mode)}) of a branch."""
    commit = api_json("/branches/" + urllib.parse.quote(branch))["commit"]["sha"]
    tree = api_json(f"/git/trees/{commit}?recursive=1")
    if tree.get("truncated"):
        raise RuntimeError("GitHub returned a truncated file list")
    files = {e["path"]: (e["sha"], e.get("size", 0), e.get("mode", "100644"))
             for e in tree["tree"] if e["type"] == "blob"}
    return commit, files


def latest_release_assets(repo):
    """{asset name: download url} of the latest release, {} on failure."""
    try:
        d = json.loads(http_get(f"https://api.github.com/repos/{repo}/releases/latest",
                                {"Accept": "application/vnd.github+json"}))
        return {a["name"]: a["browser_download_url"] for a in d.get("assets", [])}
    except Exception:
        return {}


class HTTPRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests, so that single members
    of a large remote zip can be read without downloading all of it."""

    def __init__(self, url):
        super().__init__()
        req = urllib.request.Request(url, headers=dict(_UA, Range="bytes=0-0"))
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status != 206:
                raise OSError("server does not support range requests")
            self.url = resp.geturl()           # follow the redirect only once
            self.size = int(resp.headers["Content-Range"].split("/")[-1])
        self.pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def read(self, n=-1):
        if self.pos >= self.size:
            return b""
        end = self.size - 1 if n is None or n < 0 else min(self.size, self.pos + n) - 1
        data = http_get(self.url, {"Range": f"bytes={self.pos}-{end}"}, timeout=120)
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def blob_sha(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ---------------------------------------------------------------------------
# Installation state
# ---------------------------------------------------------------------------
def find_git_root(path):
    path = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def venv_python(venv_dir):
    if os_key() == "windows":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


class Installation:
    """Local installation in <target>: sources/, venv/, launchers."""

    def __init__(self, target, python=None):
        self.target = os.path.abspath(target)
        self.sources = os.path.join(self.target, "sources")
        self.python = python or venv_python(os.path.join(self.target, "venv"))
        self.state_path = os.path.join(self.sources, STATE_FILE)
        self.state = {}
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                self.state = json.load(fh)
        except (OSError, ValueError):
            self.state = {}
        self.git_root = find_git_root(self.target)

    def p(self, repo_path):
        return os.path.join(self.target, *repo_path.split("/"))

    def exists(self):
        return os.path.isfile(os.path.join(self.sources, "COHIWizard.py"))

    def installed_modules(self):
        return [d for d, mod, _ in MODULES
                if os.path.isfile(os.path.join(self.sources, d, mod + ".py"))]

    def installed_drivers(self):
        return [d for d in DRIVERS
                if os.path.isfile(os.path.join(self.sources, "dev_drivers", d,
                                               "cohi_playrecworker.py"))]

    def save_state(self):
        os.makedirs(self.sources, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh, indent=1, sort_keys=True)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------
def _excluded(path):
    parts = path.split("/")
    return ("__pycache__" in parts or path.endswith(".pyc")
            or (len(parts) > 2 and parts[1] in ("build", "dist")))


def wanted_files(tree, modules, drivers, osk=None):
    """Select the repo paths needed for the given modules and drivers."""
    osk = osk or os_key()
    dirs = list(CORE_DIRS)
    dirs += [f"sources/{d}/" for d, _, _ in MODULES if d in modules or d in MANDATORY_MODULES]
    libs = set()
    for d in drivers:
        dirs.append(f"sources/dev_drivers/{d}/")
        libs.update(DRIVERS[d]["libs"].get(osk, []))
        dirs += DRIVERS[d].get("extra_dirs", {}).get(osk, [])
    out = {}
    for path, entry in tree.items():
        if _excluded(path) or path in GENERATED_FILES:
            continue
        top_source = path.startswith("sources/") and path.count("/") == 1
        in_libs = path.startswith(LIBS_DIR) and path.count("/") == 3
        name = path.rsplit("/", 1)[-1]
        if (path in CORE_FILES or top_source
                or any(path.startswith(d) for d in dirs)
                or (in_libs and (name.endswith(LIBS_SOURCE_EXT) or name.startswith("Makefile")
                                 or name in libs))):
            out[path] = entry
    return out


def managed_libs(osk=None):
    osk = osk or os_key()
    out = set()
    for d in DRIVERS.values():
        out.update(d["libs"].get(osk, []))
    return out


class Plan:
    def __init__(self):
        self.download = []        # repo paths
        self.uptodate = 0
        self.remove_module_dirs = []
        self.remove_driver_dirs = []
        self.remove_files = []    # repo paths
        self.modules = []
        self.drivers = []
        self.new_drivers = []

    def summary(self):
        lines = [f"files to download/update: {len(self.download)} (up to date: {self.uptodate})"]
        if self.remove_module_dirs:
            lines.append("modules to remove: " + ", ".join(self.remove_module_dirs))
        if self.remove_driver_dirs:
            lines.append("drivers to remove: " + ", ".join(self.remove_driver_dirs))
        if self.remove_files:
            lines.append(f"obsolete files to delete: {len(self.remove_files)}")
        return "\n".join(lines)


def make_plan(inst, tree, modules, drivers):
    plan = Plan()
    plan.modules = [d for d, _, _ in MODULES if d in modules or d in MANDATORY_MODULES]
    plan.drivers = [d for d in DRIVERS if d in drivers]
    have_drivers = inst.installed_drivers()
    plan.new_drivers = [d for d in plan.drivers if d not in have_drivers]
    want = wanted_files(tree, plan.modules, plan.drivers)
    for path, (sha, _size, _mode) in sorted(want.items()):
        local = inst.p(path)
        if os.path.isfile(local) and blob_sha(local) == sha:
            plan.uptodate += 1
        else:
            plan.download.append(path)
    plan.remove_module_dirs = [d for d in inst.installed_modules()
                               if d not in plan.modules and d not in MANDATORY_MODULES]
    plan.remove_driver_dirs = [d for d in have_drivers if d not in plan.drivers]
    # unused native libs of the current OS
    for lib in sorted(managed_libs() - set(want_lib_names(want))):
        if os.path.isfile(inst.p(LIBS_DIR + lib)):
            plan.remove_files.append(LIBS_DIR + lib)
    # extra driver directories (e.g. the osmo-fl2k Windows binaries)
    needed_extra = {e for d in plan.drivers for e in DRIVERS[d].get("extra_dirs", {}).get(os_key(), [])}
    for d in DRIVERS.values():
        for e in d.get("extra_dirs", {}).get(os_key(), []):
            if e not in needed_extra and os.path.isdir(inst.p(e)):
                plan.remove_driver_dirs.append(e)
    # files installed earlier by this tool which are no longer in the branch
    removed_dirs = ([f"sources/{d}/" for d in plan.remove_module_dirs]
                    + [f"sources/dev_drivers/{d}/" for d in plan.remove_driver_dirs])
    for path in sorted(inst.state.get("files", {})):
        if (path not in want and path not in plan.remove_files
                and not any(path.startswith(r) for r in removed_dirs)
                and os.path.isfile(inst.p(path))
                and blob_sha(inst.p(path)) == inst.state["files"][path]):
            plan.remove_files.append(path)
    return plan


def want_lib_names(want):
    return [p.rsplit("/", 1)[-1] for p in want if p.startswith(LIBS_DIR)]


# ---------------------------------------------------------------------------
# User interaction (console version; the GUI provides the same methods)
# ---------------------------------------------------------------------------
class ConsoleUI:
    def __init__(self, assume_yes=False):
        self.assume_yes = assume_yes
        self.graphical = False

    def log(self, msg):
        print(msg, flush=True)

    def progress(self, done, total):
        if total:
            print(f"\r  {done}/{total}", end="" if done < total else "\n", flush=True)

    def ask(self, question):
        if self.assume_yes:
            self.log(question + " -> yes (--yes)")
            return True
        if not sys.stdin or not sys.stdin.isatty():
            self.log(question + " -> no (no terminal)")
            return False
        return input(question + " [y/N] ").strip().lower() in ("y", "yes", "j", "ja")

    def info(self, msg):
        self.log(msg)


# ---------------------------------------------------------------------------
# Applying a plan
# ---------------------------------------------------------------------------
class Installer:
    def __init__(self, inst, ui, branch, dry_run=False):
        self.inst = inst
        self.ui = ui
        self.branch = branch
        self.dry_run = dry_run
        self.manual_steps = []

    # --- files ------------------------------------------------------------
    def _fetch(self, commit, path, mode):
        dest = self.inst.p(path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        data = http_get(raw_url(commit, path), timeout=120)
        tmp = dest + ".cohi_tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        try:
            os.replace(tmp, dest)
        except PermissionError:
            os.remove(tmp)
            raise RuntimeError(f"{path} is in use; close COHIWizard and run the setup again")
        if mode == "100755" and os_key() == "linux":
            os.chmod(dest, 0o755)

    def _remove_file(self, path):
        try:
            os.remove(self.inst.p(path))
            self.inst.state.get("files", {}).pop(path, None)
        except FileNotFoundError:
            self.inst.state.get("files", {}).pop(path, None)
        except OSError as exc:
            self.ui.log(f"  cannot delete {path}: {exc} (close COHIWizard and run the setup again)")

    def _clear_module_dir(self, mod):
        """Delete the files of a module, keep its directory tree and a .info placeholder."""
        top = os.path.join(self.inst.sources, mod)
        os.makedirs(top, exist_ok=True)
        for root, dirs, files in os.walk(top, topdown=False):
            for f in files:
                if root == top and f == INFO_FILE:
                    continue
                try:
                    os.remove(os.path.join(root, f))
                except OSError as exc:
                    self.ui.log(f"  cannot delete {os.path.join(root, f)}: {exc}")
            if os.path.basename(root) == "__pycache__":
                shutil.rmtree(root, ignore_errors=True)
        with open(os.path.join(top, INFO_FILE), "w", encoding="utf-8") as fh:
            fh.write(f"Module '{mod}' is not installed.\n"
                     "Install it with the COHIWizard setup tool (menu Setup or cohi_setup.py).\n")
        prefix = f"sources/{mod}/"
        for p in [p for p in self.inst.state.get("files", {}) if p.startswith(prefix)]:
            del self.inst.state["files"][p]

    def _remove_driver_dir(self, drv):
        path = drv if drv.startswith("sources/") else f"sources/dev_drivers/{drv}/"
        shutil.rmtree(self.inst.p(path), ignore_errors=True)
        if os.path.isdir(self.inst.p(path)):
            self.ui.log(f"  could not remove {path} completely (files in use?)")
        for p in [p for p in self.inst.state.get("files", {}) if p.startswith(path)]:
            del self.inst.state["files"][p]

    def apply(self, commit, tree, plan):
        ui = self.ui
        ui.log(plan.summary())
        if self.dry_run:
            for p in plan.download:
                ui.log("  would download " + p)
            for p in plan.remove_files:
                ui.log("  would delete " + p)
            ui.log("dry run: nothing changed")
            return True
        files_state = self.inst.state.setdefault("files", {})
        if plan.download:
            ui.log(f"downloading {len(plan.download)} files from {REPO} ({self.branch}) ...")
            done = [0]
            lock = threading.Lock()

            def job(path):
                self._fetch(commit, path, tree[path][2])
                with lock:
                    done[0] += 1
                    ui.progress(done[0], len(plan.download))
                return path

            with ThreadPoolExecutor(max_workers=8) as pool:
                for path in pool.map(job, plan.download):
                    files_state[path] = tree[path][0]
        for path in wanted_files(tree, plan.modules, plan.drivers):
            files_state.setdefault(path, tree[path][0])
        # a freshly installed module no longer needs its placeholder
        for mod in plan.modules:
            info = os.path.join(self.inst.sources, mod, INFO_FILE)
            if os.path.isfile(info):
                with open(info, encoding="utf-8", errors="replace") as fh:
                    generated = "is not installed" in fh.read()
                if generated:
                    os.remove(info)
        for mod in plan.remove_module_dirs:
            ui.log("removing module " + mod)
            self._clear_module_dir(mod)
        # keep the directory structure: placeholder for modules never installed
        for mod, _, _ in MODULES:
            top = os.path.join(self.inst.sources, mod)
            if mod not in plan.modules and not os.path.isfile(os.path.join(top, INFO_FILE)):
                self._clear_module_dir(mod)
        for drv in plan.remove_driver_dirs:
            ui.log("removing driver " + drv)
            self._remove_driver_dir(drv)
        for path in plan.remove_files:
            ui.log("deleting " + path)
            self._remove_file(path)
        self.write_config_modules(plan)
        self.fix_config_wizard(plan)
        self.inst.state.update({"repo": REPO, "branch": self.branch, "commit": commit,
                                "modules": plan.modules, "drivers": plan.drivers,
                                "updated": time.strftime("%Y-%m-%d %H:%M:%S")})
        self.inst.save_state()
        return True

    # --- configuration ----------------------------------------------------
    def write_config_modules(self, plan):
        import yaml
        path = os.path.join(self.inst.sources, "config_modules.yaml")
        try:
            with open(path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        except OSError:
            cfg = {}
        cfg["modules"] = {d: mod for d, mod, _ in MODULES if d in plan.modules}
        cfg["module_names"] = {d: name for d, _, name in MODULES if d in plan.modules}
        cfg["dev_workers"] = {d: "cohi_playrecworker.py" for d in plan.drivers}
        cfg["SDR_controllers"] = {d: "SDR_control.py" for d in plan.drivers}
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh, sort_keys=False)
        self.ui.log("config_modules.yaml written")

    def fix_config_wizard(self, plan):
        """Point the last used device to an installed driver."""
        import yaml
        path = os.path.join(self.inst.sources, "config_wizard.yaml")
        if not os.path.isfile(path) or not plan.drivers:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            return
        if cfg.get("last_device_name") in plan.drivers:
            return
        cfg["last_device_name"] = plan.drivers[0]
        cfg["last_device"] = 0
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(cfg, fh)
        self.ui.log(f"config_wizard.yaml: last device set to {plan.drivers[0]}")

    def pip_install_requirements(self):
        req = os.path.join(self.inst.target, "requirements.txt")
        if not os.path.isfile(req) or self.dry_run:
            return True
        sha = blob_sha(req)
        if self.inst.state.get("requirements_sha") == sha:
            return True
        self.ui.log("installing Python packages (requirements.txt) ...")
        ok = pip_install(self.inst.python, req, self.ui.log)
        if ok:
            self.inst.state["requirements_sha"] = sha
            self.inst.save_state()
        return ok

    # --- 3rd party software -----------------------------------------------
    def run_root(self, commands, why):
        """Run shell commands as root on Linux after confirmation."""
        script = " && ".join(commands)
        if not self.ui.ask(f"{why}\n\nThe following commands need administrator rights:\n\n"
                           f"  {script}\n\nRun them now?"):
            self.manual_steps.append(script)
            return False
        if os.geteuid() == 0:
            cmd = ["sh", "-c", script]
        elif self.ui.graphical and shutil.which("pkexec") and os.environ.get("DISPLAY", os.environ.get("WAYLAND_DISPLAY")):
            cmd = ["pkexec", "sh", "-c", script]
        elif shutil.which("sudo") and sys.stdin and sys.stdin.isatty():
            cmd = ["sudo", "sh", "-c", script]
        else:
            self.ui.log("no way to obtain administrator rights, please run manually:\n  sudo sh -c '" + script + "'")
            self.manual_steps.append(script)
            return False
        self.ui.log("$ " + " ".join(cmd))
        rc = run_logged(cmd, self.ui.log)
        if rc != 0:
            self.ui.log(f"command failed (exit code {rc})")
            self.manual_steps.append(script)
        return rc == 0

    def ensure_third_party(self, plan):
        if self.dry_run:
            self.ui.log("dry run: 3rd party software is not checked")
            return
        needs = {n for d in plan.drivers for n in DRIVERS[d]["needs"]}
        if os_key() == "linux":
            self._linux_packages(needs)
        else:
            self._windows_ffmpeg()
        if "libm2k" in needs:
            self.ensure_libm2k()
        if "zadig" in needs and os_key() == "windows":
            if any("zadig" in DRIVERS[d]["needs"] for d in plan.new_drivers):
                if self.ui.ask("The FL2K dongle needs the WinUSB driver under Windows.\n"
                               "Download and start Zadig now?\n\n" + ZADIG_HINT):
                    launch_zadig(self.inst.sources, self.ui.log)

    def _linux_packages(self, needs):
        import ctypes.util
        pkgs = []
        if not shutil.which("ffmpeg"):
            pkgs.append("ffmpeg")
        if "osmo_fl2k" in needs and not ctypes.util.find_library("osmo-fl2k"):
            pkgs.append("libosmo-fl2k0")
        if "osmo_fl2k_tools" in needs and not shutil.which("fl2k_file"):
            pkgs.append("osmo-fl2k")
        if not pkgs:
            self.ui.log("ffmpeg / osmo-fl2k: present")
            return
        if not shutil.which("apt-get"):
            msg = "please install with your package manager: " + " ".join(pkgs)
            self.ui.log(msg)
            self.manual_steps.append(msg)
            return
        cmds = ["apt-get update", "apt-get install -y " + " ".join(pkgs)]
        if "osmo-fl2k" in pkgs or "libosmo-fl2k0" in pkgs:
            # access to the dongle without root
            cmds.append("printf '%s\\n' 'SUBSYSTEM==\"usb\", ATTR{idVendor}==\"1d5c\", "
                        "ATTR{idProduct}==\"2000\", MODE=\"0666\"' > /etc/udev/rules.d/99-fl2k.rules")
            cmds.append("udevadm control --reload-rules")
        self.run_root(cmds, "Missing system packages: " + ", ".join(pkgs))

    def _windows_ffmpeg(self):
        local = os.path.join(self.inst.sources, FFMPEG_WIN_DIR, "bin", "ffmpeg.exe")
        if shutil.which("ffmpeg") or os.path.isfile(local):
            self.ui.log("ffmpeg: present")
            return
        if not self.ui.ask("ffmpeg is required by resampler, synthesizer and the drivers.\n"
                           "Download ffmpeg now (about 90 MB)?"):
            self.manual_steps.append("install ffmpeg (https://www.ffmpeg.org/download.html)")
            return
        tmp = os.path.join(tempfile.gettempdir(), "cohi_ffmpeg.zip")
        self.ui.log("downloading ffmpeg ...")
        http_download(FFMPEG_WIN_URL, tmp, self.ui.progress)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(self.inst.sources)
        os.remove(tmp)
        self.ui.log("ffmpeg installed in " + os.path.join(self.inst.sources, FFMPEG_WIN_DIR))

    def _venv_has(self, module):
        return subprocess.run([self.inst.python, "-c", "import " + module],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    def _venv_info(self):
        out = subprocess.run([self.inst.python, "-c",
                              "import sys,sysconfig;print(sys.version_info[0],sys.version_info[1]);"
                              "print(sysconfig.get_paths()['platlib'])"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
        major, minor = (int(x) for x in out[0].split())
        return (major, minor), out[1]

    def ensure_libm2k(self):
        if self._venv_has("libm2k"):
            self.ui.log("libm2k: present")
        elif self.ui.ask("The ADALM2000 drivers need libm2k (Analog Devices).\nInstall libm2k now?"):
            try:
                self._install_libm2k()
            except Exception as exc:
                self.ui.log(f"libm2k installation failed: {exc}")
                self.manual_steps.append("install libm2k: https://wiki.analog.com/university/tools/m2k/libm2k/libm2k")
        else:
            self.manual_steps.append("install libm2k: https://wiki.analog.com/university/tools/m2k/libm2k/libm2k")
        # USB access
        if os_key() == "linux":
            if not os.path.isfile(M2K_UDEV_PATH) and not os.path.isfile("/lib/udev/rules.d/53-adi-m2k-usb.rules"):
                rule = M2K_UDEV_RULE.replace("'", "")
                self.run_root([f"printf '%s' '{rule}' > {M2K_UDEV_PATH}",
                               "udevadm control --reload-rules", "udevadm trigger"],
                              "USB access to the ADALM2000 without root needs a udev rule.")
        elif self.ui.ask("Windows needs the Analog Devices USB driver for the ADALM2000.\n"
                         "Download and start the driver installer now?\n"
                         "(skip this if Scopy or the driver is already installed)"):
            dest = os.path.join(self.inst.sources, "tools", "PlutoSDR-M2k-USB-Drivers.exe")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            http_download(M2K_USB_DRIVER_URL, dest, self.ui.progress)
            os.startfile(dest)

    def _install_libm2k(self):
        assets = latest_release_assets("analogdevicesinc/libm2k")
        tag = LIBM2K_FALLBACK_TAG
        for name in assets:
            if name.startswith("libm2k-") and name.endswith("-python-wheels.zip"):
                tag = "v" + name[len("libm2k-"):-len("-python-wheels.zip")]
        ver = tag.lstrip("v")
        base = f"https://github.com/analogdevicesinc/libm2k/releases/download/{tag}/"
        (major, minor), platlib = self._venv_info()
        tag_py = f"cp{major}{minor}"
        tmpdir = tempfile.mkdtemp(prefix="cohi_m2k_")
        try:
            if os_key() == "windows":
                zpath = os.path.join(tmpdir, "m2k.zip")
                self.ui.log("downloading libm2k for Windows ...")
                http_download(base + f"libm2k-{ver}-windows.zip", zpath, self.ui.progress)
                with zipfile.ZipFile(zpath) as z:
                    names = z.namelist()
                    whl = [n for n in names if n.endswith(f"-{tag_py}-{tag_py}-win_amd64.whl")]
                    if not whl:
                        raise RuntimeError(f"no libm2k wheel for Python {major}.{minor}")
                    wpath = os.path.join(tmpdir, whl[0].rsplit("/", 1)[-1])
                    with open(wpath, "wb") as fh:
                        fh.write(z.read(whl[0]))
                    self._pip_wheel(wpath)
                    # native dlls next to _libm2k.pyd (found via the dll load dir)
                    for n in names:
                        base_name = n.rsplit("/", 1)[-1]
                        if n.count("/") == 1 and base_name.endswith(".dll") and "sharp" not in base_name \
                                and not base_name.endswith("_lv.dll"):
                            with open(os.path.join(platlib, base_name), "wb") as fh:
                                fh.write(z.read(n))
            elif is_arm():
                arch = "arm64" if platform.machine().lower() in ("aarch64", "arm64") else "armhf"
                zpath = os.path.join(tmpdir, "m2k.zip")
                self.ui.log(f"downloading libm2k for Debian {arch} ...")
                http_download(base + f"libm2k-{ver}-debian-13-{arch}.zip", zpath, self.ui.progress)
                with zipfile.ZipFile(zpath) as z:
                    debs = [n for n in z.namelist() if n.endswith(".deb")
                            and (n.rsplit("/", 1)[-1].startswith("libm2k_")
                                 or n.rsplit("/", 1)[-1].startswith("python3-libm2k_"))]
                    z.extractall(tmpdir, debs)
                paths = " ".join(os.path.join(tmpdir, d) for d in debs)
                if self.run_root([f"apt-get install -y {paths}"], "libm2k is installed as system package."):
                    enable_system_site_packages(os.path.dirname(os.path.dirname(self.inst.python)), self.ui.log)
            else:
                member = f"libm2k-{ver}-python-wheels/libm2k-{ver}-{tag_py}-{tag_py}-manylinux_2_28_x86_64.whl"
                wpath = os.path.join(tmpdir, member.rsplit("/", 1)[-1])
                self.ui.log("downloading libm2k wheel ...")
                url = base + f"libm2k-{ver}-python-wheels.zip"
                try:
                    zsrc = zipfile.ZipFile(io.BufferedReader(HTTPRangeFile(url), 4 << 20))
                except OSError:
                    zfile = os.path.join(tmpdir, "wheels.zip")
                    http_download(url, zfile, self.ui.progress)
                    zsrc = zipfile.ZipFile(zfile)
                with zsrc:
                    if member not in zsrc.namelist():
                        raise RuntimeError(f"no libm2k wheel for Python {major}.{minor}")
                    with open(wpath, "wb") as fh:
                        fh.write(zsrc.read(member))
                self._pip_wheel(wpath)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if self._venv_has("libm2k"):
            self.ui.log("libm2k installed")
        else:
            raise RuntimeError("libm2k cannot be imported after installation")

    def _pip_wheel(self, wpath):
        rc = run_logged([self.inst.python, "-m", "pip", "install", "--no-deps", wpath], self.ui.log)
        if rc != 0:
            raise RuntimeError("pip install of the libm2k wheel failed")

    # --- launchers --------------------------------------------------------
    def create_launchers(self, shortcut=True):
        if self.dry_run:
            return
        t = self.inst.target
        py = self.inst.python
        if os_key() == "windows":
            pyw = py[:-len("python.exe")] + "pythonw.exe" if py.endswith("python.exe") else py
            bat = os.path.join(t, "COHIWizard.bat")
            with open(bat, "w") as fh:
                fh.write(f'@echo off\r\ncd /d "{self.inst.sources}"\r\nstart "" "{pyw}" COHIWizard.py\r\n')
            setup_bat = os.path.join(t, "COHIWizard_setup.bat")
            with open(setup_bat, "w") as fh:
                fh.write(f'@echo off\r\ncd /d "{self.inst.sources}"\r\n"{py}" cohi_setup.py --stage2 '
                         f'--target "{t}" --python "{py}"\r\n')
            self.ui.log("launcher: " + bat)
            if shortcut:
                lnk = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut("
                       "[Environment]::GetFolderPath('Desktop')+'\\COHIWizard.lnk');"
                       f"$s.TargetPath='{pyw}';$s.Arguments='COHIWizard.py';"
                       f"$s.WorkingDirectory='{self.inst.sources}';"
                       f"$s.IconLocation='{os.path.join(self.inst.sources, 'COHIWizard_ico4.ico')}';$s.Save()")
                subprocess.run(["powershell", "-NoProfile", "-Command", lnk])
        else:
            sh = os.path.join(t, "COHIWizard.sh")
            with open(sh, "w") as fh:
                fh.write(f'#!/bin/sh\ncd "{self.inst.sources}" && exec "{py}" COHIWizard.py "$@"\n')
            os.chmod(sh, 0o755)
            sh2 = os.path.join(t, "COHIWizard_setup.sh")
            with open(sh2, "w") as fh:
                fh.write(f'#!/bin/sh\ncd "{self.inst.sources}" && exec "{py}" cohi_setup.py --stage2 '
                         f'--target "{t}" --python "{py}" "$@"\n')
            os.chmod(sh2, 0o755)
            self.ui.log("launcher: " + sh)
            if shortcut:
                appdir = os.path.expanduser("~/.local/share/applications")
                os.makedirs(appdir, exist_ok=True)
                icon = os.path.join(self.inst.sources, "logos", "SplasScreen_s.png")
                with open(os.path.join(appdir, "cohiwizard.desktop"), "w") as fh:
                    fh.write("[Desktop Entry]\nType=Application\nName=COHIWizard\n"
                             f"Exec=\"{sh}\"\nPath={self.inst.sources}\nIcon={icon}\n"
                             "Terminal=false\nCategories=AudioVideo;HamRadio;\n")
                self.ui.log("menu entry: " + os.path.join(appdir, "cohiwizard.desktop"))


def enable_system_site_packages(venv_dir, log):
    cfg = os.path.join(venv_dir, "pyvenv.cfg")
    try:
        with open(cfg) as fh:
            lines = fh.read().splitlines()
        lines = [l for l in lines if not l.startswith("include-system-site-packages")]
        lines.append("include-system-site-packages = true")
        with open(cfg, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        log("venv now also uses the system site-packages")
    except OSError as exc:
        log(f"cannot change {cfg}: {exc}")


def run_logged(cmd, log, cwd=None):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=cwd, text=True, errors="replace")
    for line in proc.stdout:
        log("  " + line.rstrip())
    return proc.wait()


def pip_install(python, requirements, log):
    """pip install -r requirements; on ARM PyQt5 comes from the system packages."""
    req = requirements
    if is_arm():
        with open(requirements) as fh:
            lines = [l for l in fh if not l.lower().startswith(("pyqt5", "pyqtwebengine", "pyinstaller"))]
        req = os.path.join(tempfile.gettempdir(), "cohi_requirements_arm.txt")
        with open(req, "w") as fh:
            fh.writelines(lines)
    rc = run_logged([python, "-m", "pip", "install", "-r", req], log)
    if rc != 0:
        log("pip install failed")
    return rc == 0


# ---------------------------------------------------------------------------
# Windows FL2K driver check (also used by the player)
# ---------------------------------------------------------------------------
def windows_fl2k_driver_state():
    """'absent' (no dongle plugged in), 'ok' (WinUSB/libusb driver) or 'missing'."""
    if os_key() != "windows":
        return "ok"
    vid, pid = FL2K_VID_PID
    ps = ("Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -like "
          f"'USB\\VID_{vid}&PID_{pid}*' }} | ForEach-Object {{ $_.Service }}")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                             text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "ok"            # cannot tell, do not bother the user
    services = [s.strip().lower() for s in out.splitlines() if s.strip()]
    if not services and not out.strip():
        # a device without driver has no Service, check presence separately
        ps2 = ("(Get-CimInstance Win32_PnPEntity | Where-Object { $_.DeviceID -like "
               f"'USB\\VID_{vid}&PID_{pid}*' }}).Count")
        try:
            cnt = subprocess.run(["powershell", "-NoProfile", "-Command", ps2], capture_output=True,
                                 text=True, timeout=20,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return "ok"
        return "missing" if cnt not in ("", "0") else "absent"
    if any(s in ("winusb", "libusb0", "libusbk") for s in services):
        return "ok"
    return "missing"


def launch_zadig(sources_dir, log=print):
    """Download Zadig into sources/tools (once) and start it (asks for admin rights)."""
    dest = os.path.join(sources_dir, "tools", "zadig.exe")
    if not os.path.isfile(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        assets = latest_release_assets("pbatard/libwdi")
        url = next((u for n, u in assets.items() if n.startswith("zadig") and n.endswith(".exe")),
                   ZADIG_FALLBACK_URL)
        log("downloading " + url)
        http_download(url, dest)
    log(ZADIG_HINT)
    os.startfile(dest)


# ---------------------------------------------------------------------------
# Stage 1: bootstrap
# ---------------------------------------------------------------------------
def default_target():
    if os_key() == "windows":
        return os.path.join(os.path.expanduser("~"), "COHIWizard")
    return os.path.expanduser("~/COHIWizard")


def bootstrap(args):
    ui = ConsoleUI(args.yes)
    if not (PY_MIN <= sys.version_info[:2] <= PY_MAX):
        ui.log(f"COHIWizard needs Python {PY_MIN[0]}.{PY_MIN[1]} - {PY_MAX[0]}.{PY_MAX[1]}, "
               f"this is {platform.python_version()}.")
        if os_key() == "windows":
            ui.log("Run cohi_setup.bat, it installs Python 3.10 if necessary, or get it from " + PY_WIN_INSTALLER)
        return 1
    target = args.target
    if not target:
        target = default_target()
        if not args.yes and sys.stdin and sys.stdin.isatty():
            ans = input(f"Installation directory [{target}]: ").strip()
            target = os.path.abspath(os.path.expanduser(ans)) if ans else target
    target = os.path.abspath(target)
    os.makedirs(target, exist_ok=True)
    inst = Installation(target)
    branch = args.branch or inst.state.get("branch") or DEFAULT_BRANCH
    ui.log(f"COHIWizard setup: target {target}, branch {branch}")

    venv_dir = os.path.join(target, "venv")
    py = venv_python(venv_dir)
    if not os.path.isfile(py):
        ui.log("creating virtual environment " + venv_dir)
        cmd = [sys.executable, "-m", "venv", venv_dir]
        if is_arm():
            cmd.insert(3, "--system-site-packages")
        if subprocess.run(cmd).returncode != 0 or not os.path.isfile(py):
            ui.log("creating the venv failed.")
            if os_key() == "linux":
                ui.log(f"On Debian/Ubuntu install it with:  sudo apt install python3-venv "
                       f"(or python3.{sys.version_info[1]}-venv) and run the setup again.")
            shutil.rmtree(venv_dir, ignore_errors=True)
            return 1
        if is_arm():
            ui.log("ARM: PyQt5 is taken from the system, install it with: "
                   "sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine")
    req = os.path.join(target, "requirements.txt")
    try:
        commit = api_json("/branches/" + urllib.parse.quote(branch))["commit"]["sha"]
        with open(req, "wb") as fh:
            fh.write(http_get(raw_url(commit, "requirements.txt")))
    except Exception as exc:
        ui.log(f"cannot download requirements.txt from GitHub ({exc}); check the internet connection")
        return 1
    ui.log("installing Python packages, this takes a few minutes ...")
    if not pip_install(py, req, ui.log):
        return 1
    inst.state["requirements_sha"] = blob_sha(req)
    inst.save_state()
    cmd = [py, os.path.abspath(__file__), "--stage2", "--target", target, "--branch", branch,
           "--python", py] + passthrough_args(args)
    ui.log("starting stage 2 ...")
    return subprocess.call(cmd)


def passthrough_args(args):
    out = []
    for flag in ("no_gui", "yes", "dry_run", "allow_git_tree", "no_shortcut"):
        if getattr(args, flag):
            out.append("--" + flag.replace("_", "-"))
    if args.modules is not None:
        out += ["--modules", args.modules]
    if args.drivers is not None:
        out += ["--drivers", args.drivers]
    return out


# ---------------------------------------------------------------------------
# Stage 2: headless
# ---------------------------------------------------------------------------
def parse_list(text, valid, what):
    items = [x.strip() for x in (text or "").split(",") if x.strip()]
    bad = [x for x in items if x not in valid]
    if bad:
        raise SystemExit(f"unknown {what}: {', '.join(bad)}; valid: {', '.join(valid)}")
    return items


def run_headless(args):
    ui = ConsoleUI(args.yes)
    inst = Installation(args.target, args.python)
    dry = args.dry_run or (inst.git_root is not None and not args.allow_git_tree)
    if dry and not args.dry_run:
        ui.log(f"{inst.git_root} is a git checkout: dry run (use --allow-git-tree to override)")
    modules = (parse_list(args.modules, [m[0] for m in MODULES], "modules")
               if args.modules is not None else inst.installed_modules() or [m[0] for m in MODULES])
    drivers = (parse_list(args.drivers, list(DRIVERS), "drivers")
               if args.drivers is not None else inst.installed_drivers() or DEFAULT_DRIVERS)
    if not drivers:
        ui.log("at least one driver must be selected")
        return 1
    branch = args.branch or inst.state.get("branch") or DEFAULT_BRANCH
    return 0 if run_install(inst, ui, branch, modules, drivers, dry, not args.no_shortcut) else 1


def run_install(inst, ui, branch, modules, drivers, dry_run, shortcut=True):
    ui.log(f"reading file list of branch {branch} ...")
    commit, tree = resolve_branch(branch)
    plan = make_plan(inst, tree, modules, drivers)
    installer = Installer(inst, ui, branch, dry_run)
    installer.apply(commit, tree, plan)
    if not installer.pip_install_requirements():
        installer.manual_steps.append(f'"{inst.python}" -m pip install -r requirements.txt')
    installer.ensure_third_party(plan)
    installer.create_launchers(shortcut)
    if installer.manual_steps:
        ui.info("Please complete these steps manually:\n\n" + "\n".join("- " + s for s in installer.manual_steps))
    ui.log("done.")
    return True


# ---------------------------------------------------------------------------
# Stage 2: GUI
# ---------------------------------------------------------------------------
def run_gui(args):
    from PyQt5 import QtCore, QtWidgets
    from PyQt5.QtCore import Qt

    class Bridge(QtCore.QObject):
        sig_log = QtCore.pyqtSignal(str)
        sig_progress = QtCore.pyqtSignal(int, int)
        sig_ask = QtCore.pyqtSignal(str)
        sig_info = QtCore.pyqtSignal(str)

    class GuiUI:
        """Thread-safe UI for the installer running in a worker thread."""
        graphical = True

        def __init__(self, bridge):
            self.bridge = bridge
            self.answer = False

        def log(self, msg):
            self.bridge.sig_log.emit(str(msg))

        def progress(self, done, total):
            self.bridge.sig_progress.emit(int(done), int(total))

        def ask(self, question):
            self.bridge.sig_ask.emit(question)     # BlockingQueuedConnection
            return self.answer

        def info(self, msg):
            self.bridge.sig_info.emit(msg)

    class Worker(QtCore.QThread):
        sig_done = QtCore.pyqtSignal(bool, str)

        def __init__(self, job):
            super().__init__()
            self.job = job

        def run(self):
            try:
                self.job()
                self.sig_done.emit(True, "")
            except Exception as exc:
                self.sig_done.emit(False, f"{type(exc).__name__}: {exc}")

    class SetupDialog(QtWidgets.QDialog):
        def __init__(self):
            super().__init__()
            self.inst = Installation(args.target, args.python)
            self.forced_dry = self.inst.git_root is not None and not args.allow_git_tree
            self.setWindowTitle("COHIWizard setup")
            self.resize(760, 720)
            lay = QtWidgets.QVBoxLayout(self)

            top = QtWidgets.QFormLayout()
            top.addRow("Installation:", QtWidgets.QLabel(self.inst.target))
            self.cb_branch = QtWidgets.QComboBox()
            branches = list_branches()
            current = args.branch or self.inst.state.get("branch") or DEFAULT_BRANCH
            if current not in branches:
                branches.insert(0, current)
            self.cb_branch.addItems(branches)
            self.cb_branch.setCurrentText(current)
            top.addRow("GitHub branch:", self.cb_branch)
            if self.inst.state.get("commit"):
                top.addRow("Installed:", QtWidgets.QLabel(
                    f"{self.inst.state.get('branch')} @ {self.inst.state['commit'][:10]} "
                    f"({self.inst.state.get('updated', '')})"))
            lay.addLayout(top)

            if self.forced_dry:
                warn = QtWidgets.QLabel(f"<b>{self.inst.git_root}</b> is a git checkout (developer tree). "
                                        "The setup only shows what it would do (dry run).")
                warn.setWordWrap(True)
                warn.setStyleSheet("color: #b05000")
                lay.addWidget(warn)

            have_mod = self.inst.installed_modules()
            have_drv = self.inst.installed_drivers()
            fresh = not self.inst.exists()

            grp = QtWidgets.QGroupBox("Modules (tabs)")
            g = QtWidgets.QGridLayout(grp)
            for i, name in enumerate(["Core", "Player"]):
                cb = QtWidgets.QCheckBox(name + " (required)")
                cb.setChecked(True)
                cb.setEnabled(False)
                g.addWidget(cb, 0, i)
            self.cb_mod = {}
            col = 2
            row = 0
            for d, _, label in MODULES:
                cb = QtWidgets.QCheckBox(label + (" (required)" if d in MANDATORY_MODULES else ""))
                cb.setChecked(fresh or d in have_mod or d in MANDATORY_MODULES)
                cb.setEnabled(d not in MANDATORY_MODULES)
                self.cb_mod[d] = cb
                g.addWidget(cb, row, col)
                col += 1
                if col > 2:
                    col = 0
                    row += 1
            lay.addWidget(grp)

            grp = QtWidgets.QGroupBox("Device drivers (at least one)")
            g = QtWidgets.QGridLayout(grp)
            self.cb_drv = {}
            for c, group in enumerate(["universal", "reference"]):
                hdr = QtWidgets.QLabel("<i>%s</i>" % ("Universal drivers (recommended)" if group == "universal"
                                                      else "Reference drivers"))
                g.addWidget(hdr, 0, c)
                r = 1
                for d, spec in DRIVERS.items():
                    if spec["group"] != group:
                        continue
                    cb = QtWidgets.QCheckBox(spec["label"])
                    cb.setToolTip(d)
                    cb.setChecked(d in have_drv if have_drv else d in DEFAULT_DRIVERS)
                    cb.toggled.connect(self.check_drivers)
                    self.cb_drv[d] = cb
                    g.addWidget(cb, r, c)
                    r += 1
            lay.addWidget(grp)

            self.cb_shortcut = QtWidgets.QCheckBox("Create launcher and desktop/menu shortcut")
            self.cb_shortcut.setChecked(not args.no_shortcut)
            self.cb_dry = QtWidgets.QCheckBox("Dry run (only show what would be done)")
            self.cb_dry.setChecked(args.dry_run or self.forced_dry)
            self.cb_dry.setEnabled(not self.forced_dry)
            lay.addWidget(self.cb_shortcut)
            lay.addWidget(self.cb_dry)

            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumBlockCount(20000)
            lay.addWidget(self.log, 1)
            self.bar = QtWidgets.QProgressBar()
            self.bar.setValue(0)
            lay.addWidget(self.bar)

            btns = QtWidgets.QHBoxLayout()
            self.bt_apply = QtWidgets.QPushButton("Install / apply changes")
            self.bt_apply.clicked.connect(self.start)
            self.bt_start = QtWidgets.QPushButton("Start COHIWizard")
            self.bt_start.clicked.connect(self.start_wizard)
            self.bt_start.setEnabled(self.inst.exists() and not self.forced_dry)
            self.bt_close = QtWidgets.QPushButton("Close")
            self.bt_close.clicked.connect(self.close)
            btns.addWidget(self.bt_apply)
            btns.addStretch(1)
            btns.addWidget(self.bt_start)
            btns.addWidget(self.bt_close)
            lay.addLayout(btns)

            self.bridge = Bridge()
            self.gui_ui = GuiUI(self.bridge)
            self.bridge.sig_log.connect(self.append_log)
            self.bridge.sig_progress.connect(self.set_progress)
            self.bridge.sig_ask.connect(self.on_ask, Qt.BlockingQueuedConnection)
            self.bridge.sig_info.connect(self.on_info)
            self.worker = None
            self.check_drivers()

        def check_drivers(self):
            ok = any(cb.isChecked() for cb in self.cb_drv.values())
            self.bt_apply.setEnabled(ok and self.worker is None)
            self.bt_apply.setToolTip("" if ok else "select at least one driver")

        def append_log(self, msg):
            self.log.appendPlainText(msg)

        def set_progress(self, done, total):
            self.bar.setMaximum(max(total, 1))
            self.bar.setValue(done)

        def on_ask(self, question):
            r = QtWidgets.QMessageBox.question(self, "COHIWizard setup", question,
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            self.gui_ui.answer = r == QtWidgets.QMessageBox.Yes

        def on_info(self, msg):
            QtWidgets.QMessageBox.information(self, "COHIWizard setup", msg)

        def start(self):
            modules = [d for d, cb in self.cb_mod.items() if cb.isChecked()]
            drivers = [d for d, cb in self.cb_drv.items() if cb.isChecked()]
            removed = [d for d in self.inst.installed_modules() + self.inst.installed_drivers()
                       if d not in modules + drivers and d not in MANDATORY_MODULES]
            if removed and not self.cb_dry.isChecked():
                if QtWidgets.QMessageBox.question(
                        self, "COHIWizard setup",
                        "The following parts will be removed from this installation:\n\n  "
                        + "\n  ".join(removed) + "\n\nContinue?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) != QtWidgets.QMessageBox.Yes:
                    return
            branch = self.cb_branch.currentText()
            dry = self.cb_dry.isChecked()
            shortcut = self.cb_shortcut.isChecked()
            self.inst = Installation(args.target, args.python)
            self.bt_apply.setEnabled(False)
            self.bt_start.setEnabled(False)
            self.bt_close.setEnabled(False)
            self.worker = Worker(lambda: run_install(self.inst, self.gui_ui, branch,
                                                     modules, drivers, dry, shortcut))
            self.worker.sig_done.connect(self.finished)
            self.worker.start()

        def finished(self, ok, err):
            self.worker = None
            self.bt_close.setEnabled(True)
            self.check_drivers()
            if not ok:
                self.append_log("ERROR: " + err)
                QtWidgets.QMessageBox.critical(self, "COHIWizard setup", "Setup failed:\n\n" + err)
                return
            ready = Installation(args.target, args.python).exists() and not self.cb_dry.isChecked()
            self.bt_start.setEnabled(ready)
            if ready and QtWidgets.QMessageBox.question(
                    self, "COHIWizard setup", "Setup finished. Start COHIWizard now?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
                self.start_wizard()

        def start_wizard(self):
            subprocess.Popen([self.inst.python, "COHIWizard.py"], cwd=self.inst.sources)
            self.close()

        def closeEvent(self, ev):
            if self.worker is not None:
                ev.ignore()
            else:
                ev.accept()

    app = QtWidgets.QApplication(sys.argv[:1])
    dlg = SetupDialog()
    dlg.show()
    return app.exec_()


# ---------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(description="COHIWizard setup / module manager")
    ap.add_argument("--target", help="installation directory (contains sources/ and venv/)")
    ap.add_argument("--branch", help=f"GitHub branch (default {DEFAULT_BRANCH} or the installed one)")
    ap.add_argument("--modules", help="comma separated optional modules: "
                    + ",".join(m[0] for m in MODULES if m[0] not in MANDATORY_MODULES))
    ap.add_argument("--drivers", help="comma separated drivers: " + ",".join(DRIVERS))
    ap.add_argument("--no-gui", action="store_true", help="no GUI, use --modules/--drivers")
    ap.add_argument("--yes", action="store_true", help="answer all questions with yes")
    ap.add_argument("--dry-run", action="store_true", help="only show what would be done")
    ap.add_argument("--allow-git-tree", action="store_true", help="also modify a git checkout")
    ap.add_argument("--no-shortcut", action="store_true", help="no desktop/menu shortcut")
    ap.add_argument("--stage2", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--python", help=argparse.SUPPRESS)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.stage2:
        return bootstrap(args)
    args.target = os.path.abspath(args.target or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args.python = args.python or sys.executable
    if args.no_gui:
        return run_headless(args)
    return run_gui(args)


if __name__ == "__main__":
    sys.exit(main())
