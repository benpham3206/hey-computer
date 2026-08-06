"""Deterministic speech/silence state for wake-triggered prompt submission."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SilenceSubmitState:
    speech_rms: float = 0.025
    silence_rms: float = 0.015
    silence_seconds: float = 2.0
    timeout_seconds: float = 60.0
    grace_seconds: float = 1.0

    def __post_init__(self) -> None:
        self.armed = False
        self.started_at = 0.0
        self.speech_seen = False
        self.silence_started_at: float | None = None

    def start(self, now: float) -> None:
        self.armed = True
        self.started_at = now
        self.speech_seen = False
        self.silence_started_at = None

    def update(self, now: float, rms: float) -> str | None:
        if not self.armed:
            return None
        if now - self.started_at >= self.timeout_seconds:
            self.armed = False
            return "timeout"
        if now - self.started_at < self.grace_seconds:
            return None

        if rms >= self.speech_rms:
            first_speech = not self.speech_seen
            self.speech_seen = True
            self.silence_started_at = None
            return "speech_started" if first_speech else None

        if not self.speech_seen or rms > self.silence_rms:
            return None
        if self.silence_started_at is None:
            self.silence_started_at = now
            return None
        if now - self.silence_started_at >= self.silence_seconds:
            self.armed = False
            return "submit"
        return None
