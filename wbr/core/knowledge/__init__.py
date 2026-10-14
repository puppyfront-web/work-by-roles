"""角色独立知识库（V1.x F2 / SPEC-007 §2）。

权限锚定 ROLE_STATIC 记忆层语义（契约零改动）；确定性轻量检索；零依赖。
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.constants import MemoryLayer
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import MemoryPermissionDeniedError
from wbr.core.security.redactor import Redactor


class KnowledgeDocument(BaseModel):
    doc_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    role_id: str
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False          # True = 公司级共享，可被有读权限的其他角色检索
    created_at: float = Field(default_factory=time.time)


class KnowledgeSearchHit(BaseModel):
    doc_id: str
    title: str
    score: float
    snippet: str


_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+")


def _terms(query: str) -> list[str]:
    """查询分词：CJK 按字、拉丁按词（小写）。"""
    terms: list[str] = []
    for token in _TOKEN.findall(query.lower()):
        if re.fullmatch(r"[a-z0-9_]+", token):
            terms.append(token)
        else:
            terms.extend(ch for ch in token if ch.strip())
    return terms


class KnowledgeBase:
    """角色私有（或共享）知识库：写需 ROLE_STATIC 写权限，读需 ROLE_STATIC 读权限。"""

    def __init__(self, *, audit: AuditTrail | None = None, redactor: Redactor | None = None) -> None:
        self._docs: dict[str, KnowledgeDocument] = {}
        self._lock = threading.RLock()
        self._audit = audit
        self._redactor = redactor

    # ---- 权限（锚定 ROLE_STATIC 语义，契约零改动） ----
    @staticmethod
    def _check(mode: str, contract: RoleContract) -> None:
        perms = contract.memory_permissions
        layers = perms.read_layers if mode == "read" else perms.write_layers
        if MemoryLayer.ROLE_STATIC not in layers:
            raise MemoryPermissionDeniedError(
                f"角色 {contract.role_id} 无知识库{mode}权限（需 ROLE_STATIC {'读' if mode == 'read' else '写'}授权）",
                details={"role_id": contract.role_id, "layer": MemoryLayer.ROLE_STATIC.value, "mode": mode},
            )

    def _emit(self, event: str, payload: dict) -> None:
        if self._audit is not None:
            self._audit.append(
                AuditEvent(event_type=AuditEventType.MEMORY_ACCESS,
                           trace_id="no-trace", payload={"kb_event": event, **payload})
            )

    # ---- API ----
    def add(self, doc: KnowledgeDocument, *, contract: RoleContract,
            redact: bool | None = None) -> KnowledgeDocument:
        self._check("write", contract)
        with self._lock:
            if doc.doc_id in self._docs:
                raise ValueError(f"知识文档 doc_id 已存在: {doc.doc_id}")
            stored = doc
            if (redact is not False) and self._redactor is not None:
                cleaned = self._redactor.redact_obj({"title": doc.title, "content": doc.content})
                stored = doc.model_copy(update=cleaned[0])
            self._docs[doc.doc_id] = stored
        self._emit("kb_add", {"doc_id": doc.doc_id, "role_id": doc.role_id})
        return stored

    def remove(self, doc_id: str, *, contract: RoleContract) -> bool:
        self._check("write", contract)
        with self._lock:
            doc = self._docs.get(doc_id)
            if doc is None or (doc.role_id != contract.role_id and not doc.shared):
                return False
            del self._docs[doc_id]
        self._emit("kb_remove", {"doc_id": doc_id})
        return True

    def documents(self, role_id: str) -> list[KnowledgeDocument]:
        with self._lock:
            return sorted(
                (d for d in self._docs.values() if d.role_id == role_id),
                key=lambda d: d.doc_id,
            )

    def search(self, query: str, *, role_id: str, contract: RoleContract,
               top_k: int = 5) -> list[KnowledgeSearchHit]:
        self._check("read", contract)
        terms = _terms(query)
        if not terms:
            return []
        with self._lock:
            candidates = [
                d for d in self._docs.values()
                if d.shared or d.role_id == role_id
            ]
        scored: list[KnowledgeSearchHit] = []
        for doc in candidates:
            score = self._score(doc, terms, query)
            if score > 0:
                snippet = doc.content[:80]
                scored.append(KnowledgeSearchHit(doc_id=doc.doc_id, title=doc.title,
                                                 score=round(score, 6), snippet=snippet))
        scored.sort(key=lambda h: (-h.score, h.doc_id))  # 确定性
        self._emit("kb_search", {"role_id": role_id, "hits": len(scored[:top_k])})
        return scored[:top_k]

    @staticmethod
    def _score(doc: KnowledgeDocument, terms: list[str], query: str) -> float:
        title_l, content_l = doc.title.lower(), doc.content.lower()
        title_hits = sum(1 for t in terms if t in title_l)
        content_hits = sum(1 for t in terms if t in content_l)
        content_occurrences = sum(content_l.count(t) for t in terms)
        tag_hits = sum(1 for t in terms if any(t in tag.lower() for tag in doc.tags))
        if title_hits == 0 and content_hits == 0:
            return 0.0
        density = content_occurrences / max(1, len(terms))
        return round(title_hits * 2.0 + density * 1.0 + tag_hits * 1.5, 6)


class KnowledgeEvidenceCollector:
    """把知识库检索结果接到既有 evidence 通道（编译器/会审直接可用）。"""

    def __init__(self, kb: KnowledgeBase, *, top_k: int = 3) -> None:
        self._kb = kb
        self._top_k = top_k

    def collect(self, query: str, *, role_id: str, contract: RoleContract) -> list[str] | None:
        hits = self._kb.search(query, role_id=role_id, contract=contract, top_k=self._top_k)
        if not hits:
            return None
        docs = {d.doc_id: d for d in self._kb.documents(role_id)}
        # 共享文档可能不在本 role 名下，补查全库
        evidence = []
        for h in hits:
            doc = docs.get(h.doc_id)
            if doc is None:
                with self._kb._lock:  # noqa: SLF001 - 同模块只读访问
                    doc = self._kb._docs.get(h.doc_id)
            if doc is not None:
                evidence.append(f"[{h.doc_id}] {doc.title}: {doc.content[:200]}")
        return evidence or None
