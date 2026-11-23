import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, can, type Team, type TemplateInfo } from "../api";

export function TeamsPage({ workspaceId, role }: { workspaceId: string; role: string }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Team[]>(`/api/workspaces/${workspaceId}/teams`)
      .then(setTeams)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId]);

  return (
    <section>
      <div className="row">
        <h1>团队</h1>
        {can(role, "member") ? <Link className="button" to="/teams/new">从模板创建</Link> : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {teams.length === 0 ? <p className="muted">还没有团队。</p> : null}
      {teams.map((team) => (
        <article className="card" key={team.id}>
          <div className="row">
            <strong>{team.name}</strong>
            <span>
              <Link to={`/teams/${team.id}/contract`}>契约 v{team.current_version}</Link>
              {can(role, "member") ? <> · <Link to={`/runs/new?team=${team.id}`}>发起会审</Link></> : null}
            </span>
          </div>
          <p className="muted">{team.template_name ?? "自定义契约"}</p>
          <div>{team.roles.map((role) => (
            <span className="pill" key={role.role_id}>{role.role_type} · {role.name}</span>
          ))}</div>
        </article>
      ))}
    </section>
  );
}

export function TeamNewPage({ workspaceId }: { workspaceId: string }) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("arch_review_team");
  const [error, setError] = useState("");

  useEffect(() => {
    api<TemplateInfo[]>("/api/templates")
      .then((rows) => {
        setTemplates(rows);
        if (rows[0]) setTemplate(rows[0].name);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/api/workspaces/${workspaceId}/teams`, {
        method: "POST",
        body: JSON.stringify({ name, template }),
      });
      window.location.assign("/teams");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  const selected = templates.find((item) => item.name === template);

  return (
    <section>
      <h1>从模板创建团队</h1>
      <form className="card" onSubmit={submit}>
        <label><span>名称</span><input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label>
          <span>模板</span>
          <select value={template} onChange={(e) => setTemplate(e.target.value)}>
            {templates.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
          </select>
        </label>
        {selected ? (
          <p className="muted">{selected.roles.map((role) => `${role.role_type}:${role.role_id}`).join(" · ")}</p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">创建</button>
      </form>
    </section>
  );
}
