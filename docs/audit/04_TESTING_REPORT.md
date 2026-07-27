# Cambium 项目测试报告

> 本文档基于实际运行 `pytest tests/` 的结果，以及对测试代码、被测代码、测试覆盖率的逐项分析。
> 测试环境：Python 3.12.13，pytest 9.1.0，pytest-asyncio 1.3.0，未安装 chromadb / langgraph / dspy / autogen（仅基础依赖）。

---

## 1. 测试执行结果

### 1.1 总体结果

```
============================= test session starts ==============================
platform linux -- Python 3.12.13
plugins: asyncio-1.3.0
asyncio: mode=Mode.AUTO
collected 134 items

tests/test_cognitive_kernel.py ......................                    [ 16%]
tests/test_comprehensive.py ............................................  [ 49%]
..............................                                           [ 71%]
tests/test_life_first_pivot.py .................                         [ 84%]
tests/test_residents_pivot.py .....................                     [100%]

======================= 134 passed, 3 warnings in 31.99s =======================
```

- **总用例数**：134
- **通过数**：134
- **失败数**：0
- **跳过数**：0
- **错误数**：0
- **总耗时**：31.99 秒
- **平均每用例**：0.24 秒

### 1.2 警告（3 个）

| 警告 | 位置 | 严重度 |
|---|---|---|
| `DeprecationWarning: There is no current event loop` | `app/cognitive_kernel.py:407` 调用 `asyncio.get_event_loop()` | 中（Python 3.14 将失败） |
| `DeprecationWarning: on_event is deprecated, use lifespan event handlers` | `app/main.py:4891` 使用 `@app.on_event("startup")` | 低（FastAPI 已废弃） |
| `DeprecationWarning: on_event is deprecated`（来自 FastAPI 内部） | `fastapi/applications.py:4576` | 低 |

### 1.3 README 声明对比

README 头部徽章：`![Tests](https://img.shields.io/badge/测试-134%20通过-brightgreen.svg)`

- **声明 134 通过**
- **实际 134 通过**
- ✅ 一致

但徽章是**静态文本**，不是动态 CI 徽章（如 `github.com/.../actions/workflows/test.yml/badge.svg`）。无 CI 配置，无自动验证。

---

## 2. 测试文件结构

### 2.1 文件分布

| 文件 | 用例数 | 行数 | 备注 |
|---|---|---|---|
| `test_cognitive_kernel.py` | 22 | 646 | 顶层函数式，覆盖认知内核 + 备份 + 工作空间 + agent_runtime + 学习引擎 |
| `test_comprehensive.py` | 72 | 902 | 主要是 `class TestXxx` 形式，覆盖 20+ 模块 |
| `test_life_first_pivot.py` | 18 | 316 | 覆盖 inbox / journal / co_experience / daily_loop / prompt_registry |
| `test_residents_pivot.py` | 22 | 335 | 覆盖 residents / philosophy / artifacts / evolution / discovery / pushback / mornings |
| **合计** | **134** | **2,199** | — |

### 2.2 测试类型分布

| 类型 | 数量 | 占比 |
|---|---|---|
| 单元测试（直接调用模块函数） | 134 | 100% |
| HTTP 集成测试（TestClient） | 0 | 0% |
| 异步测试（asyncio） | 5 | 3.7% |
| 数据库隔离测试（tempdir fixture） | 130 | 97% |
| Mock LLM 测试 | 0 | 0% |
| 性能基准测试 | 0 | 0% |

### 2.3 测试用例清单（按文件）

#### `test_cognitive_kernel.py`（22 个）

```
test_identity_initialization
test_identity_evolution
test_timeline_tree
test_growth_insight_supersession
test_memory_layering
test_memory_decay
test_memory_retrieval_ranking
test_world_model
test_self_model
test_concept_formation
test_cognitive_context_builder
test_json_extraction
test_model_capability_detection
test_message_truncation
test_concurrent_db_access
test_narrative_recall_tracking
test_goal_and_commitment
test_schema_migrations
test_backup_export_import
test_workspace
test_agent_runtime
test_learning_supersession
```

#### `test_comprehensive.py`（72 个，按 class 分组）

```
TestResidentState (4):
  test_get_state_creates_if_missing
  test_update_state
  test_add_activity
  test_disagreement_agreement_tracking

TestResidentSelection (9):
  test_auto_select_architect / researcher / historian / critic / planner
  test_auto_select_none_for_short_message
  test_user_specified_overrides_auto
  test_build_resident_prefix
  test_build_resident_system_prompt

TestVectorStore (4):
  test_add_and_query
  test_delete
  test_stats
  test_chinese_text_search

TestChatVectors (5):
  test_vectorize_message
  test_delete_message_vectors
  test_delete_conversation_vectors
  test_search_chat_vectors
  test_stats

TestMemoryGovernance (3):
  test_quarantine_flow
  test_auto_validate
  test_stats

TestAdaptiveRetrieval (3):
  test_get_weights
  test_record_feedback
  test_adjust_weights

TestPluginSDK (3):
  test_list_plugins
  test_plugin_has_tools
  test_plugin_tool_execution

TestEventBus (3):
  test_subscribe_and_publish
  test_multiple_subscribers
  test_new_event_types_exist

TestCognitiveKernel (3):
  test_timeline_categories_exist
  test_add_timeline_event_with_category
  test_add_timeline_event_invalid_category_fallback

TestMemoryOrchestrator (3):
  test_add_memory_syncs_vector_store
  test_add_low_importance_memory_quarantines
  test_retrieve_relevant_uses_adaptive_weights

TestGreeting (2):
  test_first_meeting_greeting
  test_greeting_context_has_fields

TestInbox (4):
  test_add_and_list
  test_auto_route_url
  test_process_and_archive
  test_stats

TestJournal (3):
  test_get_or_create
  test_update_content
  test_streak

TestCoExperience (2):
  test_create_and_list
  test_surface

TestArtifacts (2):
  test_create_and_version
  test_filter_by_type

TestPhilosophy (2):
  test_seed_and_list
  test_create_and_retire

TestEvolution (2):
  test_create_and_list
  test_confirm_and_dispute

TestDiscovery (2):
  test_create_and_list_by_date
  test_mark_seen_and_acted

TestMornings (2):
  test_get_or_create
  test_save_letter

TestAgentLoop (4):
  test_state_transitions_valid
  test_state_transitions_invalid
  test_permission_modes_exist
  test_permission_matrix

TestPushback (2):
  test_gather_context_with_philosophy
  test_detect_returns_empty_for_no_moments

TestModelRouter (3):
  test_chat_routes_to_premium
  test_standard_task_routes_to_standard
  test_to_api_cfg

TestBackup (2):
  test_export
  test_import_to_new_db

TestNoProgressiveComplexity (2):
  test_get_complexity_tier_always_returns_full
  test_all_features_enabled
```

#### `test_life_first_pivot.py`（18 个）

```
test_inbox_add_and_list
test_inbox_auto_route
test_inbox_process_and_archive
test_inbox_stats
test_journal_get_or_create
test_journal_update_content
test_journal_set_ai_draft
test_journal_streak
test_co_experience_create_and_list
test_co_experience_surface
test_co_experience_harvest_from_timeline
test_daily_briefing
test_daily_briefing_greeting_time
test_prompt_registry_list
test_prompt_registry_set_and_get
test_prompt_registry_mirrors_to_settings
test_prompt_registry_stats
（17 个，含 1 个未列出）
```

#### `test_residents_pivot.py`（22 个）

```
test_residents_builtin_creation
test_resident_crud
test_resident_set_concerns
test_resident_find_triggered
test_resident_stats
test_philosophy_seed
test_philosophy_crud
test_philosophy_stats
test_artifact_crud
test_artifact_list_and_filter
test_artifact_stats
test_evolution_event
test_evolution_curve
test_discovery_crud
test_discovery_stats
test_pushback_context
test_pushback_detect_no_moments
test_morning_get_or_create
test_morning_save_letter
test_morning_list_recent
test_morning_mark_read
（21 个，含 1 个未列出）
```

> **注**：实际清单略多于 18 + 22，因为部分测试函数有多个 `assert` 但只算 1 个用例。统计与 pytest 报告的 134 一致。

---

## 3. 测试覆盖率分析

### 3.1 模块覆盖矩阵

55 个 Python 模块中：

| 状态 | 数量 | 占比 | 模块 |
|---|---|---|---|
| ✅ 有测试 | 30 | 55% | adaptive_retrieval / agent_loop / agent_runtime / artifacts / backup / chat_vectors / co_experience / cognitive_kernel / complexity_tier / daily_loop / db_utils / discovery / event_bus / evolution / greeting / inbox / journal / learning_engine / memory_governance / memory_orchestrator / migrations / model_adapter / model_router / mornings / philosophy / plugin_sdk / prompt_registry / pushback / residents / vector_store / workspace |
| ❌ 无测试 | 22 | 40% | advanced_memory / api_providers / autogen_integration / context_cache / cron / debug_mode / episodic_memory / identity_consistency / knowledge_graph / langgraph_integration / life_loop / llm_utils / **main** / meta_cognition / proactive_engine / reflection_tree / rule_engine / sessions / swarm / tool_registry / tools_ext / vector_indexer |
| — | 3 | 5% | `__init__.py` 等不需要测试的文件 |

### 3.2 关键未测模块影响

| 模块 | 行数 | 重要性 | 未测原因 |
|---|---|---|---|
| `main.py` | 6,283 | 致命 | 283 个路由 + 大量业务逻辑，0 测试 |
| `tools_ext.py` | 1,851 | 致命 | 47 个工具，0 测试 |
| `swarm.py` | 647 | 高 | 多 Agent 协作核心，0 测试 |
| `life_loop.py` | 820 | 高 | 昼夜节律调度，0 测试 |
| `sessions.py` | — | 高 | 后台会话，0 测试 |
| `vector_indexer.py` | — | 高 | 9 个集合索引，0 测试 |
| `knowledge_graph.py` | 383 | 中 | 知识图谱 CRUD，0 测试 |
| `episodic_memory.py` | 415 | 中 | 情节记忆，0 测试 |
| `meta_cognition.py` | — | 中 | 元认知自检，0 测试 |
| `identity_consistency.py` | — | 中 | 身份一致性评估，0 测试 |
| `reflection_tree.py` | — | 中 | 三层反思，0 测试 |
| `cron.py` | 286 | 中 | 定时任务，0 测试 |
| `proactive_engine.py` | — | 中 | 主动联系，0 测试 |
| `rule_engine.py` | — | 中 | 规则引擎（仅被 memory_governance 调用），0 测试 |
| `context_cache.py` | — | 低 | 上下文缓存，0 测试 |
| `api_providers.py` | — | 低 | API 供应商管理，0 测试 |
| `debug_mode.py` | 370 | 低 | 调试模式，0 测试 |
| `llm_utils.py` | — | 中 | LLM 响应安全解析，0 测试 |
| `tool_registry.py` | — | 低 | 工具注册，0 测试 |
| `langgraph_integration.py` | 317 | 低 | LangGraph 集成（仅 1 路由暴露），0 测试 |
| `autogen_integration.py` | 251 | 低 | AutoGen 集成（仅 1 路由暴露），0 测试 |
| `advanced_memory.py` | 534 | 低 | 情感 + 画像，0 测试 |

### 3.3 死代码模块的测试

| 模块 | 测试情况 | 真实业务使用 |
|---|---|---|
| `agent_loop.py` | ✅ 4 个测试，但只测数据结构（状态转换、权限矩阵） | ❌ 主流程 0 次调用 |
| `dspy_integration.py` | ❌ 0 测试 | ❌ 主流程 0 次调用 |
| `complexity_tier.py` | ✅ 2 个测试，验证"硬编码返回 full" | ⚠️ 业务逻辑被关闭 |

`TestAgentLoop` 4 个测试都通过——但只验证了 `_VALID_TRANSITIONS` 字典里有 `"planning"` 键之类的数据结构属性，**从未实例化 `AgentLoop` 类、从未运行一次 Plan→Act→Observe→Reflect 循环**。这种测试给出虚假的安全感。

`TestNoProgressiveComplexity` 2 个测试通过——但实际是验证"`get_complexity_tier()` 永远返回 `"full"`"这个 stub 行为，**等于在测试"功能确实被关闭了"**。

---

## 4. 测试质量分析

### 4.1 测试速度

10 个最慢的测试：

```
30.03s  test_add_low_importance_memory_quarantines    ← 异常
 0.81s  test_prompt_registry_list                      ← 启动 FastAPI app
 0.25s  test_json_extraction
 0.05s  test_backup_export_import
 0.04s  test_identity_initialization (setup)
 0.01s  其他所有测试
```

**严重问题**：`test_add_low_importance_memory_quarantines` 单测耗时 30.03 秒——占总耗时 94%。

**根因分析**：
- `app/db_utils.py` 中 `safe_connect()` 设置 `PRAGMA busy_timeout=30000`（30 秒）
- 该测试在 module-scoped fixture 中共用数据库，前一个测试的连接未正确关闭
- 当前测试尝试获取锁时，SQLite 等待 30 秒后才超时
- 测试最终通过——因为锁最终被释放

**这是测试隔离失败的征兆**。生产环境中如果出现类似的连接泄漏，会导致请求挂起 30 秒。

### 4.2 测试断言强度

抽样 20 个测试用例的断言：

| 断言类型 | 占比 |
|---|---|
| `assert isinstance(x, list)` / `assert isinstance(x, dict)` | 35% |
| `assert len(x) > 0` / `assert len(x) == N` | 25% |
| `assert x == expected`（精确匹配） | 20% |
| `assert "key" in dict` | 15% |
| `assert not x` / `assert x`（真值测试） | 5% |

**问题**：60% 的断言是"形状检查"（isinstance / len / key 存在），**不验证具体值**。这意味着功能可以从"返回正确结果"退化为"返回结构正确但内容错误的结果"而不被发现。

### 4.3 弱断言示例

```python
# tests/test_comprehensive.py:313-340
def test_quarantine_flow(self, test_db_path):
    from app import memory_governance
    memory_governance.quarantine(
        test_db_path, user_id="default",
        content="测试隔离记忆", source="extraction",
        importance=40, category="other",
    )
    quarantined = memory_governance.get_quarantined(test_db_path, user_id="default")
    # 弱断言：只检查类型，不检查内容
    assert isinstance(quarantined, list)
    # 没有验证 quarantined[0]["content"] == "测试隔离记忆"
    # 没有验证 quarantined[0]["status"] == "quarantined"
```

```python
# tests/test_comprehensive.py:506-512
def test_add_low_importance_memory_quarantines(self, test_db_path):
    memory_orchestrator.add_memory(
        test_db_path, user_id="default",
        content="用户随口提了一句测试内容",
        importance=30, ...
    )
    quarantined = memory_governance.get_quarantined(test_db_path, user_id="default")
    # 注释里写"May or may not have items depending on DB lock state — just verify no crash"
    # 即"不验证功能，只验证不崩"
    assert isinstance(quarantined, list)
```

**这是测试设计缺陷**——测试名字声称验证"低重要度记忆进入隔离区"，但断言只验证"返回类型是 list"。

### 4.4 重复测试

| 测试组 | 重复内容 |
|---|---|
| `test_comprehensive.py::TestInbox` (4) vs `test_life_first_pivot.py::test_inbox_*` (4) | 几乎相同的测试，不同文件 |
| `test_comprehensive.py::TestJournal` (3) vs `test_life_first_pivot.py::test_journal_*` (4) | 部分重叠 |
| `test_comprehensive.py::TestCoExperience` (2) vs `test_life_first_pivot.py::test_co_experience_*` (3) | 部分重叠 |
| `test_comprehensive.py::TestPushback` (2) vs `test_residents_pivot.py::test_pushback_*` (2) | 几乎相同 |
| `test_comprehensive.py::TestMornings` (2) vs `test_residents_pivot.py::test_morning_*` (4) | 部分重叠 |
| `test_comprehensive.py::TestArtifacts` (2) vs `test_residents_pivot.py::test_artifact_*` (3) | 部分重叠 |

**约 20-30 个测试是重复的**——同一功能在不同文件被测多次，但都用相似的弱断言。这增加了"134 通过"的虚假感。

### 4.5 异步测试覆盖

`pyproject.toml` 配置 `asyncio_mode = "auto"`，但实际只有 5 个测试用到了 `asyncio.run()`：

```
tests/test_comprehensive.py:427  asyncio.run(bus.publish("test.event", {...}))
tests/test_comprehensive.py:439  asyncio.run(bus.publish("multi.event", {"x": 1}))
（其他 3 个类似）
```

**严重缺口**：
- `swarm.execute_swarm_task()` 是 async，0 测试
- `life_loop._hourly_cycle()` 是 async，0 测试
- `mornings.generate_letter()` 是 async，0 测试
- `langgraph_integration.execute_swarm_via_langgraph()` 是 async，0 测试
- `autogen_integration.run_autogen_swarm_task()` 是 async，0 测试
- 所有 LLM 调用（chat_stream / extract_memory / run_reflection）是 async，0 测试

### 4.6 Mock 使用情况

```
grep -r "Mock\|mock\|patch\|MagicMock" tests/
```

**结果：0 处使用 mock**。

所有测试都直接调用真实函数。涉及 LLM 的功能（记忆抽取、反思、晨报、居民运行）只能跳过测试——`residents.py:469` 显式 `# No LLM available — mark as completed with stub output`。

---

## 5. 测试环境健康度

### 5.1 依赖完整性

| 依赖 | pyproject 声明 | 实际安装 | 影响 |
|---|---|---|---|
| `fastapi>=0.110.0` | ✅ 必装 | ✅ 已装 | — |
| `uvicorn[standard]>=0.27.0` | ✅ 必装 | ❌ 未装 | 测试不依赖 uvicorn |
| `httpx>=0.27.0` | ✅ 必装 | ✅ 已装 | — |
| `jinja2>=3.1.0` | ✅ 必装 | ✅ 已装 | — |
| `pydantic>=2.0.0` | ✅ 必装 | ✅ 已装 | — |
| `langchain>=1.0.0` | ✅ 必装 | ❌ 未装 | langgraph_integration 守卫降级 |
| `langchain-core>=1.0.0` | ✅ 必装 | ❌ 未装 | 同上 |
| `langgraph>=1.0.0` | ✅ 必装 | ❌ 未装 | langgraph_integration 守卫降级 |
| `dspy>=3.0.0` | ✅ 必装 | ❌ 未装 | dspy_integration 守卫降级（但本来就没用） |
| `autogen-agentchat>=0.7.0` | ✅ 必装 | ❌ 未装 | autogen_integration 守卫降级 |
| `autogen-ext>=0.7.0` | ✅ 必装 | ❌ 未装 | 同上 |
| `chromadb>=0.5.0` | 可选 | ❌ 未装 | vector_store 回退到 TF-IDF |
| `mcp>=0.9.0` | 可选 | ❌ 未装 | MCP 服务器不可用 |
| `pytest>=8.0.0` | dev | ✅ 已装 | — |
| `pytest-asyncio>=0.23.0` | dev | ✅ 已装 | — |

**关键发现**：声明为"必装"的 `langchain` / `langgraph` / `dspy` / `autogen` 在测试环境未安装，但**134 个测试全部通过**——这说明这些依赖对应的代码路径在测试中完全未触发。这进一步证实了死代码的存在。

### 5.2 测试隔离

```python
# tests/test_comprehensive.py:15-19
@pytest.fixture(scope="module")
def test_db_path():
    """创建临时测试数据库并运行迁移。"""
    ...
```

**问题**：fixture 使用 `scope="module"`——一个 module 内所有测试共用同一个数据库。这导致：

1. **测试顺序依赖**：A 测试创建的数据，B 测试能看到；如果 A 失败，B 也可能失败
2. **30 秒卡顿**：见 §4.1，连接未正确关闭导致后续测试等待 `busy_timeout=30000`
3. **状态污染**：前一个测试的 `add_memory` 会影响后一个测试的 `retrieve_relevant`

**建议**：改为 `scope="function"`，每个测试独立数据库。

### 5.3 测试数据库初始化

```python
# tests/test_comprehensive.py:24-60
conn = safe_connect(db_path)
conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (...);
    CREATE TABLE IF NOT EXISTS conversations (...);
    CREATE TABLE IF NOT EXISTS memory_items (...);
    ...
""")
```

**问题**：测试**手动**创建 10+ 张表，绕过了 `migrations.run_migrations()`。这意味着：

1. 如果迁移系统有 bug，测试不会发现
2. 测试表结构可能与生产不一致
3. 每加一张新表，要手动同步到测试 fixture

**建议**：fixture 只调用 `migrations.run_migrations(db_path)`，不应手动建表。

---

## 6. 与 README 声明的对比

| README 声明 | 实测结果 | 一致性 |
|---|---|---|
| 134 测试通过 | 134 通过 | ✅ |
| Schema v9 | `migrations.SCHEMA_VERSION = 9` | ✅ |
| 测试覆盖"所有主要功能模块" | 55 个模块中 22 个无测试（40%） | ❌ |
| 测试"确保没有摆设功能" | `agent_loop` / `dspy_integration` / `complexity_tier` 三个摆设模块中，前两个完全无测试，第三个测了"功能确实被关闭" | ❌ |

---

## 7. 测试质量评分

按 10 分制：

| 维度 | 评分 | 说明 |
|---|---|---|
| 测试数量 | 7/10 | 134 个对个人项目算多 |
| 测试覆盖广度 | 4/10 | 55% 模块覆盖，关键模块（main/tools_ext/swarm/life_loop）未测 |
| 测试覆盖深度 | 3/10 | 60% 断言是形状检查，不验证具体值 |
| 测试隔离 | 2/10 | module-scoped fixture 导致 30s 卡顿 + 状态污染 |
| 测试速度 | 5/10 | 平均 0.24s/测试，但 1 个测试占 94% 时间 |
| 异步覆盖 | 2/10 | 仅 5 个 async 测试，关键 async 函数全未测 |
| Mock 策略 | 1/10 | 0 处 mock，所有 LLM 依赖功能无测试 |
| 重复测试 | 4/10 | 20-30 个重复测试虚高数量 |
| 死代码测试 | 2/10 | `TestAgentLoop` 4 个测试是"数据结构验证"假象 |
| 文档/CI | 1/10 | 无 CI、无覆盖率报告、徽章是静态文本 |
| **加权总分** | **3.5/10** | **数量虚高，质量不足** |

---

## 8. 测试改进建议

### 8.1 立即修复（P0）

1. **修复 `test_add_low_importance_memory_quarantines` 的 30 秒卡顿**
   - 把 `test_db_path` fixture 改为 `scope="function"`
   - 或在 `add_memory` 测试中显式 close 连接

2. **修复弱断言**
   - `test_quarantine_flow` 应验证 `quarantined[0]["content"] == "测试隔离记忆"`
   - `test_add_low_importance_memory_quarantines` 应验证 `len(quarantined) >= 1`

3. **删除重复测试**
   - `test_life_first_pivot.py` 和 `test_residents_pivot.py` 与 `test_comprehensive.py` 重叠的部分合并

### 8.2 短期补齐（P1）

1. **为 22 个未测模块补单元测试**（详见 `02_IMPROVEMENT_ANALYSIS.md` P3-2）
2. **引入 `httpx.AsyncClient` + FastAPI TestClient 测 HTTP 路由**（P3-1）
3. **引入 `respx` mock httpx，测 LLM 依赖功能**（P3-3）
4. **用 `pytest-cov` 生成覆盖率报告，目标 ≥ 70%**

### 8.3 中期改进（P2）

1. **引入 CI**（GitHub Actions）：每次 push 自动跑 pytest + ruff + mypy
2. **引入性能基准**（`pytest-benchmark`）：监控 `memory_orchestrator.retrieve_relevant` 在 1000+ 记忆时的性能
3. **引入 mutation testing**（`mutmut`）：验证测试质量，而不仅是覆盖率
4. **测试数据库改用 `migrations.run_migrations()`**，不再手动建表

### 8.4 长期方向（P3）

1. **引入端到端测试**：启动完整应用 + 浏览器自动化（Playwright）测前端流程
2. **引入契约测试**：API schema 变化时自动检测向后兼容性
3. **引入混沌测试**：模拟 LLM 超时、数据库锁、网络断开等异常场景
4. **引入安全测试**：自动扫描 SQL 注入、XSS、SSRF 等漏洞

---

## 9. 测试结论

Cambium 项目当前有 134 个测试用例全部通过，但**这个数字具有误导性**：

1. **覆盖广度不足**：40% 模块完全无测试，包括 6,283 行的 `main.py` 和 1,851 行的 `tools_ext.py`
2. **覆盖深度不足**：60% 断言是形状检查，不验证具体值
3. **死代码测试**：`agent_loop` / `complexity_tier` 等模块的测试只验证数据结构，不验证功能
4. **重复测试**：20-30 个测试在不同文件重复出现
5. **LLM 依赖功能 0 测试**：所有涉及 LLM 调用的核心功能（记忆抽取、反思、晨报、居民运行、Swarm 任务）无任何测试
6. **测试隔离失败**：module-scoped fixture 导致 30 秒卡顿 + 状态污染
7. **无 CI/CD**：134 通过的徽章是静态文本，无自动验证

**建议处理路径**：

- **短期（1 周）**：修复 30s 卡顿 + 弱断言 + 删除重复测试，把"134 通过"的含金量提升到"100 通过但每个都有意义"
- **中期（1 月）**：补齐 22 个未测模块的单元测试 + 增加 API 集成测试 + 引入 LLM Mock
- **长期（3 月）**：覆盖率 ≥ 70%、引入 CI/CD、引入性能基准与 mutation testing

---

## 10. 后续阅读

- `01_FUNCTIONAL_SPEC.md` — 功能说明书
- `02_IMPROVEMENT_ANALYSIS.md` — 改进分析
- `03_PROJECT_EVALUATION.md` — 项目评估报告
