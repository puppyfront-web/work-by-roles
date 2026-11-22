"""把运行交给 Arq。测试和单进程开发可以把 STUDIO_RUN_INLINE 设为 1。"""
from __future__ import annotations

from wbr_studio.runner import execute_run
from wbr_studio.settings import get_settings


async def enqueue_run(run_id: str) -> None:
    if get_settings().studio_run_inline:
        execute_run(run_id)
        return
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    try:
        await pool.enqueue_job("run_review", run_id)
    finally:
        await pool.close()
