"""Structured logging with per-request ID tracking.

Uses contextvars to propagate a request_id through async call chains,
injecting it into every log record via a custom filter.
"""

import logging
import uuid
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    rid = request_id_ctx.get()
    if not rid:
        rid = uuid.uuid4().hex[:12]
        request_id_ctx.set(rid)
    return rid


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("") or "-"
        return True


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("csr_service")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = setup_logging()
