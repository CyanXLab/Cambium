"""
DSPy Integration — prompt 优化和签名化 AI 调用。

DSPy 提供:
  1. Signature — 声明式定义 AI 任务的输入/输出
  2. Module — 可组合的 AI 调用单元（类似 nn.Module）
  3. Optimizer — 自动优化 prompt（基于示例和反馈）

集成方式:
  - 用 DSPy Signature 替代硬编码 prompt
  - 用 DSPy Module 组合多步推理
  - 未来可用 Optimizer 自动优化 prompt（需要标注数据）
"""
from __future__ import annotations
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False


# ============================================================
# DSPy Signatures — 声明式 AI 任务定义
# ============================================================

if DSPY_AVAILABLE:
    # 记忆编辑签名
    class MemoryEditSignature(dspy.Signature):
        """编辑用户记忆摘要。基于新对话更新当前摘要。"""
        current_summary: str = dspy.InputField(desc="当前记忆摘要")
        conversation: str = dspy.InputField(desc="最新对话片段")
        updated_summary: str = dspy.OutputField(desc="编辑后的摘要全文")

    # 认知提取签名
    class CognitiveExtractionSignature(dspy.Signature):
        """从对话中提取认知更新。"""
        conversation: str = dspy.InputField(desc="对话内容")
        identity_summary: str = dspy.InputField(desc="当前身份摘要")
        extraction: str = dspy.OutputField(desc="JSON 格式的认知更新")

    # 反思签名
    class ReflectionSignature(dspy.Signature):
        """整体反思最近的对话。"""
        recent_conversation: str = dspy.InputField(desc="最近对话")
        existing_memories: str = dspy.InputField(desc="已有记忆")
        profile: str = dspy.InputField(desc="用户画像")
        reflection: str = dspy.OutputField(desc="JSON 格式的反思结果")

    # 晨报签名
    class MorningLetterSignature(dspy.Signature):
        """给用户写一封早晨信件。"""
        context: str = dspy.InputField(desc="上下文信息")
        letter: str = dspy.OutputField(desc="信件正文")

    # 居民回复签名
    class ResidentResponseSignature(dspy.Signature):
        """居民以自己的视角回复。"""
        system_prompt: str = dspy.InputField(desc="居民人格设定")
        user_message: str = dspy.InputField(desc="用户消息")
        context: str = dspy.InputField(desc="共享认知上下文")
        response: str = dspy.OutputField(desc="回复内容")


# ============================================================
# DSPy Modules — 可组合的 AI 调用
# ============================================================

if DSPY_AVAILABLE:
    class MemoryEditor(dspy.Module):
        """记忆编辑模块。"""
        def __init__(self):
            super().__init__()
            self.edit = dspy.ChainOfThought(MemoryEditSignature)

        def forward(self, current_summary: str, conversation: str) -> str:
            result = self.edit(current_summary=current_summary, conversation=conversation)
            return result.updated_summary

    class CognitiveExtractor(dspy.Module):
        """认知提取模块。"""
        def __init__(self):
            super().__init__()
            self.extract = dspy.ChainOfThought(CognitiveExtractionSignature)

        def forward(self, conversation: str, identity_summary: str = "") -> str:
            result = self.extract(conversation=conversation, identity_summary=identity_summary)
            return result.extraction

    class Reflector(dspy.Module):
        """反思模块。"""
        def __init__(self):
            super().__init__()
            self.reflect = dspy.ChainOfThought(ReflectionSignature)

        def forward(self, recent_conversation: str, existing_memories: str, profile: str) -> str:
            result = self.reflect(
                recent_conversation=recent_conversation,
                existing_memories=existing_memories,
                profile=profile,
            )
            return result.reflection


# ============================================================
# LM 配置 — 连接 DSPy 到 Cambium 的 API 配置
# ============================================================

_dspy_lm = None

def configure_dspy(api_base_url: str, api_key: str, model: str):
    """配置 DSPy 的 LM（语言模型）。"""
    global _dspy_lm
    if not DSPY_AVAILABLE:
        return False
    try:
        lm = dspy.LM(
            model=f"openai/{model}" if "/" in model and not model.startswith("openai/") else model,
            api_base=api_base_url,
            api_key=api_key,
        )
        dspy.configure(lm=lm)
        _dspy_lm = lm
        return True
    except Exception as e:
        print(f"[dspy] configure failed: {e}")
        return False


def is_available() -> bool:
    return DSPY_AVAILABLE


def get_module(name: str):
    """获取一个 DSPy 模块实例。"""
    if not DSPY_AVAILABLE:
        return None
    modules = {
        "memory_editor": MemoryEditor,
        "cognitive_extractor": CognitiveExtractor,
        "reflector": Reflector,
    }
    cls = modules.get(name)
    return cls() if cls else None
