# 阶段4 验收报告（PHASE4 · V0.4 API 服务与可视化画布 MVP）

> 日期：2026-10-14 · 依据：SPEC-005 · 版本：0.4.0 · 结论：**通过，进入阶段5**

## 1. 验收标准核对

| SPEC-005 验收标准 | 证据 | 结果 |
|---|---|---|
| 契约 CRUD + 版本管理 + Diff API | `test_contract_crud_api`（POST/GET/PUT/DELETE/versions/diff 全路径断言） | ✅ |
| 会审任务提交→轮询→完成→结果含分歧 | `test_review_submit_and_result` + 异步 worker 单测 + 落盘恢复 | ✅ |
| 回归任务提交→报告含六项指标 | `test_harness_suite_and_regression`（metrics 键逐一断言） | ✅ |
| 审计导出 API（脱敏开关/trace 过滤） | `test_audit_export` | ✅ |
| 异步任务队列支持长时会审/批量回归 | `InProcessTaskQueue`（asyncio worker）+ `InlineTaskQueue` + `JsonTaskStore` 重启恢复 | ✅ |
| 任务重启恢复 | `test_json_task_store_restart_recovery`（DONE 可查/PENDING 重投） | ✅ |
| 统一错误规范 404/409/422 | `test_unified_error_envelope`（8 条参数化）+ 409/422 专项 | ✅ |
| 画布静态资源可访问且引用合法 | `test_canvas_static.py`（HTML→资源引用全部 200、分歧高亮标识存在） | ✅ |
| 完整可演示产品形态 | `examples/phase4_demo.md` + **真实 uvicorn 冒烟**：healthz/canvas/3 契约/会审 done/审计包 8 events | ✅ |

**阶段4 测试统计：26 passed（累计 227 passed / 1 skipped Redis 门控）**
**真实环境冒烟：`/tmp/wbr_live_smoke.py` 输出 `LIVE SMOKE OK`（uvicorn 127.0.0.1:8907）**

## 2. 关键实现记录
- 请求模型必须定义在模块层：`from __future__ import annotations` 使闭包内局部类注解成为无法解析的 ForwardRef，FastAPI 会把 body 参数误判为 query（TDD 捕获）。
- 统一错误体经单一 `WBRError` 异常处理器 + code→HTTP 状态映射表实现，路由层只抛 AppError 语义码。
- 画布为纯静态三件套（index.html/app.js/style.css），仅消费 API；分歧高亮通过 `state.disputed` 驱动节点红框与红色虚线边。
- 默认 Invoker 为确定性演示实现（`_DemoInvoker`），`create_app(invoker=...)` 可注入任意 ModelInvoker——API 层永不硬编码模型调用。

## 3. 交付物清单
- App：`wbr/app/{store.py, api/main.py, tasks/queue.py, canvas/static/*}`（三件套约 400 行，零外部依赖）
- 测试：`tests/wbr/phase4/`（4 文件 26 用例）
- 文档：`examples/phase4_demo.md`、SPEC-005、本报告

## 4. 遗留事项
- 画布拓扑连线为固定布局算法（Coordinator/Expert/Verifier 三列），未做自由画布编辑——MVP 范围内符合 SPEC（"极简专家画布"）。
- 外部消息队列（Celery/Redis broker）按方案规划不进入 V0.4。
