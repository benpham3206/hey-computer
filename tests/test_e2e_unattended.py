import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "scripts" / "e2e_unattended.py"


class E2EHarnessTests(unittest.TestCase):
    def run_harness(self, *args):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(HARNESS), "--evidence-root", temp, *args],
                capture_output=True,
                text=True,
                timeout=60,
            )
            reports = list(Path(temp).glob("*/report.json"))
            self.assertEqual(1, len(reports), result.stdout + result.stderr)
            return result.returncode, json.loads(reports[0].read_text())

    def test_dry_run_passes_and_writes_report(self):
        code, report = self.run_harness("--mode", "dry-run")
        self.assertEqual(0, code)
        self.assertEqual("dry-run", report["mode"])
        self.assertTrue(report["passed"])
        self.assertIn("python", report["versions"])
        self.assertIn("platform", report["host"])

    def test_unreadable_wav_fails_dry_run(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as bad:
            bad.write(b"not a wav")
            bad.flush()
            code, report = self.run_harness("--mode", "dry-run", "--input-wav", bad.name)
        self.assertEqual(1, code)
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
