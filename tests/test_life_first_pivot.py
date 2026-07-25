"""
Tests for the life-first pivot modules: inbox, journal, co_experience, daily_loop, prompt_registry.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, date, timedelta


@pytest.fixture(scope="module")
def test_db_path():
    """Create a temporary test database and run migrations."""
    from app import migrations
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = tmp_dir / "test.db"
    # Initialize all tables that exist in the main app
    from app.db_utils import safe_connect
    import sqlite3
    conn = safe_connect(db_path)
    # Run schema migrations
    migrations.run_migrations(db_path)
    # Create additional tables that the modules expect
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            content TEXT NOT NULL,
            layer TEXT NOT NULL DEFAULT 'short_term',
            importance INTEGER NOT NULL DEFAULT 30,
            category TEXT NOT NULL DEFAULT 'other',
            keywords TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'auto',
            decay_weight REAL NOT NULL DEFAULT 1.0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            last_accessed INTEGER NOT NULL,
            access_count INTEGER NOT NULL DEFAULT 0,
            conversation_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS long_term_goals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            goal TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            target_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            progress INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS timeline_events (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            occurred_at TEXT NOT NULL DEFAULT '',
            occurred_ts INTEGER,
            category TEXT NOT NULL DEFAULT 'milestone',
            emotional_valence TEXT NOT NULL DEFAULT 'neutral',
            significance INTEGER NOT NULL DEFAULT 50,
            parent_event TEXT,
            related_entities TEXT NOT NULL DEFAULT '[]',
            narrative TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            importance_weight REAL DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    conn.close()
    yield db_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ===== Inbox tests =====
def test_inbox_add_and_list(test_db_path):
    from app import inbox
    item = inbox.add_item(test_db_path, "default", "text", "hello world", title="test")
    assert item["id"]
    assert item["type"] == "text"
    assert item["content"] == "hello world"
    assert item["status"] == "pending"
    items = inbox.list_items(test_db_path, "default")
    assert any(i["id"] == item["id"] for i in items)


def test_inbox_auto_route(test_db_path):
    from app import inbox
    assert inbox.auto_route("https://arxiv.org/paper", "url") == "research"
    assert inbox.auto_route("todo: buy milk", "text") == "task"
    assert inbox.auto_route("想要学习 Rust", "text") == "goal"
    assert inbox.auto_route("remember: I love coffee", "text") == "memory"
    assert inbox.auto_route("just a thought", "text") == "note"


def test_inbox_process_and_archive(test_db_path):
    from app import inbox
    item = inbox.add_item(test_db_path, "default", "todo", "do homework")
    assert inbox.process_item(test_db_path, item["id"], "task")
    updated = inbox.get_item(test_db_path, item["id"])
    assert updated["status"] == "processed"
    assert updated["destination"] == "task"

    item2 = inbox.add_item(test_db_path, "default", "note", "random note")
    assert inbox.archive_item(test_db_path, item2["id"])
    archived = inbox.get_item(test_db_path, item2["id"])
    assert archived["status"] == "archived"


def test_inbox_stats(test_db_path):
    from app import inbox
    stats = inbox.get_stats(test_db_path, "default")
    assert "pending" in stats
    assert "total" in stats
    assert stats["total"] >= stats["pending"]


# ===== Journal tests =====
def test_journal_get_or_create(test_db_path):
    from app import journal
    today = datetime.now().strftime("%Y-%m-%d")
    j = journal.get_or_create(test_db_path, "default")
    assert j["date"] == today
    assert j["content"] == ""
    # Calling again returns the same record
    j2 = journal.get_or_create(test_db_path, "default")
    assert j["id"] == j2["id"]


def test_journal_update_content(test_db_path):
    from app import journal
    j = journal.update_content(test_db_path, "default",
                                datetime.now().strftime("%Y-%m-%d"),
                                "Today I worked on tests.")
    assert j["content"] == "Today I worked on tests."
    assert j["is_auto_generated"] == 0


def test_journal_set_ai_draft(test_db_path):
    from app import journal
    today = datetime.now().strftime("%Y-%m-%d")
    j = journal.set_ai_draft(
        test_db_path, "default", today,
        draft="AI 起草的日志内容...",
        summary="今天主要写测试",
        emotional_tone="focused",
        highlights=["测试 1", "测试 2"],
    )
    assert j["ai_draft"] == "AI 起草的日志内容..."
    assert j["ai_summary"] == "今天主要写测试"
    assert j["emotional_tone"] == "focused"
    assert "测试 1" in j["highlights"]
    assert j["is_auto_generated"] == 1


def test_journal_streak(test_db_path):
    from app import journal
    today = datetime.now().strftime("%Y-%m-%d")
    journal.update_content(test_db_path, "default", today, "today's entry")
    streak = journal.get_streak(test_db_path, "default")
    assert streak["current_streak"] >= 1
    assert streak["total_entries"] >= 1


# ===== Co-experience tests =====
def test_co_experience_create_and_list(test_db_path):
    from app import co_experience
    m = co_experience.create_moment(
        test_db_path, "default",
        title="First test moment",
        story="We tested co-experience together for the first time.",
        moment_type="first",
        emotional_weight=0.8,
    )
    assert m["id"]
    assert m["emotional_weight"] == 0.8
    moments = co_experience.list_moments(test_db_path, "default")
    assert any(x["id"] == m["id"] for x in moments)


def test_co_experience_surface(test_db_path):
    from app import co_experience
    # Create several moments
    for i in range(3):
        co_experience.create_moment(
            test_db_path, "default",
            title=f"Moment {i}",
            story=f"Story {i}",
            emotional_weight=0.5 + i * 0.1,
        )
    surfaced = co_experience.surface_for_today(test_db_path, "default")
    assert surfaced is not None
    # After surface_for_today, the surfaced moment should have surfaced_count >= 1 in DB.
    # (The returned dict was captured BEFORE mark_surfaced, so re-fetch to verify.)
    re_fetched = co_experience.get_moment(test_db_path, surfaced["id"])
    assert re_fetched["surfaced_count"] >= 1
    assert re_fetched["last_surfaced_at"] is not None


def test_co_experience_harvest_from_timeline(test_db_path):
    from app import co_experience
    import time
    # Insert a high-importance timeline event
    from app.db_utils import safe_connect
    import sqlite3
    conn = safe_connect(test_db_path)
    now = int(time.time())
    conn.execute(
        """INSERT INTO timeline_events
           (id, user_id, title, description, occurred_at, occurred_ts,
            category, emotional_valence, significance, related_entities,
            narrative, created_at, importance_weight)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("tl-test-1", "default", "First release", "v0.1 release of Cambium",
         "", now, "milestone", "happy", 95, "[]", "", now, 0.9)
    )
    conn.commit()
    conn.close()
    # Harvest
    count = co_experience.harvest_from_timeline(test_db_path, "default")
    assert count >= 1
    # Idempotent — running again should not re-create
    count2 = co_experience.harvest_from_timeline(test_db_path, "default")
    assert count2 == 0


# ===== Daily Loop tests =====
def test_daily_briefing(test_db_path):
    from app import daily_loop
    b = daily_loop.build_briefing(test_db_path, "default")
    assert "greeting" in b
    assert "date" in b
    assert "yesterday_done" in b
    assert "today_goals" in b
    assert "inbox_pending" in b
    assert "journal" in b
    assert "recent_activity" in b


def test_daily_briefing_greeting_time(test_db_path):
    from app import daily_loop
    b = daily_loop.build_briefing(test_db_path, "default")
    h = datetime.now().hour
    if h < 5:
        assert "深夜" in b["greeting"] or b["greeting"]  # may not have name
    elif h < 11:
        assert "早上好" in b["greeting"]
    elif h < 14:
        assert "中午好" in b["greeting"]
    # etc.


# ===== Prompt Registry tests =====
def test_prompt_registry_list(test_db_path):
    from app import prompt_registry
    prompts = prompt_registry.list_prompts()
    assert len(prompts) >= 13
    # Should have at least: system, memory, cognitive, reflection, identity, profile, journal
    categories = {p["category"] for p in prompts}
    assert "system" in categories
    assert "memory" in categories
    assert "journal" in categories


def test_prompt_registry_set_and_get(test_db_path):
    from app import prompt_registry
    # Set a custom prompt
    ok = prompt_registry.set_prompt(test_db_path, "prompt_journal_draft", "Custom journal prompt v1")
    assert ok
    p = prompt_registry.get_prompt_with_meta(test_db_path, "prompt_journal_draft")
    assert p["content"] == "Custom journal prompt v1"
    assert p["is_default"] is False

    # Reset
    ok = prompt_registry.reset_prompt(test_db_path, "prompt_journal_draft")
    assert ok
    p = prompt_registry.get_prompt_with_meta(test_db_path, "prompt_journal_draft")
    assert p["is_default"] is True
    assert p["content"] == p["default"]


def test_prompt_registry_mirrors_to_settings(test_db_path):
    """Setting a prompt should also mirror it to the settings table."""
    from app import prompt_registry
    from app.db_utils import safe_connect
    import sqlite3
    ok = prompt_registry.set_prompt(test_db_path, "prompt_journal_draft", "Mirror test value")
    assert ok
    # Check settings table
    conn = safe_connect(test_db_path)
    cur = conn.execute(
        "SELECT value FROM settings WHERE key=?", ("prompt_journal_draft",)
    ).fetchone()
    conn.close()
    assert cur is not None
    assert cur[0] == "Mirror test value"


def test_prompt_registry_stats(test_db_path):
    from app import prompt_registry
    stats = prompt_registry.get_stats(test_db_path)
    assert stats["total"] >= 13
    assert stats["customized"] + stats["default"] == stats["total"]
    assert "categories" in stats
