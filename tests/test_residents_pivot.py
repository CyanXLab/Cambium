"""
Tests for the Residents / Mornings / Pushback / Artifacts / Philosophy / Evolution / Discovery modules.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime


@pytest.fixture(scope="module")
def test_db_path():
    from app import migrations
    from app.db_utils import safe_connect
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = tmp_dir / "test.db"
    migrations.run_migrations(db_path)
    # Create settings table (needed by prompt_registry mirror)
    conn = safe_connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()
    yield db_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ===== Residents tests =====
def test_residents_builtin_creation(test_db_path):
    from app import residents
    n = residents.ensure_builtin_residents(test_db_path, "default")
    assert n == 7  # 7 built-in residents
    # Idempotent
    n2 = residents.ensure_builtin_residents(test_db_path, "default")
    assert n2 == 0
    items = residents.list_residents(test_db_path, "default")
    assert len(items) == 7
    names = [r["name"] for r in items]
    assert "Architect" in names
    assert "Critic" in names


def test_resident_crud(test_db_path):
    from app import residents
    r = residents.create_resident(
        test_db_path, "default",
        name="TestBot",
        role="custom",
        system_prompt="You are a test bot.",
        personality_traits={"rigor": 0.5, "curiosity": 0.9},
        triggers=[{"type": "manual"}],
        depends_on=[],
    )
    assert r["id"]
    assert r["name"] == "TestBot"
    fetched = residents.get_resident(test_db_path, r["id"])
    assert fetched["name"] == "TestBot"
    assert fetched["personality_traits"]["curiosity"] == 0.9
    # Update
    updated = residents.update_resident(test_db_path, r["id"], {"status": "paused"})
    assert updated["status"] == "paused"
    # Delete
    assert residents.delete_resident(test_db_path, r["id"])
    assert residents.get_resident(test_db_path, r["id"]) is None


def test_resident_set_concerns(test_db_path):
    from app import residents
    r = residents.create_resident(test_db_path, "default", name="ConcernBot")
    concerns = [
        {"title": "Inbox 积压", "why": "10 条未处理"},
        {"title": "目标缺失", "why": "今天没有目标"},
    ]
    assert residents.set_concerns(test_db_path, r["id"], concerns)
    fetched = residents.get_resident(test_db_path, r["id"])
    assert len(fetched["current_concerns"]) == 2
    assert fetched["current_concerns"][0]["title"] == "Inbox 积压"


def test_resident_find_triggered(test_db_path):
    from app import residents
    # Create a resident with a trigger
    r = residents.create_resident(
        test_db_path, "default",
        name="Triggered",
        triggers=[{"type": "artifact_created"}],
    )
    found = residents.find_triggered(test_db_path, "default", "artifact_created")
    assert any(x["id"] == r["id"] for x in found)
    not_found = residents.find_triggered(test_db_path, "default", "manual")
    # manual trigger residents may exist; just check our resident isn't there
    assert all(x["id"] != r["id"] for x in not_found)


def test_resident_stats(test_db_path):
    from app import residents
    residents.ensure_builtin_residents(test_db_path, "default")
    stats = residents.get_stats(test_db_path, "default")
    assert stats["total_residents"] >= 7
    assert stats["active_residents"] >= 7


# ===== Philosophy tests =====
def test_philosophy_seed(test_db_path):
    from app import philosophy
    n = philosophy.ensure_seed_philosophy(test_db_path, "default")
    assert n == 8  # 8 seed items
    # Idempotent
    n2 = philosophy.ensure_seed_philosophy(test_db_path, "default")
    assert n2 == 0
    items = philosophy.list_active(test_db_path, "default")
    assert len(items) >= 8


def test_philosophy_crud(test_db_path):
    from app import philosophy
    p = philosophy.create(
        test_db_path, "default",
        type_="principle",
        content="Test principle",
        rationale="For testing",
        confidence=0.7,
    )
    assert p["id"]
    fetched = philosophy.get(test_db_path, p["id"])
    assert fetched["content"] == "Test principle"
    assert fetched["confidence"] == 0.7
    # Update
    updated = philosophy.update(test_db_path, p["id"], {"confidence": 0.9})
    assert updated["confidence"] == 0.9
    # List by type
    principles = philosophy.list_by_type(test_db_path, "default", "principle")
    assert any(x["id"] == p["id"] for x in principles)
    # Retire
    assert philosophy.retire(test_db_path, p["id"])
    retired = philosophy.get(test_db_path, p["id"])
    assert retired["status"] == "retired"
    # Delete
    assert philosophy.delete(test_db_path, p["id"])


def test_philosophy_stats(test_db_path):
    from app import philosophy
    philosophy.ensure_seed_philosophy(test_db_path, "default")
    stats = philosophy.get_stats(test_db_path, "default")
    assert stats["total"] >= 8
    assert "by_type" in stats
    assert stats["principles"] >= 1


# ===== Artifacts tests =====
def test_artifact_crud(test_db_path):
    from app import artifacts
    a = artifacts.create(
        test_db_path, "default",
        type_="readme",
        title="Test README",
        content="# Test\n\nHello world.",
        tags=["test", "example"],
    )
    assert a["id"]
    assert a["version"] == 1
    fetched = artifacts.get(test_db_path, a["id"])
    assert fetched["title"] == "Test README"
    assert "test" in fetched["tags"]
    # New version
    v2 = artifacts.new_version(test_db_path, a["id"], "# Test v2\n\nUpdated.")
    assert v2["version"] == 2
    assert v2["parent_id"] == a["id"]
    # History
    history = artifacts.get_history(test_db_path, v2["id"])
    assert len(history) == 2
    assert history[0]["version"] == 2  # newest first
    assert history[1]["version"] == 1


def test_artifact_list_and_filter(test_db_path):
    from app import artifacts
    artifacts.create(test_db_path, "default", type_="code", title="Code 1", content="x")
    artifacts.create(test_db_path, "default", type_="note", title="Note 1", content="y")
    artifacts.create(test_db_path, "default", type_="code", title="Code 2", content="z")
    all_items = artifacts.list_artifacts(test_db_path, "default")
    assert len(all_items) >= 3
    code_only = artifacts.list_artifacts(test_db_path, "default", type_="code")
    assert all(a["type"] == "code" for a in code_only)
    assert len(code_only) >= 2


def test_artifact_stats(test_db_path):
    from app import artifacts
    stats = artifacts.get_stats(test_db_path, "default")
    assert "total" in stats
    assert "by_type" in stats
    assert "recent_7d" in stats


# ===== Evolution tests =====
def test_evolution_event(test_db_path):
    from app import evolution
    e = evolution.create_event(
        test_db_path, "default",
        type_="interest_shift",
        from_state="Memory",
        to_state="Identity",
        evidence="User stopped asking about memory, started asking about identity",
        confidence=0.8,
    )
    assert e["id"]
    fetched = evolution.get_event(test_db_path, e["id"])
    assert fetched["from_state"] == "Memory"
    assert fetched["to_state"] == "Identity"
    # Confirm
    assert evolution.confirm_event(test_db_path, e["id"])
    confirmed = evolution.get_event(test_db_path, e["id"])
    assert confirmed["status"] == "confirmed"
    # List
    events = evolution.list_events(test_db_path, "default", type_="interest_shift")
    assert any(x["id"] == e["id"] for x in events)


def test_evolution_curve(test_db_path):
    from app import evolution
    # Create a few events
    for i in range(3):
        evolution.create_event(
            test_db_path, "default",
            type_="interest_shift",
            from_state=f"State{i}",
            to_state=f"State{i+1}",
        )
    curve = evolution.get_evolution_curve(test_db_path, "default", type_="interest_shift", months=12)
    assert len(curve) >= 3


# ===== Discovery tests =====
def test_discovery_crud(test_db_path):
    from app import discovery
    d = discovery.create(
        test_db_path, "default",
        type_="pattern",
        title="Test pattern",
        content="User mentions X 5 times this week",
        confidence=0.7,
    )
    assert d["id"]
    fetched = discovery.get(test_db_path, d["id"])
    assert fetched["title"] == "Test pattern"
    assert fetched["status"] == "new"
    # Mark seen
    assert discovery.mark_seen(test_db_path, d["id"])
    seen = discovery.get(test_db_path, d["id"])
    assert seen["status"] == "seen"
    # Mark acted
    assert discovery.mark_acted(test_db_path, d["id"])
    # Dismiss another
    d2 = discovery.create(test_db_path, "default", type_="observation", title="Obs", content="...")
    assert discovery.dismiss(test_db_path, d2["id"])
    # List by date
    today = datetime.now().strftime("%Y-%m-%d")
    today_items = discovery.list_by_date(test_db_path, "default", today)
    assert len(today_items) >= 2


def test_discovery_stats(test_db_path):
    from app import discovery
    stats = discovery.get_stats(test_db_path, "default")
    assert "total" in stats
    assert "new_today" in stats
    assert "by_status" in stats


# ===== Pushback tests =====
def test_pushback_context(test_db_path):
    from app import pushback, philosophy
    philosophy.ensure_seed_philosophy(test_db_path, "default")
    ctx = pushback.build_pushback_system_prompt(test_db_path, "default")
    # Should contain philosophy items
    assert "原则" in ctx or "principle" in ctx.lower() or "信念" in ctx
    # Should contain at least one seed philosophy item
    assert "Continuity" in ctx or "Simple" in ctx or "Memory" in ctx


def test_pushback_detect_no_moments(test_db_path):
    """When there are no co-experience moments, detect returns empty related_moments."""
    from app import pushback
    result = pushback.detect_pushback_opportunities(test_db_path, "default", "Hello world")
    assert "related_moments" in result
    assert "memory_surface_context" in result
    assert isinstance(result["related_moments"], list)


# ===== Mornings tests =====
def test_morning_get_or_create(test_db_path):
    from app import mornings
    today = datetime.now().strftime("%Y-%m-%d")
    m = mornings.get_or_create(test_db_path, "default", today)
    assert m["date"] == today
    assert m["letter"] == ""  # empty by default
    # Get or create again returns same
    m2 = mornings.get_or_create(test_db_path, "default", today)
    assert m["id"] == m2["id"]


def test_morning_save_letter(test_db_path):
    from app import mornings
    today = datetime.now().strftime("%Y-%m-%d")
    m = mornings.save_letter(
        test_db_path, "default", today,
        letter="早安。今天我注意到...",
        concerns=[{"title": "Inbox 积压", "why": "10 条"}],
        growth_notes="我开始理解用户的兴趣",
        discovery_refs=[],
        artifact_refs=[],
        mood="thoughtful",
    )
    assert m["letter"].startswith("早安")
    assert len(m["concerns"]) == 1
    assert m["mood"] == "thoughtful"


def test_morning_list_recent(test_db_path):
    from app import mornings
    today = datetime.now().strftime("%Y-%m-%d")
    mornings.save_letter(test_db_path, "default", today, letter="test", concerns=[],
                         growth_notes="", discovery_refs=[], artifact_refs=[], mood="neutral")
    items = mornings.list_recent(test_db_path, "default", days=14)
    assert any(i["date"] == today for i in items)


def test_morning_mark_read(test_db_path):
    from app import mornings
    today = datetime.now().strftime("%Y-%m-%d")
    mornings.get_or_create(test_db_path, "default", today)
    assert mornings.mark_read(test_db_path, "default", today)
    m = mornings.get(test_db_path, "default", today)
    assert m["read_at"] is not None
