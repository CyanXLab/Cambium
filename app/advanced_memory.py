from __future__ import annotations
"""
Advanced memory subsystem for CyanX AI.

Provides:
- Emotion recognition from text (rule-based, lightweight, no external API)
- User profile management (personality, interests, preferences, relationships)
- Emotion state tracking (recent emotions curve per user)
- Proactive memory recall (find memories with temporal cues for "I remember" feature)

All data is stored in SQLite. Designed to support multiple users (user_id field)
but defaults to 'default' for single-user deployments.

This module is self-contained: no FastAPI imports, so it can be tested in isolation.
main.py wires it up to HTTP endpoints and injects results into the system prompt.
"""
import json
import re
import sqlite3
import time
from app.db_utils import safe_connect


def _get_prompt(key, default):
    try:
        from app.main import get_prompt
        return get_prompt(key, default)
    except Exception:
        return default
import hashlib
from typing import List, Dict, Optional, Tuple
from pathlib import Path


# ============================================================
# Emotion recognition (rule-based, lightweight)
# ============================================================
# Each emotion has a list of trigger patterns (regex) and weight.
# When a text matches multiple patterns, the highest-weighted emotion wins.
# This is intentionally simple — for production-grade emotion detection,
# plug in a fine-tuned classifier via the embedding API config.

EMOTION_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    "joy": [
        (r"哈哈|嘿嘿|嘻嘻|😄|😊|😍|❤️|开心|高兴|快乐|棒极了|太好了|完美|爽|赞|厉害|牛逼|nb|666", 1.0),
        (r"谢谢|感谢|多谢|thx|thanks|thank you", 0.6),
        (r"完成了|成功了|搞定了|做到了|终于", 0.8),
    ],
    "excitement": [
        (r"哇|天哪|卧槽|我去|卧擦|牛逼|amazing|awesome|incredible|太牛|太强|震撼", 1.0),
        (r"期待|激动|兴奋|等不及|迫不及待", 0.9),
    ],
    "anxiety": [
        (r"担心|害怕|焦虑|紧张|不安|压力|stress|anxious|worry|nervous", 1.0),
        (r"怎么办|怎么办啊|完蛋了|糟了|麻烦了|出事了", 0.9),
        (r"会不会|是否能|能不能|行不行", 0.4),
    ],
    "sadness": [
        (r"难过|伤心|悲伤|失落|郁闷|沮丧|emo|depressed|sad|unhappy", 1.0),
        (r"失败了|没成功|搞砸了|完不成|做不到|放弃了", 0.8),
        (r"😢|😭|💔|😔", 1.0),
    ],
    "anger": [
        (r"气死|愤怒|生气|讨厌|烦死|恶心|垃圾|shit|fuck|damn|wtf", 1.0),
        (r"😡|🤬|😤|💪", 0.7),
        (r"凭什么|为什么总是|又来了|真烦|受不了", 0.8),
    ],
    "frustration": [
        (r"唉|哎|无语|服了|醉了|累觉不爱|心累|无奈", 0.9),
        (r"为什么|怎么搞的|搞什么|什么鬼", 0.6),
        (r"不行|不对|不是这样|搞错了|又错了", 0.7),
    ],
    "sarcasm": [
        (r"真是不错呢|好棒哦|呵呵|呵|厉害厉害|6666|牛逼牛逼", 0.8),
        (r"才怪|你想多了|想得美|做梦|不可能的事", 0.7),
    ],
    "gratitude": [
        (r"谢谢|感谢|多谢|辛苦了|麻烦你了|thx|thanks|appreciate", 1.0),
        (r"帮了大忙|救了我|太感谢|太有用了", 1.0),
    ],
    "curiosity": [
        (r"为什么|怎么回事|如何|怎么|怎么办|为什么|what|how|why", 0.6),
        (r"好奇|想知道|请问|请教|研究一下|看看", 0.7),
    ],
    "neutral": [],
}


def detect_emotion(text: str) -> Dict:
    """Detect the dominant emotion in a text. Returns {emotion, confidence, scores}.
    Confidence is the normalized top score; scores is a dict of all matched emotions."""
    if not text or not text.strip():
        return {"emotion": "neutral", "confidence": 0.0, "scores": {}}
    text_lower = text.lower()
    scores: Dict[str, float] = {}
    for emotion, patterns in EMOTION_PATTERNS.items():
        if not patterns:
            continue
        total = 0.0
        for pattern, weight in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                total += weight * min(len(matches), 3)  # cap at 3 matches per pattern
        if total > 0:
            scores[emotion] = total
    if not scores:
        return {"emotion": "neutral", "confidence": 0.0, "scores": {}}
    # Pick the highest-scoring emotion
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    top_emotion, top_score = sorted_scores[0]
    total_score = sum(scores.values())
    confidence = top_score / total_score if total_score > 0 else 0.0
    return {
        "emotion": top_emotion,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 3) for k, v in sorted_scores[:5]},
    }


# ============================================================
# DB schema for advanced memory
# ============================================================

ADVANCED_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_emotions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    conversation_id TEXT,
    message_id TEXT,
    emotion TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    scores_json TEXT NOT NULL DEFAULT '{}',
    text_snippet TEXT NOT NULL DEFAULT '',
    detected_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_emotions_user ON user_emotions(user_id, detected_at);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id TEXT PRIMARY KEY,
    personality TEXT NOT NULL DEFAULT '',
    interests TEXT NOT NULL DEFAULT '',
    preferences TEXT NOT NULL DEFAULT '',
    relationships TEXT NOT NULL DEFAULT '',
    communication_style TEXT NOT NULL DEFAULT '',
    emotional_patterns TEXT NOT NULL DEFAULT '',
    auto_summary TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS emotion_state (
    user_id TEXT PRIMARY KEY,
    current_emotion TEXT NOT NULL DEFAULT 'neutral',
    emotion_intensity REAL NOT NULL DEFAULT 0.0,
    recent_emotions_json TEXT NOT NULL DEFAULT '[]',
    last_updated INTEGER NOT NULL DEFAULT 0
);
"""


def init_advanced_db(db_path: Path):
    """Create advanced memory tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = safe_connect(db_path)
    conn.executescript(ADVANCED_MEMORY_SCHEMA)
    conn.commit()
    conn.close()


# ============================================================
# Emotion tracking
# ============================================================

def record_emotion(db_path: Path, *, user_id: str = "default",
                   conversation_id: Optional[str] = None,
                   message_id: Optional[str] = None,
                   text: str = "", emotion_data: Optional[Dict] = None) -> Dict:
    """Record an emotion detection event for a user message."""
    if emotion_data is None:
        emotion_data = detect_emotion(text)
    eid = hashlib.sha1(f"{user_id}:{message_id or text[:50]}:{time.time()}".encode()).hexdigest()[:16]
    now = int(time.time())
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO user_emotions (id, user_id, conversation_id, message_id, emotion, confidence, scores_json, text_snippet, detected_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, user_id, conversation_id, message_id,
         emotion_data["emotion"], emotion_data["confidence"],
         json.dumps(emotion_data.get("scores", {}), ensure_ascii=False),
         text[:300], now)
    )
    conn.commit()
    conn.close()
    # Update rolling emotion state
    _update_emotion_state(db_path, user_id, emotion_data["emotion"], emotion_data["confidence"])
    return {"id": eid, **emotion_data}


def _update_emotion_state(db_path: Path, user_id: str, emotion: str, confidence: float):
    """Maintain a rolling window of recent emotions (last 20) for the user."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM emotion_state WHERE user_id=?", (user_id,)).fetchone()
    now = int(time.time())
    if row:
        recent = json.loads(row["recent_emotions_json"] or "[]")
        recent.append({"emotion": emotion, "confidence": confidence, "ts": now})
        recent = recent[-20:]  # keep last 20
        # Compute current emotion = most common in last 5
        last_5 = [e["emotion"] for e in recent[-5:]]
        if last_5:
            from collections import Counter
            current = Counter(last_5).most_common(1)[0][0]
            intensity = sum(e["confidence"] for e in recent[-5:]) / 5
        else:
            current = emotion
            intensity = confidence
        conn.execute(
            "UPDATE emotion_state SET current_emotion=?, emotion_intensity=?, recent_emotions_json=?, last_updated=? WHERE user_id=?",
            (current, intensity, json.dumps(recent, ensure_ascii=False), now, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO emotion_state (user_id, current_emotion, emotion_intensity, recent_emotions_json, last_updated) VALUES (?,?,?,?,?)",
            (user_id, emotion, confidence, json.dumps([{"emotion": emotion, "confidence": confidence, "ts": now}], ensure_ascii=False), now)
        )
    conn.commit()
    conn.close()


def get_emotion_state(db_path: Path, user_id: str = "default") -> Dict:
    """Get the current rolling emotion state for a user."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM emotion_state WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return {"current_emotion": "neutral", "emotion_intensity": 0.0, "recent_emotions": []}
    return {
        "current_emotion": row["current_emotion"],
        "emotion_intensity": row["emotion_intensity"],
        "recent_emotions": json.loads(row["recent_emotions_json"] or "[]"),
        "last_updated": row["last_updated"],
    }


def get_emotion_history(db_path: Path, user_id: str = "default", limit: int = 50) -> List[Dict]:
    """Get recent emotion detection events for a user."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM user_emotions WHERE user_id=? ORDER BY detected_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# User profile management
# ============================================================

def get_user_profile(db_path: Path, user_id: str = "default") -> Dict:
    """Get the user profile. Returns empty fields if not yet built."""
    conn = safe_connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return {
            "user_id": user_id,
            "personality": "",
            "interests": "",
            "preferences": "",
            "relationships": "",
            "communication_style": "",
            "emotional_patterns": "",
            "auto_summary": "",
            "updated_at": 0,
        }
    return dict(row)


def update_user_profile(db_path: Path, user_id: str = "default", **fields) -> bool:
    """Update specific fields of the user profile."""
    allowed = {"personality", "interests", "preferences", "relationships",
               "communication_style", "emotional_patterns", "auto_summary"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = int(time.time())
    conn = safe_connect(db_path)
    # Upsert
    cur = conn.execute("SELECT user_id FROM user_profile WHERE user_id=?", (user_id,))
    if cur.fetchone():
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [user_id]
        conn.execute(f"UPDATE user_profile SET {sets} WHERE user_id=?", vals)
    else:
        cols = ["user_id"] + list(updates.keys())
        placeholders = ",".join("?" * len(cols))
        vals = [user_id] + list(updates.values())
        conn.execute(f"INSERT INTO user_profile ({','.join(cols)}) VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    return True


# Profile auto-update prompt — the LLM uses this to extract profile updates
# from recent conversation. The result is JSON with field keys.
PROFILE_UPDATE_PROMPT_DEFAULT = """你是一个用户画像分析器。基于最新对话，更新用户画像。

【当前画像】
{current_profile}

【最新对话】
{conversation}

【任务】
分析对话中关于用户的信息，更新画像字段。规则：
1. 只记录持久特征，不要记录临时对话内容
2. 字段说明：
   - personality: 性格特征（如内向/外向、谨慎/果断、理性/感性）
   - interests: 兴趣爱好（如技术、游戏、音乐、运动）
   - preferences: 偏好（喜欢/讨厌什么、风格倾向、工作习惯）
   - relationships: 人际关系（家人/朋友/同事/宠物）
   - communication_style: 沟通风格（直接/委婉、正式/休闲、喜欢详细/简洁）
   - emotional_patterns: 情绪模式（容易焦虑/乐观/敏感等）
   - auto_summary: 一段话总结这个用户的整体画像
3. 如果某字段在对话中没有新信息，保持原值不变
4. 如果新信息与原值冲突，用新值替换
5. 输出必须是 JSON 格式，只包含有更新的字段

输出格式（只输出有更新的字段，没有更新就不包含）：
```json
{
  "interests": "原兴趣 + 新发现的兴趣",
  "preferences": "新偏好"
}
```

如果对话中没有值得记录的持久信息，输出：
```json
{}
```"""


async def auto_update_profile_via_llm(db_path: Path, user_id: str, conv_text: str,
                                       http_client, api_cfg: Dict) -> Dict:
    """Ask the LLM to update the user profile based on recent conversation."""
    if len(conv_text) < 50:
        return {"updated": False, "reason": "conversation too short"}
    try:
        current = get_user_profile(db_path, user_id)
        profile_summary = "\n".join(
            f"- {k}: {current[k]}" for k in
            ["personality", "interests", "preferences", "relationships",
             "communication_style", "emotional_patterns", "auto_summary"]
            if current.get(k)
        ) or "(空)"
        payload = {
            "model": api_cfg["api_model"],
            "messages": [{"role": "user", "content": _get_prompt("prompt_profile_update", PROFILE_UPDATE_PROMPT_DEFAULT).format(
                current_profile=profile_summary,
                conversation=conv_text[:2500],
            )}],
            "temperature": 0.2,
            "max_tokens": 600,
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
        text = data["choices"][0]["message"]["content"].strip()
        # Extract JSON from response (may be wrapped in ```json ... ```)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Try to find a complete JSON object (handle nested braces)
            depth = 0
            start = -1
            for i, ch in enumerate(text):
                if ch == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        text = text[start:i+1]
                        break
            else:
                text = ""  # No valid JSON found
        try:
            updates = json.loads(text)
        except json.JSONDecodeError:
            return {"updated": False, "reason": "invalid JSON", "raw": text[:200]}
        if not updates or not isinstance(updates, dict):
            return {"updated": False, "reason": "no updates"}
        # Filter to only allowed fields + convert lists/dicts to JSON strings
        allowed = {"personality", "interests", "preferences", "relationships",
                   "communication_style", "emotional_patterns", "auto_summary"}
        clean_updates = {}
        for k, v in updates.items():
            if k not in allowed:
                continue
            if v is None or v == "":
                continue
            if isinstance(v, (list, dict)):
                clean_updates[k] = json.dumps(v, ensure_ascii=False)
            else:
                clean_updates[k] = str(v)
        if not clean_updates:
            return {"updated": False, "reason": "no valid fields"}
        update_user_profile(db_path, user_id, **clean_updates)
        return {"updated": True, "fields": list(updates.keys()), "updates": updates}
    except Exception as e:
        print(f"[profile] auto-update failed: {e}")
        return {"updated": False, "error": str(e)}


# ============================================================
# Proactive memory recall — find memories worth mentioning
# ============================================================

def find_recallable_memories(db_path: Path, query: str, user_id: str = "default",
                              top_k: int = 3) -> List[Dict]:
    """Find memories that could be proactively recalled in conversation.
    Looks for memories with temporal cues ('上次', '之前', '提到过', '说过的')
    in the current query, then finds matching past memories.
    Returns memories that the AI could naturally bring up."""
    # This is a thin wrapper around the main memory_search function.
    # We import it lazily to avoid circular imports.
    from app.main import memory_search
    return memory_search(query, user_id, top_k)


# ============================================================
# Build system prompt sections for advanced memory
# ============================================================

def build_emotional_context_section(db_path: Path, user_id: str = "default") -> str:
    """Build a system prompt section describing the user's current emotional state.
    Returns empty string if emotion tracking is unavailable or state is neutral."""
    state = get_emotion_state(db_path, user_id)
    if state["current_emotion"] == "neutral" or state["emotion_intensity"] < 0.2:
        return ""
    emotion_zh = {
        "joy": "愉悦", "excitement": "兴奋", "anxiety": "焦虑",
        "sadness": "低落", "anger": "愤怒", "frustration": "挫败",
        "sarcasm": "讽刺", "gratitude": "感激", "curiosity": "好奇",
        "neutral": "平静",
    }
    cur = emotion_zh.get(state["current_emotion"], state["current_emotion"])
    intensity_pct = int(state["emotion_intensity"] * 100)
    recent = state["recent_emotions"][-5:]
    recent_str = " → ".join(emotion_zh.get(e["emotion"], e["emotion"]) for e in recent)
    return (
        f"【用户当前情绪状态】\n"
        f"当前主导情绪：{cur}（强度 {intensity_pct}%）\n"
        f"近期情绪轨迹：{recent_str}\n"
        f"提示：根据情绪调整回应风格。如果用户低落/焦虑，多给鼓励和共情；如果用户兴奋，可以一起热情；如果讽刺，可以理解其言外之意。"
    )


def build_user_profile_section(db_path: Path, user_id: str = "default") -> str:
    """Build a system prompt section describing the user's profile."""
    profile = get_user_profile(db_path, user_id)
    parts = []
    if profile.get("auto_summary"):
        parts.append(f"用户画像总结：{profile['auto_summary']}")
    if profile.get("personality"):
        parts.append(f"性格：{profile['personality']}")
    if profile.get("interests"):
        parts.append(f"兴趣：{profile['interests']}")
    if profile.get("preferences"):
        parts.append(f"偏好：{profile['preferences']}")
    if profile.get("communication_style"):
        parts.append(f"沟通风格：{profile['communication_style']}")
    if profile.get("emotional_patterns"):
        parts.append(f"情绪模式：{profile['emotional_patterns']}")
    if profile.get("relationships"):
        parts.append(f"人际关系：{profile['relationships']}")
    if not parts:
        return ""
    return "【用户画像】（基于过往对话积累，越用越懂你）\n" + "\n".join(parts)


def build_proactive_recall_section(db_path: Path, current_query: str,
                                    user_id: str = "default",
                                    top_k: int = 3) -> str:
    """Find memories related to the current query that could be proactively recalled.
    Looks for temporal cues ('上次', '之前', '后来', '那个') in the query and surfaces
    relevant past memories the AI could naturally mention."""
    if not current_query or len(current_query) < 5:
        return ""
    # Only trigger if query has recall cues
    recall_cues = ["上次", "之前", "之前说", "那个", "后来", "提到过", "说过的", "记得吗", "还记得"]
    has_cue = any(cue in current_query for cue in recall_cues)
    if not has_cue:
        return ""
    try:
        mems = find_recallable_memories(db_path, current_query, user_id, top_k=top_k)
    except Exception as e:
        print(f"[recall] failed: {e}")
        return ""
    if not mems:
        return ""
    items = []
    for m in mems[:top_k]:
        # Format the memory and how long ago it was
        age_days = (int(time.time()) - m.get("updated_at", 0)) / 86400
        if age_days < 1:
            age = "今天早些时候"
        elif age_days < 2:
            age = "昨天"
        elif age_days < 7:
            age = f"{int(age_days)}天前"
        elif age_days < 30:
            age = f"{int(age_days / 7)}周前"
        else:
            age = f"{int(age_days / 30)}个月前"
        items.append(f"- ({age}) {m['content']}")
    return (
        "【主动回忆】以下是与当前话题相关的过往记忆，如果合适可以自然地提及（如\"你上次提到过X，后来怎么样了？\"），"
        "但不要生硬复述，要根据对话情境判断是否提起：\n" + "\n".join(items)
    )
