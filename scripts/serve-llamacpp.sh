#!/usr/bin/env bash
# Start llama.cpp OpenAI-compatible server for Muse Glimmer GGUF.
set -euo pipefail

HF_REPO="${LLAMA_HF_REPO:-meta-models/Muse-Glimmer-30B-GGUF}"
PORT="${LLAMA_PORT:-8080}"
HOST="${LLAMA_HOST:-127.0.0.1}"
EXTRA="${LLAMA_EXTRA_ARGS:-}"

find_llama() {
  if command -v llama >/dev/null 2>&1; then
    echo "llama"
    return
  fi
  if command -v llama-server >/dev/null 2>&1; then
    echo "llama-server"
    return
  fi
  if command -v llama-cli >/dev/null 2>&1 && command -v llama-server >/dev/null 2>&1; then
    echo "llama-server"
    return
  fi
  # common local build locations
  for c in \
    "$HOME/llama.cpp/build/bin/llama-server" \
    "$HOME/src/llama.cpp/build/bin/llama-server" \
    "./llama-server"; do
    if [[ -x "$c" ]]; then
      echo "$c"
      return
    fi
  done
  return 1
}

if ! BIN="$(find_llama)"; then
  cat <<'EOF' >&2
llama.cpp server binary not found.

Install options:
  • Official installer (if available):  curl -LsSf https://llama.app/install.sh | sh
  • Build from source: https://github.com/ggml-org/llama.cpp
  • Homebrew (when packaged): brew install llama.cpp

Then re-run: ./scripts/serve-llamacpp.sh
EOF
  exit 1
fi

echo "Using: $BIN"
echo "Repo:  $HF_REPO"
echo "Bind:  http://${HOST}:${PORT}/v1"
echo

# Prefer modern `llama serve -hf …` if the binary is the meta CLI wrapper
if [[ "$(basename "$BIN")" == "llama" ]]; then
  # shellcheck disable=SC2086
  exec llama serve -hf "$HF_REPO" --host "$HOST" --port "$PORT" $EXTRA
fi

# Classic llama-server: try -hf first (newer builds), else tell user to pass -m
set +e
# shellcheck disable=SC2086
"$BIN" -h 2>&1 | grep -q -- '-hf'
HAS_HF=$?
set -e

if [[ $HAS_HF -eq 0 ]]; then
  # shellcheck disable=SC2086
  exec "$BIN" -hf "$HF_REPO" --host "$HOST" --port "$PORT" $EXTRA
fi

cat <<EOF >&2
This llama-server build may not support -hf.

Download a GGUF from:
  https://huggingface.co/${HF_REPO}

Then run:
  $BIN -m /path/to/model.gguf --host ${HOST} --port ${PORT} --port ${PORT}

Or upgrade llama.cpp and re-try this script.
EOF
exit 1
