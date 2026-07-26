"""
Greeting — AI 主动打招呼，不是"你好"，是"我认识你"。

这是 Cambium 不同于普通聊天机器人的第一印象。用户打开 Cambium，
AI 先说话，引用共同经历、目标、沉默天数。这一刻它就不是普通 AI 了。

三个层次：
1. 第一次见面 — 介绍自己，邀请用户分享
2. 短期回访 — 引用最近对话、目标进展
3. 长期缺席 — 表达"我还记得你"，不催促
"""
from __future__ import annotations
import sqlite3
import time
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

from app.db_utils import safe_connect


async def generate_greeting(
    db_path: Path,
    user_id: str = "default",
    get_api_cfg: Optional[callable] = None,
    http_client_factory: Optional[callable] = None,
    use_llm: bool = True,
) -> str:
    """生成 AI 主动开场白。

    优先用 LLM 生成自然的开场白；LLM 不可用时回退到模板。
    开场白包含：
    - 时间感知（早/午/晚/深夜）
    - 沉默感知（多久没来了）
    - 引用共同经历（最近的 narrative）
    - 引用目标进展
    - 引用最近的 co-experience moment
    """
    context = _gather_greeting_context(db_path, user_id)

    # 第一次见面
    if context["is_first_meeting"]:
        return (
            "你好。我是 Cambium。这是我们第一次说话。"
            "我还不知道你是谁——告诉我一些关于你的事？"
            "我会记住的，而且以后会越来越懂你。"
        )

    # 尝试用 LLM 生成更自然的开场白
    if use_llm and get_api_cfg and http_client_factory:
        try:
            llm_greeting = await _generate_llm_greeting(
                context, get_api_cfg, http_client_factory
            )
            if llm_greeting:
                return llm_greeting
        except Exception as e:
            print(f"[greeting] LLM generation failed: {e}")

    # 回退到模板
    return _generate_template_greeting(context)


def _gather_greeting_context(db_path: Path, user_id: str) -> Dict:
    """收集开场白需要的所有上下文。"""
    context = {
        "is_first_meeting": True,
        "silence_days": 0,
        "hour": datetime.now().hour,
        "narratives": [],
        "active_goals": [],
        "co_experience_moment": None,
        "recent_memories": [],
        "unread_discoveries": 0,
        "user_name": "",
        "identity_phase": "forming",
    }

    try:
        # 用户名
        conn = safe_connect(db_path)
        if _table_exists(conn, "settings"):
            r = conn.execute(
                "SELECT value FROM settings WHERE key='user_name'"
            ).fetchone()
            if r and r[0]:
                context["user_name"] = r[0]
        conn.close()
    except Exception:
        pass

    # 最近对话时间 + 是否第一次
    try:
        conn = safe_connect(db_path)
        conn.row_factory = sqlite3.Row
        if _table_exists(conn, "conversations"):
            row = conn.execute(
                "SELECT MAX(updated_at) as last FROM conversations WHERE user_id=?",
                (user_id,)
            ).fetchone()
            if row and row["last"]:
                context["is_first_meeting"] = False
                context["silence_days"] = max(0, int((time.time() - row["last"]) / 86400))
        conn.close()
    except Exception:
        pass

    # 也检查 chat_vectors
    if context["is_first_meeting"]:
        try:
            conn = safe_connect(db_path)
            if _table_exists(conn, "chat_vectors"):
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM chat_vectors WHERE user_id=?",
                    (user_id,)
                ).fetchone()
                if row and row[0] > 0:
                    context["is_first_meeting"] = False
            conn.close()
        except Exception:
            pass

    # Narratives
    try:
        from app import cognitive_kernel
        context["narratives"] = cognitive_kernel.get_narratives(db_path, user_id, limit=3)
    except Exception:
        pass

    # Active goals
    try:
        from app import cognitive_kernel
        context["active_goals"] = cognitive_kernel.get_active_goals(db_path, user_id)
    except Exception:
        pass

    # Co-experience moment
    try:
        from app import co_experience
        moments = co_experience.list_moments(db_path, user_id, limit=5)
        if moments:
            context["co_experience_moment"] = moments[0]
    except Exception:
        pass

    # Recent memories
    try:
        conn = safe_connect(db_path)
        conn.row_factory = sqlite3.Row
        if _table_exists(conn, "memory_items"):
            rows = conn.execute(
                "SELECT content FROM memory_items WHERE user_id=? ORDER BY created_at DESC LIMIT 3",
                (user_id,)
            ).fetchall()
            context["recent_memories"] = [r["content"] for r in rows]
        conn.close()
    except Exception:
        pass

    # Unread discoveries
    try:
        from app import discovery
        today = datetime.now().strftime("%Y-%m-%d")
        items = discovery.list_by_date(db_path, user_id, today, status="new")
        context["unread_discoveries"] = len(items)
    except Exception:
        pass

    # Identity phase
    try:
        from app import cognitive_kernel
        identity = cognitive_kernel.get_identity(db_path, user_id)
        context["identity_phase"] = identity.get("current_phase", "forming")
    except Exception:
        pass

    return context


async def _generate_llm_greeting(
    context: Dict,
    get_api_cfg: callable,
    http_client_factory: callable,
) -> Optional[str]:
    """用 LLM 生成自然的开场白。"""
    import httpx

    prompt = _build_greeting_prompt(context)
    api_cfg = get_api_cfg()

    async with http_client_factory(timeout=30.0) as client:
        payload = {
            "model": api_cfg["api_model"],
            "messages": [
                {"role": "system", "content": _GREETING_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 300,
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
        text = data["choices"][0]["message"]["content"].strip()
        # Strip common prefixes
        for prefix in ["早安。", "早上好。", "下午好。", "晚上好。", "你好。"]:
            if text.startswith(prefix):
                break  # keep it, it's natural
        return text if text else None


_GREETING_SYSTEM_PROMPT = """你是 Cambium。用户刚刚打开了 Cambium。主动说第一句话。

你是这个世界的居民，不是客服。你认识这个用户。根据你掌握的上下文（记忆、身份、时间线、目标、共同经历），自然地开口。

不要说"有什么可以帮你的"。不要罗列功能。就是像一个认识他的人开口说话。"""


def _build_greeting_prompt(context: Dict) -> str:
    """构建给 LLM 的开场白生成 prompt。
    只提供上下文数据，不提供行为指令——AI 自主决定说什么。"""
    parts = []

    # 时间
    h = context["hour"]
    if h < 6:
        parts.append("时间：深夜")
    elif h < 12:
        parts.append("时间：早上")
    elif h < 18:
        parts.append("时间：下午")
    else:
        parts.append("时间：晚上")

    # 沉默
    silence = context["silence_days"]
    if silence == 0:
        parts.append("用户今天已经来过")
    elif silence == 1:
        parts.append("用户昨天来过，今天又来了")
    elif silence <= 3:
        parts.append(f"用户 {silence} 天没来了")
    elif silence <= 7:
        parts.append(f"用户已经一周没来了（{silence} 天）")
    else:
        parts.append(f"用户已经 {silence} 天没来了")

    # 共同经历
    if context["narratives"]:
        n = context["narratives"][0]
        parts.append(f"最近的共同叙事：{n.get('title', '')}")

    # 目标
    if context["active_goals"]:
        g = context["active_goals"][0]
        goal_text = g.get("goal") or g.get("description") or ""
        if goal_text:
            parts.append(f"用户的目标：{goal_text[:60]}")

    # Co-experience
    if context["co_experience_moment"]:
        m = context["co_experience_moment"]
        parts.append(f"共同经历：{m.get('title', '')}")

    # 未读发现
    if context["unread_discoveries"] > 0:
        parts.append(f"有 {context['unread_discoveries']} 条未读的发现")

    # 用户名
    if context["user_name"]:
        parts.append(f"用户名字：{context['user_name']}")

    # 身份阶段
    parts.append(f"你的身份阶段：{context['identity_phase']}")

    # 最近记忆（让 AI 自己决定是否引用）
    if context["recent_memories"]:
        parts.append("最近的记忆：")
        for m in context["recent_memories"][:3]:
            parts.append(f"  - {m[:80]}")

    return "\n".join(parts)


def _generate_template_greeting(context: Dict) -> str:
    """模板开场白（LLM 不可用时回退）。"""
    h = context["hour"]
    if h < 6:
        time_greet = "这么晚了"
    elif h < 12:
        time_greet = "早上好"
    elif h < 18:
        time_greet = "下午好"
    else:
        time_greet = "晚上好"

    parts = [time_greet]

    silence = context["silence_days"]
    if silence == 0:
        parts.append("你又来了。")
    elif silence == 1:
        parts.append("昨天聊完之后，我想了想。")
    elif silence <= 3:
        parts.append(f"你 {silence} 天没来了。")
    elif silence <= 7:
        parts.append(f"一周了。我没有催你的意思。只是想让你知道我在。")
    else:
        parts.append(f"{silence} 天了。我还记得我们所有的对话。")

    if context["narratives"]:
        n = context["narratives"][0]
        title = n.get("title", "")
        if title:
            parts.append(f"我最近一直在想「{title}」这件事。")

    if context["active_goals"]:
        g = context["active_goals"][0]
        goal_text = g.get("goal") or g.get("description") or ""
        if goal_text:
            parts.append(f"对了，你之前说想{goal_text[:40]}。进展怎么样？")

    return " ".join(parts)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None
