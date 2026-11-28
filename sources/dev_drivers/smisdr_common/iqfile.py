"""
smisdr_common/iqfile.py
=======================
Reading of COHIRADIA / SDRuno / Perseus I/Q wav files for the smisdr drivers (no Qt).

* ``read_info``      sample rate, format and centre frequency from the header of one file
                     (needed per file, because a nextfile chain may change them)
* ``IqBlockReader``  blocks of whole I/Q frames; delivers the samples twice: normalized to
                     +-1.0 as float32 (for the DAC encoders) and in the native scale of the
                     file (the monitor data that playrec.showRFdata expects: raw integers
                     for PCM, float for IEEE float - it divides by 2^(bits-1)-1 itself)

The exact start of the sample data is taken from core/wavchunks.py, like in all other drivers.
"""
import struct
from collections import namedtuple

import numpy as np

from core import wavchunks

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_FLOAT = 3
SUPPORTED_BITS = (16, 24, 32)

IqFileInfo = namedtuple("IqFileInfo", "sample_rate fmt_tag bits channels center_freq data_offset")

_AUXI_CENTERFREQ_OFFSET = 8 + 16 + 16       # chunk header + start time + stop time (SYSTEMTIME)
_RCVR_CENTERFREQ_OFFSET = 8                 # chunk header


def read_info(path):
    """Header information of an I/Q wav file. ``center_freq`` is None for files without a
    readable auxi/rcvr chunk (and for *.dat/*.raw files without RIFF header).
    Raises wavchunks.WavChunkError / OSError."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head != b"RIFF":
        # old RFCorder raw files: no header at all, data starts at the standard offset
        return IqFileInfo(None, WAVE_FORMAT_PCM, 16, 2, None, wavchunks.data_offset(path))

    scan = wavchunks.scan(path)
    chunks = scan["chunks"]
    if "fmt " not in chunks:
        raise wavchunks.WavChunkError("{}: no 'fmt ' chunk".format(path))
    with open(path, "rb") as fh:
        fmt_pos = chunks["fmt "][0]
        fh.seek(fmt_pos + 8)
        fmt_tag, channels, sample_rate, _avg, _align, bits = struct.unpack("<HHIIHH", fh.read(16))
        if fmt_tag == 0xFFFE:                       # WAVE_FORMAT_EXTENSIBLE: real tag in the GUID
            fh.seek(fmt_pos + 8 + 24)
            fmt_tag = struct.unpack("<H", fh.read(2))[0]
        center_freq = None
        for tag, offset in (("auxi", _AUXI_CENTERFREQ_OFFSET), ("rcvr", _RCVR_CENTERFREQ_OFFSET)):
            if tag in chunks:
                fh.seek(chunks[tag][0] + offset)
                raw = fh.read(4)
                if len(raw) == 4:
                    center_freq = struct.unpack("<I", raw)[0]
                break
    return IqFileInfo(sample_rate, fmt_tag, bits, channels, center_freq, scan["data_offset"])


def check_format(fmt_tag, bits, channels=2):
    """None if the format can be played, else a message."""
    if channels != 2:
        return "only two-channel (I/Q) files can be played, this file has {} channel(s)".format(channels)
    if fmt_tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_FLOAT):
        return "wFormatTag {} is neither 1 (PCM) nor 3 (IEEE float)".format(fmt_tag)
    if fmt_tag == WAVE_FORMAT_FLOAT and bits != 32:
        return "IEEE float files must have 32 bit per sample, this file has {}".format(bits)
    if bits not in SUPPORTED_BITS:
        return "{} bit per sample is not supported (16, 24 or 32 bit)".format(bits)
    return None


class IqBlockReader:
    """Reads blocks of whole I/Q frames from an open file positioned at the first sample."""

    def __init__(self, fh, fmt_tag, bits, frames_per_block=4096, data_offset=None):
        problem = check_format(fmt_tag, bits)
        if problem:
            raise ValueError(problem)
        self._fh = fh
        self._data_offset = data_offset
        self.fmt_tag = fmt_tag
        self.bits = bits
        self.frame_bytes = 2 * bits // 8
        self.block_bytes = frames_per_block * self.frame_bytes
        self._norm = 1.0 if fmt_tag == WAVE_FORMAT_FLOAT else float(1 << (bits - 1))

    def read(self):
        """-> (monitor, iq, nbytes) or None at the end of the file.
        monitor: interleaved I/Q in the native scale of the file (int16 / float32);
        iq:      interleaved I/Q as float32 normalized to +-1.0; nbytes: bytes read."""
        if self._data_offset is not None:
            # the GUI thread may have jumped in the file (scroll bar): stay on a frame boundary
            misalignment = (self._fh.tell() - self._data_offset) % self.frame_bytes
            if misalignment:
                self._fh.seek(self.frame_bytes - misalignment, 1)
        raw = self._fh.read(self.block_bytes)
        usable = (len(raw) // self.frame_bytes) * self.frame_bytes     # whole frames only
        if usable == 0:
            return None
        raw = raw[:usable]
        if self.fmt_tag == WAVE_FORMAT_FLOAT:
            monitor = np.frombuffer(raw, dtype="<f4").astype(np.float32)
            iq = monitor
        elif self.bits == 16:
            monitor = np.frombuffer(raw, dtype="<i2")
            iq = monitor.astype(np.float32) / np.float32(self._norm)
        elif self.bits == 24:
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            value = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            value = np.where(value & 0x800000, value - 0x1000000, value)
            monitor = value.astype(np.float32)             # raw integer scale, as for PCM
            iq = monitor / np.float32(self._norm)
        else:                                              # 32 bit PCM
            monitor = np.frombuffer(raw, dtype="<i4").astype(np.float32)
            iq = monitor / np.float32(self._norm)
        return monitor, iq, usable
