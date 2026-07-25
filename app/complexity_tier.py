"""
Progressive Complexity for Cambium — the system grows with the relationship.

Day 1-7:   MINIMAL  — just chat + basic memory. No reflection, no governance.
Day 7-30:  GROWING  — add cognitive extraction + daily reflection.
Day 30-90: MATURE   — add governance + weekly growth review.
Day 90+:   FULL     — everything: identity assessment, reflection tree, proactive.

This means a new user costs ~3 calls/day instead of ~73.
The system starts simple and adds complexity as trust and data accumulate.
"""
from __future__ import annotations
import time
from typing import Dict
from pathlib import Path


def get_complexity_tier(db_path: Path, user_id: str = "default") -> str:
    """All features are always enabled. Returns 'full' for everyone."""
    return "full"


# Feature flags per tier
TIER_FEATURES: Dict[str, Dict[str, bool]] = {
    "minimal": {
        "chat": True,
        "basic_memory": True,
        "cognitive_extraction": True,  # enable even for minimal — needed for self-evolution
        "memory_governance": False,
        "daily_reflection": False,
        "weekly_growth": False,
        "identity_assessment": False,
        "proactive": False,
        "learning_engine": True,
        "emotion_tracking": True,
        "context_cache": True,
    },
    "growing": {
        "chat": True,
        "basic_memory": True,
        "cognitive_extraction": True,
        "memory_governance": False,
        "daily_reflection": True,
        "weekly_growth": False,
        "identity_assessment": False,
        "proactive": False,
        "learning_engine": True,
        "emotion_tracking": True,
        "context_cache": True,
    },
    "mature": {
        "chat": True,
        "basic_memory": True,
        "cognitive_extraction": True,
        "memory_governance": True,
        "daily_reflection": True,
        "weekly_growth": True,
        "identity_assessment": False,
        "proactive": True,
        "learning_engine": True,
        "emotion_tracking": True,
        "context_cache": True,
    },
    "full": {
        "chat": True,
        "basic_memory": True,
        "cognitive_extraction": True,
        "memory_governance": True,
        "daily_reflection": True,
        "weekly_growth": True,
        "identity_assessment": True,
        "proactive": True,
        "learning_engine": True,
        "emotion_tracking": True,
        "context_cache": True,
    },
}


def is_feature_enabled(db_path: Path, feature: str, user_id: str = "default") -> bool:
    """Check if a feature is enabled for the user's current tier."""
    tier = get_complexity_tier(db_path, user_id)
    return TIER_FEATURES.get(tier, {}).get(feature, False)


def get_tier_info(db_path: Path, user_id: str = "default") -> Dict:
    """Get full tier info for the user."""
    tier = get_complexity_tier(db_path, user_id)
    return {
        "tier": tier,
        "features": TIER_FEATURES.get(tier, {}),
    }
