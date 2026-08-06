import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from wake_debug_summary import AttemptTracker, recommend_threshold  # noqa: E402


class WakeDebugSummaryTests(unittest.TestCase):
    def test_tracks_separate_score_bursts(self):
        tracker = AttemptTracker(candidate_score=0.05, settle_seconds=1.0)
        tracker.observe(1.0, 0.08)
        tracker.observe(1.2, 0.31)
        tracker.observe(2.3, 0.01)
        tracker.observe(4.0, 0.06)
        tracker.observe(4.2, 0.42)
        tracker.observe(5.3, 0.01)
        self.assertEqual([(1.2, 0.31), (4.2, 0.42)], tracker.finish(6.5))

    def test_ignores_scores_below_candidate_floor(self):
        tracker = AttemptTracker(candidate_score=0.05, settle_seconds=1.0)
        tracker.observe(1.0, 0.049)
        self.assertEqual([], tracker.finish(3.0))

    def test_finish_flushes_latest_attempt_without_waiting_for_settle_delay(self):
        tracker = AttemptTracker(candidate_score=0.05, settle_seconds=1.0)
        tracker.observe(1.0, 0.24)
        self.assertEqual([(1.0, 0.24)], tracker.finish(1.1))

    def test_recommendation_uses_eighty_percent_of_lowest_attempt(self):
        self.assertEqual(0.25, recommend_threshold([0.31, 0.42]))

    def test_recommendation_is_none_without_attempts(self):
        self.assertIsNone(recommend_threshold([]))


if __name__ == "__main__":
    unittest.main()
