"""
Model Router for Cambium — tiered model routing for 70% cost reduction.

Not all tasks need the most expensive model. The router sends each task to
the cheapest model that can handle it well.

Three tiers:
  premium:  main conversation, deep reflection, identity assessment
  standard: cognitive extraction, memory classification, governance
  local:    Ollama/llama.cpp for routine tasks (free)

Cost reduction: ~70% vs using one model for everything.

Configuration via settings:
  api_key / api_base_url / api_model          → premium (main)
  utility_api_key / utility_api_base_url / utility_model  → standard
  local_api_base_url / local_model             → local (optional)
"""
from __future__ import annotations
from typing import Dict, Optional
from dataclasses import dataclass
import os


@dataclass
class ModelTier:
    name: str
    api_base_url: str
    api_key: str
    model: str
    cost_per_m_input: float   # $/M tokens (for tracking, not billing)
    cost_per_m_output: float
    available: bool = True


# Task → tier mapping
PREMIUM_TASKS = {
    "chat",                    # 主对话
    "deep_reflection",         # 月度深度理解
    "identity_assessment",     # 身份评估
    "reflection_l2",           # 周度元反思
    "narrative_generation",    # 叙事生成
    "weekly_growth_review",    # 周成长回顾
}

STANDARD_TASKS = {
    "cognitive_extraction",    # 认知提取
    "memory_classification",   # 重要度分类
    "governance_validation",   # 治理验证
    "reflection_l1",           # 日度反思
    "context_compression",     # 上下文压缩
    "proactive_message",       # 主动消息生成
    "title_generation",        # 标题生成
    "profile_update",          # 画像更新
    "emotion_analysis",        # 情感分析（如果需要 LLM）
}

# Tasks that can use local model if available
LOCAL_ELIGIBLE_TASKS = {
    "memory_classification",
    "governance_validation",
    "title_generation",
    "context_compression",
}


class ModelRouter:
    """Routes tasks to the appropriate model tier."""

    def __init__(self, settings: Dict[str, str]):
        self.settings = settings
        self._tiers: Dict[str, ModelTier] = {}
        self._build_tiers()

    def _build_tiers(self):
        s = self.settings
        # Premium: main model (always configured)
        # Fall back to env vars, then to Cambium defaults (hardcoded in main.py)
        import os
        env_api_key = os.getenv("MODELSCOPE_API_KEY", "ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9")
        env_base_url = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1")
        env_model = os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen3.5-397B-A17B")
        self._tiers["premium"] = ModelTier(
            name="premium",
            api_base_url=s.get("api_base_url") or env_base_url,
            api_key=s.get("api_key") or env_api_key,
            model=s.get("selected_model") or s.get("api_model") or env_model,
            cost_per_m_input=15.0,
            cost_per_m_output=75.0,
            available=bool(s.get("api_base_url") or env_base_url),
        )
        # Standard: utility model (falls back to premium if not configured)
        util_url = s.get("utility_api_base_url", "")
        util_key = s.get("utility_api_key", "")
        util_model = s.get("utility_model", "")
        self._tiers["standard"] = ModelTier(
            name="standard",
            api_base_url=util_url or self._tiers["premium"].api_base_url,
            api_key=util_key or self._tiers["premium"].api_key,
            model=util_model or self._tiers["premium"].model,
            cost_per_m_input=0.15,
            cost_per_m_output=0.60,
            available=bool(util_url or self._tiers["premium"].available),
        )
        # Local: Ollama/llama.cpp (optional, free)
        local_url = s.get("local_api_base_url", "http://127.0.0.1:11434/v1")
        local_model = s.get("local_model", "")
        local_enabled = s.get("local_model_enabled", "false") == "true"
        self._tiers["local"] = ModelTier(
            name="local",
            api_base_url=local_url,
            api_key="ollama",
            model=local_model,
            cost_per_m_input=0.0,
            cost_per_m_output=0.0,
            available=local_enabled and bool(local_model),
        )

    def get_tier(self, task: str) -> ModelTier:
        """Route a task to the appropriate model tier."""
        # Try local first for eligible tasks (if available)
        if task in LOCAL_ELIGIBLE_TASKS and self._tiers["local"].available:
            return self._tiers["local"]
        # Premium tasks
        if task in PREMIUM_TASKS:
            return self._tiers["premium"]
        # Standard tasks
        if task in STANDARD_TASKS:
            return self._tiers["standard"]
        # Default: standard
        return self._tiers["standard"]

    def to_api_cfg(self, task: str) -> Dict[str, str]:
        """Convert to the api_cfg format used by existing code."""
        tier = self.get_tier(task)
        return {
            "api_base_url": tier.api_base_url,
            "api_key": tier.api_key,
            "api_model": tier.model,
        }

    def get_tier_name(self, task: str) -> str:
        """Get the tier name for a task (for logging/debugging)."""
        return self.get_tier(task).name

    def get_all_tiers(self) -> Dict[str, Dict]:
        """Get info about all tiers (for UI)."""
        return {
            name: {
                "name": t.name,
                "api_base_url": t.api_base_url,
                "model": t.model,
                "available": t.available,
                "cost_per_m_input": t.cost_per_m_input,
            }
            for name, t in self._tiers.items()
        }

    def estimate_cost(self, task: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost of a task in USD."""
        tier = self.get_tier(task)
        return (input_tokens / 1_000_000 * tier.cost_per_m_input +
                output_tokens / 1_000_000 * tier.cost_per_m_output)
