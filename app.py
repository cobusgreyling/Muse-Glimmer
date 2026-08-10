#!/usr/bin/env python3
"""Muse Glimmer — interactive local agent lab (FastAPI).

Offline-first: scenario playback, benchmarks, memory footprint, reasoning A/B.
Optional live chat against any OpenAI-compatible endpoint (llama.cpp, HF
Endpoints, Together, OpenRouter, etc.).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "7870"))
LIVE_PROVIDER = os.getenv("LIVE_PROVIDER", "").strip() or "custom"


def _normalize_base_url(raw: str) -> str:
    """Ensure OpenAI-compatible root ending in /v1 (no trailing slash)."""
    base = (raw or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/v1"):
        return base
    # HF sometimes paste full chat path
    for suffix in ("/chat/completions", "/models"):
        if base.endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
            break
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _api_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("HF_TOKEN", "").strip()
        or os.getenv("OPENROUTER_API_KEY", "").strip()
    )


OPENAI_BASE_URL = _normalize_base_url(os.getenv("OPENAI_BASE_URL", ""))
OPENAI_API_KEY = _api_key()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()

STATIC_DIR = ROOT / "static"
HEADER_SRC = ROOT / "assets" / "header.jpg"
HEADER_DST = STATIC_DIR / "header.jpg"
MODEL_CARD = ROOT / "data" / "model-card.json"
SCENARIOS = ROOT / "data" / "agent-scenarios.json"
PROMPTS = ROOT / "data" / "prompts.json"

app = FastAPI(
    title="Muse Glimmer Lab",
    description="Interactive companion for Meta's on-device agentic model",
    version="1.1.0",
)


def _ensure_header() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if HEADER_SRC.exists() and (
        not HEADER_DST.exists()
        or HEADER_SRC.stat().st_mtime > HEADER_DST.stat().st_mtime
    ):
        HEADER_DST.write_bytes(HEADER_SRC.read_bytes())


_ensure_header()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing fixture: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _live_configured() -> bool:
    return bool(OPENAI_BASE_URL)


def _live_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    return headers


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0))


def _fetch_models() -> list[dict[str, Any]]:
    if not _live_configured():
        return []
    url = f"{OPENAI_BASE_URL}/models"
    try:
        with _http_client() as client:
            r = client.get(url, headers=_live_headers())
    except httpx.RequestError:
        return []
    if r.status_code >= 400:
        return []
    try:
        body = r.json()
    except json.JSONDecodeError:
        return []
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            out.append({"id": str(item["id"]), "owned_by": item.get("owned_by")})
        elif isinstance(item, str):
            out.append({"id": item, "owned_by": None})
    return out


def _resolve_model(explicit: str | None = None) -> str:
    """Prefer explicit request model, then env, then first /v1/models id."""
    if explicit and explicit.strip():
        return explicit.strip()
    if OPENAI_MODEL:
        return OPENAI_MODEL
    models = _fetch_models()
    if models:
        return models[0]["id"]
    # Last-resort defaults by provider
    if LIVE_PROVIDER in {"hf-endpoint", "huggingface", "hf"}:
        return "meta-models/Muse-Glimmer-30B"
    return "muse-glimmer"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    reasoning_strength: str = Field(default="medium", pattern="^(low|medium|high)$")
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=16, le=4096)
    model: str | None = Field(default=None, max_length=256)


class FootprintRequest(BaseModel):
    device_ram_gb: float = Field(default=32, ge=8, le=192)
    quant_bits: float = Field(default=4.0, ge=2.0, le=16.0)
    include_drafter: bool = True
    include_vision: bool = True
    kv_context: int = Field(default=8192, ge=512, le=131072)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model": "Muse Glimmer 30B",
        "version": "1.1.0",
        "demo_mode": True,
        "live_configured": _live_configured(),
        "live": {
            "provider": LIVE_PROVIDER if _live_configured() else None,
            "base_url": OPENAI_BASE_URL or None,
            "model": OPENAI_MODEL or ("(auto)" if _live_configured() else None),
            "auth": bool(OPENAI_API_KEY),
        },
        "endpoints": {
            "model_card": "/api/model-card",
            "scenarios": "/api/scenarios",
            "scenario": "/api/scenarios/{id}",
            "benchmarks": "/api/benchmarks",
            "prompts": "/api/prompts",
            "footprint": "/api/footprint",
            "chat": "/api/chat",
            "live_probe": "/api/live/probe",
            "live_models": "/api/live/models",
        },
    }


@app.get("/api/model-card")
def model_card() -> dict[str, Any]:
    return _load_json(MODEL_CARD)


@app.get("/api/scenarios")
def list_scenarios() -> dict[str, Any]:
    data = _load_json(SCENARIOS)
    summary = [
        {
            "id": s["id"],
            "title": s["title"],
            "tagline": s["tagline"],
            "highlight": s.get("highlight"),
            "user_prompt": s["user_prompt"],
            "metrics": s.get("metrics"),
        }
        for s in data["scenarios"]
    ]
    return {"scenarios": summary}


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict[str, Any]:
    data = _load_json(SCENARIOS)
    for s in data["scenarios"]:
        if s["id"] == scenario_id:
            return s
    raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")


@app.get("/api/benchmarks")
def benchmarks() -> dict[str, Any]:
    card = _load_json(MODEL_CARD)
    return {
        "model": card["full_name"],
        "comparators": card["comparators"],
        "benchmarks": card["benchmarks"],
        "disclaimer": card["disclaimer"],
        "source": card["hub"]["hf_blog"],
    }


@app.get("/api/prompts")
def prompts() -> dict[str, Any]:
    return _load_json(PROMPTS)


@app.post("/api/footprint")
def footprint(req: FootprintRequest) -> dict[str, Any]:
    """Rough on-device memory model for teaching the 24–32 GB story.

    Not a substitute for real profiling — educational envelope only.
    """
    lm_gb = (30.0e9 * req.quant_bits) / 8.0 / (1024**3)
    vision_gb = 3.8 if req.include_vision else 0.0
    drafter_gb = 1.6 if req.include_drafter else 0.0
    kv_gb = (req.kv_context / 8192.0) * (1.2 if req.quant_bits <= 4.5 else 2.4)
    total = lm_gb + vision_gb + drafter_gb + kv_gb
    headroom = req.device_ram_gb - total
    fits = headroom >= 1.5
    tier = (
        "comfortable"
        if headroom >= 6
        else "tight"
        if fits
        else "oversubscribed"
    )
    return {
        "inputs": req.model_dump(),
        "breakdown_gb": {
            "language_model": round(lm_gb, 2),
            "perception_encoder": round(vision_gb, 2),
            "dflash_drafter": round(drafter_gb, 2),
            "kv_cache_est": round(kv_gb, 2),
            "total": round(total, 2),
        },
        "device_ram_gb": req.device_ram_gb,
        "headroom_gb": round(headroom, 2),
        "fits": fits,
        "tier": tier,
        "narrative": _footprint_narrative(tier, req.device_ram_gb, total),
    }


def _footprint_narrative(tier: str, device: float, total: float) -> str:
    if tier == "comfortable":
        return (
            f"~{total:.1f} GB estimated load on a {device:.0f} GB envelope leaves room "
            "for OS, browser, and agent tools — the practical always-on local agent setup."
        )
    if tier == "tight":
        return (
            f"~{total:.1f} GB on {device:.0f} GB is workable if you lower context, "
            "drop the drafter, or use a leaner quant. Still local — just less headroom."
        )
    return (
        f"~{total:.1f} GB exceeds a {device:.0f} GB envelope. Drop bits (e.g. Q4), "
        "shrink context, or disable vision/drafter — or use a larger GPU/unified-memory box."
    )


@app.get("/api/live/models")
def live_models() -> dict[str, Any]:
    if not _live_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "title": "Live endpoint not configured",
                "message": "Set OPENAI_BASE_URL in .env",
                "fix": "./scripts/configure-live.sh llamacpp  # or hf-endpoint",
            },
        )
    models = _fetch_models()
    return {
        "base_url": OPENAI_BASE_URL,
        "provider": LIVE_PROVIDER,
        "models": models,
        "resolved_default": _resolve_model(),
    }


@app.get("/api/live/probe")
def live_probe(
    ping: bool = Query(
        default=True,
        description="If true, send a 1-token chat completion after listing models",
    ),
) -> dict[str, Any]:
    """Reachability check for llama.cpp / HF / any OpenAI-compatible server."""
    if not _live_configured():
        return {
            "ok": False,
            "configured": False,
            "title": "Live endpoint not configured",
            "message": "Demo mode works offline. For live Muse Glimmer, set OPENAI_BASE_URL.",
            "fix": "./scripts/configure-live.sh llamacpp   # or: hf-endpoint",
            "docs": "docs/LIVE.md",
        }

    result: dict[str, Any] = {
        "ok": False,
        "configured": True,
        "provider": LIVE_PROVIDER,
        "base_url": OPENAI_BASE_URL,
        "auth": bool(OPENAI_API_KEY),
        "models": [],
        "model": None,
        "latency_models_s": None,
        "latency_chat_s": None,
        "chat_preview": None,
        "error": None,
        "fix": None,
    }

    t0 = time.perf_counter()
    try:
        with _http_client() as client:
            r = client.get(f"{OPENAI_BASE_URL}/models", headers=_live_headers())
    except httpx.RequestError as exc:
        result["error"] = f"Cannot reach {OPENAI_BASE_URL}/models: {exc}"
        result["fix"] = (
            "Start the server (./scripts/serve-llamacpp.sh) or check HF endpoint status."
        )
        return result

    result["latency_models_s"] = round(time.perf_counter() - t0, 3)
    if r.status_code >= 400:
        result["error"] = f"GET /models → HTTP {r.status_code}: {r.text[:400]}"
        if r.status_code in (401, 403):
            result["fix"] = "Set OPENAI_API_KEY or HF_TOKEN in .env"
        else:
            result["fix"] = "Confirm OPENAI_BASE_URL ends with /v1 and the server is ready."
        return result

    try:
        body = r.json()
        data = body.get("data") if isinstance(body, dict) else []
        models = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    models.append(str(item["id"]))
                elif isinstance(item, str):
                    models.append(item)
        result["models"] = models
    except json.JSONDecodeError:
        result["error"] = "Models response was not JSON"
        result["fix"] = "Is this an OpenAI-compatible server?"
        return result

    model = _resolve_model()
    result["model"] = model

    if not ping:
        result["ok"] = True
        return result

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: muse-ready"}],
        "max_tokens": 16,
        "temperature": 0,
    }
    t1 = time.perf_counter()
    try:
        with _http_client() as client:
            cr = client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=_live_headers(),
                json=payload,
            )
    except httpx.RequestError as exc:
        result["error"] = f"Chat probe failed: {exc}"
        result["fix"] = "Models listed OK but completions failed — check server logs."
        return result

    result["latency_chat_s"] = round(time.perf_counter() - t1, 3)
    if cr.status_code >= 400:
        result["error"] = f"POST /chat/completions → HTTP {cr.status_code}: {cr.text[:500]}"
        result["fix"] = (
            "Model id mismatch? Leave OPENAI_MODEL empty or set it to an id from /v1/models."
        )
        return result

    try:
        cbody = cr.json()
        content = cbody["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        content = cr.text[:300]

    result["chat_preview"] = content
    result["ok"] = True
    return result


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    """Optional live chat via OpenAI-compatible /v1/chat/completions."""
    if not _live_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "title": "Live endpoint not configured",
                "message": "Demo mode works offline. For live Muse Glimmer, set OPENAI_BASE_URL.",
                "fix": "./scripts/configure-live.sh llamacpp  # or hf-endpoint — see docs/LIVE.md",
            },
        )

    if not OPENAI_BASE_URL.startswith("http"):
        raise HTTPException(status_code=400, detail="OPENAI_BASE_URL must be http(s)")

    model = _resolve_model(req.model)
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = _live_headers()

    payload: dict[str, Any] = {
        "model": model,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "reasoning_strength": req.reasoning_strength,
    }

    t0 = time.perf_counter()
    try:
        with _http_client() as client:
            r = client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "title": "Could not reach endpoint",
                "message": str(exc),
                "fix": "Check OPENAI_BASE_URL and that llama.cpp / HF endpoint is up. See docs/LIVE.md",
            },
        ) from exc

    latency_s = time.perf_counter() - t0
    if r.status_code >= 400:
        # Retry without reasoning_strength for strict OpenAI-compatible servers
        if r.status_code in (400, 422):
            payload.pop("reasoning_strength", None)
            with _http_client() as client:
                r = client.post(url, headers=headers, json=payload)
            latency_s = time.perf_counter() - t0
        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "title": "Endpoint error",
                    "message": r.text[:800],
                    "fix": "Confirm model id via GET /api/live/models and docs/LIVE.md",
                },
            )

    body = r.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = json.dumps(body)[:2000]

    return {
        "content": content,
        "latency_s": round(latency_s, 3),
        "model": model,
        "provider": LIVE_PROVIDER,
        "base_url": OPENAI_BASE_URL,
        "reasoning_strength": req.reasoning_strength,
        "raw_usage": body.get("usage"),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
