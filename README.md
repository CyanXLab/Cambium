<div align="center">

# 🌱 Cambium v1.3.0

### 个人 AI 的连续性引擎

**每个 AI 都能回答问题。**
**有些 AI 能记住。**
**几乎没有 AI 能成为某个人。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-green.svg)](https://langchain.ai)
[![DSPy](https://img.shields.io/badge/DSPy-3.0+-orange.svg)](https://dspy.ai)
[![Tests](https://img.shields.io/badge/测试-134%20通过-brightgreen.svg)](tests/)
[![Schema](https://img.shields.io/badge/Schema-v9-orange.svg)](app/migrations.py)

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

## 五层架构

### 第一层 — 基础设施
| 模块 | 功能 |
|------|------|
| `db_utils.py` | SQLite WAL + busy_timeout（并发安全）|
| `migrations.py` | 前向 Schema 迁移（v9）|
| `model_adapter.py` | Protocol + 能力探测 + 回退 |
| `model_router.py` | 三级路由（premium/standard/local）|
| `api_providers.py` | **动态多供应商管理**（添加/删除/功能分配）|
| `event_bus.py` | asyncio 发布/订阅，30+ 事件类型 |
| `vector_store.py` | ChromaDB（首选）或 TF-IDF（回退）|
| `vector_indexer.py` | **全面向量化**（记忆/聊天/作品/原则/发现/日志/时间线/共同经历/自主目标）|
| `backup.py` | 完整导出/导入（ZIP）|
| `prompt_registry.py` | 15 个 LLM prompt 用户可编辑 |
| `plugin_sdk.py` | 插件系统（plugin.yaml + tool.py + hooks.py）|
| `llm_utils.py` | 安全 LLM 响应解析 |

### 第二层 — 认知内核
| 模块 | 功能 | 论文来源 |
|------|------|---------|
| `cognitive_kernel.py` | 七支柱：身份/时间线(11类)/叙事/成长/目标/世界/自我 | — |
| `memory_orchestrator.py` | 四层记忆 + 艾宾浩斯衰减 + Jaccard 去重 | Mem0 |
| `memory_governance.py` | 隔离→验证→晋升 | SSGM Framework |
| `adaptive_retrieval.py` | 自适应检索权重 | EvolveMem |
| `reflection_tree.py` | 三层反思（观察→反思→元反思）| Generative Agents |
| `identity_consistency.py` | LLM 驱动身份评估 | Identity Layer |
| `philosophy.py` | 价值观/信念/原则/反目标（8 条种子）|

### 第三层 — 能动性
| 模块 | 功能 |
|------|------|
| `agent_loop.py` | Plan→Act→Observe→Reflect→Done + checkpoint |
| `residents.py` | 7 居民（独立状态/自动选择/多居民讨论）|
| `pushback.py` | 原则引用 + 记忆浮现 |
| `swarm.py` | **Swarm Task 多 Agent 协作** |
| `langgraph_integration.py` | **LangGraph StateGraph 实现** |
| `dspy_integration.py` | **DSPy 签名化 AI 调用** |
| `tools_ext.py` | **47 个工具**（含 AI 服务器控制）|
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

```bash
git clone https://github.com/CyanXLab/Cambium
cd Cambium
pip install -e .
pip install chromadb  # 可选：向量数据库
python -m uvicorn app.main:app --port 3000
```

打开 http://localhost:3000

---

## 关键特性

### AI 居民（7 个）
Architect / Researcher / Writer / Planner / Historian / Critic / Explorer

- **单居民回复**：根据消息内容自动选择最合适的居民
- **多居民讨论**：检测"讨论/对比/权衡"等关键词 → 2-3 个居民讨论 → 综合结果
- **独立状态**：每个居民有自己的关注、观点、心情、活动日志
- **用户指定**：顶部栏下拉选择器可手动指定居民

### Swarm Task（多 Agent 协作）
- 用 **LangGraph StateGraph** 实现：decompose → execute → review → END
- 任务分解 → 分配居民 → 可见协作 → Critic 审查 → 交付结果
- 居民间通信全部存储，用户可查看完整对话流

### 自主目标生成
- Life Loop 每日观察记忆/目标/Inbox/模式
- AI 识别值得行动的机会 → 生成提案
- 用户审批 → 自动创建 SwarmTask → 多 Agent 执行

### AI 服务器控制
AI 可通过工具完全控制服务器：
- 读取/修改设置（API 配置/系统提示词/功能开关）
- 执行 SQL 查询和写操作
- 调用内部 API（触发晨报/反思/Swarm 等）

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
| 文件 | read_file, write_file, str_replace, regex_replace, multi_edit, apply_patch, file_append, file_prepend, insert_lines, delete_lines, file_move, file_copy, delete_file, make_directory, file_stat |
| 搜索 | web_search, fetch_web_content |
| 记忆 | memory_search, memory_add |
| 技能 | skill_create, skill_update, skill_read, skill_list |
| 自定义工具 | save_custom_tool, run_custom_tool, list_custom_tools |
| 会话 | sessions_list, session_status, sessions_history, sessions_spawn, sessions_send |
| **AI 服务器控制** | get_setting, set_setting, list_settings, db_query, db_execute, list_tables, describe_table, api_call |

---

## 技术栈

| 层 | 选择 |
|----|------|
| 语言 | Python 3.11+ |
| Web | FastAPI + WebSocket |
| 数据库 | SQLite WAL |
| 向量 | ChromaDB / TF-IDF |
| Agent | LangGraph StateGraph |
| Prompt | DSPy Signature |
| 事件 | asyncio 发布/订阅 |

---

## 项目结构

```
Cambium/
├── app/
│   ├── main.py              # FastAPI, 284 路由
│   ├── cognitive_kernel.py  # 七支柱
│   ├── memory_orchestrator.py # 四层记忆
│   ├── agent_loop.py        # Agent 状态机
│   ├── residents.py         # 7 居民 + 独立状态
│   ├── swarm.py             # Swarm Task + 自主目标
│   ├── langgraph_integration.py # LangGraph 多 Agent
│   ├── dspy_integration.py  # DSPy 签名化调用
│   ├── vector_store.py      # ChromaDB/TF-IDF
│   ├── vector_indexer.py    # 全面向量索引
│   ├── api_providers.py     # 动态多供应商
│   ├── tools_ext.py         # 47 个工具
│   ├── ... (40+ 模块)
│   ├── static/js/
│   │   ├── app.js           # 核心逻辑
│   │   └── modules/         # 27 个模块文件
│   └── templates/index.html
├── .skills/                 # 项目技能
├── plugins/                 # 插件目录
├── tests/                   # 134 个测试
├── docs/USAGE.md            # 完整功能文档
└── pyproject.toml
```

---

## 许可证

MIT — 你的身份，你的数据，你的连续性。永远。
