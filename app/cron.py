from __future__ import annotations
"""
Cron subsystem — scheduled task execution for the AI agent.

Supports:
- cron expressions (5-field: minute hour day month weekday)
- one-shot scheduled tasks (epoch millis)
- fixed-rate recurring tasks (every N minutes)
- Each job has: id, schedule, prompt, target_session_model, last_run, next_run, enabled
- Jobs run in a background asyncio task that checks every 60s
- When a job fires, it spawns a new session with the configured prompt
- Job results are stored and viewable in the UI (separate chat page)

This module is self-contained; main.py wires up HTTP endpoints and the
background scheduler loop.
"""
import asyncio
import json
import sqlite3
import time
from app.db_utils import safe_connect
import re
import uuid
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from datetime import datetime, timezone, timedelta


def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'cron',
            -- 'cron' = cron expression, 'one_time' = epoch millis, 'fixed_rate' = interval seconds
            schedule TEXT NOT NULL,
            prompt TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            system_prompt TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            last_run INTEGER,
            next_run INTEGER,
            last_result TEXT,
            last_session_id TEXT,
            run_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS cron_runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            session_id TEXT,
            started_at INTEGER NOT NULL,
            completed_at INTEGER,
            status TEXT NOT NULL DEFAULT 'running',
            result TEXT,
            FOREIGN KEY (job_id) REFERENCES cron_jobs(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_cron_runs_job ON cron_runs(job_id);
        CREATE INDEX IF NOT EXISTS idx_cron_jobs_enabled ON cron_jobs(enabled);
    """)
    conn.commit()
    conn.close()


def cron_create(db_path: Path, *, name: str = "", kind: str = "cron",
                schedule: str = "", prompt: str = "", model: str = "",
                system_prompt: str = "", enabled: bool = True) -> Dict:
    sid = uuid.uuid4().hex[:16]
    now = int(time.time())
    next_run = _compute_next_run(kind, schedule, now)
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO cron_jobs (id, name, kind, schedule, prompt, model, system_prompt, enabled, created_at, next_run) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, name, kind, schedule, prompt, model, system_prompt, 1 if enabled else 0, now, next_run)
    )
    conn.commit()
    conn.close()
    return {"id": sid, "name": name, "kind": kind, "schedule": schedule, "next_run": next_run}


def cron_list(db_path: Path, include_disabled: bool = True) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if include_disabled:
        rows = conn.execute("SELECT * FROM cron_jobs ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM cron_jobs WHERE enabled=1 ORDER BY next_run ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cron_get(db_path: Path, job_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM cron_jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def cron_update(db_path: Path, job_id: str, **fields) -> bool:
    if not fields:
        return False
    # Recompute next_run if schedule changed
    if "schedule" in fields or "kind" in fields:
        job = cron_get(db_path, job_id)
        if job:
            kind = fields.get("kind", job["kind"])
            schedule = fields.get("schedule", job["schedule"])
            fields["next_run"] = _compute_next_run(kind, schedule, int(time.time()))
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [job_id]
    conn = safe_connect(db_path)
    cur = conn.execute(f"UPDATE cron_jobs SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def cron_delete(db_path: Path, job_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM cron_jobs WHERE id=?", (job_id,))
    conn.execute("DELETE FROM cron_runs WHERE job_id=?", (job_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def cron_runs_list(db_path: Path, job_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if job_id:
        rows = conn.execute(
            "SELECT * FROM cron_runs WHERE job_id=? ORDER BY started_at DESC LIMIT ?",
            (job_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM cron_runs ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Cron expression parsing (5-field)
# ============================================================

def _parse_cron_field(expr: str, min_val: int, max_val: int) -> set:
    """Parse a single cron field. Supports: *, */N, N, N-M, N,M,K."""
    result = set()
    for part in expr.split(","):
        part = part.strip()
        if part == "*":
            result.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                start, end = min_val, max_val
            elif "-" in base:
                s, e = base.split("-")
                start, end = int(s), int(e)
            else:
                start, end = int(base), max_val
            result.update(range(start, end + 1, step))
        elif "-" in part:
            s, e = part.split("-")
            result.update(range(int(s), int(e) + 1))
        else:
            result.add(int(part))
    return {x for x in result if min_val <= x <= max_val}


def _parse_cron(expr: str) -> Optional[Dict]:
    """Parse a 5-field cron expression. Returns dict with sets for each field, or None if invalid."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return None
    try:
        minute = _parse_cron_field(parts[0], 0, 59)
        hour = _parse_cron_field(parts[1], 0, 23)
        day = _parse_cron_field(parts[2], 1, 31)
        month = _parse_cron_field(parts[3], 1, 12)
        # Weekday: 0-6 (0=Sunday in cron, but we'll accept 0-7)
        weekday = _parse_cron_field(parts[4], 0, 7)
        if 7 in weekday:
            weekday.discard(7)
            weekday.add(0)
        return {"minute": minute, "hour": hour, "day": day, "month": month, "weekday": weekday}
    except Exception:
        return None


def _compute_next_run(kind: str, schedule: str, from_ts: int) -> int:
    """Compute the next run timestamp for a schedule."""
    now = datetime.fromtimestamp(from_ts, tz=timezone.utc)
    if kind == "one_time":
        try:
            return int(schedule)
        except Exception:
            return from_ts + 86400  # fallback: 1 day
    if kind == "fixed_rate":
        try:
            interval = int(schedule)
            return from_ts + interval
        except Exception:
            return from_ts + 3600
    if kind == "cron":
        cron = _parse_cron(schedule)
        if not cron:
            return from_ts + 3600  # fallback: 1 hour
        # Find next matching time, scanning minute by minute (max 366 days)
        for i in range(1, 366 * 24 * 60):
            t = now + timedelta(minutes=i)
            if (t.minute in cron["minute"] and
                t.hour in cron["hour"] and
                t.day in cron["day"] and
                t.month in cron["month"] and
                (t.weekday() + 1) % 7 in cron["weekday"]):
                return int(t.timestamp())
        return from_ts + 86400
    return from_ts + 3600


# ============================================================
# Scheduler loop
# ============================================================

_scheduler_task: Optional[asyncio.Task] = None
_scheduler_running = False


async def scheduler_loop(db_path: Path, spawn_fn: Callable, check_interval: int = 60):
    """Background loop that checks for due cron jobs and spawns sessions.
    spawn_fn(job_dict) -> session_id (called when a job is due)."""
    global _scheduler_running
    _scheduler_running = True
    while _scheduler_running:
        try:
            now = int(time.time())
            jobs = cron_list(db_path, include_disabled=False)
            for job in jobs:
                next_run = job.get("next_run") or 0
                if next_run <= now:
                    try:
                        # Spawn a session for this job
                        session_id = await spawn_fn(job)
                        # Record run
                        run_id = uuid.uuid4().hex[:16]
                        conn = safe_connect(db_path)
                        conn.execute(
                            "INSERT INTO cron_runs (id, job_id, session_id, started_at, status) VALUES (?,?,?,?,?)",
                            (run_id, job["id"], session_id, now, "running")
                        )
                        conn.execute(
                            "UPDATE cron_jobs SET last_run=?, next_run=?, run_count=run_count+1, last_session_id=? WHERE id=?",
                            (now, _compute_next_run(job["kind"], job["schedule"], now), session_id, job["id"])
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"[cron] job {job.get('name', job['id'])} failed to spawn: {e}")
        except Exception as e:
            print(f"[cron] scheduler error: {e}")
        await asyncio.sleep(check_interval)


def start_scheduler(db_path: Path, spawn_fn: Callable) -> asyncio.Task:
    """Start the background scheduler. Returns the asyncio task."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task
    _scheduler_task = asyncio.create_task(scheduler_loop(db_path, spawn_fn))
    return _scheduler_task


def stop_scheduler():
    global _scheduler_running, _scheduler_task
    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
