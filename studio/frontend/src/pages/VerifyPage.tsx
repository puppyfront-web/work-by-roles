import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";

export function VerifyPage() {
  const [params] = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      await api("/api/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) });
      setMessage("邮箱已验证，可以返回工作区。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    }
  }

  return (
    <main className="auth card">
      <h1>验证邮箱</h1>
      <p className="muted">把日志里的令牌贴在这里，或直接打开邮件里的链接。</p>
      <form onSubmit={submit}>
        <label>
          <span>令牌</span>
          <input value={token} onChange={(event) => setToken(event.target.value)} required />
        </label>
        {error ? <p className="error">{error}</p> : null}
        {message ? <p className="muted">{message}</p> : null}
        <button type="submit">验证</button>
      </form>
      <p><Link to="/login">返回登录</Link></p>
    </main>
  );
}
