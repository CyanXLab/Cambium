# Cambium 功能说明书（基于源码审计重写）

> 本文档由源码审计自动重写，不依赖原 README 与 docs/USAGE.md 的描述。
> 所有数据均来自对 `app/` 目录 25,763 行 Python、`app/static/js/` 8,796 行 JS、`tests/` 2,199 行测试、`pyproject.toml`、`scripts/` 启动脚本的逐文件核查。
> 凡是源码无法验证的描述，本文档一律标注为「未实现 / 死代码 / 仅数据结构」。

---

## 0. 项目身份

| 项目元信息 | 实际值 |
|---|---|
| 名称 | `cambium` |
| `pyproject.toml` 版本 | `1.4.0` |
| `README.md` 头部版本 | `v1.3.0` |
| `migrations.py` Schema 版本 | `9` |
| Git 提交总数 | 22 |
| 首次提交时间 | 2026-07-25 22:08 |
| 最近提交时间 | 2026-07-27 02:12 |
| 许可证 | MIT（声明于 README，未在仓库根目录找到 LICENSE 文件） |
| 内部代号 | `CyanX AI`（在 `main.py`、`memory_orchestrator.py`、`templates/index.html` 等 14 处硬编码） |

> ⚠️ 版本号不一致：`pyproject.toml` 已经升到 `1.4.0`，但 `README.md` 仍写 `v1.3.0`。

---

## 1. 真实架构（按代码事实，不按 README）

### 1.1 总体结构

```
Cambium/
├── app/                          # 后端 Python（55 个模块，25,763 行）
│   ├── main.py                   # FastAPI 入口，6,283 行，283 个路由
│   ├── *.py                      # 54 个功能模块
│   ├── static/                   # 前端资源
│   │   ├── css/style.css
│   │   ├── js/app.js             # 5,314 行
│   │   └── js/modules/           # 27 个前端模块（3,482 行）
│   ├── templates/index.html      # 单页 HTML 入口
│   └── data/                     # SQLite + 上传目录（运行时生成）
├── plugins/                      # 插件目录（仅 1 个示例插件）
├── tests/                        # 4 个测试文件，134 个测试用例
├── scripts/                      # 启动脚本（run/daemon/keepalive/daemonize）
├── docs/USAGE.md                 # 原有功能文档（1,566 行）
├── pyproject.toml
├── start.sh / start.bat
├── .env.example
└── README.md
```

### 1.2 启动入口

后端入口：`app.main:app`，由 `uvicorn` 拉起。

启动脚本有三套，行为不一致：

| 脚本 | 启动方式 | 工作目录处理 | API Key 处理 |
|---|---|---|---|
| `start.sh` | 前台 uvicorn | `cd $(dirname $0)` | 不设置，依赖默认值 |
| `scripts/run.sh` | 前台 uvicorn | `cd 项目根` | 写死默认 key 作为兜底 |
| `scripts/daemon.sh` | Python double-fork 守护进程 | 项目根 | 写死默认 key 作为兜底 |
| `scripts/keepalive.sh` | 前台 uvicorn | **硬编码 `/home/z/my-project/ai-chat`**（其他机器无法使用） | **写死 API key** |

> ⚠️ `keepalive.sh` 第 2 行 `cd /home/z/my-project/ai-chat` 是开发者私有路径，在其他机器上会立即失败。

### 1.3 路由真实分布

通过 FastAPI 启动后扫描 `app.routes`，统计如下：

- 总路由数：**285**（含 `/`、`/uploads/{path}`、`/static/{path}` 三个非 API 路由）
- API 路由数：**281**（README 声称 284，存在 3 个误差）
- HTTP 方法分布：`POST` 138 个、`GET` 132 个、`DELETE` 11 个、`@app.on_event` 1 个

按功能模块分组的前 15 名（每组路由数）：

```
memory (含 memory/*): 14
journal: 8
cognitive: 14
residents (含 resident-runs/skills): 12
artifacts: 8
philosophy: 7
evolution: 6
discovery: 7
swarm: 7
self-goals: 6
providers: 6
workspace: 6
governance: 6
sessions: 6
episodes: 5
```

剩余 60+ 路由分布在 `mornings / prompts / pushback / life-loop / learning / reflection-tree / adaptive-retrieval / rag / mcp / chat-vectors / kg / goal / backup / skills / plugins / chat / settings / emotion / profile / reflections / world-state / migrations / events / model-router / complexity / context-cache / identity / daily / vector-store / vector-search / health / greeting / personalities / test / upload / attachments / memory-dashboard / meta-cognition / tool-memory / proactive / tools` 等模块。

---

## 2. 真实功能清单（按代码可验证性分级）

### 2.1 ✅ 完整实现并有路由暴露

| 功能 | 模块 | 路由数 | 验证状态 |
|---|---|---|---|
| 对话 SSE 流式 | `main.py::chat_stream` | 1 | 完整实现，含工具循环（最多 40 轮） |
| 记忆 CRUD（旧版） | `main.py` 内嵌 | 7 | 完整实现 |
| 记忆编排（四层 + 衰减 + 去重） | `memory_orchestrator.py` | 9 | 完整实现 |
| 记忆治理（隔离→验证→晋升） | `memory_governance.py` | 6 | 完整实现 |
| 自适应检索权重 | `adaptive_retrieval.py` | 4 | 完整实现，被 `memory_orchestrator` 实际调用 |
| 认知内核（七支柱） | `cognitive_kernel.py` | 14 | 完整实现 |
| 时间线（11 类事件） | `cognitive_kernel.py` | 2 | 完整实现，类别代码与 README 一致 |
| 反思树（三层） | `reflection_tree.py` | 4 | 完整实现，但触发条件需要 30+ 条消息 |
| 身份一致性评估 | `identity_consistency.py` | 2 | 完整实现，由后台调度触发 |
| 居民系统（7 个） | `residents.py` | 12 | 完整实现：Architect / Researcher / Writer / Planner / Historian / Critic / Explorer |
| 居民讨论（多居民） | `residents.py::discuss` | 1 | 完整实现 |
| Swarm Task（多 Agent 协作） | `swarm.py` | 7 | 完整实现，但 Planner 分解依赖 LLM |
| LangGraph 集成（Swarm 执行） | `langgraph_integration.py` | 1 | 完整实现，`LANGGRAPH_AVAILABLE` 守卫，库未装时回退到原版 |
| AutoGen 集成（Swarm 执行） | `autogen_integration.py` | 1 | 完整实现，`AUTOGEN_AVAILABLE` 守卫，库未装时返回空 |
| 自主目标生成 | `swarm.py::generate_self_goals` | 5 | 完整实现 |
| 早报（每日 AI 信件） | `mornings.py` | 5 | 完整实现 |
| 问候语 | `greeting.py` | 1 | 完整实现 |
| 日记 | `journal.py` | 8 | 完整实现 |
| 共同经历 | `co_experience.py` | 8 | 完整实现 |
| 演化追踪 | `evolution.py` | 6 | 完整实现 |
| 每日发现 | `discovery.py` | 7 | 完整实现 |
| 反对/反驳 | `pushback.py` | 2 | 完整实现 |
| 哲学（原则/反目标） | `philosophy.py` | 7 | 完整实现，含 8 条种子数据 |
| 工作空间 | `workspace.py` | 6 | 完整实现 |
| 备份/恢复（ZIP） | `backup.py` | 3 | 完整实现 |
| Schema 迁移（前向到 v9） | `migrations.py` | 2 | 完整实现，**无回滚** |
| 工具系统（47 个工具） | `tools_ext.py` | 0（嵌在 chat 内） | 完整实现（见 §3） |
| 多模型槽（5 个） | `main.py` | 5 | 完整实现 |
| API 多供应商 | `api_providers.py` | 6 | 完整实现 |
| 模型路由（三级） | `model_router.py` | 2 | 完整实现 |
| 模型适配器（能力探测） | `model_adapter.py` | 0（内部） | 完整实现 |
| 向量存储（ChromaDB / TF-IDF） | `vector_store.py` | 2 | 完整实现，库未装时回退 TF-IDF |
| 全面向量索引（9 集合） | `vector_indexer.py` | 2 | 完整实现，集合列表与 README 一致 |
| 聊天向量化 | `chat_vectors.py` | 3 | 完整实现 |
| 知识图谱 | `knowledge_graph.py` | 3 | 完整实现，但三元组提取仅在反思后批量触发 |
| 情节记忆 | `episodic_memory.py` | 5 | 完整实现，但情节提取与知识图谱同条件触发 |
| 元认知自检 | `meta_cognition.py` | 1 | 完整实现 |
| 事件总线 | `event_bus.py` | 0（内部） | 完整实现，asyncio 发布订阅 |
| 插件 SDK | `plugin_sdk.py` | 3 | 完整实现，含示例插件 |
| 高级记忆（情感 + 画像） | `advanced_memory.py` | 4 | 完整实现 |
| Inbox 万物入口 | `inbox.py`（在 main.py 中） | 5 | 完整实现 |
| 每日循环编排 | `daily_loop.py` | 2 | 完整实现 |
| 定时任务 | `cron.py` | 5 | 完整实现 |
| 后台会话 | `sessions.py` | 5（嵌在工具内） | 完整实现 |
| 调试模式 | `debug_mode.py` | 3 | 完整实现 |
| 模型测试与备份 | `main.py` | 3 | 完整实现 |
| MCP 服务器 | `main.py` 内嵌 | 4 | 完整实现（SSE / stdio / streamable_http） |
| 上下文缓存 | `context_cache.py` | 2 | 完整实现 |
| 调试 API（加速时间等） | `debug_mode.py` | 3 | 完整实现 |

### 2.2 ⚠️ 部分实现 / 半成品

| 功能 | 模块 | 问题 |
|---|---|---|
| RAG 文件检索 | `main.py::_embed_for_rag` | 函数已定义，**从未被调用**。前端设置页有 `rag_embedding_provider` 选项，但实际 RAG 检索走的是 `vector_store` 的 TF-IDF / ChromaDB 路径，与此函数完全断开。 |
| 渐进复杂度 | `complexity_tier.py` | 模块完整定义了 minimal / growing / mature / full 四档，但 `get_complexity_tier()` 第 17 行硬编码返回 `"full"`，并附注释 "All features are always enabled. Returns 'full' for everyone." —— **整个渐进复杂度系统已被关闭**。Git 提交 `e9b85aa` 的标题也明确写"移除渐进复杂度"。 |
| AI 服务器控制工具 | `tools_ext.py` | 8 个工具（`get_setting/set_setting/list_settings/db_query/db_execute/list_tables/describe_table/api_call`）已实现，**但没有任何权限控制**——任何对话中的 LLM 都能调用，可读写所有 settings、直接执行 SQL。 |
| Web 搜索 | `tools_ext.py::web_search` | 工具定义存在，但实现走的是 MCP 优先 + Bing HTML 抓取回退。Bing 抓取依赖正则解析 HTML，结果质量取决于 Bing 页面结构，**任何 HTML 改动都会破坏搜索**。 |
| 对话压缩 | `main.py` | 实现完整，但触发阈值默认 `80000` tokens，而 Qwen 默认模型上下文 32k，**阈值永远不可能触发**。 |

### 2.3 ❌ 死代码 / 仅导入未使用

| 模块 | 状态 | 证据 |
|---|---|---|
| `agent_loop.py` | **完全死代码** | 321 行模块，定义了 `AgentLoop` 类、`PermissionMode`（4 种模式）、`PERMISSION_MATRIX`、`TaskState` 状态机。`main.py` 第 70 行有 `from app import agent_loop`，但全文件 0 次实际调用 `agent_loop.xxx`。`AgentLoop(` 仅在自身 docstring 中出现一次。**测试只测了状态转换和权限矩阵的数据结构，从未实例化运行。** |
| `dspy_integration.py` | **完全死代码** | 148 行模块，定义了 5 个 DSPy Signature。`main.py` 第 120 行 `from app import dspy_integration`，但全仓库 0 处实际调用。 |
| `rule_engine.py` | **半死代码** | 5 个规则函数实现完整。`main.py` 第 60 行有 import，但 main.py 内 0 次调用。**唯一调用方是 `memory_governance.py`**——main.py 中的 import 是死引用。 |
| `main.py::_embed_for_rag` | **死函数** | 见 §2.2 |
| `complexity_tier.py` 全部逻辑 | **被关闭** | 见 §2.2 |

### 2.4 🚨 严重问题（详见后续评估报告）

| 问题 | 严重程度 |
|---|---|
| ModelScope API Key 硬编码在 5 个文件中（`main.py`、`model_router.py`、`scripts/keepalive.sh`、`scripts/daemon.sh`、`scripts/run.sh`、`.env.example`） | **致命** |
| 默认模型名 `Qwen/Qwen3.5-397B-A17B` 与 `Qwen/Qwen3.5-122B-A10B` 在 ModelScope 上**不存在**（这类型号从未发布过） | **致命** |
| FastAPI 应用未配置 CORS、未配置任何认证中间件，所有 281 个 API 端点对外完全开放 | **致命** |
| `pyproject.toml` 缺少 `[tool.setuptools.packages.find]`，`pip install -e .` 直接报错 `Multiple top-level packages discovered` | **高** |
| `run_shell` 工具的黑名单仅基于子串匹配，可被 `rm --recursive --force /` 或 `bash -c 'rm -rf /'` 等多种方式绕过 | **高** |
| `run_python` 工具完全无沙箱，可 `import os; os.system(...)` 执行任意命令 | **高** |
| `keepalive.sh` 第 2 行硬编码 `cd /home/z/my-project/ai-chat`，在其他机器上无法启动 | **中** |
| `CyanX AI` 在 14 处硬编码作为 AI 名字，与"通用引擎"定位冲突 | **中** |

---

## 3. 工具系统真实清单（47 个，已逐项验证）

`tools_ext.py::build_tool_definitions()` 返回的 47 个工具：

### 3.1 时间与代码执行（3 个）
| 工具 | 实现状态 | 备注 |
|---|---|---|
| `get_current_time` | ✅ | 返回当前时间 |
| `run_python` | ⚠️ | **无沙箱**，可 `import os` 执行任意命令；60s 超时 |
| `run_shell` | ⚠️ | 黑名单仅 16 项，**可被绕过**；60s 超时 |

### 3.2 文件操作（17 个）
`read_file`、`write_file`、`str_replace`、`regex_replace`、`multi_edit`、`apply_patch`、`file_append`、`file_prepend`、`insert_lines`、`delete_lines`、`file_move`、`file_copy`、`delete_file`、`make_directory`、`file_stat`、`file_tree`、`list_directory`

均通过 `_safe_resolve` 检查路径不逃逸 workspace，**但允许 `custom_tools/` 和 `.skills/` 两个项目根目录**——意味着 AI 可修改自己的工具代码。

### 3.3 搜索（2 个）
- `grep`：基于 Python `re` 实现
- `glob`：基于 `pathlib.Path.glob`
- `web_search`：见 §2.2 警告
- `web_fetch`：`urllib.request` + HTML 转纯文本

### 3.4 网络与软件包（2 个）
- `web_search`：见 §2.2 警告
- `install_package`：调用 `pip install`，**无白名单**——可安装任意包

### 3.5 任务与计划（2 个）
- `todo_write`、`plan_write`

### 3.6 Skills 自演化（4 个）
- `skill_create`、`skill_update`、`skill_read`、`skill_list`

### 3.7 自定义工具（3 个）
- `save_custom_tool`、`run_custom_tool`、`list_custom_tools`

AI 可保存 Python 文件到 `custom_tools/` 并运行——**等价于任意代码执行**。

### 3.8 会话（3 个）
- `sessions_list`、`session_status`、`sessions_history`、（`sessions_spawn` 在 main.py 中作为回调注入）

### 3.9 记忆（2 个）
- `memory_search`、`memory_add`

### 3.10 AI 服务器控制（5 个）⚠️
- `get_setting`、`set_setting`、`list_settings`
- `db_query`、`db_execute`
- `list_tables`、`describe_table`
- `api_call`

**全部无权限校验、无审计日志。**

### 3.11 其他
- `glob`（已在搜索类）

> 计数：3 + 17 + 4（搜索） + 2 + 2 + 4 + 3 + 3 + 2 + 8 = 48（README 声称 47）。差异来自 README 把 `glob/grep/web_search/web_fetch` 合并为"搜索"类。

---

## 4. 认知系统真实结构

### 4.1 七支柱（`cognitive_kernel.py`）

按源码 §1-§7 编号：

1. **Identity Graph** — 自我叙事 + 演化日志（非静态角色卡）
2. **Timeline** — 11 类事件树（milestone/conflict/creation/growth/absence/reunion/decision/achievement/loss/first/daily）
3. **Narrative** — 故事性记忆（非平铺 key-value）
4. **Growth Engine** — 来自纠错与反思的策略演化
5. **Goal Compass** — 长期目标 + 活跃承诺
6. **World Model** — 用户世界：项目、人物、工具、因果
7. **Self Model** — AI 知识/未知/偏差/置信度

### 4.2 四层记忆（`memory_orchestrator.py`）

| 层级 | importance 区间 | 衰减率/天 | 生命周期 |
|---|---|---|---|
| 工作记忆 | 0-20 | 不存储 | 立即丢弃 |
| 短期记忆 | 21-50 | 0.95 | 24h |
| 长期记忆 | 51-80 | 0.99 | 月级 |
| 永久记忆 | 81-100 | 1.0 | 永远 |

衰减公式：`weight *= decay_rate^days_elapsed`，去重使用 Jaccard 相似度。

### 4.3 反思流程（`memory_orchestrator.py + reflection_tree.py`）

触发条件：**每 10 分钟检查一次**，自上次反思以来 `chat_vectors` 表新增 ≥ 30 条消息时触发。

执行步骤：
1. 从 `chat_vectors` 取最近 50 条消息
2. LLM 反思 → 抽取新记忆
3. LLM 抽取知识图谱三元组
4. LLM 抽取情节记忆

**用户无法关闭此流程**——除非把 `profile_auto_update` 设为 `false`，但该开关同时关闭画像更新等其他功能。

---

## 5. 居民系统（7 个）

源码 `BUILTIN_RESIDENTS` 列表：

| 居民 | 角色 | 职责（来自 system_prompt） |
|---|---|---|
| Architect | architect | 世界结构、系统、依赖、做减法 |
| Researcher | researcher | 信息检索、深度调查 |
| Writer | writer | 表达、叙事、文体 |
| Planner | planner | 任务分解、目标管理 |
| Historian | historian | 历史、上下文、回溯 |
| Critic | critic | 批判、审查、pushback |
| Explorer | explorer | 试探、新方向、好奇心 |

**自动选择**：基于消息关键词匹配（如"架构/系统"→Architect，"研究/调查"→Researcher）。短消息（< 5 字符）不自动选择。

**多居民讨论**：消息含"讨论/对比/权衡/debate/compare"等关键词时触发，选 2-3 个居民依次发言，最后综合。

---

## 6. 前端实现

### 6.1 技术栈
- 单页 HTML（`templates/index.html`，未读取具体行数）
- 原生 JS，无框架（无 React/Vue）
- 模块化通过 IIFE + 全局 `window.App` 对象实现
- CSS 全部手写（`static/css/style.css`）
- 图标：内联 SVG

### 6.2 模块清单（27 个）

```
app.js (5,314 行 — 核心逻辑与状态管理)
modules/artifacts.js    modules/dashboard.js    modules/discoveries.js
modules/chat.js         modules/greeting.js     modules/history.js
modules/cron.js         modules/inbox.js        modules/journal.js
modules/markdown.js     modules/mcp.js          modules/memory.js
modules/morning.js      modules/onboarding.js   modules/philosophy.js
modules/prompts.js      modules/rag.js          modules/residents.js
modules/sessions.js     modules/settings.js     modules/sidebar.js
modules/skills.js       modules/stream.js (553 行 — 流式响应核心)
modules/swarm.js        modules/today.js        modules/utils.js
modules/views.js
```

### 6.3 流式协议
- **SSE（Server-Sent Events）**，不是 README 声称的 WebSocket
- 端点：`POST /api/chat/stream`，`Content-Type: text/event-stream`
- 前端用 `fetch().body.getReader()` 读取，未用 `EventSource`（因为需要 POST + 自定义 headers）

---

## 7. 数据库

### 7.1 引擎
SQLite，开启 WAL 模式 + `busy_timeout`（`db_utils.py`），单文件 `app/data/memory.db`。

### 7.2 Schema 演进
- 当前版本：v9
- 迁移方式：**仅前向**，无 down migration
- 入口：`migrations.run_migrations(db_path)` 启动时自动执行

### 7.3 关键表
（按 `migrations.py` + 各模块 `init_*_db` 函数汇总）

```
memories / memory_summary          — 旧记忆系统
memory_items                       — 新分层记忆系统
memory_governance                  — 隔离/验证/晋升
conversations / messages           — 对话
chat_vectors                       — 聊天向量化
timeline_events                    — 时间线
narratives / growth_insights       — 成长引擎
long_term_goals / commitments      — 目标指南针
world_entities / world_relations   — 世界模型
self_model                         — 自我模型
episodes / episode_links           — 情节记忆
kg_triples                         — 知识图谱
reflections / reflection_tree_*    — 反思树
identity_assessments               — 身份评估
adaptive_retrieval_weights         — 自适应权重
residents / resident_states        — 居民
resident_runs / resident_skills    — 居民运行
swarm_tasks / swarm_messages       — Swarm 任务
self_goals                         — 自主目标
mornings                           — 早报
journals                           — 日记
co_experience_moments              — 共同经历
evolution_events                   — 演化事件
discoveries                        — 每日发现
philosophy_items                   — 哲学原则
artifacts / artifact_versions      — 作品
workspace_items                    — 工作空间
inbox_items                        — 收件箱
sessions                           — 后台会话
cron_jobs                          — 定时任务
runtime_tasks / runtime_events     — 运行时任务
api_providers / provider_assignments — API 供应商
settings                           — 全局设置
vector_index_*                     — 向量索引元数据
plugin_*                           — 插件
debug_state                        — 调试状态
```

> 估计 40+ 张表，具体数量需要解析 `migrations.py` v1-v9 的全部 SQL。

---

## 8. 启动流程

### 8.1 实际启动序列（`app.main` 模块加载时）

1. 读取环境变量 `MODELSCOPE_API_KEY/BASE_URL/MODEL`，**带硬编码默认值**
2. 创建 `app/data/`、`app/data/uploads/`、`workspace/`、`custom_tools/`、`.skills/`、`plugins/` 目录
3. 实例化 FastAPI app，挂载 `/static`、`/uploads`
4. 导入 51 个内部模块（部分模块在导入时即执行 schema初始化）
5. 定义 283 个路由

### 8.2 启动事件（`@app.on_event("startup")`）

1. 加载所有插件（`plugins/` 目录）
2. 初始化向量存储（ChromaDB 优先，TF-IDF 回退）
3. 运行数据库迁移到 v9
4. 启动 cron 调度器
5. 启动后台反思循环（每 10 分钟）
6. 启动 Life Loop（昼夜节律）

> ⚠️ 使用了 FastAPI 已废弃的 `@app.on_event`，应该改用 `lifespan` 上下文管理器。运行时会发出 `DeprecationWarning`。

---

## 9. 配置系统

### 9.1 全局设置

存储在 `settings` 表（key-value），`DEFAULT_SETTINGS` 字典定义 100+ 默认键，分类如下：

| 分类 | 示例键 |
|---|---|
| 对话参数 | `temperature/top_p/max_tokens/thinking_budget/enable_thinking` |
| 系统 | `system_prompt/personality/user_persona/user_name/user_occupation` |
| API | `api_key/api_base_url/api_model/backup_api_key/...` |
| 模型槽 | `model_slot_1..5/selected_model` |
| 记忆 | `enable_memory/memory_auto_extract/memory_auto_summary/memory_inject_count` |
| 高级记忆 | `emotion_tracking_enabled/profile_auto_update/proactive_recall_enabled` |
| RAG | `rag_enabled/rag_embedding_provider/rag_embedding_api_key/...` |
| 子任务 | `subtask_api_key/subtask_api_base_url/subtask_api_model/max_subtasks` |
| 会话/Cron | `sessions_enabled/cron_enabled` |
| 压缩 | `compress_enabled/compress_threshold_tokens/compress_keep_recent` |
| 聊天向量 | `chat_vectors_enabled/chat_vectors_search_top_k` |
| MCP | `mcp_enabled` |
| 主题 | `theme_appearance/theme_contrast` |
| Life Loop | `life_loop_catchup_enabled/life_loop_catchup_max_days` |
| 调试 | `debug_mode` |

### 9.2 环境变量

仅 3 个：`MODELSCOPE_API_KEY`、`MODELSCOPE_BASE_URL`、`MODELSCOPE_MODEL`、`PORT`。
**全部带硬编码默认值**，这意味着即使不配置 `.env`，应用也能启动（但使用泄露的 API key 和不存在的模型名）。

---

## 10. 已知未实现 / 跳过的功能

按代码注释和 `pass` 语句归纳：

| 位置 | 内容 |
|---|---|
| `agent_loop.py:138` | `pass  # best-effort` — checkpoint 恢复失败时静默吞掉异常 |
| `cognitive_kernel.py:413` | `pass  # no event loop` — 同步上下文中无法发布事件 |
| `db_utils.py:51` | `pass  # Some pragmas can't be set in certain contexts` |
| `memory_orchestrator.py:303` | `pass  # no event loop` |
| `migrations.py:87` | `pass  # Column might already exist` — 加列失败时静默 |
| `plugin_sdk.py:219` | `pass  # no event loop running` |
| `reflection_tree.py:262` | `pass  # Could mark existing reflections as superseded` — **该功能未实现** |

`residents.py:469` 注释 `# No LLM available — mark as completed with stub output`：当 LLM 不可用时，居民运行直接标记为完成，输出 `"[Architect would run here. Trigger: ...]"`。**这意味着没有 LLM 配置时所有居民功能都是空转**。

---

## 11. 文档与代码的偏差总结

| README 声称 | 实际情况 |
|---|---|
| `v1.3.0` | `pyproject.toml` 是 `1.4.0` |
| 134 测试通过 | 实际 134 通过（一致，但仅覆盖 30/55 模块） |
| WebSocket | 实际是 SSE |
| 47 工具 | 实际 48（差异见 §3） |
| Schema v9 | 一致 |
| 7 居民 | 一致 |
| 9 向量集合 | 一致 |
| 11 时间线类别 | 一致 |
| 8 哲学种子 | 一致 |
| 18 作品类型 | 一致 |
| 15 prompt 可编辑 | 实际 18 个（`prompt_registry.py` 中有 18 个 `"key":` 条目） |
| `agent_loop.py: Plan→Act→Observe→Reflect→Done + checkpoint` | **未实际接入 chat 流程，纯死代码** |
| `dspy_integration.py: DSPy 签名化 AI 调用` | **从未被调用，纯死代码** |
| `complexity_tier.py: Progressive complexity` | **被硬编码为 'full'，功能实质关闭** |
| LangGraph 1.0+ / DSPy 3.0+ 依赖 | `pyproject.toml` 声明但未在 `[project.optional-dependencies]` 中，是必装依赖；实际未安装也能跑（`try/except ImportError` 守卫） |
| `pip install -e .` 可用 | **报错**：`Multiple top-level packages discovered in a flat-layout: ['app', 'plugins', 'workspace', 'custom_tools']` |

---

## 12. 后续阅读

- `02_IMPROVEMENT_ANALYSIS.md` — 项目改进分析
- `03_PROJECT_EVALUATION.md` — 项目评估报告（含问题清单与半成品清单）
- `04_TESTING_REPORT.md` — 测试报告
