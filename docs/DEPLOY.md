# 部署指南（API + 画布）

## 安装

包尚未发布到 PyPI。发布之后可以把下面的 Git 地址换成 `work-by-roles[server]`。

```bash
pip install "work-by-roles[server] @ git+https://github.com/puppyfront-web/work-by-roles.git"
# 可选: pip install "work-by-roles[redis] @ git+https://github.com/puppyfront-web/work-by-roles.git"
```

`[server]` 含 fastapi、uvicorn、httpx。只跑 CLI `--live`、不要 API 时，安装 `[llm]` 即可。

## 启动

默认只监听本机。未配置 `WBR_API_KEY` 时不要使用 `--host 0.0.0.0`。

```bash
# 方式一：factory 模式（默认数据目录 ./wbr-data）
uvicorn --factory wbr.app.api.main:create_app --host 127.0.0.1 --port 8000

# 方式二：编程启动（自定义数据目录 / 注入真实模型 Invoker）
python -c "
from wbr.app.api.main import create_app
from my_org.invokers import production_invoker
import uvicorn
app = create_app(data_root='/var/lib/wbr', invoker=production_invoker)
uvicorn.run(app, host='127.0.0.1', port=8000)
"
```

- `GET /canvas`：专家画布 SPA（零外部 CDN，可内网部署）
- `GET /docs`：OpenAPI 交互文档
- `GET /api/v1/healthz`：健康检查（版本、组件状态、`auth_required`）。此接口不要求密钥。

## 鉴权

`WBR_API_KEY` 为空时，行为与旧版本相同，适合本机开发。密钥非空时，除健康检查、`/docs` 和画布静态文件外，契约、会审、Harness、模板导入、审计导出以及 `/canvas/api-bootstrap` 都要带下列之一：

- `X-API-Key: <WBR_API_KEY>`
- `Authorization: Bearer <WBR_API_KEY>`

画布页头有密钥输入框，值只写在当前浏览器会话（`sessionStorage`）里，随后请求都会带上 `X-API-Key`。

对外暴露二选一：

1. 设置 `WBR_API_KEY` 后再把端口暴露出去；
2. 进程继续只听 `127.0.0.1`，由已鉴权的反向代理转发。

未设置密钥却监听到非本机地址（例如 `0.0.0.0`）时，第一条进入进程的 HTTP 请求会打出警告日志。告警看的是 ASGI 的实际监听地址，不看可伪造的 `Host` 头。反向代理若连到本机回环地址，进程看不到公网绑定，此时必须由代理自己鉴权，或仍然设置 `WBR_API_KEY`。

## Workspace

一个进程可以挂多套隔离的契约、用例和任务。不传请求头时使用下面的默认目录，和以前一样。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/workspaces \
  -H 'content-type: application/json' -d '{"name":"team_alpha"}'
curl http://127.0.0.1:8000/api/v1/contracts -H 'X-WBR-Workspace: team_alpha'
```

名称须匹配 `[a-z][a-z0-9_]{0,31}`。画布工具栏的 Workspace 输入框会给后续请求加上同一个头。`GET /api/v1/audits/export` 仍导出整个进程的审计，不按 workspace 过滤。跨 workspace 复制契约：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/workspaces/team_beta/contracts/expert_a/copy \
  -H 'content-type: application/json' -d '{"source":"team_alpha"}'
```

## 会审预算

`POST /api/v1/reviews` 可以带可选字段。不传时与引擎默认一致：协调者没有分派的专家不再空跑，也不设全场 Token 上限。

```json
{
  "question": "如何设计登录认证？",
  "coordinator": "coordinator",
  "experts": ["expert_a"],
  "verifier": "verifier",
  "shared_context": "结论必须能回溯到给定材料。",
  "skip_unassigned_experts": true,
  "token_budget": {
    "max_total_tokens": 8000,
    "per_role": {"expert_a": 2000},
    "on_exceed": "degrade"
  }
}
```

`on_exceed` 取 `degrade` 或 `reject`。超限会跳过该角色并留在结果里，不会把预算异常抛出请求。结果增加 `token_meter`，汇总本次提示、生成和缓存命中的 token。画布会审面板可以填写共享上下文和任务上限。

## 数据布局

```
<data_root>/
├── contracts/<role_id>/versions.json   # 契约全版本快照
├── suites/<suite_id>.json              # 黄金用例库
└── tasks/<task_id>.json                # 任务记录（重启恢复）
```

## 异步任务

- 默认 `InProcessTaskQueue`（asyncio worker，lifespan 自动起停）：`POST /api/v1/reviews`、
  `POST /api/v1/harness/regressions` 立即返回 task_id，轮询 `GET .../{task_id}` 直到 done/failed。
- `JsonTaskStore` 落盘：进程重启后 DONE/FAILED 可查；PENDING/RUNNING 视为中断，
  调用 `store.resubmit_pending(queue)` 重投递。
- 需要跨进程/多副本时实现 `TaskQueue` 协议接入外部 broker（Celery/Redis），接口不变。

## 生产建议

1. **监听与鉴权**：见上文。不要在未配置 `WBR_API_KEY` 时把 uvicorn 绑到 `0.0.0.0`。
2. **模型接入**：`create_app(invoker=...)` 注入生产 ModelInvoker（超时/重试/限流在此封装）。
3. **安全模式**：对外暴露时建议 `WBRGuard(security="block")` 语义接入到自定义节点，
   并启用输入侧 `guard_user_input(block_on=HIGH)`。`WBR_API_KEY` 只保护 HTTP API，不代替输入侧防护。
4. **审计留存**：定期把 `/api/v1/audits/export` 的审计包归档到对象存储（JSON、含 content_digest）。导出接口在启用密钥后同样需要鉴权。
5. **缓存后端**：多副本共享缓存使用 `adapters.storage.redis_backend.RedisCacheBackend`。
6. **反向代理**：uvicorn 前置 Nginx/Caddy 终止 TLS；`/canvas` 与 `/api/v1` 同源无需 CORS。代理若代替应用做鉴权，不要把未鉴权的流量转到应用。

## 版本与升级

- 契约内容哈希只与业务字段相关：升级运行时不会使既有契约失效；
- 缓存条目绑定契约哈希：改契约 → 缓存自动失效，无需手工清理；
- 基线快照随 `baseline_id` 持久化，可跨版本对比回归报告。
