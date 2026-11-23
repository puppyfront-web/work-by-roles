import { FormEvent, useEffect, useState } from "react";

import { api, can, roleLabel, type Invite, type Member } from "../api";

export function MembersPage({ workspaceId, role }: { workspaceId: string; role: string }) {
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [link, setLink] = useState("");
  const [error, setError] = useState("");

  async function reload() {
    setMembers(await api<Member[]>(`/api/workspaces/${workspaceId}/members`));
    if (can(role, "admin")) {
      setInvites(await api<Invite[]>(`/api/workspaces/${workspaceId}/invites`));
    }
  }

  useEffect(() => {
    reload().catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId, role]);

  async function invite(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const created = await api<Invite>(`/api/workspaces/${workspaceId}/invites`, {
        method: "POST",
        body: JSON.stringify({ email, role: inviteRole }),
      });
      setLink(created.invite_path ? `${window.location.origin}${created.invite_path}` : "");
      setEmail("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "邀请失败");
    }
  }

  async function changeRole(member: Member, next: string) {
    setError("");
    try {
      await api(`/api/workspaces/${workspaceId}/members/${member.user_id}`, {
        method: "PATCH",
        body: JSON.stringify({ role: next }),
      });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法更改角色");
    }
  }

  async function remove(member: Member) {
    setError("");
    try {
      await api(`/api/workspaces/${workspaceId}/members/${member.user_id}`, { method: "DELETE" });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法移除");
    }
  }

  async function revoke(invite: Invite) {
    await api(`/api/workspaces/${workspaceId}/invites/${invite.id}`, { method: "DELETE" });
    await reload();
  }

  return (
    <section>
      <h1>成员</h1>
      {error ? <p className="error">{error}</p> : null}
      {members.map((member) => (
        <article className="card row" key={member.user_id}>
          <div>
            <strong>{member.email}</strong>
            <div className="muted">{roleLabel(member.role)}</div>
          </div>
          {can(role, "admin") && member.role !== "owner" ? (
            <span className="row">
              <select value={member.role} onChange={(event) => changeRole(member, event.target.value)}>
                <option value="admin">管理员</option>
                <option value="member">成员</option>
                <option value="viewer">只读</option>
                {role === "owner" ? <option value="owner">所有者</option> : null}
              </select>
              <button className="quiet" type="button" onClick={() => remove(member)}>移除</button>
            </span>
          ) : null}
        </article>
      ))}
      {can(role, "admin") ? (
        <form className="card" onSubmit={invite}>
          <h2>邀请</h2>
          <p className="hint">邀请链接会写进服务日志。这里也会显示一次，方便没有邮件服务时复制。</p>
          <label>
            <span>邮箱</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            <span>角色</span>
            <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
              <option value="admin">管理员</option>
              <option value="member">成员</option>
              <option value="viewer">只读</option>
            </select>
          </label>
          <button type="submit">生成邀请</button>
          {link ? <p className="mono">{link}</p> : null}
        </form>
      ) : null}
      {can(role, "admin") ? invites.filter((item) => !item.accepted_at && !item.revoked_at).map((item) => (
        <article className="card row" key={item.id}>
          <div>{item.email} · {roleLabel(item.role)}</div>
          <button className="quiet" type="button" onClick={() => revoke(item)}>撤销</button>
        </article>
      )) : null}
    </section>
  );
}
