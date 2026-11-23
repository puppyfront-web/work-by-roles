import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, can, type AuditPage, type Run, type Team } from "../api";

function statusClass(status: string): string {
  if (status === "completed") return "pill ok";
  if (status === "failed") return "pill bad";
  return "pill wait";
}

export function RunNewPage({ workspaceId, role }: { workspaceId: string; role: string }) {
  const [params] = useSearchParams();
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState(params.get("team") ?? "");
  const [question, setQuestion] = useState("");
  const [budget, setBudget] = useState("100000");
  const [inputPrice, setInputPrice] = useState("0.000002");
  const [cachedPrice, setCachedPrice] = useState("0.0000005");
  const [outputPrice, setOutputPrice] = useState("0.000008");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Team[]>(`/api/workspaces/${workspaceId}/teams`).then((rows) => {
      setTeams(rows);
      if (!teamId && rows[0]) setTeamId(rows[0].id);
    }).catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await api<Run>(`/api/workspaces/${workspaceId}/runs`, {
        method: "POST",
        body: JSON.stringify({
          team_id: teamId,
          question,
          token_budget: budget ? Number(budget) : null,
          input_price: Number(inputPrice),
          output_price: Number(outputPrice),
          cached_input_price: Number(cachedPrice),
        }),
      });
      window.location.assign(`/runs/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动失败");
    }
  }

  return (
    <section>
      <h1>发起会审</h1>
      <form className="card" onSubmit={submit}>
        <label>
          <span>团队</span>
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)} required>
            {teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
          </select>
        </label>
        <label>
          <span>问题</span>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} required />
        </label>
        <label>
          <span>Token 预算（整次会审）</span>
          <input value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="numeric" />
        </label>
        <p className="hint">单价是每 token，用来估算缓存命中省下的费用。缓存单价应低于输入单价。</p>
        <label><span>输入单价</span><input value={inputPrice} onChange={(e) => setInputPrice(e.target.value)} /></label>
        <label><span>缓存命中单价</span><input value={cachedPrice} onChange={(e) => setCachedPrice(e.target.value)} /></label>
        <label><span>输出单价</span><input value={outputPrice} onChange={(e) => setOutputPrice(e.target.value)} /></label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={!can(role, "member")}>开始</button>
      </form>
    </section>
  );
}

export function RunDetailPage({ workspaceId, role }: { workspaceId: string; role: string }) {
  const { runId } = useParams();
  const [run, setRun] = useState<Run | null>(null);
  const [audit, setAudit] = useState<AuditPage | null>(null);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!runId) return;
    let timer = 0;
    let stop = false;

    async function tick() {
      try {
        const next = await api<Run>(`/api/workspaces/${workspaceId}/runs/${runId}`);
        if (stop) return;
        setRun(next);
        if (next.status === "queued" || next.status === "running") {
          timer = window.setTimeout(tick, 1500);
          return;
        }
        const events = await api<AuditPage>(`/api/workspaces/${workspaceId}/runs/${runId}/audit`);
        if (!stop) setAudit(events);
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "加载失败");
      }
    }

    void tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [workspaceId, runId]);

  if (error) return <p className="error">{error}</p>;
  if (!run) return <p className="muted">加载中…</p>;
  const verdict = run.result?.verifier_verdict;

  return (
    <section>
      <p><Link to="/teams">返回团队</Link></p>
      <div className="row">
        <h1>会审结果</h1>
        <span className={statusClass(run.status)}>{run.status}</span>
        {can(role, "member") && (run.status === "queued" || run.status === "running") ? (
          <button
            className="quiet"
            type="button"
            disabled={cancelling}
            onClick={() => {
              setCancelling(true);
              api<Run>(`/api/workspaces/${workspaceId}/runs/${run.id}/cancel`, { method: "POST" })
                .then(setRun)
                .catch((err: unknown) => setError(err instanceof Error ? err.message : "取消失败"))
                .finally(() => setCancelling(false));
            }}
          >
            {run.cancel_requested ? "取消中" : "取消"}
          </button>
        ) : null}
      </div>
      <p>{run.question}</p>
      {run.error ? <p className="error">{run.error}</p> : null}
      <div className="grid">
        <div className="metric"><b>{run.prompt_tokens}</b><span>prompt tokens</span></div>
        <div className="metric"><b>{run.completion_tokens}</b><span>completion tokens</span></div>
        <div className="metric"><b>{run.cached_prompt_tokens}</b><span>cache-hit tokens</span></div>
        <div className="metric"><b>{run.cost_total.toExponential(2)}</b><span>估算费用</span></div>
        <div className="metric"><b>{run.cost_savings.toExponential(2)}</b><span>缓存节省</span></div>
      </div>
      {run.result?.final_answer ? (
        <article className="card">
          <h2>最终结论</h2>
          <p>{run.result.final_answer}</p>
        </article>
      ) : null}
      {verdict ? (
        <article className="card">
          <h2>复核 {verdict.passed ? "通过" : "未通过"}</h2>
          <p>{verdict.comments}</p>
          <div>{Object.entries(verdict.scores).map(([name, score]) => (
            <span className="pill" key={name}>{name} {score}</span>
          ))}</div>
        </article>
      ) : null}
      {(run.result?.expert_outcomes ?? []).map((expert) => (
        <article className="card" key={expert.role_id}>
          <div className="row">
            <strong>{expert.role_id}</strong>
            <span className={statusClass(expert.status)}>{expert.status}</span>
          </div>
          <p className="muted">{expert.sub_question}</p>
          <p className="hint">
            prompt {expert.prompt_tokens} · completion {expert.completion_tokens} · cached {expert.cached_prompt_tokens}
            {expert.skip_reason ? ` · ${expert.skip_reason}` : ""}
          </p>
          {expert.error ? <p className="error">{expert.error}</p> : null}
          {expert.output ? <pre>{JSON.stringify(expert.output, null, 2)}</pre> : null}
        </article>
      ))}
      {run.result?.usage_by_role ? (
        <article className="card">
          <h2>分角色用量</h2>
          {run.result.usage_by_role.map((row) => (
            <div key={`${row.role_id}-${row.step}`}>
              {row.role_id} / {row.step} · prompt {row.prompt_tokens} · cached {row.cached_prompt_tokens} · {row.cache_scope}
            </div>
          ))}
        </article>
      ) : null}
      <article className="card">
        <h2>审计链 {audit ? (audit.chain.ok ? "完整" : `在 ${audit.chain.broken_at} 处断裂`) : ""}</h2>
        <ul className="timeline">
          {(audit?.events ?? []).map((event) => (
            <li key={event.seq}>
              <span className="pill">{event.seq}</span> {event.event_type}
              {event.role_id ? ` · ${event.role_id}` : ""}
              <div className="muted">{new Date(event.ts * 1000).toLocaleString()}</div>
              {Object.keys(event.payload).length > 0 ? <pre>{JSON.stringify(event.payload)}</pre> : null}
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}
