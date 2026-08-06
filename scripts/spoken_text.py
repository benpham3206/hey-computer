"""Prepare assistant text for xAI TTS (Hermes-inspired cleaning + speech tags)."""

from __future__ import annotations

import html
import re
from typing import List, Optional, Tuple

# --- Voice blocks: only these segments are spoken when present ---
_VOICE_FENCE_RE = re.compile(
    r"```(?:voice|speak|tts)\s*\n(.*?)```",
    flags=re.DOTALL | re.IGNORECASE,
)
_VOICE_TAG_RE = re.compile(
    r"<voice(?:\s[^>]*)?>(.*?)</voice>",
    flags=re.DOTALL | re.IGNORECASE,
)
_VOICE_BB_RE = re.compile(
    r"\[\[\[voice\]\]\](.*?)\[\[\[/voice\]\]\]",
    flags=re.DOTALL | re.IGNORECASE,
)

# xAI speech tags (from docs + Hermes)
INLINE_SPEECH_TAGS = (
    "pause",
    "long-pause",
    "hum-tune",
    "laugh",
    "chuckle",
    "giggle",
    "cry",
    "tsk",
    "tongue-click",
    "lip-smack",
    "breath",
    "inhale",
    "exhale",
    "sigh",
)
WRAPPING_SPEECH_TAGS = (
    "soft",
    "whisper",
    "loud",
    "build-intensity",
    "decrease-intensity",
    "higher-pitch",
    "lower-pitch",
    "slow",
    "fast",
    "sing-song",
    "singing",
    "laugh-speak",
    "emphasis",
)

_INLINE_RE = re.compile(
    r"\[(" + "|".join(INLINE_SPEECH_TAGS) + r")\]",
    flags=re.IGNORECASE,
)
# Official xAI wrapping: <whisper>...</whisper>
_WRAP_ANGLE_RE = re.compile(
    r"</?(" + "|".join(WRAPPING_SPEECH_TAGS) + r")>",
    flags=re.IGNORECASE,
)
# Hermes BBCode-style: [whisper]...[/whisper]
_WRAP_BB_RE = re.compile(
    r"\[/?(" + "|".join(WRAPPING_SPEECH_TAGS) + r")\]",
    flags=re.IGNORECASE,
)
_ANY_SPEECH_TAG_RE = re.compile(
    r"("
    + r"\[(?:" + "|".join(INLINE_SPEECH_TAGS) + r")\]"
    + r"|</?(?:" + "|".join(WRAPPING_SPEECH_TAGS) + r")>"
    + r"|\[/?(?:" + "|".join(WRAPPING_SPEECH_TAGS) + r")\]"
    + r")",
    flags=re.IGNORECASE,
)
_FIRST_SENTENCE_RE = re.compile(r"^(.{12,120}?[.!?…])\s+(?=\S)", flags=re.DOTALL)

_THINK_RE = re.compile(r"<think[\s>].*?</think>", flags=re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think[\s>].*\Z", flags=re.DOTALL | re.IGNORECASE)
_MD_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^()]|\([^)]*\))*\)")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)")
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", flags=re.DOTALL)
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", flags=re.DOTALL)
_URL_RE = re.compile(r"https?://\S+")
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)


def extract_voice_blocks(text: str) -> Optional[str]:
    """If the reply contains explicit voice blocks, return only those segments.

    Supported forms (Hermes / agent-friendly):
      ```voice
      ...
      ```
      <voice>...</voice>
      [[[voice]]]...[[[/voice]]]
    """
    if not text:
        return None
    chunks: List[str] = []
    for rx in (_VOICE_FENCE_RE, _VOICE_TAG_RE, _VOICE_BB_RE):
        chunks.extend(m.group(1).strip() for m in rx.finditer(text) if m.group(1).strip())
    if not chunks:
        return None
    return "\n\n".join(chunks)


def strip_markdown_for_tts(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(str(text))
    # Preserve voice fences before generic code strip: re-inject after
    voice_only = extract_voice_blocks(text)
    if voice_only is not None:
        text = voice_only
    else:
        text = _MD_CODE_BLOCK_RE.sub(" ", text)
    text = _THINK_RE.sub(" ", text)
    text = _THINK_OPEN_RE.sub(" ", text)
    text = _MD_IMAGE_RE.sub(lambda m: f" {m.group(1)} " if m.group(1) else " ", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _URL_RE.sub("", text)
    text = _MD_INLINE_CODE_RE.sub(r"\1", text)
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = _EMOJI_RE.sub("", text)
    return text


def normalize_bbcode_wrapping_to_angle(text: str) -> str:
    """Hermes rewriter uses [whisper]...[/whisper]; xAI docs use <whisper>...</whisper>.

    Convert BBCode wrapping tags to official angle form; leave [pause] inline alone.
    """
    def open_sub(m: re.Match) -> str:
        return f"<{m.group(1).lower()}>"

    def close_sub(m: re.Match) -> str:
        return f"</{m.group(1).lower()}>"

    text = re.sub(
        r"\[(" + "|".join(WRAPPING_SPEECH_TAGS) + r")\]",
        open_sub,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\[/(" + "|".join(WRAPPING_SPEECH_TAGS) + r")\]",
        close_sub,
        text,
        flags=re.IGNORECASE,
    )
    return text


def local_auto_speech_tags(text: str) -> str:
    """Conservative local pass (Hermes): [pause] between paragraphs / first sentence."""
    clean = text.strip()
    if not clean:
        return text
    if _ANY_SPEECH_TAG_RE.search(clean):
        # Already tagged — only normalize whitespace / wrapping style
        local = normalize_bbcode_wrapping_to_angle(clean)
        local = re.sub(r"\n\s*\n+", " [pause] ", local)
        local = re.sub(r"\s*\n\s*", " ", local)
        return re.sub(r"\s{2,}", " ", local).strip()

    local = clean
    local = re.sub(r"\n\s*\n+", " [pause] ", local)
    local = re.sub(r"\s*\n\s*", " ", local)
    if not _ANY_SPEECH_TAG_RE.search(local):
        local = _FIRST_SENTENCE_RE.sub(r"\1 [pause] ", local, count=1)
    # Soft delivery for short ack lines
    if len(local) < 120 and not local.lower().startswith("<soft"):
        local = f"<soft>{local}</soft>"
    return re.sub(r"\s{2,}", " ", local).strip()


def prepare_spoken_text(
    text: str,
    *,
    auto_speech_tags: bool = True,
    prefer_voice_blocks: bool = True,
) -> str:
    """Full pipeline: voice blocks → strip markdown → optional auto tags."""
    if not text:
        return ""
    raw = str(text).lstrip("\ufeff")
    if prefer_voice_blocks:
        blocks = extract_voice_blocks(raw)
        if blocks is not None:
            raw = blocks
    spoken = strip_markdown_for_tts(raw)
    spoken = re.sub(r"[ \t]{2,}", " ", spoken)
    spoken = re.sub(r"\n{3,}", "\n\n", spoken).strip()
    if auto_speech_tags:
        spoken = local_auto_speech_tags(spoken)
    else:
        spoken = normalize_bbcode_wrapping_to_angle(spoken)
        spoken = re.sub(r"\s*\n\s*", " ", spoken)
        spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    # Flatten newlines for payload (some engines cut at newline)
    spoken = spoken.replace("\n", " ")
    spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    return spoken


def speech_tag_cheatsheet() -> str:
    inline = ", ".join(f"[{t}]" for t in INLINE_SPEECH_TAGS)
    wrap = ", ".join(f"<{t}>…</{t}>" for t in WRAPPING_SPEECH_TAGS)
    return f"Inline: {inline}\nWrapping: {wrap}"
