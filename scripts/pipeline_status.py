#!/usr/bin/env python3
"""
Pipeline doctor for voice-computer.

Checks each stage of the intended loop:
  1. Wake model + mic
  2. Wake listener process
  3. Grok OAuth (TTS)
  4. Carina TTS smoke (optional --tts-smoke)
  5. cua-driver on PATH
  6. Recent events.jsonl

Usage:
  python -u pipeline_status.py
  python -u pipeline_status.py --tts-smoke
  python -u pipeline_status.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
LOGS = SKILL / "logs"
EVENTS = LOGS / "events.jsonl"
sys.path.insert(0, str(SCRIPTS))


def ok(msg: str) -> dict:
    return {"status": "ok", "msg": msg}


def warn(msg: str) -> dict:
    return {"status": "warn", "msg": msg}


def bad(msg: str) -> dict:
    return {"status": "fail", "msg": msg}


def check_model() -> dict:
    m = SKILL / "models" / "hey_computer.onnx"
    if m.is_file() and m.stat().st_size > 10_000:
        return ok(f"hey_computer.onnx present ({m.stat().st_size} bytes)")
    return bad(f"missing model: {m}")


def check_mic() -> dict:
    try:
        import sounddevice as sd
        import numpy as np

        d = sd.rec(int(0.4 * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        peak = float(np.max(np.abs(d)))
        name = str(sd.query_devices(kind="input").get("name", "?"))
        if peak < 1e-5:
            return warn(f"mic '{name}' peak≈0 — silent or wrong device (peak={peak:.6f})")
        return ok(f"mic '{name}' peak={peak:.4f}")
    except Exception as e:
        return bad(f"mic error: {e}")


def check_wake_process() -> dict:
    try:
        import subprocess as sp

        # Windows: wmic/cim via powershell
        r = sp.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Where-Object { $_.CommandLine -like '*wake_listener.py*' } | "
                "Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        pids = [x.strip() for x in r.stdout.splitlines() if x.strip().isdigit()]
        if pids:
            return ok(f"wake_listener running pid={','.join(pids)}")
        return warn("wake_listener not running — start with start-wake.ps1")
    except Exception as e:
        return warn(f"could not query process: {e}")


def check_oauth() -> dict:
    try:
        from xai_auth import auth_status

        st = auth_status()
        if st.get("ok"):
            return ok(f"oauth source={st.get('source')} chars={st.get('token_chars')}")
        return bad(st.get("error") or "oauth fail")
    except Exception as e:
        return bad(f"oauth: {e}")


def check_cua() -> dict:
    path = shutil.which("cua-driver")
    if path:
        return ok(f"cua-driver: {path}")
    # common install path on this machine
    alt = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Cua" / "cua-driver" / "bin" / "cua-driver.exe"
    if alt.is_file():
        return warn(f"cua-driver not on PATH but found at {alt}")
    return bad("cua-driver not found")


def check_events(limit: int = 8) -> dict:
    if not EVENTS.is_file():
        return warn("no events.jsonl yet — run wake_debug.py or wake_listener")
    lines = EVENTS.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return warn("events.jsonl empty")
    recent = []
    for line in lines[-limit:]:
        try:
            recent.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    wakes = sum(1 for r in recent if r.get("kind") == "wake")
    last = recent[-1] if recent else {}
    return ok(
        f"events={len(lines)} recent_wakes={wakes} last={last.get('kind')}@{last.get('ts', '')[:19]}"
    )


def tts_smoke() -> dict:
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-u",
                str(SCRIPTS / "speak_xai.py"),
                "--text",
                "Pipeline status check. Carina online.",
                "--no-play",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if r.returncode == 0:
            return ok((r.stdout or "").strip() or "tts ok")
        return bad((r.stderr or r.stdout or "tts failed")[:300])
    except Exception as e:
        return bad(str(e))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts-smoke", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": str(SKILL),
        "stages": {
            "1_wake_model": check_model(),
            "2_microphone": check_mic(),
            "3_wake_listener": check_wake_process(),
            "4_oauth_tts_auth": check_oauth(),
            "5_cua_driver": check_cua(),
            "6_event_log": check_events(),
        },
        "intended_loop": [
            "hey computer (openWakeWord)",
            "activate_grok + Ctrl+Space (Grok STT dictation)",
            "user finishes speech → Enter sends prompt",
            "agent ACK + TTS parrot (speak_xai / carina)",
            "cua-driver acts",
            "agent TTS summarize",
        ],
        "common_breaks": [
            "Wake never fires → use wake_debug.py; lower --threshold",
            "Wake fires but Grok doesn't listen → check activate_grok / SuperGrok voice",
            "Dictation lands but no CUA → agent must load /voice-computer skill and act",
            "No parrot TTS → agent must call speak_xai.py on ack",
            "Enter required after dictation (Grok has no auto-send yet)",
        ],
    }
    if args.tts_smoke:
        report["stages"]["7_tts_smoke"] = tts_smoke()

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print("voice-computer pipeline status")
    print("=" * 48)
    print(f"skill: {SKILL}")
    for name, st in report["stages"].items():
        mark = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}.get(st["status"], "????")
        print(f"  [{mark}] {name}: {st['msg']}")
    print()
    print("Intended loop:")
    for i, step in enumerate(report["intended_loop"], 1):
        print(f"  {i}. {step}")
    print()
    print("If the loop fails, check common breaks:")
    for b in report["common_breaks"]:
        print(f"  • {b}")
    print()
    print("Debug wake word live:")
    print(f'  python -u "{SCRIPTS / "wake_debug.py"}"')
    print(f"Events: {EVENTS}")


if __name__ == "__main__":
    main()
