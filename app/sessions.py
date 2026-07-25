from __future__ import annotations
"""
Multi-session subsystem — allows AI to spawn background sessions that process
tasks in parallel. Each session has its own message history and can be queried
via sessions_list/sessions_history/session_status.

A session is essentially an asyncio task running an LLM conversation loop.
The session runs independently of the main chat, and its result is stored
when it completes. Sessions can also communicate with each other via
sessions_send.

This module is self-contained: it doesn't import FastAPI, so it can be tested
in isolation. main.py wires it up to HTTP endpoints.
"""
import asyncio
import json
import time
import uuid
import sqlite3
from typing import Dict, List, Optional, Any, Callable
from app.db_utils import safe_connect
from pathlib import Path


# In-memory registry of active sessions
_sessions: Dict[str, Dict[str, Any]] = {}
# Lock for concurrent access
_lock = asyncio.Lock()


def init_db(db_path: Path):
    """Create the sessions table if it doesn't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            parent_session TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            model TEXT NOT NULL DEFAULT '',
            system_prompt TEXT NOT NULL DEFAULT '',
            user_message TEXT NOT NULL DEFAULT '',
            assistant_result TEXT NOT NULL DEFAULT '',
            messages_json TEXT NOT NULL DEFAULT '[]',
            created_at INTEGER NOT NULL,
            started_at INTEGER,
            completed_at INTEGER,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
    """)
    conn.commit()
    conn.close()


def session_create(db_path: Path, *, title: str = "", parent_session: Optional[str] = None,
                   model: str = "", system_prompt: str = "", user_message: str = "") -> Dict:
    """Create a session record in DB and return its data."""
    sid = uuid.uuid4().hex[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO sessions (id, title, parent_session, status, model, system_prompt, user_message, messages_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (sid, title, parent_session, "pending", model, system_prompt, user_message, "[]", now)
    )
    conn.commit()
    conn.close()
    return {
        "id": sid,
        "title": title,
        "parent_session": parent_session,
        "status": "pending",
        "model": model,
        "system_prompt": system_prompt,
        "user_message": user_message,
        "messages": [],
        "created_at": now,
    }


def session_update(db_path: Path, sid: str, **fields):
    """Update session fields in DB."""
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [sid]
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE sessions SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def session_get(db_path: Path, sid: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["messages"] = json.loads(d.get("messages_json", "[]"))
    except Exception:
        d["messages"] = []
    return d


def session_list(db_path: Path, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute(
            "SELECT id, title, parent_session, status, model, created_at, started_at, completed_at, error "
            "FROM sessions WHERE status=? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, parent_session, status, model, created_at, started_at, completed_at, error "
            "FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def session_delete(db_path: Path, sid: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


async def session_run(sid: str, db_path: Path, messages: List[Dict],
                      api_cfg: Dict, system_prompt: str,
                      on_message: Optional[Callable] = None,
                      max_turns: int = 10):
    """Run an LLM conversation loop for a session. Updates DB with progress.
    api_cfg: {api_key, api_base_url, api_model}
    on_message: optional callback(chunk_dict) for streaming events
    """
    import httpx
    session_update(db_path, sid, status="running", started_at=int(time.time()))
    full_response = ""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            for turn in range(max_turns):
                # Build messages
                msgs = []
                if system_prompt:
                    msgs.append({"role": "system", "content": system_prompt})
                msgs.extend(messages)
                payload = {
                    "model": api_cfg["api_model"],
                    "messages": msgs,
                    "stream": False,
                    "enable_thinking": False,
                    "temperature": 0.6,
                    "max_tokens": 4096,
                }
                resp = await client.post(
                    f"{api_cfg['api_base_url']}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_cfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                messages.append({"role": "assistant", "content": reply})
                full_response = reply
                # Persist
                session_update(db_path, sid,
                    messages_json=json.dumps(messages, ensure_ascii=False),
                    assistant_result=reply[:5000])
                if on_message:
                    on_message({"type": "assistant", "content": reply, "turn": turn})
                # Check if there's a follow-up question (we stop after one turn for now;
                # multi-turn requires user input which isn't supported in background mode)
                break
        session_update(db_path, sid, status="completed", completed_at=int(time.time()))
        if on_message:
            on_message({"type": "done", "result": full_response})
        return full_response
    except Exception as e:
        session_update(db_path, sid, status="failed", error=str(e)[:500],
                      completed_at=int(time.time()))
        if on_message:
            on_message({"type": "error", "error": str(e)})
        raise


async def spawn_session(sid: str, db_path: Path, api_cfg: Dict,
                        system_prompt: str, user_message: str,
                        title: str = "", model: str = "",
                        on_message: Optional[Callable] = None):
    """Spawn a background session that runs an LLM conversation."""
    messages = [{"role": "user", "content": user_message}]
    # Use provided model or fall back to api_cfg
    effective_cfg = dict(api_cfg)
    if model:
        effective_cfg["api_model"] = model
    try:
        await session_run(sid, db_path, messages, effective_cfg, system_prompt, on_message)
    except Exception as e:
        # Already recorded in DB
        pass


def session_send(db_path: Path, sid: str, message: str) -> Dict:
    """Send a follow-up message to a completed session, resuming the conversation.
    Returns the new assistant reply (synchronously)."""
    import asyncio
    import httpx
    sess = session_get(db_path, sid)
    if not sess:
        return {"success": False, "error": "session not found"}
    messages = sess.get("messages", [])
    messages.append({"role": "user", "content": message})
    # Synchronous call (since this is invoked from a tool dispatcher that's sync)
    api_cfg = _get_api_cfg_for_session(sess)
    try:
        loop = asyncio.new_event_loop()
        try:
            async def _run():
                async with httpx.AsyncClient(timeout=120.0) as c:
                    payload = {
                        "model": api_cfg["api_model"],
                        "messages": ([{"role": "system", "content": sess["system_prompt"]}] if sess["system_prompt"] else []) + messages,
                        "stream": False,
                        "enable_thinking": False,
                    }
                    r = await c.post(
                        f"{api_cfg['api_base_url']}/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
                    )
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            reply = loop.run_until_complete(_run())
        finally:
            loop.close()
        messages.append({"role": "assistant", "content": reply})
        session_update(db_path, sid,
            messages_json=json.dumps(messages, ensure_ascii=False),
            assistant_result=reply[:5000],
            status="completed",
            completed_at=int(time.time()))
        return {"success": True, "result": reply, "messages": messages}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_api_cfg_for_session(sess: Dict) -> Dict:
    """Get API config for a session. Placeholder — main.py overrides this."""
    return {"api_key": "", "api_base_url": "", "api_model": ""}
