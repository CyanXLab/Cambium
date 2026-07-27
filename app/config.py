"""
Cambium Configuration — Pydantic Settings with validation.

Replaces the flat DEFAULT_SETTINGS dict with a typed, validated, hierarchical
config model. Settings are loaded from (in priority order):
  1. Environment variables (CAMBIUM_ prefix)
  2. .env file
  3. SQLite settings table (user overrides via UI)
  4. Defaults defined here

This module is the single source of truth for configuration. All other modules
should import from here rather than reading os.getenv() directly.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# Base directories
# ============================================================

BASE_DIR = Path(__file__).resolve().parent  # app/
PROJECT_ROOT = BASE_DIR.parent               # Cambium/
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
CUSTOM_TOOLS_DIR = PROJECT_ROOT / "custom_tools"
SKILLS_ROOT = PROJECT_ROOT / ".skills"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
DB_PATH = DATA_DIR / "memory.db"


# ============================================================
# Sub-models
# ============================================================

class APIConfig(BaseModel):
    """LLM API configuration."""
    api_key: str = Field(default="", description="Primary API key")
    api_base_url: str = Field(default="https://api-inference.modelscope.cn/v1")
    api_model: str = Field(default="", description="Default model name")
    backup_api_key: str = ""
    backup_api_base_url: str = ""
    backup_api_model: str = ""

    # Sub-task (background sessions, Swarm)
    subtask_api_key: str = ""
    subtask_api_base_url: str = ""
    subtask_api_model: str = ""
    max_subtasks: int = Field(default=3, ge=1, le=20)

    # Memory API (reflection, extraction)
    memory_api_key: str = ""
    memory_api_base_url: str = ""
    memory_api_model: str = ""

    @field_validator("api_key", "backup_api_key", "subtask_api_key", "memory_api_key")
    @classmethod
    def strip_key(cls, v: str) -> str:
        return (v or "").strip()


class ChatConfig(BaseModel):
    """Chat / generation parameters."""
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=0, ge=0)
    max_tokens: int = Field(default=8192, ge=1, le=131072)
    thinking_budget: int = Field(default=0, ge=0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.15, ge=-2.0, le=2.0)
    enable_thinking: bool = False
    stop_sequences: str = ""


class MemoryConfig(BaseModel):
    """Memory system configuration."""
    enable_memory: bool = True
    memory_auto_extract: bool = False
    memory_auto_summary: bool = True
    memory_inject_count: int = Field(default=0, ge=0, le=50)

    # Advanced memory
    emotion_tracking_enabled: bool = True
    profile_auto_update: bool = True
    proactive_recall_enabled: bool = True

    # Background reflection
    background_reflection_enabled: bool = True
    background_reflection_trigger_msgs: int = Field(default=30, ge=1, le=500)
    background_reflection_interval_sec: int = Field(default=600, ge=60, le=86400)

    # Memory governance (SSGM)
    memory_governance_enabled: bool = True
    governance_auto_validate_interval_sec: int = Field(default=3600, ge=300, le=86400)

    # Knowledge graph + episodic auto-extraction
    kg_auto_extract: bool = True
    episodic_auto_extract: bool = True


class CompressionConfig(BaseModel):
    """Conversation compression."""
    compress_enabled: bool = True
    compress_threshold_tokens: int = Field(default=24000, ge=1000, le=200000)
    compress_keep_recent: int = Field(default=6, ge=1, le=50)


class ChatVectorsConfig(BaseModel):
    """Chat vectorization for semantic search."""
    chat_vectors_enabled: bool = True
    chat_vectors_search_top_k: int = Field(default=5, ge=1, le=50)


class RAGConfig(BaseModel):
    """RAG file retrieval."""
    rag_enabled: bool = False
    rag_api_key: str = ""
    rag_api_base_url: str = ""
    rag_api_model: str = ""
    rag_embedding_provider: Literal["local", "api"] = "local"
    rag_embedding_api_key: str = ""
    rag_embedding_api_base_url: str = ""
    rag_embedding_model: str = ""


class VectorStoreConfig(BaseModel):
    """Vector store backend."""
    vector_backend: Literal["chromadb", "tfidf"] = "chromadb"
    vector_search_top_k: int = Field(default=5, ge=1, le=50)


class MCPCConfig(BaseModel):
    """MCP server configuration."""
    mcp_enabled: bool = True


class SessionsConfig(BaseModel):
    """Background sessions."""
    sessions_enabled: bool = True
    cron_enabled: bool = True


class LifeLoopConfig(BaseModel):
    """Life Loop circadian rhythm."""
    life_loop_enabled: bool = True
    life_loop_catchup_enabled: bool = True
    life_loop_catchup_max_days: int = Field(default=7, ge=1, le=90)
    life_loop_daily_hour: int = Field(default=8, ge=0, le=23)


class SwarmConfig(BaseModel):
    """Swarm Task multi-agent collaboration."""
    swarm_enabled: bool = True
    swarm_engine: Literal["native", "langgraph", "autogen"] = "native"
    swarm_parallel: bool = True
    swarm_max_rounds: int = Field(default=3, ge=1, le=10)


class SecurityConfig(BaseModel):
    """Security configuration."""
    # Even for personal use, these are good defaults
    bind_host: str = "127.0.0.1"
    bind_port: int = Field(default=3000, ge=1, le=65535)
    cors_origins: str = ""  # comma-separated, empty = localhost only
    api_token: str = ""     # empty = no token required
    audit_log_enabled: bool = True


class AgentLoopConfig(BaseModel):
    """Agent Loop (CoALA + Claude Code)."""
    agent_loop_enabled: bool = True
    agent_loop_max_steps: int = Field(default=25, ge=1, le=100)
    agent_loop_max_context_chars: int = Field(default=120000, ge=10000, le=500000)
    agent_loop_permission_mode: Literal["plan", "reflect", "grow", "autonomous"] = "grow"


class ProactiveConfig(BaseModel):
    """Proactive engine."""
    proactive_enabled: bool = True
    proactive_silence_days_1: int = Field(default=3, ge=1, le=30)
    proactive_silence_days_2: int = Field(default=7, ge=2, le=60)
    proactive_silence_days_3: int = Field(default=30, ge=7, le=180)


class IdentityConfig(BaseModel):
    """Identity consistency (Identity Layer paper)."""
    identity_assessment_enabled: bool = True
    identity_assessment_interval_days: int = Field(default=7, ge=1, le=90)


class ThemeConfig(BaseModel):
    """UI theme."""
    theme_appearance: Literal["dark", "light"] = "dark"
    theme_contrast: Literal["default", "high"] = "default"


class AppConfig(BaseSettings):
    """Top-level application configuration.

    Loads from environment variables (CAMBIUM_ prefix) and .env file.
    Runtime overrides come from the SQLite settings table.
    """
    model_config = SettingsConfigDict(
        env_prefix="cambium_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # App metadata
    app_name: str = "Cambium"
    app_version: str = "2.1.0"
    ai_name: str = "Cambium"  # replaces hardcoded "CyanX AI"
    debug_mode: bool = False

    # Sub-configs (nested via CAMBIUM_API__API_KEY etc.)
    api: APIConfig = Field(default_factory=APIConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    chat_vectors: ChatVectorsConfig = Field(default_factory=ChatVectorsConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    mcp: MCPCConfig = Field(default_factory=MCPCConfig)
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    life_loop: LifeLoopConfig = Field(default_factory=LifeLoopConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    agent_loop: AgentLoopConfig = Field(default_factory=AgentLoopConfig)
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)
    identity: IdentityConfig = Field(default_factory=IdentityConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)


# ============================================================
# Singleton accessor
# ============================================================

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global AppConfig singleton."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reload_config() -> AppConfig:
    """Force reload config from environment (useful for tests)."""
    global _config
    _config = AppConfig()
    return _config


def ensure_directories():
    """Create all required directories if they don't exist."""
    for d in (DATA_DIR, UPLOAD_DIR, WORKSPACE_DIR, CUSTOM_TOOLS_DIR, SKILLS_ROOT, PLUGINS_ROOT):
        d.mkdir(parents=True, exist_ok=True)


# ============================================================
# SQLite settings table bridge
# ============================================================

def load_settings_from_db(db_path: Path) -> dict:
    """Load user-overridden settings from the SQLite settings table.
    Returns a flat dict of key→value, mirroring the legacy DEFAULT_SETTINGS structure.
    """
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}
    except Exception:
        return {}


def get_setting(key: str, default: str = "") -> str:
    """Get a single setting from the SQLite settings table.
    This is the bridge between the old flat-settings system and the new Pydantic config.
    """
    settings = load_settings_from_db(DB_PATH)
    return settings.get(key, default)
