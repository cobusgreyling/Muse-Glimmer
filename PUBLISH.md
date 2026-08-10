# Publish checklist — Muse Glimmer (standalone)

Use this when shipping or refreshing **https://github.com/cobusgreyling/Muse-Glimmer**.

## 1. Repo identity (GitHub SEO)

- [ ] **Name** includes the product: `Muse-Glimmer` (done)
- [ ] **Description** has search phrases: open-weight, 30B, on-device, agentic, Apache 2.0, Meta
- [ ] **Homepage** → model card or research blog  
  `https://huggingface.co/meta-models/Muse-Glimmer-30B`
- [ ] **Public** visibility
- [ ] **Topics** (12 max practical):  
  `muse-glimmer` `meta` `local-llm` `agentic-ai` `on-device-ai` `open-weights` `multimodal` `function-calling` `llama-cpp` `agents` `openai-compatible` `apache-2`
- [ ] **README H1** matches announcement title (search + social unfurl)
- [ ] **Header image** at top of README (`assets/header.jpg`) — ~1200–1600px wide, high contrast
- [ ] **Keywords line** early in README (done)
- [ ] No secrets in tree (`.env` gitignored; only `.env.example`)

```bash
# re-apply topics anytime
gh repo edit cobusgreyling/Muse-Glimmer \
  --description "Introducing Muse Glimmer: open-weight 30B agentic multimodal model that runs on your device (Meta). Interactive local agent lab + guide. Apache 2.0 · on-device AI · function calling" \
  --homepage "https://huggingface.co/meta-models/Muse-Glimmer-30B" \
  --add-topic muse-glimmer --add-topic meta --add-topic local-llm \
  --add-topic agentic-ai --add-topic on-device-ai --add-topic open-weights \
  --add-topic multimodal --add-topic function-calling --add-topic llama-cpp \
  --add-topic agents --add-topic openai-compatible --add-topic apache-2
```

## 2. Content quality gate

- [ ] `README.md` — 30s start works from a clean clone
- [ ] `BLOG.md` — long-form story, primary links, disclaimer
- [ ] `docs/LIVE.md` — llama.cpp + HF Endpoint live chat
- [ ] Lab offline tabs work with **no** `OPENAI_BASE_URL`
- [ ] Live tab: **Probe endpoint** + chat when configured
- [ ] License: code MIT; weights Apache 2.0 (Meta) called out
- [ ] Independent-companion disclaimer present

## 3. Smoke tests (before every release push)

```bash
# Offline lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py &
sleep 1
curl -sf http://127.0.0.1:7870/api/health | python3 -m json.tool
curl -sf http://127.0.0.1:7870/api/scenarios | python3 -c "import sys,json; assert len(json.load(sys.stdin)['scenarios'])>=4"
curl -sf -X POST http://127.0.0.1:7870/api/footprint \
  -H 'Content-Type: application/json' \
  -d '{"device_ram_gb":32,"quant_bits":4}' | python3 -m json.tool
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7870/
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7870/static/header.jpg

# Optional live (server must already be up)
./scripts/configure-live.sh llamacpp   # or: hf-endpoint
./scripts/probe-live.sh
```

Docker:

```bash
docker compose up --build -d
curl -sf http://127.0.0.1:7870/api/health
docker compose down
```

## 4. Live chat wiring checklist

See **[docs/LIVE.md](docs/LIVE.md)** for full detail.

| Path | Configure | Serve |
|------|-----------|--------|
| **llama.cpp** | `./scripts/configure-live.sh llamacpp` | `./scripts/serve-llamacpp.sh` |
| **HF Inference Endpoint** | `./scripts/configure-live.sh hf-endpoint` | Create endpoint in HF UI |
| **OpenRouter / Together / Fireworks** | `./scripts/configure-live.sh openrouter` (edit model) | Hosted |

- [ ] `.env` not committed
- [ ] `GET /api/live/probe` returns `ok: true`
- [ ] Live Chat tab replies with non-empty content
- [ ] Model id matches `/v1/models` (or lab auto-picked it)

## 5. Git push

```bash
git status
git add -A
git commit -m "Describe the user-facing change"
git push origin main
```

Never force-push `main` unless intentional recovery.

## 6. Amplify (optional, post-publish)

- [ ] Pin the repo on your GitHub profile while launch is hot
- [ ] Cross-link from blog / X / LinkedIn with exact title phrase
- [ ] Reply in [r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/) / HF discussions with the clone URL (no spam)
- [ ] Add a short GIF of the **Agent loops** tab in README later
- [ ] Star the official HF model card so your lab sits in the same discovery graph

## 7. Version hygiene

- [ ] Bump `version` in `app.py` FastAPI metadata when API changes
- [ ] Keep benchmark numbers sourced to HF/Meta launch posts; date the disclaimer
- [ ] If Meta renames Hub repos, update `data/model-card.json` + LIVE docs same day

---

**Done means:** clean clone → offline lab works → optional live path documented and probeable → GitHub metadata is searchable.
