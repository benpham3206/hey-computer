import contextlib
import importlib
import io
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

sounddevice = types.ModuleType("sounddevice")
sounddevice.query_devices = lambda: []
sounddevice.default = SimpleNamespace(device=None)

openwakeword = types.ModuleType("openwakeword")
openwakeword.__path__ = []
model_module = types.ModuleType("openwakeword.model")
model_module.Model = object
openwakeword.model = model_module

speak_xai = types.ModuleType("speak_xai")
speak_xai.play_mp3 = lambda _path: None

with patch.dict(
    sys.modules,
    {
        "sounddevice": sounddevice,
        "openwakeword": openwakeword,
        "openwakeword.model": model_module,
        "speak_xai": speak_xai,
    },
):
    listener = importlib.import_module("wake_listener")


class StopLoop(Exception):
    pass


class ImmediateThread:
    def __init__(self, target, args=(), daemon=False):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class WakeModel:
    def __init__(self, wake_calls):
        self.calls = 0
        self.wake_calls = set(wake_calls)

    def predict(self, _chunk):
        self.calls += 1
        return {"hey_computer": 0.9 if self.calls in self.wake_calls else 0.0}


class AudioFrames:
    def __init__(self, callback, frames, **_kwargs):
        self.callback = callback
        self.frames = frames

    def __enter__(self):
        for value in self.frames:
            self.callback(np.full(1280, value, dtype=np.float32), 1280, None, None)
        return self

    def __exit__(self, *_args):
        return False


class WakeListenerActivationTests(unittest.TestCase):
    def replay(
        self,
        activation_outputs,
        frames=(0.0, 0.04, 0.0, 0.0),
        tick_values=(100.0, 100.1, 101.2, 102.0, 104.1),
        wake_calls=(2,),
    ):
        ticks = iter(tick_values)
        listener.time = SimpleNamespace(
            time=lambda: next(ticks),
            strftime=time.strftime,
            sleep=lambda _seconds: (_ for _ in ()).throw(StopLoop()),
        )
        listener.threading = SimpleNamespace(Thread=ImmediateThread)
        listener.ensure_model = lambda: SCRIPTS.parent / "models" / "hey_computer.onnx"
        listener.build_model = lambda _path: WakeModel(wake_calls)
        listener.emit_event = lambda *_args, **_kwargs: None
        listener.speak = lambda _text: None
        sounddevice.InputStream = lambda callback, **kwargs: AudioFrames(callback, frames, **kwargs)

        commands = []
        responses = iter(activation_outputs)

        def fake_run(command, **_kwargs):
            command = list(command)
            commands.append(command)
            if str(listener.ACTIVATE_PS1) in command:
                return SimpleNamespace(returncode=3, stdout=next(responses), stderr="")
            if str(listener.SUBMIT_PS1) in command:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            raise AssertionError(f"unexpected subprocess command: {command!r}")

        listener.subprocess = SimpleNamespace(run=fake_run)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                listener.run(threshold=0.4, cooldown=4.0, device=None, announce=False)
            except StopLoop:
                pass

        return [command for command in commands if str(listener.SUBMIT_PS1) in command]

    def test_missing_window_handle_never_submits(self):
        submissions = self.replay(["WARN: launched=True could not foreground hwnd=0"])
        self.assertEqual([], submissions)

    def test_activated_window_handle_is_passed_to_submit(self):
        submissions = self.replay(["Focused hwnd=42 ok=True launched=True"])
        self.assertEqual(1, len(submissions))
        self.assertEqual(["-ExpectedHwnd", "42"], submissions[0][-2:])

    def test_failed_activation_releases_listener_for_the_next_wake(self):
        submissions = self.replay(
            [
                "WARN: launched=True could not foreground hwnd=0",
                "Focused hwnd=42 ok=True launched=True",
            ],
            frames=(0.0, 0.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0),
            tick_values=(100.0, 100.1, 101.2, 102.0, 104.1, 105.0, 106.2, 107.0, 109.1),
            wake_calls=(2, 6),
        )
        self.assertEqual(1, len(submissions))
        self.assertEqual(["-ExpectedHwnd", "42"], submissions[0][-2:])


if __name__ == "__main__":
    unittest.main()
