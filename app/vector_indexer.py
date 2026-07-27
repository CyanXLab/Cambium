"""
Universal Vector Indexer — 把所有有价值的信息都向量化。

不只是记忆和聊天记录，还包括：
  - Artifacts（作品）
  - Philosophy（原则）
  - Discoveries（发现）
  - Journals（日志）
  - Timeline events（时间线事件）
  - Co-experience moments（共同经历）
  - Self-goals（自主目标）

每次创建/更新这些数据时，自动同步到 vector_store。
搜索时可以跨类型搜索（"用户对架构的偏好" → 搜索记忆+作品+日志+原则）。
"""
from __future__ import annotations
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from app.db_utils import safe_connect


def index_artifact(db_path: Path, artifact_id: str, title: str, content: str,
                   artifact_type: str, tags: Optional[List[str]] = None):
    """索引一个作品到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"{title}\n\n{content[:2000]}"
        vs.add("artifacts", id=artifact_id, text=text,
               metadata={"type": artifact_type, "title": title,
                         "tags": ",".join(tags or [])})
    except Exception as e:
        print(f"[vector] index artifact failed: {e}")


def index_philosophy(db_path: Path, item_id: str, content: str,
                     rationale: str, ptype: str):
    """索引一条原则到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"{ptype}: {content}\n理由: {rationale}"
        vs.add("philosophy", id=item_id, text=text,
               metadata={"type": ptype})
    except Exception as e:
        print(f"[vector] index philosophy failed: {e}")


def index_discovery(db_path: Path, discovery_id: str, title: str,
                    content: str, dtype: str):
    """索引一条发现到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"{dtype}: {title}\n{content}"
        vs.add("discoveries", id=discovery_id, text=text,
               metadata={"type": dtype})
    except Exception as e:
        print(f"[vector] index discovery failed: {e}")


def index_journal(db_path: Path, date_str: str, content: str,
                  ai_draft: str = "", growth_notes: str = ""):
    """索引一篇日志到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"日志 {date_str}\n{content or ai_draft}\n{growth_notes}"
        vs.add("journals", id=f"journal_{date_str}", text=text,
               metadata={"date": date_str})
    except Exception as e:
        print(f"[vector] index journal failed: {e}")


def index_timeline_event(db_path: Path, event_id: str, title: str,
                         description: str, category: str):
    """索引一个时间线事件到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"[{category}] {title}\n{description}"
        vs.add("timeline", id=event_id, text=text,
               metadata={"category": category})
    except Exception as e:
        print(f"[vector] index timeline failed: {e}")


def index_co_experience(db_path: Path, moment_id: str, title: str,
                        story: str, moment_type: str):
    """索引一个共同经历到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"{title}\n{story}"
        vs.add("co_experience", id=moment_id, text=text,
               metadata={"type": moment_type})
    except Exception as e:
        print(f"[vector] index co_experience failed: {e}")


def index_self_goal(db_path: Path, goal_id: str, title: str,
                    description: str, reasoning: str):
    """索引一个自主目标到向量库。"""
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)
        text = f"{title}\n{description}\n{reasoning}"
        vs.add("self_goals", id=goal_id, text=text)
    except Exception as e:
        print(f"[vector] index self_goal failed: {e}")


def universal_search(db_path: Path, query: str, top_k: int = 10,
                     collections: Optional[List[str]] = None) -> List[Dict]:
    """跨所有集合搜索。

    collections: 指定要搜索的集合，None=搜索全部
    默认集合: memories, chat_vectors, artifacts, philosophy, discoveries,
             journals, timeline, co_experience, self_goals
    """
    try:
        from app.vector_store import get_vector_store
        vs = get_vector_store(db_path)

        all_collections = [
            "memories_default", "chat_vectors", "artifacts", "philosophy",
            "discoveries", "journals", "timeline", "co_experience", "self_goals",
        ]
        target_collections = collections or all_collections

        all_results = []
        for col in target_collections:
            try:
                results = vs.query(col, text=query, top_k=min(top_k, 5))
                for r in results:
                    r["collection"] = col
                    all_results.append(r)
            except Exception:
                continue

        # Sort by score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:top_k]
    except Exception as e:
        print(f"[vector] universal search failed: {e}")
        return []


def reindex_all(db_path: Path) -> Dict:
    """重新索引所有数据。"""
    stats = {"artifacts": 0, "philosophy": 0, "discoveries": 0,
             "journals": 0, "timeline": 0, "co_experience": 0}
    conn = safe_connect(db_path)
    conn.row_factory = __import__('sqlite3').Row

    # Artifacts
    try:
        rows = conn.execute("SELECT id, title, content, type, tags FROM artifacts").fetchall()
        for r in rows:
            tags = json.loads(r["tags"]) if r["tags"] else []
            index_artifact(db_path, r["id"], r["title"], r["content"], r["type"], tags)
            stats["artifacts"] += 1
    except Exception:
        pass

    # Philosophy
    try:
        rows = conn.execute("SELECT id, content, rationale, type FROM philosophy_items WHERE status='active'").fetchall()
        for r in rows:
            index_philosophy(db_path, r["id"], r["content"], r["rationale"], r["type"])
            stats["philosophy"] += 1
    except Exception:
        pass

    # Discoveries
    try:
        rows = conn.execute("SELECT id, title, content, type FROM discoveries").fetchall()
        for r in rows:
            index_discovery(db_path, r["id"], r["title"], r["content"], r["type"])
            stats["discoveries"] += 1
    except Exception:
        pass

    # Journals
    try:
        rows = conn.execute("SELECT date, content, ai_draft, growth_notes FROM journals WHERE content != ''").fetchall()
        for r in rows:
            index_journal(db_path, r["date"], r["content"], r["ai_draft"], r["growth_notes"])
            stats["journals"] += 1
    except Exception:
        pass

    # Timeline events
    try:
        rows = conn.execute("SELECT id, title, description, category FROM timeline_events").fetchall()
        for r in rows:
            index_timeline_event(db_path, r["id"], r["title"], r["description"], r["category"])
            stats["timeline"] += 1
    except Exception:
        pass

    # Co-experience
    try:
        rows = conn.execute("SELECT id, title, story, moment_type FROM co_experience_moments").fetchall()
        for r in rows:
            index_co_experience(db_path, r["id"], r["title"], r["story"], r["moment_type"])
            stats["co_experience"] += 1
    except Exception:
        pass

    conn.close()
    return stats
