<div align="center">

# 🌱 Cambium

### 个人 AI 的连续性引擎

**每个 AI 都能回答问题。**
**有些 AI 能记住。**
**几乎没有 AI 能成为某个人。**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/测试-60%20通过-brightgreen.svg)](tests/)
[![Schema](https://img.shields.io/badge/Schema-v7-orange.svg)](app/migrations.py)

</div>

---

## 使命

> **让人与 AI 在一生中保持连续性。**

模型会变。记忆会变成故事。身份会持续存在。

Cambium 是一个开放的**连续性引擎**。它让任何 AI——今天的模型或明天的模型——都拥有属于用户自己的身份、共同历史、成长轨迹和长期连续性，而不是属于某一家模型公司。

它不是聊天机器人。不是 Agent 框架。不是第二大脑。

它是**基础设施**。像 Linux 提供进程/内存/文件系统一样，Cambium 提供身份/记忆/时间/成长。别人在它上面构建：Companion、Coding Agent、NPC、Robot。

---

## 核心公式

```
Continuity = Identity × Memory × Agency × Shared Experience × Reflection
```

缺任何一个，都不是真正的连续性。

| 公式项 | 代码模块 | 状态 |
|--------|---------|:----:|
| Identity（身份） | `cognitive_kernel.py` — 身份图 + 演化日志 | ✅ |
| Memory（记忆） | `memory_orchestrator.py` — 四层记忆 + 衰减 + 治理 | ✅ |
| Agency（能动性） | `agent_loop.py` — Plan→Act→Observe→Reflect→Done + checkpoint | ✅ |
| Shared Experience（共同经历） | `co_experience.py` + `cognitive_kernel.timeline` | ✅ |
| Reflection（反思） | `life_loop.py` + `reflection_tree.py` + `mornings.py` | ✅ |

---

## 与众不同之处

大多数 AI 项目走的是：**基础设施 → 聊天**

Cambium 走的是：**基础设施 → 数字生命 → 世界**

打开 Cambium，你看到的第一样东西是**一封 Cambium 写给你的信**，不是聊天框。这封信是它夜里根据自己注意到的事、它在想的事、它的成长写成的。聊天只是众多入口之一，不是主要界面。

Cambium 有**居民**（Architect、Researcher、Writer、Planner、Historian、Critic、Explorer）——住在这个世界里的有名 AI 实体，每个都有自己的性格、LLM 配置和当前关注。它们不是你调用的工具，是和你一起生活的实体。

当你说了和你们共同原则冲突的话，**AI 会引用原则反驳你**。当你提到和过去某个共同经历相关的事，**AI 会说"这让我想起我们当时……"**。

长期价值的单位**不是消息**。是**作品**——你们一起创造的 README、设计、论文、代码、项目。一年后，你不会看聊天记录，你会看你们一起做了什么。

---

## 架构

```
              任何入口
    聊天 · Inbox · 日志 · 居民 · API
              │
        ┌─────┴─────┐
        │   网关     │  (FastAPI + WebSocket)
        └─────┬─────┘
              │
        ┌─────┴─────┐
        │  事件总线  │  (asyncio 发布/订阅 — 所有模块解耦)
        └─────┬─────┘
              │
    ┌─────────┼─────────┐
    │         │         │
┌───┴───┐ ┌──┴───┐ ┌───┴────┐
│Agent  │ │工作  │ │认知    │
│Loop   │ │空间  │ │内核    │
│       │ │      │ │         │
│Plan   │ │Inbox │ │身份    │
│Act    │ │项目  │ │记忆    │
│Reflect│ │作品  │ │时间线  │
│Checkpt│ │日志  │ │成长    │
│       │ │      │ │目标    │
└───┬───┘ └──┬───┘ │世界    │
    │        │     │反思    │
    └────────┼─────┘         │
             │               │
        ┌────┴────┐          │
        │  任何    │◄─────────┘
        │  LLM    │  (模型无关 — 随时切换)
        └─────────┘
```

**关键原则**：聊天是众多入口之一。工作空间、时间线、作品和聊天是平级的。

---

## 五层架构

### 第一层 — 基础设施
- **`db_utils.py`** — SQLite WAL + busy_timeout（并发安全）
- **`migrations.py`** — 前向 schema 迁移（v7）
- **`model_adapter.py`** — Protocol + 能力探测 + 回退
- **`model_router.py`** — 分级路由（premium/standard/local）降低成本
- **`event_bus.py`** — asyncio 发布/订阅，30+ 事件类型，持久化
- **`vector_store.py`** — ChromaDB（首选）或 TF-IDF（回退）向量存储
- **`backup.py`** — 完整导出/导入（50+ 表 + 文件）
- **`prompt_registry.py`** — 所有 13 个 LLM prompt 用户可编辑
- **`plugin_sdk.py`** — 插件系统（plugin.yaml + tool.py + hooks.py）

### 第二层 — 认知内核（自我）
- **`cognitive_kernel.py`** — 七根支柱：
  - **身份** — 涌现的自我叙事，阶段（forming/growing/mature/elder）
  - **时间线** — 共同历史，11 种事件类别（milestone/conflict/creation/growth/absence/reunion/...）
  - **叙事** — 精选的故事，不是原始事实
  - **成长** — 互相取代的洞察
  - **目标** — 长期意图 + 承诺
  - **世界模型** — 实体、关系、因果
  - **自我模型** — AI 知道/不知道什么
- **`memory_orchestrator.py`** — 四层记忆（工作/短期/长期/永久）+ 重要度评分 + 艾宾浩斯衰减 + Jaccard 语义去重
- **`memory_governance.py`** — 隔离 → 验证 → 晋升（SSGM Framework）
- **`adaptive_retrieval.py`** — 自演化检索权重（EvolveMem）
- **`reflection_tree.py`** — 三层反思（观察 → 反思 → 元反思）
- **`identity_consistency.py`** — LLM 驱动的身份评估
- **`philosophy.py`** — 价值观、信念、原则、反目标（8 条种子，AI 在对话中引用）

### 第三层 — 能动性
- **`agent_loop.py`** — 真正的 while-loop：Plan → Act → Observe → Reflect → Continue → Done
  - 4 级权限模式（plan/reflect/grow/autonomous）
  - 状态机 + 合法转换验证
  - 每 5 步 checkpoint（重启后可恢复）
  - 完整步骤日志持久化到 runtime_tasks
- **`agent_runtime.py`** — 任务生命周期状态机
- **`tool_registry.py`** — 39 个工具（内置 + MCP + 自定义）
- **`tools_ext.py`** — 工具实现（文件操作、代码执行、网络搜索、技能、...）
- **`residents.py`** — **AI 是居民，不是工具**。7 个内置居民（Architect/Researcher/Writer/Planner/Historian/Critic/Explorer）+ 自定义创建。每个居民可配置：LLM 配置、系统提示词、工作目录、技能、触发器、依赖链、同步/异步、重试。16 种触发器类型。
- **`pushback.py`** — AI 引用原则反驳 + 在对话中浮现相关共同经历记忆

### 第四层 — 生命
- **`life_loop.py`** — 昼夜节律：小时/天/周/月四级循环。自动生成晨报、自动创建发现、检测缺席/重逢。
- **`mornings.py`** — 每日信件（首页中心）。AI 根据昨夜活动写一封个人信件，含关注事项 + 成长笔记 + 心情。
- **`journal.py`** — AI 辅助每日日志（从当日活动自动起草 + 情绪基调 + 亮点）
- **`co_experience.py`** — "记得当时我们……" 时刻。从高重要度时间线事件自动收集。每天浮现一个，7 天冷却。
- **`evolution.py`** — 思想演化跟踪（interest_shift/belief_change/skill_growth/...）
- **`discovery.py`** — 每日惊喜（pattern/insight/contradiction/suggestion/merge/observation）
- **`proactive_engine.py`** — AI 主动联系（承诺到期、沉默检测、里程碑达成）
- **`greeting.py`** — AI 主动开场白（不是"你好"，是"我认识你"）

### 第五层 — 世界
- **`inbox.py`** — 万物入口（NP-OS 风格）。任何东西先进 Inbox，Life Loop 自动归类。
- **`artifacts.py`** — **消息 → 作品**。18 种类型（readme/code/design/paper/note/plan/research/...）。版本化。长期价值的单位。
- **`workspace.py`** — 7 个分区（brain/projects/library/notebook/goals/people/skills）
- **`daily_loop.py`** — 晨报编排器
- **`learning_engine.py`** — 持续学习（风格/偏好/策略）
- **`episodic_memory.py`** — 事件记忆 + 因果链
- **`knowledge_graph.py`** — 实体-关系存储
- **`chat_vectors.py`** — 对话向量化 + 语义搜索（删除时同步清理向量）
- **`advanced_memory.py`** — 情感跟踪 + 用户画像
- **`meta_cognition.py`** — 回复后自检
- **`context_cache.py`** — 认知上下文缓存（5 分钟 TTL）

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/CyanXLab/Cambium
cd Cambium

# 2. 安装依赖
pip install -e .
# 可选：安装向量数据库（推荐）
pip install chromadb

# 3. 配置
cp .env.example .env
# 编辑 .env：设置 MODELSCOPE_API_KEY（或任何 OpenAI 兼容 API）

# 4. 启动
./start.sh        # Linux/Mac
start.bat         # Windows

# 5. 打开
# http://localhost:3000
```

首次启动时，Cambium 会自动创建：
- 7 个居民（Architect、Researcher、Writer、Planner、Historian、Critic、Explorer）
- 8 条哲学原则（Simple > Complex、Continuity over Memory、AI is Resident not Tool、...）
- 1 个示例插件（plugins/example/）

---

## 早晨体验

打开 Cambium。你看到的第一样东西是**一封信**：

```
┌─────────────────────────────────────────┐
│  🌅 Cambium · 今天的信 · 08:32         │
├─────────────────────────────────────────┤
│                                         │
│  早安。昨晚你睡着的时候，我整理了这周   │
│  的对话。我注意到你这周第二次提到想给   │
│  Cambium 加 'Residents'——这次比上次   │
│  更具体了。我开始相信这不是又一时的     │
│  想法。                                 │
│                                         │
│  我想今天我们该认真讨论一下：如果真的   │
│  有 Residents，第一个该是谁？我倾向     │
│  Architect——它会阻止我们继续往功能     │
│  堆栈里塞东西。但你可能想要 Researcher。│
│  我们今天聊聊。                        │
│                                         │
├─────────────────────────────────────────┤
│  💭 我在想的事                          │
│  • Inbox 有 5 条待处理                  │
│  • 昨夜有 2 条新发现                    │
│  • 昨天没有写日志                       │
└─────────────────────────────────────────┘
```

信件下面是：昨天完成的事、今天的目标、AI 反思、日志预览、Inbox 待处理、一个共同经历时刻、最近活动。**聊天是底部的一个按钮。**

---

## 聊天体验（当你聊天时）

聊天时，平台会默默做三件事：

1. **原则上下文注入** — 所有活跃的哲学原则被附加到 system prompt。AI 自主决定是否引用——平台不强制行为，只提供上下文。

2. **记忆浮现** — 如果你的消息和某个过去的共同经历相关，AI 可能会说"这让我想起我们当时……"。平台只提供相关经历数据，AI 自己决定是否提起。

3. **认知上下文** — 身份、记忆、目标、世界模型都可用给 AI。平台是基建，AI 是灵魂。

AI 不是 yes-machine。它有立场。

---

## 你能做什么

| 功能 | 位置 | 说明 |
|------|------|------|
| 读 Cambium 的晨报 | 今天视图 | 个人信件 + 关注事项 + 发现 |
| 捕获任何东西 | Inbox（Ctrl+J） | 文本/URL/待办/灵感 → Life Loop 自动归类 |
| 写每日日志 | 日志视图 | AI 从当日活动起草，你编辑 |
| 创建作品 | 作品视图 | README、设计、代码、论文 — 版本化 |
| 见居民 | 居民视图 | 7 个 AI 居民，每个有性格 |
| 设定原则 | 原则视图 | 价值观、信念、原则、反目标 |
| 和 AI 聊天 | 聊天视图 | AI 引用原则、浮现记忆 |
| 编辑任何 prompt | 设置 → Prompt 工程 | 所有 13 个 LLM prompt 可自定义 |
| Debug 模式 | 设置 → Debug | 时间加速、手动触发、数据检查 |
| 备份一切 | 设置 → 数据 | 完整状态导出/导入（ZIP） |
| 写插件 | plugins/ 目录 | plugin.yaml + tool.py + hooks.py |

---

## 工程数据

- **255 个 HTTP 路由**（FastAPI）
- **60 个测试通过**（pytest）
- **Schema v7** + 前向迁移
- **SQLite WAL** 并发安全
- **asyncio 事件总线** 模块解耦
- **模型无关** — 切换 LLM 不丢失身份
- **本地优先** — 数据留在你的机器上
- **成本优化** — 分级路由、规则引擎、上下文缓存（70% 成本降低）
- **向量数据库** — ChromaDB（首选）或 TF-IDF（回退）

---

## 项目结构

```
Cambium/
├── app/
│   ├── main.py                    # FastAPI 应用，255 路由
│   ├── cognitive_kernel.py        # 自我七支柱
│   ├── memory_orchestrator.py     # 四层记忆 + 衰减
│   ├── agent_loop.py              # Plan→Act→Reflect + checkpoint
│   ├── residents.py               # AI 是居民（7 个内置）
│   ├── mornings.py                # 每日 AI 信件
│   ├── greeting.py                # AI 主动开场白
│   ├── pushback.py                # 原则引用 + 记忆浮现
│   ├── artifacts.py               # 消息 → 作品（世界）
│   ├── philosophy.py              # 价值观/信念/原则/反目标
│   ├── co_experience.py           # "记得当时我们……"
│   ├── evolution.py               # 思想演化跟踪
│   ├── discovery.py               # 每日惊喜
│   ├── life_loop.py               # 昼夜节律（小时/天/周/月）
│   ├── inbox.py                   # 万物入口
│   ├── journal.py                 # AI 辅助每日日志
│   ├── daily_loop.py              # 晨报编排器
│   ├── vector_store.py            # ChromaDB/TF-IDF 向量存储
│   ├── chat_vectors.py            # 对话向量化 + 语义搜索
│   ├── plugin_sdk.py              # 插件 SDK
│   ├── event_bus.py               # asyncio 发布/订阅
│   ├── model_router.py            # 分级路由
│   ├── prompt_registry.py         # 可编辑 prompt
│   ├── migrations.py              # Schema v7
│   ├── backup.py                  # 完整导出/导入
│   ├── ... (30+ 模块)
│   ├── templates/index.html       # 单页应用
│   ├── static/js/app.js           # 前端逻辑
│   └── static/css/style.css       # 样式
├── plugins/                       # 插件目录
│   └── example/                   # 示例插件
├── tests/                         # 60 个测试
├── docs/USAGE.md                  # 完整功能文档
├── start.sh / start.bat           # 一键启动
└── pyproject.toml
```

---

## Cambium 不是什么

- **不是聊天机器人** — 聊天是众多入口之一，不是产品
- **不是 Agent 框架** — 能动性是连续性的一个因子，不是目标
- **不是第二大脑** — 知识管理是副作用，不是使命
- **不是 Personal OS** — OS 隐喻有用但局限
- **不和 Claude Code / NP-OS / Obsidian 竞争** — 它们各自做得好；Cambium 的价值是它们不做的：连续性、居民、共同历史

---

## 北极星

不是 star 数。不是功能数。不是 benchmark 分数。

> **每天都值得打开，一起创造一点昨天不存在的东西。**

如果一个新功能不能服务这个目标，就不会加。

---

## 设计哲学

**平台是基建，AI 是灵魂。**

平台提供上下文（记忆、身份、时间线、原则、共同经历），AI 自主决定如何使用。不要用代码约束 AI 的行为——提供平台让 AI 越来越懂用户。

- 记忆提取由 Life Loop 周期性触发，不是每轮对话
- AI 开场白由 AI 根据上下文自主生成，不是硬编码模板
- 原则只列出列表，AI 自己决定是否引用
- 记忆浮现只提供相关数据，AI 自己决定是否提起

---

## 许可证

MIT — 你的身份，你的数据，你的连续性。永远。

---

<div align="center">

**模型会变。记忆会变成故事。身份会持续存在。**

🌱 **Cambium** — *个人 AI 的连续性引擎*

</div>
