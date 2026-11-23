"""可替换的邮件出口。默认把正文打到日志，不连接外部邮件服务。"""
from __future__ import annotations

import logging
from typing import Protocol

_log = logging.getLogger("wbr_studio.mail")


class Mailer(Protocol):
    def send(self, *, to: str, subject: str, text: str) -> None: ...


class LogMailer:
    def send(self, *, to: str, subject: str, text: str) -> None:
        _log.info("to=%s subject=%s\n%s", to, subject, text)


_mailer: Mailer = LogMailer()


def get_mailer() -> Mailer:
    return _mailer


def set_mailer(mailer: Mailer | None) -> None:
    global _mailer
    _mailer = LogMailer() if mailer is None else mailer
