# Voice Computer architecture notes

## Product loop (now)

```
hey computer (openWakeWord)
  → activate_grok (focus/launch + Ctrl+Space)
  → Grok dictation → prompt
  → agent: ack → cua-driver → speak_xai (Carina)
```

## Auth (critical)

Hermes reuses SuperGrok OAuth for `POST /v1/tts`. We do the same without Hermes:

| Source | Path |
|--------|------|
| Primary | `~/.grok/auth.json` OIDC `key` from `auth.x.ai` (Grok Build login) |
| Override | `XAI_API_KEY` |
| Optional | `~/.hermes/auth.json` → `providers.xai-oauth.tokens.access_token` |

`xai_auth.resolve_xai_bearer()` never logs the token. On 401, user re-opens Grok
or runs `grok login` (refresh). Do not require a separate console key when OAuth works.

## TTS stack (Hermes-aligned)

| Piece | Ours | Hermes |
|-------|------|--------|
| Endpoint | `https://api.x.ai/v1/tts` | same |
| Voice | `carina` (default) | configurable (`eve` default in Hermes docs) |
| Auto speech tags | local pass + agent-emitted tags | local + optional LLM rewrite |
| Voice blocks | ````voice` / `<voice>` / `[[[voice]]]` | platform voice bubbles + spoken prep |
| Text cleanup | `spoken_text.prepare_spoken_text` | `tts_text_normalize.prepare_spoken_text` |

Speech tags: inline `[pause]`, wrapping `<soft>…</soft>` (xAI docs). BBCode
`[soft]…[/soft]` from Hermes rewriters is converted to angle form before send.

## Why a skill not a full app

Grok already has STT, agent loop, tools, cua-driver, and OAuth. Packaging
policy + thin TTS/wake scripts is the smallest Windows product surface.
