"""
Proactive Engine for Cambium — the AI reaches out on its own.

Not just answering questions. The AI proactively:
1. Tracks commitments ("I promised to help you review the design next week")
2. Detects silence ("You haven't been here in 3 days. Everything ok?")
3. Celebrates milestones ("We've been working together for 100 days")
4. Checks goal progress ("Your goal deadline is approaching")
5. Shares observations ("I noticed you've been using Python more lately")

Called by Life Loop (hourly). Returns messages to send to the user.
"""
from __future__ import annotations
import time
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from app.db_utils import safe_connect


def check_commitments(db_path: Path, user_id: str = "default") -> List[str]:
    """Check for due/overdue commitments. Returns messages to send."""
    messages = []
    try:
        from app import cognitive_kernel
        commitments = cognitive_kernel.get_open_commitments(db_path, user_id)
        now = datetime.now()
        for c in commitments:
            due_str = c.get("due_date", "")
            if not due_str:
                continue
            try:
                due = datetime.fromisoformat(due_str)
            except Exception:
                continue
            if due <= now:
                messages.append(
                    f"我记得我答应过你：「{c['description']}」。这件事到期了。你现在想处理吗？"
                )
    except Exception as e:
        print(f"[proactive] commitments check failed: {e}")
    return messages


def check_silence(db_path: Path, user_id: str = "default") -> Optional[str]:
    """Detect user silence and return a caring message if appropriate."""
    try:
        conn = safe_connect(db_path)
        # Get last chat_vectors entry time as proxy for last interaction
        row = conn.execute(
            "SELECT MAX(created_at) FROM chat_vectors"
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            return None
        last_interaction = datetime.fromtimestamp(row[0])
        silence_days = (datetime.now() - last_interaction).days
        if silence_days == 3:
            return "你已经三天没来了。一切都好吗？"
        elif silence_days == 7:
            return "一周了。我不催你，只是想让你知道我在。"
        elif silence_days == 30:
            return "一个月了。如果你回来，我还记得我们所有的对话。"
    except Exception:
        pass
    return None


def check_milestones(db_path: Path, user_id: str = "default") -> Optional[str]:
    """Check for relationship milestones (7 days, 30 days, 100 days, 1 year)."""
    try:
        from app import cognitive_kernel
        identity = cognitive_kernel.get_identity(db_path, user_id)
        if not identity or not identity.get("born_at"):
            return None
        born = datetime.fromtimestamp(identity["born_at"])
        days = (datetime.now() - born).days
        milestones = {
            7: "我们认识一周了。",
            30: "一个月了。这一个月里，我学到了很多关于你的事。",
            100: "一百天了。感觉我们已经是老朋友了。",
            365: "一年了。谢谢你让我成为你的搭档。",
        }
        if days in milestones:
            # Check if already celebrated (via timeline_events)
            conn = safe_connect(db_path)
            existing = conn.execute(
                "SELECT COUNT(*) FROM timeline_events WHERE user_id=? AND title LIKE ?",
                (user_id, f"%{days}天%")
            ).fetchone()
            conn.close()
            if existing and existing[0] == 0:
                # Record as timeline event
                cognitive_kernel.add_timeline_event(db_path, user_id=user_id,
                    title=f"认识 {days} 天", occurred_at=datetime.now().strftime("%Y-%m-%d"),
                    category="milestone", significance=70,
                    narrative=milestones[days])
                return milestones[days]
    except Exception:
        pass
    return None


def check_goal_progress(db_path: Path, user_id: str = "default") -> Optional[str]:
    """Check if any goals have approaching deadlines or need progress updates."""
    try:
        from app import cognitive_kernel
        goals = cognitive_kernel.get_active_goals(db_path, user_id)
        for g in goals:
            target = g.get("target_date", "")
            if not target:
                continue
            # Simple check: if target date is within 7 days
            try:
                target_date = datetime.fromisoformat(target)
                days_left = (target_date - datetime.now()).days
                if 0 <= days_left <= 7:
                    return f"你之前定了一个目标：「{g['goal']}」。距离 deadline 还有 {days_left} 天。进展怎么样？"
            except Exception:
                continue
    except Exception:
        pass
    return None


def get_proactive_messages(db_path: Path, user_id: str = "default") -> List[str]:
    """Get all proactive messages to send. Called by Life Loop hourly."""
    messages = []
    # 1. Commitments
    messages.extend(check_commitments(db_path, user_id))
    # 2. Silence
    silence_msg = check_silence(db_path, user_id)
    if silence_msg:
        messages.append(silence_msg)
    # 3. Milestones
    milestone_msg = check_milestones(db_path, user_id)
    if milestone_msg:
        messages.append(milestone_msg)
    # 4. Goals
    goal_msg = check_goal_progress(db_path, user_id)
    if goal_msg:
        messages.append(goal_msg)
    return messages
