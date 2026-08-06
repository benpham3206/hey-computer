# Hey Computer

Hands-free Windows control for Grok Build and Codex:

> “Hey computer” (or “computer”) → spoken “Listening” acknowledgement → Grok dictation → submit after silence → computer-use action → one-sentence spoken result.

The wake word runs locally with openWakeWord. Speech-to-text is provided by Grok Build, desktop actions use CUA Driver, and spoken responses use xAI's `carina` voice with an existing Grok OAuth login.

## Features

- Always-on local wake detection for **“hey computer”** and the shorter **“computer”** trigger
- Cached “Listening” acknowledgement that finishes before dictation begins
- Automatic prompt submission after speech followed by two seconds of silence
- Exact-window foreground check before automatic submission
- xAI `carina` TTS using the existing `~/.grok/auth.json` login
- CUA Driver workflow for verified Windows GUI actions
- Live microphone and wake-score diagnostics
- Seven-day retention task for explicitly saved CUA screenshots
- Shared skill installation for Grok, Codex, and `~/.agents`

## Requirements

- Windows 11
- Python 3.10+
- Grok Build logged in with `grok login`
- [CUA Driver](https://cua.ai/docs/cua-driver) for desktop actions
- A working microphone

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Install

Clone this repository as the canonical Grok skill:

```powershell
git clone https://github.com/benpham3206/hey-computer.git "$env:USERPROFILE\.grok\skills\voice-computer"
```

Create shared junctions so Codex and other agents use the same skill:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\install-for-agents.ps1"
```

The junctions are:

- `~/.codex/skills/voice-computer`
- `~/.agents/skills/voice-computer`
- `~/.claude/skills/voice-computer`

## Start

Start the listener for the current login session:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\start-wake.ps1"
```

Install it as a per-user logon task and start it now:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\start-wake.ps1" -InstallStartup
```

The first start downloads the `hey_computer.onnx` wake model if it is missing and caches a local “Listening” MP3. OAuth tokens and microphone audio are never stored in this repository.

## Use

1. Say **“hey computer”** or **“computer.”**
2. Wait for the spoken **“Listening”** acknowledgement.
3. Speak your request.
4. Stay silent for two seconds.
5. Grok submits the prompt only if the same Grok window is still foreground.
6. The agent performs the action and speaks a one-sentence result.

Manual `Esc`, `Ctrl+Space`, and `Enter` controls remain available.

## Tune wake detection

The default threshold is `0.4`, which is intentionally sensitive enough for both supported phrases on the original setup.

```powershell
# Fewer false wakes
powershell -File .\scripts\start-wake.ps1 -Threshold 0.5

# More sensitivity
powershell -File .\scripts\start-wake.ps1 -Threshold 0.35
```

Run the live score display before tuning:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python -u .\scripts\wake_debug.py --seconds 45 --threshold 0.4
```

## Diagnostics

```powershell
python -u .\scripts\pipeline_status.py
python -u .\scripts\speak_xai.py --auth-status
cua-driver doctor
Get-Content .\logs\events.jsonl -Tail 30
```

Useful event names include `wake`, `tts_listening`, `activate_grok`, `speech_started`, `silence_complete`, `auto_submit`, and `auto_submit_refused`.

## Screenshot retention

Ordinary CUA window-state screenshots are inline and transient. Persisted screenshots should be written only under:

```text
~/.cua-driver/screenshots
```

Install the daily limited-user cleanup task:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cleanup_cua_screenshots.ps1 -InstallTask -Apply
```

It removes only `.png`, `.jpg`, `.jpeg`, and `.webp` files older than seven days inside that exact directory. It does not touch recordings or user deliverables.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m py_compile scripts\wake_listener.py scripts\silence_submit.py scripts\ack_cache.py
```

## Privacy and safety

- Wake-word inference runs locally.
- Raw microphone audio is not saved.
- Event logs contain state transitions and scores, not prompt text.
- Automatic submission is disabled after 60 seconds, before speech begins, or whenever the expected Grok window loses foreground focus.
- Destructive, messaging, payment, installation, and security-changing requests still require confirmation through the agent skill.

## Project layout

```text
SKILL.md             Agent instructions and voice-computer loop
scripts/             Wake, dictation, TTS, CUA, retention, and diagnostics
tests/               State-machine and safety-contract tests
references/          Architecture and debugging notes
```

## Contributing

Run the full test suite before opening a pull request. Keep machine-specific logs, cached audio, wake models, OAuth files, screenshots, and PID files out of commits.
