"""
Swarm Intelligence — multi-agent collaboration system.

Like a team of employees: you give a task, they decompose it, assign to each other,
communicate visibly (you can watch), argue, compromise, and deliver a result.

Flow:
  1. User or Self-Goal creates a SwarmTask
  2. Planner decomposes it into subtasks + assigns to residents
  3. Each assigned resident executes their part, posting messages to the task channel
  4. Residents can see each other's messages, agree/object/handoff
  5. Critic reviews the combined result
  6. Final result delivered to user

This is NOT "one AI wearing 7 masks". Each resident has independent state,
independent perspective, independent personality. They share the cognitive kernel
(identity, memories, timeline) but have their own working memory and opinions.

Self-Goal Generation:
  Life Loop observes patterns in user behavior, system state, and external data.
  When it finds something worth acting on, it creates a SelfGoal:
    - Title + description of the opportunity/issue
    - Evidence (what data led to this)
    - Proposed actions (which residents would do what)
    - Risk assessment
    - Confidence score
  User gets notified and can approve/reject. If approved, a SwarmTask is created.
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


# ============================================================
# Swarm Task CRUD
# ============================================================

def create_task(
    db_path: Path, user_id: str, title: str, description: str = "",
    created_by: str = "user", priority: int = 5, tags: Optional[List[str]] = None,
    parent_task: Optional[str] = None,
) -> Dict:
    tid = str(uuid.uuid4())
    now = int(time.time())
    row = {
        "id": tid, "user_id": user_id, "title": title, "description": description,
        "status": "pending", "created_by": created_by, "parent_task": parent_task,
        "subtasks": "[]", "result": "", "priority": priority,
        "tags": json.dumps(tags or [], ensure_ascii=False),
        "created_at": now, "updated_at": now, "completed_at": None,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO swarm_tasks
           (id, user_id, title, description, status, created_by, parent_task,
            subtasks, result, priority, tags, created_at, updated_at, completed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["subtasks"] = []
    row["tags"] = tags or []
    return row


def get_task(db_path: Path, task_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM swarm_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    for k in ("subtasks", "tags"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    return d


def list_tasks(db_path: Path, user_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute(
            "SELECT * FROM swarm_tasks WHERE user_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
            (user_id, status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM swarm_tasks WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("subtasks", "tags"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except Exception:
                d[k] = []
        out.append(d)
    return out


def update_task(db_path: Path, task_id: str, **fields) -> Optional[Dict]:
    allowed = {"title", "description", "status", "subtasks", "result", "priority", "tags", "completed_at"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("subtasks", "tags"):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return get_task(db_path, task_id)
    sets.append("updated_at=?")
    vals.append(int(time.time()))
    vals.append(task_id)
    conn = safe_connect(db_path)
    conn.execute(f"UPDATE swarm_tasks SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return get_task(db_path, task_id)


def delete_task(db_path: Path, task_id: str) -> bool:
    conn = safe_connect(db_path)
    cur = conn.execute("DELETE FROM swarm_tasks WHERE id=?", (task_id,))
    conn.execute("DELETE FROM swarm_messages WHERE task_id=?", (task_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


# ============================================================
# Swarm Messages — visible inter-agent communication
# ============================================================

def add_message(
    db_path: Path, task_id: str, from_resident: str, content: str,
    to_resident: str = "all", message_type: str = "message",
    round_num: int = 0, metadata: Optional[Dict] = None,
) -> Dict:
    mid = str(uuid.uuid4())
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO swarm_messages
           (id, task_id, from_resident, to_resident, message_type, content, metadata, round, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (mid, task_id, from_resident, to_resident, message_type, content,
         json.dumps(metadata or {}, ensure_ascii=False), round_num, now)
    )
    conn.commit()
    conn.close()
    return {
        "id": mid, "task_id": task_id, "from_resident": from_resident,
        "to_resident": to_resident, "message_type": message_type,
        "content": content, "round": round_num, "created_at": now,
    }


def get_messages(db_path: Path, task_id: str, limit: int = 100) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM swarm_messages WHERE task_id=? ORDER BY created_at ASC LIMIT ?",
        (task_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = {}
        out.append(d)
    return out


# ============================================================
# Task Execution — multi-agent collaboration
# ============================================================

async def execute_swarm_task(
    db_path: Path,
    task_id: str,
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
    max_rounds: int = 3,
) -> Dict:
    """Execute a swarm task with multi-agent collaboration.
    
    Flow:
    1. Planner decomposes task into subtasks + assigns residents
    2. Each resident executes their subtask, posting visible messages
    3. Residents can see each other's work, agree/object
    4. Critic reviews combined result
    5. Final result saved to task
    """
    from app import residents as residents_mod
    from app.llm_utils import extract_content

    task = get_task(db_path, task_id)
    if not task:
        return {"error": "task not found"}

    update_task(db_path, task_id, status="decomposing")
    add_message(db_path, task_id, "system", f"任务开始: {task['title']}", message_type="system")

    # 1. Planner decomposes
    planner = _find_resident_by_role(db_path, "planner")
    if planner:
        decomposition = await _llm_call(
            planner, f"你是 Planner。分解以下任务为 2-4 个子任务，分配给合适的居民。\n\n任务: {task['title']}\n描述: {task['description']}\n\n可用居民: Architect, Researcher, Writer, Critic, Explorer, Historian\n\n输出 JSON: {{\"subtasks\": [{{\"title\": \"...\", \"assigned_to\": \"Architect\", \"description\": \"...\"}}]}}",
            http_client_factory, get_api_cfg
        )
        subtasks = _parse_json(decomposition).get("subtasks", [])
    else:
        subtasks = [{"title": task["title"], "assigned_to": "Cambium", "description": task["description"]}]

    # Save subtask assignments
    assigned_subtasks = []
    for st in subtasks:
        st_id = str(uuid.uuid4())[:8]
        assigned_subtasks.append({
            "id": st_id,
            "title": st.get("title", ""),
            "assigned_to": st.get("assigned_to", "Cambium"),
            "description": st.get("description", ""),
            "status": "pending",
        })
    update_task(db_path, task_id, status="executing", subtasks=assigned_subtasks)

    add_message(db_path, task_id, "Planner" if planner else "system",
                f"任务已分解为 {len(assigned_subtasks)} 个子任务:\n" +
                "\n".join(f"  {i+1}. {st['title']} → {st['assigned_to']}" for i, st in enumerate(assigned_subtasks)),
                message_type="proposal", round_num=0)

    # 2. Each resident executes their subtask
    results = []
    for i, st in enumerate(assigned_subtasks):
        resident = _find_resident_by_name(db_path, st["assigned_to"])
        if not resident:
            resident = _find_resident_by_role(db_path, "general") or _find_resident_by_role(db_path, "architect")

        if resident:
            # Gather previous results for context
            prev_context = ""
            if results:
                prev_context = "\n\n之前的子任务结果:\n" + "\n".join(
                    f"  [{r['resident']}] {r['result'][:200]}" for r in results
                )

            add_message(db_path, task_id, resident["name"],
                        f"开始执行: {st['title']}", message_type="message", round_num=1)

            result_text = await _llm_call(
                resident,
                f"你是 {resident['name']}。执行以下子任务:\n\n子任务: {st['title']}\n描述: {st['description']}\n{prev_context}\n\n完成你的部分，输出结果（200-500字）。",
                http_client_factory, get_api_cfg
            )

            add_message(db_path, task_id, resident["name"],
                        result_text, message_type="result", round_num=1)
            results.append({"resident": resident["name"], "result": result_text})
            st["status"] = "completed"
        else:
            add_message(db_path, task_id, "system",
                        f"未找到居民 {st['assigned_to']}", message_type="system", round_num=1)
            results.append({"resident": st["assigned_to"], "result": "(居民未找到)"})
            st["status"] = "failed"

    update_task(db_path, task_id, subtasks=assigned_subtasks)

    # 3. Critic reviews
    critic = _find_resident_by_role(db_path, "critic")
    if critic and results:
        combined = "\n\n".join(f"[{r['resident']}]: {r['result']}" for r in results)
        review = await _llm_call(
            critic,
            f"你是 Critic。审查以下各居民的执行结果，指出问题，给出改进建议或确认通过:\n\n{combined}\n\n输出审查意见（100-300字）。",
            http_client_factory, get_api_cfg
        )
        add_message(db_path, task_id, critic["name"],
                    review, message_type="result", round_num=2)

    # 4. Final result
    final_result = "\n\n".join(f"### {r['resident']}\n{r['result']}" for r in results)
    if critic and review:
        final_result += f"\n\n### Critic 审查\n{review}"

    update_task(db_path, task_id, status="completed", result=final_result, completed_at=int(time.time()))
    add_message(db_path, task_id, "system", "任务完成", message_type="system", round_num=3)

    return {
        "task_id": task_id,
        "status": "completed",
        "result": final_result,
        "messages": get_messages(db_path, task_id),
    }


async def _llm_call(
    resident: Dict, prompt: str,
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
) -> str:
    """Call LLM with resident's personality."""
    if not http_client_factory or not get_api_cfg:
        return f"（{resident['name']} 会在这里执行，但 LLM 未配置）"
    try:
        import httpx
        api_cfg = get_api_cfg()
        llm_overrides = resident.get("llm_config", {})
        model = llm_overrides.get("model") or api_cfg.get("api_model", "")
        system_prompt = resident.get("system_prompt", f"你是 {resident['name']}。")
        async with http_client_factory(timeout=60.0) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6, "max_tokens": 800,
                "stream": False, "enable_thinking": False,
            }
            resp = await client.post(
                f"{api_cfg['api_base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_cfg['api_key']}",
                         "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            from app.llm_utils import extract_content
            return extract_content(resp.json()) or f"（{resident['name']} 无输出）"
    except Exception as e:
        return f"（{resident['name']} 执行失败: {e}）"


def _find_resident_by_role(db_path: Path, role: str) -> Optional[Dict]:
    from app import residents
    for r in residents.list_residents(db_path, "default", status="active"):
        if r["role"] == role:
            return r
    return None


def _find_resident_by_name(db_path: Path, name: str) -> Optional[Dict]:
    from app import residents
    for r in residents.list_residents(db_path, "default", status="active"):
        if r["name"].lower() == name.lower():
            return r
    return None


def _parse_json(text: str) -> Dict:
    import re
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def get_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) as c FROM swarm_tasks WHERE user_id=?", (user_id,)).fetchone()
    by_status = conn.execute(
        "SELECT status, COUNT(*) as c FROM swarm_tasks WHERE user_id=? GROUP BY status", (user_id,)
    ).fetchall()
    conn.close()
    return {
        "total": total["c"] if total else 0,
        "by_status": {r["status"]: r["c"] for r in by_status},
    }


# ============================================================
# Self-Goal Generation
# ============================================================

def create_self_goal(
    db_path: Path, user_id: str, title: str, description: str,
    reasoning: str = "", evidence: str = "",
    proposed_actions: Optional[List[Dict]] = None,
    risk_assessment: str = "", confidence: float = 0.5,
    category: str = "general", expires_in_days: int = 30,
) -> Dict:
    gid = str(uuid.uuid4())
    now = int(time.time())
    expires_at = now + expires_in_days * 86400
    row = {
        "id": gid, "user_id": user_id, "title": title, "description": description,
        "reasoning": reasoning, "evidence": evidence,
        "proposed_actions": json.dumps(proposed_actions or [], ensure_ascii=False),
        "risk_assessment": risk_assessment,
        "confidence": max(0.0, min(1.0, confidence)),
        "status": "proposed", "category": category, "expires_at": expires_at,
        "created_at": now, "updated_at": now, "approved_at": None, "completed_at": None,
    }
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO self_goals
           (id, user_id, title, description, reasoning, evidence, proposed_actions,
            risk_assessment, confidence, status, category, expires_at,
            created_at, updated_at, approved_at, completed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(row.values())
    )
    conn.commit()
    conn.close()
    row["proposed_actions"] = proposed_actions or []
    return row


def get_self_goal(db_path: Path, goal_id: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM self_goals WHERE id=?", (goal_id,)).fetchone()
    conn.close()
    if not r:
        return None
    d = dict(r)
    try:
        d["proposed_actions"] = json.loads(d.get("proposed_actions") or "[]")
    except Exception:
        d["proposed_actions"] = []
    return d


def list_self_goals(db_path: Path, user_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    if status:
        rows = conn.execute(
            "SELECT * FROM self_goals WHERE user_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
            (user_id, status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM self_goals WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["proposed_actions"] = json.loads(d.get("proposed_actions") or "[]")
        except Exception:
            d["proposed_actions"] = []
        out.append(d)
    return out


def approve_self_goal(db_path: Path, goal_id: str) -> Optional[Dict]:
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "UPDATE self_goals SET status='approved', approved_at=?, updated_at=? WHERE id=?",
        (now, now, goal_id)
    )
    conn.commit()
    conn.close()
    return get_self_goal(db_path, goal_id)


def reject_self_goal(db_path: Path, goal_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE self_goals SET status='rejected', updated_at=? WHERE id=?",
        (now, goal_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def complete_self_goal(db_path: Path, goal_id: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE self_goals SET status='completed', completed_at=?, updated_at=? WHERE id=?",
        (now, now, goal_id)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


async def generate_self_goals(
    db_path: Path, user_id: str = "default",
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
) -> List[Dict]:
    """AI observes recent activity and generates proactive goal proposals.
    Called by Life Loop periodically."""
    from app.llm_utils import extract_content

    # Gather context: recent memories, timeline, goals, inbox, patterns
    context_parts = []
    try:
        from app import memory_orchestrator
        mems = memory_orchestrator.list_memories(db_path, user_id=user_id, limit=10, min_importance=50)
        if mems:
            context_parts.append("最近记忆:\n" + "\n".join(f"- {m['content'][:80]}" for m in mems[:5]))
    except Exception:
        pass

    try:
        from app import cognitive_kernel
        goals = cognitive_kernel.get_active_goals(db_path, user_id)
        if goals:
            context_parts.append("当前目标:\n" + "\n".join(f"- {g.get('goal', '')[:60]}" for g in goals[:3]))
    except Exception:
        pass

    try:
        from app import inbox
        stats = inbox.get_stats(db_path, user_id)
        if stats.get("pending", 0) > 0:
            context_parts.append(f"Inbox 待处理: {stats['pending']} 条")
    except Exception:
        pass

    if not context_parts:
        return []

    context = "\n\n".join(context_parts)

    # Ask AI to identify opportunities/issues
    prompt = f"""你是 Cambium 的自主目标系统。基于以下上下文，识别 1-2 个值得主动行动的机会或问题。

【上下文】
{context}

【任务】
观察模式，发现用户可能没注意到但值得行动的事。例如:
- 发现用户的某个目标停滞了，建议推进
- 发现 Inbox 积压，建议整理
- 发现某个兴趣可以深入，建议研究
- 发现某个模式/趋势，提醒用户

输出 JSON:
```json
{{
  "goals": [
    {{
      "title": "简短标题",
      "description": "详细描述",
      "reasoning": "为什么这值得做",
      "evidence": "什么数据/模式触发了这个建议",
      "category": "optimization|opportunity|warning|maintenance|creative",
      "confidence": 0.6,
      "risk_assessment": "风险很低/中等/需要确认"
    }}
  ]
}}
```
如果没有值得提议的，输出 {{"goals": []}}。只输出 JSON。"""

    if not http_client_factory or not get_api_cfg:
        return []

    try:
        import httpx
        api_cfg = get_api_cfg()
        async with http_client_factory(timeout=30.0) as client:
            payload = {
                "model": api_cfg["api_model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5, "max_tokens": 600,
                "stream": False, "enable_thinking": False,
            }
            resp = await client.post(
                f"{api_cfg['api_base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_cfg['api_key']}",
                         "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            text = extract_content(resp.json())
        result = _parse_json(text)
        goals_data = result.get("goals", [])
        if not goals_data:
            return []

        created = []
        for g in goals_data:
            if not g.get("title"):
                continue
            sg = create_self_goal(
                db_path, user_id,
                title=g["title"],
                description=g.get("description", ""),
                reasoning=g.get("reasoning", ""),
                evidence=g.get("evidence", ""),
                risk_assessment=g.get("risk_assessment", ""),
                confidence=g.get("confidence", 0.5),
                category=g.get("category", "general"),
            )
            created.append(sg)
        return created
    except Exception as e:
        print(f"[self_goal] generation failed: {e}")
        return []


def get_self_goal_stats(db_path: Path, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) as c FROM self_goals WHERE user_id=?", (user_id,)).fetchone()
    by_status = conn.execute(
        "SELECT status, COUNT(*) as c FROM self_goals WHERE user_id=? GROUP BY status", (user_id,)
    ).fetchall()
    by_category = conn.execute(
        "SELECT category, COUNT(*) as c FROM self_goals WHERE user_id=? AND status='proposed' GROUP BY category", (user_id,)
    ).fetchall()
    conn.close()
    return {
        "total": total["c"] if total else 0,
        "by_status": {r["status"]: r["c"] for r in by_status},
        "proposed_by_category": {r["category"]: r["c"] for r in by_category},
        "pending_approval": sum(1 for r in by_status if r["status"] == "proposed"),
    }
