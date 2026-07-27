"""
API Provider Manager — 动态管理多个 API 供应商。

用户可以添加任意数量的 API 供应商（名称 + URL + Key + 模型列表），
然后每个功能（对话/记忆/认知/反思等）可以选择使用哪个供应商。

主 API（id="main"）：
  - 不可删除，但可编辑
  - 负责核心功能：对话、推理、难度高的任务
  - 默认所有功能都使用主 API，除非显式分配其他供应商

其他供应商：
  - 可添加/删除
  - 用于浪费 token 的、简单的、决定性的功能
  - 每个功能可通过下拉框选择使用哪个供应商

存储在 settings 表:
  - api_providers: JSON 数组 [{id, name, base_url, api_key, models: [], is_main: bool}]
  - api_provider_assignments: JSON 对象 {chat: "provider_id", memory: "provider_id", ...}
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect
from app.logging_config import get_logger

log = get_logger(__name__)

# 主 API 的固定 ID
MAIN_PROVIDER_ID = "main"


def get_providers(db_path: Path) -> List[Dict]:
    """获取所有 API 供应商配置。

    主 API 始终在列表首位（如果不存在会自动创建空壳）。
    """
    conn = safe_connect(db_path)
    row = conn.execute("SELECT value FROM settings WHERE key='api_providers'").fetchone()
    conn.close()
    providers: List[Dict] = []
    if row and row[0]:
        try:
            providers = json.loads(row[0])
        except Exception:
            providers = []

    # Ensure main provider exists
    if not any(p.get("id") == MAIN_PROVIDER_ID for p in providers):
        main_provider = {
            "id": MAIN_PROVIDER_ID,
            "name": "主 API",
            "base_url": "",
            "api_key": "",
            "models": [],
            "is_main": True,
            "created_at": int(time.time()),
        }
        providers.insert(0, main_provider)
        save_providers(db_path, providers)
    else:
        # Ensure is_main flag is set
        for p in providers:
            if p.get("id") == MAIN_PROVIDER_ID:
                p["is_main"] = True
                break

    return providers


def save_providers(db_path: Path, providers: List[Dict]):
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('api_providers', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(providers, ensure_ascii=False),)
    )
    conn.commit()
    conn.close()


def add_provider(db_path: Path, name: str, base_url: str, api_key: str,
                 models: Optional[List[str]] = None) -> Dict:
    """添加一个 API 供应商（非主 API）。"""
    providers = get_providers(db_path)
    pid = f"provider_{int(time.time())}_{len(providers)}"
    provider = {
        "id": pid,
        "name": name,
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "models": models or [],
        "is_main": False,
        "created_at": int(time.time()),
    }
    providers.append(provider)
    save_providers(db_path, providers)
    log.info("provider.added", extra={"id": pid, "name": name})
    return provider


def update_provider(db_path: Path, provider_id: str, **fields) -> Optional[Dict]:
    """更新供应商配置。主 API 也可编辑。"""
    providers = get_providers(db_path)
    for p in providers:
        if p["id"] == provider_id:
            for k, v in fields.items():
                if k in ("name", "base_url", "api_key", "models"):
                    p[k] = v
            save_providers(db_path, providers)
            log.info("provider.updated", extra={"id": provider_id})
            return p
    return None


def delete_provider(db_path: Path, provider_id: str) -> bool:
    """删除供应商。主 API 不可删除。"""
    if provider_id == MAIN_PROVIDER_ID:
        log.warning("provider.delete_main_blocked", extra={"id": provider_id})
        return False
    providers = get_providers(db_path)
    new_providers = [p for p in providers if p["id"] != provider_id]
    if len(new_providers) == len(providers):
        return False
    save_providers(db_path, new_providers)
    # 清除使用该供应商的分配（回退到主 API）
    assignments = get_assignments(db_path)
    for task, pid in list(assignments.items()):
        if pid == provider_id:
            del assignments[task]
    save_assignments(db_path, assignments)
    log.info("provider.deleted", extra={"id": provider_id})
    return True


def get_provider(db_path: Path, provider_id: str) -> Optional[Dict]:
    providers = get_providers(db_path)
    for p in providers:
        if p["id"] == provider_id:
            return p
    return None


def get_main_provider(db_path: Path) -> Optional[Dict]:
    """获取主 API 配置。"""
    return get_provider(db_path, MAIN_PROVIDER_ID)


def get_assignments(db_path: Path) -> Dict[str, str]:
    """获取功能到供应商的分配。{task: provider_id}"""
    conn = safe_connect(db_path)
    row = conn.execute("SELECT value FROM settings WHERE key='api_provider_assignments'").fetchone()
    conn.close()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            pass
    return {}


def save_assignments(db_path: Path, assignments: Dict[str, str]):
    conn = safe_connect(db_path)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('api_provider_assignments', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(assignments, ensure_ascii=False),)
    )
    conn.commit()
    conn.close()


def set_assignment(db_path: Path, task: str, provider_id: str):
    """设置某个功能使用哪个供应商。"""
    assignments = get_assignments(db_path)
    assignments[task] = provider_id
    save_assignments(db_path, assignments)


def get_api_config_for_task(db_path: Path, task: str, fallback: Optional[Dict] = None) -> Dict:
    """获取某个功能的 API 配置。

    优先级：
      1. 该功能分配的供应商
      2. 主 API
      3. fallback（通常是 settings 中的 api_key/api_base_url/api_model）
    """
    assignments = get_assignments(db_path)
    provider_id = assignments.get(task)

    # If assigned to a specific provider, use it
    if provider_id and provider_id != MAIN_PROVIDER_ID:
        provider = get_provider(db_path, provider_id)
        if provider and provider.get("api_key"):
            return {
                "api_base_url": provider["base_url"],
                "api_key": provider["api_key"],
                "api_model": provider["models"][0] if provider["models"] else "",
            }

    # Try main provider
    main = get_main_provider(db_path)
    if main and main.get("api_key"):
        return {
            "api_base_url": main["base_url"],
            "api_key": main["api_key"],
            "api_model": main["models"][0] if main["models"] else "",
        }

    # Fall back to legacy settings
    return fallback or {}


def get_provider_names(db_path: Path) -> List[Dict]:
    """获取所有供应商的 ID 和名称（用于下拉选择）。

    主 API 标记为 "主 API (name)"，其他显示名称。
    """
    providers = get_providers(db_path)
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "is_main": p.get("is_main", False),
        }
        for p in providers
    ]


# 功能列表（用于前端分配 UI）
# 主对话（chat）始终使用主 API，不在列表中（强制不可改）
TASK_LIST = [
    {"key": "memory", "label": "记忆编辑/提取", "description": "从对话中提取记忆，编辑摘要"},
    {"key": "cognitive", "label": "认知提取", "description": "身份/时间线/叙事等认知更新"},
    {"key": "reflection", "label": "反思", "description": "周期性反思与知识图谱/情节提取"},
    {"key": "journal", "label": "日志起草", "description": "AI 辅助日志草稿"},
    {"key": "morning", "label": "晨报生成", "description": "每日 AI 信件"},
    {"key": "resident", "label": "居民运行", "description": "7 个居民的独立任务"},
    {"key": "title", "label": "标题生成", "description": "对话标题自动生成"},
    {"key": "emotion", "label": "情感分析", "description": "用户消息情绪识别"},
    {"key": "swarm", "label": "Swarm 协作", "description": "多 Agent 任务协作"},
    {"key": "greeting", "label": "问候语", "description": "AI 主动开场白"},
    {"key": "discovery", "label": "每日发现", "description": "每日惊喜生成"},
    {"key": "meta_cognition", "label": "元认知自检", "description": "回复后自检"},
]
