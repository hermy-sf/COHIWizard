"""
smisdr_common/protocol.py
=========================
Protocol and signal helpers for the smiSDR / parlioSDR drivers ``smisdr_iq`` and
``smisdr_raw``.  Pure Python / NumPy - no Qt, no sockets - so everything in here can be
tested without a GUI and without hardware (see sources/tests/test_smisdr_drivers.py).

Both drivers talk to the same TCP interface (https://github.com/radiolab81/smisdr):

  control port (default 5000, TCP, OPTIONAL, one short connection per command)
      "width <8|16>\\n"            DAC bus width
      "rate <MSps, 1 decimal>\\n"  bus sample rate
  data port (default 1234, TCP, ONE long connection)
      smisdr_raw : finished RF samples (8 bit int8, or int16 with 8/10/12/14 bit values)
      smisdr_iq  : baseband I/Q as tagged 16 bit words with in-band signalling for the
                   DUC gateware (NCO shift 'S' and input rate 'R'):
                     bit 15:14 = 00  I sample, 14 bit signed in bit 13:0
                     bit 15:14 = 01  Q sample, 14 bit signed in bit 13:0
                     bit 15:14 = 10  command word: bit 13:8 = index, bit 7:0 = payload
                     bit 15:14 = 11  execute: payload 'E'

The protocol follows COHI-Player-Universal (smisdr_backend.py / smisdr_iq_backend.py) and
DspWorker::run_IQ_engine of COHIRADIAStreamer, both tested on smiSDR and parlioSDR.
"""
import time

import numpy as np

# --------------------------------------------------------------------------------------
# smisdr_iq: DUC gateware with in-band signalling
# --------------------------------------------------------------------------------------
DEFAULT_REF_CLOCK_HZ = 50_000_000.0     # reference clock of the DUC; output rate == this clock

TAG_I = 0
TAG_Q = 1
TAG_CMD = 2
TAG_EXEC = 3
CMD_INIT_INDEX = 63
CMD_SHIFT = ord("S")        # NCO frequency shift = centre frequency of the recording
CMD_RATE = ord("R")         # sample rate of the incoming I/Q data
CMD_EXECUTE = ord("E")

IQ_BITS = 14
IQ_MIN = -(1 << (IQ_BITS - 1))          # -8192
IQ_MAX = (1 << (IQ_BITS - 1)) - 1       # +8191
IQ_MASK = (1 << IQ_BITS) - 1            # 0x3FFF
IQ_FULL_SCALE = float(1 << (IQ_BITS - 1))   # normalized +-1.0 -> +-8192 (clipped to 8191)

# The gateware (multirate_upsampler.v) knows exactly three input rates and picks one by
# thresholds on the rate word: any other rate would be treated as the nearest class and
# play back at the wrong speed / frequency.
SUPPORTED_IQ_RATES_HZ = (250_000, 500_000, 1_250_000)
RATE_TOLERANCE = 0.001

# highest signal edge relative to the Nyquist frequency of the output rate
MAX_EDGE_OF_NYQUIST = 0.95

# --------------------------------------------------------------------------------------
# smisdr_raw: finished RF samples, up-conversion on the host (cohi_native_upconverter)
# --------------------------------------------------------------------------------------
SMISDR_RATES_HZ = (5_000_000, 10_000_000, 12_500_000)
RATE_AUTO = "auto"
FORMAT_8 = 8                # int8 (optionally unsigned = offset binary)
FORMAT_8_IN_16 = 816        # int16 little endian, values in the 8 bit range
FORMATS_WIDE = (10, 12, 14) # DAC bits, transferred as int16 little endian
FORMATS = (FORMAT_8, FORMAT_8_IN_16) + FORMATS_WIDE

# Upconverter parameters as in COHI-Player-Universal (fl2k_cpp_backend.py)
UPCONVERTER_OUTPUT_SHIFT = 6
UPCONVERTER_FIR_TAPS = 15


# ======================================================================================
# smisdr_iq
# ======================================================================================
def _finite(values):
    """float32 copy in which NaN / inf (corrupt float files) are 0: one such sample must neither
    become full scale nor send the peak limiter down by 300 dB"""
    return np.nan_to_num(np.asarray(values, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def make_cmd_word(ctrl, index, payload):
    """16 bit word: bit 15:14 = ctrl, bit 13:8 = index, bit 7:0 = payload."""
    return ((ctrl & 0x03) << 14) | ((index & 0x3F) << 8) | (payload & 0xFF)


def calculate_ftw(frequency_hz, ref_clk_hz=DEFAULT_REF_CLOCK_HZ):
    """Phase tuning word (32 bit): frequency / ref_clk * 2^32."""
    ftw = int(round(float(frequency_hz) / float(ref_clk_hz) * 4294967296.0))
    if not 0 <= ftw <= 0xFFFFFFFF:
        raise ValueError("frequency {} Hz outside the range of the tuning word "
                         "(reference clock {} Hz)".format(frequency_hz, ref_clk_hz))
    return ftw


def build_command(opcode, ftw):
    """In-band command with a 32 bit value as little endian 16 bit words:
    (10, 63, opcode), (10, 0..3, FTW byte 0..3 LSB first), (11, 0, 'E')."""
    return [
        make_cmd_word(TAG_CMD, CMD_INIT_INDEX, opcode),
        make_cmd_word(TAG_CMD, 0, ftw & 0xFF),
        make_cmd_word(TAG_CMD, 1, (ftw >> 8) & 0xFF),
        make_cmd_word(TAG_CMD, 2, (ftw >> 16) & 0xFF),
        make_cmd_word(TAG_CMD, 3, (ftw >> 24) & 0xFF),
        make_cmd_word(TAG_EXEC, 0, CMD_EXECUTE),
    ]


def build_init_sequence(center_freq_hz, sample_rate_hz, ref_clk_hz=DEFAULT_REF_CLOCK_HZ):
    """Bytes for the start of a track: 'S' (NCO) followed by 'R' (input rate)."""
    words = (build_command(CMD_SHIFT, calculate_ftw(center_freq_hz, ref_clk_hz))
             + build_command(CMD_RATE, calculate_ftw(sample_rate_hz, ref_clk_hz)))
    return np.asarray(words, dtype="<u2").tobytes()


def _tag_values(values):
    """14 bit signed values (I, Q, I, Q ...) -> tagged little endian 16 bit words."""
    masked = values.astype(np.int16).astype(np.uint16) & IQ_MASK
    words = np.empty(len(masked), dtype="<u2")
    words[0::2] = masked[0::2] | (TAG_I << 14)
    words[1::2] = masked[1::2] | (TAG_Q << 14)
    return words.tobytes()


def encode_iq_words(iq, gain=1.0):
    """Interleaved float32 I/Q, normalized to +-1.0 = full scale of the source format
    -> tagged 16 bit words (bytes).

    ``gain`` 1.0 corresponds to the plain 16 -> 14 bit reduction of run_IQ_engine
    (a 16 bit WAV sample is divided by 4); values are limited to the 14 bit range.
    An odd trailing sample (half an I/Q pair) is dropped."""
    count = (len(iq) // 2) * 2
    scaled = _finite(iq[:count]) * np.float32(gain * IQ_FULL_SCALE)
    return _tag_values(np.clip(np.rint(scaled), IQ_MIN, IQ_MAX))


def silence_words(iq_pairs):
    """Zero I/Q (e.g. at pause / end of play) so that the DAC does not stay on the last value."""
    return encode_iq_words(np.zeros(2 * int(iq_pairs), dtype=np.float32))


def decode_iq_words(payload):
    """Tagged words -> complex baseband in the range +-1 (inverse of encode_iq_words,
    used by the tests and debug displays)."""
    words = np.frombuffer(payload, dtype="<u2")
    count = (len(words) // 2) * 2
    raw = (words[:count] & IQ_MASK).astype(np.int32)
    raw = np.where(raw > IQ_MAX, raw - (1 << IQ_BITS), raw).astype(np.float32) / IQ_FULL_SCALE
    return raw[0::2] + 1j * raw[1::2]


def supported_iq_rate(sample_rate_hz):
    """Nominal DUC input rate for a recording rate, or None if the gateware does not support it."""
    for rate in SUPPORTED_IQ_RATES_HZ:
        if abs(sample_rate_hz - rate) <= rate * RATE_TOLERANCE:
            return rate
    return None


def format_iq_bus_rate_command(sample_rate_hz):
    """'rate <MSps>' as in run_IQ_engine: I and Q are sent one after the other as 16 bit
    words, so the BUS rate is 2 x the I/Q sample rate (250 kSps -> 0.5, 500 kSps -> 1.0,
    1.25 MSps -> 2.5)."""
    return "rate {:.1f}\n".format(2.0 * sample_rate_hz / 1_000_000.0)


def iq_edge_problem(center_freq_hz, sample_rate_hz, ref_clk_hz):
    """None if the signal fits below the Nyquist limit of the DUC output, else a message."""
    upper_edge = center_freq_hz + sample_rate_hz / 2.0
    limit = MAX_EDGE_OF_NYQUIST * ref_clk_hz / 2.0
    if upper_edge > limit:
        return ("recording (up to {} Hz) is above the usable range of the DUC ({} Hz) - "
                "check smisdr_iq_ref_clock").format(int(upper_edge), int(limit))
    return None


# ======================================================================================
# smisdr_raw
# ======================================================================================
def parse_control_port(value, default=5000):
    """Port number, or None if the control port is switched off
    (0 / off / none / no / false; note: YAML reads an unquoted 'off' as False)."""
    if value is None:
        return default
    if value is False:
        return None
    if isinstance(value, str) and value.strip().lower() in ("", "off", "none", "no", "false", "0"):
        return None
    port = int(value)
    if port == 0:
        return None
    if not 1 <= port <= 65535:
        raise ValueError("port out of range 1..65535")
    return port


def parse_rate_setting(value):
    """'auto' or 5 / 10 / 12.5 (MSps, also 5000000 / 12500000 Hz) -> 'auto' or Hz (int).
    Returns None for anything else."""
    if value is None:
        return RATE_AUTO
    if isinstance(value, str):
        text = value.strip().lower().replace(",", ".")
        if text == RATE_AUTO:
            return RATE_AUTO
        text = text.replace("msps", "").replace("mhz", "").strip()
        try:
            number = float(text)
        except ValueError:
            return None
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
    else:
        return None
    hz = number * 1_000_000 if number < 1_000_000 else number
    for allowed in SMISDR_RATES_HZ:
        if abs(hz - allowed) < 1.0:
            return allowed
    return None


def format_rate_command(rate_hz):
    return "rate {:.1f}\n".format(rate_hz / 1_000_000.0)


def format_width_command(sample_format):
    return "width {}\n".format(8 if sample_format == FORMAT_8 else 16)


def choose_target_rate(sample_rate, center_freq, rate_setting, has_control_port):
    """Output rate in Hz (5 / 10 / 12.5 MSps), or None if the recording does not fit.
    'auto' picks the lowest rate with the signal edge below 95 % of Nyquist; it needs the
    control port, because the hardware has to be told the rate."""
    upper_edge = center_freq + sample_rate / 2.0
    if rate_setting == RATE_AUTO:
        if not has_control_port:
            return None
        candidates = SMISDR_RATES_HZ
    else:
        candidates = (rate_setting,)
    for rate in candidates:
        if upper_edge <= MAX_EDGE_OF_NYQUIST * rate / 2.0 and sample_rate <= rate:
            return rate
    return None


def build_upconverter_command(tool_path, sample_rate, center_freq, target_rate, sample_format):
    """Command line of cohi_native_upconverter (stdin: int16 interleaved I/Q at
    ``sample_rate``; stdout: real RF samples at ``target_rate``)."""
    command = [
        tool_path,
        "--sample-rate", str(int(sample_rate)),
        "--center-freq", str(int(round(center_freq))),
        "--target-rate", str(int(target_rate)),
        "--output-shift", str(UPCONVERTER_OUTPUT_SHIFT),
        "--fir-taps", str(UPCONVERTER_FIR_TAPS),
    ]
    if sample_format in FORMATS_WIDE:
        command += ["--output-bits", str(sample_format)]
    return command


def convert_rf_block(raw, sample_format, offset_binary):
    """int8 output of the upconverter -> wire format of the DAC. Only the 8-bit-in-16-bit and
    the unsigned 8 bit formats need a conversion; the 10/12/14 bit formats are already
    delivered as int16 by the upconverter."""
    if sample_format == FORMAT_8_IN_16:
        return np.frombuffer(raw, dtype=np.int8).astype("<i2").tobytes()
    if offset_binary and sample_format == FORMAT_8:
        return np.bitwise_xor(np.frombuffer(raw, dtype=np.uint8), 0x80).tobytes()
    return bytes(raw)


def rf_silence(sample_format, offset_binary, samples):
    """Bytes of ``samples`` RF zero samples in the wire format (offset binary: 0x80)."""
    if sample_format == FORMAT_8:
        return (b"\x80" if offset_binary else b"\x00") * samples
    return b"\x00\x00" * samples


def float_iq_to_int16(iq, gain=1.0):
    """Interleaved float32 I/Q (+-1.0 = full scale) -> int16 for the upconverter."""
    scaled = _finite(iq) * np.float32(gain * 32768.0)
    return np.clip(np.rint(scaled), -32768, 32767).astype("<i2")


# ======================================================================================
# real-time pacing (smisdr_iq)
# ======================================================================================
class Pacer:
    """Real-time pacing as in run_IQ_engine / cohi_native_upconverter: the deadline moves
    on by the duration of every block; the sender may run ``lead_s`` ahead of real time, and
    if it falls more than ``max_behind_s`` behind (track change, pause) the time base is set
    anew instead of catching up with a burst.  ``clock`` / ``sleep`` can be replaced in tests."""

    def __init__(self, units_per_second, lead_s=0.100, max_behind_s=0.250,
                 clock=time.monotonic, sleep=time.sleep):
        self.rate = float(units_per_second)
        self.lead_s = lead_s
        self.max_behind_s = max_behind_s
        self._clock = clock
        self._sleep = sleep
        self._deadline = None

    def pace(self, units):
        now = self._clock()
        if self._deadline is None:
            self._deadline = now
        self._deadline += units / self.rate
        if now - self._deadline > self.max_behind_s:
            self._deadline = now                       # do not catch up with a burst
        elif self._deadline - self.lead_s > now:
            self._sleep(self._deadline - self.lead_s - now)


# ======================================================================================
# overload protection
# ======================================================================================
RAW_INPUT_CEILING = 0.24
# cohi_native_upconverter (--output-shift 6) reaches the full scale of the DAC (127 at 8 bit,
# 2^(n-1)-1 at 10/12/14 bit) with an input magnitude |z| of 0.25 of the int16 full scale, measured
# with the tool; 0.24 leaves a little margin. That is why the player uses a gain of 0.4.


MIN_LIMITER_GAIN = 1.0 / 256.0      # -48 dB: below that single samples are held at the ceiling


class PeakLimiter:
    """Slow peak limiter in front of the DAC stage.

    COHIWizard's AVC regulates the gain so that its own volume figure reaches the target; for
    a band signal that is typically 10-14 dB above digital full scale (peaks of 4 x full scale,
    25 % of the samples clipped - measured with a simulated MW band). Hard clipping destroys
    the signal, so a block whose peak would exceed the ceiling is scaled down at once (faded over
    ``ramp_pairs`` I/Q pairs), and the gain recovers by ``release_per_s`` per second.

    magnitude=False: I and Q are limited separately (smisdr_iq: both are 14 bit words);
    magnitude=True : the magnitude |I + jQ| is limited (smisdr_raw: it is the RF amplitude)."""

    def __init__(self, rate_hz, ceiling=1.0, magnitude=False, release_per_s=1.0, ramp_pairs=128):
        self.rate = float(rate_hz)
        self.ceiling = float(ceiling)
        self.magnitude = magnitude
        self.release = release_per_s
        self.ramp = ramp_pairs
        self.gain = 1.0                 # limiter gain at the end of the last block (<= 1)
        self.min_gain = 1.0             # lowest gain since the last reset_stats()

    def reset_stats(self):
        self.min_gain = self.gain

    def _peak(self, x):
        if self.magnitude:
            return float(np.max(np.hypot(x[0::2], x[1::2])))
        return float(np.max(np.abs(x)))

    def process(self, iq, gain=1.0):
        """interleaved float32 I/Q (+-1.0 = full scale) times ``gain`` -> limited float32"""
        count = (len(iq) // 2) * 2
        x = _finite(iq[:count]) * np.float32(gain)
        if count == 0:
            return x
        peak = self._peak(x)
        target = min(1.0, self.gain + (count / 2) / self.rate * self.release)
        if peak * target > self.ceiling:
            target = max(self.ceiling / peak, MIN_LIMITER_GAIN)
        if target != self.gain or self.gain != 1.0:
            gains = np.full(count, target, dtype=np.float32)
            if target != self.gain:
                ramp = min(self.ramp, count // 2)
                gains[:2 * ramp] = np.repeat(np.linspace(self.gain, target, ramp, dtype=np.float32), 2)
            x = x * gains
            self.gain = float(target)
            self.min_gain = min(self.min_gain, self.gain)
        self._clamp(x)                      # only samples in a fade or beyond MIN_LIMITER_GAIN
        return x

    def _clamp(self, x):
        """individual samples above the ceiling (the start of an attack, where the fade is still
        above the final gain) are held at the ceiling, in place; the gain is not touched"""
        if self.magnitude:
            mag = np.hypot(x[0::2], x[1::2])
            over = mag > self.ceiling
            if np.any(over):
                scale = np.where(over, self.ceiling / np.maximum(mag, 1e-30), 1.0).astype(np.float32)
                x[0::2] *= scale
                x[1::2] *= scale
        else:
            np.clip(x, -self.ceiling, self.ceiling, out=x)
