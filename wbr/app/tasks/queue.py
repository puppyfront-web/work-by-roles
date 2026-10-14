"""异步任务队列：进程内实现 + JSON 落盘恢复（SPEC-005 §3 / D-11）。

TaskQueue 为抽象点，可替换为外部 broker（Celery/Redis，V1.x+）。
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class TaskKind(str, Enum):
    REVIEW = "review"
    REGRESSION = "regression"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TaskRecord(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: TaskKind
    payload: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: float = Field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


TaskHandler = Callable[[TaskRecord], Any]


@runtime_checkable
class TaskQueue(Protocol):
    def submit(self, record: TaskRecord) -> TaskRecord: ...

    def get(self, task_id: str) -> TaskRecord | None: ...

    def list(self) -> list[TaskRecord]: ...


class InlineTaskQueue:
    """同步直通：submit 即执行（测试与嵌入式场景）。"""

    def __init__(self, handler: TaskHandler) -> None:
        self.handler = handler
        self._records: dict[str, TaskRecord] = {}

    def submit(self, record: TaskRecord) -> TaskRecord:
        record.status = TaskStatus.RUNNING
        record.started_at = time.time()
        self._records[record.task_id] = record
        try:
            record.result = self.handler(record)
            record.status = TaskStatus.DONE
        except Exception as e:
            record.status = TaskStatus.FAILED
            record.error = str(e)
        finally:
            record.finished_at = time.time()
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        return self._records.get(task_id)

    def list(self) -> list[TaskRecord]:
        return sorted(self._records.values(), key=lambda r: r.created_at)


class InProcessTaskQueue:
    """asyncio 队列 + 单 worker 协程（长时会审/批量回归异步化）。"""

    def __init__(self, handler: TaskHandler) -> None:
        self.handler = handler
        self._records: dict[str, TaskRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._lock = threading.RLock()

    async def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def _run(self) -> None:
        while True:
            task_id = await self._queue.get()
            with self._lock:
                record = self._records.get(task_id)
            if record is None:
                continue
            record.status = TaskStatus.RUNNING
            record.started_at = time.time()
            try:
                result = self.handler(record)
                if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                    result = await result
                record.result = result
                record.status = TaskStatus.DONE
            except Exception as e:
                record.status = TaskStatus.FAILED
                record.error = str(e)
            finally:
                record.finished_at = time.time()

    def submit(self, record: TaskRecord) -> TaskRecord:
        with self._lock:
            self._records[record.task_id] = record
        try:
            self._queue.put_nowait(record.task_id)
        except RuntimeError:
            # 无运行中事件循环：降级为同步执行
            self._run_one(record)
        return record

    def _run_one(self, record: TaskRecord) -> None:
        record.status = TaskStatus.RUNNING
        record.started_at = time.time()
        try:
            record.result = self.handler(record)
            record.status = TaskStatus.DONE
        except Exception as e:
            record.status = TaskStatus.FAILED
            record.error = str(e)
        finally:
            record.finished_at = time.time()

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._records.get(task_id)

    def list(self) -> list[TaskRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.created_at)


class JsonTaskStore:
    """任务记录落盘：重启后 DONE/FAILED 可查，PENDING 重投递。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def save(self, record: TaskRecord) -> None:
        self._path(record.task_id).write_text(record.model_dump_json(), encoding="utf-8")

    def load(self, task_id: str) -> TaskRecord | None:
        p = self._path(task_id)
        if not p.is_file():
            return None
        return TaskRecord.model_validate_json(p.read_text(encoding="utf-8"))

    def load_all(self) -> list[TaskRecord]:
        out = []
        for p in sorted(self.root.glob("*.json")):
            try:
                out.append(TaskRecord.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def resubmit_pending(self, queue: TaskQueue) -> list[TaskRecord]:
        """重启恢复：把 PENDING/RUNNING（视为中断）的任务重新投递。"""
        resubmitted = []
        for record in self.load_all():
            if record.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                record.status = TaskStatus.PENDING
                record.error = None
                queue.submit(record)
                self.save(record)
                resubmitted.append(record)
        return resubmitted
