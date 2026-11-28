"""
Tests of the smisdr_iq and smisdr_raw drivers.

Run from the sources directory (the same working directory COHIWizard uses):

    python -m unittest discover -s tests -v

No hardware and no PyQt5 are required (tests/qt_stub.py replaces QtCore if PyQt5 is missing).
The device is a fake smiSDR on localhost (tests/fake_device.py).  The smisdr_raw tests build the
real C++ tool cohi_native_upconverter with g++ and are skipped if there is no compiler.
Optional: COHI_PLAYER_SRC=<COHI-Player-Universal/sources> adds a cross-check of the wire format
against the original, hardware-tested implementation of that project.
"""
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import numpy as np

SOURCES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SOURCES not in sys.path:
    sys.path.insert(0, SOURCES)

from tests import qt_stub, wavgen                       # noqa: E402
from tests.fake_device import FakeSmisdr                # noqa: E402

qt_stub.install()

from core import wavchunks                              # noqa: E402
from dev_drivers.smisdr_common import iqfile, protocol, settings   # noqa: E402

RATE = 250_000


# ======================================================================================
# helpers
# ======================================================================================
class Recorder:
    """collects the signals of a worker / control object"""

    def __init__(self, obj):
        self.errors, self.finished, self.ticks, self.nextfiles, self.messages = [], 0, 0, [], []
        for name in ("SigError", "SigFinished", "SigIncrementCurTime", "SigNextfile", "SigMessage"):
            sig = getattr(obj, name, None)
            if sig is not None:
                sig.connect(getattr(self, "_" + name))

    def _SigError(self, msg):               self.errors.append(msg)
    def _SigFinished(self):                 self.finished += 1
    def _SigIncrementCurTime(self):         self.ticks += 1
    def _SigNextfile(self, name):           self.nextfiles.append(name)
    def _SigMessage(self, msg):             self.messages.append(msg)


class DriverTestCase(unittest.TestCase):
    driver = None           # "smisdr_iq" / "smisdr_raw"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="smisdr_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.device = FakeSmisdr()
        self.addCleanup(self.device.close)
        self.cfg_extra = {}
        self.old_config = settings.CONFIG_FILE
        self.addCleanup(setattr, settings, "CONFIG_FILE", self.old_config)
        settings._cache.clear()

    def write_config(self, **extra):
        """config_wizard.yaml in the temp dir, pointing at the fake device"""
        import yaml
        cfg = {"smisdr_data_port": self.device.data_port,
               "smisdr_control_port": self.device.control_port}
        cfg.update(self.cfg_extra)
        cfg.update(extra)
        path = os.path.join(self.tmp, "config_wizard.yaml")
        with open(path, "w") as fh:
            yaml.safe_dump(cfg, fh)
        settings.CONFIG_FILE = path
        settings._cache.clear()

    def modules(self):
        ctrl_mod = importlib.import_module("dev_drivers.{}.SDR_control".format(self.driver))
        work_mod = importlib.import_module("dev_drivers.{}.cohi_playrecworker".format(self.driver))
        return ctrl_mod.SDR_control, work_mod.playrec_worker

    def wav(self, name, frames, rate=RATE, center=1_000_000, offset_hz=5_000, bits=16,
            float_format=False, amplitude=0.5):
        return wavgen.make_wav(os.path.join(self.tmp, name),
                               wavgen.tone(frames, rate, offset_hz, amplitude),
                               rate, center, bits, float_format)

    def start(self, files, rate=RATE, center=1_000_000, icorr=0, gain=1.0, test=False,
              timescaler=None, check_config=True):
        """control + worker for ``files``; -> (worker, recorder, ctrl_recorder)"""
        Control, Worker = self.modules()
        ctrl = Control()
        crec = Recorder(ctrl)
        params = {"HostAddress": "127.0.0.1", "ifreq": center, "irate": rate, "icorr": icorr,
                  "LO_offset": 0, "rates": ctrl.identify()["rates"]}
        if check_config:
            self.assertTrue(ctrl.config_socket(params), crec.errors)
        worker = Worker(ctrl)
        wrec = Recorder(worker)
        worker.set_configparameters(params)
        worker.set_filename(list(files))
        worker.set_timescaler(timescaler or rate * 4)
        worker.set_TEST(test)
        worker.set_gain(gain)
        worker.set_pause(False)
        return worker, wrec, crec

    def run_worker(self, worker):
        started = time.monotonic()
        worker.play_loop_filelist()
        return time.monotonic() - started

    def run_in_thread(self, worker):
        thread = threading.Thread(target=worker.play_loop_filelist, daemon=True)
        thread.start()
        self.addCleanup(lambda: (worker.stop_loop(), thread.join(5)))
        return thread

    def wait_for(self, condition, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if condition():
                return True
            time.sleep(0.01)
        return False


# ======================================================================================
# protocol (pure functions)
# ======================================================================================
class ProtocolTest(unittest.TestCase):

    def test_ftw_and_commands(self):
        self.assertEqual(protocol.calculate_ftw(0), 0)
        self.assertEqual(protocol.calculate_ftw(25_000_000), 1 << 31)
        self.assertEqual(protocol.calculate_ftw(1_000_000), 85899346)        # 1e6/50e6 * 2^32
        words = protocol.build_command(protocol.CMD_SHIFT, 0x01020304)
        self.assertEqual(words, [0x8000 | (63 << 8) | ord("S"), 0x8000 | 0x04,
                                 0x8000 | (1 << 8) | 0x03, 0x8000 | (2 << 8) | 0x02,
                                 0x8000 | (3 << 8) | 0x01, 0xC000 | ord("E")])
        init = np.frombuffer(protocol.build_init_sequence(1_000_000, 500_000), dtype="<u2")
        self.assertEqual(len(init), 12)
        self.assertEqual(int(init[0]) & 0xFF, ord("S"))
        self.assertEqual(int(init[6]) & 0xFF, ord("R"))

    def test_ftw_out_of_range(self):
        with self.assertRaises(ValueError):
            protocol.calculate_ftw(-1)
        with self.assertRaises(ValueError):
            protocol.calculate_ftw(1e12)

    def test_iq_encoding_tags_and_roundtrip(self):
        iq = np.array([0.5, -0.5, 1.0, -1.0, 0.0, 0.25], dtype=np.float32)
        words = np.frombuffer(protocol.encode_iq_words(iq), dtype="<u2")
        self.assertEqual([int(w) >> 14 for w in words], [0, 1, 0, 1, 0, 1])    # I Q I Q ...
        back = protocol.decode_iq_words(words.tobytes())
        np.testing.assert_allclose(back.real, [0.5, 1.0 - 1 / 8192, 0.0], atol=1 / 8192)
        np.testing.assert_allclose(back.imag, [-0.5, -1.0, 0.25], atol=1 / 8192)

    def test_iq_encoding_clips_and_drops_odd_sample(self):
        words = protocol.encode_iq_words(np.array([5.0, -5.0, 0.1], dtype=np.float32), 1.0)
        self.assertEqual(len(words), 4)                       # one pair; the odd sample is dropped
        back = protocol.decode_iq_words(words)
        self.assertAlmostEqual(back.real[0], 8191 / 8192, places=6)
        self.assertAlmostEqual(back.imag[0], -1.0, places=6)

    def test_iq_encoding_nan_is_zero(self):
        words = protocol.encode_iq_words(np.array([np.nan, np.inf], dtype=np.float32))
        self.assertEqual(len(words), 4)

    def test_silence(self):
        s = np.frombuffer(protocol.silence_words(4), dtype="<u2")
        self.assertEqual(list(s), [0x0000, 0x4000] * 4)

    def test_rates_and_edges(self):
        self.assertEqual(protocol.supported_iq_rate(1_250_000), 1_250_000)
        self.assertEqual(protocol.supported_iq_rate(500_100), 500_000)         # within 0.1 %
        self.assertIsNone(protocol.supported_iq_rate(300_000))
        self.assertIsNone(protocol.iq_edge_problem(1e6, 250e3, 50e6))
        self.assertIsNotNone(protocol.iq_edge_problem(24.0e6, 1.25e6, 50e6))
        self.assertEqual(protocol.format_iq_bus_rate_command(250_000), "rate 0.5\n")
        self.assertEqual(protocol.format_iq_bus_rate_command(1_250_000), "rate 2.5\n")

    def test_parse_control_port(self):
        self.assertEqual(protocol.parse_control_port(None), 5000)
        self.assertEqual(protocol.parse_control_port(6000), 6000)
        for off in (0, "0", "off", "OFF", False, "none", ""):
            self.assertIsNone(protocol.parse_control_port(off), off)
        with self.assertRaises(ValueError):
            protocol.parse_control_port(70000)

    def test_parse_rate_setting(self):
        self.assertEqual(protocol.parse_rate_setting("auto"), "auto")
        self.assertEqual(protocol.parse_rate_setting(5), 5_000_000)
        self.assertEqual(protocol.parse_rate_setting("12,5"), 12_500_000)
        self.assertEqual(protocol.parse_rate_setting("10 MSps"), 10_000_000)
        self.assertEqual(protocol.parse_rate_setting(12_500_000), 12_500_000)
        self.assertIsNone(protocol.parse_rate_setting(7))
        self.assertIsNone(protocol.parse_rate_setting(True))

    def test_choose_target_rate(self):
        c = protocol.choose_target_rate
        self.assertEqual(c(250e3, 1e6, "auto", True), 5_000_000)
        self.assertEqual(c(1.25e6, 5e6, "auto", True), 12_500_000)
        self.assertIsNone(c(250e3, 1e6, "auto", False))                  # auto needs the control port
        self.assertEqual(c(250e3, 1e6, 12_500_000, False), 12_500_000)
        self.assertIsNone(c(250e3, 5e6, 5_000_000, True))                # above 95 % of Nyquist
        self.assertIsNone(c(8e6, 1e6, 5_000_000, True))                  # input faster than output

    def test_rf_block_conversion(self):
        raw = bytes([0, 1, 255, 128])                                     # int8: 0, 1, -1, -128
        self.assertEqual(protocol.convert_rf_block(raw, protocol.FORMAT_8, False), raw)
        self.assertEqual(protocol.convert_rf_block(raw, protocol.FORMAT_8, True),
                         bytes([128, 129, 127, 0]))
        wide = np.frombuffer(protocol.convert_rf_block(raw, protocol.FORMAT_8_IN_16, False), dtype="<i2")
        self.assertEqual(list(wide), [0, 1, -1, -128])
        self.assertEqual(protocol.rf_silence(protocol.FORMAT_8, True, 3), b"\x80\x80\x80")
        self.assertEqual(protocol.rf_silence(12, False, 2), b"\x00" * 4)

    def test_upconverter_command(self):
        cmd = protocol.build_upconverter_command("/x/up", 250000, 999999.6, 5_000_000, 12)
        self.assertEqual(cmd[:7], ["/x/up", "--sample-rate", "250000", "--center-freq", "1000000",
                                   "--target-rate", "5000000"])
        self.assertEqual(cmd[-2:], ["--output-bits", "12"])
        self.assertNotIn("--output-bits", protocol.build_upconverter_command("/x/up", 1, 1, 1, 8))

    def test_float_to_int16(self):
        out = protocol.float_iq_to_int16(np.array([0.5, -2.0, 1.0], dtype=np.float32), 1.0)
        self.assertEqual(list(out), [16384, -32768, 32767])
        self.assertEqual(list(protocol.float_iq_to_int16(np.array([0.5], dtype=np.float32), 0.5)), [8192])

    def test_pacer(self):
        now = [0.0]
        slept = []
        p = protocol.Pacer(1000, lead_s=0.1, max_behind_s=0.25,
                           clock=lambda: now[0], sleep=lambda s: slept.append(s))
        p.pace(50)                          # 50 ms ahead: within the lead, no sleep
        self.assertEqual(slept, [])
        p.pace(150)                         # deadline 0.2 s, lead 0.1 -> sleep 0.1
        self.assertAlmostEqual(slept[-1], 0.1)
        now[0] = 5.0                        # far behind (pause): clock is reset, no burst catch-up
        p.pace(10)
        self.assertEqual(len(slept), 1)
        p.pace(300)
        self.assertGreater(len(slept), 1)


# ======================================================================================
# settings
# ======================================================================================
class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        s = settings.parse_settings({})
        self.assertEqual((s["data_port"], s["control_port"], s["ref_clock"]), (1234, 5000, 50e6))
        self.assertEqual((s["sample_rate"], s["format"], s["offset"]), ("auto", 8, False))

    def test_values(self):
        s = settings.parse_settings({"smisdr_data_port": 4321, "smisdr_control_port": "off",
                                     "smisdr_sample_rate": 12.5, "smisdr_format": 12,
                                     "smisdr_offset": True, "smisdr_iq_ref_clock": 100e6})
        self.assertEqual(s["data_port"], 4321)
        self.assertIsNone(s["control_port"])
        self.assertEqual(s["sample_rate"], 12_500_000)
        self.assertFalse(s["offset"])                      # offset binary only exists for 8 bit
        self.assertEqual(s["ref_clock"], 100e6)

    def test_invalid_values_name_the_key(self):
        for key, value in (("smisdr_data_port", 0), ("smisdr_control_port", 99999),
                           ("smisdr_sample_rate", 7), ("smisdr_format", 9),
                           ("smisdr_iq_ref_clock", -1)):
            with self.assertRaises(settings.SettingsError) as ctx:
                settings.parse_settings({key: value})
            self.assertIn(key, str(ctx.exception))

    def test_auto_rate_needs_control_port_only_for_raw(self):
        cfg = settings.parse_settings({"smisdr_control_port": 0})        # fine for smisdr_iq ...
        self.assertIn("auto", settings.raw_problem(cfg))                 # ... not for smisdr_raw
        cfg = settings.parse_settings({"smisdr_control_port": 0, "smisdr_sample_rate": 5})
        self.assertIsNone(settings.raw_problem(cfg))

    def test_missing_file_gives_defaults_and_cache_follows_changes(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "c.yaml")
            self.assertEqual(settings.load_settings(path)["data_port"], 1234)
            with open(path, "w") as fh:
                fh.write("smisdr_data_port: 2222\n")
            self.assertEqual(settings.load_settings(path)["data_port"], 2222)
            time.sleep(0.01)
            with open(path, "w") as fh:
                fh.write("smisdr_data_port: 3333\n")
            os.utime(path, (time.time() + 5, time.time() + 5))
            self.assertEqual(settings.load_settings(path)["data_port"], 3333)
        finally:
            shutil.rmtree(tmp, True)

    def test_broken_yaml(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "c.yaml")
            with open(path, "w") as fh:
                fh.write("smisdr_data_port: [unclosed\n")
            with self.assertRaises(settings.SettingsError):
                settings.load_settings(path)
        finally:
            shutil.rmtree(tmp, True)


# ======================================================================================
# file reading
# ======================================================================================
class IqFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make(self, bits, float_format=False, frames=3000):
        iq = wavgen.tone(frames, 250000, 7000, 0.6)
        path = wavgen.make_wav(os.path.join(self.tmp, "a.wav"), iq, 250000, 1_234_567, bits, float_format)
        return path, iq

    def test_header_info(self):
        path, _ = self.make(16)
        info = iqfile.read_info(path)
        self.assertEqual((info.sample_rate, info.fmt_tag, info.bits, info.channels),
                         (250000, 1, 16, 2))
        self.assertEqual(info.center_freq, 1_234_567)
        self.assertEqual(info.data_offset, 216)

    def test_reader_all_formats_give_same_normalized_samples(self):
        for bits, flt in ((16, False), (24, False), (32, False), (32, True)):
            path, iq = self.make(bits, flt)
            info = iqfile.read_info(path)
            with open(path, "rb") as fh:
                fh.seek(info.data_offset)
                reader = iqfile.IqBlockReader(fh, info.fmt_tag, info.bits, 1000, info.data_offset)
                out, native, total = [], [], 0
                while True:
                    block = reader.read()
                    if block is None:
                        break
                    monitor, norm, nbytes = block
                    out.append(norm)
                    native.append(monitor)
                    total += nbytes
            norm = np.concatenate(out)
            self.assertEqual(total, 3000 * 2 * bits // 8, (bits, flt))
            np.testing.assert_allclose(norm[0::2], iq.real, atol=2e-4, err_msg=str((bits, flt)))
            np.testing.assert_allclose(norm[1::2], iq.imag, atol=2e-4, err_msg=str((bits, flt)))
            peak = float(np.max(np.abs(np.concatenate(native))))
            expect = 0.6 if flt else 0.6 * (2 ** (bits - 1) - 1)
            self.assertAlmostEqual(peak / expect, 1.0, places=2, msg=str((bits, flt)))

    def test_reader_realigns_after_odd_seek_and_drops_partial_frame(self):
        path, iq = self.make(16)
        info = iqfile.read_info(path)
        with open(path, "rb") as fh:
            fh.seek(info.data_offset + 4 * 100 + 1)          # GUI jump to a misaligned byte
            reader = iqfile.IqBlockReader(fh, 1, 16, 50, info.data_offset)
            _, norm, _ = reader.read()
            self.assertAlmostEqual(norm[0], iq.real[101], places=3)           # next whole frame
            self.assertEqual(len(norm), 100)
        with open(path, "rb") as fh:                          # truncated file: partial frame dropped
            fh.seek(0, 2)
            size = fh.tell()
        with open(path, "r+b") as fh:
            fh.truncate(size - 3)
        with open(path, "rb") as fh:
            fh.seek(info.data_offset)
            reader = iqfile.IqBlockReader(fh, 1, 16, 10000, info.data_offset)
            _, norm, nbytes = reader.read()
            self.assertEqual(nbytes % 4, 0)
            self.assertEqual(len(norm), 2 * 2999)

    def test_check_format(self):
        self.assertIsNone(iqfile.check_format(1, 16))
        self.assertIsNone(iqfile.check_format(3, 32))
        self.assertIsNotNone(iqfile.check_format(1, 8))
        self.assertIsNotNone(iqfile.check_format(3, 64))
        self.assertIsNotNone(iqfile.check_format(2, 16))
        self.assertIsNotNone(iqfile.check_format(1, 16, channels=1))

    def test_no_riff_raw_file(self):
        path = os.path.join(self.tmp, "x.dat")
        with open(path, "wb") as fh:
            fh.write(b"\x00" * 216 + b"\x01\x00\x02\x00")
        info = iqfile.read_info(path)
        self.assertEqual(info.data_offset, 216)
        self.assertIsNone(info.sample_rate)
        self.assertIsNone(info.center_freq)

    def test_not_a_wav(self):
        path = os.path.join(self.tmp, "x.wav")
        with open(path, "wb") as fh:
            fh.write(b"hello world, this is no wav file at all")
        with self.assertRaises(wavchunks.WavChunkError):
            iqfile.read_info(path)


# ======================================================================================
# smisdr_iq: complete worker against the fake device
# ======================================================================================
class SmisdrIqTest(DriverTestCase):
    driver = "smisdr_iq"

    def setUp(self):
        super().setUp()
        self.write_config()

    def words_after_init(self, index=0, init_len=24):
        return self.device.data(index)[init_len:]

    def test_stream_content_commands_and_pacing(self):
        path = self.wav("a.wav", 100_000)                      # 0.4 s
        worker, rec, _ = self.start([path], timescaler=100_000)
        elapsed = self.run_worker(worker)
        time.sleep(0.2)
        self.assertEqual(rec.errors, [])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(len(rec.nextfiles), 1)
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])
        self.assertEqual(len(self.device.connections), 1)

        data = self.device.data()
        self.assertEqual(data[:24], protocol.build_init_sequence(1_000_000, RATE))
        body = self.words_after_init()
        # 100000 frames * 4 bytes + 256 frames of closing silence
        self.assertEqual(len(body), 100_000 * 4 + 256 * 4)
        decoded = protocol.decode_iq_words(body[:100_000 * 4])
        expected = wavgen.tone(100_000, RATE, 5_000, 0.5) * (32767 / 32768)
        np.testing.assert_allclose(decoded, expected, atol=3 / 8192)
        tail = np.frombuffer(body[-1024:], dtype="<u2")
        self.assertEqual(list(tail[:4]), [0x0000, 0x4000, 0x0000, 0x4000])    # DAC left at zero

        self.assertGreater(elapsed, 0.4 - 0.15)                 # paced to real time (lead 100 ms)
        self.assertLess(elapsed, 1.5)
        self.assertEqual(rec.ticks, 4)                          # 400000 bytes / 100000 per tick
        self.assertTrue(worker.get_fileclose())
        monitor = worker.get_data()
        self.assertGreater(len(monitor), 256)
        self.assertLessEqual(float(np.max(np.abs(monitor))), 32767.5)          # native 16 bit scale

    def test_gain(self):
        path = self.wav("a.wav", 25_000)
        worker, rec, _ = self.start([path], gain=0.5)
        self.run_worker(worker)
        time.sleep(0.2)
        decoded = protocol.decode_iq_words(self.words_after_init()[:25_000 * 4])
        self.assertAlmostEqual(float(np.max(np.abs(decoded.real))), 0.25, delta=0.002)

    def test_gain_changes_while_playing(self):
        path = self.wav("a.wav", 100_000)
        worker, rec, _ = self.start([path], gain=1.0)
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 80_000))
        worker.set_gain(0.1)
        thread.join(5)
        time.sleep(0.2)
        decoded = protocol.decode_iq_words(self.words_after_init()[:100_000 * 4])
        self.assertAlmostEqual(float(np.max(np.abs(decoded[:5000].real))), 0.5, delta=0.01)
        self.assertAlmostEqual(float(np.max(np.abs(decoded[-5000:].real))), 0.05, delta=0.01)

    def test_other_sample_formats_play_the_same(self):
        reference = None
        for n, (bits, flt) in enumerate(((16, False), (24, False), (32, False), (32, True))):
            self.device.connections.clear()
            path = self.wav("f{}.wav".format(n), 12_500, bits=bits, float_format=flt)
            worker, rec, _ = self.start([path])
            self.run_worker(worker)
            time.sleep(0.15)
            self.assertEqual(rec.errors, [], (bits, flt))
            decoded = protocol.decode_iq_words(self.words_after_init()[:12_500 * 4])
            if reference is None:
                reference = decoded
            np.testing.assert_allclose(decoded, reference, atol=3 / 8192, err_msg=str((bits, flt)))

    def test_ppm_correction_moves_the_nco(self):
        path = self.wav("a.wav", 2_000)
        worker, rec, _ = self.start([path], icorr=10)           # +10 ppm of 1 MHz = 1000010 Hz
        self.run_worker(worker)
        time.sleep(0.15)
        self.assertEqual(self.device.data()[:24], protocol.build_init_sequence(1_000_010, RATE))

    def test_nextfile_chain_same_parameters_is_gapless(self):
        a = self.wav("a.wav", 10_000)
        b = self.wav("b.wav", 10_000)
        worker, rec, _ = self.start([a, b])
        self.run_worker(worker)
        time.sleep(0.15)
        self.assertEqual(len(rec.nextfiles), 2)
        self.assertEqual(len(self.device.connections), 1)                    # one connection
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])  # configured once
        self.assertEqual(len(self.words_after_init()), 20_000 * 4 + 256 * 4)

    def test_nextfile_chain_new_parameters_reconfigure_from_the_header(self):
        a = self.wav("a.wav", 10_000, rate=250_000, center=1_000_000)
        b = self.wav("b.wav", 20_000, rate=500_000, center=1_100_000)
        worker, rec, _ = self.start([a, b])
        self.run_worker(worker)
        time.sleep(0.2)
        self.assertEqual(rec.errors, [])
        self.assertEqual(len(self.device.connections), 2)
        self.assertEqual(self.device.commands,
                         ["width 16\n", "rate 0.5\n", "width 16\n", "rate 1.0\n"])
        self.assertEqual(self.device.data(1)[:24], protocol.build_init_sequence(1_100_000, 500_000))
        self.assertEqual(len(self.words_after_init(1)), 20_000 * 4 + 256 * 4)
        # the first connection ended with the closing silence before it was dropped
        self.assertEqual(len(self.device.data(0)), 24 + 10_000 * 4 + 256 * 4)

    def test_no_control_port_sends_no_commands(self):
        self.write_config(smisdr_control_port=0)
        path = self.wav("a.wav", 5_000)
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        time.sleep(0.15)
        self.assertEqual(rec.errors, [])
        self.assertEqual(self.device.commands, [])
        self.assertEqual(self.device.data()[:24], protocol.build_init_sequence(1_000_000, RATE))

    def test_unsupported_sample_rate(self):
        path = self.wav("a.wav", 3_000, rate=300_000)
        worker, rec, _ = self.start([path], rate=300_000)
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("250000, 500000 and 1250000", rec.errors[0])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(self.device.connections, [])

    def test_signal_above_the_dac_range(self):
        path = self.wav("a.wav", 3_000, center=24_900_000)
        worker, rec, _ = self.start([path], center=24_900_000)
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("above the usable range", rec.errors[0])
        self.assertEqual(rec.finished, 1)

    def test_device_not_reachable(self):
        path = self.wav("a.wav", 3_000)
        self.write_config(smisdr_data_port=1)                  # nothing listens there
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("not reachable", rec.errors[0])
        self.assertEqual(rec.finished, 1)

    def test_control_port_not_accepting(self):
        path = self.wav("a.wav", 3_000)
        self.write_config(smisdr_control_port=1)
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("control port", rec.errors[0])
        self.assertEqual(self.device.connections, [])

    def test_bad_file_does_not_stop_the_chain(self):
        bad = os.path.join(self.tmp, "bad.wav")
        with open(bad, "wb") as fh:
            fh.write(b"not a wav file")
        good = self.wav("a.wav", 5_000)
        worker, rec, _ = self.start([bad, good])
        self.run_worker(worker)
        time.sleep(0.15)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("bad.wav", rec.errors[0])
        self.assertEqual(len(rec.nextfiles), 1)                # the good file was played
        self.assertEqual(len(self.words_after_init()), 5_000 * 4 + 256 * 4)

    def test_mono_and_8bit_files_are_refused(self):
        path = self.wav("a.wav", 3_000)
        with open(path, "r+b") as fh:                         # patch nChannels to 1
            fh.seek(12 + 8 + 2)
            fh.write((1).to_bytes(2, "little"))
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("channel", rec.errors[0])

    def test_pause_sends_silence_and_stop_ends_cleanly(self):
        path = self.wav("a.wav", 4 * RATE)                    # 4 s
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 200_000))
        worker.set_pause(True)
        time.sleep(0.6)
        size_paused = len(self.device.data())
        time.sleep(0.4)
        grown = self.device.data()[size_paused:]
        self.assertGreater(len(grown), 100_000)                # the stream goes on ...
        words = np.frombuffer(grown[:len(grown) // 4 * 4], dtype="<u2")
        self.assertEqual(set(words[::2].tolist()), {0x0000})   # ... with I = 0
        self.assertEqual(set(words[1::2].tolist()), {0x4000})  # ... and Q = 0
        ticks = rec.ticks
        time.sleep(0.3)
        self.assertEqual(rec.ticks, ticks)                     # the clock stands still
        worker.set_pause(False)
        time.sleep(0.2)
        stop_at = time.monotonic()
        worker.stop_loop()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - stop_at, 1.5)
        self.assertEqual(rec.errors, [])                       # stopping is not an error
        self.assertEqual(rec.finished, 1)

    def test_stop_while_the_socket_is_closed_from_the_gui_thread_is_not_an_error(self):
        path = self.wav("a.wav", 4 * RATE)
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1))
        worker.stop_loop()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(rec.errors, [])

    def test_device_resets_the_connection(self):
        path = self.wav("a.wav", 4 * RATE)
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 50_000))
        self.device.drop_connections()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(rec.errors), 1, rec.errors)
        self.assertIn("connection to the device lost", rec.errors[0])
        self.assertEqual(rec.finished, 1)

    def test_test_mode_makes_no_connection_but_runs_in_real_time(self):
        path = self.wav("a.wav", 50_000)                       # 0.2 s
        worker, rec, _ = self.start([path], test=True, timescaler=100_000)
        elapsed = self.run_worker(worker)
        self.assertEqual(self.device.connections, [])
        self.assertEqual(self.device.commands, [])
        self.assertEqual(rec.errors, [])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(rec.ticks, 2)
        self.assertGreater(elapsed, 0.2 - 0.15)

    def test_identify_matches_the_player_checks(self):
        Control, _ = self.modules()
        dev = Control().identify()
        self.assertEqual(dev["device_name"], "smisdr_iq")
        self.assertEqual(dev["connection_type"], "ethernet")
        self.assertFalse(dev["server_boot"])
        self.assertTrue(dev["TX"] and not dev["RX"])
        self.assertEqual(sorted(dev["rates"]), [250000, 500000, 1250000])
        self.assertEqual(dev["rate_type"], "discrete")
        self.assertEqual(dev["max_IFREQ"], 23_750_000)
        for key in ("rates", "rate_type", "RX", "TX", "device_name", "max_IFREQ", "min_IFREQ",
                    "resolutions", "connection_type", "volume_mode"):
            self.assertIn(key, dev)

    def test_max_ifreq_follows_the_ref_clock(self):
        self.write_config(smisdr_iq_ref_clock=100_000_000)
        Control, _ = self.modules()
        self.assertEqual(Control().identify()["max_IFREQ"], 47_500_000)

    def test_adapter_legacy_interface(self):
        Control, _ = self.modules()
        ctrl = Control()
        rec = Recorder(ctrl)
        self.assertEqual(ctrl.set_play(), (False, ""))
        self.assertTrue(ctrl.set_rec()[0])                     # recording: error
        self.assertEqual(ctrl.sdrserverstart({}), (False, ["", None]))
        self.assertEqual(ctrl.RPShutdown({"HostAddress": "x"}), (False, ""))
        self.assertEqual(ctrl.RPShutdown(["watchdog_start", None]), (False, ""))
        self.assertFalse(ctrl.config_socket({"HostAddress": ""}))        # no IP given
        self.assertIn("IP address", rec.errors[-1])
        self.assertTrue(ctrl.config_socket({"HostAddress": "127.0.0.1"}))
        self.assertTrue(ctrl.is_ready())
        ctrl.teardown()
        self.assertFalse(ctrl.is_ready())
        self.assertEqual(self.device.connections, [])          # config_socket never connects

    def test_invalid_settings_are_reported_by_config_socket(self):
        self.write_config(smisdr_format=9)
        Control, _ = self.modules()
        ctrl = Control()
        rec = Recorder(ctrl)
        self.assertFalse(ctrl.config_socket({"HostAddress": "127.0.0.1"}))
        self.assertIn("smisdr_format", rec.errors[0])


# ======================================================================================
# smisdr_raw: with the real C++ upconverter
# ======================================================================================
def build_upconverter(directory):
    src = os.path.join(SOURCES, "dev_drivers", "smisdr_common", "upconverter", "cohi_native_upconverter.cpp")
    exe = os.path.join(directory, "cohi_native_upconverter")
    compiler = shutil.which("g++") or shutil.which("c++")
    if compiler is None:
        return None
    result = subprocess.run([compiler, "-O2", "-o", exe, src, "-lm", "-lpthread"],
                            capture_output=True, text=True)
    return exe if result.returncode == 0 else None


def upconverter_processes(exe):
    """PIDs of running upconverter processes (Linux /proc)"""
    pids = []
    if not os.path.isdir("/proc"):
        return pids
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open("/proc/{}/cmdline".format(entry), "rb") as fh:
                    if exe.encode() in fh.read():
                        pids.append(int(entry))
            except OSError:
                pass
    return pids


def spectrum_peak(samples, rate):
    n = 1 << 17
    seg = samples[len(samples) // 2: len(samples) // 2 + n].astype(np.float64)
    seg = (seg - seg.mean()) * np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg))
    return float(np.argmax(spec)) * rate / len(seg)


class SmisdrRawTest(DriverTestCase):
    driver = "smisdr_raw"
    exe = None
    exe_dir = None

    @classmethod
    def setUpClass(cls):
        cls.exe_dir = tempfile.mkdtemp(prefix="smisdr_up_")
        cls.exe = build_upconverter(cls.exe_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.exe_dir, True)

    def setUp(self):
        if self.exe is None:
            self.skipTest("no C++ compiler: cohi_native_upconverter cannot be built")
        super().setUp()
        self.cfg_extra = {"smisdr_upconverter_path": self.exe, "smisdr_sample_rate": 5}
        self.write_config()

    def rf(self, index=0, dtype="int8"):
        return np.frombuffer(self.device.data(index), dtype=dtype)

    def test_rf_stream_8bit(self):
        path = self.wav("a.wav", 100_000, offset_hz=10_000)               # 0.4 s
        worker, rec, _ = self.start([path], timescaler=100_000)
        elapsed = self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(rec.finished, 1)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"])
        rf = self.rf()
        expected = int(0.4 * 5_000_000)
        self.assertAlmostEqual(len(rf) / expected, 1.0, delta=0.03)        # 5 MSps, 8 bit
        self.assertAlmostEqual(spectrum_peak(rf, 5_000_000), 1_010_000, delta=300)
        self.assertGreater(int(np.max(np.abs(rf[:2_000_000]))), 10)
        self.assertGreater(elapsed, 0.25)                                  # paced by the C++ tool
        self.assertEqual(rec.ticks, 4)
        self.assertEqual(upconverter_processes(self.exe), [])              # no process left behind

    def test_formats(self):
        cases = {
            "12": dict(smisdr_format=12, width="width 16\n"),
            "14": dict(smisdr_format=14, width="width 16\n"),
            "816": dict(smisdr_format=816, width="width 16\n"),
            "offset": dict(smisdr_format=8, smisdr_offset=True, width="width 8\n"),
        }
        for name, spec in cases.items():
            with self.subTest(name):
                self.device.commands.clear()
                self.device.connections.clear()
                width = spec.pop("width")
                self.write_config(**spec)
                path = self.wav("f{}.wav".format(name), 25_000, offset_hz=10_000, amplitude=0.4)
                worker, rec, _ = self.start([path])
                self.run_worker(worker)
                time.sleep(0.3)
                self.assertEqual(rec.errors, [], rec.errors)
                self.assertEqual(self.device.commands, [width, "rate 5.0\n"])
                if name in ("12", "14"):
                    rf = self.rf(dtype="<i2")
                    bits = int(name)
                    peak = int(np.max(np.abs(rf)))
                    self.assertLessEqual(peak, 2 ** (bits - 1))
                    self.assertGreater(peak, 2 ** (bits - 1) // 8)
                    self.assertAlmostEqual(spectrum_peak(rf[: len(rf)], 5_000_000)
                                           if len(rf) > 2 ** 18 else 1_010_000, 1_010_000, delta=800)
                elif name == "816":
                    rf = self.rf(dtype="<i2")
                    self.assertLessEqual(int(np.max(np.abs(rf))), 128)
                    self.assertAlmostEqual(len(rf) / 500_000, 1.0, delta=0.05)   # 0.1 s at 5 MSps, int16
                else:
                    rf = self.rf(dtype=np.uint8)
                    self.assertAlmostEqual(float(np.mean(rf[: 500_000])), 128.0, delta=2.0)
                    self.assertGreater(int(np.max(rf)), 128 + 5)
                self.write_config()

    def test_auto_rate_picks_the_lowest_fitting_rate(self):
        self.write_config(smisdr_sample_rate="auto")
        path = self.wav("a.wav", 62_500, rate=1_250_000, center=5_000_000, offset_hz=20_000)   # 50 ms
        worker, rec, _ = self.start([path], rate=1_250_000, center=5_000_000)
        self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 12.5\n"])

    def test_signal_does_not_fit_the_output_rate(self):
        path = self.wav("a.wav", 5_000, center=4_000_000)
        worker, rec, _ = self.start([path], center=4_000_000)               # 5 MSps: limit 2.375 MHz
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("does not fit", rec.errors[0])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(self.device.connections, [])

    def test_chain_is_kept_for_same_parameters_and_rebuilt_otherwise(self):
        a = self.wav("a.wav", 12_500, center=1_000_000)
        b = self.wav("b.wav", 12_500, center=1_000_000)
        c = self.wav("c.wav", 12_500, center=1_200_000)
        worker, rec, _ = self.start([a, b, c])
        self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(len(self.device.connections), 2)                  # a+b together, then c
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"] * 2)
        first, second = self.rf(0), self.rf(1)
        self.assertAlmostEqual(len(first) / (2 * 12_500 * 20), 1.0, delta=0.05)
        self.assertAlmostEqual(len(second) / (12_500 * 20), 1.0, delta=0.08)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_stop_kills_the_chain_without_error(self):
        path = self.wav("a.wav", 4 * RATE)
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 300_000))
        self.assertEqual(len(upconverter_processes(self.exe)), 1)
        t0 = time.monotonic()
        worker.stop_loop()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - t0, 2.5)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(rec.finished, 1)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_pause_feeds_silence(self):
        path = self.wav("a.wav", 4 * RATE, amplitude=0.8)
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.data()) > 500_000 if self.device.connections else False))
        worker.set_pause(True)
        time.sleep(0.8)                                       # let the old data drain
        size = len(self.device.data())
        time.sleep(0.5)
        tail = np.frombuffer(self.device.data()[size:], dtype=np.int8)
        self.assertGreater(len(tail), 500_000)
        self.assertLessEqual(int(np.max(np.abs(tail))), 1)    # silence at the DAC
        worker.stop_loop()
        thread.join(5)
        self.assertEqual(rec.errors, [], rec.errors)

    def test_device_resets_the_connection(self):
        path = self.wav("a.wav", 4 * RATE)
        worker, rec, _ = self.start([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 300_000))
        self.device.drop_connections()
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(rec.errors), 1, rec.errors)
        self.assertEqual(rec.finished, 1)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_device_not_reachable(self):
        self.write_config(smisdr_data_port=1)
        path = self.wav("a.wav", 3_000)
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("not reachable", rec.errors[0])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_upconverter_dying_is_reported_once(self):
        bad = os.path.join(self.tmp, "fake_upconverter")
        with open(bad, "w") as fh:
            fh.write("#!/bin/sh\necho 'boom: something is wrong' >&2\nexit 3\n")
        os.chmod(bad, 0o755)
        self.write_config(smisdr_upconverter_path=bad)
        path = self.wav("a.wav", 4 * RATE)
        worker, rec, _ = self.start([path])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1, rec.errors)
        self.assertEqual(rec.finished, 1)

    def test_missing_upconverter_is_reported_before_play(self):
        self.write_config(smisdr_upconverter_path="/nonexistent/cohi_native_upconverter")
        Control, _ = self.modules()
        ctrl = Control()
        rec = Recorder(ctrl)
        self.assertFalse(ctrl.config_socket({"HostAddress": "127.0.0.1"}))
        self.assertIn("not found", rec.errors[0])
        self.assertIn("make", rec.errors[0])

    def test_identify(self):
        Control, _ = self.modules()
        dev = Control().identify()
        self.assertEqual(dev["device_name"], "smisdr_raw")
        self.assertEqual(dev["rate_type"], "continuous")
        keys = list(dev["rates"])
        self.assertLess(keys[0], 8_000)
        self.assertGreater(keys[1], 5_000_000)
        self.assertEqual(dev["max_IFREQ"], int(0.95 * 5_000_000 / 2))      # follows smisdr_sample_rate
        self.assertFalse(dev["server_boot"])
        self.assertEqual(dev["connection_type"], "ethernet")


# ======================================================================================
# integration into COHIWizard (driver discovery, playrec patch)
# ======================================================================================
class IntegrationTest(unittest.TestCase):

    def test_driver_discovery_rule_of_playrec(self):
        drvdir = os.path.join(SOURCES, "dev_drivers")
        devices = [cf for cf in os.listdir(drvdir) if not cf.startswith(".")
                   and os.path.isfile(os.path.join(drvdir, cf, "cohi_playrecworker.py"))]
        self.assertIn("smisdr_iq", devices)
        self.assertIn("smisdr_raw", devices)
        self.assertNotIn("smisdr_common", devices)           # shared code is not a driver

    def test_drivers_appear_in_band_only_mode_only(self):
        """the list filter of playrec for the three modulator types"""
        for cf in ("smisdr_iq", "smisdr_raw"):
            band_only = not (cf.endswith("_modulator") or cf.endswith("_plus") or cf.find("__") == 0)
            band_and_audio = (cf.endswith("_plus") or cf.endswith("_universal")) and cf.find("__") != 0
            audio_only = (cf.endswith("_modulator")
                          or cf in ("fl2k_universal", "stemlab_universal", "ADALM2000_universal"))
            self.assertTrue(band_only)
            self.assertFalse(band_and_audio)
            self.assertFalse(audio_only)

    def test_every_driver_has_the_modules_playrec_imports(self):
        for cf in ("smisdr_iq", "smisdr_raw"):
            work = importlib.import_module("dev_drivers.{}.cohi_playrecworker".format(cf))
            ctrl = importlib.import_module("dev_drivers.{}.SDR_control".format(cf))
            self.assertTrue(hasattr(work, "playrec_worker"))
            self.assertTrue(hasattr(ctrl, "SDR_control"))

    def test_worker_has_every_member_that_playrec_uses(self):
        import re
        with open(os.path.join(SOURCES, "player", "playrec.py"), encoding="utf-8") as fh:
            text = fh.read()
        used = set(re.findall(r"playrec_tworker\.([A-Za-z_]+)", text))
        optional = {"set_audio_mix_db", "dialog_handler", "moveToThread", "deleteLater"}
        # (guarded by hasattr / provided by QObject itself)
        used -= optional
        worker_cls = importlib.import_module("dev_drivers.smisdr_iq.cohi_playrecworker").playrec_worker
        missing = sorted(name for name in used if not hasattr(worker_cls, name)
                         and name not in ("moveToThread", "deleteLater"))
        # QObject methods of real PyQt are not part of the stub; everything else must exist
        self.assertEqual(missing, [])

    def test_playrec_server_boot_helper(self):
        import ast
        with open(os.path.join(SOURCES, "player", "playrec.py"), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        func = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "device_boots_server")
        ns = {}
        exec(compile(ast.Module(body=[func], type_ignores=[]), "playrec_helper", "exec"), ns)
        fn = ns["device_boots_server"]

        class Fake:
            def __init__(self, dev):
                self.m = {"device_ID_dict": dev}
        self.assertTrue(fn(Fake({"connection_type": "ethernet"})))                  # STEMLAB: as before
        self.assertFalse(fn(Fake({"connection_type": "USB"})))                      # fl2k: as before
        self.assertTrue(fn(Fake({"connection_type": "USB_Vethernet"})))
        for cf in ("smisdr_iq", "smisdr_raw"):
            ctrl = importlib.import_module("dev_drivers.{}.SDR_control".format(cf)).SDR_control()
            self.assertFalse(fn(Fake(ctrl.identify())))                              # smisdr: no wait

    def test_existing_drivers_keep_their_behaviour(self):
        """the playrec patch must not change drivers that have no 'server_boot' key"""
        for cf in ("stemlab_125_14", "stemlab_universal", "fl2k_universal", "ADALM2000_universal"):
            with open(os.path.join(SOURCES, "dev_drivers", cf, "SDR_control.py"), encoding="utf-8") as fh:
                self.assertNotIn("server_boot", fh.read(), cf)

    def test_identify_passes_the_rate_check_of_playrec(self):
        """re-implementation of the checks of checkSTEMLABrates for typical files"""
        def check(dev, irate, ifreq):
            if ifreq < dev["min_IFREQ"] or ifreq > dev["max_IFREQ"]:
                return False
            if dev["rate_type"] == "discrete":
                return irate in dev["rates"]
            lo, hi = list(dev["rates"].keys())[:2]
            return lo <= irate <= hi
        iq = importlib.import_module("dev_drivers.smisdr_iq.SDR_control").SDR_control().identify()
        raw = importlib.import_module("dev_drivers.smisdr_raw.SDR_control").SDR_control().identify()
        self.assertTrue(check(iq, 250_000, 1_000_000))
        self.assertTrue(check(iq, 1_250_000, 12_000_000))
        self.assertFalse(check(iq, 192_000, 1_000_000))
        self.assertTrue(check(raw, 250_000, 1_000_000))
        self.assertTrue(check(raw, 1_250_000, 1_500_000))
        self.assertFalse(check(raw, 250_000, 6_000_000))


# ======================================================================================
# cross-check against the hardware-tested reference implementation (optional)
# ======================================================================================
@unittest.skipUnless(os.environ.get("COHI_PLAYER_SRC"), "COHI_PLAYER_SRC not set")
class ReferenceCrossCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = os.environ["COHI_PLAYER_SRC"]
        sys.path.insert(0, src)
        try:
            sys.modules.setdefault("psutil", type(sys)("psutil"))
            cls.iq = importlib.import_module("smisdr_iq_backend")
            cls.raw = importlib.import_module("smisdr_backend")
        except Exception as exc:                              # pragma: no cover
            raise unittest.SkipTest("reference modules not importable: {}".format(exc))
        finally:
            sys.path.remove(src)

    def test_commands_and_ftw(self):
        for f, rate in ((1_000_000, 250_000), (7_654_321, 1_250_000), (0, 500_000)):
            self.assertEqual(protocol.build_init_sequence(f, rate),
                             self.iq.build_init_sequence(f, rate))
        self.assertEqual(protocol.calculate_ftw(12_345_678), self.iq.calculate_ftw(12_345_678))

    def test_sample_words(self):
        rng = np.random.default_rng(1)
        ints = rng.integers(-32768, 32767, size=4096).astype(np.int16)
        for gain in (1.0, 0.5, 0.25):
            ref = self.iq.encode_iq_words(ints, gain)
            mine = protocol.encode_iq_words(ints.astype(np.float32) / 32768.0, gain)
            self.assertEqual(ref, mine, gain)

    def test_helper_functions(self):
        self.assertEqual(protocol.format_iq_bus_rate_command(250_000),
                         self.iq.format_bus_rate_command(2 * 250_000))
        for v in ("auto", 5, "12,5", 10, 7):
            self.assertEqual(protocol.parse_rate_setting(v), self.raw.parse_rate_setting(v))
        for v in (None, 0, "off", False, 5000):
            self.assertEqual(protocol.parse_control_port(v), self.raw.parse_control_port(v))
        for fmt in protocol.FORMATS:
            self.assertEqual(protocol.format_width_command(fmt), self.raw.format_width_command(fmt))
        self.assertEqual(protocol.format_rate_command(12_500_000), self.raw.format_rate_command(12_500_000))


if __name__ == "__main__":
    unittest.main(verbosity=2)
