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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "7870"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "meta-models/Muse-Glimmer-30B").strip()

STATIC_DIR = ROOT / "static"
HEADER_SRC = ROOT / "assets" / "header.jpg"
HEADER_DST = STATIC_DIR / "header.jpg"
MODEL_CARD = ROOT / "data" / "model-card.json"
SCENARIOS = ROOT / "data" / "agent-scenarios.json"
PROMPTS = ROOT / "data" / "prompts.json"

app = FastAPI(
    title="Muse Glimmer Lab",
    description="Interactive companion for Meta's on-device agentic model",
    version="1.0.0",
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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    reasoning_strength: str = Field(default="medium", pattern="^(low|medium|high)$")
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=16, le=4096)


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
        "demo_mode": True,
        "live_configured": _live_configured(),
        "live": {
            "base_url": OPENAI_BASE_URL or None,
            "model": OPENAI_MODEL if _live_configured() else None,
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
    # 30B params * bits / 8 → bytes, then GB
    lm_gb = (30.0e9 * req.quant_bits) / 8.0 / (1024**3)
    vision_gb = 3.8 if req.include_vision else 0.0  # ~2B PE + activations ballpark
    drafter_gb = 1.6 if req.include_drafter else 0.0
    # crude KV: layers * heads_factor * context * bytes; keep simple
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


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    """Optional live chat via OpenAI-compatible /v1/chat/completions."""
    if not _live_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "title": "Live endpoint not configured",
                "message": "Demo mode works offline. For live Muse Glimmer, set OPENAI_BASE_URL.",
                "fix": "cp .env.example .env  # then set OPENAI_BASE_URL + OPENAI_MODEL (+ key if needed)",
            },
        )

    url = f"{OPENAI_BASE_URL}/chat/completions"
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="OPENAI_BASE_URL must be http(s)")

    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"

    # Many local stacks ignore custom fields; include reasoning_strength when supported.
    payload: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": [m.model_dump() for m in req.messages],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "reasoning_strength": req.reasoning_strength,
    }

    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "title": "Could not reach endpoint",
                "message": str(exc),
                "fix": "Check OPENAI_BASE_URL (e.g. http://127.0.0.1:8080/v1) and that the server is up.",
            },
        ) from exc

    latency_s = time.perf_counter() - t0
    if r.status_code >= 400:
        # Retry without reasoning_strength for strict OpenAI-compatible servers
        if r.status_code in (400, 422) and "reasoning" in r.text.lower():
            payload.pop("reasoning_strength", None)
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, headers=headers, json=payload)
            latency_s = time.perf_counter() - t0
        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail={
                    "title": "Endpoint error",
                    "message": r.text[:800],
                    "fix": "Confirm model id and that the server exposes /v1/chat/completions.",
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
        "model": OPENAI_MODEL,
        "reasoning_strength": req.reasoning_strength,
        "raw_usage": body.get("usage"),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
