#!/usr/bin/env bash
# Run the "hey computer" wake listener in the foreground on macOS
# (counterpart to start-wake.ps1 -Foreground). Ctrl+C stops it.
#
# Usage: scripts/start-wake.sh [--threshold 0.4] [--cooldown 4] [--quiet]
set -euo pipefail

threshold=0.4
cooldown=4
extra=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --threshold) threshold="$2"; shift 2 ;;
    --cooldown) cooldown="$2"; shift 2 ;;
    --quiet) extra+=(--quiet); shift ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

scripts="$(cd "$(dirname "$0")" && pwd)"
python="${PYTHON:-}"
if [[ -z "$python" ]]; then
  if [[ -x "$scripts/../.venv/bin/python" ]]; then python="$scripts/../.venv/bin/python"; else python=python3; fi
fi

exec "$python" -u "$scripts/wake_listener.py" --threshold "$threshold" --cooldown "$cooldown" ${extra[@]+"${extra[@]}"}
