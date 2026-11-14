"""Paths in the audio station lists (CSV) and m3u playlists of the universal
drivers (ADALM2000_universal, fl2k_universal, stemlab_universal).

- Relative paths in a CSV are relative to the folder of the CSV file,
  relative entries in an m3u are relative to the folder of the m3u file
  (as usual for m3u playlists, e.g. in VLC).
- '/' and '\\' are both accepted as separators.
- Absolute paths and URLs are used unchanged.

So a folder with CSV, m3u files and music can be copied as a whole to any
place, drive or operating system and works without editing, as long as the
files keep their positions relative to each other.

Problems are returned as short messages, so that the drivers can show
skipped stations in the GUI instead of only on the console.

Two formats of the station list exist (config_wizard.yaml: modulator_playlist_mode):
- csv: one line per station 'frequency;bandwidth;programme name;source', the source
  being a URL, an audio file or an m3u playlist;
- m3u: one extended m3u file with all information (parse_station_m3u):

    #EXTM3U
    #EXTPARAM_BW: <global audio bandwidth in kHz>
    #EXTPARAM_FILEPREFIX: <prefix for file names or web addresses>
    #EXTPARAM_LOFREQ: <LO frequency in kHz>          (audio modulator only)
    #EXTPARAM_SAMPLERATE: <sample rate in kHz>       (audio modulator only)
    #EXTPARAM_SILENCE: <silence between the titles in s>
    #EXTPARAM_MODDEPTH: <modulation depth 0..1>
    #EXTPARAM_RECLENGTH / #EXTPARAM_OUTPUTFILE      (only for COHI-Coder)
    #PLAYLIST: <programme name>
    #EXTGRP: <carrier frequency in kHz>
    #EXTPARAM_BW: <optional bandwidth of this station in kHz>
    #EXTINF: -1,<artist> - <title>
    <file or web address>
    ...
"""
import os
import re
import subprocess
import tempfile

_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
PLAYLIST_EXT = (".m3u", ".m3u8", ".pls")


def is_url(s: str) -> bool:
    """http://, https://, rtsp://, ..."""
    return bool(_URL_RE.match(s.strip()))


def is_absolute(p: str) -> bool:
    """Absolute on Windows or Linux: '/...', '\\...', '\\\\server\\...', 'C:\\...', 'C:/...'."""
    return p.startswith(("/", "\\")) or bool(_DRIVE_RE.match(p)) or os.path.isabs(p)


def resolve(p: str, base_dir: str) -> str:
    """Path p as written in a CSV/m3u -> usable path; relative to base_dir."""
    p = p.strip()
    if not p or is_url(p):
        return p
    p = os.path.expanduser(p)
    if is_absolute(p):
        return p
    return os.path.normpath(os.path.join(base_dir, p.replace("\\", "/")))


def is_playlist(p: str) -> bool:
    """Local m3u/m3u8/pls file (not a URL)."""
    return p.lower().endswith(PLAYLIST_EXT) and not is_url(p)


def resolve_csv_source(source: str, csv_path: str) -> str:
    """Source column of a station CSV, relative paths based on the CSV folder."""
    return resolve(source, os.path.dirname(os.path.abspath(csv_path)))


def read_m3u(path: str):
    """Entries of a local m3u file -> (entries, message).

    entries: existing local files (relative ones resolved against the folder
    of the m3u) and http(s) URLs, in the order of the file.
    message: None if at least one entry is playable, otherwise the reason.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [l.strip() for l in fh]
    except OSError as exc:
        return [], f"playlist not found or not readable: {path} ({exc.strerror or exc})"
    base = os.path.dirname(os.path.abspath(path))
    entries, missing = [], []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("http://", "https://")):
            entries.append(line)
            continue
        f = resolve(line, base)
        if os.path.isfile(f):
            entries.append(f)
        else:
            missing.append(line)
    if entries:
        return entries, None
    if missing:
        return [], (f"no playable entry in {path}: {len(missing)} file(s) not found, "
                    f"e.g. {missing[0]}")
    return [], f"playlist is empty: {path}"


def check_local_file(source: str):
    """Message if a local (non-URL, non-playlist) source file does not exist."""
    if source and not is_url(source) and not is_playlist(source) and not os.path.isfile(source):
        return f"file not found: {source}"
    return None


def skipped_message(skipped) -> str:
    """One text for the GUI from [(station name, reason), ...]."""
    lines = [f"- {name}: {reason}" for name, reason in skipped]
    return ("The following audio stations are not played:\n\n" + "\n".join(lines)
            + "\n\nRelative paths in the station list (csv or m3u) refer to the folder of "
              "the station list, relative entries in an m3u file to the folder of that file.")


# ---------------------------------------------------------------------------
# station lists: csv and extended m3u
# ---------------------------------------------------------------------------

STATION_M3U_EXT = (".m3u", ".m3u8")
DEFAULT_BW_HZ = 9000.0


def is_station_m3u(path: str) -> bool:
    """station list in the extended m3u format (not a csv)"""
    return bool(path) and path.lower().endswith(STATION_M3U_EXT) and not is_url(path)


def parse_frequency(s: str, unit: float = 1.0) -> float:
    """'576', '576 kHz', '1.25 MHz', '4,5' -> Hz; a plain number is multiplied by unit"""
    s = s.strip().replace(",", ".")
    sl = s.lower()
    for suffix, factor in (("mhz", 1e6), ("khz", 1e3), ("hz", 1.0)):
        if sl.endswith(suffix):
            return float(s[:-len(suffix)].strip()) * factor
    return float(s) * unit


def parse_seconds(s: str) -> float:
    """'hh:mm:ss', 'mm:ss' or seconds -> seconds"""
    parts = s.strip().replace(",", ".").split(":")
    value = 0.0
    for p in parts:
        value = value * 60 + float(p)
    return value


def parse_station_csv(path: str):
    """csv 'frequency;bandwidth;programme name;source' -> (stations, problems)"""
    import csv
    quotes = str.maketrans({0x201C: 0x22, 0x201D: 0x22})
    stations, problems = [], []
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            rows = list(csv.reader((l.translate(quotes) for l in fh), delimiter=";",
                                   quotechar='"', skipinitialspace=True))
    except OSError as exc:
        return [], [f"station list not readable: {path} ({exc.strerror or exc})"]
    for lineno, parts in enumerate(rows, 1):
        if not parts or parts[0].strip().startswith("#"):
            continue
        if len(parts) < 4:
            problems.append(f"line {lineno}: 4 columns expected")
            continue
        freq_s, bw_s, name, source = (p.strip() for p in parts[:4])
        if freq_s.lower() in ("frequenz", "frequency", "freq"):
            continue
        try:
            freq_hz = parse_frequency(freq_s)
            bw_hz = parse_frequency(bw_s) if bw_s else DEFAULT_BW_HZ
        except ValueError:
            problems.append(f"line {lineno}: cannot read '{freq_s}' / '{bw_s}'")
            continue
        stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz, "name": name,
                         "url": resolve_csv_source(source, path)})
    return stations, problems


PARAM_KEYS = ["RECLENGTH", "BW", "OUTPUTFILE", "FILEPREFIX", "LOFREQ", "SAMPLERATE",
              "SILENCE", "MODDEPTH"]          # order in written files
PARAM_ALIASES = {"FILEPREXIX": "FILEPREFIX"}  # spelling in early example files


def read_station_m3u_raw(path: str):
    """extended m3u as written in the file -> (params, stations, problems)

    params:   {KEY: text} of the global #EXTPARAM_KEY lines (KEY from PARAM_KEYS)
    stations: [{"name", "freq", "bw", "titles": [[title, entry], ...], "line"}] with the
              texts of #PLAYLIST, #EXTGRP, #EXTPARAM_BW and the #EXTINF title / entry lines
              unchanged (prefix not applied, paths not resolved); used by the station editor
    problems: messages; an unreadable file gives ([], {}, [message])
    """
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        return {}, [], [f"station list not readable: {path} ({exc.strerror or exc})"]
    params, stations, problems, cur, title = {}, [], [], None, ""
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("#"):
            if cur is None:
                problems.append(f"line {lineno}: entry before the first #PLAYLIST ignored")
            else:
                cur["titles"].append([title, line])
            title = ""
            continue
        tag, _, value = line[1:].partition(":")
        tag, value = tag.strip().upper(), value.strip()
        if tag == "PLAYLIST":
            cur = {"name": value, "freq": "", "bw": "", "titles": [], "line": lineno}
            stations.append(cur)
        elif tag == "EXTGRP":
            if cur is None:
                problems.append(f"line {lineno}: #EXTGRP before the first #PLAYLIST ignored")
            else:
                cur["freq"] = value
        elif tag == "EXTINF":
            title = value.split(",", 1)[1].strip() if "," in value else ""
        elif tag.startswith("EXTPARAM_"):
            key = tag[len("EXTPARAM_"):]
            key = PARAM_ALIASES.get(key, key)
            if key == "BW" and cur is not None:
                cur["bw"] = value
            elif key in PARAM_KEYS:
                params[key] = value
            else:
                problems.append(f"line {lineno}: unknown parameter #{tag} ignored")
        # #EXTM3U and other tags carry nothing
    return params, stations, problems


def write_station_m3u(path: str, params: dict, stations: list):
    """writes an extended m3u from the structures of read_station_m3u_raw"""
    out = ["#EXTM3U", ""]
    for key in PARAM_KEYS:
        out.append(f"#EXTPARAM_{key}: {params.get(key, '')}".rstrip())
    for sta in stations:
        out += ["", "", f"#PLAYLIST: {sta['name']}", f"#EXTGRP: {sta['freq']}"]
        if str(sta.get("bw", "")).strip():
            out.append(f"#EXTPARAM_BW: {sta['bw']}")
        for title, entry in sta["titles"]:
            out += [f"#EXTINF: -1,{title}", entry]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


def entry_path(entry: str, prefix: str, base_dir: str) -> str:
    """entry line of the extended m3u -> file path or URL: prefix only before relative
    entries (not before URLs or absolute paths), relative paths based on base_dir"""
    if prefix and not is_url(entry) and not is_absolute(entry):
        entry = prefix + entry
    return resolve(entry, base_dir)


def parse_station_m3u(path: str):
    """extended m3u (see module docstring) -> (stations, params, problems)

    stations: dicts with freq_hz, bw_hz, name and entries (resolved files / URLs)
    params:   bw_hz, prefix, lo_hz, samplerate_hz, silence_s, moddepth,
              reclength_s, outputfile - only the ones given in the file
    problems: messages for the user; stations with problems are left out, missing
              local files are only reported
    """
    raw, blocks, problems = read_station_m3u_raw(path)
    if not raw and not blocks and problems and problems[0].startswith("station list not readable"):
        return [], {}, problems
    readers = {"RECLENGTH": ("reclength_s", parse_seconds),
               "OUTPUTFILE": ("outputfile", str),
               "FILEPREFIX": ("prefix", str),
               "LOFREQ": ("lo_hz", lambda v: parse_frequency(v, 1e3)),
               "SAMPLERATE": ("samplerate_hz", lambda v: parse_frequency(v, 1e3)),
               "SILENCE": ("silence_s", parse_seconds),
               "MODDEPTH": ("moddepth", lambda v: float(v.replace(",", "."))),
               "BW": ("bw_hz", lambda v: parse_frequency(v, 1e3))}
    params = {}
    for key, value in raw.items():
        if not value:
            continue
        name, read = readers[key]
        try:
            params[name] = read(value)
        except ValueError:
            problems.append(f"#EXTPARAM_{key}: cannot read '{value}'")
    if "moddepth" in params:
        m = params["moddepth"]
        params["moddepth"] = min(1.0, max(0.0, m / 100.0 if m > 1.0 else m))

    prefix = params.get("prefix", "")
    base = os.path.dirname(os.path.abspath(path))
    stations, used = [], {}
    for idx, b in enumerate(blocks):
        name = b["name"] or f"station {idx + 1}"
        where = f"'{name}' (line {b['line']})"
        if not b["freq"]:
            problems.append(f"{where}: no frequency (#EXTGRP), station left out")
            continue
        try:
            freq_hz = parse_frequency(b["freq"], 1e3)
            bw_hz = parse_frequency(b["bw"], 1e3) if b["bw"] else params.get("bw_hz", DEFAULT_BW_HZ)
        except ValueError:
            problems.append(f"{where}: cannot read frequency '{b['freq']}' / bandwidth '{b['bw']}', "
                            "station left out")
            continue
        if not b["titles"]:
            problems.append(f"{where}: no file or web address, station left out")
            continue
        if freq_hz in used:
            problems.append(f"{where}: {freq_hz / 1e3:g} kHz is already used by "
                            f"'{used[freq_hz]}', station left out")
            continue
        used[freq_hz] = name
        entries = [entry_path(e, prefix, base) for _, e in b["titles"]]
        missing = [e for e in entries if not is_url(e) and not os.path.isfile(e)]
        if missing:
            problems.append(f"{where}: {len(missing)} of {len(entries)} file(s) not found, "
                            f"e.g. {missing[0]}")
        stations.append({"freq_hz": freq_hz, "bw_hz": bw_hz, "name": name, "entries": entries})
    return stations, params, problems


def parse_station_list(path: str):
    """csv or extended m3u -> (stations, params, problems); params empty for csv"""
    if is_station_m3u(path):
        return parse_station_m3u(path)
    stations, problems = parse_station_csv(path)
    return stations, {}, problems


def band_problem(stations, lo_hz: float, samplerate_hz: float):
    """Message if carriers (frequency +- bandwidth/2) lie outside the band of the IQ
    file, i.e. outside LO +- samplerate/2; None if all fit"""
    low, high = lo_hz - samplerate_hz / 2.0, lo_hz + samplerate_hz / 2.0
    outside = [s for s in stations
               if s["freq_hz"] - s["bw_hz"] / 2.0 < low or s["freq_hz"] + s["bw_hz"] / 2.0 > high]
    if not outside:
        return None
    names = "\n".join(f"- {s['name']}: {s['freq_hz'] / 1e3:g} kHz" for s in outside[:10])
    more = f"\n... and {len(outside) - 10} more" if len(outside) > 10 else ""
    return (f"The following stations of the station list lie outside the band of the IQ file "
            f"({low / 1e3:g} - {high / 1e3:g} kHz, LO {lo_hz / 1e3:g} kHz, "
            f"sample rate {samplerate_hz / 1e3:g} kHz):\n\n{names}{more}\n\n"
            f"Please load a station list that is compatible with the IQ file.")


def silence_file(ffmpeg_bin: str, seconds: float):
    """mp3 with 'seconds' of silence (cached in the temp folder); None if ffmpeg fails"""
    path = os.path.join(tempfile.gettempdir(), f"cohi_silence_{seconds:g}s.mp3")
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return path
    cmd = [ffmpeg_bin, "-y", "-loglevel", "error", "-f", "lavfi",
           "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds:g}",
           "-c:a", "libmp3lame", "-b:a", "64k", path]
    try:
        subprocess.run(cmd, timeout=30, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return path
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[playlist_paths] silence file could not be created ({exc}); "
              "titles are played without pauses")
        return None


def load_station_m3u(path: str, ffmpeg_bin: str, tempfiles: list):
    """stations of an extended m3u, prepared for the drivers -> (stations, moddepth)

    Each station gets a 'url' as in the csv: its single entry, or a temporary m3u with
    all entries (and the silence of #EXTPARAM_SILENCE between them), which the drivers
    play in a loop like any local m3u. The temporary files are appended to tempfiles
    (removed by the driver after STOP). moddepth is None if the file gives none.
    """
    stations, params, problems = parse_station_m3u(path)
    for p in problems:
        print(f"[playlist_paths] {path}: {p}")
    silence = params.get("silence_s", 0.0)
    pause = None
    if silence > 0 and any(len(s["entries"]) > 1 for s in stations):
        pause = silence_file(ffmpeg_bin, silence)
    for idx, sta in enumerate(stations):
        if len(sta["entries"]) == 1:
            sta["url"] = sta["entries"][0]
            continue
        with tempfile.NamedTemporaryFile(mode="w", suffix=".m3u", prefix=f"cohi_station{idx}_",
                                         delete=False, encoding="utf-8") as fh:
            for e in sta["entries"]:
                fh.write(e + "\n")
                if pause:
                    fh.write(pause + "\n")
        sta["url"] = fh.name
        tempfiles.append(fh.name)
    return stations, params.get("moddepth")
