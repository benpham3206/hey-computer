import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

with patch.dict(sys.modules, {"requests": sys.modules.get("requests") or types.ModuleType("requests")}):
    speak_xai = importlib.import_module("speak_xai")


class PlayMp3Tests(unittest.TestCase):
    def play(self, platform):
        with patch.object(speak_xai.sys, "platform", platform), patch.object(speak_xai.subprocess, "run") as run:
            run.return_value = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            speak_xai.play_mp3(Path("/tmp/clip.mp3"))
        return run.call_args

    def test_macos_plays_through_afplay_and_fails_loud(self):
        call = self.play("darwin")
        self.assertEqual(["afplay", str(Path("/tmp/clip.mp3").resolve())], call.args[0])
        self.assertTrue(call.kwargs["check"])

    def test_windows_keeps_powershell_media_player(self):
        call = self.play("win32")
        self.assertEqual("powershell", call.args[0][0])
        self.assertIn("MediaPlayer", call.args[0][-1])


if __name__ == "__main__":
    unittest.main()
