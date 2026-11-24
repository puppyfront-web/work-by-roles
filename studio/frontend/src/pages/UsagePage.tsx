import { useEffect, useState } from "react";

import { api, type UsageBucket, type UsageReport } from "../api";

function tokens(value: number): string {
  return value.toLocaleString("zh-CN");
}

function money(value: number): string {
  if (!value) return "0";
  return value.toExponential(2);
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function Bars({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <div className="bars">
      {rows.map((row) => (
        <div className="bar-row" key={row.label}>
          <span>{row.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(row.value / max) * 100}%` }} />
          </div>
          <span>{tokens(row.value)}</span>
        </div>
      ))}
    </div>
  );
}

function Cells({ bucket }: { bucket: UsageBucket }) {
  return (
    <>
      <td>{tokens(bucket.prompt_tokens)}</td>
      <td>{tokens(bucket.completion_tokens)}</td>
      <td>{tokens(bucket.cached_prompt_tokens)}</td>
      <td>{percent(bucket.cache_hit_rate)}</td>
      <td>{money(bucket.cost_total)}</td>
    </>
  );
}

export function UsagePage({ workspaceId }: { workspaceId: string }) {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<UsageReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<UsageReport>(`/api/workspaces/${workspaceId}/usage?days=${days}`)
      .then(setReport)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId, days]);

  return (
    <section>
      <div className="row">
        <h1>用量</h1>
        <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
          <option value={7}>近 7 天</option>
          <option value={30}>近 30 天</option>
          <option value={90}>近 90 天</option>
        </select>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {report ? (
        <>
          <div className="grid">
            <div className="metric"><b>{tokens(report.totals.prompt_tokens)}</b><span>prompt tokens</span></div>
            <div className="metric"><b>{tokens(report.totals.completion_tokens)}</b><span>completion tokens</span></div>
            <div className="metric"><b>{tokens(report.totals.cached_prompt_tokens)}</b><span>cache-hit tokens</span></div>
            <div className="metric"><b>{percent(report.totals.cache_hit_rate)}</b><span>缓存命中率</span></div>
            <div className="metric"><b>{money(report.totals.cost_total)}</b><span>估算费用</span></div>
            <div className="metric"><b>{tokens(report.totals.saved_tokens ?? 0)}</b><span>累计节省 tokens</span></div>
            <div className="metric"><b>{money(report.totals.saved_cost ?? 0)}</b><span>估算节省费用</span></div>
          </div>
          <p className="hint">节省来自每次运行的回执（基线减实际），不是比例。</p>
          <article className="card">
            <h2>按天</h2>
            {report.by_day.length === 0 ? <p className="muted">这段时间没有已结束的运行。</p> : (
              <Bars rows={report.by_day.map((row) => ({ label: row.day, value: row.prompt_tokens }))} />
            )}
          </article>
          <article className="card">
            <h2>按模型</h2>
            <table>
              <thead>
                <tr><th>模型</th><th>prompt</th><th>completion</th><th>cached</th><th>命中率</th><th>费用</th></tr>
              </thead>
              <tbody>
                {report.by_model.map((row) => (
                  <tr key={row.model}><td>{row.model}</td><Cells bucket={row} /></tr>
                ))}
              </tbody>
            </table>
          </article>
          <article className="card">
            <h2>按角色</h2>
            <table>
              <thead>
                <tr><th>角色</th><th>prompt</th><th>completion</th><th>cached</th><th>命中率</th><th>费用</th></tr>
              </thead>
              <tbody>
                {report.by_role.map((row) => (
                  <tr key={row.role_id}><td>{row.role_id}</td><Cells bucket={row} /></tr>
                ))}
              </tbody>
            </table>
          </article>
        </>
      ) : null}
    </section>
  );
}
