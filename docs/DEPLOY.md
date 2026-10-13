# 部署指南（API + 画布）

## 安装

```bash
pip install "work-by-roles[server]"        # fastapi + uvicorn + httpx
# 可选: pip install "work-by-roles[redis]"  # 记忆/缓存持久化
```

## 启动

```bash
# 方式一：factory 模式（默认数据目录 ./wbr-data）
uvicorn --factory wbr.app.api.main:create_app --host 0.0.0.0 --port 8000

# 方式二：编程启动（自定义数据目录 / 注入真实模型 Invoker）
python -c "
from wbr.app.api.main import create_app
from my_org.invokers import production_invoker
import uvicorn
app = create_app(data_root='/var/lib/wbr', invoker=production_invoker)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

- `GET /canvas`：专家画布 SPA（零外部 CDN，可内网部署）
- `GET /docs`：OpenAPI 交互文档
- `GET /api/v1/healthz`：健康检查（版本 + 组件状态）

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

1. **模型接入**：`create_app(invoker=...)` 注入生产 ModelInvoker（超时/重试/限流在此封装）。
2. **安全模式**：对外暴露时建议 `WBRGuard(security="block")` 语义接入到自定义节点，
   并启用输入侧 `guard_user_input(block_on=HIGH)`。
3. **审计留存**：定期把 `/api/v1/audits/export` 的审计包归档到对象存储（JSON、含 content_digest）。
4. **缓存后端**：多副本共享缓存使用 `adapters.storage.redis_backend.RedisCacheBackend`。
5. **反向代理**：uvicorn 前置 Nginx/Caddy 终止 TLS；`/canvas` 与 `/api/v1` 同源无需 CORS。

## 版本与升级

- 契约内容哈希只与业务字段相关：升级运行时不会使既有契约失效；
- 缓存条目绑定契约哈希：改契约 → 缓存自动失效，无需手工清理；
- 基线快照随 `baseline_id` 持久化，可跨版本对比回归报告。
