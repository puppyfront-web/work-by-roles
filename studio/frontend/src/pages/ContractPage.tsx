import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, can, type ContractVersion, type Team } from "../api";

export function ContractPage({ workspaceId, role }: { workspaceId: string; role: string }) {
  const { teamId } = useParams();
  const [team, setTeam] = useState<Team | null>(null);
  const [versions, setVersions] = useState<ContractVersion[]>([]);
  const [text, setText] = useState("");
  const [viewing, setViewing] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function load() {
    if (!teamId) return;
    const [next, history] = await Promise.all([
      api<Team>(`/api/workspaces/${workspaceId}/teams/${teamId}`),
      api<ContractVersion[]>(`/api/workspaces/${workspaceId}/teams/${teamId}/versions`),
    ]);
    setTeam(next);
    setVersions(history);
    setText(JSON.stringify(next.contracts ?? [], null, 2));
    setViewing(next.current_version);
  }

  useEffect(() => {
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId, teamId]);

  async function show(version: number) {
    if (!teamId) return;
    setError("");
    setSaved("");
    const row = await api<{ version: number; contracts: Record<string, unknown>[] }>(
      `/api/workspaces/${workspaceId}/teams/${teamId}/versions/${version}`,
    );
    setViewing(row.version);
    setText(JSON.stringify(row.contracts, null, 2));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!teamId) return;
    setError("");
    setSaved("");
    let contracts: unknown;
    try {
      contracts = JSON.parse(text);
    } catch {
      setError("契约不是合法的 JSON");
      return;
    }
    try {
      const next = await api<Team>(`/api/workspaces/${workspaceId}/teams/${teamId}`, {
        method: "PATCH",
        body: JSON.stringify({ contracts }),
      });
      setTeam(next);
      setSaved(`已保存为 v${next.current_version}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  const editable = can(role, "member") && viewing === team?.current_version;

  return (
    <section>
      <p><Link to="/teams">返回团队</Link></p>
      <div className="row">
        <h1>{team?.name ?? "契约"}</h1>
        <span className="muted">当前 v{team?.current_version ?? ""}</span>
      </div>
      <div className="versions">
        {versions.map((item) => (
          <button
            className={item.version === viewing ? "" : "quiet"}
            type="button"
            key={item.version}
            onClick={() => show(item.version)}
          >
            v{item.version}
          </button>
        ))}
      </div>
      <form className="card" onSubmit={save}>
        <p className="hint">保存前会用内核 RoleContract 校验。历史版本只读，再次保存会生成新版本。</p>
        <textarea className="code" value={text} onChange={(event) => setText(event.target.value)} readOnly={!editable} />
        {error ? <p className="error">{error}</p> : null}
        {saved ? <p className="muted">{saved}</p> : null}
        {can(role, "member") ? <button type="submit">保存为新版本</button> : <p className="muted">只读成员不能修改契约。</p>}
      </form>
    </section>
  );
}
