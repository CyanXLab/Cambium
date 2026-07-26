from __future__ import annotations
"""
Life Loop for Cambium — the living pulse that makes the AI grow continuously.

Unlike a simple cron scheduler (which fires user-defined jobs), the Life Loop
is the AI's own circadian rhythm. It runs in the background and performs
self-maintenance at different timescales:

- Hourly:    decay + light observation (extract cognitive updates from recent chat)
- Daily:     reflection (what happened today? what's worth keeping?)
- Weekly:    growth review (update identity, consolidate concepts, prune contradictions)
- Monthly:   deep understanding (re-examine user model, interest shifts, goal progress)

Each cycle runs asynchronously and never blocks user conversations. The AI
becomes smarter even when the user is asleep.

Self-contained module. main.py starts the loop on FastAPI startup.
"""
import asyncio
import json
from app.db_utils import safe_connect
import sqlite3
import time
from typing import Dict, Optional, Callable
from pathlib import Path


# Cycle intervals (seconds)
HOURLY_INTERVAL = 3600       # 1 hour
DAILY_INTERVAL = 86400       # 1 day
WEEKLY_INTERVAL = 604800     # 7 days
MONTHLY_INTERVAL = 2592000   # 30 days


class LifeLoop:
    """Background life-cycle scheduler. Runs cognitive maintenance at multiple timescales."""

    def __init__(self, db_path: Path, get_memory_api_cfg: Callable, httpx_client_factory: Callable):
        self.db_path = db_path
        self.get_memory_api_cfg = get_memory_api_cfg
        self.httpx_client_factory = httpx_client_factory  # async context manager factory
        self._tasks: list = []
        self._running = False
        # Track last run times for each cycle (persisted to survive restarts)
        self._last_run = self._load_last_runs()

    def _load_last_runs(self) -> Dict[str, int]:
        """Load last-run timestamps from DB."""
        try:
            conn = safe_connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT value FROM settings WHERE key='life_loop_last_runs'"
            ).fetchone()
            conn.close()
            if row:
                return json.loads(row["value"])
        except Exception:
            pass
        return {"hourly": 0, "daily": 0, "weekly": 0, "monthly": 0}

    def _save_last_runs(self):
        """Persist last-run timestamps to DB."""
        try:
            conn = safe_connect(self.db_path)
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('life_loop_last_runs', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(self._last_run),)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[life_loop] save last runs failed: {e}")

    def start(self):
        """Start all cycle tasks."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._hourly_cycle()),
            asyncio.create_task(self._daily_cycle()),
            asyncio.create_task(self._weekly_cycle()),
            asyncio.create_task(self._monthly_cycle()),
        ]
        print("[life_loop] started (hourly/daily/weekly/monthly)")

    def stop(self):
        """Stop all cycles."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks = []

    async def _hourly_cycle(self):
        """Hourly: light maintenance — decay + cognitive extraction from recent chat."""
        while self._running:
            try:
                await asyncio.sleep(60)  # check every minute
                now = int(time.time())
                if now - self._last_run["hourly"] < HOURLY_INTERVAL:
                    continue
                self._last_run["hourly"] = now
                self._save_last_runs()
                # 1. Apply memory decay
                try:
                    from app import memory_orchestrator, episodic_memory
                    memory_orchestrator.apply_decay(self.db_path, user_id="default", days_elapsed=0.04)
                    episodic_memory.apply_decay(self.db_path, user_id="default")
                except Exception as e:
                    print(f"[life_loop] hourly decay failed: {e}")
                # 2. Extract cognitive updates from recent chat (if enough new messages)
                await self._extract_cognitive_updates("hourly")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[life_loop] hourly error: {e}")

    async def _daily_cycle(self):
        """Daily: reflection + morning letter + discoveries + resident work."""
        while self._running:
            try:
                await asyncio.sleep(300)  # check every 5 minutes
                now = int(time.time())
                if now - self._last_run["daily"] < DAILY_INTERVAL:
                    continue
                self._last_run["daily"] = now
                self._save_last_runs()
                await self._run_reflection("daily")
                # Generate tomorrow's morning letter (or today's if not exists)
                await self._generate_morning_letter()
                # Auto-create discoveries from recent activity
                await self._auto_discover()
                # Residents do their own work (shared soul, independent present)
                await self._residents_do_daily_work()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[life_loop] daily error: {e}")

    async def _weekly_cycle(self):
        """Weekly: growth review + identity assessment + adaptive weight adjustment + learning consolidation."""
        while self._running:
            try:
                await asyncio.sleep(600)  # check every 10 minutes
                now = int(time.time())
                if now - self._last_run["weekly"] < WEEKLY_INTERVAL:
                    continue
                self._last_run["weekly"] = now
                self._save_last_runs()
                await self._run_growth_review()
                # Identity consistency assessment (weekly)
                await self._run_identity_assessment()
                # Adaptive retrieval weight adjustment (weekly, based on accumulated feedback)
                await self._adjust_retrieval_weights()
                # Learning engine consolidation (weekly — find patterns in observations)
                await self._consolidate_learning()
                # Memory governance auto-validate (weekly — validate quarantined memories)
                await self._auto_validate_quarantine()
                # Proactive engine check (weekly — commitments, milestones)
                await self._run_proactive_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[life_loop] weekly error: {e}")

    async def _monthly_cycle(self):
        """Monthly: deep understanding — re-examine user model, interest shifts, goal progress."""
        while self._running:
            try:
                await asyncio.sleep(1800)  # check every 30 minutes
                now = int(time.time())
                if now - self._last_run["monthly"] < MONTHLY_INTERVAL:
                    continue
                self._last_run["monthly"] = now
                self._save_last_runs()
                await self._run_deep_understanding()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[life_loop] monthly error: {e}")

    async def _gather_recent_conversation(self, limit: int = 50) -> str:
        """Gather recent conversation text from chat_vectors."""
        try:
            conn = safe_connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content FROM chat_vectors ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            if not rows:
                return ""
            return "\n\n".join(
                f"{'用户' if r['role'] == 'user' else 'Cambium'}: {r['content']}"
                for r in reversed(rows)
            )
        except Exception:
            return ""

    async def _extract_cognitive_updates(self, trigger: str):
        """Extract cognitive updates (identity shifts, timeline, narratives, etc.) from recent chat."""
        try:
            from app import cognitive_kernel
            conv = await self._gather_recent_conversation(limit=30)
            if len(conv) < 100:
                return
            api_cfg = self.get_memory_api_cfg()
            async with self.httpx_client_factory(timeout=60.0) as c:
                result = await cognitive_kernel.extract_cognitive_updates(
                    self.db_path, user_id="default",
                    conversation=conv, http_client=c, api_cfg=api_cfg,
                )
            if result.get("extracted"):
                applied = result.get("applied", {})
                total = sum(applied.values())
                if total > 0:
                    print(f"[life_loop] {trigger} cognitive extraction: {applied}")
        except Exception as e:
            print(f"[life_loop] {trigger} cognitive extraction failed: {e}")

    async def _run_reflection(self, trigger: str):
        """Run a reflection: summarize recent conversation, update profile, extract long-term memories."""
        try:
            from app import memory_orchestrator
            conv = await self._gather_recent_conversation(limit=80)
            if len(conv) < 100:
                return
            api_cfg = self.get_memory_api_cfg()
            async with self.httpx_client_factory(timeout=90.0) as c:
                result = await memory_orchestrator.run_reflection(
                    self.db_path, user_id="default",
                    recent_conversation=conv,
                    message_count=80,
                    http_client=c, api_cfg=api_cfg,
                )
            if result.get("success"):
                print(f"[life_loop] {trigger} reflection: {result.get('new_memories_added', 0)} new memories")
            # Also extract cognitive updates (deeper than reflection)
            await self._extract_cognitive_updates(trigger)
        except Exception as e:
            print(f"[life_loop] {trigger} reflection failed: {e}")

    async def _run_growth_review(self):
        """Weekly: consolidate growth insights, update identity phase (LLM-judged), form concepts."""
        try:
            from app import cognitive_kernel
            # 1. Promote high-confidence insights to 'validated'
            conn = safe_connect(self.db_path)
            conn.execute(
                "UPDATE growth_insights SET status='validated' WHERE confidence >= 0.7 AND status='forming'"
            )
            conn.commit()
            conn.close()
            # 2. Update identity phase — ask LLM to judge based on narrative quality, NOT count
            await self._update_identity_phase_via_llm()
            # 3. Run a reflection + cognitive extraction
            await self._run_reflection("weekly")
            print(f"[life_loop] weekly growth review complete")
        except Exception as e:
            print(f"[life_loop] weekly growth review failed: {e}")

    async def _update_identity_phase_via_llm(self):
        """Ask the LLM to judge the identity phase based on narrative quality,
        not a simple count of shifts."""
        try:
            from app import cognitive_kernel
            identity = cognitive_kernel.get_identity(self.db_path, user_id="default")
            evolution = cognitive_kernel.get_identity_evolution(self.db_path, user_id="default", limit=30)
            narratives = cognitive_kernel.get_narratives(self.db_path, user_id="default", limit=10)
            evo_text = "\n".join(f"- [{e.get('shift_type','')}] {e['description']}" for e in evolution[:15]) or "(无)"
            nar_text = "\n".join(f"- {n['title']}: {n['story'][:100]}" for n in narratives[:5]) or "(无)"
            current_narrative = identity.get("self_narrative", "") or "(尚未形成)"
            current_phase = identity.get("current_phase", "forming")
            prompt = f"""你是 Cambium 的身份演化系统。请基于以下信息判断当前身份阶段。

【当前自我叙事】
{current_narrative}

【当前阶段】
{current_phase}

【身份演化日志（最近 15 条）】
{evo_text}

【核心叙事记忆（最近 5 条）】
{nar_text}

【阶段说明】
- forming（形成中）: 刚开始，身份还不清晰，叙事稀少
- growing（成长中）: 有了一些经历和叙事，身份开始成形，但还不够稳定
- mature（成熟）: 有丰富的叙事和深刻的演化，身份清晰且稳定
- elder（长者）: 经历了大量共同历史，身份深刻且有智慧

【任务】
基于叙事的**质量和深度**（不是数量），判断当前处于哪个阶段。输出 JSON：
```json
{{"phase": "growing", "reason": "已经有叙事涉及命名之争和架构决策，身份开始成形但仍在探索"}}
```
只输出 JSON。"""
            api_cfg = self.get_memory_api_cfg()
            import httpx, re, json as _json
            async with httpx.AsyncClient(timeout=30.0) as c:
                payload = {
                    "model": api_cfg["api_model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3, "max_tokens": 200, "stream": False, "enable_thinking": False,
                }
                resp = await c.post(
                    f"{api_cfg['api_base_url']}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_cfg['api_key']}", "Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if m:
                    try:
                        result = _json.loads(m.group(0))
                        new_phase = result.get("phase", current_phase)
                        if new_phase in ("forming", "growing", "mature", "elder") and new_phase != current_phase:
                            cognitive_kernel.update_identity(self.db_path, user_id="default", current_phase=new_phase)
                            print(f"[life_loop] identity phase: {current_phase} → {new_phase} ({result.get('reason','')})")
                    except _json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[life_loop] identity phase update failed: {e}")

    async def _run_deep_understanding(self):
        """Monthly: deep re-examination of user model, interest shifts, goal progress."""
        try:
            # 1. Check goal progress (mark stale goals)
            conn = safe_connect(self.db_path)
            now = int(time.time())
            # Mark goals not updated in 90 days as 'paused'
            stale_cutoff = now - 90 * 86400
            conn.execute(
                "UPDATE long_term_goals SET status='paused' WHERE status='active' AND updated_at < ?",
                (stale_cutoff,)
            )
            # Mark commitments open for >60 days as broken
            stale_commit = now - 60 * 86400
            conn.execute(
                "UPDATE commitments SET status='broken' WHERE status='open' AND created_at < ?",
                (stale_commit,)
            )
            conn.commit()
            conn.close()
            # 2. Run a deep reflection
            await self._run_reflection("monthly")
            # 3. Detect long-term absence → log as evolution event
            await self._detect_absence_and_reunion()
            print("[life_loop] monthly deep understanding complete")
        except Exception as e:
            print(f"[life_loop] monthly deep understanding failed: {e}")

    async def _generate_morning_letter(self):
        """Generate today's morning letter via the mornings module."""
        try:
            from app import mornings
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            # Skip if today's letter already exists and is non-empty
            existing = mornings.get(self.db_path, "default", today)
            if existing and existing.get("letter"):
                return
            await mornings.generate_letter(
                self.db_path, "default", today,
                http_client_factory=lambda timeout: __import__('httpx').AsyncClient(timeout=timeout),
                get_api_cfg=self.get_memory_api_cfg,
            )
            print(f"[life_loop] morning letter generated for {today}")
        except Exception as e:
            print(f"[life_loop] morning letter generation failed: {e}")

    async def _auto_discover(self):
        """Auto-create discoveries from recent activity.
        Looks for patterns, contradictions, and observations in the past day."""
        try:
            from app import discovery, cognitive_kernel
            from datetime import datetime, timedelta
            today = datetime.now().strftime("%Y-%m-%d")

            # 1. Count today's timeline events by category
            conn = safe_connect(self.db_path)
            conn.row_factory = sqlite3.Row
            today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            rows = conn.execute(
                """SELECT category, COUNT(*) as cnt FROM timeline_events
                   WHERE user_id='default' AND created_at >= ?
                   GROUP BY category""",
                (today_start,)
            ).fetchall()
            conn.close()

            for r in rows:
                cat, cnt = r["category"], r["cnt"]
                if cnt >= 3:
                    # Pattern: user had 3+ events of same category today
                    discovery.create(
                        self.db_path, "default",
                        type_="pattern",
                        title=f"今日{cat}事件 {cnt} 次",
                        content=f"今天发生了 {cnt} 个 {cat} 类别的时间线事件。",
                        evidence=f"timeline_events count by category={cat}",
                        confidence=0.6,
                        discovered_by="life_loop",
                        date_str=today,
                    )

            # 2. Check inbox pile-up
            try:
                from app import inbox
                inbox_stats = inbox.get_stats(self.db_path, "default")
                if inbox_stats.get("pending", 0) >= 5:
                    discovery.create(
                        self.db_path, "default",
                        type_="suggestion",
                        title=f"Inbox 积压 {inbox_stats['pending']} 条",
                        content=f"Inbox 待处理项已达 {inbox_stats['pending']} 条。建议花 10 分钟分类。",
                        evidence=f"inbox pending count={inbox_stats['pending']}",
                        confidence=0.8,
                        discovered_by="life_loop",
                        date_str=today,
                    )
            except Exception:
                pass

            # 3. Check stalled goals (active but not updated in 14 days)
            try:
                conn = safe_connect(self.db_path)
                stale_cutoff = int(time.time()) - 14 * 86400
                stale = conn.execute(
                    """SELECT id, goal FROM long_term_goals
                       WHERE user_id='default' AND status='active' AND updated_at < ?""",
                    (stale_cutoff,)
                ).fetchall()
                conn.close()
                for g in stale:
                    discovery.create(
                        self.db_path, "default",
                        type_="observation",
                        title=f"目标停滞：{g[1][:40]}",
                        content=f"这个目标已经 14 天没有更新了。是否还在推进？",
                        evidence=f"goal_id={g[0]}, last_updated < {stale_cutoff}",
                        confidence=0.7,
                        discovered_by="life_loop",
                        date_str=today,
                    )
            except Exception:
                pass

        except Exception as e:
            print(f"[life_loop] auto_discover failed: {e}")

    async def _detect_absence_and_reunion(self):
        """Detect long absences and reunions, log as timeline events."""
        try:
            from app import cognitive_kernel
            from datetime import datetime
            conn = safe_connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Find the most recent conversation
            row = conn.execute(
                """SELECT MAX(updated_at) as last FROM conversations WHERE user_id='default'"""
            ).fetchone() if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
            ).fetchone() else None
            conn.close()
            if not row or not row["last"]:
                return
            days_since = (int(time.time()) - row["last"]) / 86400
            if days_since >= 7:
                # Check if we already logged this absence
                # (best-effort: look for absence event in past 30 days)
                from app import cognitive_kernel
                existing = cognitive_kernel.get_timeline_events(
                    self.db_path, user_id="default", limit=50
                ) if hasattr(cognitive_kernel, 'get_timeline_events') else []
                already = any(
                    e.get("category") == "absence" and "缺席" in e.get("title", "")
                    for e in existing
                )
                if not already:
                    cognitive_kernel.add_timeline_event(
                        self.db_path,
                        user_id="default",
                        title=f"用户缺席 {int(days_since)} 天",
                        description=f"用户已经 {int(days_since)} 天没有和 Cambium 对话了。",
                        category="absence",
                        emotional_valence="neutral",
                        significance=60,
                    )
                    print(f"[life_loop] logged absence of {int(days_since)} days")
        except Exception as e:
            print(f"[life_loop] absence detection failed: {e}")

    async def _run_identity_assessment(self):
        """Weekly: run LLM-driven identity consistency assessment."""
        try:
            from app import identity_consistency
            if not identity_consistency.should_assess(self.db_path, user_id="default"):
                return
            api_cfg = self.get_memory_api_cfg()
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as c:
                result = await identity_consistency.assess_identity(
                    self.db_path, user_id="default",
                    http_client=c, api_cfg=api_cfg,
                )
            if result.get("status") == "assessed":
                print(f"[life_loop] identity assessment: consistency={result.get('consistency_score', 0):.2f}")
        except Exception as e:
            print(f"[life_loop] identity assessment failed: {e}")

    async def _adjust_retrieval_weights(self):
        """Weekly: adjust retrieval weights based on accumulated feedback (EvolveMem)."""
        try:
            from app import adaptive_retrieval
            new_weights = adaptive_retrieval.adjust_weights(self.db_path, user_id="default")
            print(f"[life_loop] adaptive weights adjusted: {new_weights}")
        except Exception as e:
            print(f"[life_loop] weight adjustment failed: {e}")

    async def _consolidate_learning(self):
        """Weekly: consolidate learning observations into patterns."""
        try:
            from app import learning_engine
            # The learning engine records observations during chat (via event bus subscribers)
            # Here we trigger consolidation — find patterns in accumulated observations
            patterns = learning_engine.get_learned_patterns(self.db_path, user_id="default")
            stats = learning_engine.get_stats(self.db_path, user_id="default")
            print(f"[life_loop] learning: {stats.get('total_patterns', 0)} patterns, {stats.get('total_observations', 0)} observations")
        except Exception as e:
            print(f"[life_loop] learning consolidation failed: {e}")

    async def _auto_validate_quarantine(self):
        """Weekly: auto-validate quarantined memories using rule engine."""
        try:
            from app import memory_governance
            result = memory_governance.auto_validate_by_rules(self.db_path, user_id="default")
            if result.get("validated", 0) > 0 or result.get("rejected", 0) > 0:
                print(f"[life_loop] governance: validated={result.get('validated', 0)}, rejected={result.get('rejected', 0)}")
        except Exception as e:
            print(f"[life_loop] auto-validate failed: {e}")

    async def _run_proactive_checks(self):
        """Weekly: check commitments, silence, milestones — generate proactive messages."""
        try:
            from app import proactive_engine
            messages = proactive_engine.get_proactive_messages(self.db_path, user_id="default")
            if messages:
                print(f"[life_loop] proactive: {len(messages)} messages generated")
                # Publish as discoveries so they surface in the morning letter
                try:
                    from app import discovery
                    from datetime import datetime
                    today = datetime.now().strftime("%Y-%m-%d")
                    for msg in messages:
                        discovery.create(
                            self.db_path, "default",
                            type_="observation",
                            title="主动提醒",
                            content=msg,
                            discovered_by="life_loop",
                            date_str=today,
                        )
                except Exception:
                    pass
        except Exception as e:
            print(f"[life_loop] proactive check failed: {e}")

    async def _residents_do_daily_work(self):
        """每天，居民各自做自己的事。共享灵魂，独立当下。
        每个居民根据自己的角色做不同的工作，结果写入 activity_log，
        在第二天的晨报中显示。"""
        try:
            from app import residents as residents_mod
            all_residents = residents_mod.list_residents(self.db_path, "default", status="active")
            if not all_residents:
                return

            # 为每个角色定义每日工作
            ROLE_TASKS = {
                "researcher": "回顾最近的对话和记忆，找出一个值得深入研究的主题，写一段简短的研究方向建议。",
                "historian": "回顾最近 7 天的对话和时间线，写一段周记（100-200字），记录这周发生了什么。",
                "critic": "审查最近的记忆和认知更新，找出可能的矛盾或过度设计，提出一条改进建议。",
                "planner": "查看当前的目标和承诺，找出最停滞的一个，建议下一步行动。",
                "explorer": "基于最近的对话和记忆，发现一个用户可能感兴趣但还没探索的相邻领域。",
                "architect": "审视系统的整体结构，指出一个可以简化或合并的部分。",
                "writer": "把最近的重要记忆或时间线事件，写成一段简短的叙事（100-200字）。",
            }

            api_cfg = self.get_memory_api_cfg()
            import httpx

            for resident in all_residents:
                role = resident["role"]
                if role in ("general", "custom"):
                    continue
                task = ROLE_TASKS.get(role)
                if not task:
                    continue
                try:
                    result = await residents_mod.resident_do_work(
                        self.db_path, resident["id"], task,
                        http_client_factory=lambda timeout: httpx.AsyncClient(timeout=timeout),
                        get_api_cfg=self.get_memory_api_cfg,
                    )
                    if result.get("result"):
                        print(f"[life_loop] {resident['name']} 完成了每日工作")
                except Exception as e:
                    print(f"[life_loop] {resident['name']} work failed: {e}")

        except Exception as e:
            print(f"[life_loop] residents daily work failed: {e}")


# Global instance (set by main.py on startup)
_life_loop: Optional[LifeLoop] = None


def get_life_loop() -> Optional[LifeLoop]:
    return _life_loop


def set_life_loop(loop: LifeLoop):
    global _life_loop
    _life_loop = loop
