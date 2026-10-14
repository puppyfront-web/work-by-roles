"""TC-V1.1-KB：角色独立知识库。"""
from __future__ import annotations

import pytest

from tests.wbr.factories import expert_contract
from wbr.core.constants import MemoryLayer
from wbr.core.exceptions import MemoryPermissionDeniedError
from wbr.core.knowledge import KnowledgeBase, KnowledgeDocument, KnowledgeEvidenceCollector
from wbr.core.security.redactor import Redactor


WRITER = lambda: expert_contract("expert_a", read_layers=[MemoryLayer.ROLE_STATIC],
                                 write_layers=[MemoryLayer.ROLE_STATIC])  # noqa: E731
READER_B = lambda: expert_contract("expert_b", read_layers=[MemoryLayer.ROLE_STATIC],
                                   write_layers=[MemoryLayer.ROLE_STATIC])  # noqa: E731
NO_ACCESS = lambda: expert_contract("expert_c", read_layers=[], write_layers=[])  # noqa: E731


def make_kb() -> KnowledgeBase:
    return KnowledgeBase()


def test_add_and_search_role_scoped():
    kb = make_kb()
    ca, cb = WRITER(), READER_B()
    kb.add(KnowledgeDocument(doc_id="d1", role_id="expert_a", title="JWT 设计规范",
                             content="无状态 JWT 搭配刷新令牌，短期有效"), contract=ca)
    kb.add(KnowledgeDocument(doc_id="d2", role_id="expert_b", title="B 的私有知识",
                             content="仅 expert_b 可见的内容"), contract=cb)
    # 角色隔离：A 检索不到 B 的文档
    hits_a = kb.search("JWT", role_id="expert_a", contract=ca)
    assert [h.doc_id for h in hits_a] == ["d1"]
    assert kb.search("仅 expert_b", role_id="expert_a", contract=ca) == []


def test_write_requires_role_static_permission():
    kb = make_kb()
    with pytest.raises(MemoryPermissionDeniedError):
        kb.add(KnowledgeDocument(doc_id="d", role_id="expert_c", title="t", content="c"),
               contract=NO_ACCESS())


def test_search_scoring_deterministic_and_title_boost():
    kb = make_kb()
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="t1", role_id="expert_a", title="缓存策略",
                             content="多级缓存可降低延迟"), contract=ca)
    kb.add(KnowledgeDocument(doc_id="t2", role_id="expert_a", title="其他主题",
                             content="正文提到缓存一词"), contract=ca)
    kb.add(KnowledgeDocument(doc_id="t3", role_id="expert_a", title="缓存策略高级版",
                             content="缓存 命中率 优化 缓存"), contract=ca)
    hits = kb.search("缓存", role_id="expert_a", contract=ca, top_k=3)
    assert [h.doc_id for h in hits] == ["t3", "t1", "t2"]  # 命中密度+标题加权
    assert hits == kb.search("缓存", role_id="expert_a", contract=ca)  # 确定性
    assert hits[0].score >= hits[1].score >= hits[2].score


def test_shared_doc_visible_cross_role_with_permission():
    kb = make_kb()
    ca, cb = WRITER(), READER_B()
    kb.add(KnowledgeDocument(doc_id="pub", role_id="expert_a", title="公司规范",
                             content="全员合规要求", shared=True), contract=ca)
    hits = kb.search("合规", role_id="expert_b", contract=cb)
    assert [h.doc_id for h in hits] == ["pub"]


def test_read_permission_required():
    kb = make_kb()
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="d", role_id="expert_a", title="t", content="缓存"), contract=ca)
    with pytest.raises(MemoryPermissionDeniedError):
        kb.search("缓存", role_id="expert_a", contract=NO_ACCESS())


def test_remove_and_documents():
    kb = make_kb()
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="d1", role_id="expert_a", title="t", content="c"), contract=ca)
    kb.add(KnowledgeDocument(doc_id="d2", role_id="expert_b", title="t2", content="c2"),
           contract=READER_B())
    kb.remove("d1", contract=ca)
    assert [d.doc_id for d in kb.documents("expert_a")] == []
    assert len(kb.documents("expert_b")) == 1
    # 不能删他人私有文档（expert_a 删 expert_b 的 → 找不到即无操作）
    kb.remove("d2", contract=ca)
    assert len(kb.documents("expert_b")) == 1


def test_duplicate_doc_id_rejected():
    kb = make_kb()
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="dup", role_id="expert_a", title="t", content="c"), contract=ca)
    with pytest.raises(ValueError, match="已存在"):
        kb.add(KnowledgeDocument(doc_id="dup", role_id="expert_a", title="t2", content="c2"),
               contract=ca)


def test_evidence_collector_integration():
    kb = make_kb()
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="kb-1", role_id="expert_a", title="JWT 规范",
                             content="无状态 JWT 有效期 15 分钟"), contract=ca)
    collector = KnowledgeEvidenceCollector(kb)
    evidence = collector.collect("JWT 有效期", role_id="expert_a", contract=ca)
    assert evidence and evidence[0].startswith("[kb-1]")
    # 空结果 → None（与编译器 evidence 通道约定一致）
    assert collector.collect("量子加密", role_id="expert_a", contract=ca) is None


def test_redaction_on_add_optional():
    kb = KnowledgeBase(redactor=Redactor())
    ca = WRITER()
    kb.add(KnowledgeDocument(doc_id="d", role_id="expert_a", title="t",
                             content="联系人 admin@corp.com"), contract=ca)
    doc = kb.documents("expert_a")[0]
    assert "admin@corp.com" not in doc.content
    assert "[EMAIL_1]" in doc.content
