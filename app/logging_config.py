"""
Cambium Structured Logging.

Replaces the 197 print() calls with a proper logging system:
  - Structured JSON output (machine-parseable)
  - Log levels (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  - Module-scoped loggers
  - Configurable via environment variables
  - Optional file output with rotation

Usage:
    from app.logging_config import get_logger
    log = get_logger(__name__)
    log.info("memory.added", memory_id=mid, user_id=uid)
    log.error("reflection.failed", error=str(e))

Output (JSON to stdout):
    {"ts": "2026-07-27T10:00:00Z", "level": "info", "event": "memory.added",
     "module": "app.memory_orchestrator", "memory_id": "abc123", "user_id": "default"}
"""
from __future__ import annotations

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================
# JSON Formatter
# ============================================================

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter.
    Each log line is a single JSON object with:
      - ts: ISO timestamp (UTC)
      - level: log level
      - module: logger name
      - event: the message (treated as event name)
      - extra: all keyword arguments
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        log_entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "module": record.name,
            "event": record.getMessage(),
        }

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                # Skip non-serializable
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError, OverflowError):
                    log_entry[key] = repr(value)

        # Add exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development.
    Example: 2026-07-27 10:00:00 INFO  [app.memory] memory.added  memory_id=abc123 user_id=default
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(7)
        module = record.name.ljust(28)[:28]

        # Extract extra fields
        extras = []
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                extras.append(f"{key}={value}")

        extra_str = "  ".join(extras) if extras else ""
        msg = record.getMessage()
        line = f"{ts} {level} [{module}] {msg}"
        if extra_str:
            line += f"  {extra_str}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# ============================================================
# Logger factory
# ============================================================

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_configured = False
_loggers: Dict[str, logging.Logger] = {}


def configure_logging(
    level: str = "INFO",
    format_type: str = "human",
    log_file: Optional[str] = None,
    log_file_max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    log_file_backup_count: int = 5,
):
    """Configure the root logging system. Called once at startup.

    Args:
        level: Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        format_type: "human" (dev) or "json" (production)
        log_file: Optional file path for log output
        log_file_max_bytes: Max file size before rotation
        log_file_backup_count: Number of rotated files to keep
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_level = _LOG_LEVELS.get(level.upper(), logging.INFO)
    formatter = JSONFormatter() if format_type == "json" else HumanFormatter()

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler (with rotation)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=log_file_max_bytes,
            backupCount=log_file_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a module-scoped logger.

    Usage:
        log = get_logger(__name__)
        log.info("memory.added", extra={"memory_id": mid, "user_id": uid})

    Note: keyword-style extras must be passed via `extra={}`.
    """
    if not _configured:
        # Auto-configure with defaults if not explicitly configured
        level = os.getenv("CAMBIUM_LOG_LEVEL", "INFO")
        fmt = os.getenv("CAMBIUM_LOG_FORMAT", "human")
        log_file = os.getenv("CAMBIUM_LOG_FILE", "")
        configure_logging(level=level, format_type=fmt, log_file=log_file or None)

    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger
    return _loggers[name]


# ============================================================
# Convenience: log event helper
# ============================================================

def log_event(level: str, event: str, module: str = "app", **kwargs):
    """Log a structured event with keyword extras.

    Example:
        from app.logging_config import log_event
        log_event("info", "memory.added", module="memory_orchestrator",
                  memory_id=mid, user_id=uid)
    """
    log = get_logger(module)
    getattr(log, level.lower())(event, extra=kwargs)
