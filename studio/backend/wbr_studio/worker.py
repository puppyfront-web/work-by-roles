"""Arq worker。``arq wbr_studio.worker.WorkerSettings``。"""
from __future__ import annotations

import logging

from arq import cron
from arq.connections import RedisSettings

from wbr_studio.reaper import reap_stuck_runs
from wbr_studio.runner import execute_run
from wbr_studio.settings import get_settings

_log = logging.getLogger("wbr_studio.worker")


async def run_review(_ctx: dict, run_id: str) -> None:
    execute_run(run_id)


def _safe_reap() -> None:
    try:
        reap_stuck_runs()
    except Exception as exc:
        _log.warning("reap failed (%s)", type(exc).__name__)


async def startup(_ctx: dict) -> None:
    _safe_reap()


async def reap_stuck_job(_ctx: dict) -> None:
    _safe_reap()


_settings = get_settings()


class WorkerSettings:
    functions = [run_review]
    cron_jobs = [cron(reap_stuck_job, second=0, run_at_startup=True)]
    on_startup = startup
    job_timeout = _settings.studio_run_timeout_seconds + 60
    max_tries = 1
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
