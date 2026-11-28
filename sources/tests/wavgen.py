"""Synthetic SDRuno-style I/Q wav files for the tests (216 byte header with auxi chunk)."""
import struct

import numpy as np


def make_wav(path, iq_complex, sample_rate, center_freq, bits=16, float_format=False):
    """iq_complex: complex array with |x| <= 1 -> interleaved I/Q wav file"""
    interleaved = np.empty(2 * len(iq_complex), dtype=np.float64)
    interleaved[0::2] = iq_complex.real
    interleaved[1::2] = iq_complex.imag
    if float_format:
        assert bits == 32
        payload = interleaved.astype("<f4").tobytes()
        tag = 3
    elif bits == 16:
        payload = np.rint(interleaved * 32767).astype("<i2").tobytes()
        tag = 1
    elif bits == 24:
        ints = np.rint(interleaved * 8388607).astype(np.int32)
        payload = b"".join(struct.pack("<i", v)[:3] for v in ints)
        tag = 1
    elif bits == 32:
        payload = np.rint(interleaved * 2147483647).astype("<i4").tobytes()
        tag = 1
    else:
        raise ValueError(bits)
    block_align = 2 * bits // 8
    fmt = struct.pack("<HHIIHH", tag, 2, sample_rate, sample_rate * block_align, block_align, bits)
    auxi = bytearray(164)
    struct.pack_into("<I", auxi, 32, int(center_freq))           # after 2 x 16 byte SYSTEMTIME
    struct.pack_into("<I", auxi, 36, 0)
    body = (b"WAVE"
            + b"fmt " + struct.pack("<I", 16) + fmt
            + b"auxi" + struct.pack("<I", 164) + bytes(auxi)
            + b"data" + struct.pack("<I", len(payload)) + payload)
    with open(path, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", len(body)) + body)
    return path


def tone(n_frames, sample_rate, offset_hz, amplitude=0.5):
    t = np.arange(n_frames) / sample_rate
    return amplitude * np.exp(2j * np.pi * offset_hz * t)
