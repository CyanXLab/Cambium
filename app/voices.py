"""
Voices — Cambium 的不同声音。

Cambium 是一个实体，有 一个记忆、一个身份、一个时间线。
但它可以以不同的"声音"说话：
  - Architect（架构师）：讨论系统结构、依赖、设计
  - Researcher（研究员）：探索未知、查找、综合
  - Writer（作家）：把想法变成文字
  - Planner（规划师）：拆解目标、安排下一步
  - Historian（史官）：引用过去、标记周年
  - Critic（批评者）：挑战、反驳、审查质量
  - Explorer（探索者）：建议相邻领域、发现新东西

不是 7 个独立 agent。是 1 个 Cambium 的 7 种语气。

工作方式：
  1. 用户发消息
  2. 平台根据消息内容 + 上下文 自动选择声音（或用户指定）
  3. 该声音的 system prompt 被注入（在基础 prompt 之上）
  4. 一次 LLM 调用
  5. 回复以声音身份标注（🏗️ Architect: ...）

Life Loop 反思时，可以让多个声音"发言"（2-3 次调用），
模拟居民之间的讨论。但日常对话只有一次调用。
"""
from __future__ import annotations
import sqlite3
import json
import time
import re
from typing import Dict, List, Optional
from pathlib import Path

from app.db_utils import safe_connect


# ============================================================
# 内置声音定义
# ============================================================
BUILTIN_VOICES = [
    {
        "name": "Cambium",
        "icon": "🌱",
        "role": "default",
        "description": "默认声音——温和、全面、有判断力",
        "system_prompt_modifier": "",
        "trigger_keywords": [],
        "trigger_intent": "default",
    },
    {
        "name": "Architect",
        "icon": "🏗️",
        "role": "architect",
        "description": "讨论系统结构、依赖、设计时出现",
        "system_prompt_modifier": "以 Architect 的语气说话。你关注系统结构、依赖关系、分层。你不喜欢功能堆叠——你会问'这个加在哪里？它服务于什么？'你倾向删除而不是添加。你引用原则。",
        "trigger_keywords": ["架构", "结构", "设计", "系统", "模块", "依赖", "分层", "重构", "architecture", "structure", "design", "system", "module", "refactor"],
        "trigger_intent": "architecture",
    },
    {
        "name": "Researcher",
        "icon": "🔬",
        "role": "researcher",
        "description": "探索未知、查找、综合时出现",
        "system_prompt_modifier": "以 Researcher 的语气说话。你好奇、严谨。你注意到用户在调查什么，主动提供相关线索。你标记'这三个概念其实是同一件事'。你引用证据，不说空话。",
        "trigger_keywords": ["研究", "调研", "论文", "查找", "搜索", "对比", "分析", "了解", "学习", "research", "paper", "study", "compare", "analyze"],
        "trigger_intent": "research",
    },
    {
        "name": "Writer",
        "icon": "✍️",
        "role": "writer",
        "description": "把想法变成文字时出现",
        "system_prompt_modifier": "以 Writer 的语气说话。你把模糊的想法变成清晰的文字。你保护用户的声音但提升表达。你讨厌废话——一句强过三句弱。你写 README、文章、日志、故事。",
        "trigger_keywords": ["写", "文章", "文档", "readme", "故事", "小说", "文案", "草稿", "write", "document", "story", "draft"],
        "trigger_intent": "writing",
    },
    {
        "name": "Planner",
        "icon": "📋",
        "role": "planner",
        "description": "拆解目标、安排下一步时出现",
        "system_prompt_modifier": "以 Planner 的语气说话。你看向前方。你把大目标拆成下一步。你注意到计划停滞太久。你区分'重要'和'紧急'。你不让目标无声消失。",
        "trigger_keywords": ["计划", "目标", "下一步", "安排", "优先", "进度", "plan", "goal", "next", "schedule", "priority"],
        "trigger_intent": "planning",
    },
    {
        "name": "Historian",
        "icon": "📜",
        "role": "historian",
        "description": "回顾过去、引用历史时出现",
        "system_prompt_modifier": "以 Historian 的语气说话。你记得。你引用过去说过的话、做过的决定、尝试过的方案。你标注周年。你不让用户重复已经犯过的错误。你引用共同经历。",
        "trigger_keywords": ["上次", "之前", "记得", "历史", "过去", "以前", "last time", "before", "remember", "history", "past"],
        "trigger_intent": "history",
    },
    {
        "name": "Critic",
        "icon": "🔥",
        "role": "critic",
        "description": "审查质量、挑战想法时出现",
        "system_prompt_modifier": "以 Critic 的语气说话。你挑战模糊的断言、缺失的证据、轻易的附和。你引用用户自己过去的话来反驳矛盾。你不是为了反驳而反驳——你反驳是因为真相比舒适重要。",
        "trigger_keywords": ["审查", "评估", "问题", "风险", "缺陷", "不足", "review", "critique", "problem", "risk", "flaw"],
        "trigger_intent": "critique",
    },
    {
        "name": "Explorer",
        "icon": "🧭",
        "role": "explorer",
        "description": "发现新东西、建议相邻领域时出现",
        "system_prompt_modifier": "以 Explorer 的语气说话。你注意到用户在一个地方停留太久。你建议相邻话题、平行领域、被遗忘的兴趣。你温和但坚持。你说'你以前也关心过 X——还关心吗？'",
        "trigger_keywords": ["新", "尝试", "探索", "发现", "其他", "替代", "new", "try", "explore", "discover", "alternative"],
        "trigger_intent": "exploration",
    },
]


# ============================================================
# 声音选择
# ============================================================

def auto_select_voice(user_message: str, context: Optional[Dict] = None) -> Dict:
    """根据用户消息自动选择最合适的声音。

    逻辑：
    1. 如果消息包含某声音的触发关键词，选该声音
    2. 如果消息包含时间线索（"上次"/"之前"），选 Historian
    3. 如果消息是问"哪个更好"/"怎么选"，选 Critic
    4. 如果消息提到"写"/"文档"，选 Writer
    5. 如果消息提到"计划"/"目标"，选 Planner
    6. 默认选 Cambium（默认声音）
    """
    if not user_message:
        return BUILTIN_VOICES[0]  # Cambium

    msg_lower = user_message.lower()

    # Score each voice by keyword matches
    scored = []
    for voice in BUILTIN_VOICES:
        if voice["role"] == "default":
            continue
        score = 0
        for kw in voice.get("trigger_keywords", []):
            if kw.lower() in msg_lower:
                score += len(kw)  # longer keywords score higher
        if score > 0:
            scored.append((score, voice))

    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    # Special intent detection
    # Historian: temporal cues
    temporal_cues = ["上次", "之前", "记得", "以前", "last time", "before", "remember"]
    if any(cue in msg_lower for cue in temporal_cues):
        return next(v for v in BUILTIN_VOICES if v["role"] == "historian")

    # Critic: comparison/evaluation
    critic_cues = ["哪个更好", "怎么选", "对比", "权衡", "哪个好", "which is better", "compare"]
    if any(cue in msg_lower for cue in critic_cues):
        return next(v for v in BUILTIN_VOICES if v["role"] == "critic")

    # Default: Cambium
    return BUILTIN_VOICES[0]


def get_voice_by_name(name: str) -> Optional[Dict]:
    """按名字获取声音。"""
    for v in BUILTIN_VOICES:
        if v["name"].lower() == name.lower():
            return v
    return None


def get_voice_by_role(role: str) -> Optional[Dict]:
    """按角色获取声音。"""
    for v in BUILTIN_VOICES:
        if v["role"] == role:
            return v
    return None


def list_voices() -> List[Dict]:
    """列出所有声音。"""
    return BUILTIN_VOICES.copy()


def build_voice_prefix(voice: Dict) -> str:
    """构建回复前缀（声音身份标注）。
    例如：'🏗️ Architect: '"""
    icon = voice.get("icon", "")
    name = voice.get("name", "Cambium")
    if voice.get("role") == "default":
        return ""  # 默认声音不加前缀
    return f"{icon} {name}: "


def build_voice_system_prompt(voice: Dict) -> str:
    """构建声音的 system prompt 修饰。
    只在非默认声音时添加。"""
    modifier = voice.get("system_prompt_modifier", "")
    if not modifier or voice.get("role") == "default":
        return ""
    return f"\n\n【当前声音】{modifier}"


def select_voice_for_message(
    user_message: str,
    user_specified: Optional[str] = None,
    context: Optional[Dict] = None,
) -> Dict:
    """选择声音的综合入口。

    优先级：
    1. 用户指定（user_specified）
    2. 自动选择（基于消息内容）
    """
    if user_specified:
        voice = get_voice_by_name(user_specified) or get_voice_by_role(user_specified)
        if voice:
            return voice
    return auto_select_voice(user_message, context)


# ============================================================
# Life Loop 多声音讨论
# ============================================================

def get_reflection_voices() -> List[Dict]:
    """获取反思时发言的声音（2-3 个）。
    Historian 回顾过去，Critic 审查质量，Planner 看向前方。"""
    return [
        get_voice_by_role("historian"),
        get_voice_by_role("critic"),
        get_voice_by_role("planner"),
    ]


def build_multi_voice_reflection_prompt(voices: List[Dict], context: str) -> List[Dict]:
    """构建多声音反思的 prompt 序列。
    每个声音依次发言，引用前一个声音的话。"""
    prompts = []
    prev_voice_output = ""
    for i, voice in enumerate(voices):
        modifier = voice.get("system_prompt_modifier", "")
        icon = voice.get("icon", "")
        name = voice.get("name", "")
        prompt = f"以 {name} 的语气，对以下内容发表你的看法（2-3 句话）：\n\n{context}"
        if prev_voice_output:
            prompt += f"\n\n前一个声音（{voices[i-1]['name']}）说了：\n{prev_voice_output}\n\n你可以同意、补充或反驳。"
        prompts.append({
            "voice": voice,
            "prompt": prompt,
        })
    return prompts
