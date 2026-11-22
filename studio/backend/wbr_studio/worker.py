"""Arq worker。``arq wbr_studio.worker.WorkerSettings``。"""
from __future__ import annotations

from arq.connections import RedisSettings

from wbr_studio.runner import execute_run
from wbr_studio.settings import get_settings


async def run_review(_ctx: dict, run_id: str) -> None:
    execute_run(run_id)


class WorkerSettings:
    functions = [run_review]
    job_timeout = 900
    max_tries = 1
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
