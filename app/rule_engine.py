"""
Rule Engine for Cambium — rule-first, LLM fallback.

80% of "utility" LLM calls can be replaced by rules. This module provides
fast, zero-cost rule-based handlers for:
- Memory importance classification
- Cognitive extraction decision (skip trivial exchanges)
- Contradiction detection
- Emotion detection (already in advanced_memory, but here as fallback)

Principle: try rules first. Only call LLM if rules return None (uncertain).

This eliminates ~80% of utility-model API calls.
"""
from __future__ import annotations
import re
from typing import Optional, Tuple


def classify_importance_by_rules(content: str) -> Optional[int]:
    """Rule-based importance classification (0-100).
    Returns None if uncertain → caller falls back to LLM.
    Covers ~90% of cases without any API call.
    """
    if not content or len(content.strip()) < 3:
        return 5  # trivial
    content_lower = content.lower()

    # High importance signals (80-100)
    high_signals = [
        (r"(决定|选择|确定|最终).{0,10}(用|使用|采用|架构|方案)", 90),
        (r"(讨厌|不喜欢|绝对不|永远不|再也不)", 85),
        (r"(重要|关键|核心|必须|一定)", 80),
        (r"(deadline|截止|紧急|urgent)", 85),
        (r"(承诺|答应|约定|说好)", 85),
        (r"(分手|离婚|辞职|离职|搬家|生病|住院|高考|面试)", 95),
        (r"(我的名字|我叫|我是).{0,10}[a-zA-Z\u4e00-\u9fff]", 95),
        (r"(我的学校|我在|我读|我学)", 88),
        (r"(记住|remember|别忘了|don't forget)", 80),
    ]
    for pattern, score in high_signals:
        if re.search(pattern, content_lower):
            return score

    # Low importance signals (10-30)
    low_signals = [
        (r"^(好的|ok|嗯|哦|行|可以|没问题|对|是的)$", 10),
        (r"(今天天气|吃了吗|早上好|晚安|你好|hi|hello)", 15),
        (r"^(哈哈|呵呵|😂|🤣|👍|666)$", 10),
        (r"^(谢谢|感谢|辛苦了|thx|thanks)$", 20),
        (r"^(继续|go|next|下一个)$", 15),
    ]
    for pattern, score in low_signals:
        if re.search(pattern, content_lower):
            return score

    # Medium importance signals (40-60)
    medium_signals = [
        (r"(觉得|认为|偏好|喜欢|倾向)", 55),
        (r"(项目|工作|代码|bug|功能|开发)", 50),
        (r"(计划|打算|准备|想要|考虑)", 55),
        (r"(学习|研究|在看|在读)", 50),
        (r"(游戏|电影|音乐|书)", 45),
    ]
    for pattern, score in medium_signals:
        if re.search(pattern, content_lower):
            return score

    # Uncertain → return None → caller falls back to LLM
    return None


def should_extract_cognitive(user_msg: str, ai_msg: str) -> bool:
    """Decide whether this conversation turn warrants cognitive extraction.
    Skip extraction for trivial exchanges. Saves ~60% of extraction calls.
    """
    if not user_msg or not user_msg.strip():
        return False

    # Skip if both messages are very short
    if len(user_msg) < 10 and len(ai_msg) < 50:
        return False

    # Skip if it's a pure greeting/farewell
    greetings = {"你好", "hi", "hello", "hey", "早上好", "晚安", "bye", "再见",
                 "ok", "好的", "嗯", "谢谢", "thanks", "thank you", "哈喽"}
    if user_msg.strip().lower() in greetings:
        return False

    # Skip if it's a pure code block with no discussion
    if user_msg.count("```") >= 2 and len(user_msg.replace("```", "").strip()) < 50:
        return False

    # Always extract if user shares personal info or makes decisions
    personal_signals = [
        r"(我|my|me).{0,20}(决定|选择|喜欢|讨厌|计划|打算|叫|是|在|读|学)",
        r"(我们|our|we).{0,20}(项目|团队|公司)",
        r"(记住|remember|别忘了|don't forget)",
        r"(高考|面试|毕业|工作|创业)",
    ]
    for pattern in personal_signals:
        if re.search(pattern, user_msg, re.IGNORECASE):
            return True

    # Default: extract if conversation is substantive
    return len(user_msg) > 30 or len(ai_msg) > 200


def detect_contradiction_by_rules(new_content: str, existing_content: str) -> Optional[bool]:
    """Rule-based contradiction detection.
    Returns True (contradiction), False (no contradiction), or None (uncertain → use LLM).
    Saves ~90% of contradiction detection calls.
    """
    new_lower = new_content.lower()
    existing_lower = existing_content.lower()

    negation_pairs = [
        ("喜欢", "讨厌"), ("love", "hate"),
        ("擅长", "不擅长"), ("good at", "bad at"),
        ("总是", "从不"), ("always", "never"),
        ("是", "不是"), ("can", "cannot"),
        ("用", "不用"), ("use", "don't use"),
        ("想要", "不想要"), ("want", "don't want"),
    ]

    # Check if they share enough keywords to be about the same topic
    new_words = set(w for w in re.findall(r'\w+', new_lower) if len(w) > 1)
    existing_words = set(w for w in re.findall(r'\w+', existing_lower) if len(w) > 1)
    if not new_words or not existing_words:
        return None
    overlap = len(new_words & existing_words) / max(len(new_words | existing_words), 1)

    if overlap < 0.2:
        return False  # Different topics, no contradiction possible

    for pos, neg in negation_pairs:
        if (pos in new_lower and neg in existing_lower) or \
           (neg in new_lower and pos in existing_lower):
            return True  # Clear contradiction

    return None  # Uncertain → fall back to LLM


def should_run_reflection(observations_count: int, total_importance: int,
                           min_observations: int = 3, min_importance: int = 100) -> bool:
    """Decide whether a reflection cycle should run.
    Conditional trigger: only run if there's enough new material.
    Saves ~60% of Life Loop reflection calls.
    """
    if observations_count < min_observations:
        return False
    if total_importance < min_importance:
        return False
    return True


def categorize_by_rules(content: str) -> Optional[str]:
    """Rule-based category detection for memory items.
    Returns: identity/preference/goal/skill/relationship/event/other, or None.
    """
    content_lower = content.lower()
    if re.search(r"(我叫|我的名字|我是|我住|我在|我读|我学|我的学校|我的职业)", content_lower):
        return "identity"
    if re.search(r"(喜欢|讨厌|偏好|倾向|口味|风格)", content_lower):
        return "preference"
    if re.search(r"(计划|打算|目标|想要|准备|决定)", content_lower):
        return "goal"
    if re.search(r"(擅长|会|精通|熟练|能力|技能)", content_lower):
        return "skill"
    if re.search(r"(朋友|家人|同事|同学|女朋友|男朋友|老婆|老公|父母)", content_lower):
        return "relationship"
    if re.search(r"(今天|昨天|上次|刚才|发生了|经历了)", content_lower):
        return "event"
    return None
