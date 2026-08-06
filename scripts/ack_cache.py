"""Small cache contract for the wake acknowledgement audio."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def ensure_ack_cache(target: Path, generator: Callable[[Path], None]) -> bool:
    target = Path(target)
    if target.is_file() and target.stat().st_size > 0:
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    generator(target)
    return target.is_file() and target.stat().st_size > 0
