"""
Agent Runtime for Cambium — long-running tasks with lifecycle management.

Unlike a simple "one-shot" LLM call, the runtime supports:
- Task state machine: pending → running → (paused ↔ resumed) → completed/cancelled/failed
- Dependencies: task B can wait for task A to complete
- Priority: higher-priority tasks run first
- Agent assignment: tasks can be assigned to internal agents (planner/researcher/etc.)
- Progress tracking: 0-100%
- Event log: every state change is recorded
- Background execution: tasks run as asyncio tasks, don't block user chat

This transforms Cambium from "chat → answer" to "chat → plan → spawn tasks →
background work → report back". The AI is always alive.

State machine:
    pending → running → completed
              ↕          ↑
            paused → resumed
              ↓
           cancelled
"""
from __future__ import annotations
import asyncio
import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from pathlib import Path
from app.db_utils import safe_connect


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Valid state transitions
_VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.PAUSED: {TaskStatus.RESUMED, TaskStatus.CANCELLED},
    TaskStatus.RESUMED: {TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),  # terminal
    TaskStatus.CANCELLED: set(),  # terminal
    TaskStatus.FAILED: set(),     # terminal (could add retry → PENDING later)
}

INTERNAL_AGENTS = ["planner", "researcher", "memory", "reflection", "critic", "default"]


def _log_event(db_path: Path, task_id: str, event_type: str, message: str = ""):
    """Log a runtime event."""
    eid = hashlib.sha1(f"{task_id}:{event_type}:{time.time()}".encode()).hexdigest()[:16]
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO runtime_events (id, task_id, event_type, message, timestamp) VALUES (?,?,?,?,?)",
        (eid, task_id, event_type, message, int(time.time()))
    )
    conn.commit()
    conn.close()


def create_task(db_path: Path, *, user_id: str = "default",
                title: str, description: str = "",
                priority: int = 5, parent_task: Optional[str] = None,
                depends_on: Optional[List[str]] = None,
                assigned_agent: str = "default",
                input: Optional[Dict] = None) -> Dict:
    """Create a new runtime task."""
    tid = hashlib.sha1(f"{user_id}:{title}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO runtime_tasks (id, user_id, title, description, status, priority, "
        "parent_task, depends_on, assigned_agent, input, output, error, progress, "
        "created_at, started_at, paused_at, completed_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tid, user_id, title, description, TaskStatus.PENDING.value, priority,
         parent_task, json.dumps(depends_on or [], ensure_ascii=False),
         assigned_agent if assigned_agent in INTERNAL_AGENTS else "default",
         json.dumps(input or {}, ensure_ascii=False),
         "{}", "", 0, now, None, None, None, now)
    )
    conn.commit()
    conn.close()
    _log_event(db_path, tid, "created", f"Task created: {title}")
    return {"id": tid, "title": title, "status": TaskStatus.PENDING.value}


def transition_task(db_path: Path, task_id: str, new_status: TaskStatus,
                    message: str = "") -> Dict:
    """Transition a task to a new status. Validates the transition."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM runtime_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "task not found"}
    current = TaskStatus(row["status"])
    if new_status not in _VALID_TRANSITIONS.get(current, set()):
        conn.close()
        return {"ok": False, "error": f"invalid transition: {current.value} → {new_status.value}"}
    now = int(time.time())
    updates = {"status": new_status.value, "updated_at": now}
    if new_status == TaskStatus.RUNNING:
        updates["started_at"] = now
    elif new_status == TaskStatus.PAUSED:
        updates["paused_at"] = now
    elif new_status == TaskStatus.COMPLETED:
        updates["completed_at"] = now
        updates["progress"] = 100
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [task_id]
    conn.execute(f"UPDATE runtime_tasks SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()
    _log_event(db_path, task_id, new_status.value, message)
    return {"ok": True, "task_id": task_id, "status": new_status.value}


def update_task_progress(db_path: Path, task_id: str, progress: int,
                          output: Optional[Dict] = None) -> bool:
    """Update task progress (0-100). Optionally update output."""
    now = int(time.time())
    conn = safe_connect(db_path)
    if output:
        conn.execute(
            "UPDATE runtime_tasks SET progress=?, output=?, updated_at=? WHERE id=?",
            (max(0, min(100, progress)), json.dumps(output, ensure_ascii=False), now, task_id)
        )
    else:
        conn.execute(
            "UPDATE runtime_tasks SET progress=?, updated_at=? WHERE id=?",
            (max(0, min(100, progress)), now, task_id)
        )
    conn.commit()
    conn.close()
    return True


def set_task_output(db_path: Path, task_id: str, output: Dict, status: Optional[TaskStatus] = None) -> bool:
    """Set task output and optionally transition status."""
    now = int(time.time())
    conn = safe_connect(db_path)
    if status:
        updates = {"output": json.dumps(output, ensure_ascii=False), "status": status.value, "updated_at": now}
        if status == TaskStatus.COMPLETED:
            updates["completed_at"] = now
            updates["progress"] = 100
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [task_id]
        conn.execute(f"UPDATE runtime_tasks SET {sets} WHERE id=?", vals)
    else:
        conn.execute(
            "UPDATE runtime_tasks SET output=?, updated_at=? WHERE id=?",
            (json.dumps(output, ensure_ascii=False), now, task_id)
        )
    conn.commit()
    conn.close()
    if status:
        _log_event(db_path, task_id, status.value, "output set")
    return True


def set_task_error(db_path: Path, task_id: str, error: str) -> bool:
    """Mark a task as failed with an error message."""
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "UPDATE runtime_tasks SET status=?, error=?, updated_at=? WHERE id=?",
        (TaskStatus.FAILED.value, error, now, task_id)
    )
    conn.commit()
    conn.close()
    _log_event(db_path, task_id, "failed", error)
    return True


def get_task(db_path: Path, task_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM runtime_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["depends_on"] = json.loads(d.get("depends_on", "[]"))
    d["input"] = json.loads(d.get("input", "{}"))
    d["output"] = json.loads(d.get("output", "{}"))
    return d


def list_tasks(db_path: Path, *, user_id: str = "default",
               status: Optional[str] = None, assigned_agent: Optional[str] = None,
               limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM runtime_tasks WHERE user_id=?"
    params = [user_id]
    if status:
        sql += " AND status=?"
        params.append(status)
    if assigned_agent:
        sql += " AND assigned_agent=?"
        params.append(assigned_agent)
    sql += " ORDER BY priority DESC, created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["depends_on"] = json.loads(d.get("depends_on", "[]"))
        d["input"] = json.loads(d.get("input", "{}"))
        d["output"] = json.loads(d.get("output", "{}"))
        out.append(d)
    return out


def get_task_events(db_path: Path, task_id: str, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runtime_events WHERE task_id=? ORDER BY timestamp DESC LIMIT ?",
        (task_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ready_tasks(db_path: Path, user_id: str = "default") -> List[Dict]:
    """Get tasks that are pending AND all dependencies are completed."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runtime_tasks WHERE user_id=? AND status='pending' ORDER BY priority DESC, created_at",
        (user_id,)
    ).fetchall()
    conn.close()
    ready = []
    for r in rows:
        d = dict(r)
        deps = json.loads(d.get("depends_on", "[]"))
        if not deps:
            ready.append(d)
            continue
        # Check if all deps are completed
        conn = safe_connect(db_path)
        all_done = True
        for dep_id in deps:
            dep = conn.execute(
                "SELECT status FROM runtime_tasks WHERE id=?", (dep_id,)
            ).fetchone()
            if not dep or dep[0] != TaskStatus.COMPLETED.value:
                all_done = False
                break
        conn.close()
        if all_done:
            ready.append(d)
    return ready


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    stats = {}
    for s in TaskStatus:
        count = conn.execute(
            "SELECT COUNT(*) FROM runtime_tasks WHERE user_id=? AND status=?",
            (user_id, s.value)
        ).fetchone()[0]
        stats[s.value] = count
    conn.close()
    return stats
