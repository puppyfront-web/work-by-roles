import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, type InvitePreview } from "../api";

export function InvitePage({ authed }: { authed: boolean }) {
  const { token } = useParams();
  const navigate = useNavigate();
  const [info, setInfo] = useState<InvitePreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    api<InvitePreview>(`/api/invites/${token}`)
      .then(setInfo)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "邀请无效"));
  }, [token]);

  async function accept() {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/invites/${token}/accept`, { method: "POST" });
      navigate("/teams");
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法接受");
    } finally {
      setBusy(false);
    }
  }

  const next = `/invite/${token ?? ""}`;

  return (
    <main className="auth card">
      <h1>工作区邀请</h1>
      {info ? (
        <p>加入「{info.workspace_name}」，角色为 {info.role}。请使用 {info.email} 的账号接受。</p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {authed ? (
        <button type="button" disabled={busy || !info} onClick={accept}>接受邀请</button>
      ) : (
        <p>
          <Link to={`/login?next=${encodeURIComponent(next)}`}>登录</Link>
          {" · "}
          <Link to={`/register?email=${encodeURIComponent(info?.email ?? "")}&next=${encodeURIComponent(next)}`}>注册</Link>
        </p>
      )}
    </main>
  );
}
