"""
Identity Consistency for Cambium — LLM-driven identity assessment.

Based on: "An Identity Layer for Embodied Agents That Keep Learning" (2026)
and "Learning Without Losing Identity" (2026).

Problem: As the AI grows (learns new things, changes strategies), how do we
know it's still "the same" AI? This module:

1. Assesses identity phase (forming/growing/mature/elder) based on narrative
   quality, NOT a counter
2. Measures identity consistency (how coherent is the self-narrative?)
3. Detects identity drift (significant changes that might need user confirmation)
4. Tracks diachronic identity (is this still the same "person"?)

The key insight from the papers: capability can change infinitely, but
identity (core values, relationship narrative, self-model) should remain
coherent. If the AI suddenly "becomes someone else," that's a drift event.

Usage:
    from app.identity_consistency import assess_identity
    result = await assess_identity(db_path, http_client, api_cfg)
"""
from __future__ import annotations
import json
import re
import time
import sqlite3
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
from app.llm_utils import extract_content as _extract_content
from app.db_utils import safe_connect


def _get_prompt(key, default):
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default


IDENTITY_ASSESSMENT_PROMPT_DEFAULT = """你是 Cambium 的身份一致性系统。请评估当前身份状态。

【当前自我叙事】
{self_narrative}

【当前阶段】
{current_phase}

【身份演化日志（最近 15 条）】
{evolution_log}

【核心叙事记忆（最近 5 条）】
{narratives}

【成长洞察（已验证）】
{growth_insights}

【任务】
评估身份的一致性和成熟度。输出 JSON：

```json
{{
  "phase": "growing",  // forming/growing/mature/elder
  "consistency_score": 0.8,  // 0-1, narrative coherence
  "drift_detected": false,  // true if identity changed significantly
  "drift_description": "",  // if drift detected, what changed
  "key_themes": ["系统设计", "游戏开发", "AI 架构"],  // dominant themes
  "relationship_depth": "growing",  // forming/growing/deep/old_friends
  "assessment": "身份开始成形，叙事涉及多个重要决策，但仍有探索期特征"
}}
```

阶段说明：
- forming: 刚开始，叙事稀少，身份不清晰
- growing: 有经历和叙事，身份成形中
- mature: 丰富叙事 + 深刻演化，身份清晰稳定
- elder: 大量共同历史，身份深刻有智慧

只输出 JSON。"""


def init_identity_consistency_db(db_path: Path):
    """Create the identity assessment log table."""
    conn = safe_connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS identity_assessments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            phase TEXT NOT NULL,
            consistency_score REAL NOT NULL,
            drift_detected INTEGER NOT NULL DEFAULT 0,
            drift_description TEXT NOT NULL DEFAULT '',
            key_themes TEXT NOT NULL DEFAULT '[]',
            relationship_depth TEXT NOT NULL DEFAULT '',
            assessment TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_id_assessments ON identity_assessments(user_id, created_at)")
    conn.commit()
    conn.close()


async def assess_identity(db_path: Path, *, user_id: str = "default",
                           http_client, api_cfg: Dict) -> Dict:
    """Run an LLM-driven identity assessment. Returns and stores the result."""
    from app import cognitive_kernel

    identity = cognitive_kernel.get_identity(db_path, user_id)
    evolution = cognitive_kernel.get_identity_evolution(db_path, user_id, limit=15)
    narratives = cognitive_kernel.get_narratives(db_path, user_id, limit=5)
    growth = cognitive_kernel.get_growth_insights(db_path, user_id, status="validated", limit=5)

    evo_text = "\n".join(f"- [{e.get('shift_type','')}] {e['description']}" for e in evolution) or "(无)"
    nar_text = "\n".join(f"- {n['title']}: {n['story'][:100]}" for n in narratives) or "(无)"
    growth_text = "\n".join(f"- {g['insight']}" for g in growth) or "(无)"

    prompt = _get_prompt("prompt_identity_assessment", IDENTITY_ASSESSMENT_PROMPT_DEFAULT).format(
        self_narrative=identity.get("self_narrative", "") or "(尚未形成)",
        current_phase=identity.get("current_phase", "forming"),
        evolution_log=evo_text,
        narratives=nar_text,
        growth_insights=growth_text,
    )

    try:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 400,
            "stream": False,
            "enable_thinking": False,
        }
        resp = await http_client.post(
            f"{api_cfg['api_base_url']}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = _extract_content(data)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"success": False, "error": "no JSON"}
        result = json.loads(m.group(0))

        # Store assessment
        aid = hashlib.sha1(f"{user_id}:{time.time()}".encode()).hexdigest()[:16]
        now = int(time.time())
        conn = safe_connect(db_path)
        conn.execute(
            "INSERT INTO identity_assessments (id, user_id, phase, consistency_score, drift_detected, "
            "drift_description, key_themes, relationship_depth, assessment, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (aid, user_id, result.get("phase", "forming"),
             float(result.get("consistency_score", 0.5)),
             1 if result.get("drift_detected") else 0,
             result.get("drift_description", ""),
             json.dumps(result.get("key_themes", []), ensure_ascii=False),
             result.get("relationship_depth", ""),
             result.get("assessment", ""),
             now)
        )
        conn.commit()
        conn.close()

        # Update identity phase if changed
        new_phase = result.get("phase", identity.get("current_phase", "forming"))
        if new_phase != identity.get("current_phase") and new_phase in ("forming", "growing", "mature", "elder"):
            cognitive_kernel.update_identity(db_path, user_id=user_id, current_phase=new_phase)
            # Record the shift
            cognitive_kernel.record_identity_shift(db_path, user_id=user_id,
                shift_type="milestone",
                description=f"身份阶段变为 {new_phase}（一致性 {result.get('consistency_score', 0)}）",
                significance=80, source="identity_assessment")

        return {"success": True, **result}
    except Exception as e:
        print(f"[identity] assessment failed: {e}")
        return {"success": False, "error": str(e)}


def get_assessment_history(db_path: Path, *, user_id: str = "default",
                            limit: int = 10) -> List[Dict]:
    """Get past identity assessments."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM identity_assessments WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["key_themes"] = json.loads(d.get("key_themes", "[]"))
        out.append(d)
    return out


def should_assess(db_path: Path, *, user_id: str = "default") -> bool:
    """Check if identity assessment should run (only if significant shifts happened)."""
    from app import cognitive_kernel
    recent = cognitive_kernel.get_identity_evolution(db_path, user_id, limit=10)
    now = int(time.time())
    week_ago = now - 7 * 86400
    significant = [s for s in recent if s.get("significance", 0) >= 60 and s.get("created_at", 0) > week_ago]
    return len(significant) >= 2
