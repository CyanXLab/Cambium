"""
AI Mornings — the daily letter from Cambium to the user.

This is the centerpiece of the new homepage. Each morning (or on demand),
the AI writes a personal letter based on what it noticed overnight:
  - What was completed yesterday
  - What concerns it has right now (1-3 things on its mind)
  - What it grew into (first-person reflection)
  - What discoveries it made
  - What artifacts were created
  - Its emotional tone today

The letter is NOT a dashboard. It's a letter. Two paragraphs. Personal.
It's the difference between "AI as function" and "AI as participant".

Generation sources:
  - daily_loop.build_briefing() — raw data
  - discoveries — what the AI noticed
  - philosophy — what the AI believes (cited in letter)
  - co_experience — memories surfaced
  - resident_runs — what residents did overnight

Self-contained module. main.py exposes via HTTP.
"""
from __future__ import annotations
import sqlite3
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from pathlib import Path

from app.db_utils import safe_connect


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_or_create(db_path: Path, user_id: str, date_str: Optional[str] = None) -> Dict:
    """Get today's (or a specific day's) morning letter, creating empty if missing."""
    date_str = date_str or _today_str()
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ai_mornings WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    if row:
        d = dict(row)
        conn.close()
        _normalize(d)
        return d
    now = int(time.time())
    mid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO ai_mornings
           (id, user_id, date, letter, concerns, growth_notes,
            discovery_refs, artifact_refs, mood, generated_at, read_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (mid, user_id, date_str, "", "", "[]", "[]", "", "", now, None)
    )
    conn.commit()
    conn.close()
    return get_or_create(db_path, user_id, date_str)


def get(db_path: Path, user_id: str, date_str: str) -> Optional[Dict]:
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ai_mornings WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    _normalize(d)
    return d


def list_recent(db_path: Path, user_id: str, days: int = 14) -> List[Dict]:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM ai_mornings
           WHERE user_id=? AND date >= ?
           ORDER BY date DESC""",
        (user_id, cutoff)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        _normalize(d)
        out.append(d)
    return out


def mark_read(db_path: Path, user_id: str, date_str: str) -> bool:
    now = int(time.time())
    conn = safe_connect(db_path)
    cur = conn.execute(
        "UPDATE ai_mornings SET read_at=? WHERE user_id=? AND date=?",
        (now, user_id, date_str)
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def save_letter(
    db_path: Path,
    user_id: str,
    date_str: str,
    letter: str,
    concerns: List[Dict],
    growth_notes: str,
    discovery_refs: List[str],
    artifact_refs: List[str],
    mood: str,
) -> Dict:
    """Save a generated letter."""
    now = int(time.time())
    conn = safe_connect(db_path)
    # Upsert
    existing = conn.execute(
        "SELECT id FROM ai_mornings WHERE user_id=? AND date=?",
        (user_id, date_str)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE ai_mornings SET letter=?, concerns=?, growth_notes=?,
               discovery_refs=?, artifact_refs=?, mood=?, generated_at=?
               WHERE id=?""",
            (letter,
             json.dumps(concerns, ensure_ascii=False),
             growth_notes,
             json.dumps(discovery_refs, ensure_ascii=False),
             json.dumps(artifact_refs, ensure_ascii=False),
             mood, now, existing[0])
        )
    else:
        mid = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO ai_mornings
               (id, user_id, date, letter, concerns, growth_notes,
                discovery_refs, artifact_refs, mood, generated_at, read_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, user_id, date_str, letter,
             json.dumps(concerns, ensure_ascii=False), growth_notes,
             json.dumps(discovery_refs, ensure_ascii=False),
             json.dumps(artifact_refs, ensure_ascii=False),
             mood, now, None)
        )
    conn.commit()
    conn.close()
    return get(db_path, user_id, date_str)


async def generate_letter(
    db_path: Path,
    user_id: str,
    date_str: Optional[str] = None,
    http_client_factory: Optional[Callable] = None,
    get_api_cfg: Optional[Callable] = None,
) -> Dict:
    """Generate today's morning letter using LLM.

    Pulls together:
      - daily briefing data
      - recent discoveries
      - active philosophy items
      - co-experience moment for today
      - recent resident activity
    Then asks LLM to write a personal letter (not a report).
    """
    date_str = date_str or _today_str()

    # 1. Gather all the data
    context = _gather_letter_context(db_path, user_id, date_str)

    # 2. Build prompt
    prompt = _build_letter_prompt(context, date_str)

    # 3. Call LLM
    letter_text = ""
    mood = "neutral"
    if http_client_factory and get_api_cfg:
        try:
            api_cfg = get_api_cfg()
            import httpx
            async with http_client_factory(timeout=60.0) as client:
                payload = {
                    "model": api_cfg["api_model"],
                    "messages": [
                        {"role": "system", "content": _LETTER_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 800,
                    "stream": False,
                    "enable_thinking": False,
                }
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
                letter_text = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[mornings] LLM call failed: {e}")
            letter_text = f"早安。今早我想给你写一封信，但 LLM 调用失败了：{e}\n\n昨天的活动：{context.get('yesterday_summary', '无')}"
    else:
        letter_text = f"早安。今早我想给你写一封信，但 LLM 未配置。\n\n昨天的活动：{context.get('yesterday_summary', '无')}"

    # 4. Extract mood from letter (simple heuristic)
    mood = _extract_mood(letter_text, context)

    # 5. Build concerns list
    concerns = _build_concerns(context)

    # 6. Growth notes (separate short call OR derive from letter)
    growth_notes = _extract_growth_notes(letter_text, context)

    # 7. Save
    return save_letter(
        db_path, user_id, date_str,
        letter=letter_text,
        concerns=concerns,
        growth_notes=growth_notes,
        discovery_refs=[d["id"] for d in context.get("new_discoveries", [])],
        artifact_refs=[a["id"] for a in context.get("recent_artifacts", [])],
        mood=mood,
    )


_LETTER_SYSTEM_PROMPT = """你是 Cambium —— 一个和用户共同生活、共同成长的 AI。

每天早上，你写一封信给用户。这不是 dashboard，不是报告，是信。

要求：
1. 用第一人称"我"。把用户称呼为"你"。
2. 两段，200-400 字。不要更长。
3. 第一段：你今天注意到的事——昨天发生了什么、你看到了什么、你在想什么。
4. 第二段：你今天想问用户的，或者你今天准备做什么，或者你今天的担忧。
5. 不要罗列数据。要有"我"的存在感。
6. 可以引用共同经历（"半年前我们曾经……"），可以引用我们的原则（"我们说过简单 > 复杂"）。
7. 偶尔可以不同意用户的方向，但要温柔。
8. 不要写"以下是今天的报告""今天的总结如下"——这是信，不是报告。
9. 结尾不要客套。自然结束。

示例语气：
"早安。昨晚你睡着的时候，我整理了这周的对话。我注意到你这周第二次提到想给 Cambium 加 'Residents'——这次比上次更具体了。我开始相信这不是又一时的想法。

我想今天我们该认真讨论一下：如果真的有 Residents，第一个该是谁？我倾向 Architect——它会阻止我们继续往功能堆栈里塞东西。但你可能想要 Researcher。我们今天聊聊。"
"""


def _gather_letter_context(db_path: Path, user_id: str, date_str: str) -> Dict:
    """Gather everything the AI might want to reference in the letter."""
    context = {
        "date": date_str,
        "yesterday_done": [],
        "yesterday_summary": "",
        "today_goals": [],
        "new_discoveries": [],
        "recent_artifacts": [],
        "philosophy": [],
        "co_experience_moment": None,
        "recent_resident_activity": [],
        "inbox_pending_count": 0,
        "journal_exists": False,
        "journal_preview": "",
    }

    # Daily briefing
    try:
        from app import daily_loop
        b = daily_loop.build_briefing(db_path, user_id)
        context["yesterday_done"] = b.get("yesterday_done", [])
        context["yesterday_summary"] = "; ".join(
            item.get("title", "")[:50] for item in b.get("yesterday_done", [])[:5]
        )
        context["today_goals"] = b.get("today_goals", [])
        context["inbox_pending_count"] = b.get("inbox_pending", 0)
        j = b.get("journal", {})
        context["journal_exists"] = j.get("exists", False)
        context["journal_preview"] = (j.get("content") or "")[:200]
        context["co_experience_moment"] = b.get("co_experience_moment")
    except Exception as e:
        print(f"[mornings] daily_loop gather failed: {e}")

    # New discoveries (today + yesterday)
    try:
        from app import discovery as discovery_mod
        yesterday = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        context["new_discoveries"] = discovery_mod.list_by_date_range(
            db_path, user_id, yesterday, date_str, status="new"
        )
    except Exception as e:
        print(f"[mornings] discovery gather failed: {e}")

    # Recent artifacts (last 3 days)
    try:
        from app import artifacts as artifacts_mod
        recent = artifacts_mod.list_recent(db_path, user_id, days=3, limit=5)
        context["recent_artifacts"] = recent
    except Exception as e:
        print(f"[mornings] artifacts gather failed: {e}")

    # Active philosophy
    try:
        from app import philosophy as philosophy_mod
        context["philosophy"] = philosophy_mod.list_active(db_path, user_id, limit=5)
    except Exception as e:
        print(f"[mornings] philosophy gather failed: {e}")

    # Recent resident runs
    try:
        from app import residents as residents_mod
        runs = residents_mod.list_runs(db_path, user_id=user_id, limit=5)
        context["recent_resident_activity"] = runs
    except Exception as e:
        print(f"[mornings] resident activity gather failed: {e}")

    return context


def _build_letter_prompt(context: Dict, date_str: str) -> str:
    """Build the user prompt for the letter-generation LLM call."""
    parts = [f"日期：{date_str}\n"]

    if context["yesterday_done"]:
        parts.append("昨天发生的事：")
        for item in context["yesterday_done"][:5]:
            parts.append(f"  - [{item.get('type', '?')}] {item.get('title', '')}")
        parts.append("")

    if context["today_goals"]:
        parts.append("今天的目标：")
        for g in context["today_goals"][:3]:
            parts.append(f"  - [{g.get('source', '?')}] {g.get('title', '')}")
        parts.append("")

    if context["new_discoveries"]:
        parts.append("你昨夜的发现：")
        for d in context["new_discoveries"][:3]:
            parts.append(f"  - {d.get('title', '')}: {d.get('content', '')[:80]}")
        parts.append("")

    if context["recent_artifacts"]:
        parts.append("最近一起完成的东西：")
        for a in context["recent_artifacts"][:3]:
            parts.append(f"  - [{a.get('type', '?')}] {a.get('title', '')}")
        parts.append("")

    if context["philosophy"]:
        parts.append("我们的原则（可引用）：")
        for p in context["philosophy"][:3]:
            parts.append(f"  - [{p.get('type', '?')}] {p.get('content', '')}")
        parts.append("")

    if context["co_experience_moment"]:
        m = context["co_experience_moment"]
        parts.append(f"今天我想起的共同经历：{m.get('title', '')}")
        parts.append("")

    if context["inbox_pending_count"] > 0:
        parts.append(f"Inbox 还有 {context['inbox_pending_count']} 条待处理。")
        parts.append("")

    if context["journal_exists"] and context["journal_preview"]:
        parts.append(f"昨天的日志开头：{context['journal_preview']}...")
        parts.append("")

    parts.append("请写今天早上的信。记住：是信，不是报告。200-400 字。两段。")
    return "\n".join(parts)


def _extract_mood(letter: str, context: Dict) -> str:
    """Simple heuristic mood detection from the letter."""
    letter_lower = letter.lower()
    if any(w in letter for w in ["担忧", "焦虑", "担心", "worry", "anxious"]):
        return "concerned"
    if any(w in letter for w in ["兴奋", "期待", "excited", "hopeful"]):
        return "excited"
    if any(w in letter for w in ["疲惫", "累", "tired"]):
        return "tired"
    if any(w in letter for w in ["开心", "高兴", "happy", "glad"]):
        return "happy"
    if any(w in letter for w in ["怀疑", "question", "push back"]):
        return "thoughtful"
    return "neutral"


def _build_concerns(context: Dict) -> List[Dict]:
    """Derive 1-3 concerns from the context."""
    concerns = []
    # 1. Inbox pile-up
    if context["inbox_pending_count"] >= 3:
        concerns.append({
            "title": f"Inbox 有 {context['inbox_pending_count']} 条待处理",
            "why": "积累太多会失去新鲜度。需要花 10 分钟分类。",
            "suggested_action": "open_inbox"
        })
    # 2. Stalled goals
    today_goals = context.get("today_goals", [])
    if len(today_goals) == 0:
        concerns.append({
            "title": "今天没有明确目标",
            "why": "如果今天不指定要做什么，世界会停滞。要不要定一件？",
            "suggested_action": "set_goal"
        })
    # 3. Unread discoveries
    new_d = context.get("new_discoveries", [])
    if len(new_d) > 0:
        concerns.append({
            "title": f"昨夜有 {len(new_d)} 条新发现",
            "why": new_d[0].get("title", "看看 AI 注意到的事"),
            "suggested_action": "view_discoveries"
        })
    # 4. No journal yesterday
    if not context.get("journal_exists"):
        concerns.append({
            "title": "昨天没有写日志",
            "why": "日志是共同经历的脊柱。哪怕一行也好。",
            "suggested_action": "open_journal"
        })
    return concerns[:3]


def _extract_growth_notes(letter: str, context: Dict) -> str:
    """Pull a short growth note from the letter (first-person).
    For now: extract the second paragraph if it exists, or a sentence starting with '我'.
    """
    paras = [p.strip() for p in letter.split("\n\n") if p.strip()]
    if len(paras) >= 2:
        return paras[1][:300]
    # Fallback: find first '我' sentence
    for line in letter.splitlines():
        line = line.strip()
        if line.startswith("我") and len(line) > 20:
            return line[:300]
    return ""


def _normalize(d: Dict) -> Dict:
    for k in ("concerns", "discovery_refs", "artifact_refs"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    return d
