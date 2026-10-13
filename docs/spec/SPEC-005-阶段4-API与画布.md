# SPEC-005 · 阶段4 · V0.4 API 服务与可视化画布 MVP

> 前置：阶段3 完成。目标版本：0.4.0。画布只消费 API，不耦合内核（规则8）。

## 1. FastAPI 后台服务 `wbr/app/api/`

依赖：fastapi/uvicorn/httpx 放在可选组 `server`；`wbr.app.api.main:create_app()` 惰性 import，缺失时抛带指引的 `AppError`。

### 1.1 存储层 `wbr/app/store.py`
- `JsonFileStore(root: Path)`：契约库/会审记录/回归报告的落盘（JSON 文件，进程内锁）；`ContractRegistry`：CRUD + 版本历史（保存每个版本快照，`list_versions(cid)`、`get_version(cid, version|hash)`、`diff_versions(cid, v1, v2)`）。

### 1.2 路由（全部 /api/v1 前缀，Pydantic request/response 模型）
| 方法与路径 | 功能 |
|---|---|
| `POST /contracts` | 创建契约（校验+hash 定版） |
| `GET /contracts` · `GET /contracts/{cid}` | 列表 / 详情（含全部版本号） |
| `PUT /contracts/{cid}` | 更新为新版本（自动 diff、缓存失效联动） |
| `DELETE /contracts/{cid}` | 删除 |
| `GET /contracts/{cid}/versions` / `GET /contracts/{cid}/versions/{v}` | 版本历史 / 指定版本 |
| `GET /contracts/{cid}/diff?from=&to=` | 版本 Diff 报告 |
| `POST /reviews` | 提交会审任务 `{question, coordinator, experts[], verifier}` → task_id |
| `GET /reviews/{task_id}` · `GET /reviews` | 任务状态与结果（含分歧点） / 列表 |
| `POST /harness/suites` · `GET /harness/suites/{sid}` | 创建/查看黄金用例库 |
| `POST /harness/regressions` | 提交回归任务 `{suite_id, contracts, baseline_id?}` → task_id |
| `GET /harness/regressions/{task_id}` | 回归报告（含 metrics、degradation） |
| `GET /audits/export?trace_id=&review_id=&contents=` | 审计包 JSON 下载 |
| `GET /healthz` | 健康检查（版本、组件开关状态） |

错误规范：统一 `{"error": {"code": "E2xxx", "message": ...}}`；404/409/422 语义正确（重复版本、未知 cid 等）。

### 1.3 画布静态托管
- `GET /canvas` 返回 SPA；`/canvas/static/*` 托管资源；`GET /canvas/api-bootstrap` 返回画布所需契约清单摘要。

## 2. 极简专家画布 `wbr/app/canvas/static/`（原生 JS+SVG，D-10）
- 画布区（SVG）：专家节点拖拽定位（节点=角色契约，显示 role_id/type/version/hash 前 8 位）；连线表达 Coordinator→Experts→Verifier 会审拓扑（自动布局 + 可拖动微调）。
- 右侧面板：契约可视化编辑（表单化：基础信息/SOP 步骤增删/禁区/输出 schema(JSON 文本框+校验反馈)/工具白名单/记忆权限/Token 配额/评审标准）→ 保存调用 `PUT /contracts`。
- 运行区：输入问题 → `POST /reviews` → 轮询 `GET /reviews/{id}` → 结果时间线展示（专家结论卡片、verifier 裁决）。
- 分歧点高亮：disagreements 渲染为红色虚线连接冲突专家节点 + 侧栏分歧详情（分歧留存的可视化）。
- 单文件原则：`index.html + app.js + style.css`，零构建、零外部 CDN 依赖。

## 3. 异步任务队列 `wbr/app/tasks/`
```python
TaskRecord: task_id / kind(REVIEW|REGRESSION) / payload / status(PENDING/RUNNING/DONE/FAILED)
          / result: Any|None / error / created_at/started_at/finished_at
TaskQueue(Protocol): submit(record) / get(task_id) / list()
InProcessTaskQueue: asyncio 队列 + 后台 worker 协程（create_app 启动 lifespan 内拉起）
JsonTaskStore(root): TaskRecord 落盘，重启后 DONE/FAILED 记录可查，PENDING 重投递
```
- 长时会审/批量回归经队列异步执行；API 立即返回 task_id。
- 同步直通模式 `TaskQueue` 可替换为 `InlineTaskQueue`（测试与嵌入式场景）。

## 4. 验收标准 → 测试映射（tests/wbr/phase4/，全部走 httpx ASGI，无需真实端口）

| 验收标准 | 测试 |
|---|---|
| 契约 CRUD + 版本管理 + Diff API | `test_contracts_api.py` |
| 会审任务提交→轮询→完成→结果含分歧 | `test_review_api.py`（InlineQueue 同步路径）+ `test_tasks_async.py`（异步 worker） |
| 回归任务提交→报告含六项指标 | `test_harness_api.py` |
| 审计导出 API（可下载 JSON、支持脱敏开关） | `test_audit_api.py` |
| 任务重启恢复（DONE 可查/PENDING 重投） | `test_task_store.py` |
| 画布静态资源可访问且引用合法 | `test_canvas_static.py`（资源存在、HTML 引用 200、含关键挂载点） |
| API 错误规范统一 | `test_api_errors.py`（404/409/422 样例） |
| 完整可演示产品形态 | `examples/phase4_demo.md`（启动命令+操作路径截图位说明） |
