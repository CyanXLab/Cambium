"""
API Provider Manager — 动态管理多个 API 供应商。

用户可以添加任意数量的 API 供应商（名称 + URL + Key + 模型列表），
然后每个功能（对话/记忆/认知/反思等）可以选择使用哪个供应商。

存储在 settings 表:
  - api_providers: JSON 数组 [{id, name, base_url, api_key, models: []}]
  - api_provider_assignments: JSON 对象 {chat: "provider_id", memory: "provider_id", ...}
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect


def get_providers(db_path: Path) -> List[Dict]:
    """获取所有 API 供应商配置。"""
    conn = safe_connect(db_path)
    row = conn.execute("SELECT value FROM settings WHERE key='api_providers'").fetchone()
    conn.close()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            pass
    return []


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
    """添加一个 API 供应商。"""
    providers = get_providers(db_path)
    pid = f"provider_{int(time.time())}_{len(providers)}"
    provider = {
        "id": pid,
        "name": name,
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "models": models or [],
        "created_at": int(time.time()),
    }
    providers.append(provider)
    save_providers(db_path, providers)
    return provider


def update_provider(db_path: Path, provider_id: str, **fields) -> Optional[Dict]:
    """更新供应商配置。"""
    providers = get_providers(db_path)
    for p in providers:
        if p["id"] == provider_id:
            for k, v in fields.items():
                if k in ("name", "base_url", "api_key", "models"):
                    p[k] = v
            save_providers(db_path, providers)
            return p
    return None


def delete_provider(db_path: Path, provider_id: str) -> bool:
    providers = get_providers(db_path)
    new_providers = [p for p in providers if p["id"] != provider_id]
    if len(new_providers) == len(providers):
        return False
    save_providers(db_path, new_providers)
    # 清除使用该供应商的分配
    assignments = get_assignments(db_path)
    for task, pid in list(assignments.items()):
        if pid == provider_id:
            del assignments[task]
    save_assignments(db_path, assignments)
    return True


def get_provider(db_path: Path, provider_id: str) -> Optional[Dict]:
    providers = get_providers(db_path)
    for p in providers:
        if p["id"] == provider_id:
            return p
    return None


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
    如果该功能分配了供应商，返回供应商配置；
    否则返回 fallback（通常是主 API 配置）。"""
    assignments = get_assignments(db_path)
    provider_id = assignments.get(task)
    if provider_id:
        provider = get_provider(db_path, provider_id)
        if provider:
            return {
                "api_base_url": provider["base_url"],
                "api_key": provider["api_key"],
                "api_model": provider["models"][0] if provider["models"] else "",
            }
    return fallback or {}


def get_provider_names(db_path: Path) -> List[Dict]:
    """获取所有供应商的 ID 和名称（用于下拉选择）。"""
    providers = get_providers(db_path)
    return [{"id": p["id"], "name": p["name"]} for p in providers]


# 功能列表（用于前端分配 UI）
TASK_LIST = [
    {"key": "chat", "label": "主对话"},
    {"key": "memory", "label": "记忆编辑/提取"},
    {"key": "cognitive", "label": "认知提取"},
    {"key": "reflection", "label": "反思"},
    {"key": "journal", "label": "日志起草"},
    {"key": "morning", "label": "晨报生成"},
    {"key": "resident", "label": "居民运行"},
    {"key": "title", "label": "标题生成"},
    {"key": "emotion", "label": "情感分析"},
    {"key": "swarm", "label": "Swarm 协作"},
]
