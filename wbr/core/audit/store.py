"""可插拔审计存储。

AuditStore 是内核与 wbr-studio 之间的契约：append / query / verify。
默认实现是进程内内存，行为与「不落盘」一致。SQLite 实现只用标准库 sqlite3，
供单进程内多线程追加：同一把锁包住 BEGIN IMMEDIATE，链尾的 prev_hash 不会交叉。

Postgres 不进内核。wbr-studio 另写一个 AuditStore 即可，沿用下面的逻辑列与
``audit_record_hash``（HASH_ALG），追加时在事务里锁住链尾
（``SELECT ... FOR UPDATE`` 最后一行，或 advisory lock）再插入下一 seq。
类型对应：TEXT、INTEGER、REAL（Postgres 用 DOUBLE PRECISION）。
schema 版本放在 audit_meta.schema_version，不要在内核里加驱动依赖。

多进程同时写同一个 SQLite 文件不在支持范围内。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from wbr.core.audit.chain import GENESIS, HASH_ALG, ChainVerification, audit_record_hash
from wbr.core.audit.models import AuditEvent, AuditEventType, RoleBehaviorRecord
from wbr.core.exceptions import AuditChainBroken, AuditSchemaError

SCHEMA_VERSION = 1

_V1_DDL = """
CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ts REAL NOT NULL,
    role_id TEXT,
    event_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_type_ts ON audit_events(event_type, ts);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(ts);
"""


class StoredAuditRecord:
    """一条已定版的审计记录。event_hash 即该记录的链哈希。"""

    __slots__ = ("event", "event_hash", "prev_hash", "run_id", "seq", "session_id")

    def __init__(
        self,
        *,
        seq: int,
        prev_hash: str,
        event_hash: str,
        run_id: str,
        session_id: str,
        event: AuditEvent,
    ) -> None:
        self.seq = seq
        self.prev_hash = prev_hash
        self.event_hash = event_hash
        self.run_id = run_id
        self.session_id = session_id
        self.event = event

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "event": self.event.model_dump(mode="json"),
        }


def canonical_event(event: AuditEvent) -> tuple[AuditEvent, str]:
    """先按 JSON 往返一次，保证落盘字节和校验时重新解析的结果是同一份。"""
    parsed = AuditEvent.model_validate_json(event.model_dump_json())
    return parsed, parsed.model_dump_json()


def normalize_scope(
    event: AuditEvent,
    run_id: str | None,
    session_id: str | None,
) -> tuple[str, str]:
    """未指定 run_id 时用 trace_id，这样一次会审的事件默认可按运行检索。"""
    if run_id is None:
        run_id = event.trace_id
    if session_id is None:
        session_id = ""
    return run_id, session_id


def link_next(
    prev: StoredAuditRecord | None,
    event: AuditEvent,
    *,
    run_id: str,
    session_id: str,
) -> tuple[int, str, str]:
    if prev is None:
        seq = 0
        prev_hash = GENESIS
    else:
        seq = prev.seq + 1
        prev_hash = prev.event_hash
    digest = audit_record_hash(
        prev_hash, seq, event, run_id=run_id, session_id=session_id
    )
    return seq, prev_hash, digest


def verify_records(records: list[StoredAuditRecord]) -> ChainVerification:
    """按链序检查。broken_at 是第一条对不上的位置（从 0 起），不是业务序号的别名。"""
    prev = GENESIS
    for index, record in enumerate(records):
        if record.seq != index or record.prev_hash != prev:
            return ChainVerification(ok=False, broken_at=index, checked=index)
        expected = audit_record_hash(
            record.prev_hash,
            record.seq,
            record.event,
            run_id=record.run_id,
            session_id=record.session_id,
        )
        if record.event_hash != expected:
            return ChainVerification(ok=False, broken_at=index, checked=index + 1)
        prev = record.event_hash
    return ChainVerification(ok=True, checked=len(records))


def _event_type_value(event_type: AuditEventType | str | None) -> str | None:
    if event_type is None:
        return None
    if isinstance(event_type, AuditEventType):
        return event_type.value
    return str(event_type)


def record_matches(
    record: StoredAuditRecord,
    *,
    run_id: str | None,
    session_id: str | None,
    trace_id: str | None,
    event_type: str | None,
    since: float | None,
    until: float | None,
) -> bool:
    if run_id is not None and record.run_id != run_id:
        return False
    if session_id is not None and record.session_id != session_id:
        return False
    if trace_id is not None and record.event.trace_id != trace_id:
        return False
    if event_type is not None and record.event.event_type.value != event_type:
        return False
    if since is not None and record.event.ts < since:
        return False
    return until is None or record.event.ts <= until


def _check_limit(limit: int | None) -> None:
    if limit is not None and limit < 1:
        raise ValueError("limit 必须 >= 1")


@runtime_checkable
class AuditStore(Protocol):
    """追加、按运行/会话/时间/事件类型检索，并校验整条哈希链。"""

    backend_name: str

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> StoredAuditRecord: ...

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
    ) -> list[StoredAuditRecord]: ...

    def verify(self, *, strict: bool = False) -> ChainVerification: ...

    def close(self) -> None: ...

    def __iter__(self) -> Any: ...


class InMemoryAuditStore:
    """进程内存储。重启即丢，哈希链只在本进程有效。"""

    backend_name = "memory"

    def __init__(self) -> None:
        self._records: list[StoredAuditRecord] = []
        self._lock = threading.RLock()

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> StoredAuditRecord:
        scoped_run, scoped_session = normalize_scope(event, run_id, session_id)
        stored, _raw = canonical_event(event)
        with self._lock:
            prev = self._records[-1] if self._records else None
            seq, prev_hash, digest = link_next(
                prev, stored, run_id=scoped_run, session_id=scoped_session
            )
            record = StoredAuditRecord(
                seq=seq,
                prev_hash=prev_hash,
                event_hash=digest,
                run_id=scoped_run,
                session_id=scoped_session,
                event=stored,
            )
            self._records.append(record)
            return record

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
        _check_limit(limit)
        wanted = _event_type_value(event_type)
        with self._lock:
            matched = [
                record for record in self._records
                if record_matches(
                    record,
                    run_id=run_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    event_type=wanted,
                    since=since,
                    until=until,
                )
            ]
        if limit is not None:
            return matched[:limit]
        return matched

    def verify(self, *, strict: bool = False) -> ChainVerification:
        with self._lock:
            result = verify_records(list(self._records))
        if strict and not result.ok:
            _raise_broken(result)
        return result

    def close(self) -> None:
        return None

    def __iter__(self):
        return iter(self.query())


class SqliteAuditStore:
    """单进程 SQLite。schema_version 写在 audit_meta，启动时校验整链。"""

    backend_name = "sqlite"

    def __init__(self, path: str | Path, *, verify_on_load: bool = True) -> None:
        self.path = path
        self._lock = threading.RLock()
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            path, timeout=5.0, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA busy_timeout=5000").fetchone()
            if str(path) != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._ensure_schema()
            if verify_on_load:
                self.verify(strict=True)
        except Exception:
            self._conn.close()
            self._conn = None
            raise

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> StoredAuditRecord:
        scoped_run, scoped_session = normalize_scope(event, run_id, session_id)
        stored, event_json = canonical_event(event)
        event_type = stored.event_type.value
        with self._lock:
            conn = self._require_conn()
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT seq, prev_hash, event_hash, run_id, session_id, event_json "
                    "FROM audit_events ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                prev = _record_from_row(row) if row is not None else None
                seq, prev_hash, digest = link_next(
                    prev, stored, run_id=scoped_run, session_id=scoped_session
                )
                conn.execute(
                    """
                    INSERT INTO audit_events (
                        seq, prev_hash, event_hash, run_id, session_id,
                        trace_id, event_type, ts, role_id, event_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        seq,
                        prev_hash,
                        digest,
                        scoped_run,
                        scoped_session,
                        stored.trace_id,
                        event_type,
                        stored.ts,
                        stored.role_id,
                        event_json,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
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
        _check_limit(limit)
        clauses: list[str] = []
        params: list[Any] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if trace_id is not None:
            clauses.append("trace_id = ?")
            params.append(trace_id)
        wanted = _event_type_value(event_type)
        if wanted is not None:
            clauses.append("event_type = ?")
            params.append(wanted)
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        if until is not None:
            clauses.append("ts <= ?")
            params.append(until)
        sql = (
            "SELECT seq, prev_hash, event_hash, run_id, session_id, event_json "
            "FROM audit_events"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [_record_from_row(row) for row in rows]

    def verify(self, *, strict: bool = False) -> ChainVerification:
        with self._lock:
            rows = self._require_conn().execute(
                "SELECT seq, prev_hash, event_hash, run_id, session_id, event_json "
                "FROM audit_events ORDER BY seq ASC"
            ).fetchall()
        result = verify_records([_record_from_row(row) for row in rows])
        if strict and not result.ok:
            _raise_broken(result)
        return result

    def close(self) -> None:
        with self._lock:
            conn = self._conn
            if conn is None:
                return
            self._conn = None
            try:
                if str(self.path) != ":memory:":
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                conn.close()

    def __iter__(self):
        return iter(self.query())

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise AuditSchemaError("审计库已关闭")
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._require_conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        current = self._meta("schema_version")
        version = int(current) if current is not None else 0
        if version > SCHEMA_VERSION:
            raise AuditSchemaError(
                f"审计库 schema {version} 高于内核支持的 {SCHEMA_VERSION}",
                details={"schema_version": version, "supported": SCHEMA_VERSION},
            )
        if version < 1:
            conn.executescript(_V1_DDL)
            version = 1
            self._set_meta("schema_version", str(version))
        if version != SCHEMA_VERSION:
            raise AuditSchemaError(
                f"审计库 schema {version} 没有到 {SCHEMA_VERSION} 的迁移",
                details={"schema_version": version, "supported": SCHEMA_VERSION},
            )
        alg = self._meta("hash_alg")
        if alg is not None and alg != HASH_ALG:
            raise AuditSchemaError(
                f"审计库哈希算法 {alg} 与内核 {HASH_ALG} 不一致",
                details={"hash_alg": alg, "expected": HASH_ALG},
            )
        self._set_meta("schema_version", str(SCHEMA_VERSION))
        self._set_meta("hash_alg", HASH_ALG)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _meta(self, key: str) -> str | None:
        row = self._require_conn().execute(
            "SELECT value FROM audit_meta WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def _set_meta(self, key: str, value: str) -> None:
        self._require_conn().execute(
            """
            INSERT INTO audit_meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def _record_from_row(row: sqlite3.Row) -> StoredAuditRecord:
    return StoredAuditRecord(
        seq=int(row["seq"]),
        prev_hash=str(row["prev_hash"]),
        event_hash=str(row["event_hash"]),
        run_id=str(row["run_id"]),
        session_id=str(row["session_id"]),
        event=AuditEvent.model_validate_json(row["event_json"]),
    )


def _raise_broken(result: ChainVerification) -> None:
    raise AuditChainBroken(
        f"审计哈希链在位置 {result.broken_at} 处断裂",
        details={"broken_at": result.broken_at, "checked": result.checked},
    )


class AuditRunScope:
    """把同一次运行的 append 打上固定的 run_id / session_id。

    会审专家在线程池里写审计，不能依赖 contextvars。本对象的标识在构造时确定，
    任意线程调用 append 都会带到存储。
    """

    def __init__(self, trail: Any, *, run_id: str, session_id: str | None = None) -> None:
        self._trail = trail
        self.run_id = run_id
        self.session_id = run_id if session_id is None else session_id

    def append(
        self,
        event: AuditEvent,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._trail.append(
            event,
            run_id=self.run_id if run_id is None else run_id,
            session_id=self.session_id if session_id is None else session_id,
        )

    def append_behavior(self, record: RoleBehaviorRecord) -> None:
        self._trail.append_behavior(record)


def resolve_audit_store(
    store: AuditStore | None = None,
    path: str | Path | None = None,
) -> AuditStore:
    """显式 store 优先；path 为空字符串则强制内存；path 为 None 时读 WBR_AUDIT_DB。"""
    if store is not None:
        return store
    if path is not None:
        text = str(path).strip()
        if not text:
            return InMemoryAuditStore()
        return SqliteAuditStore(text)
    env = os.environ.get("WBR_AUDIT_DB", "").strip()
    if env:
        return SqliteAuditStore(env)
    return InMemoryAuditStore()
