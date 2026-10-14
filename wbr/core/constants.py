"""全局常量（SPEC-001 §2.4）。枚举使用 (str, Enum) 以兼容 Python 3.10。"""
from __future__ import annotations

from enum import Enum


class MemoryLayer(str, Enum):
    """四层隔离记忆（SPEC-002 §5）。"""

    ROLE_STATIC = "role_static"        # 角色长期静态记忆
    ROLE_SESSION = "role_session"      # 角色私有会话记忆
    TASK_SCRATCH = "task_scratch"      # 本轮短时任务记忆
    GLOBAL_SHARED = "global_shared"    # 全局公共受控记忆

    @classmethod
    def all_layers(cls) -> list[MemoryLayer]:
        return list(cls)


# ---- 内容边界隔离符（编译器与安全层共用） ----
USER_INPUT_OPEN = "<<<WBR_USER_INPUT>>>"
USER_INPUT_CLOSE = "<<<END_WBR_USER_INPUT>>>"
EXTERNAL_CONTENT_OPEN = "<<<WBR_EXTERNAL_CONTENT>>>"
EXTERNAL_CONTENT_CLOSE = "<<<END_WBR_EXTERNAL_CONTENT>>>"

# ---- 默认限额 ----
DEFAULT_TOKEN_QUOTA = 8000
AUDIT_BUS_MAX_QUEUE = 10000

# ---- 通用分隔 ----
DIGEST_BYTES = 16  # 行为记录摘要长度（sha256 截断）
