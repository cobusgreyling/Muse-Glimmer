#!/usr/bin/env bash
# Probe configured live endpoint (via running lab or direct OpenAI-compatible URL).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer lab proxy if up; else hit OPENAI_BASE_URL from .env directly
LAB="${LAB_URL:-http://127.0.0.1:${PORT:-7870}}"

if curl -sf "$LAB/api/health" >/dev/null 2>&1; then
  echo "Probing via lab: $LAB/api/live/probe"
  curl -sf "$LAB/api/live/probe" | python3 -m json.tool
  exit 0
fi

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE="${OPENAI_BASE_URL:-}"
if [[ -z "$BASE" ]]; then
  echo "Lab not running and OPENAI_BASE_URL unset. Start ./run.sh or configure-live.sh first." >&2
  exit 1
fi

BASE="${BASE%/}"
[[ "$BASE" == */v1 ]] || BASE="${BASE}/v1"
KEY="${OPENAI_API_KEY:-${HF_TOKEN:-}}"

echo "Lab down — probing endpoint directly: $BASE/models"
AUTH=()
if [[ -n "$KEY" ]]; then
  AUTH=(-H "Authorization: Bearer ${KEY}")
fi
curl -sf "${AUTH[@]}" "$BASE/models" | python3 -m json.tool
echo
echo "OK models list. Start the lab (./run.sh) for full /api/live/probe + chat UI."
