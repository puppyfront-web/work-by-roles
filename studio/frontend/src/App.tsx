import { FormEvent, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { ApiError, api, type Workspace } from "./api";
import { KeysPage } from "./pages/KeysPage";
import { RunDetailPage, RunNewPage } from "./pages/RunPage";
import { TeamNewPage, TeamsPage } from "./pages/TeamsPage";

export function token(): string | null {
  return localStorage.getItem("studio_token");
}

export function App() {
  const navigate = useNavigate();
  const [authed, setAuthed] = useState(Boolean(token()));

  useEffect(() => {
    const onLost = () => {
      setAuthed(false);
      navigate("/login");
    };
    window.addEventListener("studio-unauthorized", onLost);
    return () => window.removeEventListener("studio-unauthorized", onLost);
  }, [navigate]);

  if (!authed) {
    return (
      <Routes>
        <Route path="/register" element={<AuthPage mode="register" onAuth={() => setAuthed(true)} />} />
        <Route path="*" element={<AuthPage mode="login" onAuth={() => setAuthed(true)} />} />
      </Routes>
    );
  }

  return <Shell onLogout={() => { localStorage.removeItem("studio_token"); setAuthed(false); }} />;
}

function Shell({ onLogout }: { onLogout: () => void }) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Workspace[]>("/api/workspaces")
      .then((rows) => setWorkspace(rows[0] ?? null))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "无法加载工作区"));
  }, []);

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">wbr-studio <span>{workspace?.name ?? ""}</span></div>
        <nav>
          <NavLink to="/teams">团队</NavLink>
          <NavLink to="/keys">密钥</NavLink>
          <NavLink to="/runs/new">发起会审</NavLink>
          <button className="quiet" type="button" onClick={onLogout}>退出</button>
        </nav>
      </header>
      {error ? <p className="error">{error}</p> : null}
      {workspace ? (
        <Routes>
          <Route path="/teams" element={<TeamsPage workspaceId={workspace.id} />} />
          <Route path="/teams/new" element={<TeamNewPage workspaceId={workspace.id} />} />
          <Route path="/keys" element={<KeysPage workspaceId={workspace.id} />} />
          <Route path="/runs/new" element={<RunNewPage workspaceId={workspace.id} />} />
          <Route path="/runs/:runId" element={<RunDetailPage workspaceId={workspace.id} />} />
          <Route path="*" element={<Navigate to="/teams" replace />} />
        </Routes>
      ) : null}
    </div>
  );
}

function AuthPage({ mode, onAuth }: { mode: "login" | "register"; onAuth: () => void }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      const body = mode === "login"
        ? { email, password }
        : { email, password, workspace_name: workspaceName };
      const result = await api<{ access_token: string }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      localStorage.setItem("studio_token", result.access_token);
      onAuth();
      navigate("/teams");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth card">
      <h1>{mode === "login" ? "登录" : "注册"}</h1>
      <p className="muted">自带模型密钥，在你的工作区里跑一支专家团。</p>
      <form onSubmit={submit}>
        <label>
          <span>邮箱</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label>
          <span>密码</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={8} required />
        </label>
        {mode === "register" ? (
          <label>
            <span>工作区名称</span>
            <input value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} />
          </label>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={busy}>{busy ? "提交中…" : "继续"}</button>
      </form>
      <p>
        {mode === "login" ? <a href="/register">注册</a> : <a href="/login">已有账号</a>}
      </p>
    </main>
  );
}
