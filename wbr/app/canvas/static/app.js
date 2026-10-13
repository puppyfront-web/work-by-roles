/* work-by-roles 专家画布（零依赖 vanilla JS）
 * 画布仅消费 API，不耦合内核（规则8 / D-10）。
 */
"use strict";

const API = "/api/v1";
const state = {
  contracts: [],          // 契约摘要列表
  selected: null,         // 当前编辑的 role_id
  positions: {},          // role_id -> {x,y} 画布坐标
  disputed: new Set(),    // 分歧专家
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, text) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
};

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = body.error ? `${body.error.code}: ${body.error.message}` : res.statusText;
    throw new Error(msg);
  }
  return body;
}

/* ---------- 契约列表 ---------- */
async function refresh() {
  const res = await fetch("/canvas/api-bootstrap");
  if (!res.ok) throw new Error("bootstrap " + res.status);
  const boot = await res.json();
  state.contracts = boot.contracts || [];
  $("api-version").textContent = "v" + boot.version;
  renderSelectors();
  layout();
}

async function fetchFullContract(roleId) {
  return api("/contracts/" + encodeURIComponent(roleId));
}

/* ---------- 画布布局与渲染 ---------- */
function layout() {
  const types = { coordinator: [], expert: [], verifier: [] };
  state.contracts.forEach((c) => (types[c.role_type] || types.expert).push(c));
  types.coordinator.forEach((c, i) => {
    state.positions[c.role_id] = state.positions[c.role_id] || { x: 80, y: 250 + i * 120 };
  });
  types.expert.forEach((c, i) => {
    state.positions[c.role_id] = state.positions[c.role_id] || { x: 380, y: 60 + i * 110 };
  });
  types.verifier.forEach((c, i) => {
    state.positions[c.role_id] = state.positions[c.role_id] || { x: 690, y: 250 + i * 120 };
  });
  renderGraph();
}

function nodeHTML(c) {
  const disputed = state.disputed.has(c.role_id) ? " disputed" : "";
  return `<g class="node ${c.role_type}${disputed}" data-role="${c.role_id}">
    <rect x="0" y="0" width="170" height="72" rx="10"></rect>
    <text x="12" y="22">${escapeHTML(c.name || c.role_id)}</text>
    <text class="sub" x="12" y="40">${c.role_type} · v${c.version}</text>
    <text class="sub" x="12" y="56">hash:${c.content_hash}</text>
  </g>`;
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function renderGraph() {
  const nodes = $("nodes");
  const edges = $("edges");
  nodes.innerHTML = "";
  edges.innerHTML = "";
  const byId = Object.fromEntries(state.contracts.map((c) => [c.role_id, c]));
  const coordinator = state.contracts.find((c) => c.role_type === "coordinator");
  const verifier = state.contracts.find((c) => c.role_type === "verifier");
  const experts = state.contracts.filter((c) => c.role_type === "expert");

  // 边：Coordinator → Experts → Verifier；分歧专家间红色虚线
  const link = (from, to, disputed) => {
    const a = state.positions[from], b = state.positions[to];
    if (!a || !b) return;
    edges.appendChild(el("path", {
      class: "edge" + (disputed ? " disputed" : ""),
      d: `M ${a.x + 170} ${a.y + 36} C ${a.x + 260} ${a.y + 36}, ${b.x - 90} ${b.y + 36}, ${b.x} ${b.y + 36}`,
      "marker-end": disputed ? "url(#arrow-red)" : "url(#arrow)",
    }));
  };
  if (coordinator && verifier) {
    experts.forEach((e) => {
      link(coordinator.role_id, e.role_id, false);
      link(e.role_id, verifier.role_id, state.disputed.has(e.role_id));
    });
    if (experts.length === 0) link(coordinator.role_id, verifier.role_id, false);
  }
  // 分歧专家互连
  const list = [...state.disputed];
  for (let i = 0; i + 1 < list.length; i++) link(list[i], list[i + 1], true);

  state.contracts.forEach((c) => {
    const pos = state.positions[c.role_id] || { x: 20, y: 20 };
    const tpl = el("template");
    tpl.innerHTML = nodeHTML(c);
    const g = tpl.content.firstChild;
    g.setAttribute("transform", `translate(${pos.x},${pos.y})`);
    attachDrag(g, c.role_id);
    g.addEventListener("dblclick", () => openEditor(c.role_id));
    nodes.appendChild(g);
  });
}

function attachDrag(g, roleId) {
  let dragging = false, dx = 0, dy = 0;
  g.addEventListener("mousedown", (ev) => {
    dragging = true;
    const pt = state.positions[roleId];
    const svg = $("canvas").getBoundingClientRect();
    const scale = 960 / svg.width;
    dx = (ev.clientX - svg.left) * scale - pt.x;
    dy = (ev.clientY - svg.top) * scale - pt.y;
    ev.preventDefault();
  });
  window.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    const svg = $("canvas").getBoundingClientRect();
    const scale = 960 / svg.width;
    const x = Math.max(0, (ev.clientX - svg.left) * scale - dx);
    const y = Math.max(0, (ev.clientY - svg.top) * scale - dy);
    state.positions[roleId] = { x, y };
    g.setAttribute("transform", `translate(${x},${y})`);
    renderGraph();
  });
  window.addEventListener("mouseup", () => (dragging = false));
}

/* ---------- 契约编辑 ---------- */
async function openEditor(roleId) {
  const c = await fetchFullContract(roleId);
  state.selected = roleId;
  $("editor").classList.remove("hidden");
  $("editor-title").textContent = "契约编辑 · " + roleId;
  $("f-role-id").value = c.identity.role_id;
  $("f-role-id").disabled = true;
  $("f-name").value = c.identity.name;
  $("f-role-type").value = c.identity.role_type;
  $("f-desc").value = c.identity.description || "";
  $("f-sop").value = (c.sop.steps || []).map((s) => `${s.step_id}|${s.title}|${s.instruction}`).join("\n");
  $("f-forbidden").value = [...(c.forbidden?.behaviors || []), ...(c.forbidden?.domains || [])].join("\n");
  $("f-schema").value = JSON.stringify(c.output_spec?.schema || {}, null, 2);
  schemaFeedback($("f-schema").value);
  $("f-tools").value = (c.tool_policy?.whitelist || []).join(",");
  $("f-read").value = (c.memory_permissions?.read_layers || []).join(",");
  $("f-write").value = (c.memory_permissions?.write_layers || []).join(",");
  const q = c.token_quota || {};
  $("f-quota").value = `${q.max_prompt_tokens ?? 6000}/${q.max_completion_tokens ?? 2000}/${q.max_turn_tokens ?? 8000}`;
  const vers = await api(`/contracts/${encodeURIComponent(roleId)}/versions`);
  $("version-info").textContent = "版本历史:\n" + vers.map((v) => `  v${v.version}  ${v.content_hash.slice(0, 10)}…`).join("\n");
}

function buildContractPayload() {
  const [p, cm, t] = $("f-quota").value.split("/").map((n) => parseInt(n, 10));
  const layers = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
  return {
    identity: {
      role_id: $("f-role-id").value.trim(),
      name: $("f-name").value.trim() || $("f-role-id").value.trim(),
      role_type: $("f-role-type").value,
      description: $("f-desc").value,
    },
    sop: { steps: $("f-sop").value.split("\n").map((line) => line.trim()).filter(Boolean).map((line, i) => {
      const [sid, title, instruction] = line.split("|");
      return { step_id: (sid || `step_${i + 1}`).trim(), title: (title || "步骤").trim(), instruction: (instruction || title || "执行").trim() };
    }) },
    forbidden: { behaviors: $("f-forbidden").value.split("\n").map((s) => s.trim()).filter(Boolean), domains: [] },
    output_spec: { schema: JSON.parse($("f-schema").value || "{}"), strict: true },
    tool_policy: { whitelist: $("f-tools").value.split(",").map((s) => s.trim()).filter(Boolean), deny_by_default: true },
    memory_permissions: { read_layers: layers($("f-read").value), write_layers: layers($("f-write").value), allow_global_write: layers($("f-write").value).includes("global_shared") },
    token_quota: { max_prompt_tokens: p || 6000, max_completion_tokens: cm || 2000, max_turn_tokens: t || 8000 },
  };
}

function schemaFeedback(text) {
  const fb = $("schema-feedback");
  try {
    JSON.parse(text || "{}");
    fb.textContent = "✓ JSON 合法";
    fb.className = "feedback ok";
    return true;
  } catch (e) {
    fb.textContent = "✗ " + e.message;
    fb.className = "feedback err";
    return false;
  }
}

async function saveContract() {
  if (!schemaFeedback($("f-schema").value)) return;
  const payload = buildContractPayload();
  try {
    if (state.selected) {
      await api("/contracts/" + encodeURIComponent(state.selected), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract: payload }),
      });
    } else {
      await api("/contracts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract: payload }),
      });
    }
    $("editor").classList.add("hidden");
    state.selected = null;
    await refresh();
  } catch (e) {
    alert("保存失败: " + e.message);
  }
}

async function deleteContract() {
  if (!state.selected || !confirm(`删除契约 ${state.selected}?`)) return;
  await api("/contracts/" + encodeURIComponent(state.selected), { method: "DELETE" });
  $("editor").classList.add("hidden");
  state.selected = null;
  await refresh();
}

function newContract() {
  state.selected = null;
  $("editor").classList.remove("hidden");
  $("editor-title").textContent = "新建契约";
  ["f-role-id", "f-name", "f-desc", "f-sop", "f-forbidden", "f-tools", "f-read", "f-write"].forEach((id) => ($(id).value = ""));
  $("f-role-id").disabled = false;
  $("f-role-type").value = "expert";
  $("f-schema").value = JSON.stringify({
    type: "object", required: ["conclusion", "confidence"],
    properties: { conclusion: { type: "string", minLength: 1 }, confidence: { type: "number", minimum: 0, maximum: 1 } },
  }, null, 2);
  schemaFeedback($("f-schema").value);
  $("version-info").textContent = "";
}

/* ---------- 会审运行 ---------- */
function renderSelectors() {
  const fill = (sel, type) => {
    sel.innerHTML = "";
    state.contracts.filter((c) => c.role_type === type).forEach((c) => {
      const opt = el("option", { value: c.role_id }, `${c.name} (${c.role_id})`);
      sel.appendChild(opt);
    });
  };
  fill($("sel-coordinator"), "coordinator");
  fill($("sel-verifier"), "verifier");
  const box = $("expert-checks");
  box.innerHTML = "";
  state.contracts.filter((c) => c.role_type === "expert").forEach((c) => {
    const label = el("label");
    const cb = el("input", { type: "checkbox", value: c.role_id });
    cb.checked = true;
    label.appendChild(cb);
    label.appendChild(document.createTextNode(` ${c.name} (${c.role_id})`));
    box.appendChild(label);
  });
}

async function runReview() {
  const question = $("f-question").value.trim();
  if (!question) return alert("请输入问题");
  const experts = [...$("expert-checks").querySelectorAll("input:checked")].map((i) => i.value);
  if (!experts.length) return alert("请选择至少一位专家");
  const body = {
    question,
    coordinator: $("sel-coordinator").value,
    experts,
    verifier: $("sel-verifier").value,
  };
  if (!body.coordinator || !body.verifier) return alert("需要 Coordinator 与 Verifier 契约");
  $("btn-run").disabled = true;
  try {
    const { task_id } = await api("/reviews", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    pollReview(task_id);
  } catch (e) {
    alert("提交失败: " + e.message);
    $("btn-run").disabled = false;
  }
}

function pollReview(taskId) {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    const r = await api("/reviews/" + taskId);
    $("run-result").classList.remove("hidden");
    $("run-status").textContent = r.status;
    $("run-status").className = "badge " + r.status;
    if (r.status === "done" || r.status === "failed") {
      clearInterval(state.pollTimer);
      $("btn-run").disabled = false;
      if (r.status === "failed") {
        $("final-answer").textContent = "失败: " + (r.error || "未知错误");
        return;
      }
      renderResult(r.result);
    }
  }, 400);
}

function renderResult(result) {
  $("final-answer").textContent = "📌 " + (result.final_answer || "（无）");
  const cards = $("expert-cards");
  cards.innerHTML = "";
  state.disputed = new Set();
  (result.disagreements || []).forEach((d) => d.between.forEach((r) => state.disputed.add(r)));
  (result.expert_outcomes || []).forEach((o) => {
    const card = el("div", { class: "expert-card" });
    const viol = (o.violations || []).map((v) => `${v.kind}: ${v.detail}`).join("; ");
    card.innerHTML = `<b>${escapeHTML(o.role_id)}</b> <span class="muted">${o.status}</span>
      <div>${escapeHTML(o.output?.conclusion || o.error || "")}</div>
      ${viol ? `<div class="viol">⚠ ${escapeHTML(viol)}</div>` : ""}`;
    cards.appendChild(card);
  });
  const dg = $("disagreements");
  dg.innerHTML = "";
  (result.disagreements || []).forEach((d) => {
    const card = el("div", { class: "disagree-card" });
    card.innerHTML = `<b>⚔ 分歧留存</b>（议题: ${escapeHTML(d.topic)}）<br>` +
      d.positions.map((p) => `${escapeHTML(p.role_id)}: ${escapeHTML(String(p.conclusion))}`).join("<br>");
    dg.appendChild(card);
  });
  renderGraph(); // 分歧节点红色高亮
}

/* ---------- 启动 ---------- */
window.addEventListener("DOMContentLoaded", () => {
  $("btn-refresh").addEventListener("click", refresh);
  $("btn-new").addEventListener("click", newContract);
  $("btn-save").addEventListener("click", saveContract);
  $("btn-delete").addEventListener("click", deleteContract);
  $("btn-close-editor").addEventListener("click", () => $("editor").classList.add("hidden"));
  $("btn-run").addEventListener("click", runReview);
  $("f-schema").addEventListener("input", (e) => schemaFeedback(e.target.value));
  refresh().catch((e) => {
    $("api-version").textContent = "API 不可用: " + e.message;
  });
});
