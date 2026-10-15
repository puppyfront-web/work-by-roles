# work-by-roles · LLM 专家团治理系统

> 像管理代码一样管理你的 AI 角色：**角色有契约、运行有强制、结论有证据、过程有审计、变更有回归。**

把多个 LLM Agent 拼在一起上生产，通常会撞上三堵墙：**输出不可控**（职责漂移、格式乱飘、一本正经地编造）、**结论不可查**（证据在哪、谁复核过、哪一版提示词，答不上来）、**变更不敢做**（改一行提示词像拆盲盒）。

work-by-roles 的回答：为每个 LLM 角色建立一份**可版本化的角色契约**，用**会审范式**组织协作，在**运行时强制执行**边界，并为每一次变更提供**回归门禁**。

```text
                        ┌─────────────┐
         问题 / 方案 ──▶ │ Coordinator │  拆解子问题、分派专家
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
         ┌──────────┐    ┌──────────┐    ┌──────────┐
         │  专家 A   │    │  专家 B   │    │  专家 C   │  并行作答
         └─────┬────┘    └─────┬────┘    └─────┬────┘   （Schema 校验 + 证据引用强约束）
               └───────────────┼───────────────┘
                               ▼
                        ┌─────────────┐
                        │  Verifier   │  独立复核 · 裁决 · 分歧留存不仲裁
                        └──────┬──────┘
                               ▼
                     结构化结论 + 证据链 + 全程审计事件
```

## 30 秒跑通（无需任何模型 Key）

```bash
pip install "work-by-roles[server]"
wbr run-team arch_review_team "评审：订单系统微服务拆分方案"
```

接入真实模型只需三个环境变量（兼容 OpenAI / DeepSeek / Kimi / Qwen / GLM / Ollama / vLLM）：

```bash
export WBR_LLM_API_KEY=sk-...
export WBR_LLM_MODEL=deepseek-chat
# export WBR_LLM_BASE_URL=https://api.deepseek.com/v1   # 非 OpenAI 厂商必填

wbr run-team arch_review_team "评审：订单系统微服务拆分方案" --live
```

## 导航

| 文档 | 内容 |
|---|---|
| [架构设计](ARCHITECTURE_V2.md) | 三层架构、治理内核全貌、设计决策 |
| [SDK 全量 API](SDK.md) | RoleContract / ReviewSession / 记忆 / 缓存 / 审计 |
| [LangGraph 接入](INTEGRATION_LANGGRAPH.md) | `WBRGuard` 3 行接入存量 Graph |
| [Harness 回归与指标](HARNESS.md) | 黄金用例、基线快照、六项指标、退化检测 |
| [部署指南](DEPLOY.md) | 生产部署、存储选型、OTel |
| [真实项目验证](REAL_WORLD_VALIDATION.md) | 真实项目接入的验证流程 |
| [设计规格](spec/README.md) | SPEC-000~006 + 审核记录 |
| [验收总结](acceptance/FINAL.md) | 阶段验收报告汇总 |

项目主页与快速上手见 [GitHub README](https://github.com/puppyfront-web/work-by-roles#readme)。
