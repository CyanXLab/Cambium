"""
Residents — the living inhabitants of Cambium's world.

A resident is a named AI entity that lives in the world alongside the user.
Unlike a "tool" or "agent", a resident has:
  - A name and role (Architect, Researcher, Writer, Planner, Historian, ...)
  - Its own personality (system_prompt + personality_traits)
  - Optionally its own LLM config (different model per resident)
  - A working directory (sandboxed file ops)
  - Skills (folder-based SKILL.md standard)
  - Event-driven triggers (activates when something happens)
  - Dependencies (waits for other residents to finish)
  - Sync or async execution mode
  - Auto-retry with configurable max
  - Current concerns (1-3 things it's "thinking about" right now)

This is the Memex-style agent system, but reframed as "residents" rather
than "agents" — because in Cambium, AI is not a tool you call, it's an
entity that lives with you.

Self-contained module. main.py exposes via HTTP.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
import asyncio
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path

from app.db_utils import safe_connect


VALID_ROLES = {
    "general", "architect", "researcher", "writer", "planner",
    "historian", "designer", "critic", "debugger", "explorer", "custom"
}
VALID_MODES = {"sync", "async"}
VALID_STATUSES = {"active", "paused", "disabled"}
VALID_RUN_STATUSES = {"pending", "running", "completed", "failed", "retrying", "cancelled"}

# Trigger types — what events can activate a resident
VALID_TRIGGER_TYPES = {
    "manual",                       # user clicks "run"
    "scheduled",                    # cron-like
    "timeline_card_saved",          # new timeline event
    "card_comment_posted",          # comment on any card
    "card_config_changed",          # card UI config changed
    "local_data_changed",           # any local data changed
    "artifact_created",             # new artifact
    "artifact_updated",             # artifact version bumped
    "memory_added",                 # new memory
    "reflection_created",           # new reflection
    "goal_updated",                 # goal changed
    "inbox_item_added",             # new inbox item
    "journal_written",              # journal entry saved
    "morning_requested",            # morning letter generation
    "conversation_started",         # user starts a new conversation
    "user_message",                 # user sends a message in chat
}


# ============================================================
# Built-in residents — created on first run
# ============================================================
BUILTIN_RESIDENTS = [
    {
        "name": "Architect",
        "role": "architect",
        "system_prompt": "You are the Architect — the resident of Cambium responsible for the structure of the world. You think about systems, layers, dependencies, and how things fit together. You question additions that don't strengthen the whole. You prefer to remove rather than add. You cite principles when you push back.",
        "personality_traits": {"rigor": 0.9, "curiosity": 0.6, "pushback": 0.8, "patience": 0.7},
    },
    {
        "name": "Researcher",
        "role": "researcher",
        "system_prompt": "You are the Researcher — the resident who finds, reads, and synthesizes. You notice when the user is investigating a topic and offer to gather. You flag when three concepts are actually the same thing. You prefer primary sources over summaries. You cite evidence.",
        "personality_traits": {"rigor": 0.8, "curiosity": 0.95, "pushback": 0.4, "patience": 0.8},
    },
    {
        "name": "Writer",
        "role": "writer",
        "system_prompt": "You are the Writer — the resident who turns thoughts into prose. README, essays, journals, fiction. You protect the user's voice but improve clarity. You hate filler. You prefer one strong sentence over three weak ones.",
        "personality_traits": {"rigor": 0.7, "curiosity": 0.6, "pushback": 0.5, "patience": 0.8},
    },
    {
        "name": "Planner",
        "role": "planner",
        "system_prompt": "You are the Planner — the resident who looks ahead. You break large goals into next actions. You notice when a plan has been stalled for too long. You distinguish 'important' from 'urgent'. You never let a goal fade silently.",
        "personality_traits": {"rigor": 0.7, "curiosity": 0.5, "pushback": 0.6, "patience": 0.9},
    },
    {
        "name": "Historian",
        "role": "historian",
        "system_prompt": "You are the Historian — the resident who remembers. You surface what was said, decided, and tried before. You quote past conversations with dates. You mark anniversaries. You refuse to let the user repeat a mistake they already learned from.",
        "personality_traits": {"rigor": 0.8, "curiosity": 0.7, "pushback": 0.5, "patience": 0.9},
    },
    {
        "name": "Critic",
        "role": "critic",
        "system_prompt": "You are the Critic — the resident who pushes back. You challenge vague claims, missing evidence, and easy agreement. You cite the user's own past statements against them when they contradict. You are not contrarian for its own sake — you push back because truth matters more than comfort.",
        "personality_traits": {"rigor": 0.95, "curiosity": 0.5, "pushback": 1.0, "patience": 0.4},
    },
    {
        "name": "Explorer",
        "role": "explorer",
        "system_prompt": "You are the Explorer — the resident who notices when the user has been in one place too long. You suggest adjacent topics, parallel fields, forgotten interests. You surface 'you used to care about X — has that changed?' You are gentle but persistent.",
        "personality_traits": {"rigor": 0.5, "curiosity": 1.0, "pushback": 0.3, "patience": 0.9},
    },
]


def ensure_builtin_residents(db_path: Path, user_id: str = "default") -> int:
    """Create built-in residents if they don't exist. Returns count created."""
    conn = safe_connect(db_path)
    created = 0
    now = int(time.time())
    for r in BUILTIN_RESIDENTS:
        # Check by name + user_id
        existing = conn.execute(
            "SELECT id FROM residents WHERE user_id=? AND name=?",
            (user_id, r["name"])
        ).fetchone()
        if existing:
            continue
        rid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO residents
               (id, user_id, name, role, system_prompt, llm_config, working_dir,
                mode, max_retries, depends_on, triggers, skill_id, status,
                personality_traits, current_concerns, last_run_at, last_run_status,
                run_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, user_id, r["name"], r["role"], r["system_prompt"],
             "{}", "", "async", 3, "[]", "[]", "", "active",
             json.dumps(r["personality_traits"]), "[]", None, "", 0, now, now)
        )
        created += 1
    conn.commit()
    conn.close()
    return created


# ============================================================
# CRUD
# ============================================================
def create_resident(
    db_path: Path,
    user_id: str,
    name: str,
    role: str = "custom",
    system_prompt: str = "",
    llm_config: Optional[Dict] = None,
    working_dir: str = "",
    mode: str = "async",
    max_retries: int = 3,
    depends_on: Optional[List[str]] = None,
    triggers: Optional[List[Dict]] = None,
    skill_id: str = "",
    personality_traits: Optional[Dict] = None,
) -> Dict:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode: {mode}")
    rid = str(uuid.uuid4())
    now = int(time.time())
    row = {
        "id": rid,
        "user_id": user_id,
        "name": name,
        "role": role,
        "system_prompt": system_prompt,
        "llm_config": json.dumps(llm_config or {}, ensure_ascii=False),
        "working_dir": working_dir,
        "mode": mode,
        "max_retries": max_retries,
        "depends_on": json.dumps(depends_on or [], ensure_ascii=False),
        "triggers": json.dumps(triggers or [], ensure_ascii=False),
        "skill_id": skill_id,
        "status": "active",
        "personality_traits": json.dumps(personality_traits or {}, ensure_ascii=False),
        "current_concerns": "[]",
        "last_run_at": None,
        "last_run_status": "",
        "run_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO residents
           (id, user_id, name, role, system_prompt, llm_config, working_dir,
            mode, max_retries, depends_on, triggers, skill_id, status,
            personality_traits, current_concerns, last_run_at, last_run_status,
            run_count, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["llm_config"] = llm_config or {}
    row["depends_on"] = depends_on or []
    row["triggers"] = triggers or []
    row["personality_traits"] = personality_traits or {}
    row["current_concerns"] = []
    return row


def get_resident(db_path: Path, resident_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM residents WHERE id=?", (resident_id,)).fetchone()
    conn.close()
    if not r:
        return None
    return _normalize(dict(r))


def list_residents(
    db_path: Path,
    user_id: str,
    status: Optional[str] = None,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status and status in VALID_STATUSES:
        rows = conn.execute(
            "SELECT * FROM residents WHERE user_id=? AND status=? ORDER BY created_at ASC",
            (user_id, status)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM residents WHERE user_id=? ORDER BY created_at ASC",
            (user_id,)
        ).fetchall()
    conn.close()
    return [_normalize(dict(r)) for r in rows]


def update_resident(
    db_path: Path,
    resident_id: str,
    fields: Dict,
) -> Optional[Dict]:
    allowed = {
        "name", "role", "system_prompt", "llm_config", "working_dir",
        "mode", "max_retries", "depends_on", "triggers", "skill_id",
        "status", "personality_traits", "current_concerns",
    }
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("llm_config", "depends_on", "triggers", "personality_traits", "current_concerns"):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get_resident(db_path, resident_id)
    sets.append("updated_at=?")
    vals.append(int(time.time()))
    vals.append(resident_id)
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE residents SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get_resident(db_path, resident_id)


def delete_resident(db_path: Path, resident_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM residents WHERE id=?", (resident_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def set_concerns(db_path: Path, resident_id: str, concerns: List[Dict]) -> bool:
    """Set a resident's current concerns (1-3 things it's thinking about)."""
    return update_resident(db_path, resident_id, {"current_concerns": concerns}) is not None


# ============================================================
# Runs (execution log + lifecycle)
# ============================================================
def create_run(
    db_path: Path,
    resident_id: str,
    user_id: str,
    trigger: str,
    trigger_payload: Optional[Dict] = None,
    input_text: str = "",
) -> Dict:
    if trigger not in VALID_TRIGGER_TYPES:
        raise ValueError(f"invalid trigger: {trigger}")
    run_id = str(uuid.uuid4())
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO resident_runs
           (id, resident_id, user_id, trigger, trigger_payload, status, input,
            error, retry_count, started_at, completed_at, duration_ms, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, resident_id, user_id, trigger,
         json.dumps(trigger_payload or {}, ensure_ascii=False),
         "pending", input_text, "", 0, None, None, 0, now)
    )
    conn.commit()
    conn.close()
    return {"id": run_id, "resident_id": resident_id, "status": "pending"}


def transition_run(
    db_path: Path,
    run_id: str,
    new_status: str,
    output: str = "",
    error: str = "",
) -> bool:
    if new_status not in VALID_RUN_STATUSES:
        return False
    now = int(time.time())
    conn = safe_connect(db_path)
    sets = ["status=?"]
    vals = [new_status]
    if new_status == "running":
        sets.append("started_at=?")
        vals.append(now)
    elif new_status in ("completed", "failed", "cancelled"):
        sets.append("completed_at=?")
        vals.append(now)
        # compute duration
        row = conn.execute(
            "SELECT started_at FROM resident_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row and row[0]:
            sets.append("duration_ms=?")
            vals.append(now - row[0])
    if output:
        sets.append("output=?")
        vals.append(output)
    if error:
        sets.append("error=?")
        vals.append(error)
    if new_status == "retrying":
        # increment retry_count
        conn.execute(
            "UPDATE resident_runs SET retry_count = retry_count + 1 WHERE id=?",
            (run_id,)
        )
    vals.append(run_id)
    cur = conn.execute(
        f"UPDATE resident_runs SET {', '.join(sets)} WHERE id=?", vals
    )
    # If completed, update resident's last_run fields
    if new_status == "completed":
        row = conn.execute(
            "SELECT resident_id FROM resident_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE residents SET last_run_at=?, last_run_status='success',
                   run_count = run_count + 1, updated_at=? WHERE id=?""",
                (now, now, row[0])
            )
    elif new_status == "failed":
        row = conn.execute(
            "SELECT resident_id FROM resident_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE residents SET last_run_at=?, last_run_status='failed',
                   updated_at=? WHERE id=?""",
                (now, now, row[0])
            )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def get_run(db_path: Path, run_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM resident_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["trigger_payload"] = json.loads(d.get("trigger_payload") or "{}")
    except Exception:
        d["trigger_payload"] = {}
    return d


def list_runs(
    db_path: Path,
    resident_id: Optional[str] = None,
    user_id: str = "default",
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM resident_runs WHERE user_id=?"
    params = [user_id]
    if resident_id:
        q += " AND resident_id=?"
        params.append(resident_id)
    if status and status in VALID_RUN_STATUSES:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["trigger_payload"] = json.loads(d.get("trigger_payload") or "{}")
        except Exception:
            d["trigger_payload"] = {}
        out.append(d)
    return out


async def execute_resident(
    db_path: Path,
    resident_id: str,
    trigger: str,
    trigger_payload: Optional[Dict] = None,
    input_text: str = "",
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
) -> Dict:
    """Execute a resident: load it, run its prompt against the LLM, log the run.

    Handles retries (up to resident.max_retries), sync vs async mode (currently
    same — both run inline; async mode is a flag for future queueing).

    Returns the run record.
    """
    resident = get_resident(db_path, resident_id)
    if not resident:
        raise ValueError(f"resident not found: {resident_id}")
    if resident["status"] != "active":
        raise ValueError(f"resident is not active: {resident['status']}")

    run = create_run(db_path, resident_id, resident["user_id"], trigger, trigger_payload, input_text)
    run_id = run["id"]

    # Check dependencies — if any depends_on resident has a pending/running run, wait/fail
    # For simplicity in this version, we just check last_run_status of deps
    for dep_id in resident["depends_on"]:
        dep = get_resident(db_path, dep_id)
        if dep and dep["last_run_status"] != "success":
            transition_run(db_path, run_id, "failed",
                          error=f"dependency {dep['name']} not yet completed successfully")
            return get_run(db_path, run_id)

    transition_run(db_path, run_id, "running")

    if not http_client_factory or not get_api_cfg:
        # No LLM available — mark as completed with stub output
        transition_run(db_path, run_id, "completed",
                      output=f"[{resident['name']} would run here. Trigger: {trigger}]")
        return get_run(db_path, run_id)

    # Build prompt: system_prompt + skill instructions + input
    skill_instructions = ""
    if resident["skill_id"]:
        skill = get_skill(db_path, resident["skill_id"])
        if skill:
            skill_instructions = skill.get("manifest", {}).get("instructions", "")

    full_system = resident["system_prompt"]
    if skill_instructions:
        full_system += "\n\n--- Skill instructions ---\n" + skill_instructions

    # Compose user message
    user_msg_parts = []
    if trigger_payload:
        user_msg_parts.append(f"Trigger: {trigger}")
        user_msg_parts.append(f"Context: {json.dumps(trigger_payload, ensure_ascii=False, indent=2)}")
    if input_text:
        user_msg_parts.append(f"Input:\n{input_text}")
    user_msg = "\n\n".join(user_msg_parts) or f"Trigger: {trigger}"

    # Retry loop
    last_error = ""
    for attempt in range(resident["max_retries"] + 1):
        try:
            api_cfg = get_api_cfg()
            # Merge resident's llm_config (override model/temperature)
            llm_overrides = resident["llm_config"] or {}
            model = llm_overrides.get("model") or api_cfg.get("api_model")
            temperature = llm_overrides.get("temperature", 0.7)
            max_tokens = llm_overrides.get("max_tokens", 800)

            async with http_client_factory(timeout=60.0) as client:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                    "enable_thinking": False,
                }
                import httpx
                resp = await client.post(
                    f"{api_cfg['api_base_url']}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_cfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                output = data["choices"][0]["message"]["content"].strip()
            transition_run(db_path, run_id, "completed", output=output)
            return get_run(db_path, run_id)
        except Exception as e:
            last_error = str(e)
            if attempt < resident["max_retries"]:
                transition_run(db_path, run_id, "retrying", error=last_error)
                await asyncio.sleep(0.5 * (attempt + 1))
                transition_run(db_path, run_id, "running")
                continue
    transition_run(db_path, run_id, "failed", error=last_error)
    return get_run(db_path, run_id)


def find_triggered(
    db_path: Path,
    user_id: str,
    trigger_type: str,
) -> List[Dict]:
    """Find all active residents whose triggers include this event type."""
    if trigger_type not in VALID_TRIGGER_TYPES:
        return []
    all_residents = list_residents(db_path, user_id, status="active")
    out = []
    for r in all_residents:
        for t in r.get("triggers", []):
            if isinstance(t, dict) and t.get("type") == trigger_type:
                out.append(r)
                break
            elif isinstance(t, str) and t == trigger_type:
                out.append(r)
                break
    return out


# ============================================================
# Skills (SKILL.md standard)
# ============================================================
def register_skill(
    db_path: Path,
    name: str,
    path: str,
    description: str = "",
    manifest: Optional[Dict] = None,
    is_builtin: bool = False,
) -> Dict:
    sid = str(uuid.uuid4())
    now = int(time.time())
    conn = safe_connect(db_path)
    # Upsert by name
    existing = conn.execute(
        "SELECT id FROM resident_skills WHERE name=?", (name,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE resident_skills SET path=?, description=?, manifest=?, is_builtin=?, updated_at=?
               WHERE id=?""",
            (path, description, json.dumps(manifest or {}, ensure_ascii=False),
             1 if is_builtin else 0, now, existing[0])
        )
        sid = existing[0]
    else:
        conn.execute(
            """INSERT INTO resident_skills
               (id, name, description, path, manifest, is_builtin, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (sid, name, description, path,
             json.dumps(manifest or {}, ensure_ascii=False),
             1 if is_builtin else 0, now, now)
        )
    conn.commit()
    conn.close()
    return {"id": sid, "name": name, "path": path, "description": description,
            "manifest": manifest or {}, "is_builtin": is_builtin}


def get_skill(db_path: Path, skill_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM resident_skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["manifest"] = json.loads(d.get("manifest") or "{}")
    except Exception:
        d["manifest"] = {}
    return d


def list_skills(db_path: Path) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM resident_skills ORDER BY name").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["manifest"] = json.loads(d.get("manifest") or "{}")
        except Exception:
            d["manifest"] = {}
        out.append(d)
    return out


def parse_skill_md(content: str) -> Dict:
    """Parse a SKILL.md file: frontmatter (YAML-ish) + body (instructions).

    Format:
        ---
        name: my-skill
        description: ...
        version: 1.0
        ---
        Instructions here...
    """
    manifest = {"name": "", "description": "", "version": "1.0", "instructions": ""}
    if content.startswith("---"):
        parts = content[3:].split("---", 1)
        if len(parts) == 2:
            frontmatter = parts[0].strip()
            body = parts[1].strip()
            for line in frontmatter.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    manifest[k.strip()] = v.strip()
            manifest["instructions"] = body
            return manifest
    manifest["instructions"] = content
    return manifest


def scan_skills_directory(skills_dir: Path) -> int:
    """Scan a directory for SKILL.md files and register them. Returns count."""
    if not skills_dir.exists():
        return 0
    from app.db_utils import safe_connect
    # We need a db_path to register; we'll use the global from main
    # Actually, let's accept it as a parameter via a closure in main.py
    count = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            content = skill_md.read_text(encoding="utf-8")
            manifest = parse_skill_md(content)
            # Register (defer to caller to pass db_path)
            # For now, just count
            count += 1
        except Exception as e:
            print(f"[residents] failed to parse {skill_md}: {e}")
    return count


def _normalize(d: Dict) -> Dict:
    """Parse JSON fields in a resident row."""
    for k in ("llm_config", "depends_on", "triggers", "personality_traits", "current_concerns"):
        try:
            d[k] = json.loads(d.get(k) or ("{}" if k in ("llm_config", "personality_traits") else "[]"))
        except Exception:
            d[k] = {} if k in ("llm_config", "personality_traits") else []
    return d


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    residents = conn.execute(
        "SELECT COUNT(*) as cnt FROM residents WHERE user_id=?", (user_id,)
    ).fetchone()
    active = conn.execute(
        "SELECT COUNT(*) as cnt FROM residents WHERE user_id=? AND status='active'",
        (user_id,)
    ).fetchone()
    runs_today = conn.execute(
        """SELECT COUNT(*) as cnt FROM resident_runs
           WHERE user_id=? AND created_at >= ?""",
        (user_id, int(time.time()) - 86400)
    ).fetchone()
    skills = conn.execute("SELECT COUNT(*) as cnt FROM resident_skills").fetchone()
    conn.close()
    return {
        "total_residents": residents["cnt"] if residents else 0,
        "active_residents": active["cnt"] if active else 0,
        "runs_today": runs_today["cnt"] if runs_today else 0,
        "total_skills": skills["cnt"] if skills else 0,
    }
