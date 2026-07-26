"""
Pushback — the AI's ability to disagree, and to surface memories mid-conversation.

Two responsibilities:

1. PUSHBACK: When the user says something that contradicts a stored belief,
   principle, or past statement, the AI should push back — citing evidence.
   This is the "ENTP dialogue" the user wants. AI is not a yes-machine.

2. MEMORY SURFACING: When the user says something related to a past
   co-experience moment, the AI should occasionally say "this reminds me
   of when we..." and link to that moment. Not every time — only when
   genuinely relevant.

Both happen during chat. They are injected as system-prompt context,
not as separate messages. The AI decides whether to use them.

Self-contained module. main.py wires into the chat stream.
"""
from __future__ import annotations
import sqlite3
import json
import time
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


# ============================================================
# Pushback — detect contradictions with stored beliefs/principles
# ============================================================

PUSHBACK_SYSTEM_PROMPT = """

【我们的原则与信念】
以下是你们共同形成的原则和信念。AI 自主决定如何使用它们——可以引用、可以参考、也可以在认为合适时提出不同意见。这不是规则，是你们共同的历史。

{philosophy_items}
"""


def gather_pushback_context(db_path: Path, user_id: str = "default") -> str:
    """Gather active philosophy items formatted for injection into system prompt."""
    try:
        from app import philosophy as philosophy_mod
        items = philosophy_mod.list_active(db_path, user_id, limit=20)
        if not items:
            return "（暂无明确原则。鼓励用户通过 Philosophy 设置添加。）"
        lines = []
        for p in items:
            type_label = {
                "value": "价值观", "belief": "信念",
                "principle": "原则", "anti_goal": "反目标"
            }.get(p["type"], p["type"])
            confidence_marker = " (强)" if p.get("confidence", 0.8) >= 0.85 else ""
            lines.append(f"- [{type_label}{confidence_marker}] {p['content']}")
            if p.get("rationale"):
                lines.append(f"    理由：{p['rationale']}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[pushback] gather failed: {e}")
        return "（加载原则失败）"


def build_pushback_system_prompt(db_path: Path, user_id: str = "default") -> str:
    """Build the pushback section to append to the chat system prompt."""
    philosophy_text = gather_pushback_context(db_path, user_id)
    return PUSHBACK_SYSTEM_PROMPT.format(philosophy_items=philosophy_text)


# ============================================================
# Memory surfacing — find related co-experience moments
# ============================================================

def find_related_moments(
    db_path: Path,
    user_id: str,
    user_message: str,
    limit: int = 3,
) -> List[Dict]:
    """Find co-experience moments that might be related to what the user just said.

    Uses keyword matching + recency + emotional_weight to rank.
    Returns 0-3 moments, or empty list if nothing relevant.

    The AI then decides whether to surface one ("this reminds me of when we...").
    """
    if not user_message or len(user_message) < 10:
        return []
    try:
        from app import co_experience as co_exp_mod
        all_moments = co_exp_mod.list_moments(db_path, user_id, limit=100)
        if not all_moments:
            return []
        # Extract keywords from user message (simple: split by spaces/punctuation)
        import re
        words = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', user_message.lower()))
        if not words:
            return []
        scored = []
        for m in all_moments:
            text = (m.get("title", "") + " " + m.get("story", "")).lower()
            # Count overlapping keywords
            moment_words = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', text))
            overlap = len(words & moment_words)
            if overlap == 0:
                continue
            # Score: overlap * 10 + emotional_weight * 5 - recency_penalty
            age_days = (time.time() - m.get("occurred_at", 0)) / 86400
            recency_penalty = min(age_days / 365, 1.0)  # cap at 1
            score = overlap * 10 + m.get("emotional_weight", 0.5) * 5 - recency_penalty * 2
            # Don't surface very recently surfaced moments
            if m.get("last_surfaced_at") and (time.time() - m["last_surfaced_at"]) < 86400:
                score -= 5
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Only return if top score is meaningfully high
        if not scored or scored[0][0] < 3:
            return []
        out = [m for _, m in scored[:limit]]
        # Mark them as surfaced (counts toward surfaced_count)
        for m in out:
            try:
                co_exp_mod.mark_surfaced(db_path, m["id"])
            except Exception:
                pass
        return out
    except Exception as e:
        print(f"[pushback] find_related_moments failed: {e}")
        return []


def build_memory_surface_context(moments: List[Dict]) -> str:
    """Format surfaced moments for injection into chat context.
    Only provides data — AI decides whether and how to use it."""
    if not moments:
        return ""
    lines = ["\n\n【相关共同经历】"]
    for m in moments[:2]:
        age_days = int((time.time() - m.get("occurred_at", 0)) / 86400)
        age_str = f"{age_days} 天前" if age_days > 0 else "今天"
        lines.append(f"- {age_str}：{m.get('title', '')}")
        if m.get("story"):
            lines.append(f"  故事：{m['story'][:150]}")
    return "\n".join(lines)


# ============================================================
# Evolution logging — when user overrides a principle
# ============================================================

def log_principle_override(
    db_path: Path,
    user_id: str,
    principle_id: str,
    principle_content: str,
    user_statement: str,
):
    """When the user explicitly chooses to violate a principle, log it as an evolution event."""
    try:
        from app import evolution as evolution_mod
        evolution_mod.create_event(
            db_path, user_id,
            type_="belief_change",
            from_state=principle_content,
            to_state="(用户推翻)",
            evidence=f"用户说：{user_statement[:200]}",
            evidence_refs={"philosophy_id": principle_id},
            confidence=0.7,
            observed_by="ai",
        )
    except Exception as e:
        print(f"[pushback] log_principle_override failed: {e}")


# ============================================================
# Detect pushback opportunities (lightweight, pre-LLM)
# ============================================================

def detect_pushback_opportunities(
    db_path: Path,
    user_id: str,
    user_message: str,
) -> Dict:
    """Pre-LLM detection: scan user message for keywords that contradict principles.

    Returns dict with:
      - related_moments: list of co-experience moments to surface
      - pushback_context: string to inject into system prompt
    """
    related = find_related_moments(db_path, user_id, user_message, limit=2)
    return {
        "related_moments": related,
        "memory_surface_context": build_memory_surface_context(related),
        # Pushback context is gathered separately (heavier)
    }
