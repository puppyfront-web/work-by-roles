import { FormEvent, useEffect, useState } from "react";

import { api, type ProviderKey } from "../api";

export function KeysPage({ workspaceId }: { workspaceId: string }) {
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [error, setError] = useState("");
  const [name, setName] = useState("默认");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [model, setModel] = useState("gpt-4o-mini");
  const [apiKey, setApiKey] = useState("");

  async function reload() {
    setKeys(await api<ProviderKey[]>(`/api/workspaces/${workspaceId}/provider-keys`));
  }

  useEffect(() => {
    reload().catch((err: unknown) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [workspaceId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(`/api/workspaces/${workspaceId}/provider-keys`, {
        method: "POST",
        body: JSON.stringify({ name, base_url: baseUrl, model, api_key: apiKey }),
      });
      setApiKey("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function remove(id: string) {
    await api(`/api/workspaces/${workspaceId}/provider-keys/${id}`, { method: "DELETE" });
    await reload();
  }

  return (
    <section>
      <h1>供应商密钥</h1>
      <p className="muted">密钥只在服务端加密保存。页面上之后只能看到末四位。</p>
      <form className="card" onSubmit={submit}>
        <label><span>名称</span><input value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label><span>Base URL</span><input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} required /></label>
        <label><span>模型</span><input value={model} onChange={(e) => setModel(e.target.value)} required /></label>
        <label>
          <span>API Key</span>
          <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type="password" required />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button type="submit">保存</button>
      </form>
      {keys.map((key) => (
        <article className="card row" key={key.id}>
          <div>
            <strong>{key.name}</strong>
            <div className="muted">{key.model} · {key.base_url}</div>
            <div>····{key.key_hint}</div>
          </div>
          <button className="quiet" type="button" onClick={() => remove(key.id)}>删除</button>
        </article>
      ))}
    </section>
  );
}
