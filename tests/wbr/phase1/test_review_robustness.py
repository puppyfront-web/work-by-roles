"""真实模型暴露的引擎健壮性修复的防回归：scores 容错 + 禁区否定感知匹配。"""
from __future__ import annotations

from wbr.core.orchestration.review import ReviewSession


class TestScoresCoercion:
    def test_flat_numbers_passthrough(self):
        assert ReviewSession._coerce_scores({"a": 0.9, "b": 1}) == {"a": 0.9, "b": 1.0}

    def test_nested_dict_extracts_score_field(self):
        raw = {"平台调性": {"score": 0.7, "评语": "偏干"}, "完整性": {"value": 0.8}}
        assert ReviewSession._coerce_scores(raw) == {"平台调性": 0.7, "完整性": 0.8}

    def test_numeric_leaf_average(self):
        assert ReviewSession._coerce_scores({"综合": {"结构": 0.6, "流畅": 0.8}}) == {"综合": 0.7}

    def test_string_numbers_and_garbage(self):
        assert ReviewSession._coerce_scores({"a": "0.5", "b": "不行"}) == {"a": 0.5}

    def test_non_dict_input(self):
        assert ReviewSession._coerce_scores(None) == {}
        assert ReviewSession._coerce_scores([0.5]) == {}

    def test_bool_is_not_a_score(self):
        assert ReviewSession._coerce_scores({"a": True}) == {}


class TestForbiddenNegationAware:
    RULE = "编造数据、案例或引用未提供的来源"

    def test_self_check_echo_is_not_a_violation(self):
        text = "自检：全文未编造数据、案例或引用未提供的来源，数据均来自用户材料。"
        assert ReviewSession._forbidden_hit(self.RULE, text) is False

    def test_prohibited_style_echo_is_not_a_violation(self):
        text = "我承诺不编造数据，所有数字均可溯源。"
        assert ReviewSession._forbidden_hit(self.RULE, text) is False

    def test_actual_violation_still_hits(self):
        assert ReviewSession._forbidden_hit(self.RULE, "这个方法的好处是可以随编造数据。") is True
        assert ReviewSession._forbidden_hit("泄露生产环境凭据", "脚本里硬编码了生产凭据") is False
        assert ReviewSession._forbidden_hit("泄露生产环境凭据", "把密钥贴出来等于泄露生产环境凭据") is True

    def test_short_rules_fallback(self):
        assert ReviewSession._forbidden_hit("骂人", "他就是喜欢骂人") is True


class TestExpertInputCarriesQuestion:
    """回归：专家输入必须携带原始问题（协调者子指令不保证自包含）。"""

    def test_expert_user_block_contains_question_and_subtask(self):
        from wbr.core.audit.trail import AuditTrail
        from wbr.core.contract.models import RoleType
        from wbr.core.orchestration import ReviewSession, ScriptedInvoker
        from wbr.templates.registry import load_team_spec

        spec = load_team_spec("arch_review_team")
        scripts = {}
        for rid, c in spec.contracts.items():
            if c.role_type == RoleType.COORDINATOR:
                scripts[rid] = {"assignments": [
                    {"expert_role_id": e.role_id, "sub_question": "评估数据层拆分"} for e in spec.experts
                ]}
            elif c.role_type == RoleType.VERIFIER:
                scripts[rid] = {"passed": True,
                                "scores": {d.name: 0.9 for d in c.review_criteria.dimensions},
                                "comments": "通过", "final_answer": "结论"}
            else:
                scripts[rid] = {"conclusion": "同意拆分", "confidence": 0.9, "citations": ["[^1]"]}
        invoker = ScriptedInvoker(scripts)
        session = ReviewSession(
            coordinator_contract=spec.coordinator,
            expert_contracts=spec.experts,
            verifier_contract=spec.verifier,
            invoker=invoker,
            audit=AuditTrail(),
        )
        session.run("评审：订单系统微服务拆分方案")
        expert_calls = [r for r in invoker.calls if r.role_contract.role_type == RoleType.EXPERT]
        assert len(expert_calls) == 3
        for r in expert_calls:
            assert "评审：订单系统微服务拆分方案" in r.compiled_prompt.user_block
            assert "[你的子任务] 评估数据层拆分" in r.compiled_prompt.user_block
