"""Exact location of the chunks of RIFF/WAVE IQ files (SDRuno 'auxi', Perseus 'rcvr', ...)

All readers of IQ wav files must start reading the samples exactly at the first byte
of the 'data' chunk. A wrong offset shifts the sample frames: with 16 bit stereo a shift
of 2 bytes swaps I and Q, with 24 bit (6-byte frames) any offset that is not a multiple
of 6 mixes bytes of different samples.

The usual SDRuno header is 216 bytes long (RIFF 12 + fmt 24 + auxi 8+164 + data 8), but
other programs write other layouts, and some write inconsistent size fields, e.g. an
'auxi' chunk of 164 bytes with sdr_nChunkSize = 172. scan() walks the chunks and repairs
such size fields when the content length of the chunk is known; if the layout cannot be
resolved, it raises WavChunkError instead of guessing an offset.

The C++ players (dev_drivers/libs/DspWorkerFL2K.cpp, ADALM2000_universal/DspWorkerADALM.cpp)
implement the same rules.
"""
import os
import struct

STANDARD_DATA_OFFSET = 216
# content lengths of chunks with a fixed layout, used to repair wrong size fields
KNOWN_CONTENT_SIZES = {
    b"fmt ": (16, 18, 40),
    b"auxi": (164,),
    b"rcvr": (34,),
}
_HEADER_READ = 1 << 16       # the chunks in front of 'data' are always within the first 64 kB


class WavChunkError(ValueError):
    """the file is no RIFF/WAVE file or its 'data' chunk cannot be located exactly"""


def _valid_tag(b):
    return len(b) == 4 and all(0x20 <= c <= 0x7E for c in b)


def scan(path):
    """walk the RIFF chunks of a wav file

    :param path: file name
    :return: dict with
        'data_offset': position of the first sample byte
        'data_size':   bytes of sample data actually present (limited by the file size)
        'data_nChunkSize': size field of the data chunk as written in the file
        'chunks':      {tag (str): (header_offset, content_size)} of the chunks in front of 'data'
        'repaired':    list of messages about size fields which had to be corrected
    :raises WavChunkError: if no exact data position can be determined
    """
    filesize = os.path.getsize(path)
    with open(path, "rb") as fh:
        buf = fh.read(_HEADER_READ)
    if len(buf) < 12 or buf[0:4] != b"RIFF" or buf[8:12] != b"WAVE":
        raise WavChunkError(f"{os.path.basename(path)}: no RIFF/WAVE file")

    def tag_at(p):
        return buf[p:p + 4] if p + 8 <= len(buf) else b""

    chunks = {}
    repaired = []
    p = 12
    while p + 8 <= len(buf):
        tag = buf[p:p + 4]
        size = struct.unpack_from("<I", buf, p + 4)[0]
        if tag == b"data":
            offset = p + 8
            available = max(0, filesize - offset)
            return {"data_offset": offset, "data_size": min(size, available), "data_nChunkSize": size,
                    "chunks": chunks, "repaired": repaired}
        if not _valid_tag(tag):
            break
        nxt = p + 8 + size + (size & 1)
        if not _valid_tag(tag_at(nxt)):
            # size field inconsistent with the file: try the known content lengths of this chunk
            for known in KNOWN_CONTENT_SIZES.get(tag, ()):
                cand = p + 8 + known
                if _valid_tag(tag_at(cand)):
                    repaired.append(f"chunk '{tag.decode('ascii')}' at {p}: size field {size}, "
                                    f"actual content {known} bytes")
                    size, nxt = known, cand
                    break
        chunks[tag.decode("ascii")] = (p, size)
        p = nxt
    raise WavChunkError(f"{os.path.basename(path)}: inconsistent wav header, 'data' chunk not found "
                        f"(chunks read: {', '.join(chunks) or 'none'})")


def data_offset(path):
    """position of the first sample byte of a wav file (raises WavChunkError)"""
    return scan(path)["data_offset"]


def seek_to_data(fh, path=None):
    """position the open file fh exactly at the first sample byte
    :param fh: file object opened in binary mode
    :param path: file name (default fh.name)
    :return: data offset
    :raises WavChunkError"""
    offset = data_offset(path or fh.name)
    fh.seek(offset, 0)
    return offset
