# work-by-roles · LLM Expert Team Governance System

> Manage your AI roles like code: **contracts for duties, enforcement at runtime, evidence
> behind conclusions, audit across the process, regression gates on every change.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-green.svg)]()
[![CI](https://github.com/puppyfront-web/work-by-roles/actions/workflows/ci.yml/badge.svg)](https://github.com/puppyfront-web/work-by-roles/actions/workflows/ci.yml)

[中文](README.md) | English

---

## Why

Putting multiple LLM agents into production typically hits three walls:

1. **Uncontrolled output** — role drift, inconsistent formats, confident fabrication
2. **Unverifiable conclusions** — no answer to "where is the evidence, who reviewed it, which prompt version"
3. **Risky changes** — changing one line of a prompt is a gamble; you can't tell what else it breaks

work-by-roles answers by giving every LLM role a **versioned role contract** (SOP duties,
forbidden zones, output schema, evidence rules, tool whitelist, token quota), organizing
collaboration as a **review paradigm**, **enforcing boundaries at runtime**, and providing
**regression gates** for every change.

```text
                        ┌─────────────┐
      question/design ─▶│ Coordinator │  decompose & dispatch
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
         ┌──────────┐    ┌──────────┐    ┌──────────┐
         │ Expert A │    │ Expert B │    │ Expert C │  answer in parallel
         └─────┬────┘    └─────┬────┘    └─────┬────┘  (schema + citation enforced)
               └───────────────┼───────────────┘
                               ▼
                        ┌─────────────┐
                        │  Verifier   │  independent review · verdict
                        └──────┬──────┘  disagreements preserved, never arbitrated
                               ▼
              structured answer + evidence chain + audit events
```

## Positioning: how it relates to mainstream tools

| What you use | What it solves | What this project adds |
|---|---|---|
| LangGraph / AutoGen / CrewAI | How agents are orchestrated | Role boundaries, output constraints, evidence chains, versioning, regression, audit (`WBRGuard` wraps existing graphs in 3 lines) |
| promptfoo / DeepEval | Offline prompt evaluation | Adds **runtime enforcement** (schema validation / tool whitelist / quotas) and a contract-versioning loop |
| LangSmith (SaaS) | Observability & tracing | Open source, self-hostable; audit + evidence chains aimed at compliance review |
| Hand-written multi-role prompts | — | Boundary definitions and regression safety from day one |

**In one sentence: orchestration frameworks make agents run, eval tools measure them —
this project keeps them governable.**

## Quick start: zero to first review in 5 minutes

### Step 1 · Install

```bash
pip install "work-by-roles[server]"   # SDK + CLI + API service + canvas (httpx for live models)
# or minimal: pip install work-by-roles
```

### Step 2 · Run the demo (no model key needed)

```bash
wbr list-teams                                    # list official team templates
wbr run-team arch_review_team "Review: monolith → microservices split"
```

You get a full review JSON: status, final answer, participating experts, disagreement count,
audit event count. This uses the built-in demo invoker (deterministic output) —
**no external model is called**.

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

### Step 4 · Visual canvas

```bash
uvicorn --factory wbr.app.api.main:create_app --port 8000
# open http://127.0.0.1:8000/canvas
```

- **Import official templates** — pick one from the dropdown, click Import
- **Assemble your own team** — create coordinator/expert/verifier contracts, drag nodes
- **Edit contracts** — double-click any node to edit SOP, forbidden zones, tool whitelist,
  token quota, output schema (live validation); saving creates a new version (browsable, diffable)
- **Run reviews** — submit a question, disagreement nodes highlight in red, export audit packs

The header shows the current mode (live model / demo). The API service auto-detects
`WBR_LLM_*` environment variables — no code changes needed.

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
        #                "verifier": "gpt-4o"},      # coordinator/verifier, cheaper for experts
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

| Concept | Description |
|---|---|
| **RoleContract** | A role's job description: SOP, forbidden behaviors, output schema, evidence rules, tool whitelist, memory permissions, token quota, review criteria. Declarative YAML, versioned + content-hash pinned |
| **Review** | Coordinator decomposes → experts answer in parallel → Verifier independently judges. **Disagreements are preserved, never arbitrated**; final judgment stays with you |
| **Harness quality gate** | Golden cases + baseline snapshots + one-click regression. Capability degradation after any contract or model change is detected automatically |
| **Full-chain audit** | Every compile/call/validate/verdict emits a TraceID-linked typed event; exportable audit packs |

## Design principles

1. **Contract first** — boundaries are declared and enforced before runtime, not patched by after-the-fact evaluation
2. **Preserve disagreement** — independent review reaches a verdict but never arbitrates; conclusions and disagreements are delivered together
3. **Regression-safe changes** — the impact of any contract or model change can be verified against a baseline
4. **Auditable end to end** — every conclusion traces back to evidence, contract version, and operations

## Typical scenarios

| Scenario | What you do | What you get |
|---|---|---|
| **Architecture / design review** | Import `arch_review_team`, submit your design | Three experts (API / data / infrastructure) review in parallel + verifier verdict, conclusions carry citations |
| **Security audit** | Import `security_audit_team` | Injection / authz / data-leakage audit dimensions with severity calibration |
| **Pre-publish content review** | Import `content_review_team`, paste your copy and target platform | Fact-checking + platform compliance + conversion experts review in parallel; final verdict: publish / revise / reject with a must-fix list |
| **Custom expert team** | Write YAML role contracts | A team tailored to your business; every contract change has version, diff, and regression safety |
| **User-facing expert-team platform** | Build on the bundled REST API + canvas | Governance kernel, contract CRUD, async reviews, audit export out of the box — add user accounts and model-key management |

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

Three ways to assemble a team: **canvas forms** (no YAML), **copy an official template**
(`wbr/templates/teams/arch_review_team/`), or the **SDK** (`RoleContract.model_validate(...)`).

<details>
<summary><b>Full feature map (click to expand)</b></summary>

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

</details>

## Architecture (three layers, one-way dependencies)

```text
App       wbr/app        FastAPI service · expert canvas (SPA) · async task queue
Adapter   wbr/adapters   LangGraph · OpenAI-compatible LLM · MCP · Redis/Memory storage · OTel
Core      wbr/core       contracts · compiler · diff · audit · memory · orchestration
                         security · token · cache · schema · harness   (stdlib + pydantic only)
```

Core never makes network calls — all model invocation lives in the Adapter layer, pointed at
whatever endpoint you configure. Governance takes effect at four moments: **definition**
(contracts), **runtime** (schema / whitelist / quota enforcement), **verdict** (review + audit),
and **evolution** (Harness regression).

## FAQ

**Q: My `wbr run-team` output says "demo" everywhere — is it broken?**
No. The default demo invoker replays deterministic output with zero external calls.
Set `WBR_LLM_API_KEY` / `WBR_LLM_MODEL` and add `--live` for real models.

**Q: Does it compete with AutoGen / CrewAI / LangGraph?**
No. They solve orchestration; this project solves governance after orchestration. They compose —
`WBRGuard` adds governance to an existing LangGraph.

**Q: Which models are supported?**
Any OpenAI-compatible `/chat/completions` endpoint (see table above). For other protocols,
implement the `ModelInvoker` protocol (~60 lines); Core stays framework-agnostic.

**Q: Where do my API key and data go?**
Only to the endpoint set in `WBR_LLM_BASE_URL`. Core has zero network dependencies; traffic can
pass PII redaction and injection filtering; everything is audit-logged and exportable.

**Q: How do I know a contract/prompt change didn't break other capabilities?**
Harness: pin a baseline snapshot first, then run the golden-case regression after any change —
six metrics compared, degradation auto-flagged. See [docs/HARNESS.md](docs/HARNESS.md).

**Q: What do I need to build a "users create their own expert teams" platform?**
The governance kernel, REST API (contract CRUD/versioning/diff, async reviews, Harness, audit
export), and visual canvas are built in. What you add: user accounts, model-key management,
team-level CRUD and persistence (the enterprise multi-workspace layer is directly reusable).

## Docs

- [Architecture](docs/ARCHITECTURE_V2.md) · [SDK API](docs/SDK.md) ·
  [LangGraph integration](docs/INTEGRATION_LANGGRAPH.md) · [Harness](docs/HARNESS.md) ·
  [Deploy](docs/DEPLOY.md)
- Specs: [docs/spec/README.md](docs/spec/README.md) (SPEC-000~006 + review records) ·
  Acceptance reports: [docs/acceptance/](docs/acceptance/)
- Examples: [examples/README.md](examples/README.md) · Changelog: [CHANGELOG.md](CHANGELOG.md)

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). A good starting point:
contribute a new official team template under `wbr/templates/teams/` (contract review,
financial report audit, and interview assessment are all in real demand).

## Development & testing

```bash
pip install -e ".[dev,langgraph,server]"
pytest tests -q                           # full suite (370+ cases)
pytest tests/wbr/phase5 -q                # packaging & performance benchmarks (slow/performance marks)
```

## License

MIT © Work-by-Roles Contributors
