from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict


APP_DIR = Path.home() / ".inventory-system"
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = APP_DIR / "app.log"


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger("inventory.audit")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    _logger = logger
    return logger


def audit(event: str, **data: Any) -> None:
    rec: Dict[str, Any] = {"event": event, **data}
    try:
        get_logger().info(json.dumps(rec, ensure_ascii=False))
    except Exception:
        # Best-effort only
        pass

