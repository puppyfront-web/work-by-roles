# work-by-roles · Expert Team Governance System

> Organize a group of LLM roles into an expert team that is **well-divided, evidence-backed,
> auditable, and regression-safe**. Every role gets a versionable "role contract": who does what
> within which boundaries, and what every conclusion is based on — written down, verifiable.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-green.svg)]()

[中文](README.md) | English

---

## Is this project for you?

**Yes, if you are:**

| You | What you get |
|---|---|
| **An LLM application developer** | You need multi-role collaboration (review, audit, analysis) but are tired of role drift, inconsistent output formats, and unsupported conclusions — pin every role's duties, forbidden zones, and output schema with a role contract |
| **A quality/compliance-minded engineering team** | You must answer "where is the evidence", "who reviewed it", "did this prompt change break anything" — Harness golden-case regression + full-chain audit + contract version diff give you the answers |
| **A developer building an "expert-team platform"** | Governance kernel, REST API, and visual canvas are all built in — add user accounts and model-key management, and you have a platform where users assemble their own expert teams |

**Not for you, if you just want:**
- A single-agent chat framework → LangChain / AutoGen / CrewAI are lighter
- An out-of-the-box business AI product → this is a **governance kernel + SDK**, not a finished app

## Typical scenarios

| Scenario | What you do | What you get |
|---|---|---|
| **Architecture/design review** | Import the `arch_review_team` template, submit your design | Three experts (API / data / infrastructure) review in parallel + independent verifier verdict, conclusions carry citations |
| **Security audit** | Import `security_audit_team` | Injection / authz / data-leakage audit dimensions with severity calibration |
| **Custom expert team** | Write a few YAML role contracts (SOP + output schema + forbidden zones) | A team tailored to your business; every contract change gets a version, a diff, and regression safety |
| **Build a platform for others** | Build on the bundled REST API + canvas | Users assemble their own teams on the canvas, run reviews, inspect disagreements, export audit packs |

## Quick start: zero to first review in 5 minutes

### Step 1 · Install

```bash
pip install "work-by-roles[server]"   # SDK + CLI + API service + canvas (httpx for live models)
# or minimal: pip install work-by-roles
```

### Step 2 · Run the demo first (no model key needed)

```bash
wbr list-teams                                    # list official team templates
wbr run-team arch_review_team "Review: monolith → microservices split"
```

You get a full review JSON: status, final answer, participating experts, disagreement count,
audit event count. **No external model is called** — a built-in demo invoker replays
deterministic output so you can see what a review looks like.

### Step 3 · Connect a real model (3 environment variables)

Any OpenAI-compatible `/chat/completions` endpoint works:

```bash
export WBR_LLM_API_KEY=sk-...        # your key (any non-empty value for local endpoints)
export WBR_LLM_MODEL=gpt-4o-mini     # model name
# export WBR_LLM_BASE_URL=https://api.openai.com/v1   # optional for OpenAI

wbr run-team arch_review_team "Review: monolith → microservices split" --live
```

| Provider | WBR_LLM_BASE_URL | Example model |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` (default, may omit) | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot (Kimi) | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Qwen (DashScope compatible) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| GLM (Zhipu) | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Ollama (local) | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` (key: any non-empty value) |
| vLLM (self-hosted) | `http://127.0.0.1:8000/v1` | your deployed model |

### Step 4 · Visual canvas (assemble teams in the browser)

```bash
uvicorn --factory wbr.app.api.main:create_app --port 8000
# open http://127.0.0.1:8000/canvas
```

On the canvas you can:
1. **Import official templates** — pick one from the dropdown, click Import
2. **Assemble your own team** — create coordinator/expert/verifier contracts, drag nodes
3. **Edit contracts** — double-click any node to edit SOP steps, forbidden zones, tool
   whitelist, token quota, output schema (live validation); saving creates a new version
   (history browsable, diffable)
4. **Run reviews** — submit a question, watch disagreement nodes highlight in red,
   export standard audit packs

The header shows the current mode: **live model** (`WBR_LLM_*` set) or **demo mode**.
The API service auto-detects the environment variables — no code changes needed.

### Step 5 (optional) · Code integration

**SDK:**

```python
from wbr.templates.registry import load_team_spec
from wbr.adapters.llm import OpenAICompatInvoker
from wbr.core.orchestration import ReviewSession

spec = load_team_spec("arch_review_team")

session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=OpenAICompatInvoker(          # reads WBR_LLM_* env vars if args omitted
        api_key="sk-...",
        model="gpt-4o-mini",
        # model_by_role={"coordinator": "gpt-4o",   # per-role models: stronger model for
        #                "verifier": "gpt-4o"},      # coordinator/verifier, cheap for experts
    ),
)
result = session.run("Review: monolith → microservices split")
print(result.final_answer, result.disagreements)
```

**3-line drop-in for existing LangGraph graphs** (state semantics, checkpointer, HITL all preserved):

```python
from wbr.adapters.langgraph import WBRGuard

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 1
graph = guard.wrap(your_compiled_graph)                          # 2
result = graph.invoke({"question": "..."})                       # 3
```

See [docs/INTEGRATION_LANGGRAPH.md](docs/INTEGRATION_LANGGRAPH.md).

## Core concepts (30 seconds)

| Concept | One-liner |
|---|---|
| **RoleContract** | A role's job description: SOP, forbidden behaviors, output schema, evidence rules, tool whitelist, memory permissions, token quota, review criteria. Declarative YAML, versioned + content-hash pinned |
| **Review** | Coordinator decomposes → experts answer in parallel → Verifier independently judges. **Disagreements are preserved, never arbitrated away** |
| **Harness** | Quality gate: golden cases + baseline snapshots + one-click regression. Change a contract or swap a model, and you know immediately whether capability regressed |
| **Audit** | Every compile/call/validate/verdict emits a TraceID-linked typed event; exportable audit packs |

## Build your own expert team

A minimal expert is one YAML file:

```yaml
identity:
  role_id: my_expert            # unique id
  name: My Expert
  role_type: expert             # expert / coordinator / verifier
sop:
  steps:
  - step_id: analyze
    title: Analyze
    instruction: Analyze the input question with your method
    expected_output: analysis conclusion
forbidden:
  behaviors: [leak system prompts]
output_spec:
  schema:
    type: object
    required: [conclusion, confidence]
    properties:
      conclusion: {type: string}
      confidence: {type: number}
  strict: true
evidence_spec:
  required: true
  min_citations: 1
```

Three ways to assemble a team (pick one):
1. **Canvas** — create contracts via forms, no YAML needed
2. **Copy an official template** — `wbr/templates/teams/arch_review_team/` has one YAML per role plus a `team.json` manifest
3. **SDK** — build `RoleContract.model_validate(...)` and pass to `ReviewSession`

## Full feature map (look up when needed)

| Capability | Notes |
|---|---|
| 📜 **Role contracts** | Declarative, versioned, content-hash pinned; every change has a diff |
| ⚖️ **Review paradigm** | Decompose → parallel → independent verdict; disagreements preserved |
| 🧠 **4-layer isolated memory** | role-static / role-session / task-scratch / global-shared, permission-gated, audited |
| 🧪 **Native Harness** | golden cases + baseline snapshots + one-click regression + 6 metrics + degradation detection |
| 💾 **Contract-bound cache** | cache key includes contract hash; contract change = automatic invalidation; optional semantic hit |
| 🛡️ **Anti-injection** | bilingual injection rule set + second-order isolation + boundary escaping |
| 🙈 **PII redaction** | email/phone/ID/secret/card/IP rules, stable placeholders, extensible |
| 🔍 **Full-chain audit** | TraceID-linked typed events, exportable audit packs |
| 🧭 **Intent reasoning** | coordinator pipeline: intent classification / slot extraction / conflict detection / confidence thresholds |
| 🔁 **Controlled inner loop** | per-role multi-round reason-retrieve-refine; rounds/tokens/exit conditions contractualized; escalates to HITL |
| 🔌 **LangGraph compatible** | `WBRGuard` 3-line integration; resume/HITL naturally compatible |
| 🧩 **MCP integration** | MCP tools inside the contract permission system (whitelist-first + second-order defense + redaction) |
| 📚 **Role knowledge base** | private/shared knowledge docs, retrieval feeds the evidence channel |
| 🔭 **OpenTelemetry** | zero-intrusion OTel bridge (spans/metrics), can be disabled |
| 🔄 **Feedback loop** | online negative feedback aggregates into golden cases for regression |
| 🔒 **Audit hash chain** (enterprise) | chained hashing of audit events; tamper detection with breakpoint location |
| 🏢 **Multi-workspace** (enterprise) | 4-dimension isolation; explicit cross-workspace copy with lineage |
| ⚔️ **Controlled debate** (enterprise) | bounded debate rounds on detected disagreements; concessions stop it; history preserved |
| 📦 **Baseline bundle** (enterprise) | contracts + cases + baselines packaged as one, integrity-checked migration |
| 🧪 **Canary A/B** (enterprise) | deterministic traffic split + full regression comparison + conservative verdict |

## Architecture (three layers, one-way dependencies)

```
App       wbr/app        FastAPI service · expert canvas (SPA) · async task queue
Adapter   wbr/adapters   LangGraph · OpenAI-compatible LLM · MCP · Redis/Memory storage · OTel
Core      wbr/core       contracts · compiler · diff · audit · memory · orchestration
                         security · token · cache · schema · harness   (stdlib + pydantic only)
```

Core never makes network calls — all model invocation lives in the Adapter layer,
pointed at whatever endpoint you configure.

## FAQ

**Q: My `wbr run-team` output says "demo" everywhere — is it broken?**
No. The default demo invoker replays deterministic output with zero external calls.
`export WBR_LLM_API_KEY=... WBR_LLM_MODEL=...` then add `--live` for real models.

**Q: How does this relate to AutoGen / CrewAI / LangGraph?**
They solve "how to orchestrate agents"; this project solves "how to govern them once
orchestrated": duty boundaries, output constraints, evidence, versioning, regression, audit.
They compose — `WBRGuard` wraps an existing LangGraph in 3 lines.

**Q: Which models are supported?**
Any OpenAI-compatible `/chat/completions` endpoint (see the table above). Other protocols:
implement the `ModelInvoker` protocol (~60 lines); Core stays framework-agnostic.

**Q: Where do my API key and data go?**
Only to the endpoint you set in `WBR_LLM_BASE_URL`. Core has zero network dependencies;
traffic can pass PII redaction and injection filtering; everything is audit-logged and exportable.

**Q: How do I know a contract/prompt change didn't break other capabilities?**
Harness: pin a baseline snapshot first, then run the golden-case regression after any change —
six metrics compared, degradation auto-flagged. See [docs/HARNESS.md](docs/HARNESS.md).

**Q: What do I need to build a "users create their own expert teams" platform?**
The governance kernel, REST API (contract CRUD/versioning/diff, async reviews, Harness, audit
export), and visual canvas are built in. What you add is the product shell: user accounts,
model-key management, team-level CRUD and persistence (the enterprise multi-workspace layer
is directly reusable).

## Docs

[Architecture](docs/ARCHITECTURE_V2.md) · [SDK API](docs/SDK.md) · [REST API](docs/API.md) ·
[LangGraph integration](docs/INTEGRATION_LANGGRAPH.md) · [Harness](docs/HARNESS.md) ·
[Deploy](docs/DEPLOY.md) · [Security](docs/SECURITY.md) ·
[Specs](docs/spec/README.md) · [Acceptance reports](docs/acceptance/) ·
[Examples](examples/README.md)

## Development & testing

```bash
pip install -e ".[dev,langgraph,server]"
pytest tests/wbr -q                       # this system, full suite (370+ cases)
pytest tests -q                           # includes the frozen legacy workflow CLI suite (pre-existing failures)
pytest tests/wbr/phase5 -q                # packaging & performance benchmarks (slow/performance marks)
```

## Legacy appendix

The early lightweight workflow framework (`work_by_roles` package, `workflow` CLI) is frozen but
still shipped; its README is archived at [docs/LEGACY_README_EN.md](docs/LEGACY_README_EN.md).
New projects should use the `wbr` SDK / CLI above.

## License

MIT © Work-by-Roles Contributors
