#!/usr/bin/env python3
"""
Live "hey computer" debug monitor.

Shows continuously:
  - Mic peak level (are we hearing the room?)
  - openWakeWord score for hey_computer (0.00–1.00)
  - Whether score is above threshold (WOULD WAKE)
  - Explicit WAKE events with timestamp + score

Does NOT open Grok or fire TTS unless --activate is passed.

Usage:
  python -u wake_debug.py
  python -u wake_debug.py --threshold 0.4
  python -u wake_debug.py --list-devices
  python -u wake_debug.py --seconds 30        # auto-exit
  python -u wake_debug.py --csv debug.csv     # also write samples

Stop with Ctrl+C.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("Missing sounddevice. pip install --user sounddevice", file=sys.stderr)
    sys.exit(1)

try:
    from openwakeword.model import Model
except ImportError:
    print("Missing openwakeword. pip install --user openwakeword onnxruntime", file=sys.stderr)
    sys.exit(1)

# Reuse model path helpers from wake_listener
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from wake_listener import (  # noqa: E402
    FRAME_SAMPLES,
    HEY_COMPUTER,
    SAMPLE_RATE,
    activate_grok,
    build_model,
    ensure_model,
    list_devices,
    speak,
)
from wake_debug_summary import AttemptTracker, recommend_threshold  # noqa: E402

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
EVENTS = LOG_DIR / "events.jsonl"


def emit_event(kind: str, **fields) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        **fields,
    }
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def bar(score: float, width: int = 40) -> str:
    score = max(0.0, min(1.0, score))
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)


def mic_bar(peak: float, width: int = 20) -> str:
    # peak is 0..1 float abs
    x = max(0.0, min(1.0, peak * 4.0))  # amplify quiet mics a bit for display
    filled = int(round(x * width))
    return "▓" * filled + "·" * (width - filled)


def run(
    threshold: float,
    device: int | None,
    seconds: float | None,
    csv_path: Path | None,
    activate: bool,
    announce: bool,
    sample_hz: float,
) -> None:
    model_path = ensure_model()
    print(f"Model:      {model_path}")
    print(f"Threshold:  {threshold:.2f}  (score ≥ this → WAKE)")
    print(f"Device:     {device if device is not None else 'default'}")
    print(f"Activate:   {activate}  (open Grok on wake)")
    print(f"Events log: {EVENTS}")
    print("Say each phrase once, then pause 2 seconds between attempts.")
    print("Legend: mic peak | score bar | score | status")
    print("-" * 72, flush=True)

    oww = build_model(model_path)
    oww.predict(np.zeros(FRAME_SAMPLES, dtype=np.int16))

    emit_event(
        "debug_start",
        threshold=threshold,
        device=device,
        model=str(model_path),
        activate=activate,
    )

    csv_writer = None
    csv_file = None
    if csv_path:
        csv_file = csv_path.open("w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["iso_time", "score", "peak", "above_threshold", "woke"])

    state = {
        "buf": np.array([], dtype=np.int16),
        "score": 0.0,
        "peak": 0.0,
        "last_ui": 0.0,
        "last_wake": 0.0,
        "frames": 0,
        "max_score": 0.0,
        "wakes": 0,
        "attempts": AttemptTracker(),
    }
    ui_interval = 1.0 / max(sample_hz, 0.5)
    t0 = time.time()

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        if status:
            print(f"\n[audio] {status}", file=sys.stderr, flush=True)
        audio = indata[:, 0] if indata.ndim > 1 else indata
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        state["peak"] = max(state["peak"] * 0.85, peak)  # slow decay for readability
        pcm = (audio * 32767).astype(np.int16)
        state["buf"] = np.concatenate([state["buf"], pcm])
        while len(state["buf"]) >= FRAME_SAMPLES:
            chunk = state["buf"][:FRAME_SAMPLES]
            state["buf"] = state["buf"][FRAME_SAMPLES:]
            scores = oww.predict(chunk)
            score = 0.0
            for _n, v in scores.items():
                score = max(score, float(v))
            state["score"] = score
            state["frames"] += 1
            if score > state["max_score"]:
                state["max_score"] = score

            now = time.time()
            state["attempts"].observe(now, score)
            above = score >= threshold
            woke = False
            if above and (now - state["last_wake"]) >= 2.0:
                state["last_wake"] = now
                state["wakes"] += 1
                woke = True
                ts = time.strftime("%H:%M:%S")
                print(
                    f"\n*** [{ts}] HEARD «hey computer»  score={score:.3f}  "
                    f"(threshold {threshold:.2f}) ***",
                    flush=True,
                )
                emit_event("wake", score=round(score, 4), threshold=threshold, activate=activate)
                if announce:
                    speak(f"Heard you. Score {score:.2f}.")
                if activate:
                    activate_grok()

            if csv_writer and (woke or state["frames"] % 5 == 0):
                csv_writer.writerow(
                    [
                        datetime.now(timezone.utc).isoformat(),
                        f"{score:.4f}",
                        f"{peak:.4f}",
                        int(above),
                        int(woke),
                    ]
                )

        now = time.time()
        if now - state["last_ui"] >= ui_interval:
            state["last_ui"] = now
            s = state["score"]
            p = state["peak"]
            status = "WOULD WAKE" if s >= threshold else "listening"
            line = (
                f"\r mic {mic_bar(p)} {p:5.3f} │ "
                f"{bar(s)} {s:5.3f} │ {status:<10} │ "
                f"max={state['max_score']:.3f} wakes={state['wakes']}   "
            )
            sys.stdout.write(line)
            sys.stdout.flush()

    kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": 1,
        "dtype": "float32",
        "blocksize": FRAME_SAMPLES,
        "callback": callback,
    }
    if device is not None:
        kwargs["device"] = device

    try:
        with sd.InputStream(**kwargs):
            if seconds is None:
                while True:
                    time.sleep(0.2)
            else:
                while time.time() - t0 < seconds:
                    time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopped by user.", flush=True)
    finally:
        if csv_file:
            csv_file.close()
        attempts = state["attempts"].finish(time.time())
        attempt_peaks = [score for _at, score in attempts]
        suggested = recommend_threshold(attempt_peaks)
        emit_event(
            "debug_stop",
            frames=state["frames"],
            max_score=round(state["max_score"], 4),
            wakes=state["wakes"],
            elapsed_s=round(time.time() - t0, 1),
        )
        if attempts:
            emit_event(
                "debug_attempts",
                attempts=[
                    {"time": datetime.fromtimestamp(at).astimezone().isoformat(), "peak": round(score, 4)}
                    for at, score in attempts
                ],
                recommended_threshold=suggested,
            )
        print(
            f"\nSummary: frames={state['frames']}  max_score={state['max_score']:.3f}  "
            f"wakes={state['wakes']}  threshold={threshold}",
            flush=True,
        )
        if attempts:
            print("Attempt peaks (speak one phrase, then pause 2 seconds):", flush=True)
            for at, score in attempts:
                verdict = "would wake" if score >= threshold else "below threshold"
                stamp = datetime.fromtimestamp(at).strftime("%H:%M:%S")
                print(f"  {stamp}  peak={score:.3f}  {verdict}", flush=True)
            print(
                f"Suggested threshold for these attempts: {suggested:.2f} "
                "(verify false-wake behavior before changing the production listener).",
                flush=True,
            )
        if state["wakes"] == 0:
            print(
                "No wake detected. Tips:\n"
                "  • Speak clearly: «hey computer»\n"
                "  • Check mic: peak should jump when you talk (try --list-devices)\n"
                "  • Lower threshold: --threshold 0.35\n"
                "  • Move closer / raise Windows mic level",
                flush=True,
            )
        else:
            print(f"Success: wake word heard {state['wakes']} time(s).", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Debug monitor for hey computer wake word")
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--device", type=int, default=None)
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--seconds", type=float, default=None, help="Auto-exit after N seconds")
    p.add_argument("--csv", type=Path, default=None, help="Write per-frame CSV")
    p.add_argument("--activate", action="store_true", help="Also open Grok on wake")
    p.add_argument("--quiet", action="store_true", help="No TTS on wake")
    p.add_argument("--hz", type=float, default=8.0, help="UI refresh rate")
    args = p.parse_args()

    if args.list_devices:
        list_devices()
        return

    if not HEY_COMPUTER.is_file():
        ensure_model()

    run(
        threshold=args.threshold,
        device=args.device,
        seconds=args.seconds,
        csv_path=args.csv,
        activate=args.activate,
        announce=not args.quiet,
        sample_hz=args.hz,
    )


if __name__ == "__main__":
    main()
