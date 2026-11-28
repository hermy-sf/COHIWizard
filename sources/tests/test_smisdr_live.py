"""
Tests of the live drivers smisdr_iq_universal and smisdr_raw_universal.

They run the REAL signal chain of stemlab_universal: ffmpeg (station = a local audio file) ->
UDP -> libdspflmod NCO engine (built from the real source, see flmod_stub.py) -> mixer ->
output stage -> fake smiSDR on localhost (and, for the raw driver, the real C++ upconverter).
Skipped without g++ or ffmpeg.  Run from the sources directory:

    python -m unittest discover -s tests -t . -v
"""
import ctypes
import os
import shutil
import struct
import sys
import tempfile
import time
import unittest
import wave
from unittest import mock

import numpy as np

SOURCES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SOURCES not in sys.path:
    sys.path.insert(0, SOURCES)

from tests import flmod_stub, qt_stub, wavgen                      # noqa: E402
from tests.test_smisdr_drivers import (DriverTestCase, RATE, build_upconverter,   # noqa: E402
                                       upconverter_processes)

qt_stub.install()

from dev_drivers.smisdr_common import protocol                      # noqa: E402

FFMPEG = shutil.which("ffmpeg")
STATION_HZ = 1_010_000          # carrier of the test station
IQ_TONE_HZ = 970_000            # tone inside the IQ file (centre 1.0 MHz, offset -30 kHz)
AUDIO_HZ = 1_000                # modulation


def spectrum(x, rate, n=1 << 16, start=None):
    """complex spectrum magnitude (Hann), -> (freqs, magnitude)"""
    start = len(x) // 3 if start is None else start
    seg = np.asarray(x[start:start + n], dtype=np.complex128)
    seg = seg - seg.mean()
    mag = np.abs(np.fft.fftshift(np.fft.fft(seg * np.hanning(len(seg)))))
    return np.fft.fftshift(np.fft.fftfreq(len(seg), 1.0 / rate)), mag


def peak_db(freqs, mag, f, width=150.0):
    """level (dB) of the strongest bin within +-width Hz of f, relative to the median noise floor"""
    sel = np.abs(freqs - f) <= width
    return 20 * np.log10(np.max(mag[sel]) / np.median(mag) + 1e-12)


def trim_silence(x):
    """The idle silence runs while ffmpeg starts up (about 1.5 s before the first block) and after
    the last block: -> the part between the first and the last non-zero sample"""
    nz = np.flatnonzero(np.asarray(x) != 0)
    return x[nz[0]: nz[-1] + 1] if len(nz) else x[:0]


def ffmpeg_processes(port):
    pids = []
    if os.path.isdir("/proc"):
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                try:
                    with open("/proc/{}/cmdline".format(entry), "rb") as fh:
                        if "udp://127.0.0.1:{}".format(port).encode() in fh.read():
                            pids.append(int(entry))
                except OSError:
                    pass
    return pids


@unittest.skipUnless(FFMPEG, "ffmpeg not available")
class LiveDriverBase(DriverTestCase):
    """common set-up: station list, config_wizard.yaml in the working directory, real
    libdspflmod, files; subclasses choose the driver"""
    lib_dir = None
    exe_dir = None
    exe = None

    @classmethod
    def setUpClass(cls):
        cls.lib_dir = tempfile.mkdtemp(prefix="smisdr_flmod_")
        cls.lib_path = flmod_stub.build(cls.lib_dir, SOURCES)
        cls.exe_dir = tempfile.mkdtemp(prefix="smisdr_up_")
        cls.exe = build_upconverter(cls.exe_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.lib_dir, True)
        shutil.rmtree(cls.exe_dir, True)

    def setUp(self):
        if self.lib_path is None:
            self.skipTest("libdspflmod cannot be built (no compiler)")
        super().setUp()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)                                  # the worker reads ./config_wizard.yaml
        self.addCleanup(os.chdir, self.old_cwd)
        self.audio_port = 23000 + (os.getpid() * 7 + int(time.time() * 10)) % 5000
        self.station_audio = self.make_audio("station.wav")
        self.playlist = os.path.join(self.tmp, "stations.csv")
        with open(self.playlist, "w") as fh:
            fh.write("{};9000;TestStation;{}\n".format(STATION_HZ, self.station_audio))

        import dev_drivers.stemlab_universal.cohi_playrecworker as sw
        lib_path = self.lib_path

        def load():
            lib = ctypes.CDLL(lib_path)
            sw._setup_lib_mod(lib, lib_path)
            return lib
        patcher = mock.patch.object(sw, "_load_lib_mod", load)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mode = "band_and_audio"
        self.write_live_config()

    def make_audio(self, name, seconds=40):
        path = os.path.join(self.tmp, name)
        rate = 22050
        t = np.arange(rate * seconds) / rate
        pcm = (0.8 * 32767 * np.sin(2 * np.pi * AUDIO_HZ * t)).astype("<i2")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(pcm.tobytes())
        return path

    def write_live_config(self, **extra):
        values = {"audioplaylist": self.playlist, "audio_rate_hz": 25000, "audio_mix_level": 1.0,
                  "audio_base_port": self.audio_port, "audio_mod_index": 0.9,
                  "ffmpeg_path": FFMPEG, "last_modulator_type": self.mode,
                  "autoAGC_DspWorker": False}
        values.update(self.cfg_extra)
        values.update(extra)
        self.write_config(**values)

    def start_live(self, files, rate=RATE, center=1_000_000, synth_only=False, **kw):
        worker, rec, crec = self.start(files, rate=rate, center=center, **kw)
        # playrec.py does this before it starts the worker: [wFormatTag, nBlockAlign, nBitsPerSample]
        if files:
            from dev_drivers.smisdr_common import iqfile
            info = iqfile.read_info(files[0])
            worker.set_formattag([info.fmt_tag, 2 * info.bits // 8, info.bits])
        if synth_only:
            worker.get_configparameters()["synth_only"] = True
        return worker, rec, crec

    def wait_audio_gone(self):
        self.assertTrue(self.wait_for(lambda: ffmpeg_processes(self.audio_port) == [], 5.0),
                        "ffmpeg is still running")


# ======================================================================================
class SmisdrIqUniversalTest(LiveDriverBase):
    driver = "smisdr_iq_universal"

    def iq_signal(self, index=0, skip_bytes=24):
        body = self.device.data(index)[skip_bytes:]
        return protocol.decode_iq_words(body[: len(body) // 4 * 4])

    def active_frames(self):
        """frames of signal (without the idle silence in front of it) received so far"""
        data = self.device.data()[24:] if self.device.connections else b""
        return len(trim_silence(protocol.decode_iq_words(data[: len(data) // 4 * 4])))

    def test_iq_file_plus_audio_carrier(self):
        path = self.wav("a.wav", 4 * RATE, offset_hz=-30_000, amplitude=0.3)
        worker, rec, crec = self.start_live([path])
        elapsed = self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(rec.finished, 1)
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n"])
        self.assertEqual(self.device.data()[:24], protocol.build_init_sequence(1_000_000, RATE))
        self.assertGreater(elapsed, 3.0)                                     # real time

        x = trim_silence(self.iq_signal())
        self.assertAlmostEqual(len(x) / (4 * RATE), 1.0, delta=0.03)         # the whole file was played
        freqs, mag = spectrum(x, RATE, start=100_000)
        carrier = peak_db(freqs, mag, STATION_HZ - 1_000_000)
        self.assertGreater(carrier, 30, "carrier of the station at +10 kHz")
        self.assertGreater(peak_db(freqs, mag, IQ_TONE_HZ - 1_000_000), 30)   # IQ file tone at -30 kHz
        for sideband in (9_000, 11_000):                                     # AM with 1 kHz audio
            self.assertGreater(peak_db(freqs, mag, sideband), carrier - 14, sideband)
        self.assertLess(peak_db(freqs, mag, 25_000), carrier - 40)           # nothing else there
        self.assertLess(float(np.mean(x == 0)), 0.01)                        # no idle silence while playing
        self.assertLess(float(np.max(np.abs(x.real))), 1.0)
        self.wait_audio_gone()

    def test_audio_only_synthesizer(self):
        self.mode = "audio_only"
        self.write_live_config()
        worker, rec, _ = self.start_live([], synth_only=True)
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: self.active_frames() > 300_000, 20))
        worker.stop_loop()
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertEqual(rec.errors, [], rec.errors)
        freqs, mag = spectrum(trim_silence(self.iq_signal()), RATE, start=100_000)
        carrier = peak_db(freqs, mag, 10_000)
        self.assertGreater(carrier, 30)
        for sideband in (9_000, 11_000):
            self.assertGreater(peak_db(freqs, mag, sideband), carrier - 14)
        self.wait_audio_gone()

    def test_pause_sends_silence_instead_of_a_carrier(self):
        self.mode = "audio_only"
        self.write_live_config()
        worker, rec, _ = self.start_live([], synth_only=True)
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: self.active_frames() > 150_000, 20))
        worker.set_pause(True)
        time.sleep(1.2)                                       # old data drains, idle silence takes over
        size = len(self.device.data())
        time.sleep(0.8)
        grown = self.device.data()[size:]
        self.assertGreater(len(grown), 4 * 100_000)           # the stream is kept alive ...
        words = np.frombuffer(grown[:len(grown) // 4 * 4], dtype="<u2")
        self.assertEqual(set(words[::2].tolist()), {0x0000})  # ... with zeros
        self.assertEqual(set(words[1::2].tolist()), {0x4000})
        worker.set_pause(False)
        before = len(self.device.data())
        time.sleep(1.0)
        resumed = np.frombuffer(self.device.data()[before:][:400_000], dtype="<u2")
        self.assertGreater(len(set(resumed[::2].tolist())), 50)       # the carrier is back
        worker.stop_loop()
        thread.join(8)
        self.assertEqual(rec.errors, [], rec.errors)

    def test_stop_cleans_up(self):
        path = self.wav("a.wav", 30 * RATE)
        worker, rec, _ = self.start_live([path])
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: len(self.device.connections) == 1
                                      and len(self.device.data()) > 24 + 4 * 300_000, 15))
        self.assertTrue(ffmpeg_processes(self.audio_port))
        t0 = time.monotonic()
        worker.stop_loop()
        thread.join(8)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - t0, 5)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(rec.finished, 1)
        self.wait_audio_gone()

    def test_chain_with_new_parameters_reconfigures_without_audio(self):
        self.mode = "band_only"                               # no overlay: plain IQ chain
        self.write_live_config()
        a = self.wav("a.wav", 25_000, rate=250_000, center=1_000_000)
        b = self.wav("b.wav", 50_000, rate=500_000, center=1_100_000)
        worker, rec, _ = self.start_live([a, b])
        self.run_worker(worker)
        time.sleep(0.3)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(len(self.device.connections), 2)
        self.assertEqual(self.device.commands, ["width 16\n", "rate 0.5\n", "width 16\n", "rate 1.0\n"])
        self.assertEqual(self.device.data(1)[:24], protocol.build_init_sequence(1_100_000, 500_000))
        self.assertEqual(len(self.device.data(1)), 24 + 50_000 * 4 + 256 * 4)

    def test_chain_with_new_parameters_is_refused_with_audio_overlay(self):
        a = self.wav("a.wav", 2 * RATE, rate=250_000, center=1_000_000)
        b = self.wav("b.wav", 2 * RATE, rate=250_000, center=1_100_000)
        worker, rec, _ = self.start_live([a, b])
        self.run_worker(worker)
        self.assertEqual(len(rec.errors), 1, rec.errors)
        self.assertIn("audio overlay", rec.errors[0])
        self.assertEqual(rec.finished, 1)
        self.wait_audio_gone()

    def test_same_parameters_chain_plays_through_with_audio(self):
        a = self.wav("a.wav", RATE, center=1_000_000)
        b = self.wav("b.wav", RATE, center=1_000_000)
        worker, rec, _ = self.start_live([a, b])
        self.run_worker(worker)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(len(rec.nextfiles), 2)
        self.assertEqual(len(self.device.connections), 1)
        self.wait_audio_gone()

    def test_config_socket_reports_problems(self):
        Control, _ = self.modules()
        for params, text in (({"ifreq": 1e6, "irate": 300_000}, "not supported"),
                             ({"ifreq": 24.9e6, "irate": 250_000}, "above the usable range")):
            ctrl = Control()
            crec = __import__("tests.test_smisdr_drivers", fromlist=["Recorder"]).Recorder(ctrl)
            params.update({"HostAddress": "127.0.0.1", "icorr": 0, "LO_offset": 0})
            self.assertFalse(ctrl.config_socket(params))
            self.assertIn(text, crec.errors[0])
            self.assertIsNone(ctrl.data_sock)
        self.write_live_config(smisdr_data_port=1)
        ctrl = Control()
        self.assertFalse(ctrl.config_socket({"HostAddress": "127.0.0.1", "ifreq": 1e6, "irate": 250_000,
                                             "icorr": 0, "LO_offset": 0}))

    def test_config_socket_opens_the_device_and_applies_ppm(self):
        Control, _ = self.modules()
        ctrl = Control()
        self.assertTrue(ctrl.config_socket({"HostAddress": "127.0.0.1", "ifreq": 1e6, "irate": 250_000,
                                            "icorr": 10, "LO_offset": 0}))
        self.assertIs(ctrl.data_sock, ctrl.sink)
        self.assertTrue(self.wait_for(lambda: len(self.device.data()) >= 24, 3))
        self.assertEqual(self.device.data()[:24], protocol.build_init_sequence(1_000_010, 250_000))
        ctrl.sdrserverstop()
        self.assertIsNone(ctrl.data_sock)

    def test_test_mode_needs_no_device(self):
        path = self.wav("a.wav", 20_000)
        worker, rec, _ = self.start_live([path], test=True, check_config=False)
        self.run_worker(worker)
        self.assertEqual(self.device.connections, [])
        self.assertEqual(rec.finished, 1)
        self.assertEqual(rec.errors, [])

    def test_identify(self):
        Control, _ = self.modules()
        dev = Control().identify()
        self.assertEqual(dev["device_name"], "smisdr_iq_universal")
        self.assertEqual(dev["resolutions"], [16, 32])
        self.assertTrue(dev["RX"] and dev["TX"])
        self.assertFalse(dev["server_boot"])
        ctrl = Control()
        self.assertTrue(ctrl.set_rec()[0])                    # recording is refused with a message


# ======================================================================================
class SmisdrRawUniversalTest(LiveDriverBase):
    driver = "smisdr_raw_universal"

    def setUp(self):
        if shutil.which("g++") is None:
            self.skipTest("no compiler")
        super().setUp()
        self.cfg_extra = {"smisdr_upconverter_path": self.exe, "smisdr_sample_rate": 5}
        self.write_live_config()

    def rf(self, index=0):
        return np.frombuffer(self.device.data(index), dtype=np.int8)

    def active_samples(self):
        data = self.rf() if self.device.connections else np.zeros(0, dtype=np.int8)
        return len(trim_silence(data))

    def rf_spectrum(self, x, n=1 << 18):
        seg = x[len(x) // 3: len(x) // 3 + n].astype(np.float64)
        seg = (seg - seg.mean()) * np.hanning(len(seg))
        mag = np.abs(np.fft.rfft(seg))
        return np.fft.rfftfreq(len(seg), 1 / 5_000_000), mag

    def test_iq_file_plus_audio_carrier_on_rf(self):
        path = self.wav("a.wav", 4 * RATE, offset_hz=-30_000, amplitude=0.3)
        worker, rec, _ = self.start_live([path])
        self.run_worker(worker)
        time.sleep(0.5)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(rec.finished, 1)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"])
        x = trim_silence(self.rf())
        self.assertAlmostEqual(len(x) / (4 * 5_000_000), 1.0, delta=0.06)
        freqs, mag = self.rf_spectrum(x)
        floor = float(np.median(mag))
        db = lambda f, w=200: 20 * np.log10(np.max(mag[np.abs(freqs - f) <= w]) / floor)     # noqa: E731
        carrier = db(STATION_HZ)
        self.assertGreater(carrier, 30, "carrier at 1010 kHz")
        self.assertGreater(db(IQ_TONE_HZ), 30, "IQ file tone at 970 kHz")
        for f in (STATION_HZ - 1_000, STATION_HZ + 1_000):
            self.assertGreater(db(f), carrier - 14)
        self.assertEqual(upconverter_processes(self.exe), [])
        self.wait_audio_gone()

    def test_audio_only_on_rf_and_clean_stop(self):
        self.mode = "audio_only"
        self.write_live_config()
        worker, rec, _ = self.start_live([], synth_only=True)
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: self.active_samples() > 1_500_000, 25))
        self.assertEqual(len(upconverter_processes(self.exe)), 1)
        worker.stop_loop()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(rec.errors, [], rec.errors)
        freqs, mag = self.rf_spectrum(trim_silence(self.rf()))
        floor = float(np.median(mag))
        self.assertGreater(20 * np.log10(np.max(mag[np.abs(freqs - STATION_HZ) <= 200]) / floor), 30)
        self.assertEqual(upconverter_processes(self.exe), [])
        self.wait_audio_gone()

    def test_pause_sends_rf_silence(self):
        self.mode = "audio_only"
        self.write_live_config()
        worker, rec, _ = self.start_live([], synth_only=True)
        thread = self.run_in_thread(worker)
        self.assertTrue(self.wait_for(lambda: self.active_samples() > 1_000_000, 25))
        worker.set_pause(True)
        time.sleep(1.5)
        size = len(self.device.data())
        time.sleep(0.8)
        tail = np.frombuffer(self.device.data()[size:], dtype=np.int8)
        self.assertGreater(len(tail), 1_000_000)
        self.assertLessEqual(int(np.max(np.abs(tail))), 1)
        worker.stop_loop()
        thread.join(10)
        self.assertEqual(rec.errors, [], rec.errors)

    def test_chain_with_new_parameters_reconfigures_without_audio(self):
        self.mode = "band_only"
        self.write_live_config()
        a = self.wav("a.wav", 25_000, center=1_000_000)
        b = self.wav("b.wav", 25_000, center=1_200_000)
        worker, rec, _ = self.start_live([a, b])
        self.run_worker(worker)
        time.sleep(0.4)
        self.assertEqual(rec.errors, [], rec.errors)
        self.assertEqual(len(self.device.connections), 2)
        self.assertEqual(self.device.commands, ["width 8\n", "rate 5.0\n"] * 2)
        f1, m1 = self.rf_spectrum(self.rf(0), 1 << 17)
        f2, m2 = self.rf_spectrum(self.rf(1), 1 << 17)
        self.assertAlmostEqual(float(f1[np.argmax(m1)]), 1_005_000, delta=400)
        self.assertAlmostEqual(float(f2[np.argmax(m2)]), 1_205_000, delta=400)
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_missing_tool_is_reported_by_config_socket(self):
        self.write_live_config(smisdr_upconverter_path="/nonexistent/up")
        Control, _ = self.modules()
        ctrl = Control()
        errors = []
        ctrl.SigError.connect(errors.append)
        self.assertFalse(ctrl.config_socket({"HostAddress": "127.0.0.1", "ifreq": 1e6,
                                             "irate": 250_000, "icorr": 0, "LO_offset": 0}))
        self.assertIn("not found", errors[0])

    def test_signal_outside_the_output_rate(self):
        Control, _ = self.modules()
        ctrl = Control()
        errors = []
        ctrl.SigError.connect(errors.append)
        self.assertFalse(ctrl.config_socket({"HostAddress": "127.0.0.1", "ifreq": 4e6,
                                             "irate": 250_000, "icorr": 0, "LO_offset": 0}))
        self.assertIn("does not fit", errors[0])
        self.assertEqual(upconverter_processes(self.exe), [])

    def test_identify(self):
        Control, _ = self.modules()
        dev = Control().identify()
        self.assertEqual(dev["device_name"], "smisdr_raw_universal")
        self.assertEqual(dev["rate_type"], "continuous")
        self.assertEqual(dev["max_IFREQ"], int(0.95 * 5_000_000 / 2))


# ======================================================================================
class LiveIntegrationTest(unittest.TestCase):
    def test_visible_in_the_modes_with_audio(self):
        """the list filters of playrec (after the change from a list of three names to *_universal)"""
        drvdir = os.path.join(SOURCES, "dev_drivers")
        names = [cf for cf in os.listdir(drvdir) if not cf.startswith(".")
                 and os.path.isfile(os.path.join(drvdir, cf, "cohi_playrecworker.py"))]
        for cf in ("smisdr_iq_universal", "smisdr_raw_universal"):
            self.assertIn(cf, names)
            band_only = not (cf.endswith("_modulator") or cf.endswith("_plus") or cf.find("__") == 0)
            band_and_audio = (cf.endswith("_plus") or cf.endswith("_universal")) and cf.find("__") != 0
            audio_only = cf.endswith("_modulator") or cf.endswith("_universal")
            self.assertTrue(band_and_audio and audio_only)
            self.assertFalse(band_only is False and False)
        # the old list of the three universal drivers is still covered, nothing else is added
        universal = sorted(cf for cf in names if cf.endswith("_universal") and not cf.startswith("__"))
        self.assertEqual(universal, ["ADALM2000_universal", "fl2k_universal", "smisdr_iq_universal",
                                     "smisdr_raw_universal", "stemlab_universal"])

    def test_playrec_has_no_hardcoded_driver_list_any_more(self):
        with open(os.path.join(SOURCES, "player", "playrec.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn('cf in ("fl2k_universal", "stemlab_universal", "ADALM2000_universal")', text)
        self.assertEqual(text.count('endswith("_universal")'), 3)      # 2 filters + band_and_audio

    def test_worker_is_a_stemlab_universal_worker(self):
        qt_stub.install()
        import importlib
        base = importlib.import_module("dev_drivers.stemlab_universal.cohi_playrecworker").playrec_worker
        for cf in ("smisdr_iq_universal", "smisdr_raw_universal"):
            worker = importlib.import_module("dev_drivers.{}.cohi_playrecworker".format(cf)).playrec_worker
            self.assertTrue(issubclass(worker, base))


if __name__ == "__main__":
    unittest.main(verbosity=2)
