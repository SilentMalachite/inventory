from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from typing import Any, Dict
import os


APP_DIR = Path(os.environ.get("INVENTORY_APP_DIR", Path.home() / ".inventory-system"))
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = APP_DIR / "app.log"


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    # Allow disabling audit by env
    if os.environ.get("INVENTORY_AUDIT_DISABLED", "").lower() in ("1", "true", "yes"):
        logger = logging.getLogger("inventory.audit.nop")
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return logger
    try:
        logger = logging.getLogger("inventory.audit")
        logger.setLevel(logging.INFO)
        if os.environ.get("INVENTORY_AUDIT_STDOUT", "").lower() in ("1", "true", "yes"):
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        _logger = logger
        return logger
    except Exception:
        # Fallback to null logger if file cannot be used
        logger = logging.getLogger("inventory.audit.nop")
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return logger


def audit(event: str, **data: Any) -> None:
    rec: Dict[str, Any] = {"event": event, **data}
    try:
        get_logger().info(json.dumps(rec, ensure_ascii=False))
    except Exception:
        # Best-effort only
        pass
