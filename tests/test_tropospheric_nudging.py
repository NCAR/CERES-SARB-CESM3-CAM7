"""Compile the actual kernel and optics adapter to verify tropospheric state updates."""
from pathlib import Path
import importlib.util
import subprocess

import numpy as np
import yaml
from davinci_monet.config.parser import load_config
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]

class TroposphericNudgingTests(unittest.TestCase):
    def test_compiled_state_update(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "tropospheric_nudging"
            subprocess.run(["gfortran", "-std=f2008", "-fcheck=all", "-fbacktrace", "-o", str(exe),
                            str(REPO / "tests/fortran/cam_nudging_fixture.F90"),
                            str(REPO / "src/cam/aod_nudging_kernel.F90"),
                            str(REPO / "src/cam/aod_nudging_optics.F90"),
                            str(REPO / "tests/fortran/test_tropospheric_nudging.F90")], cwd=temp, check=True)
            subprocess.run([str(exe)], check=True)

    def test_numeric_gate_catches_protected_increment(self):
        spec = importlib.util.spec_from_file_location("verify_tropo", REPO / "scripts/verify_tropospheric_july2008.py")
        verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier)
        before = np.ones((1, 4, 2, 2))
        ratio = np.full((1, 2, 2), 2.)
        mask = np.zeros(before.shape, dtype=bool)
        mask[:, 2:] = True
        after = before*np.where(mask, ratio[:, None], 1.)
        self.assertEqual(verifier.check_profiles(before, after, ratio, mask, True), 0.)
        after[0, 1, 0, 0] += .1
        with self.assertRaises(ValueError):
            verifier.check_profiles(before, after, ratio, mask, True)
        self.assertEqual(verifier.check_profiles(before, 2*before, ratio, mask, False), 1.)

    def test_native_davinci_config_and_profile_semantics(self):
        path = REPO / "analyses/davinci/tropospheric-july2008-v1.yaml"
        load_config(path)
        config = yaml.safe_load(path.read_text())
        self.assertEqual(config["analysis"]["end_time"], "2008-07-31T23:59:59")
        self.assertEqual(len(config["plots"]), 10)
        self.assertEqual(sum(p["type"] == "vertical_profile" for p in config["plots"].values()), 7)
        self.assertFalse(config["sources"]["profiles"]["standardize"])
        for plot in config["plots"].values():
            self.assertEqual(plot["formats"], ["pdf"])
            if plot["type"] == "vertical_profile":
                self.assertEqual(plot["alt_coord"], "altitude")
        self.assertTrue(config["plots"]["tropospheric_minus_column_aod"]["symmetric"])
        self.assertTrue(config["plots"]["tropospheric_minus_column_aod"]["robust"])

if __name__ == "__main__":
    unittest.main()
