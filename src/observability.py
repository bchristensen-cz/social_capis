from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "ts", "levelname": "severity"},
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level)

    for noisy in ("google.auth", "google.api_core", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def order_prefix(order_id: str, n: int = 4) -> str:
    """Redact order ID for logs — first N chars only."""
    s = order_id or ""
    return s[:n] + "…" if len(s) > n else s


def hash_prefix(hash_hex: str, n: int = 8) -> str:
    """Redact hashed identifier for logs — first N chars only."""
    s = hash_hex or ""
    return s[:n] + "…" if len(s) > n else s


def log_send(
    logger: logging.Logger,
    platform: str,
    order_id: str,
    event_id: str,
    status: str,
    http_code: int | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "platform": platform,
        "order_id_prefix": order_prefix(order_id),
        "event_id_prefix": hash_prefix(event_id),
        "status": status,
    }
    if http_code is not None:
        payload["http_code"] = http_code
    if error:
        payload["error"] = error
    if extra:
        payload.update(extra)
    if status == "ok":
        logger.info("send", extra=payload)
    else:
        logger.error("send_failed", extra=payload)
