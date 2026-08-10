# Introducing Muse Glimmer: An Open Agentic Model That Runs on Your Device

<p align="center">
  <img src="assets/header.jpg" alt="Muse Glimmer — open agentic local AI model network visualization" width="100%" />
</p>

<p align="center">
  <strong>Meta Muse Glimmer 30B</strong> · open-weight · Apache 2.0 · on-device agents · multimodal<br/>
  Interactive lab + deep-dive guide for the local agentic model released 10 August 2026
</p>

<p align="center">
  <a href="https://huggingface.co/meta-models/Muse-Glimmer-30B">Weights</a> ·
  <a href="https://research.meta.ai/blog/introducing-muse-glimmer-open-agentic-model">Research blog</a> ·
  <a href="https://huggingface.co/blog/muse-glimmer">HF day-0 guide</a> ·
  <a href="BLOG.md">Article in this repo</a>
</p>

---

**Muse Glimmer** is Meta Superintelligence Labs’ open-weight **30-billion-parameter agentic multimodal** model optimized for **always-on local agent workflows**. It runs on consumer hardware (Mac / PC with a performant GPU or large unified memory) after ~4-bit quantization (~**under 20&nbsp;GB** for the LM), with tool calling, failure recovery, controllable reasoning, and a 2B perception encoder for images and video frames.

This repository is a **search-friendly companion**: a long-form intro ([`BLOG.md`](BLOG.md)) plus an **offline-first interactive lab** so you can feel agent loops, benchmarks, and memory envelopes before you download the weights.

**Keywords:** Muse Glimmer, Meta AI, open agentic model, local LLM, on-device AI, Apache 2.0, function calling, OpenClaw, llama.cpp, GGUF, multimodal agents, DFlash, SWE-Bench, MCP Atlas

---

## The one-liner

> **An open agentic model that runs on your device** — Apache 2.0 weights, dense 30B (2B perception + 28B decoder), ~4-bit under ~20&nbsp;GB, trained for tool loops, failure recovery, and controllable reasoning.

| | |
|--|--|
| **Model** | Muse Glimmer 30B (dense multimodal) |
| **Weights** | [meta-models/Muse-Glimmer-30B](https://huggingface.co/meta-models/Muse-Glimmer-30B) |
| **License** | Apache 2.0 |
| **Released** | 10 August 2026 |
| **This repo** | Offline-first lab + optional live OpenAI-compatible chat |

---

## 30-second start

```bash
git clone https://github.com/cobusgreyling/Muse-Glimmer.git
cd Muse-Glimmer

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:7870**

Or:

```bash
./run.sh
```

### Docker

```bash
docker compose up --build
# → http://127.0.0.1:7870
```

No GPU. No API key. Scenario playback, benchmarks, and memory sizing work **offline**.

### Optional live chat (llama.cpp / Hugging Face)

Full guide: **[docs/LIVE.md](docs/LIVE.md)** · Publish checklist: **[PUBLISH.md](PUBLISH.md)**

**A) On-device with llama.cpp**

```bash
# Terminal 1 — serve GGUF (needs llama.cpp installed)
./scripts/serve-llamacpp.sh

# Terminal 2 — wire lab + run
./scripts/configure-live.sh llamacpp
./run.sh
# → Live chat tab → Probe endpoint → Send
```

**B) Hugging Face Inference Endpoint**

```bash
export HF_ENDPOINT_URL="https://XXXX.region.cloud.endpoints.huggingface.cloud"
export HF_TOKEN="hf_…"
./scripts/configure-live.sh hf-endpoint
./scripts/probe-live.sh   # lab must be running for full probe
./run.sh
```

Or hand-edit `.env` (see [`.env.example`](.env.example)). Leave `OPENAI_MODEL` empty to auto-pick from `GET /v1/models`.

---

## What the lab shows

| Tab | What you learn |
|-----|----------------|
| **Agent loops** | Multi-step local agents: tools, **failure recovery**, coding fix, multimodal tool call, reasoning low vs high |
| **Benchmarks** | Interactive scoreboard vs Gemma4-31B & Qwen3.6-27B (published launch numbers) |
| **Memory** | Footprint calculator — why ~4-bit + 24–32&nbsp;GB is the practical envelope |
| **Live chat** | Optional `/v1/chat/completions` against *your* Muse Glimmer endpoint |

### Scenario highlights

1. **Home Assistant dashboard** — discover → 401 → recover token → build → deploy  
2. **Coding fix** — red test → patch → green  
3. **Multimodal tools** — image city → `weather.get` → clothing advice  
4. **Reasoning A/B** — same architecture question, low vs high effort  

---

## Why Muse Glimmer matters

Most “local models” are chatty generalists squeezed onto a laptop. **Muse Glimmer** is aimed at a harder job:

- **Always-on agents** that own multi-step work on-device  
- **Privacy** — contracts, code, home automation stay local  
- **Cost** — no per-token meter for every tool hop  
- **Latency** — no round-trip to a distant region for every thought  

Meta’s claim (launch materials): strong agentic scores in the ~27–31B class, with deliberate training for **function calling**, **long horizons**, and **diagnose-and-retry** when tools fail — not just next-token fluency.

Details and nuance: **[BLOG.md](BLOG.md)**.

---

## Architecture (cheat sheet)

```text
┌─────────────────────────────────────────────────────────┐
│  Muse Glimmer 30B (dense multimodal)                    │
│                                                         │
│   Perception Encoder (~2B ViT-style)                    │
│        │  images / video frames                         │
│        ▼                                                │
│   Text decoder (~28B)                                   │
│     · 52 layers · (SWA×3 + Full)×13                     │
│     · GQA (16 Q per KV) · Q-K norm                      │
│                                                         │
│   Optional: DFlash speculative drafter (block proposals)│
└─────────────────────────────────────────────────────────┘
         │
         ▼  ~4-bit quant  →  LM ≲ 20 GB
   24–32 GB device envelope (KV + vision + drafter headroom)
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Lab UI |
| `GET` | `/api/health` | Demo / live status |
| `GET` | `/api/model-card` | Specs, hub links, capabilities |
| `GET` | `/api/scenarios` | Scenario list |
| `GET` | `/api/scenarios/{id}` | Full agent transcript fixture |
| `GET` | `/api/benchmarks` | Published comparison rows |
| `GET` | `/api/prompts` | Example prompts |
| `POST` | `/api/footprint` | Memory envelope estimate |
| `GET` | `/api/live/probe` | Reachability + models + tiny completion |
| `GET` | `/api/live/models` | List models from configured endpoint |
| `POST` | `/api/chat` | Live OpenAI-compatible chat (optional) |

---

## Project layout

```text
Muse-Glimmer/
├── README.md
├── BLOG.md                 # Long-form intro article
├── PUBLISH.md              # Standalone repo publish checklist
├── docs/LIVE.md            # llama.cpp + HF live wiring
├── app.py                  # FastAPI lab
├── scripts/
│   ├── configure-live.sh   # .env presets (llamacpp | hf-endpoint | openrouter)
│   ├── serve-llamacpp.sh   # start llama OpenAI server
│   └── probe-live.sh       # health-check live endpoint
├── requirements.txt
├── run.sh
├── .env.example
├── assets/header.jpg
├── data/
│   ├── model-card.json
│   ├── agent-scenarios.json
│   └── prompts.json
└── static/                 # UI
```

---

## Run Muse Glimmer itself (not just the lab)

| Path | Link / note |
|------|-------------|
| Full weights | [Hugging Face](https://huggingface.co/meta-models/Muse-Glimmer-30B) |
| GGUF | [meta GGUF](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF) · [Unsloth](https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF) |
| Research blog | [research.meta.ai](https://research.meta.ai/blog/introducing-muse-glimmer-open-agentic-model) |
| HF day-0 guide | [huggingface.co/blog/muse-glimmer](https://huggingface.co/blog/muse-glimmer) |
| transformers / llama.cpp / vLLM | Day-0 support called out in HF blog |
| Cloud | Together · Fireworks · OpenRouter · HF Inference Endpoints |

```python
# transformers sketch (needs sufficient VRAM / offload)
from transformers import AutoProcessor, AutoModelForMultimodalLM

MODEL_ID = "meta-models/Muse-Glimmer-30B"
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForMultimodalLM.from_pretrained(
    MODEL_ID, dtype="auto", device_map="auto"
)
```

---

## Stack

FastAPI · Uvicorn · vanilla HTML/CSS/JS · offline JSON fixtures · optional httpx → OpenAI-compatible API

---

## Disclaimer

This lab is an **independent educational companion**, not an official Meta product.  
Agent timeline transcripts are **illustrative fixtures** for teaching agent behavior.  
Benchmark numbers are taken from public launch materials (Hugging Face / Meta, August 2026).  
Model weights remain under Meta’s **Apache 2.0** release; this repo’s code is MIT.

---

## License

- Lab code & fixtures: [MIT](LICENSE)  
- Muse Glimmer weights: Apache 2.0 (Meta)
