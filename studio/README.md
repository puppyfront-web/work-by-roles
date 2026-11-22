# wbr-studio

wbr-studio 是 work-by-roles 的产品壳：用户注册工作区，加密保存自己的模型 API Key，从内核自带的专家团模板创建团队，然后跑一轮「协调者 → 专家并行 → 复核人」会审。会审在 Redis/Arq worker 里调用内核 `ReviewSession`，token 与缓存命中写回 Postgres，审计事件按工作区串成一条哈希链。

内核 `wbr/` 保持 MIT 库。这里不复制契约引擎。

## 架构

```text
浏览器 (studio/frontend)
    │  /api
    ▼
FastAPI (studio/backend) ── Postgres：用户、工作区、密钥密文、团队契约、运行、审计链
    │ enqueue
    ▼
Arq worker ── Redis
    │
    ▼
wbr.ReviewSession + OpenAICompatInvoker
    密钥在 worker 里解密，只放进请求头，不进响应，也不进审计 payload
```

一个工作区一条审计链。追加时先 `SELECT ... FOR UPDATE` 锁住 `audit_chains` 的链头行，再读取链尾并插入下一序号。哈希使用内核的 `audit_record_hash`（`HASH_ALG = audit_record_hash.v1`）。

## 一条命令启动

需要 Docker。

```bash
./studio/dev.sh
```

脚本会在没有 `studio/.env` 时从 `.env.example` 生成密钥，然后 `docker compose up --build`。

- 界面：http://localhost:5173
- API：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

第一次打开先注册。在「密钥」里保存 OpenAI 兼容端点的 base URL、模型名和 API Key，在「团队」里从模板创建，再发起会审。

## 不用 Docker

Postgres 与 Redis 已在本机时：

```bash
pip install -e ".[llm]"
pip install -e studio/backend
cp studio/.env.example studio/.env   # 改 STUDIO_SECRET_KEY，并生成 STUDIO_FERNET_KEY
set -a && source studio/.env && set +a
cd studio/backend && alembic upgrade head
uvicorn wbr_studio.main:app --reload --port 8000
# 另一个终端：
arq wbr_studio.worker.WorkerSettings
# 前端：
cd studio/frontend && npm install && npm run dev
```

只想在 API 进程里跑会审、暂时不启 worker 时，把 `STUDIO_RUN_INLINE=1`。

## 环境变量

| 变量 | 作用 |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://...` |
| `REDIS_URL` | Arq 队列 |
| `STUDIO_SECRET_KEY` | JWT 签名。为空则 API 拒绝启动 |
| `STUDIO_FERNET_KEY` | 供应商密钥的 Fernet 密钥。为空则从 `STUDIO_SECRET_KEY` 派生。轮换后旧密文无法解密 |
| `STUDIO_RUN_INLINE` | `1` 时不经过 Redis |
| `STUDIO_CORS_ORIGINS` | 逗号分隔。Vite 开发默认走代理，不依赖 CORS |
| `STUDIO_JWT_TTL_MINUTES` | 登录有效期，默认 7 天 |

供应商 API Key 只出现在创建请求里。之后的接口只返回末四位 `key_hint`。库里是密文。

会审费用是估算：创建运行时可以带上每 token 的 `input_price`、`output_price`、`cached_input_price`。缓存命中 token 来自供应商 usage（OpenAI 的 `prompt_tokens_details.cached_tokens` 等），由内核 `parse_provider_usage` 解析。不填单价则只记 token，费用为 0。

## 测试

工作室测试会清空 `STUDIO_TEST_DATABASE_URL`（默认 `postgresql+psycopg://studio:studio@127.0.0.1:5432/studio`）。不要把它指向有数据的库。

```bash
STUDIO_TEST_DATABASE_URL=postgresql+psycopg://studio:studio@127.0.0.1:5432/studio \
  pytest studio/backend/tests -q
cd studio/frontend && npm run typecheck && npm run build
```

会审执行测试注入假的 Invoker，不访问网络。Postgres 审计测试覆盖内核 `AuditStore` 的追加、查询、篡改、缺行、并发和会审 token 事件。

## 开源边界

`wbr/` 和 `studio/` 是 MIT 开源核心。`ee/` 预留给商业许可功能，当前没有功能代码。外部贡献需要签署 CLA，见仓库根目录的 `CLA.md` 和 `CONTRIBUTING.md`。

## 阶段 2 还没做

- 工作区成员、邀请和角色；现在一个工作区只有所有者
- SSO、邮箱验证、限流
- 卡住的 `running` 恢复、取消运行
- 跨运行的缓存命中报表；单次运行的用量已经落库
- 在界面里编辑契约（内核画布仍在 `wbr/app`）
- `ee/`：组织管理、审计导出包、席位许可

## English

wbr-studio is the product shell on the MIT `wbr` kernel. Register a workspace, store an OpenAI-compatible API key encrypted at rest, create a team from a bundled template, and run Coordinator → parallel experts → Verifier. An Arq worker calls `ReviewSession`. Prompt, completion, and cached tokens are stored on the run. Each workspace has one Postgres audit hash chain locked at the tail and hashed with the kernel's `audit_record_hash`.

Start with `./studio/dev.sh` (Docker). UI at http://localhost:5173, API docs at http://localhost:8000/docs. Tests: `pytest studio/backend/tests -q` against `STUDIO_TEST_DATABASE_URL`. The key is never returned after create. `ee/` is a commercial-license placeholder with no features yet. Contributions need the CLA in `CLA.md`.
