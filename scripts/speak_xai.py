#!/usr/bin/env python3
"""
xAI Grok TTS (Carina) for voice-computer — Hermes-compatible path.

Auth: reuses Grok Build OAuth from ~/.grok/auth.json (same SuperGrok session).
Falls back to XAI_API_KEY, then Hermes ~/.hermes/auth.json.

Usage:
  python speak_xai.py "Done. Dark mode is on."
  python speak_xai.py --text "On it." --voice carina
  python speak_xai.py --list-voices
  python speak_xai.py --auth-status
  python speak_xai.py --no-auto-tags "Already [pause] tagged."
  python speak_xai.py --file reply.md   # extracts ```voice blocks if present
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

# Same directory imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spoken_text import prepare_spoken_text, speech_tag_cheatsheet  # noqa: E402
from xai_auth import auth_status, resolve_xai_bearer  # noqa: E402

DEFAULT_VOICE = "carina"
DEFAULT_LANGUAGE = "en"
DEFAULT_BASE = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
USER_AGENT = "GrokBuild-voice-computer/1.0 (xAI TTS; OAuth-from-grok-auth)"


def list_voices(token: str) -> list:
    r = requests.get(
        f"{DEFAULT_BASE}/tts/voices",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("voices") or []


def synthesize(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE,
    language: str = DEFAULT_LANGUAGE,
    speed: float | None = None,
    text_normalization: bool = False,
    auto_speech_tags: bool = True,
    prefer_voice_blocks: bool = True,
    out_path: Path | None = None,
) -> Path:
    spoken = prepare_spoken_text(
        text,
        auto_speech_tags=auto_speech_tags,
        prefer_voice_blocks=prefer_voice_blocks,
    )
    if not spoken:
        raise ValueError("Nothing to speak after cleanup (empty voice blocks / only markup).")

    token, source = resolve_xai_bearer()
    payload = {
        "text": spoken,
        "voice_id": voice_id,
        "language": language,
    }
    if speed is not None and abs(speed - 1.0) > 1e-6:
        payload["speed"] = max(0.7, min(1.5, float(speed)))
    if text_normalization:
        payload["text_normalization"] = True

    r = requests.post(
        f"{DEFAULT_BASE}/tts",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        json=payload,
        timeout=90,
    )
    if r.status_code == 401:
        raise RuntimeError(
            f"xAI TTS 401 Unauthorized (auth source={source}). "
            "Re-login with `grok login` so ~/.grok/auth.json refreshes, "
            "or set XAI_API_KEY."
        )
    if r.status_code == 403:
        raise RuntimeError(
            f"xAI TTS 403 Forbidden (auth source={source}). "
            "Subscription may not include Voice/TTS on this OAuth surface — "
            "try XAI_API_KEY from console.x.ai."
        )
    if not r.ok:
        raise RuntimeError(f"xAI TTS HTTP {r.status_code}: {r.text[:400]}")

    if out_path is None:
        cache = Path(os.environ.get("TEMP") or tempfile.gettempdir()) / "voice-computer-tts"
        cache.mkdir(parents=True, exist_ok=True)
        out_path = cache / f"carina_{int(time.time() * 1000)}.mp3"
    out_path = Path(out_path)
    out_path.write_bytes(r.content)
    return out_path


def play_mp3(path: Path) -> None:
    """Play MP3 on Windows via WPF MediaPlayer (no extra deps)."""
    path = path.resolve()
    # MediaPlayer needs a URI; block until done
    ps = f"""
Add-Type -AssemblyName PresentationCore | Out-Null
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([Uri]::new('{str(path).replace("'", "''")}'))
$sw = [Diagnostics.Stopwatch]::StartNew()
while (-not $p.NaturalDuration.HasTimeSpan) {{
  Start-Sleep -Milliseconds 50
  if ($sw.ElapsedMilliseconds -gt 8000) {{ throw 'Media open timeout' }}
}}
$p.Volume = 1.0
$p.Play()
$dur = $p.NaturalDuration.TimeSpan.TotalMilliseconds
Start-Sleep -Milliseconds ([int][Math]::Max(200, $dur + 250))
$p.Close()
"""
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=300,
        creationflags=flags,
    )
    if r.returncode != 0:
        # Fallback: open with default app (non-blocking)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            raise RuntimeError(r.stderr or r.stdout or "playback failed")


def speak(
    text: str,
    *,
    voice_id: str = DEFAULT_VOICE,
    play: bool = True,
    **kwargs,
) -> Path:
    path = synthesize(text, voice_id=voice_id, **kwargs)
    if play:
        play_mp3(path)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="xAI Grok TTS (Carina) via Grok OAuth")
    p.add_argument("text", nargs="?", default="", help="Text to speak")
    p.add_argument("--text", dest="text_flag", default="", help="Text to speak (alt)")
    p.add_argument("--file", type=Path, help="Read text/markdown from file")
    p.add_argument("--voice", default=DEFAULT_VOICE, help="voice_id (default: carina)")
    p.add_argument("--language", default=DEFAULT_LANGUAGE)
    p.add_argument("--speed", type=float, default=None)
    p.add_argument("--no-auto-tags", action="store_true", help="Disable auto speech tags")
    p.add_argument("--no-voice-blocks", action="store_true", help="Speak whole text, ignore ```voice fences")
    p.add_argument("--text-normalization", action="store_true")
    p.add_argument("--out", type=Path, help="Write mp3 path")
    p.add_argument("--no-play", action="store_true")
    p.add_argument("--list-voices", action="store_true")
    p.add_argument("--auth-status", action="store_true")
    p.add_argument("--tags-help", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Print spoken script only")
    args = p.parse_args()

    if args.auth_status:
        print(json.dumps(auth_status(), indent=2))
        return

    if args.tags_help:
        print(speech_tag_cheatsheet())
        return

    if args.list_voices:
        token, source = resolve_xai_bearer()
        print(f"auth: {source}")
        for v in list_voices(token):
            vid = v.get("voice_id") or v.get("id") or "?"
            name = v.get("name") or ""
            print(f"  {vid:12}  {name}")
        return

    text = args.text_flag or args.text
    if args.file:
        text = args.file.read_text(encoding="utf-8")
    if not text.strip():
        p.error("Pass text, --text, or --file")

    if args.dry_run:
        spoken = prepare_spoken_text(
            text,
            auto_speech_tags=not args.no_auto_tags,
            prefer_voice_blocks=not args.no_voice_blocks,
        )
        print(spoken)
        return

    try:
        path = speak(
            text,
            voice_id=args.voice,
            language=args.language,
            speed=args.speed,
            text_normalization=args.text_normalization,
            auto_speech_tags=not args.no_auto_tags,
            prefer_voice_blocks=not args.no_voice_blocks,
            out_path=args.out,
            play=not args.no_play,
        )
        print(f"ok voice={args.voice} file={path}", flush=True)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        # Fallback to SAPI if xAI fails
        sapi = Path(__file__).with_name("speak.ps1")
        if sapi.is_file() and not args.no_play:
            spoken = prepare_spoken_text(text, auto_speech_tags=False)
            # strip tags for SAPI
            import re

            plain = re.sub(r"\[(?:pause|long-pause|laugh|sigh|breath)\]", " ", spoken, flags=re.I)
            plain = re.sub(r"</?[^>]+>", " ", plain)
            plain = re.sub(r"\s+", " ", plain).strip()
            if plain:
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(sapi),
                        "-Text",
                        plain[:500],
                    ],
                    check=False,
                )
        sys.exit(1)


if __name__ == "__main__":
    main()
