# COHIWizard

> **Development branch `cohiwizard_v2.3` – experimental.**
> This branch contains the newest functions of COHIWizard v2.3 but is less tested than the stable
> release. When downloading and executing it, unexpected issues may arise. The stable version is
> on the branch `main` (v2.2). Please also read the description of the experimental versions on the
> COHIRADIA webpage: [Software – Experimental Versions](https://www.cohiradia.org/en/docs/documentation/software/#experimental-versions).

COHIWizard is an application for the playback, recording, analysis and processing of broadband RF
signals. Its main purpose is archiving AM radio bands like LW, MW, SW and VLF in the context of
[COHIRADIA](https://www.cohiradia.org/en/), but other purposes can be thought of. Recordings are
stored as IQ data files with 32 bits per sample (2 x 16 bit complex) and an extended wav header in
the format used by most software defined radios (SDR).

Suitable recordings can be played back into historic radio receivers with an external antenna jack:
all transmitters active at the time of the recording can then be tuned through and listened to on
the radio. Information on hardware setup and an archive with many recordings from 2006 on can be
found on the [COHIRADIA webpage](https://www.cohiradia.org/en/).

## Supported hardware

| Device | Playback | Recording |
|---|---|---|
| [STEMLAB 125-14 / 125-10](https://redpitaya.com/stemlab-125-14/) (Red Pitaya), via LAN/WLAN | yes | yes |
| FL2000 USB-VGA dongle ([osmo-fl2k](https://osmocom.org/projects/osmo-fl2k/wiki)), 8 bit | yes | no |
| [ADALM2000](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/adalm2000.html) (Analog Devices), USB | yes | no |

Each device is operated by a driver in `sources/dev_drivers`:

- **Universal drivers (recommended):** `fl2k_universal`, `stemlab_universal`, `ADALM2000_universal`.
  Besides plain IQ playback they can add AM carriers generated from audio sources (web radio streams,
  local audio files, m3u/pls playlists) to the IQ band or synthesize a band from audio sources only
  ("modulator types" *IQ band only*, *IQ band and audio modulator*, *audio modulator only*).
  The computationally expensive parts run in C++ libraries.
- **Reference drivers:** `fl2k_stream`, `stemlab_125_14`, `ADALM2000`, the drivers of v2.2
  (IQ playback only).

## What is new in v2.3

- **New installation:** Windows installer and setup tool `cohi_setup.py` (Windows and LINUX), which
  download the program directly from GitHub, manage modules and drivers and perform updates. The
  zip file with `SDR_COHIWizard_v2.x.exe` is no longer used.
- **New driver architecture** with universal drivers, audio modulator, audio station lists (csv)
  and a mixer slider for the level of the audio carriers.
- **GUI:** skin 5 as scalable default for PC screens, skins 2 and 3 for 7" displays (e.g. Raspberry
  Pi); a configuration dialog for rarely used settings; elapsed / total time display; a startup
  notice while the SDR device is starting.
- **Player:** jumps and file length from the true file size (also files > 4 GB and `*.dat` files),
  click into the scroll bar to jump; opening another file while playing stops the old one and starts
  the new one; robust parsing of wav headers with additional chunks.
- **WAV header editor:** button 'Overwrite Header' (shortcut Alt+H) instead of the entry in the
  File menu.

Details are given in the user manual (see [Documentation](#documentation)).

## Installation

From version 2.3 on COHIWizard always runs from its Python sources in a virtual Python environment
of its own. Installation, updates and the selection of modules and device drivers are done by the
setup tool `cohi_setup.py`.

### Windows 10/11 (64 bit): installer (recommended)

1. Download the installer
   **[COHIWizard_Setup_2.3.exe](https://cohiradia.radiomuseum.org/download/software/COHI_installer_v1.1/Output/COHIWizard_Setup_2.3.exe)**
   and start it.
2. The installer needs **no administrator rights**. It installs for the current user, by default
   into `%USERPROFILE%\COHIWizard`, a private Python 3.10 (nothing is registered in Windows) and the
   current setup tool, which it then starts.
3. A console window opens in which the setup tool creates the virtual environment and installs the
   required Python packages. **This can take 10 – 30 minutes**, please be patient.
4. In the window *COHIWizard setup* select the modules (tabs) and device drivers and press
   *Install / apply changes*. The setup tool also installs the external software needed by the
   selected drivers after a confirmation: ffmpeg, the osmo-fl2k library and the USB driver tool
   Zadig (FL2K dongle), libm2k (ADALM2000).
5. Start COHIWizard from the setup window or later from the start menu (*COHIWizard*; for error
   messages *COHIWizard (with console for error messages)*).

The start menu also contains *COHIWizard Setup (manage modules and drivers)* and the uninstaller.

### Windows, alternative with an installed Python

Download [`cohi_setup.bat`](https://raw.githubusercontent.com/hermy-sf/COHIWizard/cohiwizard_v2.3/sources/cohi_setup.bat)
and start it. It looks for an installed Python 3.10 – 3.13 (if none is found, it installs Python
3.10.11 for the current user), fetches the current `cohi_setup.py` from GitHub and starts it.

### LINUX (tested with Debian 12 and 13 on x86_64)

Download the setup tool
[`cohi_setup.py`](https://raw.githubusercontent.com/hermy-sf/COHIWizard/cohiwizard_v2.3/sources/cohi_setup.py)
and start it with the system Python (3.10 – 3.13):

```bash
wget https://raw.githubusercontent.com/hermy-sf/COHIWizard/cohiwizard_v2.3/sources/cohi_setup.py
python3 cohi_setup.py
```

The tool asks for the installation directory (default `~/COHIWizard`), creates the virtual
environment, installs the Python packages and opens the setup window. Missing system packages
(python3-venv, ffmpeg, osmo-fl2k, udev rules for the FL2K dongle and the ADALM2000) are installed with
apt after a query (root rights via sudo or pkexec). It creates the launchers `COHIWizard.sh` and
`COHIWizard_setup.sh` and a menu entry.

Without a graphical desktop the setup tool can be used from the command line, e.g.

```bash
python3 cohi_setup.py --no-gui --modules synthesizer,annotator --drivers fl2k_universal
python3 cohi_setup.py --help
```

### Updating, adding or removing modules and drivers

Start the setup tool again: start menu entry *COHIWizard Setup*, `COHIWizard_setup.bat` /
`COHIWizard_setup.sh` in the installation directory, or in the running COHIWizard via the menu
*Setup → Install / remove modules and drivers ...*. Only new or changed files are downloaded; your
settings in `config_wizard.yaml` are kept. The GitHub branch can be selected in the setup window:
`main` (stable) or a development branch such as `cohiwizard_v2.3`.

### Developers: working with a clone of the repository

1. Install Python 3.10 – 3.13 (development is done with 3.10.11).
2. Clone the branch and create a virtual environment:

   ```bash
   git clone -b cohiwizard_v2.3 https://github.com/hermy-sf/COHIWizard.git
   cd COHIWizard
   python -m venv venv
   ```

3. Activate the virtual environment – Windows: `venv\Scripts\activate`,
   LINUX: `source venv/bin/activate` – and install the packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the program:

   ```bash
   cd sources
   python COHIWizard.py
   ```

In a git checkout the setup tool does not change any files (it only performs a dry run, unless it is
called with `--allow-git-tree`). The external software for the drivers (ffmpeg, osmo-fl2k, libm2k,
Zadig under Windows) then has to be installed manually; see the user manual, section *Device
drivers*. The Windows installer itself is built from `installer/` (Inno Setup, `build_installer.ps1`).

## Documentation

- **User manual (v2.3):**
  [`documentation/User_Manual_COHIWizard_v2.3_en.pdf`](https://github.com/hermy-sf/COHIWizard/blob/cohiwizard_v2.3/documentation/User_Manual_COHIWizard_v2.3_en.pdf).
  The setup tool installs it into the `documentation` folder of the installation; in COHIWizard it
  is opened with the menu *Documentation → open pdf*. It describes installation, all tabs, the device
  drivers and the configuration files.
- **Experimental versions:** description on the COHIRADIA webpage,
  [Software – Experimental Versions](https://www.cohiradia.org/en/docs/documentation/software/#experimental-versions).
- **COHIRADIA project, hardware setup and recordings:** [www.cohiradia.org](https://www.cohiradia.org/en/).
- **Source code documentation** (Sphinx, work in progress): folder [`docs/`](docs/).
- **Interface of the tab modules:** [`documentation/standard_module_methods.md`](documentation/standard_module_methods.md).

## Branches

- `main`: stable release (v2.2).
- `cohiwizard_v2.3`: development branch of v2.3 (this branch), experimental.

## License

GNU General Public License v3.0, see [LICENSE](LICENSE).
