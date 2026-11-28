"""
Tests of the operating mode handling (parlioSDR control port), the peak limiter and the level
log of the smisdr drivers, plus - if PARLIOSDR_SRC points at the sources of the parlioSDR firmware
(<repo>/main) - a run of the recorded stream through the real parser, planner and DSP of the
firmware (tests/firmware_duc_sim.c).

    python -m unittest discover -s tests -t . -v
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import numpy as np

SOURCES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SOURCES not in sys.path:
    sys.path.insert(0, SOURCES)

from tests import qt_stub, wavgen                                                    # noqa: E402
from tests.fake_device import FakeSmisdr                                             # noqa: E402
from tests.test_smisdr_drivers import (DriverTestCase, RATE, build_upconverter,       # noqa: E402
                                       upconverter_processes)

qt_stub.install()

from dev_drivers.smisdr_common import protocol, settings, sinks                      # noqa: E402


class ParlioTestCase(DriverTestCase):
    def use_device(self, **kwargs):
        self.device.close()
        self.device = FakeSmisdr(parlio=True, **kwargs)
        self.addCleanup(self.device.close)
        self.write_config()


# ======================================================================================
class IqModeTest(ParlioTestCase):
    driver = "smisdr_iq"

    def play(self, frames=5_000, **kw):
        path = self.wav("a.wav", frames)
        worker, rec, _ = self.start([path], **kw)
        self.run_worker(worker)
        time.sleep(0.15)
        return rec

    def setUp(self):
        super().setUp()
        self.write_config()

    def test_plain_smisdr_is_left_alone(self):
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.queries, ["mode\n"])                    # asked once, no answer
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])   # as before

    def test_soft_needs_a_device_with_modes(self):
        self.write_config(smisdr_iq_dsp="soft")
        rec = self.play()
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("does not know the command 'mode'", rec.errors[0])
        self.assertEqual(self.device.connections, [])

    def test_auto_switches_the_esp32_to_the_soft_duc(self):
        self.use_device(mode="raw")
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["mode duc\n"])               # no width / rate in duc mode
        self.assertEqual(self.device.mode, "duc")
        self.assertEqual(len(self.device.connections), 1)                    # connected after the switch
        self.assertEqual(self.device.data()[:24], protocol.build_init_sequence(1_000_000, RATE))

    def test_no_switch_if_the_device_is_in_duc_mode_already(self):
        self.use_device(mode="duc")
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, [])
        self.assertEqual(self.device.queries, ["mode\n"])
        self.assertEqual(len(self.device.connections), 1)

    def test_extra_duc_commands_are_sent_after_the_switch(self):
        self.use_device(mode="raw")
        self.write_config(smisdr_duc_commands=["duc width 8", "duc offset on", "duc gain auto"])
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands,
                         ["mode duc\n", "duc width 8\n", "duc offset on\n", "duc gain auto\n"])

    def test_refused_extra_command_is_logged_but_playback_goes_on(self):
        self.use_device(mode="duc")
        self.write_config(smisdr_duc_commands=["duc nonsense"])
        with self.assertLogs("smisdr", level="WARNING") as logs:
            rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertTrue(any("was refused" in m for m in logs.output), logs.output)
        self.assertEqual(len(self.device.connections), 1)

    def test_fpga_behind_the_esp32_keeps_raw_mode_and_gets_width_and_rate(self):
        self.use_device(mode="raw")
        self.write_config(smisdr_iq_dsp="fpga")
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])
        self.assertEqual(self.device.mode, "raw")

    def test_fpga_setting_switches_a_soft_duc_session_back_to_raw(self):
        self.use_device(mode="duc")
        self.write_config(smisdr_iq_dsp="fpga")
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["mode raw\n", "width 16\n", "rate 0.5\n"])
        self.assertEqual(self.device.mode, "raw")

    def test_mode_switch_can_be_turned_off(self):
        self.use_device(mode="raw")
        self.write_config(smisdr_mode_switch=False)
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.queries, [])
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])
        self.assertEqual(self.device.mode, "raw")

    def test_without_control_port_nothing_is_sent(self):
        self.use_device(mode="raw")
        self.write_config(smisdr_control_port=0)
        rec = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual((self.device.queries, self.device.commands), ([], []))

    def test_a_device_that_does_not_switch_is_reported(self):
        self.use_device(mode="raw", refuse_duc=True)
        rec = self.play()
        self.assertEqual(len(rec.errors), 1)
        self.assertIn("did not switch to mode duc", rec.errors[0])
        self.assertEqual(self.device.connections, [])

    def test_chain_with_new_parameters_does_not_switch_again(self):
        self.use_device(mode="raw")
        a = self.wav("a.wav", 5_000, rate=250_000, center=1_000_000)
        b = self.wav("b.wav", 10_000, rate=500_000, center=1_100_000)
        worker, rec, _ = self.start([a, b])
        self.run_worker(worker)
        time.sleep(0.2)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["mode duc\n"])
        self.assertEqual(len(self.device.queries), 2)                        # one query per configuration
        self.assertEqual(len(self.device.connections), 2)
        self.assertEqual(self.device.data(1)[:24], protocol.build_init_sequence(1_100_000, 500_000))

    def test_settings_are_validated(self):
        for key, value in (("smisdr_iq_dsp", "esp"), ("smisdr_mode_switch", "yes"),
                           ("smisdr_duc_commands", ["width 8"]), ("smisdr_duc_commands", 5),
                           ("smisdr_limiter", 1)):
            with self.assertRaises(settings.SettingsError, msg=key) as ctx:
                settings.parse_settings({key: value})
            self.assertIn(key, str(ctx.exception))
        ok = settings.parse_settings({"smisdr_duc_commands": "duc width 8", "smisdr_iq_dsp": "SOFT"})
        self.assertEqual((ok["duc_commands"], ok["iq_dsp"]), (["duc width 8"], "soft"))
        self.assertEqual(settings.parse_settings({})["duc_commands"], [])


# ======================================================================================
class RawModeTest(ParlioTestCase):
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
            self.skipTest("no C++ compiler")
        super().setUp()
        self.cfg_extra = {"smisdr_upconverter_path": self.exe, "smisdr_sample_rate": 5}
        self.write_config()

    def play(self):
        path = self.wav("a.wav", 12_500)
        worker, rec, _ = self.start([path])
        elapsed = self.run_worker(worker)
        time.sleep(0.3)
        return rec, elapsed

    def test_soft_duc_session_is_ended_before_rf_samples_are_sent(self):
        self.use_device(mode="duc", raw_switch_delay=0.6)       # 'mode raw' takes a while
        rec, elapsed = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["mode raw\n", "width 8\n", "rate 5.0\n"])
        self.assertEqual(self.device.mode, "raw")
        self.assertGreater(elapsed, 0.6)                         # it waited for the answer
        self.assertEqual(len(self.device.connections), 1)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_device_in_raw_mode_needs_no_switch(self):
        self.use_device(mode="raw")
        rec, _ = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"])

    def test_plain_smisdr_is_left_alone(self):
        rec, _ = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"])

    def test_mode_switch_off(self):
        self.use_device(mode="duc")
        self.write_config(smisdr_mode_switch=False)
        rec, _ = self.play()
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(self.device.queries, [])
        self.assertEqual(self.device.mode, "duc")


# ======================================================================================
class PeakLimiterTest(unittest.TestCase):
    def band(self, n=65_536, seed=3):
        """noise-like band with a few carriers, normalized to a peak of 1"""
        rng = np.random.default_rng(seed)
        t = np.arange(n) / 250_000
        z = sum(rng.uniform(.3, 1) * (1 + .5 * np.sin(2 * np.pi * rng.uniform(100, 3000) * t))
                * np.exp(2j * np.pi * rng.uniform(-100e3, 100e3) * t) for _ in range(12))
        z = z + 0.05 * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
        z = z / np.max(np.abs(z))
        iq = np.empty(2 * n, np.float32)
        iq[0::2], iq[1::2] = z.real, z.imag
        return iq

    def test_avc_overdrive_is_limited_without_clipping_the_waveform(self):
        iq = self.band()
        lim = protocol.PeakLimiter(250_000)
        blocks = [lim.process(iq[i:i + 8192], 4.77) for i in range(0, len(iq), 8192)]
        out = np.concatenate(blocks)
        self.assertLessEqual(float(np.max(np.abs(out))), 1.0 + 1e-6)
        self.assertGreater(float(np.mean(np.abs(iq * 4.77) > 1)), 0.1)       # the AVC level does overload
        # inside a block the limiter only scales: out / in is constant (after the 128 pair fade),
        # hard clipping would change the waveform
        for k, block in enumerate(blocks[2:], start=2):
            src = iq[k * 8192:(k + 1) * 8192][256:]
            dst = block[256:]
            sel = np.abs(src) > 0.05
            ratio = dst[sel] / src[sel]
            self.assertLess(float(np.std(ratio) / np.mean(ratio)), 1e-4, k)
        # and the level is used: the gain returns slowly (1.0 per second), so a block after a high
        # peak may stay below the ceiling, but typically the blocks peak close to it
        peaks = [float(np.max(np.abs(b))) for b in blocks[1:]]
        self.assertGreater(float(np.median(peaks)), 0.9)
        self.assertLessEqual(max(peaks), 1.0 + 1e-6)
        hard = np.clip(iq * 4.77, -1, 1)
        self.assertGreater(float(np.mean(np.abs(hard) >= 0.9999)), 0.1)      # what clipping would do

    def test_quiet_signal_is_not_touched(self):
        iq = self.band() * 0.3
        lim = protocol.PeakLimiter(250_000)
        out = lim.process(iq, 1.0)
        np.testing.assert_array_equal(out, iq)
        self.assertEqual(lim.gain, 1.0)

    def test_attack_is_not_overshooting_into_the_gain(self):
        """the fade of the first block must not leave the gain below what the peak asks for"""
        lim = protocol.PeakLimiter(250_000)
        out = lim.process(np.full(2 * 1_000, 1.0, np.float32), 8.0)
        self.assertAlmostEqual(lim.gain, 0.125, places=4)
        self.assertLessEqual(float(np.max(out)), 1.0)
        self.assertAlmostEqual(float(out[-1]), 1.0, places=3)
        self.assertGreater(float(out[0]), 0.99)                              # held at the ceiling, not muted

    def test_gain_recovers_after_a_loud_block(self):
        lim = protocol.PeakLimiter(250_000, release_per_s=1.0)
        quiet = np.full(2 * 25_000, 0.1, np.float32)                         # 0.1 s per block
        lim.process(np.full(2 * 1_000, 1.0, np.float32), 8.0)                # peak 8 -> gain 1/8
        self.assertAlmostEqual(lim.gain, 0.125, places=3)
        gains = []
        for _ in range(10):
            lim.process(quiet, 1.0)
            gains.append(lim.gain)
        self.assertAlmostEqual(gains[0], 0.225, places=2)                    # + 0.1 per 0.1 s
        self.assertEqual(lim.gain, 1.0)
        self.assertTrue(all(b >= a for a, b in zip(gains, gains[1:])))

    def test_magnitude_mode_limits_the_rf_amplitude(self):
        lim = protocol.PeakLimiter(250_000, ceiling=0.24, magnitude=True)
        t = np.arange(8192) / 250_000
        z = 0.9 * np.exp(2j * np.pi * 10_000 * t)
        iq = np.empty(2 * len(z), np.float32)
        iq[0::2], iq[1::2] = z.real, z.imag
        out = lim.process(iq, 1.0)
        mag = np.hypot(out[0::2], out[1::2])
        self.assertLessEqual(float(np.max(mag)), 0.24 + 1e-6)
        self.assertGreater(float(np.max(mag)), 0.235)

    def test_odd_and_empty_blocks(self):
        lim = protocol.PeakLimiter(250_000)
        self.assertEqual(len(lim.process(np.zeros(0, np.float32), 1.0)), 0)
        self.assertEqual(len(lim.process(np.ones(7, np.float32), 2.0)), 6)
        lim = protocol.PeakLimiter(250_000)
        corrupt = lim.process(np.array([np.nan, np.inf, 0.1, -0.1], np.float32), 1.0)
        np.testing.assert_array_equal(corrupt, [0.0, 0.0, np.float32(0.1), np.float32(-0.1)])
        self.assertEqual(lim.gain, 1.0)                                      # one bad sample is no overload


class LevelAndLimiterInTheDriversTest(DriverTestCase):
    driver = "smisdr_iq"

    def hot_file(self, amplitude=0.9):
        return self.wav("hot.wav", 50_000, offset_hz=7_000, amplitude=amplitude)

    def test_limiter_keeps_an_overdriven_stream_clean(self):
        self.write_config()
        worker, rec, _ = self.start([self.hot_file()], gain=4.77)
        self.run_worker(worker)
        time.sleep(0.2)
        self.assertEqual(rec.errors, [], rec.errors)
        x = protocol.decode_iq_words(self.device.data()[24:][:50_000 * 4])[20_000:]
        self.assertLessEqual(float(np.max(np.abs(x.real))), 1.0)
        self.assertGreater(float(np.max(np.abs(x.real))), 0.9)               # level is used, not lost
        # still a clean tone: constant envelope (hard clipping would flatten I and Q separately)
        env = np.abs(x)
        self.assertLess(float(np.std(env) / np.mean(env)), 0.02)

    def test_without_the_limiter_the_stream_clips(self):
        self.write_config(smisdr_limiter=False)
        worker, rec, _ = self.start([self.hot_file()], gain=4.77)
        self.run_worker(worker)
        time.sleep(0.2)
        x = protocol.decode_iq_words(self.device.data()[24:][:50_000 * 4])[20_000:]
        self.assertGreater(float(np.mean(np.abs(x.real) >= 0.9998)), 0.3)    # flat tops
        self.assertGreater(float(np.std(np.abs(x)) / np.mean(np.abs(x))), 0.1)

    def test_level_is_logged_and_overload_is_warned_about(self):
        self.write_config(smisdr_limiter=False)
        with unittest_mock_level_interval(0.0):
            worker, rec, _ = self.start([self.hot_file()], gain=4.77)
            with self.assertLogs("smisdr", level="INFO") as logs:
                self.run_worker(worker)
        warnings = [m for m in logs.output if "WARNING" in m and "overdriven" in m]
        self.assertTrue(warnings, logs.output)
        self.assertIn("% of full scale", warnings[0])

    def test_limiter_action_is_logged(self):
        self.write_config()
        with unittest_mock_level_interval(0.0):
            worker, rec, _ = self.start([self.hot_file()], gain=4.77)
            with self.assertLogs("smisdr", level="INFO") as logs:
                self.run_worker(worker)
        text = " ".join(logs.output)
        self.assertIn("limiter reduced the level by up to", text)
        self.assertFalse(any("overdriven" in m for m in logs.output), logs.output)


class unittest_mock_level_interval:
    """report the level at every block (the real interval is 5 s)"""
    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        self.old = sinks.LEVEL_REPORT_S
        sinks.LEVEL_REPORT_S = self.seconds

    def __exit__(self, *exc):
        sinks.LEVEL_REPORT_S = self.old


class RawLimiterTest(DriverTestCase):
    driver = "smisdr_raw"
    exe = None

    @classmethod
    def setUpClass(cls):
        cls.exe_dir = tempfile.mkdtemp(prefix="smisdr_up_")
        cls.exe = build_upconverter(cls.exe_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.exe_dir, True)

    def setUp(self):
        if self.exe is None:
            self.skipTest("no C++ compiler")
        super().setUp()
        self.cfg_extra = {"smisdr_upconverter_path": self.exe, "smisdr_sample_rate": 5}

    def saturated_fraction(self, **cfg):
        self.write_config(**cfg)
        path = self.wav("hot.wav", 25_000, offset_hz=7_000, amplitude=0.9)
        worker, rec, _ = self.start([path], gain=1.0)
        self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        rf = np.frombuffer(self.device.data(), dtype=np.int8)
        rf = rf[len(rf) // 4: -1000]
        return float(np.mean(np.abs(rf) >= 127)), int(np.max(np.abs(rf)))

    def test_rf_output_does_not_saturate_with_the_limiter(self):
        # a 0.9 FS tone: the upconverter reaches the DAC full scale at 0.25 FS
        sat, peak = self.saturated_fraction()
        self.assertLess(sat, 0.01)
        self.assertGreater(peak, 115)                       # the DAC range is used

    def test_rf_output_saturates_without_the_limiter(self):
        sat, _ = self.saturated_fraction(smisdr_limiter=False)
        self.assertGreater(sat, 0.2)


# ======================================================================================
@unittest.skipUnless(os.environ.get("PARLIOSDR_SRC"),
                     "PARLIOSDR_SRC (the main directory of the parlioSDR firmware) is not set")
class FirmwareDspTest(DriverTestCase):
    """The recorded stream of the driver goes through the parser, the rate planner and the DSP
    of the parlioSDR firmware, which are plain C and run on the host."""
    driver = "smisdr_iq"
    sim = None

    @classmethod
    def setUpClass(cls):
        src = os.environ["PARLIOSDR_SRC"]
        cls.dir = tempfile.mkdtemp(prefix="smisdr_sim_")
        cls.sim = os.path.join(cls.dir, "sim")
        compiler = shutil.which("gcc") or shutil.which("cc")
        if compiler is None:
            raise unittest.SkipTest("no C compiler")
        result = subprocess.run(
            [compiler, "-O2", "-I", src, "-o", cls.sim,
             os.path.join(SOURCES, "tests", "firmware_duc_sim.c"),
             os.path.join(src, "duc_proto.c"), os.path.join(src, "sdr_plan.c"),
             os.path.join(src, "sdr_dsp.c"), "-lm"], capture_output=True, text=True)
        if result.returncode != 0:
            raise unittest.SkipTest("firmware sources do not build: " + result.stderr[-300:])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def run_firmware(self, frames, rate, center, offset_hz, gain=1.0, amplitude=0.5):
        self.write_config()
        path = self.wav("a.wav", frames, rate=rate, center=center, offset_hz=offset_hz,
                        amplitude=amplitude)
        worker, rec, _ = self.start([path], rate=rate, center=center, gain=gain)
        self.run_worker(worker)
        time.sleep(0.2)
        self.assertEqual(rec.errors, [], rec.errors)
        stream = os.path.join(self.tmp, "stream.bin")
        rf_path = os.path.join(self.tmp, "rf.bin")
        with open(stream, "wb") as fh:
            fh.write(self.device.data())
        out = subprocess.run([self.sim, stream, rf_path], capture_output=True, text=True).stdout
        info = dict(item.split("=") for item in out.split())
        rf = np.fromfile(rf_path, dtype=np.int16)
        return info, rf

    @staticmethod
    def spectrum_peak(rf, fs_out):
        seg = rf[len(rf) // 3: len(rf) // 3 + (1 << 18)].astype(np.float64)
        mag = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / fs_out)
        return freqs, mag

    def test_commands_samples_and_carrier_arrive_as_sent(self):
        for rate, center, offset in ((250_000, 1_000_000, 5_000), (500_000, 2_000_000, -30_000),
                                     (1_250_000, 1_250_000, -100_000)):
            with self.subTest(rate=rate, center=center):
                self.device.connections.clear()
                info, rf = self.run_firmware(int(rate * 0.6), rate, center, offset)
                self.assertEqual((info["bad"], info["drop_i"], info["drop_q"], info["bad_cfg"]),
                                 ("0", "0", "0", "0"))
                self.assertEqual(int(info["fs"]), rate)
                self.assertAlmostEqual(float(info["shift"]), center, delta=0.1)
                self.assertEqual(int(info["pairs"]), int(rate * 0.6) + 256)  # every I/Q pair + the closing silence
                freqs, mag = self.spectrum_peak(rf, int(info["fs_out"]))
                self.assertAlmostEqual(float(freqs[np.argmax(mag)]), center + offset, delta=60)
                self.assertAlmostEqual(np.max(np.abs(rf)) / 32768, 0.5, delta=0.1)   # firmware AGC

    def test_overdriven_stream_is_clean_only_with_the_limiter(self):
        def sfdr(**cfg):
            self.device.connections.clear()
            self.write_config(**cfg)
            path = self.wav("a.wav", 150_000, offset_hz=7_000, amplitude=0.5)
            worker, rec, _ = self.start([path], gain=6.0)                     # AVC-like overdrive
            self.run_worker(worker)
            time.sleep(0.2)
            stream = os.path.join(self.tmp, "stream.bin")
            with open(stream, "wb") as fh:
                fh.write(self.device.data())
            out = subprocess.run([self.sim, stream, os.path.join(self.tmp, "rf.bin")],
                                 capture_output=True, text=True).stdout
            fs_out = int(dict(i.split("=") for i in out.split())["fs_out"])
            freqs, mag = self.spectrum_peak(np.fromfile(os.path.join(self.tmp, "rf.bin"), dtype=np.int16), fs_out)
            carrier = np.max(mag)
            peak_f = freqs[np.argmax(mag)]
            rest = mag[(np.abs(freqs - peak_f) > 300)]
            return 20 * np.log10(carrier / np.max(rest))
        clean, clipped = sfdr(), sfdr(smisdr_limiter=False)
        self.assertGreater(clean, clipped + 20, (clean, clipped))
        self.assertGreater(clean, 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
