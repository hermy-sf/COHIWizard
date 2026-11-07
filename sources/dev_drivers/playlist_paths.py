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
"""
import os
import re

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
            + "\n\nRelative paths in the station CSV refer to the folder of the CSV "
              "file, relative entries in an m3u file to the folder of the m3u file.")
