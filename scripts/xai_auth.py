"""Resolve xAI bearer token from existing Grok Build OAuth (or env fallbacks).

Priority (Hermes-style dual path):
  1. XAI_API_KEY env (explicit API key)
  2. ~/.grok/auth.json OIDC session (Grok Build login — preferred for SuperGrok)
  3. ~/.hermes/auth.json xai-oauth tokens (if Hermes was used to login)

Never prints the token. Returns (token, source) or raises RuntimeError.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _parse_expires(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        # unix seconds or ms
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _is_expired(entry: dict, skew_sec: int = 60) -> bool:
    exp = _parse_expires(entry.get("expires_at") or entry.get("expiry") or entry.get("expires"))
    if exp is None:
        return False
    now = datetime.now(timezone.utc)
    return now.timestamp() >= (exp.timestamp() - skew_sec)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _from_grok_auth(path: Path) -> Optional[Tuple[str, str]]:
    """Grok Build stores OIDC under issuer::client_id keys; access token in `key`."""
    data = _load_json(path)
    if not isinstance(data, dict) or not data:
        return None

    # Prefer auth.x.ai / accounts.x.ai entries that look like xAI OIDC
    candidates = []
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        key = str(v.get("key") or v.get("access_token") or "").strip()
        if not key:
            continue
        issuer = str(v.get("oidc_issuer") or k or "").lower()
        score = 0
        if "auth.x.ai" in issuer or "accounts.x.ai" in issuer or "x.ai" in issuer:
            score += 10
        if v.get("auth_mode") == "oidc":
            score += 2
        if not _is_expired(v):
            score += 5
        else:
            score -= 20  # strongly deprioritize expired
        candidates.append((score, key, k, v))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    score, key, name, entry = candidates[0]
    if score < 0 or _is_expired(entry):
        # Still return if only expired option — caller may get 401 and re-login
        if key:
            return key, f"grok-auth:{name}:possibly-expired"
        return None
    return key, f"grok-auth:{name}"


def _from_hermes_auth(path: Path) -> Optional[Tuple[str, str]]:
    data = _load_json(path)
    if not isinstance(data, dict):
        return None
    providers = data.get("providers") if isinstance(data.get("providers"), dict) else {}
    xai = providers.get("xai-oauth") if isinstance(providers.get("xai-oauth"), dict) else None
    if xai:
        tokens = xai.get("tokens") if isinstance(xai.get("tokens"), dict) else {}
        access = str(tokens.get("access_token") or "").strip()
        if access:
            return access, "hermes-auth:xai-oauth"

    pool = data.get("credential_pool") if isinstance(data.get("credential_pool"), dict) else {}
    entries = pool.get("xai-oauth") if isinstance(pool.get("xai-oauth"), list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        access = str(entry.get("access_token") or "").strip()
        if access:
            return access, "hermes-auth:pool"
    return None


def resolve_xai_bearer() -> Tuple[str, str]:
    """Return (bearer_token, source_label). Never log the token."""
    env = (os.environ.get("XAI_API_KEY") or "").strip()
    if env:
        return env, "env:XAI_API_KEY"

    grok_home = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
    hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")

    for path in (grok_home / "auth.json",):
        hit = _from_grok_auth(path)
        if hit:
            return hit

    for path in (hermes_home / "auth.json",):
        hit = _from_hermes_auth(path)
        if hit:
            return hit

    raise RuntimeError(
        "No xAI credentials found. Sign in to Grok Build (`grok login`) so "
        "~/.grok/auth.json has an OIDC session, or set XAI_API_KEY."
    )


def auth_status() -> Dict[str, Any]:
    """Safe status dict for doctor output (no secrets)."""
    try:
        token, source = resolve_xai_bearer()
        return {
            "ok": True,
            "source": source,
            "token_chars": len(token),
            "prefix": token[:6] + "…" if len(token) > 8 else "(short)",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print(json.dumps(auth_status(), indent=2))
