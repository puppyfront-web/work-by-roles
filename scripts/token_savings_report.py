"""离线演示：用启发式计数和演示 Invoker 套同一份节省回执公式。

用法：python scripts/token_savings_report.py
不读取 API Key，也不访问网络。计数是启发式的（CJK≈1，其他≈1/4）。

这不是某次线上会审的回执。live_run_receipt 固定为 false。
回执字段与内核 SavingsReceipt（savings-receipt-v1）相同。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbr.adapters.demo import SchemaDemoInvoker
from wbr.core.cache import ContractBoundCache
from wbr.core.orchestration.invoker import ModelResponse, TokenUsage
from wbr.core.orchestration.review import ReviewSession
from wbr.core.token.meter import HeuristicTokenCounter, TokenMeter
from wbr.core.token.receipt import FORMULA_ID
from wbr.core.token.savings import SAMPLE_SHARED_CONTEXT, measure_prompt_savings
from wbr.templates.registry import list_teams, load_team_spec

QUESTION = "评审：订单系统是否应该拆成微服务？只评估数据层边界。"


class _HeuristicDemo(SchemaDemoInvoker):
    """演示输出，用量按实际编译后的提示估算。"""

    def __init__(self, question: str, counter: HeuristicTokenCounter) -> None:
        super().__init__(question=question)
        self.counter = counter

    def invoke(self, request) -> ModelResponse:
        resp = super().invoke(request)
        prompt = self.counter.count(
            request.compiled_prompt.system_prompt + "\n" + request.compiled_prompt.user_block
        )
        completion = resp.usage.completion_tokens
        if request.max_tokens is not None:
            completion = min(completion, request.max_tokens)
        return ModelResponse(
            text=resp.text,
            usage=TokenUsage(prompt_tokens=prompt, completion_tokens=completion),
            raw=resp.raw,
        )


def _replay(spec, counter: HeuristicTokenCounter) -> dict:
    """第一次真调用，第二次走契约缓存。只分派第一位专家，其余应被跳过。"""
    meter = TokenMeter(counter=counter)
    invoker = _HeuristicDemo(QUESTION, counter)
    invoker.expert_ids = [spec.experts[0].role_id]
    session = ReviewSession(
        coordinator_contract=spec.coordinator,
        expert_contracts=spec.experts,
        verifier_contract=spec.verifier,
        invoker=invoker,
        token_meter=meter,
        response_cache=ContractBoundCache(),
        shared_context=SAMPLE_SHARED_CONTEXT,
    )
    first_result = session.run(QUESTION)
    first = meter.usage_total
    second_result = session.run(QUESTION)
    second = meter.usage_total - first
    return {
        "replay_billed_first": first,
        "replay_billed_second": second,
        "unassigned_skipped": [
            o.role_id for o in first_result.expert_outcomes if o.skip_reason == "unassigned"
        ],
        "second_run_cache_hits": [
            o.role_id for o in second_result.expert_outcomes if o.cache_hit
        ],
        "first_run_receipt": _demo_receipt(first_result.savings),
        "second_run_receipt": _demo_receipt(second_result.savings),
    }


def _demo_receipt(receipt) -> dict:
    data = receipt.model_dump(mode="json")
    data["live_run"] = False
    return data


def build_savings_report() -> dict:
    counter = HeuristicTokenCounter()
    teams = []
    for item in list_teams():
        spec = load_team_spec(item["name"])
        measured = measure_prompt_savings(
            name=item["name"],
            coordinator=spec.coordinator,
            experts=spec.experts,
            verifier=spec.verifier,
            question=QUESTION,
            counter=counter,
        )
        measured.update(_replay(spec, counter))
        teams.append(measured)
    return {
        "kind": "offline_heuristic_demo",
        "live_run_receipt": False,
        "formula": FORMULA_ID,
        "counter": "heuristic_cjk_1_latin_div_4",
        "scenario": "协调者只分派第一位专家；旧行为仍调用其余专家。共享上下文使用固定的团队约定，不填充到 1024。",
        "note": "演示回执使用 SavingsReceipt 同一公式，但由启发式计数和演示 Invoker 生成，不能当作线上运行回执。",
        "shared_context": SAMPLE_SHARED_CONTEXT,
        "question": QUESTION,
        "teams": teams,
        "deferred": [
            "prompt_tokens_before/after 是提示词离线对比，不是 SavingsReceipt。回执见 first_run_receipt / second_run_receipt。",
            "供应商前缀缓存要共享前缀达到其门槛（OpenAI/Qwen 常见为 1024）才计费优惠；这里只保证前缀对齐，不填充。",
            "max_tokens 已按契约发出。演示输出短于上限，离线数字里看不到补全被截断的节省。",
            "供应商不按段落拆开 cached_tokens。专家调用上的供应商缓存整笔记入 shared_prefix，不再按共享前缀长度切分。",
        ],
    }


def main() -> int:
    json.dump(build_savings_report(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
