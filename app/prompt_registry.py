"""
Prompt Registry — central catalog of all editable LLM prompts in Cambium.

Every prompt that gets sent to an LLM (memory editing, extraction,
reflection, identity assessment, journal drafting, etc.) is registered
here with:
  - key: the settings key (e.g. "prompt_memory_edit")
  - category: memory / cognitive / reflection / identity / journal / system
  - label: human-readable label
  - description: what this prompt does
  - default: the built-in default text

The registry is the source of truth for the Prompt Engineering settings
panel. Users can edit any prompt, reset to default, or just inspect.

NOTE: Existing modules already use _get_prompt(key, default) to fetch
prompts. This module is the documentation/management layer on top.
"""
from __future__ import annotations
import sqlite3
import time
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


# ============================================================
# Registry of all prompts
# ============================================================
# Each entry: {key, category, label, description, default}
# Defaults are imported lazily to avoid circular imports.

_PROMPT_REGISTRY: List[Dict] = [
    # ===== System / Core =====
    {
        "key": "prompt_system",
        "category": "system",
        "label": "主系统 Prompt",
        "description": "AI 助手的核心人格与行为准则。每条对话都会使用。",
        "default_ref": "main.DEFAULT_SYSTEM_PROMPT",
    },
    {
        "key": "prompt_title",
        "category": "system",
        "label": "对话标题生成",
        "description": "为新对话生成简短标题（≤20 字）。",
        "default_ref": "main.TITLE_PROMPT_DEFAULT",
    },
    {
        "key": "prompt_compress",
        "category": "system",
        "label": "对话压缩",
        "description": "超长对话压缩为摘要，保留关键信息。",
        "default_ref": "main.COMPRESS_PROMPT_DEFAULT",
    },

    # ===== Memory =====
    {
        "key": "prompt_memory_edit",
        "category": "memory",
        "label": "记忆摘要编辑",
        "description": "基于新对话，原地编辑当前用户记忆摘要。",
        "default_ref": "main.MEMORY_EDIT_PROMPT_DEFAULT",
    },
    {
        "key": "prompt_memory_extract",
        "category": "memory",
        "label": "原子事实提取",
        "description": "从对话中提取分类的持久事实（仅在显式触发时使用）。",
        "default_ref": "main.EXTRACT_PROMPT_DEFAULT",
    },
    {
        "key": "prompt_memory_summary",
        "category": "memory",
        "label": "记忆摘要生成",
        "description": "根据多条记忆片段生成连贯摘要。",
        "default_ref": "main.SUMMARY_PROMPT_DEFAULT",
    },
    {
        "key": "prompt_classify_importance",
        "category": "memory",
        "label": "记忆重要度评估",
        "description": "评估一条记忆对用户的长期价值（0-1 分）。",
        "default_ref": "memory_orchestrator.CLASSIFY_IMPORTANCE_PROMPT_DEFAULT",
    },

    # ===== Cognitive =====
    {
        "key": "prompt_cognitive_extraction",
        "category": "cognitive",
        "label": "认知更新提取",
        "description": "从对话中提取身份/时间线/叙事/成长/目标等认知层更新。",
        "default_ref": "cognitive_kernel.COGNITIVE_EXTRACTION_PROMPT_DEFAULT",
    },

    # ===== Reflection =====
    {
        "key": "prompt_reflection",
        "category": "reflection",
        "label": "日度反思",
        "description": "Life Loop 每日反思的指令（整体总结，非逐条）。",
        "default_ref": None,
        "default_text": """你是 Cambium 的反思系统。请根据以下最近的对话和记忆，生成一段反思。

【最近对话】
{conversation}

【已有记忆】
{memories}

【任务】
1. 总结这段对话中值得记住的关键信息。
2. 提取关于用户的持久事实（身份、偏好、目标、技能等）。
3. 如果有新的持久事实，输出 JSON 格式：
```json
{{"memories": [{{"content": "...", "importance": 80, "category": "preference"}}]}}
```
4. 如果没有值得记住的，输出空 JSON：`{{"memories": []}}`

只输出 JSON，不要其他内容。""",
    },
    {
        "key": "prompt_reflection_tree",
        "category": "reflection",
        "label": "反思树（三层反思）",
        "description": "从观察中提炼高层洞察，再上升到元反思。",
        "default_ref": "reflection_tree.REFLECTION_PROMPT_DEFAULT",
    },
    {
        "key": "prompt_meta_cognition",
        "category": "reflection",
        "label": "元认知自检",
        "description": "每次回复后 AI 自检质量（信心度/矛盾/需澄清）的指令。",
        "default_ref": None,
        "default_text": """你是 Cambium 的元认知系统。对刚才的 AI 回复进行自检。

【用户问题】
{user_query}

【AI 回复】
{ai_response}

【相关记忆】
{relevant_memories}

请评估：
1. 信心度（0-1）：回复是否准确、完整？
2. 是否有矛盾：回复是否与已知记忆冲突？
3. 是否需要澄清：用户的问题是否有歧义？

输出 JSON：
```json
{{"confidence": 0.85, "contradiction": false, "needs_clarification": false, "notes": ""}}
```
只输出 JSON。""",
    },

    # ===== Identity =====
    {
        "key": "prompt_identity_assessment",
        "category": "identity",
        "label": "身份一致性评估",
        "description": "评估当前身份叙事是否一致、是否需要演化。",
        "default_ref": "identity_consistency.IDENTITY_ASSESSMENT_PROMPT_DEFAULT",
    },

    # ===== Profile / Emotion =====
    {
        "key": "prompt_profile_update",
        "category": "profile",
        "label": "用户画像更新",
        "description": "基于对话更新用户画像（兴趣、风格、技能等）。",
        "default_ref": "advanced_memory.PROFILE_UPDATE_PROMPT_DEFAULT",
    },

    # ===== Journal =====
    {
        "key": "prompt_journal_draft",
        "category": "journal",
        "label": "日志 AI 草稿生成",
        "description": "基于当日活动生成日志草稿，包含情绪、亮点、成长。",
        "default_ref": None,  # custom default defined below
        "default_text": """你是 Cambium 的日志助手。请基于以下今日活动，为用户写一段第一人称的日志草稿。

【今日活动】
{activity_summary}

【要求】
1. 用第一人称"我"（用户视角）。
2. 不要机械罗列，要有叙事感，像真人在写日志。
3. 200-400 字，分段。
4. 自然带出当天的主要事件、情绪和收获。
5. 不要写"以下是日志"之类的元描述。

【输出格式】
直接输出日志正文。""",
    },
    {
        "key": "prompt_journal_emotion",
        "category": "journal",
        "label": "日志情绪分析",
        "description": "分析当日活动/日志的情绪基调。",
        "default_ref": None,
        "default_text": """请分析以下内容的情绪基调，输出一个词（中文或英文皆可）概括。

【内容】
{content}

【可选情绪词】
happy / calm / focused / tired / frustrated / excited / sad / anxious / proud / grateful / neutral
开心 / 平静 / 专注 / 疲惫 / 挫败 / 兴奋 / 难过 / 焦虑 / 自豪 / 感恩 / 中性

只输出一个词。""",
    },
]


def _resolve_default(entry: Dict) -> str:
    """Resolve the default text from either inline default_text or a module reference."""
    if entry.get("default_text"):
        return entry["default_text"]
    ref = entry.get("default_ref")
    if not ref:
        return ""
    try:
        # ref format: "module.attr" e.g. "main.MEMORY_EDIT_PROMPT_DEFAULT"
        if "." not in ref:
            return ""
        mod_name, attr = ref.split(".", 1)
        if mod_name == "main":
            from app import main
            return getattr(main, attr, "")
        elif mod_name == "memory_orchestrator":
            from app import memory_orchestrator
            return getattr(memory_orchestrator, attr, "")
        elif mod_name == "cognitive_kernel":
            from app import cognitive_kernel
            return getattr(cognitive_kernel, attr, "")
        elif mod_name == "reflection_tree":
            from app import reflection_tree
            return getattr(reflection_tree, attr, "")
        elif mod_name == "identity_consistency":
            from app import identity_consistency
            return getattr(identity_consistency, attr, "")
        elif mod_name == "advanced_memory":
            from app import advanced_memory
            return getattr(advanced_memory, attr, "")
    except Exception as e:
        print(f"[prompt_registry] failed to resolve default for {ref}: {e}")
    return ""


def list_categories() -> List[str]:
    """All unique categories in the registry."""
    return sorted({e["category"] for e in _PROMPT_REGISTRY})


def list_prompts(category: Optional[str] = None) -> List[Dict]:
    """List all registered prompts. Optionally filter by category.
    Returns metadata + current content (default if not customized)."""
    out = []
    for entry in _PROMPT_REGISTRY:
        if category and entry["category"] != category:
            continue
        default_text = _resolve_default(entry)
        out.append({
            "key": entry["key"],
            "category": entry["category"],
            "label": entry["label"],
            "description": entry["description"],
            "default": default_text,
        })
    return out


def get_prompt_with_meta(db_path: Path, key: str) -> Optional[Dict]:
    """Get a single prompt with full metadata + current value."""
    entry = next((e for e in _PROMPT_REGISTRY if e["key"] == key), None)
    if not entry:
        return None
    default_text = _resolve_default(entry)
    # Try to read from DB
    conn = safe_connect(db_path)
    cur = conn.execute(
        "SELECT content, is_default, updated_at FROM prompt_templates WHERE key=?",
        (key,)
    ).fetchone()
    conn.close()
    if cur:
        return {
            "key": key,
            "category": entry["category"],
            "label": entry["label"],
            "description": entry["description"],
            "default": default_text,
            "content": cur[0],
            "is_default": bool(cur[1]),
            "updated_at": cur[2],
        }
    # Not in DB yet → use default
    return {
        "key": key,
        "category": entry["category"],
        "label": entry["label"],
        "description": entry["description"],
        "default": default_text,
        "content": default_text,
        "is_default": True,
        "updated_at": None,
    }


def set_prompt(db_path: Path, key: str, content: str) -> bool:
    """Set (customize) a prompt. Empty content resets to default."""
    entry = next((e for e in _PROMPT_REGISTRY if e["key"] == key), None)
    if not entry:
        return False
    default_text = _resolve_default(entry)
    now = int(time.time())
    # If content equals default (or empty), reset
    is_default = 1 if (not content.strip() or content.strip() == default_text.strip()) else 0
    final_content = default_text if is_default else content
    conn = safe_connect(db_path)
    conn.execute(
        """INSERT INTO prompt_templates (key, category, label, description, content, is_default, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             content=excluded.content,
             is_default=excluded.is_default,
             updated_at=excluded.updated_at""",
        (key, entry["category"], entry["label"], entry["description"],
         final_content, is_default, now)
    )
    conn.commit()
    conn.close()

    # Also mirror to settings table so existing _get_prompt() helpers pick it up
    # (existing modules read from settings; we keep both in sync)
    try:
        conn = safe_connect(db_path)
        conn.execute(
            """INSERT INTO settings (key, value) VALUES (?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, final_content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[prompt_registry] mirror to settings failed: {e}")

    return True


def reset_prompt(db_path: Path, key: str) -> bool:
    """Reset a prompt to its built-in default."""
    entry = next((e for e in _PROMPT_REGISTRY if e["key"] == key), None)
    if not entry:
        return False
    default_text = _resolve_default(entry)
    return set_prompt(db_path, key, default_text)


def get_stats(db_path: Path) -> Dict:
    """How many prompts are customized vs default."""
    conn = safe_connect(db_path)
    cur = conn.execute(
        "SELECT COUNT(*) FROM prompt_templates WHERE is_default=0"
    ).fetchone()
    customized = cur[0] if cur else 0
    conn.close()
    return {
        "total": len(_PROMPT_REGISTRY),
        "customized": customized,
        "default": len(_PROMPT_REGISTRY) - customized,
        "categories": list_categories(),
    }
