# 真实项目验证指南（Pilot Runbook）

> 目的：把本系统接入一个**真实在跑的项目/团队**，用最小成本验证治理能力是否产生实际收益。
> 建议周期：2 周（第 1 周接入+基线，第 2 周回归+对比评估）。

---

## 0. 验证目标与成功判据（先定义"有效"）

| # | 假设 | 度量 | 达标线 |
|---|---|---|---|
| V1 | 会审能拦住不合格输出 | Schema/禁区违规拦截率（审计事件统计） | 对人工抽检准确率 ≥80% |
| V2 | 契约可安全演化 | 改契约后一键回归，退化被自动检出 | 人为植入退化 100% 被报告 |
| V3 | 分歧有价值而非噪音 | 分歧检出后人工判"确属争议"占比 | ≥60%（否则收紧拆解/复核契约） |
| V4 | 缓存/成本收益 | 缓存命中率、循环 Token 占比 | 命中率 ≥30%（重复问题场景）；loop_token_ratio ≤0.4 |
| V5 | 3 行接入承诺 | 存量 LangGraph 图 wrap 后业务无感 | 业务键逐字节不变 + 原节点调用次数不变 |

---

## 1. 环境准备（半天）

```bash
# 在真实项目仓库内
python -m venv .wbr-venv && source .wbr-venv/bin/activate
pip install "work-by-roles @ file:///path/to/dist/work_by_roles-2.1.1-py3-none-any.whl"
pip install "work-by-roles[langgraph]"        # 若接 LangGraph
```

准备两样东西（不需要真实 LLM 也能先跑通链路，用 ScriptedInvoker 验证流程）：
1. **黄金问题集**：从团队工单/评审记录里挑 10~20 个真实问题（这是 Harness 的地基）；
2. **模型 Invoker**：实现 `ModelInvoker` 协议接你们真实在用的模型（见 §2）。

---

## 2. 接入真实模型（1 个文件，约 30 行）

```python
# my_project/wbr_invoker.py
import time
from wbr.core.orchestration import ModelRequest, ModelResponse, TokenUsage
from wbr.core.orchestration.invoker import parse_json_output

class ProductionInvoker:
    """把 wbr 的请求翻译成你们现有模型网关调用。"""
    def __init__(self, client, model="your-production-model"):
        self.client, self.model = client, model

    def invoke(self, request: ModelRequest) -> ModelResponse:
        t0 = time.time()
        resp = self.client.chat(
            model=self.model,
            system=request.compiled_prompt.system_prompt,
            user=request.compiled_prompt.user_block,
        )
        # 真实用量优先用网关返回；没有则用启发式计数兜底
        from wbr.core.token.meter import HeuristicTokenCounter
        c = HeuristicTokenCounter()
        usage = TokenUsage(prompt_tokens=c.count(request.compiled_prompt.system_prompt),
                           completion_tokens=c.count(resp.text))
        return ModelResponse(text=resp.text, usage=usage)
```

要点：**只换 Invoker，其余全部不动**——这是 Core 框架无关设计的验证点。

---

## 3. 路线 A：LangGraph 存量项目（3 行接入，验证 V1/V5）

```python
from wbr.adapters.langgraph import WBRGuard
from wbr.core.audit import AuditTrail
from wbr.core.contract import RoleContract, RoleIdentity, RoleType, Sop, SopStep, OutputSpec

# ① 给你们现有 agent 节点写一份契约（真实输出 Schema 从生产日志里抄）
contract = RoleContract.build(
    identity=RoleIdentity(role_id="legacy_agent", name="存量Agent", role_type=RoleType.EXPERT),
    sop=Sop(steps=[SopStep(step_id="work", title="执行", instruction="按原有业务逻辑处理")]),
    output_spec=OutputSpec(schema={
        "type": "object",
        "required": ["answer"],                    # 按真实输出结构调整
        "properties": {"answer": {"type": "string", "minLength": 1}},
    }, strict=False),                              # 灰度期先非严格，观察一周再收紧
)
trail = AuditTrail()

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 第 1 行
graph = guard.wrap(your_compiled_graph)                          # 第 2 行
result = graph.invoke({"question": real_user_question})          # 第 3 行
```

**一周观察清单**：
- `result["wbr__meta"]["violations"]` 与 `trail` 事件：有没有真实拦截/误报；
- 业务侧回归：原有功能测试全量跑一遍（这是 V5 的判据）；
- 每天抽样 5 条 `input_scan` 高危记录人工复核（防误报伤客）。
- 稳定后再切 `security="block"`、`schema_validation="block"`（先记录后阻断的灰度节奏）。

## 4. 路线 B：独立会审试点（验证 V1~V4）

```bash
# 用官方模板起步，替换 invoker 为 §2 的生产实现
wbr run-team arch_review_team "试点问题"   # 先跑通链路
```

程序化试点（推荐落进你们 CI 的 nightly）：

```python
from wbr import BaselineSnapshot, CaseSuite, GoldenCase, RegressionEngine, FeedbackLoop
from wbr.templates.registry import load_team_spec
from my_project.wbr_invoker import ProductionInvoker

spec = load_team_spec("arch_review_team")
suite = CaseSuite(suite_id="pilot")
for i, q in enumerate(load_real_questions()):      # ① 真实问题集
    suite.add(GoldenCase(case_id=f"q{i}", question=q, expert_role_ids=[
        e.role_id for e in spec.experts]))

baseline = BaselineSnapshot.capture(contracts=spec.contracts, suite=suite,
                                    model_fingerprint="pilot-week1")
engine = RegressionEngine(contracts=spec.contracts, invoker=ProductionInvoker(...))
report = engine.run_suite(suite, baseline=baseline, stability_runs=2)
print(report.metrics.to_dict())                     # ② 首周基线指标
report.save("pilot-week1.json")
```

**第二周做两件事**：
1. **退化演练（验证 V2）**：故意把某专家契约的禁区放宽（`with_changes`），重跑回归——`compare_with` 必须报出退化项，证明护栏有效，然后还原契约；
2. **反馈闭环（验证 V3）**：把试点期间人工复核不认可的结论用 `FeedbackLoop.record(rating="down", ...)` 记录，周末 `to_golden_cases()` 生成负样本用例，纳入下轮回归。

---

## 5. 评估产出（两周后出具）

从系统导出三份数据，对照 §0 判据表：

| 数据 | 来源 |
|---|---|
| 拦截/误报明细 | `AuditPackBuilder(...).build()` 审计包 + `wbr__meta.violations` |
| 六项指标基线与变化 | 两份 `RegressionReport.compare_with()` |
| 缓存与成本 | `ContractBoundCache.stats.hit_rate`、`LoopMetrics.from_snapshots(..., main_task_tokens=...)` |

达标 → 扩大灰度（更多 agent 节点接入 / 切 block 模式）；不达标 → 按 `docs/HARNESS.md` 调整契约（这正是契约驱动的意义：调优对象是契约文本而非散落代码）。

---

## 6. 常见坑位（试点期提前规避）

| 现象 | 处置 |
|---|---|
| strict 模式误杀过多 | 先 `strict=False` 跑一周看违规分布，再按数据收紧 Schema |
| 专家输出不是纯 JSON | 检查契约 `output_spec.schema` 是否与提示词要求一致；`parse_json_output` 已容忍 ```json 围栏 |
| 分歧过多噪音大 | Coordinator 契约里收紧"同一子问题只派一个专家"，或提高 Verifier `overall_pass_threshold` |
| 缓存命中率低 | 确认问题文本稳定性（语义缓存可缓解）；证据快照频繁变化会天然 miss |
| 内循环频繁打满 | 契约里下调 `max_rounds` 或放宽 `evidence` 退出条件；观察 `LoopMetrics.timeout_rate` |

---

## 7. 首个实战记录：内容生产流水线（2026-10-17，DeepSeek real-run）

> 本节是 §0 判据的第一次真实检验：用 `content_creation_team`（三写手竞稿 + 主编终审）
> 产出小红书推广笔记，再用 `content_review_team`（事实核查/平台合规/转化力 + 终审）做发布前把关。
> 模型：deepseek-chat，temperature=0.3，两次会审共 8 次真实 LLM 调用，总耗时约 26 秒。

### 7.1 真实模型首跑暴露并修复的三个引擎缺陷

| # | 现象 | 根因 | 修复 + 防回归 |
|---|---|---|---|
| B1 | 主编阶段整体失败：`float() argument must be... not 'dict'` | 真实模型返回嵌套 scores（`{"维度": {"score": 0.8, "评语": …}}`），Verdict 构造硬 `float(v)` 崩溃（演示模式从未暴露） | `_coerce_scores` 容错（嵌套取 score 字段/数值叶子均值）；`test_review_robustness.py` 6 断言 |
| B2 | evidence_writer 被禁区误判"编造数据" | 禁区规则编译进 system prompt，写手自检时复述规则原文，字面匹配 `rule in raw_text` 系统性误报 | 否定感知 tripwire：规则按标点拆段、命中前近旁有否定/自我约束词不计违规 |
| B3 | 三个写手全部跑题/拒稿（主编裁决"三稿均不可用"） | 专家输入只有协调者的 sub_question，不携带原始问题；真实协调者产出"写故事型初稿"这类薄指令 | 专家输入 = 原始问题 + `[你的子任务]`；主编摘要本已含 question。回归测试断言 user_block 必含原始问题 |

**这本身就是 §0-V1 的佐证**：主编（LLM）与引擎门禁（Schema/禁区）各自拦下了不合格产出，
且失败原因全部留痕于审计事件。

### 7.2 修复后的产出（摘录）

**创作团终稿**（主编从三稿中选定故事型，理由：平台调性/冲突感标题/场景化细节）：

> 标题：被多Agent协作逼疯后，我开源了一个「AI专家团治理系统」
> 上个月接了个私活，让几个AI角色组队写行业分析。结果产品经理AI和架构师AI吵了三天……
> 1️⃣ 角色有契约…… 2️⃣ 结论有证据…… 3️⃣ 改动有回归……
> 评论区扣「治理」…… GitHub搜 work-by-roles，求个star⭐

**评审团把关结果（passed=False，禁止直接发布）**：

- 事实核查：全部可检验主张判 unverifiable——其中指出"「一行 pip 就能装」在包未发布至 PyPI 时
  即为虚假陈述"（**属实：本项目尚未发布 PyPI**）；"改不翻车"与文中"改一行 prompt 全崩"自相矛盾
- 平台合规：`评论区扣「治理」`＝诱导互动 + 关键词私域引流（medium）；`GitHub 求 star`＝
  站外导流（**high**，小红书真实红线）
- 终审三维评分：事实准确性 0.35 / 合规安全性 0.40 / 转化力 0.72，输出逐条必改清单

### 7.3 结论与使用要点

1. **流水线价值实证**：会编故事的写手 + 不放水的编辑——创作团的高转化产出恰恰需要评审团拦截
2. **给事实核查专家喂材料**：fact_checker 无外部检索时，凡不可核验一律判 unverifiable；
   实际使用应把产品资料/数据来源放入角色知识库（evidence 通道），否则全篇都会被判不可验证
3. **待办**：发布 PyPI 前，终稿的"pip 一行装"表述必须先落实或删除
