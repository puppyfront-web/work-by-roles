# 阶段4 产品演示指南（可演示产品形态）

> 前置：`pip install -e '.[server]'`（本仓库 `.venv` 已含 fastapi/uvicorn）

## 1. 启动服务

```bash
.venv/bin/python -m uvicorn wbr.app.api.main:create_app --factory --port 8000
# 或嵌入方式：
.venv/bin/python -c "
from wbr.app.api.main import create_app
import uvicorn; uvicorn.run(create_app(data_root='./wbr-data'), port=8000)
"
```

## 2. 网页搭建专家团 → 运行 → 看结果 → 导出审计

1. 浏览器打开 `http://127.0.0.1:8000/canvas`。
2. **建契约**：点击「新建契约」→ 填 role_id/名称/角色类型（coordinator / expert ×N / verifier）→ 保存。
   - 表单实时校验输出 Schema JSON（合法 ✓ / 非法 ✗）。
   - 保存即定版（内容哈希），画布节点显示 `v版本 + hash 前 8 位`。
3. **看画布**：节点自动布局为 Coordinator → Experts → Verifier 拓扑；节点可拖拽微调。
4. **运行会审**：右侧「会审运行」输入问题 → 勾选专家 → ▶ 运行 → 每 400ms 轮询直至 done/failed。
   - 结果时间线：最终答案、各专家结论卡片（含违规标记）、分歧卡片（⚔ 分歧留存，双方立场原样展示）。
   - **分歧高亮**：存在分歧时相关专家节点变红色虚线框、连边变红。
5. **导出审计**：

```bash
curl 'http://127.0.0.1:8000/api/v1/audits/export?contents=false' -o audit-pack.json
python -m json.tool audit-pack.json | head -30   # format_version/sessions/events/integrity.content_digest
```

## 3. API 速览（curl）

```bash
# 契约 CRUD + 版本
curl -X POST http://127.0.0.1:8000/api/v1/contracts -H 'Content-Type: application/json' \
  -d '{"contract": {...}}'                       # 201 定版
curl http://127.0.0.1:8000/api/v1/contracts/expert_a/versions
curl 'http://127.0.0.1:8000/api/v1/contracts/expert_a/diff?from=1.0.0&to=1.1.0'
curl -X PUT http://127.0.0.1:8000/api/v1/contracts/expert_a -d '{"contract": {...}}' -H 'Content-Type: application/json'

# 会审（异步任务）
curl -X POST http://127.0.0.1:8000/api/v1/reviews -H 'Content-Type: application/json' \
  -d '{"question":"...","coordinator":"coordinator","experts":["expert_a"],"verifier":"verifier"}'
curl http://127.0.0.1:8000/api/v1/reviews/<task_id>

# Harness 回归（异步任务）
curl -X POST http://127.0.0.1:8000/api/v1/harness/regressions -H 'Content-Type: application/json' \
  -d '{"contract_ids":["coordinator","expert_a","verifier"],"suite":{"suite_id":"s1","cases":[{"case_id":"c1","question":"..."}]}}'
curl http://127.0.0.1:8000/api/v1/harness/regressions/<task_id>   # 报告含六项指标
```

错误体统一为 `{"error": {"code": "E9003", "message": "契约不存在: ..."}}`（404/409/422 语义正确）。

## 4. 长任务说明

默认使用进程内 asyncio 队列（`InProcessTaskQueue`，lifespan 自动起停）；任务落盘于
`<data_root>/tasks/`，重启后 DONE/FAILED 可查、PENDING 自动重投递（`JsonTaskStore.resubmit_pending`）。
接口为 `TaskQueue` 协议，可替换外部 broker（V1.x+）。

> 默认 Invoker 为确定性演示实现（无外部 LLM 依赖）；生产接入真实模型时向
> `create_app(invoker=...)` 注入任意 `ModelInvoker` 实现（如 Adapter 层的 LangChain 封装）。
