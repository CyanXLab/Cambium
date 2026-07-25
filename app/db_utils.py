"""
Shared SQLite utilities for Cambium.

All modules should use `safe_connect()` instead of `sqlite3.connect()` directly
to ensure concurrent safety (WAL mode + busy_timeout + foreign keys).

Usage:
    from app.db_utils import safe_connect
    with safe_connect(db_path) as conn:
        conn.execute("SELECT ...")

Or as a function call (must close manually):
    conn = safe_connect(db_path)
    ...
    conn.close()
"""
import sqlite3
from pathlib import Path
from typing import Union
from contextlib import contextmanager


# Default pragmas applied to every connection
_SAFETY_PRAGMAS = [
    "PRAGMA journal_mode=WAL",       # Write-Ahead Logging: concurrent reads during writes
    "PRAGMA busy_timeout=30000",     # Wait 30s on lock instead of immediate "database is locked"
    "PRAGMA foreign_keys=ON",        # Enforce FK constraints
    "PRAGMA synchronous=NORMAL",     # WAL-safe, faster than FULL
    "PRAGMA cache_size=-8000",       # 8MB cache
]


def safe_connect(db_path: Union[str, Path], *, timeout: float = 30.0, row_factory=True) -> sqlite3.Connection:
    """Open a SQLite connection with concurrent-safety pragmas applied.

    Args:
        db_path: Path to the SQLite database file
        timeout: Seconds to wait if the database is locked (default 30)
        row_factory: If True, use sqlite3.Row for dict-like access

    Returns:
        sqlite3.Connection with WAL mode, busy_timeout, and foreign keys enabled
    """
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    if row_factory:
        conn.row_factory = sqlite3.Row
    for pragma in _SAFETY_PRAGMAS:
        try:
            conn.execute(pragma)
        except sqlite3.OperationalError:
            pass  # Some pragmas can't be set in certain contexts
    return conn


@contextmanager
def safe_connect_ctx(db_path: Union[str, Path], *, timeout: float = 30.0, row_factory=True):
    """Context manager version of safe_connect. Automatically closes on exit.

    Usage:
        with safe_connect_ctx(db_path) as conn:
            conn.execute("INSERT ...")
    """
    conn = safe_connect(db_path, timeout=timeout, row_factory=row_factory)
    try:
        yield conn
    finally:
        conn.close()
