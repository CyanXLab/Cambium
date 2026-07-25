from __future__ import annotations
from app.db_utils import safe_connect


def _get_prompt(key, default):
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default
"""
Meta-cognition subsystem for CyanX AI.

After generating a response, the AI performs a self-check:
1. Am I confident in this answer?
2. What's my evidence?
3. Are there contradictions with known facts?
4. Should I search for more info?
5. Should I ask the user for clarification?

This is NOT chain-of-thought (which happens before/during generation).
It's a post-generation self-check that can trigger corrections.

Implementation:
- After the main response is generated, a separate (smaller, cheaper) LLM call
  evaluates the response
- If confidence is low or contradictions found, append a caveat or trigger
  a follow-up tool call
- Results are stored for the dashboard

Self-contained module. main.py calls evaluate_response() after chat_stream
completes (async, doesn't block the response).
"""
import json
import re
import sqlite3
import time
import hashlib
from typing import Dict, Optional, List
from pathlib import Path


META_COG_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_cognition_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    conversation_id TEXT,
    user_query TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    has_contradiction INTEGER NOT NULL DEFAULT 0,
    needs_clarification INTEGER NOT NULL DEFAULT 0,
    needs_search INTEGER NOT NULL DEFAULT 0,
    self_check TEXT NOT NULL DEFAULT '',
    correction TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metacog_user ON meta_cognition_logs(user_id, created_at);
"""


def init_meta_cog_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(META_COG_SCHEMA)
    conn.commit()
    conn.close()


SELF_CHECK_PROMPT = """你是 CyanX AI 的元认知系统。对刚才的 AI 回复进行自检。

【用户问题】
{user_query}

【AI 回复】
{ai_response}

【已知相关记忆】
{relevant_memories}

【任务】
评估这个回复的质量。检查：
1. confidence (0.0-1.0): 对回复的准确性和完整性的信心
2. has_contradiction (true/false): 回复是否与已知记忆矛盾
3. needs_clarification (true/false): 是否需要向用户澄清问题
4. needs_search (true/false): 是否需要联网搜索验证
5. self_check: 一句话自检结论
6. correction: 如果发现问题，给出修正建议（无问题则留空）

输出 JSON：
```json
{{
  "confidence": 0.85,
  "has_contradiction": false,
  "needs_clarification": false,
  "needs_search": false,
  "self_check": "回复准确，覆盖了用户问题",
  "correction": ""
}}
```

只输出 JSON。"""


async def evaluate_response(db_path: Path, *, user_id: str = "default",
                              conversation_id: Optional[str], user_query: str,
                              ai_response: str, relevant_memories: str,
                              http_client, api_cfg: Dict) -> Dict:
    """Run meta-cognition self-check on a response. Returns evaluation result.
    Stores the log in meta_cognition_logs table."""
    if len(ai_response) < 20:
        return {"confidence": 0.9, "skipped": True, "reason": "response too short"}
    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": _get_prompt("prompt_meta_cognition", SELF_CHECK_PROMPT_DEFAULT).format(
                user_query=user_query[:500],
                ai_response=ai_response[:2000],
                relevant_memories=relevant_memories[:1000] or "(无)",
            )}],
            "temperature": 0.2,
            "max_tokens": 300,
            "stream": False,
            "enable_thinking": False,
        }
        resp = await http_client.post(
            f"{api_cfg['api_base_url']}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not m:
            return {"confidence": 0.7, "skipped": True, "reason": "no JSON"}
        try:
            result = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"confidence": 0.7, "skipped": True, "reason": "invalid JSON"}

        # Store log
        log_id = hashlib.sha1(f"{user_id}:{time.time()}".encode()).hexdigest()[:16]
        now = int(time.time())
        conn = safe_connect(db_path)
        conn.execute(
            "INSERT INTO meta_cognition_logs (id, user_id, conversation_id, user_query, ai_response, "
            "confidence, has_contradiction, needs_clarification, needs_search, self_check, correction, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (log_id, user_id, conversation_id, user_query[:500], ai_response[:1000],
             float(result.get("confidence", 0.7)),
             1 if result.get("has_contradiction") else 0,
             1 if result.get("needs_clarification") else 0,
             1 if result.get("needs_search") else 0,
             result.get("self_check", ""),
             result.get("correction", ""),
             now)
        )
        conn.commit()
        conn.close()
        return result
    except Exception as e:
        print(f"[meta_cog] evaluate failed: {e}")
        return {"confidence": 0.7, "skipped": True, "error": str(e)}


def list_logs(db_path: Path, *, user_id: str = "default", limit: int = 20) -> List[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM meta_cognition_logs WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats(db_path: Path, *, user_id: str = "default") -> Dict:
    conn = safe_connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM meta_cognition_logs WHERE user_id=?", (user_id,)).fetchone()[0]
    avg_conf = conn.execute(
        "SELECT AVG(confidence) FROM meta_cognition_logs WHERE user_id=?", (user_id,)
    ).fetchone()[0] or 0.0
    contradictions = conn.execute(
        "SELECT COUNT(*) FROM meta_cognition_logs WHERE user_id=? AND has_contradiction=1",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "total_evaluations": total,
        "avg_confidence": round(avg_conf, 3),
        "contradictions_found": contradictions,
    }
