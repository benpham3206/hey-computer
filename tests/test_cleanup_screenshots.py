import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup_cua_screenshots.ps1"


class CleanupScreenshotsTests(unittest.TestCase):
    def run_script(self, root: Path, apply: bool = False):
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-Root",
            str(root),
            "-Days",
            "7",
        ]
        if apply:
            args.append("-Apply")
        return subprocess.run(args, capture_output=True, text=True, timeout=15)

    def test_apply_removes_only_old_images_inside_screenshots_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "screenshots"
            root.mkdir()
            old_png = root / "old.png"
            recent_png = root / "recent.png"
            old_txt = root / "old.txt"
            for path in (old_png, recent_png, old_txt):
                path.write_text("x", encoding="utf-8")
            old = time.time() - 8 * 86400
            os.utime(old_png, (old, old))
            os.utime(old_txt, (old, old))

            result = self.run_script(root, apply=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse(old_png.exists())
            self.assertTrue(recent_png.exists())
            self.assertTrue(old_txt.exists())
            self.assertEqual(1, json.loads(result.stdout)["deleted"])

    def test_dry_run_reports_without_deleting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "screenshots"
            root.mkdir()
            old_jpg = root / "old.jpg"
            old_jpg.write_text("x", encoding="utf-8")
            old = time.time() - 8 * 86400
            os.utime(old_jpg, (old, old))

            result = self.run_script(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(old_jpg.exists())
            payload = json.loads(result.stdout)
            self.assertEqual(1, payload["matched"])
            self.assertEqual(0, payload["deleted"])

    def test_rejects_root_not_named_screenshots(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_script(Path(temp))
            self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
