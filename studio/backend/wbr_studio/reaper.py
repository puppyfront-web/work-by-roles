"""把超时仍处于 running 的运行标成失败。重复执行不会改已结束的行。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import update

from wbr_studio.db import get_sessionmaker
from wbr_studio.models import Run, utcnow
from wbr_studio.settings import get_settings

STUCK_REASON = "运行超时"


def reap_stuck_runs(now: datetime | None = None) -> int:
    moment = now or utcnow()
    deadline = moment - timedelta(seconds=get_settings().studio_run_timeout_seconds)
    db = get_sessionmaker()()
    try:
        result = db.execute(
            update(Run)
            .where(
                Run.status == "running",
                Run.started_at.is_not(None),
                Run.started_at < deadline,
            )
            .values(status="failed", error=STUCK_REASON, finished_at=moment)
        )
        db.commit()
        return int(result.rowcount or 0)
    finally:
        db.close()
