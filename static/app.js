/* Muse Glimmer Lab — offline-first UI */
(() => {
  "use strict";

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const state = {
    scenarios: [],
    activeId: null,
    scenario: null,
    stepIdx: 0,
    playing: false,
    playTimer: null,
    benchmarks: null,
    benchCat: "all",
    chat: [],
  };

  async function api(path, opts) {
    const r = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
      ...opts,
    });
    const text = await r.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }
    if (!r.ok) {
      const err = new Error(data?.detail?.message || data?.detail || r.statusText);
      err.detail = data?.detail;
      err.status = r.status;
      throw err;
    }
    return data;
  }

  /* ── Tabs ─────────────────────────────────────────────── */
  function initTabs() {
    $$(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".tab").forEach((b) => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-selected", b === btn ? "true" : "false");
        });
        $$(".tab-panel").forEach((p) => {
          p.hidden = p.id !== `panel-${btn.dataset.tab}`;
          p.classList.toggle("active", !p.hidden);
        });
      });
    });
  }

  /* ── Health ───────────────────────────────────────────── */
  async function loadHealth() {
    try {
      const h = await api("/api/health");
      const badge = $("#liveBadge");
      badge.classList.remove("ok", "warn");
      if (h.live_configured) {
        badge.textContent = `live · ${h.live.provider || "endpoint"}`;
        badge.classList.add("ok");
        $("#chatStatus").textContent = `Configured → ${h.live.base_url} · model ${h.live.model}`;
        $("#probeResult").textContent = "Configured — click Probe endpoint to verify.";
      } else {
        badge.textContent = "offline demo";
        badge.classList.add("warn");
        $("#chatStatus").textContent =
          "No OPENAI_BASE_URL — Agent loops work offline. See docs/LIVE.md.";
        $("#probeResult").textContent =
          "Not configured. ./scripts/configure-live.sh llamacpp  (or hf-endpoint)";
      }
    } catch {
      $("#liveBadge").textContent = "server offline?";
    }
  }

  /* ── Scenarios ────────────────────────────────────────── */
  async function loadScenarios() {
    const data = await api("/api/scenarios");
    state.scenarios = data.scenarios;
    const list = $("#scenarioList");
    list.innerHTML = "";
    data.scenarios.forEach((s, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "scenario-btn" + (i === 0 ? " active" : "");
      btn.innerHTML = `<strong>${escapeHtml(s.title)}</strong><span>${escapeHtml(s.tagline)}</span>`;
      btn.addEventListener("click", () => selectScenario(s.id));
      list.appendChild(btn);
    });
    if (data.scenarios[0]) selectScenario(data.scenarios[0].id);
  }

  async function selectScenario(id) {
    stopPlay();
    state.activeId = id;
    state.stepIdx = 0;
    $$(".scenario-btn").forEach((b, i) => {
      b.classList.toggle("active", state.scenarios[i]?.id === id);
    });
    const s = await api(`/api/scenarios/${id}`);
    state.scenario = s;
    $("#scTitle").textContent = s.title;
    $("#scTagline").textContent = s.tagline;
    $("#scPrompt").textContent = s.user_prompt;
    const chips = $("#scChips");
    chips.innerHTML = "";
    ["highlight", "reasoning_strength"].forEach((k) => {
      if (!s[k] || s[k] === "compare") return;
      const c = document.createElement("span");
      c.className = "chip active";
      c.textContent = s[k].replace(/_/g, " ");
      c.style.cursor = "default";
      chips.appendChild(c);
    });
    if (s.highlight === "reasoning_control") {
      const c = document.createElement("span");
      c.className = "chip active";
      c.textContent = "low vs high";
      c.style.cursor = "default";
      chips.appendChild(c);
    }
    $("#timeline").innerHTML = "";
    const m = $("#scMetrics");
    if (s.metrics) {
      m.hidden = false;
      m.innerHTML = `
        <span>tools <strong>${s.metrics.tool_calls}</strong></span>
        <span>recoveries <strong>${s.metrics.recoveries}</strong></span>
        <span>wall <strong>${s.metrics.wall_s}s</strong></span>
        <span>on-device <strong>${s.metrics.on_device ? "yes" : "no"}</strong></span>`;
    } else {
      m.hidden = true;
    }
    $("#playBtn").disabled = false;
    $("#stepBtn").disabled = false;
    $("#resetBtn").disabled = false;
  }

  function renderStep(step) {
    const el = document.createElement("div");
    el.className = `step ${step.role}`;
    let roleLabel = step.role.replace(/_/g, " ");
    let body = "";
    if (step.role === "tool_call") {
      roleLabel = "tool call";
      body = `<div class="step-tool">${escapeHtml(step.name)}</div>
        <div class="step-body">args</div>
        <pre>${escapeHtml(JSON.stringify(step.args, null, 2))}</pre>
        <div class="step-body" style="margin-top:0.4rem">result</div>
        <pre>${escapeHtml(JSON.stringify(step.result, null, 2))}</pre>`;
    } else {
      body = `<div class="step-body">${escapeHtml(step.text || "")}</div>`;
    }
    el.innerHTML = `<div class="step-role">${roleLabel}</div>${body}`;
    $("#timeline").appendChild(el);
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderCompareVariants() {
    const v = state.scenario?.variants;
    if (!v) return;
    ["low", "high"].forEach((k) => {
      const el = document.createElement("div");
      el.className = "step final";
      el.innerHTML = `
        <div class="step-role">reasoning · ${k} · ${v[k].wall_s}s</div>
        <div class="step-body">${escapeHtml(v[k].text)}</div>`;
      $("#timeline").appendChild(el);
    });
  }

  function nextStep() {
    const s = state.scenario;
    if (!s) return false;
    const steps = s.steps || [];
    if (state.stepIdx >= steps.length) return false;
    const step = steps[state.stepIdx];
    renderStep(step);
    state.stepIdx += 1;
    // After final step on compare scenario, show both variants
    if (
      state.stepIdx >= steps.length &&
      s.variants &&
      s.highlight === "reasoning_control"
    ) {
      renderCompareVariants();
    }
    return state.stepIdx < steps.length;
  }

  function stopPlay() {
    state.playing = false;
    if (state.playTimer) {
      clearTimeout(state.playTimer);
      state.playTimer = null;
    }
    $("#playBtn").textContent = "▶ Play scenario";
  }

  function playLoop() {
    if (!state.playing) return;
    const more = nextStep();
    if (!more) {
      stopPlay();
      return;
    }
    const mult = parseFloat($("#playSpeed").value) || 1;
    const base = 700;
    state.playTimer = setTimeout(playLoop, base * mult);
  }

  function initScenarioControls() {
    $("#playBtn").addEventListener("click", () => {
      if (state.playing) {
        stopPlay();
        return;
      }
      if (!state.scenario) return;
      if (state.stepIdx >= (state.scenario.steps || []).length) {
        $("#timeline").innerHTML = "";
        state.stepIdx = 0;
      }
      state.playing = true;
      $("#playBtn").textContent = "⏸ Pause";
      playLoop();
    });
    $("#stepBtn").addEventListener("click", () => {
      stopPlay();
      if (!nextStep() && state.stepIdx === 0) {
        /* empty */
      }
    });
    $("#resetBtn").addEventListener("click", () => {
      stopPlay();
      state.stepIdx = 0;
      $("#timeline").innerHTML = "";
    });
  }

  /* ── Benchmarks ───────────────────────────────────────── */
  async function loadBenchmarks() {
    const data = await api("/api/benchmarks");
    state.benchmarks = data;
    $("#benchDisclaimer").textContent = data.disclaimer || "";
    renderBenchmarks();
    $$(".filters .chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        $$(".filters .chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.benchCat = chip.dataset.cat;
        renderBenchmarks();
      });
    });
  }

  function renderBenchmarks() {
    const data = state.benchmarks;
    if (!data) return;
    const list = $("#benchList");
    list.innerHTML = "";
    const rows = data.benchmarks.filter(
      (b) => state.benchCat === "all" || b.category === state.benchCat
    );
    rows.forEach((b) => {
      const max = Math.max(b.glimmer, b.gemma4_31b, b.qwen36_27b, 1);
      const winG = b.glimmer >= b.gemma4_31b && b.glimmer >= b.qwen36_27b;
      const el = document.createElement("div");
      el.className = "bench-row";
      el.innerHTML = `
        <header>
          <div>
            <div class="cat">${escapeHtml(b.category)}</div>
            <strong>${escapeHtml(b.name)}</strong>
          </div>
          ${winG ? '<span class="chip active" style="cursor:default">Glimmer leads</span>' : ""}
        </header>
        <div class="bars">
          ${barLine("Muse Glimmer", b.glimmer, max, "glimmer", winG)}
          ${barLine("Gemma4-31B", b.gemma4_31b, max, "gemma", false)}
          ${barLine("Qwen3.6-27B", b.qwen36_27b, max, "qwen", false)}
        </div>`;
      list.appendChild(el);
    });
  }

  function barLine(label, value, max, cls, win) {
    const pct = Math.round((value / max) * 100);
    return `<div class="bar-line ${win ? "win" : ""}">
      <span class="lbl">${label}</span>
      <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div>
      <span class="bar-val">${value}</span>
    </div>`;
  }

  /* ── Memory ───────────────────────────────────────────── */
  function bindMemory() {
    const sync = () => {
      $("#ramOut").textContent = $("#ramRange").value;
      $("#bitsOut").textContent = $("#bitsRange").value;
      $("#ctxOut").textContent = $("#ctxRange").value;
    };
    ["ramRange", "bitsRange", "ctxRange"].forEach((id) => {
      $(`#${id}`).addEventListener("input", sync);
    });
    sync();
    $("#footprintBtn").addEventListener("click", estimateFootprint);
    // auto first estimate
    estimateFootprint();
  }

  async function estimateFootprint() {
    const body = {
      device_ram_gb: parseFloat($("#ramRange").value),
      quant_bits: parseFloat($("#bitsRange").value),
      kv_context: parseInt($("#ctxRange").value, 10),
      include_vision: $("#visionChk").checked,
      include_drafter: $("#drafterChk").checked,
    };
    const data = await api("/api/footprint", {
      method: "POST",
      body: JSON.stringify(body),
    });
    const tier = $("#memTier");
    tier.textContent = data.tier;
    tier.className = "tier " + data.tier;
    $("#memNarrative").textContent = data.narrative;
    const parts = data.breakdown_gb;
    const max = Math.max(data.device_ram_gb, parts.total, 1);
    const rows = [
      ["Language model", parts.language_model, "glimmer"],
      ["Perception encoder", parts.perception_encoder, "gemma"],
      ["DFlash drafter", parts.dflash_drafter, "qwen"],
      ["KV cache (est.)", parts.kv_cache_est, "glimmer"],
      ["Total", parts.total, "glimmer"],
    ];
    $("#memBars").innerHTML = rows
      .map(([label, gb, cls]) => {
        const pct = Math.min(100, Math.round((gb / max) * 100));
        return `<div class="stack-row">
          <span>${label}</span>
          <div class="bar-track"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div>
          <span class="bar-val">${gb.toFixed(1)} GB</span>
        </div>`;
      })
      .join("");
  }

  /* ── Live chat ────────────────────────────────────────── */
  function initChat() {
    $("#sendChatBtn").addEventListener("click", sendChat);
    $("#probeBtn").addEventListener("click", probeLive);
    $("#refreshModelsBtn").addEventListener("click", refreshModels);
    $("#chatInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendChat();
    });
    $("#clearChatBtn").addEventListener("click", () => {
      state.chat = [];
      $("#chatLog").innerHTML =
        '<div class="chat-empty"><p class="muted">Chat cleared.</p></div>';
    });
  }

  function fillModels(models, selected) {
    const sel = $("#modelSel");
    const current = selected || sel.value || "";
    sel.innerHTML = '<option value="">auto</option>';
    (models || []).forEach((id) => {
      const mid = typeof id === "string" ? id : id.id;
      if (!mid) return;
      const opt = document.createElement("option");
      opt.value = mid;
      opt.textContent = mid;
      if (mid === current) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  async function refreshModels() {
    $("#probeResult").textContent = "Loading models…";
    try {
      const data = await api("/api/live/models");
      fillModels(
        data.models.map((m) => m.id),
        data.resolved_default
      );
      $("#probeResult").textContent = `Models: ${data.models.length} · default ${data.resolved_default}`;
      $("#chatStatus").textContent = `Live → ${data.base_url}`;
    } catch (err) {
      const d = err.detail;
      $("#probeResult").textContent =
        typeof d === "object"
          ? `${d.title || "Error"}: ${d.fix || d.message || ""}`
          : err.message;
    }
  }

  async function probeLive() {
    $("#probeBtn").disabled = true;
    $("#probeResult").textContent = "Probing…";
    try {
      const data = await api("/api/live/probe");
      if (data.ok) {
        fillModels(data.models, data.model);
        $("#probeResult").textContent = `OK · ${data.model} · models ${data.latency_models_s}s · chat ${data.latency_chat_s}s · “${(data.chat_preview || "").slice(0, 40)}”`;
        $("#chatStatus").textContent = `Live ready · ${data.provider} · ${data.base_url}`;
        const badge = $("#liveBadge");
        badge.textContent = "live verified";
        badge.classList.remove("warn");
        badge.classList.add("ok");
      } else {
        $("#probeResult").textContent = [
          data.title || "Probe failed",
          data.error || data.message || "",
          data.fix || "",
        ]
          .filter(Boolean)
          .join(" — ");
        $("#chatStatus").textContent = data.fix || "Probe failed — see docs/LIVE.md";
      }
    } catch (err) {
      $("#probeResult").textContent = err.message;
    } finally {
      $("#probeBtn").disabled = false;
    }
  }

  async function sendChat() {
    const text = $("#chatInput").value.trim();
    if (!text) return;
    $("#chatInput").value = "";
    state.chat.push({ role: "user", content: text });
    renderChat();
    $("#chatStatus").textContent = "Generating…";
    $("#sendChatBtn").disabled = true;
    const body = {
      messages: state.chat,
      reasoning_strength: $("#reasonSel").value,
    };
    const model = $("#modelSel").value;
    if (model) body.model = model;
    try {
      const res = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });
      state.chat.push({ role: "assistant", content: res.content });
      renderChat();
      $("#chatStatus").textContent = `Done in ${res.latency_s}s · ${res.model}${res.provider ? " · " + res.provider : ""}`;
    } catch (err) {
      const d = err.detail;
      const msg =
        typeof d === "object"
          ? `${d.title || "Error"}: ${d.message || ""}\n${d.fix || ""}`
          : err.message;
      state.chat.push({ role: "assistant", content: `⚠ ${msg}` });
      renderChat();
      $("#chatStatus").textContent = "Live chat failed — Probe endpoint, see docs/LIVE.md";
    } finally {
      $("#sendChatBtn").disabled = false;
    }
  }

  function renderChat() {
    const log = $("#chatLog");
    log.innerHTML = "";
    state.chat.forEach((m) => {
      const el = document.createElement("div");
      el.className = `msg ${m.role}`;
      el.innerHTML = `<div class="who">${m.role}</div>${escapeHtml(m.content)}`;
      log.appendChild(el);
    });
    log.scrollTop = log.scrollHeight;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ── Boot ─────────────────────────────────────────────── */
  async function boot() {
    initTabs();
    initScenarioControls();
    initChat();
    bindMemory();
    await loadHealth();
    await Promise.all([loadScenarios(), loadBenchmarks()]);
  }

  boot().catch((e) => {
    console.error(e);
    $("#liveBadge").textContent = "boot error";
  });
})();
