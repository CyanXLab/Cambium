<div align="center">

# 🌱 Cambium v2.0.0

### 个人 AI 的连续性引擎

**每个 AI 都能回答问题。**
**有些 AI 能记住。**
**几乎没有 AI 能成为某个人。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-176%20passing-brightgreen.svg)](tests/)
[![Schema](https://img.shields.io/badge/Schema-v9-orange.svg)](app/migrations.py)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-yellow.svg)](.github/workflows/ci.yml)

</div>

---

## 使命

> **让人与 AI 在一生中保持连续性。**

模型会变。记忆会变成故事。身份会持续存在。

Cambium 是一个开放的**连续性引擎**。它让任何 AI 拥有属于用户自己的身份、共同历史、成长轨迹和长期连续性。

---

## 核心公式

```
Continuity = Identity × Memory × Agency × Shared Experience × Reflection
```

---

## v2.0.0 重大更新

本版本基于源码审计 + 论文研究进行了全面升级：

### 新增基础设施
- **Pydantic Settings 配置系统**（`app/config.py`）—— 类型安全、分层、可验证
- **结构化日志**（`app/logging_config.py`）—— JSON 格式、级别控制、文件轮转
- **全局异常处理**（`app/exceptions.py`）—— 统一错误响应格式、请求日志中间件
- **现代 Lifespan 管理**（`app/lifespan.py`）—— 替换废弃的 `@app.on_event`

### 论文升级（7 篇论文 → 7 个模块）
| 论文 | 模块 | 升级内容 |
|------|------|---------|
| SSGM Framework | `memory_governance.py` | 完整隔离→验证→晋升管线 + 矛盾检测 + LLM 验证 |
| EvolveMem | `adaptive_retrieval.py` | 自适应检索权重 + 反馈循环 |
| Generative Agents | `reflection_tree.py` | 三层反思（观察→反思→元反思） |
| Identity Layer | `identity_consistency.py` | LLM 驱动身份评估 + 漂移检测 |
| CoALA + Claude Code | `agent_loop_v2.py` | **新激活**——Observe→Retrieve→Reason→Act→Learn 决策循环 |
| Mem0 | `memory_orchestrator.py` | 语义去重 + Jaccard 合并 |
| TSM | `cognitive_kernel.py` | 时间线 11 类事件 + 语义时间衰减 |

### Agent Loop v2（CoALA + Claude Code）
- 新端点 `POST /api/v2/chat/agent`
- 四级权限模式：plan / reflect / grow / autonomous
- 5 层上下文压缩（Claude Code §3.5）
- 异步认知更新（CoALA Step 5: Learn）
- Checkpoint 恢复（Claude Code §3.6）

### 工程化
- ✅ `pip install -e .` 修复（package discovery 配置）
- ✅ Docker + docker-compose
- ✅ GitHub Actions CI（Python 3.11/3.12 + Docker build）
- ✅ LICENSE (MIT) + CONTRIBUTING + CODE_OF_CONDUCT
- ✅ 移除硬编码 API key + 不存在的模型名
- ✅ 修复 `keepalive.sh` 硬编码路径
- ✅ 修复 `asyncio.get_event_loop()` 废弃用法
- ✅ 30 个 API 集成测试 + 12 个 LLM Mock 测试

### 测试
- **176 个测试全部通过**（原 134 + 新增 42）
- API 集成测试：30 个（覆盖 health/settings/memory/cognitive/residents/artifacts/philosophy/backup/governance/migrations）
- LLM Mock 测试：12 个（agent loop + memory governance + adaptive retrieval）

---

## 五层架构

### 第一层 — 基础设施
| 模块 | 功能 |
|------|------|
| `config.py` | **Pydantic Settings** 配置系统（v2 新增）|
| `logging_config.py` | **结构化日志**（JSON/Human 格式，v2 新增）|
| `exceptions.py` | **全局异常处理** + 请求日志中间件（v2 新增）|
| `lifespan.py` | **现代 Lifespan** 管理（v2 新增，替换 `@app.on_event`）|
| `db_utils.py` | SQLite WAL + busy_timeout（并发安全）|
| `migrations.py` | 前向 Schema 迁移（v9）|
| `model_adapter.py` | Protocol + 能力探测 + 回退 |
| `model_router.py` | 三级路由（premium/standard/local）|
| `api_providers.py` | 动态多供应商管理 |
| `event_bus.py` | asyncio 发布/订阅，30+ 事件类型 |
| `vector_store.py` | ChromaDB（首选）或 TF-IDF（回退）|
| `vector_indexer.py` | 全面向量化（9 种数据类型）|
| `backup.py` | 完整导出/导入（ZIP）|
| `prompt_registry.py` | 18 个 LLM prompt 用户可编辑 |
| `plugin_sdk.py` | 插件系统（plugin.yaml + tool.py + hooks.py）|
| `llm_utils.py` | 安全 LLM 响应解析 |

### 第二层 — 认知内核
| 模块 | 功能 | 论文来源 |
|------|------|---------|
| `cognitive_kernel.py` | 七支柱：身份/时间线(11类)/叙事/成长/目标/世界/自我 | — |
| `memory_orchestrator.py` | 四层记忆 + 艾宾浩斯衰减 + Jaccard 去重 | Mem0 |
| `memory_governance.py` | 隔离→验证→晋升 + 矛盾检测 + LLM 验证 | SSGM Framework |
| `adaptive_retrieval.py` | 自适应检索权重 + 反馈循环 | EvolveMem |
| `reflection_tree.py` | 三层反思（观察→反思→元反思）| Generative Agents |
| `identity_consistency.py` | LLM 驱动身份评估 + 漂移检测 | Identity Layer |
| `philosophy.py` | 价值观/信念/原则/反目标（8 条种子）|

### 第三层 — 能动性
| 模块 | 功能 |
|------|------|
| `agent_loop_v2.py` | **v2 新激活**：CoALA 决策循环 + Claude Code 权限 |
| `agent_loop.py` | Agent 状态机 + checkpoint（v1，保留兼容）|
| `residents.py` | 7 居民（独立状态/自动选择/多居民讨论）|
| `pushback.py` | 原则引用 + 记忆浮现 |
| `swarm.py` | Swarm Task 多 Agent 协作 |
| `langgraph_integration.py` | LangGraph StateGraph 实现 |
| `autogen_integration.py` | AutoGen 对话式协作 |
| `tools_ext.py` | 47 个工具（含 AI 服务器控制）|
| `tool_registry.py` | 统一工具注册 |

### 第四层 — 生命
| 模块 | 功能 |
|------|------|
| `life_loop.py` | 昼夜节律（固定 8:00 触发 + 首次检测 + 补上）|
| `mornings.py` | 每日 AI 信件 |
| `greeting.py` | AI 主动开场白 |
| `journal.py` | AI 辅助日志 |
| `co_experience.py` | "记得当时我们……" |
| `evolution.py` | 思想演化跟踪 |
| `discovery.py` | 每日惊喜 |
| `proactive_engine.py` | AI 主动联系 |
| `learning_engine.py` | 持续学习 |
| `daily_loop.py` | 晨报编排器 |

### 第五层 — 世界
| 模块 | 功能 |
|------|------|
| `inbox.py` | 万物入口（NP-OS 风格）|
| `artifacts.py` | 消息→作品（18 种类型，版本化）|
| `workspace.py` | 7 分区工作空间 |
| `chat_vectors.py` | 对话向量化 + 语义搜索 |
| `advanced_memory.py` | 情感跟踪 + 用户画像 |
| `meta_cognition.py` | 回复后自检 |

---

## 快速开始

### 方式 1：本地开发

```bash
git clone https://github.com/CyanXLab/Cambium
cd Cambium
pip install -e ".[dev]"           # 基础安装（含开发工具）
# 或 pip install -e ".[all]"      # 全功能安装（含 LangGraph/DSPy/AutoGen/ChromaDB）

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 MODELSCOPE_API_KEY 和 MODELSCOPE_MODEL

# 启动
python -m uvicorn app.main:app --port 3000 --reload
```

打开 http://localhost:3000

### 方式 2：Docker

```bash
git clone https://github.com/CyanXLab/Cambium
cd Cambium

# 配置环境
cp .env.example .env
# 编辑 .env

# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f cambium
```

### 方式 3：脚本启动

```bash
./scripts/run.sh        # 前台运行
./scripts/daemon.sh     # 守护进程
```

---

## 关键特性

### AI 居民（7 个）
Architect / Researcher / Writer / Planner / Historian / Critic / Explorer

- **单居民回复**：根据消息内容自动选择最合适的居民
- **多居民讨论**：检测"讨论/对比/权衡"等关键词 → 2-3 个居民讨论 → 综合结果
- **独立状态**：每个居民有自己的关注、观点、心情、活动日志
- **用户指定**：顶部栏下拉选择器可手动指定居民

### Agent Loop v2（CoALA + Claude Code）

新端点 `POST /api/v2/chat/agent`，实现完整的认知决策循环：

```
Observe → Retrieve → Reason → Act → Learn
  ↓          ↓          ↓        ↓       ↓
用户消息   认知内核   LLM思考   工具   异步认知更新
```

**四级权限模式**（Claude Code §3.4）：
| 模式 | 行为 |
|------|------|
| `plan` | 只读：分析但不修改任何认知状态 |
| `reflect` | 可写记忆，不可改身份 |
| `grow` | 可写记忆+成长，身份变更需确认 |
| `autonomous` | 全自动（信任模式）|

### Swarm Task（多 Agent 协作）
- 三种引擎：native / LangGraph / AutoGen
- 任务分解 → 分配居民 → 可见协作 → Critic 审查 → 交付结果
- 居民间通信全部存储，用户可查看完整对话流

### 记忆治理（SSGM Framework）
完整的三阶段记忆生命周期：
1. **QUARANTINE（隔离）**：新提取的记忆进入隔离区，不直接写入主存储
2. **VALIDATION（验证）**：规则验证 + LLM 一致性验证 + 矛盾检测
3. **PROMOTION（晋升）**：验证通过的记忆才进入主存储

### 自适应检索（EvolveMem）
- 检索权重 `[keyword, importance, recency, decay, layer]` 不是硬编码
- 根据用户反馈（positive/negative/neutral）自动调整
- 权重调整使用指数移动平均，边界 [0.05, 0.50]

### API 多供应商管理
- 动态添加任意数量的 API 供应商
- 自动获取模型列表
- 每个功能可选择使用哪个供应商
- 未分配的功能使用主 API

### 向量化（全面）
- 9 种数据类型全部向量化：记忆/聊天/作品/原则/发现/日志/时间线/共同经历/自主目标
- 创建时自动索引，删除时同步清理
- 通用搜索 API：跨所有集合搜索

---

## 工具列表（47 个）

| 类别 | 工具 |
|------|------|
| 时间 | get_current_time |
| 代码 | run_python, run_shell, install_package |
| 文件 | read_file, write_file, str_replace, regex_replace, multi_edit, apply_patch, file_append, file_prepend, insert_lines, delete_lines, file_move, file_copy, delete_file, make_directory, file_stat, file_tree, list_directory, grep, glob |
| 网络 | web_search, web_fetch |
| 记忆 | memory_search, memory_add |
| 技能 | skill_create, skill_update, skill_read, skill_list |
| 自定义工具 | save_custom_tool, run_custom_tool, list_custom_tools |
| 会话 | sessions_list, session_status, sessions_history, sessions_spawn |
| 任务 | todo_write, plan_write |
| AI 服务器控制 | get_setting, set_setting, list_settings, db_query, db_execute, list_tables, describe_table, api_call |

---

## 技术栈

| 层 | 选择 |
|----|------|
| 语言 | Python 3.11+ |
| Web | FastAPI + SSE (Server-Sent Events) |
| 数据库 | SQLite WAL |
| 向量 | ChromaDB / TF-IDF |
| Agent | LangGraph StateGraph / AutoGen / Native |
| 配置 | Pydantic Settings |
| 日志 | 结构化 JSON / Human 格式 |
| 测试 | pytest + pytest-asyncio + respx (LLM mock) |
| 容器 | Docker + docker-compose |
| CI | GitHub Actions |

---

## 项目结构

```
Cambium/
├── app/
│   ├── main.py              # FastAPI app + 283 路由
│   ├── config.py            # v2: Pydantic Settings
│   ├── logging_config.py    # v2: 结构化日志
│   ├── exceptions.py        # v2: 全局异常处理
│   ├── lifespan.py          # v2: 现代 Lifespan
│   ├── agent_loop_v2.py     # v2: CoALA + Claude Code Agent Loop
│   ├── cognitive_kernel.py  # 七支柱
│   ├── memory_orchestrator.py # 四层记忆 (Mem0)
│   ├── memory_governance.py # SSGM 治理
│   ├── adaptive_retrieval.py # EvolveMem 自适应
│   ├── reflection_tree.py   # Generative Agents 反思树
│   ├── identity_consistency.py # Identity Layer 身份评估
│   ├── residents.py         # 7 居民
│   ├── swarm.py             # Swarm Task
│   ├── tools_ext.py         # 47 工具
│   ├── ... (40+ 模块)
│   ├── static/js/
│   │   ├── app.js           # 核心逻辑
│   │   └── modules/         # 27 个模块文件
│   └── templates/index.html
├── tests/                   # 176 个测试
│   ├── test_cognitive_kernel.py
│   ├── test_comprehensive.py
│   ├── test_life_first_pivot.py
│   ├── test_residents_pivot.py
│   ├── test_api_integration.py  # v2: API 集成测试
│   └── test_llm_mock.py         # v2: LLM Mock 测试
├── docs/
│   ├── USAGE.md
│   └── audit/               # v2: 源码审计文档
│       ├── 01_FUNCTIONAL_SPEC.md
│       ├── 02_IMPROVEMENT_ANALYSIS.md
│       ├── 03_PROJECT_EVALUATION.md
│       ├── 04_TESTING_REPORT.md
│       └── 05_POST_FIX_REPORT.md
├── .github/workflows/ci.yml # v2: GitHub Actions CI
├── Dockerfile               # v2: Docker 支持
├── docker-compose.yml       # v2: Docker Compose
├── LICENSE                  # v2: MIT License
├── CONTRIBUTING.md          # v2: 贡献指南
├── CODE_OF_CONDUCT.md       # v2: 行为准则
└── pyproject.toml           # v2: 修复 package discovery
```

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest tests/ -v

# 运行测试 + 覆盖率
python -m pytest tests/ --cov=app --cov-report=term-missing

# Lint
ruff check app/ tests/

# 启动开发服务器（热重载）
python -m uvicorn app.main:app --port 3000 --reload
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

MIT — 你的身份，你的数据，你的连续性。永远。

详见 [LICENSE](LICENSE)。
