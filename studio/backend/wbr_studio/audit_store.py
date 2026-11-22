"""Postgres AuditStore。一个工作区一条链，追加时锁住链头行再取链尾。

哈希使用内核 ``audit_record_hash``（经 ``link_next`` / ``verify_records``），不另写算法。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from wbr.core.audit.chain import HASH_ALG
from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.store import (
    SCHEMA_VERSION,
    StoredAuditRecord,
    canonical_event,
    link_next,
    normalize_scope,
    verify_records,
)
from wbr.core.exceptions import AuditChainBroken, AuditSchemaError

_INSERT_CHAIN = text(
    """
    INSERT INTO audit_chains (workspace_id, schema_version, hash_alg)
    VALUES (:workspace_id, :schema_version, :hash_alg)
    ON CONFLICT (workspace_id) DO NOTHING
    """
)
_LOCK_CHAIN = text(
    """
    SELECT schema_version, hash_alg
    FROM audit_chains
    WHERE workspace_id = :workspace_id
    FOR UPDATE
    """
)
_READ_CHAIN = text(
    """
    SELECT schema_version, hash_alg
    FROM audit_chains
    WHERE workspace_id = :workspace_id
    """
)
_TAIL = text(
    """
    SELECT seq, prev_hash, event_hash, run_id, session_id, event_json
    FROM audit_events
    WHERE workspace_id = :workspace_id
    ORDER BY seq DESC
    LIMIT 1
    """
)
_INSERT_EVENT = text(
    """
    INSERT INTO audit_events (
        workspace_id, seq, prev_hash, event_hash, run_id, session_id,
        trace_id, event_type, ts, role_id, event_json
    ) VALUES (
        :workspace_id, :seq, :prev_hash, :event_hash, :run_id, :session_id,
        :trace_id, :event_type, :ts, :role_id, :event_json
    )
    """
)


class PostgresAuditStore:
    backend_name = "postgres"

    def __init__(
        self,
        engine: Engine,
        workspace_id: uuid.UUID | str,
        *,
        verify_on_load: bool = False,
    ) -> None:
        self._engine = engine
        self.workspace_id = uuid.UUID(str(workspace_id))
        if verify_on_load:
            self.verify(strict=True)

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> StoredAuditRecord:
        scoped_run, scoped_session = normalize_scope(event, run_id, session_id)
        stored, event_json = canonical_event(event)
        with self._engine.begin() as conn:
            self._lock_chain(conn)
            tail = conn.execute(_TAIL, {"workspace_id": self.workspace_id}).one_or_none()
            prev = _record_from_row(tail) if tail is not None else None
            seq, prev_hash, digest = link_next(
                prev, stored, run_id=scoped_run, session_id=scoped_session
            )
            conn.execute(
                _INSERT_EVENT,
                {
                    "workspace_id": self.workspace_id,
                    "seq": seq,
                    "prev_hash": prev_hash,
                    "event_hash": digest,
                    "run_id": scoped_run,
                    "session_id": scoped_session,
                    "trace_id": stored.trace_id,
                    "event_type": stored.event_type.value,
                    "ts": stored.ts,
                    "role_id": stored.role_id,
                    "event_json": event_json,
                },
            )
        return StoredAuditRecord(
            seq=seq,
            prev_hash=prev_hash,
            event_hash=digest,
            run_id=scoped_run,
            session_id=scoped_session,
            event=stored,
        )

    def query(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        event_type: AuditEventType | str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int | None = None,
    ) -> list[StoredAuditRecord]:
        if limit is not None and limit < 1:
            raise ValueError("limit 必须 >= 1")
        clauses = ["workspace_id = :workspace_id"]
        params: dict[str, Any] = {"workspace_id": self.workspace_id}
        if run_id is not None:
            clauses.append("run_id = :run_id")
            params["run_id"] = run_id
        if session_id is not None:
            clauses.append("session_id = :session_id")
            params["session_id"] = session_id
        if trace_id is not None:
            clauses.append("trace_id = :trace_id")
            params["trace_id"] = trace_id
        wanted = _event_type_value(event_type)
        if wanted is not None:
            clauses.append("event_type = :event_type")
            params["event_type"] = wanted
        if since is not None:
            clauses.append("ts >= :since")
            params["since"] = since
        if until is not None:
            clauses.append("ts <= :until")
            params["until"] = until
        sql = (
            "SELECT seq, prev_hash, event_hash, run_id, session_id, event_json "
            "FROM audit_events WHERE " + " AND ".join(clauses) + " ORDER BY seq ASC"
        )
        if limit is not None:
            sql += " LIMIT :limit"
            params["limit"] = limit
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).all()
        return [_record_from_row(row) for row in rows]

    def verify(self, *, strict: bool = False):
        with self._engine.connect() as conn:
            self._assert_meta(conn)
            rows = conn.execute(
                text(
                    """
                    SELECT seq, prev_hash, event_hash, run_id, session_id, event_json
                    FROM audit_events
                    WHERE workspace_id = :workspace_id
                    ORDER BY seq ASC
                    """
                ),
                {"workspace_id": self.workspace_id},
            ).all()
        result = verify_records([_record_from_row(row) for row in rows])
        if strict and not result.ok:
            raise AuditChainBroken(
                f"审计哈希链在位置 {result.broken_at} 处断裂",
                details={"broken_at": result.broken_at, "checked": result.checked},
            )
        return result

    def close(self) -> None:
        return None

    def __iter__(self):
        return iter(self.query())

    def _lock_chain(self, conn: Connection) -> None:
        conn.execute(
            _INSERT_CHAIN,
            {
                "workspace_id": self.workspace_id,
                "schema_version": SCHEMA_VERSION,
                "hash_alg": HASH_ALG,
            },
        )
        row = conn.execute(_LOCK_CHAIN, {"workspace_id": self.workspace_id}).one()
        _check_meta_row(row)

    def _assert_meta(self, conn: Connection) -> None:
        row = conn.execute(_READ_CHAIN, {"workspace_id": self.workspace_id}).one_or_none()
        if row is not None:
            _check_meta_row(row)


def _check_meta_row(row: Any) -> None:
    version = int(row.schema_version)
    alg = str(row.hash_alg)
    if version != SCHEMA_VERSION:
        raise AuditSchemaError(
            f"审计库 schema {version} 与内核 {SCHEMA_VERSION} 不一致",
            details={"schema_version": version, "supported": SCHEMA_VERSION},
        )
    if alg != HASH_ALG:
        raise AuditSchemaError(
            f"审计库哈希算法 {alg} 与内核 {HASH_ALG} 不一致",
            details={"hash_alg": alg, "expected": HASH_ALG},
        )


def _event_type_value(event_type: AuditEventType | str | None) -> str | None:
    if event_type is None:
        return None
    if isinstance(event_type, AuditEventType):
        return event_type.value
    return str(event_type)


def _record_from_row(row: Any) -> StoredAuditRecord:
    return StoredAuditRecord(
        seq=int(row.seq),
        prev_hash=str(row.prev_hash),
        event_hash=str(row.event_hash),
        run_id=str(row.run_id),
        session_id=str(row.session_id),
        event=AuditEvent.model_validate_json(row.event_json),
    )
