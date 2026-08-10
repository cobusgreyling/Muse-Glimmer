# Live chat: llama.cpp & Hugging Face

The lab is **offline-first**. Live chat is optional and talks to any **OpenAI-compatible** `POST /v1/chat/completions` server — including:

- **llama.cpp** (`llama serve` / `llama-server`)
- **Hugging Face Inference Endpoints**
- OpenRouter, Together, Fireworks, vLLM, SGLang, LM Studio, Ollama (OpenAI mode), etc.

## Quick path (recommended)

### A) Local llama.cpp (true on-device)

**Terminal 1 — serve Muse Glimmer GGUF**

```bash
# Install llama.cpp once: https://github.com/ggml-org/llama.cpp
# or: curl -LsSf https://llama.app/install.sh | sh

./scripts/serve-llamacpp.sh
# defaults: meta-models/Muse-Glimmer-30B-GGUF on port 8080
```

**Terminal 2 — wire the lab**

```bash
./scripts/configure-live.sh llamacpp
./run.sh
# open http://127.0.0.1:7870 → Live chat → Probe endpoint
```

Equivalent `.env`:

```bash
OPENAI_BASE_URL=http://127.0.0.1:8080/v1
OPENAI_API_KEY=   # often empty for local
OPENAI_MODEL=     # leave empty to auto-pick from /v1/models
LIVE_PROVIDER=llamacpp
```

### B) Hugging Face Inference Endpoint (managed GPU)

1. Create an endpoint for [`meta-models/Muse-Glimmer-30B`](https://endpoints.huggingface.co/huggingface/new/meta-models/Muse-Glimmer-30B) and wait until **Running**.
2. Copy the endpoint URL (no trailing path noise) and create a token with inference access.

```bash
export HF_ENDPOINT_URL="https://XXXX.us-east-1.aws.endpoints.huggingface.cloud"
export HF_TOKEN="hf_..."
# optional if the served model name differs:
# export OPENAI_MODEL="meta-models/Muse-Glimmer-30B"

./scripts/configure-live.sh hf-endpoint
./scripts/probe-live.sh
./run.sh
```

Equivalent `.env`:

```bash
OPENAI_BASE_URL=https://XXXX.us-east-1.aws.endpoints.huggingface.cloud/v1
OPENAI_API_KEY=hf_...
OPENAI_MODEL=meta-models/Muse-Glimmer-30B
LIVE_PROVIDER=hf-endpoint
```

HF also accepts `HF_TOKEN` — the lab treats it as a fallback for `OPENAI_API_KEY`.

### C) OpenRouter / cloud OpenAI-compatible

```bash
export OPENROUTER_API_KEY="sk-or-..."
./scripts/configure-live.sh openrouter
# edit .env OPENAI_MODEL to the exact Muse Glimmer id on that provider
./run.sh
```

---

## Lab APIs used by live mode

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Whether `OPENAI_BASE_URL` is set |
| `GET` | `/api/live/probe` | Reachability + `/v1/models` + optional tiny completion |
| `GET` | `/api/live/models` | List models from the endpoint |
| `POST` | `/api/chat` | Proxied chat completions |

Probe example:

```bash
curl -s http://127.0.0.1:7870/api/live/probe | python3 -m json.tool
```

---

## URL rules

The lab normalizes base URLs:

| You set | Lab uses |
|---------|----------|
| `http://127.0.0.1:8080` | `http://127.0.0.1:8080/v1` |
| `http://127.0.0.1:8080/v1` | unchanged |
| `https://xxx.endpoints.huggingface.cloud` | `…/v1` |
| `https://xxx.endpoints.huggingface.cloud/v1/` | strips trailing slash |

Chat hits: `{base}/chat/completions`  
Models hit: `{base}/models`

---

## Model id tips

- **llama.cpp**: often the GGUF filename stem or a short alias. Easiest: leave `OPENAI_MODEL` empty and let the lab **auto-pick** the first `/v1/models` entry after probe.
- **HF Endpoint**: usually `meta-models/Muse-Glimmer-30B` or the name shown on the endpoint Overview → use **exactly** what `/v1/models` returns.
- **Mismatch symptom**: 404 / “model not found” on chat. Fix: Live tab → refresh models → pick the listed id, or re-run probe.

---

## llama.cpp extras

Speculative decoding (DFlash) when available:

```bash
LLAMA_EXTRA_ARGS='--spec-type draft-dflash --spec-draft-n-max 15' \
  ./scripts/serve-llamacpp.sh
```

Custom port / repo:

```bash
LLAMA_PORT=8081 \
LLAMA_HF_REPO=meta-models/Muse-Glimmer-30B-GGUF \
  ./scripts/serve-llamacpp.sh
```

Then:

```bash
OPENAI_BASE_URL=http://127.0.0.1:8081/v1 ./scripts/configure-live.sh llamacpp
```

Unsloth quants: set `LLAMA_HF_REPO=unsloth/Muse-Glimmer-30B-GGUF`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Probe: connection refused | Start llama/HF server first; check port |
| 401 / unauthorized | Set `OPENAI_API_KEY` or `HF_TOKEN` |
| Model not found | Empty `OPENAI_MODEL` + probe, or set id from `/api/live/models` |
| TLS errors to HF | Corporate proxy; try updated `certifi` / system certs |
| Slow first token | Cold HF replica or huge GGUF load — wait for “running” / model load log |
| Reasoning field rejected | Lab auto-retries without `reasoning_strength` |

---

## Security

- Never commit `.env` or paste tokens into issues.
- Prefer short-lived HF tokens with minimal scopes.
- Local llama.cpp on `127.0.0.1` only unless you intentionally bind `0.0.0.0` and understand exposure.
