from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_app_dir() -> Path:
    from .config import get_settings
    settings = get_settings()
    
    if settings.app_dir:
        p = Path(settings.app_dir).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    
    # Fallback logic
    try:
        p = Path.home() / ".inventory-system"
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass
    
    p = Path.cwd() / ".inventory-system"
    p.mkdir(parents=True, exist_ok=True)
    return p


APP_DIR = _resolve_app_dir()
LOG_PATH = APP_DIR / "app.log"


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get or create audit logger with proper configuration."""
    global _logger
    if _logger is not None:
        return _logger
    
    from .config import get_settings
    settings = get_settings()
    
    # Allow disabling audit by settings
    if settings.audit_disabled:
        logger = logging.getLogger("inventory.audit.nop")
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return logger
    
    try:
        logger = logging.getLogger("inventory.audit")
        logger.setLevel(logging.INFO)
        
        # Create structured log formatter
        formatter = StructuredAuditFormatter()
        
        if settings.audit_stdout:
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = RotatingFileHandler(
                LOG_PATH, 
                maxBytes=10_000_000,  # 10MB
                backupCount=5, 
                encoding="utf-8"
            )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
        
        _logger = logger
        return logger
    except Exception as e:
        # Fallback to null logger if file cannot be used
        warnings.warn(f"Failed to initialize audit logger: {e}")
        logger = logging.getLogger("inventory.audit.nop")
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return logger


def audit(event: str, **data: Any) -> None:
    """Record audit event with structured logging.
    
    Args:
        event: Event type (e.g., "item.create", "stock.in")
        **data: Additional event data
    """
    rec: Dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **data
    }
    
    # Add request context if available
    try:
        import threading
        request_id = getattr(threading.current_thread(), 'request_id', None)
        if request_id:
            rec["request_id"] = request_id
    except:
        pass
    
    try:
        get_logger().info(json.dumps(rec, ensure_ascii=False, separators=(',', ':')))
    except Exception as e:
        # Log to stderr as fallback, but don't fail the operation
        try:
            print(f"Audit log failed: {e}", file=sys.stderr)
        except Exception:
            pass  # Ultimate fallback - do nothing


class StructuredAuditFormatter(logging.Formatter):
    """Structured JSON formatter for audit logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        try:
            log_data = json.loads(record.getMessage())
            
            # Add log record metadata
            log_data.update({
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            })
            
            return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))
        except (json.JSONDecodeError, TypeError):
            # Fallback to simple format if message is not valid JSON
            return json.dumps({
                "message": record.getMessage(),
                "level": record.levelname,
                "logger": record.name,
                "timestamp": datetime.now(UTC).isoformat(),
            }, ensure_ascii=False, separators=(',', ':'))


class AuditContext:
    """Context manager for audit operations."""
    
    def __init__(self, operation: str, **context: Any):
        self.operation = operation
        self.context = context
        self.start_time = None
        self.success = None
        self.error = None
    
    def __enter__(self) -> 'AuditContext':
        """Enter context, record start time."""
        self.start_time = datetime.now(UTC)
        audit(f"{self.operation}.start", **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context, record completion status."""
        duration = None
        if self.start_time:
            duration = (datetime.now(UTC) - self.start_time).total_seconds()
        
        if exc_type is None:
            self.success = True
            audit(
                f"{self.operation}.success",
                duration_seconds=duration,
                **self.context
            )
        else:
            self.success = False
            self.error = str(exc_val)
            audit(
                f"{self.operation}.failure",
                duration_seconds=duration,
                error=str(exc_val),
                error_type=exc_type.__name__,
                **self.context
            )


def audit_context(operation: str, **context: Any) -> AuditContext:
    """Create audit context for operation.
    
    Args:
        operation: Operation name (e.g., "item.create")
        **context: Additional context data
        
    Returns:
        AuditContext: Context manager for the operation
    """
    return AuditContext(operation, **context)


def get_audit_stats() -> Dict[str, Any]:
    """Get audit statistics.
    
    Returns:
        Dict[str, Any]: Audit statistics
    """
    try:
        settings = get_settings()
        if settings.audit_disabled or settings.audit_stdout:
            return {"error": "Audit logging disabled or not configured for file output"}
        
        if not LOG_PATH.exists():
            return {"error": "Audit log file not found"}
        
        stats = {
            "total_events": 0,
            "event_types": {},
            "recent_events": [],
            "file_size_bytes": LOG_PATH.stat().st_size,
            "last_modified": LOG_PATH.stat().st_mtime,
        }
        
        # Analyze last 1000 lines for statistics
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-1000:]  # Last 1000 lines
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            try:
                event_data = json.loads(line)
                event_type = event_data.get('event', 'unknown')
                
                stats["total_events"] += 1
                stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
                
                # Keep last 10 events
                if len(stats["recent_events"]) < 10:
                    stats["recent_events"].append(event_data)
                    
            except (json.JSONDecodeError, KeyError):
                continue
        
        return stats
        
    except Exception as e:
        return {"error": f"Failed to get audit stats: {e}"}


def cleanup_old_logs(days_to_keep: int = 30) -> int:
    """Clean up old audit log files.
    
    Args:
        days_to_keep: Number of days to keep log files
        
    Returns:
        int: Number of files deleted
    """
    try:
        import time
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        # Find and delete old backup files
        for backup_file in LOG_PATH.parent.glob("app.log.*"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                deleted_count += 1
        
        # Check main log file age
        if LOG_PATH.exists() and LOG_PATH.stat().st_mtime < cutoff_time:
            # Archive old main log
            archive_path = LOG_PATH.with_suffix(f'.log.{int(LOG_PATH.stat().st_mtime)}')
            LOG_PATH.rename(archive_path)
            deleted_count += 1
        
        return deleted_count
        
    except Exception as e:
        warnings.warn(f"Failed to cleanup old logs: {e}")
        return 0
