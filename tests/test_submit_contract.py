import json
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "submit_grok_voice.ps1"


class SubmitGrokVoiceContractTests(unittest.TestCase):
    def run_script(self, title: str = "", expected_hwnd: int = 0, foreground_hwnd: int = 0):
        args = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-DryRun",
                "-ForegroundTitle",
                title,
            ]
        if expected_hwnd:
            args.extend(["-ExpectedHwnd", str(expected_hwnd)])
        if foreground_hwnd:
            args.extend(["-ForegroundHwnd", str(foreground_hwnd)])
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_grok_foreground_would_stop_and_submit(self):
        result = self.run_script("Grok Build")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"eligible": True, "actions": ["ctrl+space", "enter"]},
            json.loads(result.stdout),
        )

    def test_non_grok_foreground_refuses_submission(self):
        result = self.run_script("ChatGPT")
        self.assertEqual(3, result.returncode)
        self.assertEqual(
            {"eligible": False, "actions": []},
            json.loads(result.stdout),
        )

    def test_exact_expected_window_is_eligible_regardless_of_title(self):
        result = self.run_script("Terminal", expected_hwnd=1234, foreground_hwnd=1234)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["eligible"])

    def test_different_foreground_window_refuses_expected_window(self):
        result = self.run_script("Grok Build", expected_hwnd=1234, foreground_hwnd=5678)
        self.assertEqual(3, result.returncode)
        self.assertFalse(json.loads(result.stdout)["eligible"])


if __name__ == "__main__":
    unittest.main()
