#!/usr/bin/env python3
"""
Unattended end-to-end checks for the wake pipeline. No room microphone needed.

Modes:
  dry-run    Check the harness itself: scripts present, fixture wav readable.
  hey-alone  Replay a wav through the real wake_listener.py (--input-wav hook)
             and check the events it writes.

Evidence: logs/e2e/<timestamp>/report.json (+ listener stdout/stderr, events).
Exit codes: 0 pass, 1 fail, 2 setup problem / skipped.

Usage:
  python -u scripts/e2e_unattended.py --mode dry-run
  python -u scripts/e2e_unattended.py --mode hey-alone
  python -u scripts/e2e_unattended.py --mode hey-alone --input-wav real.wav --expect-wake
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import math
import platform
import struct
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTENER = ROOT / "scripts" / "wake_listener.py"
EVENTS_LOG = ROOT / "logs" / "events.jsonl"
FIXTURE = ROOT / "tests" / "e2e_fixtures" / "hey_alone_placeholder.wav"
PACKAGES = ("numpy", "sounddevice", "openwakeword", "onnxruntime", "requests")
SAMPLE_RATE = 16000


def write_placeholder_wav(path: Path) -> None:
    """1 s silence, 0.5 s 440 Hz tone, 1 s silence: valid input that should not wake."""
    samples = [0] * SAMPLE_RATE
    samples += [int(8000 * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE)) for i in range(SAMPLE_RATE // 2)]
    samples += [0] * SAMPLE_RATE
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def wav_samples(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError("need 16 kHz mono 16-bit")
        return w.getnframes()


def versions() -> dict:
    out = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def oww_feature_models_present() -> bool:
    spec = importlib.util.find_spec("openwakeword")
    if spec is None or spec.origin is None:
        return False
    return (Path(spec.origin).parent / "resources" / "models" / "melspectrogram.onnx").is_file()


class Report:
    def __init__(self, mode: str, evidence: Path):
        self.mode = mode
        self.evidence = evidence
        self.checks: list[dict] = []
        self.note: str | None = None

    def check(self, name: str, ok: bool, detail: object = None) -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail is not None else ""), flush=True)
        return ok

    def finish(self, exit_code: int) -> int:
        report = {
            "mode": self.mode,
            "passed": exit_code == 0,
            "exit_code": exit_code,
            "note": self.note,
            "checks": self.checks,
            "host": {"node": platform.node(), "platform": platform.platform(), "machine": platform.machine()},
            "versions": versions(),
            "finished": datetime.now(timezone.utc).isoformat(),
        }
        (self.evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"evidence: {self.evidence}", flush=True)
        return exit_code


def fixture_check(report: Report, wav: Path) -> int | None:
    """Sample count if the wav is usable, else None (check recorded)."""
    if wav == FIXTURE and not wav.is_file():
        write_placeholder_wav(wav)
    try:
        n = wav_samples(wav)
    except (OSError, ValueError, wave.Error) as exc:
        report.check("fixture_wav_valid", False, f"{wav}: {exc}")
        return None
    report.check("fixture_wav_valid", n > 0, f"{wav} samples={n}")
    return n if n > 0 else None


def dry_run(report: Report, wav: Path) -> int:
    ok = report.check("listener_script_present", LISTENER.is_file(), str(LISTENER))
    ok = fixture_check(report, wav) is not None and ok
    return 0 if ok else 1


def hey_alone(report: Report, wav: Path, expect_wake: bool, timeout: float) -> int:
    samples = fixture_check(report, wav)
    if samples is None:
        return 2
    missing = [p for p in PACKAGES if importlib.util.find_spec(p) is None]
    if missing:
        report.note = f"missing packages: {missing}; run: uv pip install -r requirements.txt"
        return 2
    if not oww_feature_models_present():
        report.note = (
            "openWakeWord feature models missing; run: "
            'python -c "import openwakeword.utils as u; u.download_models([\'__none__\'])"'
        )
        return 2

    start_offset = EVENTS_LOG.stat().st_size if EVENTS_LOG.is_file() else 0
    command = [sys.executable, "-u", str(LISTENER), "--quiet", "--input-wav", str(wav)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    except subprocess.TimeoutExpired:
        report.check("listener_exited", False, f"timeout after {timeout}s")
        return 1
    (report.evidence / "listener_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (report.evidence / "listener_stderr.txt").write_text(result.stderr, encoding="utf-8")

    # ponytail: slices the shared events log by offset; a live listener writing concurrently would interleave.
    new_events = []
    if EVENTS_LOG.is_file():
        with EVENTS_LOG.open("rb") as f:
            f.seek(start_offset)
            raw = f.read().decode("utf-8")
        (report.evidence / "events.jsonl").write_text(raw, encoding="utf-8")
        new_events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    kinds = [e.get("kind") for e in new_events]
    done = next((e for e in new_events if e.get("kind") == "input_wav_done"), None)
    wakes = [e for e in new_events if e.get("kind") == "wake"]

    ok = report.check("listener_exit_zero", result.returncode == 0, f"exit={result.returncode}")
    ok = report.check("listener_start_event", "listener_start" in kinds) and ok
    ok = report.check("input_wav_fully_replayed", bool(done) and done.get("samples") == samples,
                      f"expected={samples} got={done and done.get('samples')}") and ok
    ok = report.check("wake_matches_expectation", bool(wakes) == expect_wake,
                      f"expect_wake={expect_wake} wakes={[w.get('score') for w in wakes]}") and ok
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Unattended wake-pipeline e2e harness")
    p.add_argument("--mode", required=True, choices=["dry-run", "hey-alone"])
    p.add_argument("--input-wav", type=Path, default=FIXTURE, help="16 kHz mono 16-bit wav to replay")
    p.add_argument("--expect-wake", action="store_true", help="Fixture contains a real 'hey computer'")
    p.add_argument("--timeout", type=float, default=180.0, help="Listener timeout in seconds")
    p.add_argument("--evidence-root", type=Path, default=ROOT / "logs" / "e2e")
    args = p.parse_args()

    evidence = args.evidence_root / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    evidence.mkdir(parents=True, exist_ok=True)
    report = Report(args.mode, evidence)
    if args.mode == "dry-run":
        return report.finish(dry_run(report, args.input_wav))
    return report.finish(hey_alone(report, args.input_wav, args.expect_wake, args.timeout))


if __name__ == "__main__":
    sys.exit(main())
