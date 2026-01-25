"""Structured logging with per-request ID tracking.

Uses contextvars to propagate a request_id through async call chains,
injecting it into every log record via a custom filter.
"""

import logging
import os
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

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
        level = os.environ.get("CSR_LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


logger = setup_logging()


SENSITIVE_KEYS = ("auth", "token", "key", "secret", "pass")


def _mask_value(key: str, value: Any) -> str:
    key_lower = key.lower()
    if any(fragment in key_lower for fragment in SENSITIVE_KEYS):
        return "*" * max(6, len(str(value)))
    return str(value)


# Helper function to print settings with sensitive data masked
def print_settings(obj: object) -> None:
    if not obj:
        return

    logger.info("=== Settings ===")

    data: Mapping[str, Any] | None = None
    if hasattr(obj, "model_dump"):
        try:
            data = obj.model_dump()  # type: ignore[attr-defined]
        except Exception:
            data = None

    if data is None and hasattr(obj, "__dict__"):
        data = obj.__dict__

    if not data:
        return

    for key, value in data.items():
        logger.info(f"{key}: {_mask_value(key, value)}")
