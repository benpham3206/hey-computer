# Debug & monitoring the voice-computer loop

## Intended loop

```
1. hey computer          → openWakeWord (wake_listener / wake_debug)
2. activate Grok         → activate_grok.ps1 + Ctrl+Space (dictation)
3. user speaks request   → Grok STT into prompt
4. user presses Enter    → prompt sent (Grok has no auto-send yet)
5. agent ACK + TTS parrot → speak_xai.py (Carina, OAuth)
6. computer use          → cua-driver
7. agent TTS summarize   → speak_xai.py
```

## Why it often "doesn't play out"

| Break | Symptom | Check |
|-------|---------|--------|
| Wake never fires | Silence after "hey computer" | `wake_debug.py` score bar |
| Wrong mic | Peak stays ~0 | `wake_debug.py --list-devices` |
| Threshold too high | Score peaks 0.3–0.4, no WAKE | `--threshold 0.35` |
| Wake but no Grok | Score WAKE, no window | `activate_grok.ps1` alone |
| Dictation empty | Grok open, no text | SuperGrok `/voice`, mic permissions |
| Stuck after speech | Text in prompt, nothing happens | Need **Enter**; agent session must load skill |
| No parrot / no CUA | Agent replies in text only | Must call `speak_xai` + cua-driver per SKILL.md |
| TTS 401 | OAuth expired | `grok login` / reopen Grok |

## Tools

```powershell
# Live: did I say hey computer? (score + mic)
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\wake_debug.py"

# Pipeline doctor
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\pipeline_status.py"
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\pipeline_status.py" --tts-smoke

# Event log (JSONL)
powershell -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\tail_events.ps1"

# Production wake (opens Grok)
powershell -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\start-wake.ps1"
```

## Multi-agent install

```powershell
powershell -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\install-for-agents.ps1"
```

Junctions: `~/.agents/skills`, `~/.codex/skills`, `~/.claude/skills` → canonical grok skill.
Also appends a pointer to `~/.codex/AGENTS.md`.
