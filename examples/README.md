# 示例索引（全部开箱可跑，无外部 LLM 依赖）

所有示例使用确定性脚本 Invoker（`ScriptedInvoker` / 演示模式），克隆仓库、装好依赖即可运行：

```bash
pip install -e ".[langgraph]"
```

| 阶段 | 示例 | 演示内容 | 运行 |
|---|---|---|---|
| 1 (V0.1) | [phase1_core_demo.py](phase1_core_demo.py) | 契约声明/序列化/编译/Diff/四层记忆/纯 Core 会审/分歧留存/审计链 | `python examples/phase1_core_demo.py` |
| 2 (V0.2) | [phase2/legacy_plugin_integration.py](phase2/legacy_plugin_integration.py) | 存量 LangGraph 图 **3 行接入** + 注入阻断 | `python examples/phase2/legacy_plugin_integration.py` |
| 2 (V0.2) | [phase2/native_graph.py](phase2/native_graph.py) | 原生会审 Graph 一键生成 + HITL 断点续跑 | `python examples/phase2/native_graph.py` |
| 3 (V0.3) | [phase3_harness_demo.py](phase3_harness_demo.py) | 基线快照/一键回归/**能力退化检出**/缓存失效联动/审计包 | `python examples/phase3_harness_demo.py` |
| 4 (V0.4) | [phase4_demo.md](phase4_demo.md) | API+画布产品形态：启动→建团→运行→分歧高亮→导出审计 | 文档指引（uvicorn） |
| 5 (V1.0) | CLI | `wbr run-team arch_review_team "问题"`（内置演示输出） | `wbr --help` |

辅助模块：[tests_helpers.py](tests_helpers.py)（示例共用的团队契约与脚本构造）。

需要真实模型时，实现 `ModelInvoker` 协议替换示例中的 Invoker 即可（见 docs/INTEGRATION_LANGGRAPH.md §真实模型接入）。
