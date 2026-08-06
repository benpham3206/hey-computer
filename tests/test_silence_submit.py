import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from silence_submit import SilenceSubmitState  # noqa: E402


class SilenceSubmitStateTests(unittest.TestCase):
    def make_state(self):
        return SilenceSubmitState(
            speech_rms=0.025,
            silence_rms=0.015,
            silence_seconds=2.0,
            timeout_seconds=60.0,
            grace_seconds=1.0,
        )

    def test_silence_before_speech_never_submits(self):
        state = self.make_state()
        state.start(10.0)
        self.assertIsNone(state.update(11.1, 0.0))
        self.assertIsNone(state.update(20.0, 0.0))

    def test_short_pause_after_speech_does_not_submit(self):
        state = self.make_state()
        state.start(10.0)
        self.assertEqual("speech_started", state.update(11.1, 0.04))
        self.assertIsNone(state.update(12.0, 0.0))
        self.assertIsNone(state.update(13.9, 0.0))

    def test_two_seconds_of_silence_after_speech_submits_once(self):
        state = self.make_state()
        state.start(10.0)
        self.assertEqual("speech_started", state.update(11.1, 0.04))
        self.assertIsNone(state.update(12.0, 0.0))
        self.assertEqual("submit", state.update(14.0, 0.0))
        self.assertIsNone(state.update(15.0, 0.0))

    def test_speech_resets_the_silence_timer(self):
        state = self.make_state()
        state.start(10.0)
        state.update(11.1, 0.04)
        state.update(12.0, 0.0)
        self.assertIsNone(state.update(13.5, 0.04))
        self.assertIsNone(state.update(14.0, 0.0))
        self.assertEqual("submit", state.update(16.0, 0.0))

    def test_timeout_disarms_without_submitting(self):
        state = self.make_state()
        state.start(10.0)
        self.assertEqual("timeout", state.update(70.0, 0.04))
        self.assertIsNone(state.update(71.0, 0.0))


if __name__ == "__main__":
    unittest.main()
