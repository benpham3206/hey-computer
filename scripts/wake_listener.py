#!/usr/bin/env python3
"""
Always-on "hey computer" wake-word listener for Grok Build (Windows).

On detection:
  1. Optional short chime / TTS "Listening"
  2. Launch or focus Grok Build window
  3. Send Ctrl+Space to start Grok voice dictation

Usage:
  python wake_listener.py
  python wake_listener.py --threshold 0.5 --cooldown 4
  python wake_listener.py --list-devices
  python wake_listener.py --input-wav clip.wav   # test hook: replay a wav, no mic
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

from ack_cache import ensure_ack_cache
from silence_submit import SilenceSubmitState
from speak_xai import play_mp3

try:
    import sounddevice as sd
except ImportError:
    print("Missing sounddevice. Run: python -m pip install --user sounddevice", file=sys.stderr)
    sys.exit(1)

try:
    from openwakeword.model import Model
except ImportError:
    print("Missing openwakeword. Run: python -m pip install --user openwakeword onnxruntime", file=sys.stderr)
    sys.exit(1)

SKILL_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = SKILL_DIR / "models"
SCRIPTS_DIR = Path(__file__).resolve().parent
LOG_DIR = SKILL_DIR / "logs"
EVENTS_LOG = LOG_DIR / "events.jsonl"
ACTIVATE_PS1 = SCRIPTS_DIR / "activate_grok.ps1"
SUBMIT_PS1 = SCRIPTS_DIR / "submit_grok_voice.ps1"
SPEAK_XAI = SCRIPTS_DIR / "speak_xai.py"
SPEAK_PS1 = SCRIPTS_DIR / "speak.ps1"
HEY_COMPUTER = MODELS_DIR / "hey_computer.onnx"
LISTENING_MP3 = LOG_DIR / "listening.mp3"

SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280  # 80 ms @ 16 kHz — openWakeWord default chunk


def emit_event(kind: str, **fields) -> None:
    """Append one JSONL event for debugging/monitoring (never secrets)."""
    try:
        import json
        from datetime import datetime, timezone

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
        with EVENTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def list_devices() -> None:
    print(sd.query_devices())
    print("\nDefault input:", sd.default.device)


def ensure_model() -> Path:
    if HEY_COMPUTER.is_file() and HEY_COMPUTER.stat().st_size > 10_000:
        return HEY_COMPUTER
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        "https://huggingface.co/Soulcreek2/speechkit-wakeword-models"
        "/resolve/main/hey_computer.onnx"
    )
    print(f"Downloading hey_computer model → {HEY_COMPUTER}")
    try:
        import urllib.request

        urllib.request.urlretrieve(url, HEY_COMPUTER)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)
    if not HEY_COMPUTER.is_file() or HEY_COMPUTER.stat().st_size < 10_000:
        print("Model file missing or too small after download.", file=sys.stderr)
        sys.exit(1)
    return HEY_COMPUTER


def speak(text: str) -> None:
    """Prefer xAI Carina via Grok OAuth; fall back to SAPI speak.ps1."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        if SPEAK_XAI.is_file():
            subprocess.Popen(
                [sys.executable, "-u", str(SPEAK_XAI), "--text", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            return
        if SPEAK_PS1.is_file():
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SPEAK_PS1),
                    "-Text",
                    text,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
    except Exception:
        pass


def activate_grok() -> int | None:
    if not ACTIVATE_PS1.is_file():
        print(f"Missing {ACTIVATE_PS1}", file=sys.stderr)
        return None
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ACTIVATE_PS1),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=flags,
        )
        if r.stdout.strip():
            print(r.stdout.strip())
        if r.returncode not in (0, 2):
            print(f"activate_grok exit {r.returncode}: {r.stderr.strip()}", file=sys.stderr)
        match = re.search(r"Focused hwnd=(\d+)", r.stdout)
        return int(match.group(1)) if match else None
    except subprocess.TimeoutExpired:
        print("activate_grok timed out", file=sys.stderr)
    except Exception as e:
        print(f"activate_grok failed: {e}", file=sys.stderr)
    return None


def generate_listening_audio(path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-u",
            str(SPEAK_XAI),
            "--text",
            "Listening.",
            "--out",
            str(path),
            "--no-play",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def submit_grok(expected_hwnd: int | None) -> bool:
    if not SUBMIT_PS1.is_file():
        emit_event("auto_submit_refused", reason="missing_script")
        return False
    command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SUBMIT_PS1),
        ]
    if expected_hwnd:
        command.extend(["-ExpectedHwnd", str(expected_hwnd)])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    emit_event(
        "auto_submit" if result.returncode == 0 else "auto_submit_refused",
        exit_code=result.returncode,
    )
    return result.returncode == 0


def read_wav(path: Path) -> np.ndarray:
    """Load a 16 kHz mono 16-bit wav as float32 [-1, 1], the InputStream sample format."""
    with wave.open(str(path), "rb") as w:
        shape = (w.getframerate(), w.getnchannels(), w.getsampwidth())
        if shape != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path}: need {SAMPLE_RATE} Hz mono 16-bit wav, got rate/channels/width={shape}")
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32767.0


def build_model(model_path: Path) -> Model:
    # Custom ONNX; openWakeWord uses its own feature models from package cache.
    return Model(
        wakeword_models=[str(model_path)],
        inference_framework="onnx",
    )


def run(
    threshold: float,
    cooldown: float,
    device: int | None,
    announce: bool,
    input_wav: Path | None = None,
) -> None:
    model_path = ensure_model()
    def log(msg: str) -> None:
        print(msg, flush=True)

    log(f"Model: {model_path}")
    log(f"Threshold: {threshold}  cooldown: {cooldown}s  device: {device}")
    oww = build_model(model_path)
    silence = SilenceSubmitState()
    wake_in_progress = False
    dictation_hwnd: int | None = None

    ack_ready = False
    if announce:
        try:
            ack_ready = ensure_ack_cache(LISTENING_MP3, generate_listening_audio)
        except Exception as exc:
            log(f"Listening acknowledgement cache failed: {exc}")
            emit_event("tts_cache_failed", error=type(exc).__name__)

    # Warm-up empty prediction so first real frame is snappy
    oww.predict(np.zeros(FRAME_SAMPLES, dtype=np.int16))

    last_fire = 0.0
    log('Listening for "hey computer"… (Ctrl+C to stop)')
    log(f"Events: {EVENTS_LOG}")
    emit_event("listener_start", threshold=threshold, cooldown=cooldown, device=device)
    if announce:
        speak("Wake word ready.")

    def callback(indata, frames, time_info, status):  # noqa: ARG001
        nonlocal last_fire, wake_in_progress, dictation_hwnd
        if status:
            print(status, file=sys.stderr, flush=True)
        # float32 [-1,1] → int16
        audio = indata[:, 0] if indata.ndim > 1 else indata
        pcm = (audio * 32767).astype(np.int16)
        # openWakeWord expects exactly FRAME_SAMPLES per call for streaming
        # sounddevice may deliver different sizes — buffer outside
        callback.buf = np.concatenate([getattr(callback, "buf", np.array([], dtype=np.int16)), pcm])
        while len(callback.buf) >= FRAME_SAMPLES:
            chunk = callback.buf[:FRAME_SAMPLES]
            callback.buf = callback.buf[FRAME_SAMPLES:]
            scores = oww.predict(chunk)
            # scores is dict model_name → float
            score = 0.0
            for _name, val in scores.items():
                score = max(score, float(val))
            now = time.time()
            rms = float(np.sqrt(np.mean(np.square(chunk.astype(np.float32) / 32767.0))))
            voice_event = silence.update(now, rms)
            if voice_event == "speech_started":
                emit_event("speech_started", rms=round(rms, 4))
            elif voice_event == "submit":
                emit_event("silence_complete", seconds=silence.silence_seconds)
                threading.Thread(target=submit_grok, args=(dictation_hwnd,), daemon=True).start()
                wake_in_progress = False
            elif voice_event == "timeout":
                emit_event("dictation_timeout", seconds=silence.timeout_seconds)
                wake_in_progress = False

            if score >= threshold and (now - last_fire) >= cooldown and not wake_in_progress:
                last_fire = now
                wake_in_progress = True
                print(f"[{time.strftime('%H:%M:%S')}] WAKE score={score:.3f}", flush=True)
                emit_event("wake", score=round(float(score), 4), threshold=threshold)

                def begin_dictation() -> None:
                    nonlocal dictation_hwnd, wake_in_progress
                    if announce:
                        if ack_ready:
                            play_mp3(LISTENING_MP3)
                        else:
                            speak("Listening.")
                        emit_event("tts_listening", cached=ack_ready)
                    dictation_hwnd = activate_grok()
                    emit_event("activate_grok", hwnd=dictation_hwnd)
                    if not dictation_hwnd:
                        wake_in_progress = False
                        return
                    silence.start(time.time())

                threading.Thread(target=begin_dictation, daemon=True).start()

    callback.buf = np.array([], dtype=np.int16)

    if input_wav is not None:
        # Test hook: replay the wav through the same callback; never opens a device.
        # ponytail: one burst with wall-clock time, so silence-submit timing is not replayed.
        audio = read_wav(input_wav)
        emit_event("input_wav_start", path=str(input_wav), samples=len(audio))
        callback(audio, len(audio), None, None)
        emit_event("input_wav_done", samples=len(audio))
        return

    kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": 1,
        "dtype": "float32",
        "blocksize": FRAME_SAMPLES,
        "callback": callback,
    }
    if device is not None:
        kwargs["device"] = device

    with sd.InputStream(**kwargs):
        while True:
            time.sleep(0.25)


def main() -> None:
    p = argparse.ArgumentParser(description='Hey computer → open Grok + voice')
    p.add_argument("--threshold", type=float, default=0.5, help="Wake score threshold (0-1)")
    p.add_argument("--cooldown", type=float, default=4.0, help="Seconds between wakes")
    p.add_argument("--device", type=int, default=None, help="sounddevice input device index")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--quiet", action="store_true", help="No TTS announcements")
    p.add_argument(
        "--input-wav",
        type=Path,
        default=os.environ.get("HEY_COMPUTER_INPUT_WAV") or None,
        help="Test hook: replay a 16 kHz mono wav instead of the microphone, then exit",
    )
    args = p.parse_args()

    if args.list_devices:
        list_devices()
        return

    try:
        run(
            threshold=args.threshold,
            cooldown=args.cooldown,
            device=args.device,
            announce=not args.quiet,
            input_wav=args.input_wav,
        )
    except KeyboardInterrupt:
        emit_event("listener_stop", reason="keyboard")
        print("\nStopped.")


if __name__ == "__main__":
    main()
