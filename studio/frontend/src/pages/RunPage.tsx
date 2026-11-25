import { FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api, can, type AuditEvent, type AuditPage, type Run, type SavingsReceipt, type Team } from "../api";

const LEVER_LABEL: Record<string, string> = {
  shared_prefix: "共享前缀",
  skipped_unassigned: "跳过未分配专家",
  cache_hit: "缓存命中",
};

function statusClass(status: string): string {
  if (status === "completed") return "pill ok";
  if (status === "failed") return "pill bad";
  return "pill wait";
}

function money(value: number): string {
  if (!value) return "0";
  return value.toExponential(2);
}

function SavingsCard({ receipt, budgetEvents }: { receipt: SavingsReceipt | null; budgetEvents: AuditEvent[] }) {
  return (
    <article className="card" id="savings">
      <div className="row">
        <h2>本次节省</h2>
        <Link to="/savings">计算公式</Link>
      </div>
      {receipt ? (
        <>
          <div className="grid">
            <div className="metric"><b>{receipt.baseline_tokens.toLocaleString("zh-CN")}</b><span>基线 tokens</span></div>
            <div className="metric"><b>{receipt.actual_tokens.toLocaleString("zh-CN")}</b><span>实际 tokens</span></div>
            <div className="metric"><b>{receipt.saved_tokens.toLocaleString("zh-CN")}</b><span>节省 tokens</span></div>
            <div className="metric"><b>{money(receipt.baseline_cost)}</b><span>基线费用</span></div>
            <div className="metric"><b>{money(receipt.actual_cost)}</b><span>实际费用</span></div>
            <div className="metric"><b>{money(receipt.saved_cost)}</b><span>节省费用</span></div>
            <div className="metric"><b>{receipt.cached_prompt_tokens.toLocaleString("zh-CN")}</b><span>cache-hit tokens</span></div>
          </div>
          <table className="lever-table">
            <thead>
              <tr><th>杠杆</th><th>token</th><th>费用</th><th>缓存 token</th><th>角色</th></tr>
            </thead>
            <tbody>
              {receipt.levers.map((lever) => (
                <tr key={lever.id}>
                  <td data-label="杠杆">{LEVER_LABEL[lever.id] ?? lever.id}</td>
                  <td data-label="token">{lever.tokens.toLocaleString("zh-CN")}</td>
                  <td data-label="费用">{money(lever.cost)}</td>
                  <td data-label="缓存 token">{lever.cached_tokens.toLocaleString("zh-CN")}</td>
                  <td data-label="角色">{lever.roles.length ? lever.roles.join("、") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">供应商把缓存算进 prompt 时，token 节省可以是 0，费用仍按未缓存单价对比。未填单价时费用为 0。</p>
        </>
      ) : <p className="muted">这次运行没有节省回执。</p>}
      {budgetEvents.length > 0 ? (
        <>
          <h3>Token 预算超限，已跳过</h3>
          <ul>
            {budgetEvents.map((event) => (
              <li key={event.seq}>
                {event.role_id ?? "本次会审"}
                {typeof event.payload.reason === "string" ? `：${event.payload.reason}` : ""}
              </li>
            ))}
          </ul>
          <p className="hint">预算跳过不计入节省。</p>
        </>
      ) : receipt && receipt.budget_skipped.length > 0 ? (
        <>
          <h3>Token 预算超限，已跳过</h3>
          <ul>
            {receipt.budget_skipped.map((item) => (
              <li key={`${item.step}-${item.role_id}`}>{item.role_id} · {item.step}</li>
            ))}
          </ul>
          <p className="hint">预算跳过不计入节省。</p>
        </>
      ) : null}
    </article>
  );
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
  const [team, setTeam] = useState<Team | null>(null);
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
        try {
          const source = await api<Team>(`/api/workspaces/${workspaceId}/teams/${next.team_id}`);
          if (!stop) setTeam(source);
        } catch {
          if (!stop) setTeam(null);
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
  const finished = run.status !== "queued" && run.status !== "running";
  const budgetEvents = (audit?.events ?? []).filter((event) => event.event_type === "token_budget_exceeded");

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
      {team?.template_name ? <p className="muted">模板 {team.template_name}</p> : null}
      <p>{run.question}</p>
      {run.error ? <p className="error">{run.error}</p> : null}
      {finished && run.result?.final_answer ? (
        <article className="card">
          <h2>最终结论</h2>
          <p>{run.result.final_answer}</p>
        </article>
      ) : null}
      {finished ? <SavingsCard receipt={run.savings} budgetEvents={budgetEvents} /> : null}
      {finished ? <p><a href="#audit">核对审计链</a></p> : null}
      <div className="grid">
        <div className="metric"><b>{run.prompt_tokens}</b><span>prompt tokens</span></div>
        <div className="metric"><b>{run.completion_tokens}</b><span>completion tokens</span></div>
        <div className="metric"><b>{run.cached_prompt_tokens}</b><span>cache-hit tokens</span></div>
        <div className="metric"><b>{money(run.cost_total)}</b><span>估算费用</span></div>
      </div>
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
      <article className="card" id="audit">
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
