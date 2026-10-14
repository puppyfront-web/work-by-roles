# work-by-roles · Expert Team Governance System

> A contract-driven, review-paradigm-native, open-source governance system for LLM expert teams
> with native Harness quality gates. Give every LLM role a versioned, auditable, regression-safe
> "role contract".

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-green.svg)]()

[中文](README.md) | English

## Why

Wiring multiple LLM agents together usually yields role drift, uncontrolled outputs, unverifiable
conclusions, and no safe way to change a prompt. work-by-roles answers with a governance kernel:

- **RoleContract** — SOP duties, forbidden behaviors, output schema, evidence rules, tool
  whitelist, memory permissions, token quota, review criteria: fully declarative, versioned with
  content-hash pinning.
- **Review paradigm** — Coordinator decomposes → experts run in parallel → Verifier independently
  judges; **disagreements are preserved, never arbitrated away**.
- **Layered isolated memory** — role-static / role-session / task-scratch / global-shared, gated
  by contract permissions, fully audited.
- **Native Harness** — golden cases + baseline snapshots (contract & model pinning) + one-click
  regression + six metrics + capability-degradation detection.
- **Contract-bound cache** — key = contract hash ‖ question hash ‖ evidence snapshot; contract
  changes invalidate automatically; never serves stale entries.
- **Security** — bilingual prompt-injection rule set, second-order content isolation, boundary
  marker escaping.
- **Full-chain audit** — typed events on every compile/call/validate/verdict, exportable audit
  packs.
- **LangGraph compatible** — 3-line drop-in guard for existing graphs, or one-call native review
  graph.

## Architecture

```
App       wbr/app        FastAPI service · expert canvas (SPA) · async task queue
Adapter   wbr/adapters   LangGraph mapping/guard/HITL · Redis/Memory storage
Core      wbr/core       contracts · compiler · diff · audit · memory · orchestration
                         security · token · cache · schema · harness   (stdlib + pydantic only)
```

## Quick start

```bash
pip install "work-by-roles[langgraph]"
```

```python
from wbr.templates.registry import load_team_spec
from wbr.core.orchestration import ReviewSession

spec = load_team_spec("arch_review_team")     # ready-made expert team
session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=your_invoker,                     # implement the ModelInvoker protocol
)
result = session.run("Review: monolith → microservices split")
print(result.final_answer, result.disagreements)
```

3-line drop-in for existing LangGraph graphs:

```python
from wbr.adapters.langgraph import WBRGuard

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 1
graph = guard.wrap(your_compiled_graph)                          # 2
result = graph.invoke({"question": "..."})                       # 3
```

Full platform (API + visual canvas): `pip install "work-by-roles[server]"` then
`uvicorn --factory wbr.app.api.main:create_app --port 8000` and open `/canvas`.

CLI (built-in deterministic demo invoker, no external LLM): `wbr list-teams`,
`wbr run-team arch_review_team "Review this design"`.

## Docs

[SDK API](docs/SDK.md) · [LangGraph integration](docs/INTEGRATION_LANGGRAPH.md) ·
[Harness](docs/HARNESS.md) · [Deploy](docs/DEPLOY.md) ·
[Specs](docs/spec/README.md) · [Acceptance reports](docs/acceptance/)

## Legacy appendix

The early lightweight workflow framework (`work_by_roles` package, `workflow` CLI) is frozen but
still shipped; its README is archived at [docs/LEGACY_README_EN.md](docs/LEGACY_README_EN.md) and
[docs/LEGACY_README.md](docs/LEGACY_README.md).

## License

MIT © Work-by-Roles Contributors
