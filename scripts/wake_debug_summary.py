"""Attempt grouping and threshold guidance for wake_debug.py."""

from __future__ import annotations


class AttemptTracker:
    def __init__(self, candidate_score: float = 0.05, settle_seconds: float = 1.0) -> None:
        self.candidate_score = candidate_score
        self.settle_seconds = settle_seconds
        self._active = False
        self._last_candidate_at = 0.0
        self._peak_at = 0.0
        self._peak_score = 0.0
        self._attempts: list[tuple[float, float]] = []

    def observe(self, now: float, score: float) -> None:
        if self._active and now - self._last_candidate_at >= self.settle_seconds:
            self._attempts.append((self._peak_at, self._peak_score))
            self._active = False
        if score < self.candidate_score:
            return
        if not self._active:
            self._active = True
            self._peak_at = now
            self._peak_score = score
        elif score > self._peak_score:
            self._peak_at = now
            self._peak_score = score
        self._last_candidate_at = now

    def finish(self, now: float) -> list[tuple[float, float]]:
        # A timed debug session can end before its final pause.  Its last
        # spoken attempt is still useful calibration data, so flush it here.
        if self._active:
            self._attempts.append((self._peak_at, self._peak_score))
            self._active = False
        return list(self._attempts)


def recommend_threshold(peaks: list[float]) -> float | None:
    if not peaks:
        return None
    return round(max(0.05, min(peaks) * 0.8), 2)
