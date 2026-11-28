"""Tests of the additions to cohi_setup.py for the smisdr drivers: dependency expansion, the
shared directory, and the build of the up-conversion tool (real make, in a temp directory)."""
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

SOURCES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SOURCES not in sys.path:
    sys.path.insert(0, SOURCES)

import cohi_setup                                                    # noqa: E402

UPDIR = "sources/dev_drivers/smisdr_common/upconverter/"


def fake_tree():
    paths = ["README.md", "requirements.txt", "LICENSE", "sources/COHIWizard.py",
             "sources/dev_drivers/__init__.py", "sources/dev_drivers/libcheck.py",
             "sources/dev_drivers/playlist_paths.py", "sources/dev_drivers/libs/Makefile",
             "sources/dev_drivers/libs/DspWorkerFLMod.cpp", "sources/dev_drivers/libs/libdspflmod.so",
             "sources/dev_drivers/libs/libdspfl2k.so"]
    for drv in ("stemlab_universal", "fl2k_universal", "smisdr_iq", "smisdr_raw",
                "smisdr_iq_universal", "smisdr_raw_universal"):
        paths += ["sources/dev_drivers/{}/{}".format(drv, f)
                  for f in ("__init__.py", "SDR_control.py", "cohi_playrecworker.py")]
    paths += ["sources/dev_drivers/smisdr_common/" + f
              for f in ("__init__.py", "protocol.py", "sinks.py", "live_worker.py", "README.md")]
    paths += [UPDIR + "Makefile", UPDIR + "cohi_native_upconverter.cpp"]
    return {p: ("sha_" + p, 1, 0o100644) for p in paths}


class WantedFilesTest(unittest.TestCase):
    def test_requirements_are_expanded(self):
        self.assertEqual(cohi_setup.expand_requires(["smisdr_iq_universal"]),
                         ["smisdr_iq_universal", "stemlab_universal"])
        self.assertEqual(cohi_setup.expand_requires(["smisdr_iq"]), ["smisdr_iq"])
        self.assertEqual(cohi_setup.expand_requires(["fl2k_universal", "smisdr_raw_universal"]),
                         ["fl2k_universal", "smisdr_raw_universal", "stemlab_universal"])
        self.assertEqual(cohi_setup.expand_requires(["unknown_driver"]), ["unknown_driver"])

    def test_selected_smisdr_driver_brings_the_shared_code_and_the_tool_source(self):
        want = cohi_setup.wanted_files(fake_tree(), ["resampler"], ["smisdr_iq"], "linux")
        self.assertIn("sources/dev_drivers/smisdr_iq/cohi_playrecworker.py", want)
        self.assertIn("sources/dev_drivers/smisdr_common/sinks.py", want)
        self.assertIn(UPDIR + "cohi_native_upconverter.cpp", want)
        self.assertNotIn("sources/dev_drivers/smisdr_raw/SDR_control.py", want)
        self.assertNotIn("sources/dev_drivers/stemlab_universal/SDR_control.py", want)

    def test_live_driver_gets_the_stemlab_universal_chain_through_make_plan(self):
        inst = SimpleNamespace(installed_drivers=lambda: [], installed_modules=lambda: [],
                               state={}, p=lambda path: os.path.join("/nonexistent", path))
        plan = cohi_setup.make_plan(inst, fake_tree(), ["resampler"], ["smisdr_iq_universal"])
        self.assertEqual(sorted(plan.drivers), ["smisdr_iq_universal", "stemlab_universal"])
        self.assertIn("sources/dev_drivers/stemlab_universal/cohi_playrecworker.py", plan.download)
        self.assertIn("sources/dev_drivers/smisdr_common/live_worker.py", plan.download)
        self.assertIn("sources/dev_drivers/libs/libdspflmod.so", plan.download)      # its DSP library
        self.assertNotIn("sources/dev_drivers/fl2k_universal/SDR_control.py", plan.download)

    def test_deselecting_all_smisdr_drivers_removes_the_shared_code(self):
        inst = SimpleNamespace(installed_drivers=lambda: ["smisdr_iq"], installed_modules=lambda: [],
                               state={"files": {}}, p=lambda path: os.path.join("/nonexistent", path))
        plan = cohi_setup.make_plan(inst, fake_tree(), ["resampler"], ["stemlab_universal"])
        self.assertEqual(plan.remove_driver_dirs, ["smisdr_iq"])
        self.assertNotIn("sources/dev_drivers/smisdr_common/sinks.py", plan.download)

    def test_manifest_entries_are_complete(self):
        for name in ("smisdr_iq", "smisdr_raw", "smisdr_iq_universal", "smisdr_raw_universal"):
            spec = cohi_setup.driver_spec(name)
            for key in ("label", "group", "libs", "needs"):
                self.assertIn(key, spec, name)
            self.assertIn("sources/dev_drivers/smisdr_common/", spec["also_dirs"])
        self.assertEqual(cohi_setup.driver_spec("smisdr_iq_universal")["group"], "universal")
        # the unknown-driver fallback of older branches is unchanged
        self.assertEqual(cohi_setup.driver_spec("something_new")["group"], "other")

    def test_every_driver_directory_has_a_manifest_entry_and_vice_versa(self):
        drvdir = os.path.join(SOURCES, "dev_drivers")
        have = {d for d in os.listdir(drvdir) if d.startswith("smisdr_") and
                os.path.isfile(os.path.join(drvdir, d, "cohi_playrecworker.py"))}
        self.assertEqual(have, {"smisdr_iq", "smisdr_raw", "smisdr_iq_universal", "smisdr_raw_universal"})
        self.assertTrue(have <= set(cohi_setup.DRIVERS))


@unittest.skipUnless(shutil.which("make") and shutil.which("g++") and sys.platform.startswith("linux"),
                     "needs make and g++ on Linux")
class BuildToolTest(unittest.TestCase):
    def setUp(self):
        self.target = tempfile.mkdtemp(prefix="smisdr_inst_")
        self.addCleanup(shutil.rmtree, self.target, True)
        src = os.path.join(SOURCES, "dev_drivers", "smisdr_common", "upconverter")
        dst = os.path.join(self.target, UPDIR)
        shutil.copytree(src, dst)
        self.logs, self.manual, self.saved = [], [], []
        self.inst = SimpleNamespace(target=self.target, state={}, save_state=lambda: self.saved.append(1))
        self.fake = SimpleNamespace(
            dry_run=False, inst=self.inst, manual_steps=self.manual,
            ui=SimpleNamespace(log=self.logs.append), _build_tools=lambda rdir: True)
        self.tree = {UPDIR + "cohi_native_upconverter.cpp": ("sha-v1", 1, 0o100644)}
        self.plan = SimpleNamespace(drivers=["smisdr_raw"])

    def run_step(self, plan=None):
        cohi_setup.Installer.ensure_smisdr_tools(self.fake, plan or self.plan, self.tree)

    def test_built_once_and_again_after_a_source_update(self):
        binary = os.path.join(self.target, UPDIR, "cohi_native_upconverter")
        self.assertFalse(os.path.exists(binary))
        self.run_step()
        self.assertTrue(os.access(binary, os.X_OK), self.logs)
        self.assertEqual(self.manual, [])
        self.assertEqual(self.inst.state["built_tools"][UPDIR + "cohi_native_upconverter"], "sha-v1")
        self.logs.clear()
        self.run_step()
        self.assertTrue(any("up to date" in line for line in self.logs), self.logs)
        self.assertFalse(any("building" in line for line in self.logs))
        self.tree[UPDIR + "cohi_native_upconverter.cpp"] = ("sha-v2", 1, 0o100644)   # repository changed
        self.logs.clear()
        self.run_step()
        self.assertTrue(any("building" in line for line in self.logs), self.logs)
        self.assertEqual(self.inst.state["built_tools"][UPDIR + "cohi_native_upconverter"], "sha-v2")

    def test_nothing_happens_for_other_drivers_and_in_dry_run(self):
        self.run_step(SimpleNamespace(drivers=["smisdr_iq", "stemlab_universal"]))
        self.assertFalse(os.path.exists(os.path.join(self.target, UPDIR, "cohi_native_upconverter")))
        self.fake.dry_run = True
        self.run_step()
        self.assertFalse(os.path.exists(os.path.join(self.target, UPDIR, "cohi_native_upconverter")))

    def test_failed_build_gives_a_manual_step(self):
        with open(os.path.join(self.target, UPDIR, "cohi_native_upconverter.cpp"), "w") as fh:
            fh.write("this is not C++\n")
        self.run_step()
        self.assertEqual(len(self.manual), 1)
        self.assertIn("make", self.manual[0])
        self.assertNotIn(UPDIR + "cohi_native_upconverter", self.inst.state.get("built_tools", {}))

    def test_missing_build_tools_give_a_manual_step(self):
        self.fake._build_tools = lambda rdir: False
        self.run_step()
        self.assertEqual(len(self.manual), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
