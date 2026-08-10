#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "Muse Glimmer Lab → http://127.0.0.1:${PORT:-7870}"
echo "Offline demos work with no model. Optional live: set OPENAI_BASE_URL in .env"
exec python app.py
