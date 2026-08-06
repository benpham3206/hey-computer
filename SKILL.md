---
name: voice-computer
description: >
  Hands-free voice + desktop control: wake "hey computer", Grok STT dictation,
  TTS parrot (Carina/OAuth), cua-driver actions, spoken summary. Also debug
  wake-word scoring and pipeline monitoring. Use for /voice-computer, "hey
  computer", voice+CUA, wake debug, pipeline status, or room voice control.
  Shared skill for Grok Build, Codex, and agents under ~/.agents/skills.
metadata:
  short-description: "Voice → CUA → spoken result (+ wake debug)"
argument-hint: "[on | status | doctor | debug | wake | task...]"
---

# Voice Computer (Grok Build + CUA)

Turn this session into a **voice → plan → CUA action → spoken result** agent.

Grok Build's built-in voice is **dictation into the prompt**. Room activation
uses a **separate always-on wake daemon** (scripts below). Use this skill for
ack → CUA → spoken result after the transcript lands.

## Grok voice mode (this version)

On **Grok Build 0.2.x** (including 0.2.121):

| Capability | Status |
|------------|--------|
| Voice **dictation** (speech → prompt text) | **Yes** |
| Toggle | `/voice` or **Ctrl+Space** / **F8** |
| Stop capture | **Esc** or **Enter** (or chord again in toggle mode) |
| Capture style | Settings: **Toggle** vs **Hold to talk** (hold needs Kitty keyboard protocol; Windows Terminal usually falls back to toggle) |
| STT language | Settings → **Voice language** (default English) |
| Mic health | `grok doctor` / `/doctor` → **Voice** section |
| Always-on wake word ("hey computer") | **Yes** — local openWakeWord daemon (see Wake daemon below) |
| On wake: open/focus Grok + start dictation | **Yes** — cached “Listening” acknowledgement, then `activate_grok.ps1` |
| Submit after dictation silence | **Yes** — after speech begins and 2 seconds of sustained silence, foreground Grok only |
| Agent spoken replies (Grok Voice TTS) | **Yes** — xAI `/v1/tts` with **carina**, auth from Grok OAuth |

**Env / flags:** `GROK_VOICE_MODE`, `GROK_VOICE_CAPTURE=inprocess` (macOS capture helper fallback).

**Subscription note:** the binary advertises that `/voice` may require **SuperGrok**. If voice fails with a plan gate, upgrade or use typed input until dictation is unlocked.

**Your machine (when doctor last ran):** microphone is supported when Doctor shows `voice.status = available`.

## TTS: xAI Grok Voice (Carina) + existing OAuth

**Do not ask the user for a new API key.** Reuse the Grok Build login already in
`~/.grok/auth.json` (OIDC against `auth.x.ai`) — same pattern as Hermes
`xai-oauth` reusing a SuperGrok session for `/v1/tts`.

Auth resolution order (`scripts/xai_auth.py`):

1. `XAI_API_KEY` env (optional override only)
2. **`~/.grok/auth.json` OIDC access token** ← primary
3. `~/.hermes/auth.json` `xai-oauth` (if present)

Default voice: **`carina`**. Endpoint: `POST https://api.x.ai/v1/tts`.

### How to Speak (required for [A]/[D])

Prefer the Python entrypoint (OAuth + tags + voice blocks):

```powershell
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\speak_xai.py" --text "On it. Opening Notepad."
```

Or the wrapper (falls back to Windows SAPI if xAI fails):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\speak.ps1" -Text "On it. Opening Notepad."
```

Doctor / auth (never print the raw token):

```powershell
python -u "...\speak_xai.py" --auth-status
python -u "...\speak_xai.py" --list-voices
```

### Voice blocks (only these get spoken when present)

When you write a longer chat reply, put the spoken line in a voice block so
markdown/tools stay silent:

````markdown
```voice
On it. [pause] Opening YouTube and starting the track.
```
````

Also accepted: `<voice>...</voice>` and `[[[voice]]]...[[[/voice]]]`.

If **no** voice block is present, the whole message is cleaned and spoken
(after markdown strip). Prefer a voice block for multi-paragraph answers.

### Auto speech tags (Hermes-style)

`speak_xai.py` defaults **`--auto-tags` on**:

1. Local pass: `[pause]` between paragraphs / after first sentence; short
   acks wrapped in `<soft>…</soft>`
2. Converts Hermes BBCode wrappers `[whisper]…[/whisper]` → xAI
   `<whisper>…</whisper>`
3. You may emit tags yourself in the voice block for richer delivery

**Inline tags (examples):** `[pause]` `[long-pause]` `[laugh]` `[chuckle]`
`[sigh]` `[breath]` `[inhale]` `[exhale]`

**Wrapping tags (examples):** `<soft>` `<whisper>` `<loud>` `<slow>` `<fast>`
`<emphasis>` `<higher-pitch>` `<lower-pitch>` `<sing-song>`

Example spoken script:

```text
<soft>On it.</soft> [pause] Opening YouTube and playing that track.
```

When writing acks/finals, either:

- Put plain short text in a ````voice` block and let auto-tags run, **or**
- Emit tags yourself for tone (still put them inside the voice block).

Do **not** dump raw URLs, code fences, or tool dumps into the spoken path.

## Wake daemon ("hey computer")

Always-on listener lives under this skill. At the default `0.4` threshold on the tuned Windows setup, both **“hey computer”** and the shorter **“computer”** are supported wake phrases:

| Script | Role |
|--------|------|
| `scripts/wake_listener.py` | Mic → openWakeWord `hey_computer` → fire (+ events.jsonl) |
| `scripts/wake_debug.py` | **Live score/mic UI** — did you say hey computer? |
| `scripts/pipeline_status.py` | Doctor for wake / oauth / cua / events |
| `scripts/tail_events.ps1` | Tail `logs/events.jsonl` |
| `scripts/activate_grok.ps1` | Focus/launch Grok → **Ctrl+Space** voice |
| `scripts/start-wake.ps1` | Start listener (background); `-InstallStartup` for logon |
| `scripts/stop-wake.ps1` | Stop listener |
| `scripts/install-for-agents.ps1` | Junction skill into Codex / `.agents` / Claude |
| `scripts/xai_auth.py` | Resolve bearer from **Grok OAuth** / env / Hermes |
| `scripts/speak_xai.py` | xAI TTS **carina** + voice blocks + auto speech tags |
| `scripts/spoken_text.py` | Markdown strip + tag helpers |
| `scripts/speak.ps1` | Wrapper → xAI first, SAPI fallback |
| `models/hey_computer.onnx` | Wake model |
| `references/debug-loop.md` | Break/fix table for the full loop |

**Start now:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\start-wake.ps1"
```

**Start at Windows logon:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\start-wake.ps1" -InstallStartup
```

**Stop:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\stop-wake.ps1"
```

**User flow after wake:**

1. Say **hey computer** (room distance OK with a decent mic).
2. PC focuses/opens Grok and starts dictation (you should hear "Listening" if TTS works).
3. Speak the request, then remain silent for 2 seconds. The listener stops dictation and submits only if Grok is still foreground. Manual **Esc** / **Enter** controls remain available.
4. This skill handles ack → CUA → spoken result.

If false wakes: raise threshold (`start-wake.ps1` defaults to `0.4`; try `0.5`–`0.7`).
If misses: lower to `0.35`–`0.45`. Logs: `~/.grok/skills/voice-computer/logs/`.

When user runs `/voice-computer wake`, `start-wake`, or asks to enable the wake word, **run `start-wake.ps1`** (or report status from logs/pid). When they say stop wake, run `stop-wake.ps1`.

## Debug: did I say "hey computer"?

**Primary tool** — live score + mic (does **not** open Grok unless `--activate`):

```powershell
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\wake_debug.py"
```

You should see a updating line like:

```text
mic ▓▓▓··· 0.12 │ ████░░░░ 0.41 │ listening │ max=0.41 wakes=0
```

When the phrase is recognized:

```text
*** [12:34:56] HEARD «hey computer»  score=0.72  (threshold 0.50) ***
```

Tips:

| Observation | Action |
|-------------|--------|
| Mic peak stays ~0 while talking | Wrong device → `--list-devices` then `--device N` |
| Score rises but never hits threshold | `--threshold 0.35` |
| Score stays ~0 always | Model/mic path issue; run `pipeline_status.py` |
| WAKE but Grok does nothing | Production listener + SuperGrok voice; test `activate_grok.ps1` |

```powershell
# 45s timed session + CSV
python -u "...\wake_debug.py" --seconds 45 --csv "$env:TEMP\wake.csv" --threshold 0.4

# Full pipeline doctor
python -u "...\pipeline_status.py"
python -u "...\pipeline_status.py" --tts-smoke

# Live event log (wake_listener + wake_debug write here)
powershell -File "...\tail_events.ps1"
```

Events file: `~/.grok/skills/voice-computer/logs/events.jsonl`.

### Why the full loop may not complete

Intended: wake → Grok STT → **TTS parrot of request** → CUA → summarize.

Common gaps (not bugs in wake alone):

1. **Auto-submit is foreground-gated**: it refuses to send if focus leaves the Grok window, if no speech was detected, or if dictation exceeds 60 seconds.
2. **Agent must be in this skill** and call `speak_xai` + `cua-driver` — wake only opens dictation.
3. **Parrot is agent-owned**: on each user turn, speak back what you heard before acting:
   `speak_xai.py --text "You said: <short paraphrase>."` then CUA, then summarize TTS.

If `$ARGUMENTS` is `debug` / `monitor`, run `wake_debug` instructions or `pipeline_status` and report results.

## Multi-agent (Codex / ChatGPT agents / Claude)

Canonical path: `~/.grok/skills/voice-computer`.

Install junctions so other harnesses see the same skill:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.grok\skills\voice-computer\scripts\install-for-agents.ps1"
```

Creates:

- `~/.agents/skills/voice-computer` → canonical
- `~/.codex/skills/voice-computer` → canonical
- `~/.claude/skills/voice-computer` → canonical
- Pointer block in `~/.codex/AGENTS.md`

Codex/ChatGPT-compatible agents should load `SKILL.md` from any of those paths and use the same scripts (absolute paths under the user profile).

## When invoked (`/voice-computer` or matching intent)

### 1. Enter mode (first message only)

Reply briefly (2–4 lines) that voice-computer mode is on, and tell the user:

1. Prefer **hey computer** if the wake daemon is running (or start it for them).
2. Or press **Ctrl+Space** / **F8** / `/voice` and speak.
3. Stop dictation, **Enter** to send — then ack → CUA → spoken result.

If `$ARGUMENTS` is `status` or `doctor`, run the status checks below and stop.
If `$ARGUMENTS` is a real task (not a meta command), treat that text as the
spoken request and skip the wait.

### 2. Per-request loop (every user turn while in this mode)

Assume the user message is a **voice transcript** (even if typed). Execute:

```
[A] ACK     — one short spoken+written line: what you will do
[B] ROUTE   — shell/API/filesystem first if that fully solves it;
              else GUI via cua-driver skill
[C] ACT     — run actions; verify after each CUA step
[D] SPEAK   — speak final outcome (1–2 sentences); mirror in text
[E] IDLE    — wait for next dictation / message
```

#### [A] Acknowledge (parrot + plan)

1. **Parrot** what you heard in one short clause (TTS + text), e.g.  
   `You said: open Notepad and type hello.`
2. **Plan** one line: `On it — opening Notepad and typing the note.`
3. Speak both via `speak_xai.py` (voice block preferred).  
   Do **not** monologue more than ~8 seconds.

#### [B] Route

Prefer non-GUI when possible (rung 0 of cua-driver skill):

- Files, git, package managers, known CLIs, APIs, PowerShell that doesn't
  steal focus for the outcome.

Use **cua-driver** when the outcome is in a GUI app/window.

**Always load and follow the `cua-driver` skill** for GUI work (Windows:
also read its `WINDOWS.md` when needed). Defaults:

- Transport: `cua-driver <tool> '<json>'` CLI (not MCP unless user asks).
- `start_session` with a stable id, e.g. `session:"voice-computer"`.
- Snapshot before every action; `verify_state` after.
- Background delivery first; escalate only on driver signal.
- Never report success without verification.

#### [C] Safety (voice mishears)

**Confirm by asking the user** (do not act) when the request would:

- Delete files, empty recycle bin, format, or mass-overwrite
- Send email/chat/messages, post publicly, submit payments/orders
- Change security/privacy, install software, disable firewall/AV
- Quit apps with unsaved work, force-kill processes

On ambiguity or bad STT, say: `I heard: "…". Confirm before I continue?`

Cancel phrases: `stop`, `cancel`, `never mind`, `abort` → halt tools, speak
`Cancelled.`, return to idle.

#### [D] Speak (final words)

After success or failure, speak **one short** result:

- Success: `Done. Dark mode is on.`
- Partial: `Opened Settings, but I couldn't find the toggle.`
- Failure: `Couldn't finish — <one reason>.`

Then mirror that line in the chat.

### 3. How to Speak

Use **§ TTS: xAI Grok Voice (Carina) + existing OAuth** above.

```powershell
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\speak_xai.py" --text "Done. Notepad has your message."
```

If xAI fails (401/403), script falls back via `speak.ps1` to SAPI; continue with
text and note TTS once. On 401: tell user to open Grok once or run `grok login`
so OAuth refreshes — **do not invent a new API key step** unless OAuth is dead.

On long multi-step GUI tasks, optional mid-progress speak every ~30–60s.

### 4. Status / doctor (`/voice-computer status` or `doctor`)

Run and summarize (do not dump secrets):

```powershell
grok doctor --json
python -u "$env:USERPROFILE\.grok\skills\voice-computer\scripts\speak_xai.py" --auth-status
where.exe cua-driver
cua-driver doctor
```

Report:

- Voice mic name / available?
- **TTS auth source** (`grok-auth:…` expected) and that voice is `carina`
- cua-driver on PATH?
- How to start dictation (Ctrl+Space / F8 / `/voice`)
- Whether wake listener is running (`logs/wake.pid` / process `wake_listener.py`)

## Out of scope (honest limits)

| Desired | Reality |
|---------|---------|
| Full duplex conversation like ChatGPT Voice | Still dictation-in + optional local TTS-out |
| Auto-send after silence | Local listener submits after speech plus 2 seconds of silence; Grok must remain foreground |
| Perfect wake with TV noise | Tune threshold; far-field mic helps |

## CUA screenshot retention

Normal CUA window-state screenshots are inline and transient. When a screenshot must persist, save it under `~/.cua-driver/screenshots`. The per-user `CuaScreenshotRetention` scheduled task runs daily and removes only `.png`, `.jpg`, `.jpeg`, and `.webp` files in that directory whose last-write time is older than seven days. It does not touch recordings or user deliverables.

## Example turns

**User (dictated):** open notepad and type hello from voice computer

1. Speak/write: `On it — opening Notepad and typing the greeting.`
2. `cua-driver launch_app ...` → snapshot → type → verify.
3. Speak/write: `Done. Notepad has your message.`

**User:** delete everything on my desktop

1. Speak/write: `That would delete Desktop files. Say confirm delete desktop if you really want that.`
2. Wait; do not call delete tools until explicit confirm.

## Mode exit

If the user says `exit voice computer`, `stop voice mode`, or `/voice-computer off`,
acknowledge, stop treating every message as a voice task, and return to normal
assistant behavior.
