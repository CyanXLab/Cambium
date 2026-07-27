# Cambium 项目评估报告

> 本文档对 Cambium 项目做整体评估，列出问题清单、半成品清单、设计冲突与综合评分。
> 评估基于源码事实，不依赖 README 与 docs/USAGE.md 的描述。

---

## 1. 项目整体评估

### 1.1 一句话定性

Cambium 是一个**野心远大于工程能力**的个人 AI 连续性引擎原型。它提出了一个有思考的产品愿景（Continuity = Identity × Memory × Agency × Shared Experience × Reflection），并且在认知内核、记忆编排、多 Agent 协作等模块上做了真实的功能实现，但同时存在**密钥泄露、模型名编造、安全裸奔、死代码堆积、测试覆盖不足**等严重工程问题，**目前的状态不适合任何形式的对外部署**。

### 1.2 量化指标

| 维度 | 数值 | 评价 |
|---|---|---|
| Python 代码行数 | 25,763 行（55 个模块） | 大型个人项目 |
| JS 代码行数 | 8,796 行（28 个文件） | 中型前端 |
| 测试代码行数 | 2,199 行（4 个文件） | 不足 |
| 测试/代码比 | 8.5% | 偏低（建议 ≥ 20%） |
| 测试用例数 | 134 | 数量虚高（仅覆盖 30/55 模块） |
| API 路由数 | 281 | 数量庞大 |
| Git 提交数 | 22 | 极少（开发周期 < 2 天） |
| 首末提交间隔 | 2026-07-25 → 2026-07-27 | **2 天内完成 26k 行代码** |
| 文档行数 | README 223 + USAGE 1566 = 1789 行 | 充足但不可靠 |
| TODO/FIXME 标记 | 0 | ❌ 不是没有问题，是不标记问题 |
| 死代码模块 | 3 个（agent_loop / dspy_integration / complexity_tier） | 高 |
| 死函数 | ≥ 1 个（_embed_for_rag） | 中 |
| 安全防护 | 0（无 CORS、无认证、无审计） | ❌ |
| 硬编码密钥 | 6 处 | ❌ |
| 硬编码路径 | 1 处（keepalive.sh） | ❌ |
| 硬编码品牌名 | 14 处（CyanX AI） | 中 |

### 1.3 综合评分

按 10 分制打分：

| 维度 | 评分 | 说明 |
|---|---|---|
| 产品愿景 | 8/10 | "连续性引擎"概念清晰，公式化表达有思考 |
| 功能广度 | 9/10 | 7 居民、9 向量集合、47 工具、281 路由——确实做了很多 |
| 功能深度 | 5/10 | 核心模块实现完整，但多个"宣传特性"是死代码 |
| 代码质量 | 3/10 | 6k 行单文件、364 处 `except Exception`、197 处 `print`、0 处日志框架 |
| 安全性 | 1/10 | 密钥泄露 + 无认证 + AI 可执行任意代码 + SQL 注入面 |
| 测试覆盖 | 3/10 | 134 测试只覆盖 55% 模块，0 个 API 集成测试 |
| 文档质量 | 4/10 | 数量充足，但 README 与代码事实多处不符 |
| 工程实践 | 2/10 | 无 CI、无 LICENSE、无 CONTRIBUTING、无 lint、无 type check |
| 可维护性 | 2/10 | 单文件 6k 行 + 死代码堆积 + 配置扁平化 |
| 社区就绪度 | 1/10 | 无 LICENSE 文件、品牌名硬编码、安装即报错 |
| **加权总分** | **3.8/10** | **原型阶段，离生产可用还差很远** |

---

## 2. 问题清单（按严重度排序）

### 2.1 致命问题（5 项）

#### F1. ModelScope API Key 全仓库泄露

- **位置**：6 个文件
- **现象**：`ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9` 作为默认值在 `app/main.py:125`、`app/model_router.py:80`、`scripts/keepalive.sh:3`、`scripts/daemon.sh:17`、`scripts/run.sh:14`、`.env.example:5` 中硬编码
- **影响**：
  - 任何拿到代码的人都能用这个 key 调用 ModelScope API
  - key 配额会被消耗光，原账号可能被冻结
  - 如果 key 有其他权限（如读取用户信息、删除模型），后果更严重
- **修复**：见 `02_IMPROVEMENT_ANALYSIS.md` P0-1

#### F2. 默认模型名 `Qwen/Qwen3.5-397B-A17B` 在 ModelScope 不存在

- **位置**：6 个文件（同 F1）
- **现象**：Qwen 系列从未发布过 `Qwen3.5` 这个版本号，`397B-A17B` / `122B-A10B` 这种参数规格也是虚构
- **影响**：
  - 新用户按 README 启动后立即收到 404 错误
  - 设置页"模型槽 1/2"显示不存在的模型
  - 让人怀疑整个项目是否真的能跑
- **推测**：这是 AI 生成代码时的"幻觉"，被原 README 与 docs/USAGE.md 一并传播
- **修复**：见 `02_IMPROVEMENT_ANALYSIS.md` P0-2

#### F3. FastAPI 应用零安全防护

- **位置**：`app/main.py`
- **现象**：
  - 未配置 CORS——任意源跨域访问
  - 未配置任何认证中间件——281 个 API 端点完全开放
  - 默认监听 `0.0.0.0:3000`（见 `scripts/run.sh:24`）
- **影响**：
  - 任何能访问该端口的人都能读取所有用户记忆、对话、画像
  - 能修改 API key、系统提示词等所有配置
  - 能通过 `db_query` / `db_execute` 工具直接执行任意 SQL（包括 DROP TABLE）
  - 如果部署在公网，等于完全裸奔
- **修复**：见 `02_IMPROVEMENT_ANALYSIS.md` P0-4

#### F4. AI 工具完全无沙箱

- **位置**：`app/tools_ext.py`
- **现象**：
  - `run_python`：调用 `subprocess.run([sys.executable, script])`，可 `import os; os.system("rm -rf ~")`
  - `run_shell`：黑名单仅 16 项子串匹配，可被 `rm --recursive --force $HOME`、`bash -c 'rm -rf /'`、`x=rm; $x -rf /` 等多种方式绕过
  - `install_package`：无白名单，可安装任意恶意包
  - `save_custom_tool` / `run_custom_tool`：可保存任意 Python 文件并执行——等价于任意代码执行
  - `_safe_resolve` 允许 `custom_tools/` 和 `.skills/` 两个目录——AI 可修改自己的工具代码
- **影响**：
  - LLM 一旦被提示注入（用户上传的文件、网页内容、邮箱正文等），可执行任意命令
  - 攻击面包括：删除用户文件、窃取 SSH key、上传数据到外部、加密文件勒索
- **修复**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-2

#### F5. `pyproject.toml` 配置错误导致 `pip install -e .` 报错

- **位置**：`pyproject.toml`
- **现象**：使用 flat-layout 但未声明 package discovery，setuptools 检测到 `app/`、`plugins/`、`workspace/`、`custom_tools/` 四个顶级包时拒绝构建
- **影响**：README 推荐的安装方式直接失败，新用户第一印象就崩
- **修复**：见 `02_IMPROVEMENT_ANALYSIS.md` P0-3

---

### 2.2 高严重度问题（8 项）

#### H1. `agent_loop.py` 整模块死代码

- **位置**：`app/agent_loop.py`（321 行）+ `app/main.py:70`（import）
- **现象**：定义了 `AgentLoop` 类、`PermissionMode` 4 种模式、`PERMISSION_MATRIX`、`TaskState` 状态机，但 `main.py` 中 0 次调用 `agent_loop.xxx`，`AgentLoop(` 仅在自身 docstring 出现
- **影响**：
  - README 宣传的 "Plan→Act→Observe→Reflect→Done + checkpoint" 完全没接入实际 chat 流程
  - 4 种权限模式（plan/reflect/grow/autonomous）形同虚设
  - 测试只测了状态转换的数据结构，从未实例化运行
- **建议**：删除整模块，或真正接入 chat 流程

#### H2. `dspy_integration.py` 整模块死代码

- **位置**：`app/dspy_integration.py`（148 行）+ `app/main.py:120`（import）
- **现象**：定义了 5 个 DSPy Signature（MemoryEdit / CognitiveExtraction / Reflection / MorningLetter / ResidentResponse），但全仓库 0 处实际调用
- **影响**：README 宣传的 "DSPy 签名化 AI 调用" 完全没生效；`dspy` 是必装依赖但从未使用
- **建议**：删除整模块，或真正用 DSPy 替换硬编码 prompt

#### H3. `complexity_tier.py` 业务逻辑被关闭

- **位置**：`app/complexity_tier.py:17`
- **现象**：`get_complexity_tier()` 硬编码返回 `"full"`，注释写 "All features are always enabled. Returns 'full' for everyone."
- **影响**：模块顶层 docstring 描述的 Day 1-7 MINIMAL / Day 7-30 GROWING / Day 30-90 MATURE / Day 90+ FULL 四档渐进复杂度系统完全不生效；Git 提交 `e9b85aa` 标题"移除渐进复杂度"也证实了这点
- **建议**：删除模块，或重新激活 tier 切换逻辑

#### H4. `_embed_for_rag` 死函数

- **位置**：`app/main.py:5211-5234`
- **现象**：函数定义了 RAG embedding API 调用逻辑，但全文件 0 次调用
- **影响**：前端设置页有 `rag_embedding_provider` 选项，但实际 RAG 检索走的是 `vector_store` 的 TF-IDF / ChromaDB 路径，与此函数完全断开
- **建议**：删除函数 + 前端选项，或接入 `vector_store`

#### H5. `keepalive.sh` 硬编码开发者私有路径

- **位置**：`scripts/keepalive.sh:2`
- **现象**：`cd /home/z/my-project/ai-chat`——这是开发者私有路径，其他机器上不存在
- **影响**：脚本完全无法使用
- **建议**：改为相对路径 `cd "$(dirname "$0")/.."`

#### H6. 281 个 API 路由 0 个集成测试

- **位置**：`tests/`
- **现象**：134 个测试全部是单元测试（直接调用模块函数），未使用 `TestClient` 测试任何 HTTP 路由
- **影响**：
  - 路由签名变化无法被测试捕获
  - 请求/响应 schema 无回归保护
  - 重构 main.py 时无安全网
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P3-1

#### H7. 22 个核心模块 0 测试

- **位置**：`tests/`
- **现象**：55 个模块中 22 个完全无测试，包括：`main.py`、`tools_ext.py`、`swarm.py`、`life_loop.py`、`sessions.py`、`vector_indexer.py`、`knowledge_graph.py`、`episodic_memory.py`、`meta_cognition.py`、`identity_consistency.py`、`reflection_tree.py`、`proactive_engine.py`、`rule_engine.py`、`context_cache.py`、`api_providers.py`、`cron.py`、`advanced_memory.py`、`debug_mode.py`、`llm_utils.py`、`tool_registry.py`、`langgraph_integration.py`、`autogen_integration.py`
- **影响**：核心功能（多 Agent 协作、昼夜节律、向量检索、知识图谱、情节记忆）无任何回归保护
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P3-2

#### H8. 对话压缩阈值与模型上下文不匹配

- **位置**：`app/main.py:810` `DEFAULT_SETTINGS["compress_threshold_tokens"] = "80000"`
- **现象**：默认 80k tokens 阈值，但 Qwen 系列模型上下文窗口最大 32k（部分新模型 128k）。对于 32k 模型，请求会先因超长报错，压缩永远不会触发
- **影响**：宣传的"长对话自动压缩"功能对大多数模型实际不生效
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-7

---

### 2.3 中严重度问题（10 项）

#### M1. `CyanX AI` 品牌名在 14 处硬编码

- **位置**：`app/main.py:3203,4044,4967`、`app/memory_orchestrator.py:14,899`、`app/advanced_memory.py:3`、`app/chat_vectors.py:3`、`app/episodic_memory.py:4`、`app/knowledge_graph.py:4`、`app/meta_cognition.py:13`、`app/templates/index.html:1628` 等
- **影响**：项目命名为 Cambium 但内部仍是 CyanX AI，定位混乱；社区复用门槛高
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-3

#### M2. 反思流程无独立开关

- **位置**：`app/main.py:4923` `_background_reflection_loop`
- **现象**：每 10 分钟检查一次，触发条件为 30+ 新消息。要关闭只能把 `profile_auto_update` 设为 false，但该开关同时关闭画像更新等其他功能
- **影响**：
  - 用户无法单独关闭反思
  - 反思会消耗大量 LLM 调用配额
  - 反思会自动抽取知识图谱三元组与情节记忆——隐私风险
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-6

#### M3. 知识图谱与情节记忆自动抽取

- **位置**：`app/main.py:4980-5007`
- **现象**：每次反思触发后，自动调用 LLM 抽取知识图谱三元组与情节记忆，无独立开关、无用户确认
- **影响**：用户对话内容被自动结构化存储，可能包含敏感信息；用户无法预览/删除单条三元组
- **建议**：增加 `kg_auto_extract` / `episodic_auto_extract` 独立开关；前端提供三元组编辑界面

#### M4. README 与代码事实多处不符

- **位置**：`README.md`
- **现象**：
  - 版本号 `v1.3.0` vs `pyproject.toml` `1.4.0`
  - 声称 WebSocket，实际是 SSE
  - 声称 47 工具，实际 48
  - 声称 15 prompt 可编辑，实际 18
  - 声称 `agent_loop.py: Plan→Act→Observe→Reflect→Done`，实际死代码
  - 声称 `dspy_integration.py: DSPy 签名化 AI 调用`，实际死代码
  - 声称 `complexity_tier.py: Progressive complexity`，实际硬编码为 full
- **影响**：用户/贡献者被误导；评估者无法信任文档
- **建议**：全面校对，或直接以审计文档替换

#### M5. `print()` 用作日志（197 处）

- **位置**：全局
- **现象**：无日志级别、无结构化、无文件输出，全部 `print()` 到 stdout
- **影响**：
  - 生产环境无法过滤日志级别
  - 无法聚合到 ELK / Loki
  - 错误追踪只能靠肉眼
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P2-3

#### M6. `except Exception` 滥用（364 处）

- **位置**：全局
- **现象**：包括 152 处 `except: pass` 或 `except Exception: pass`，静默吞掉所有错误
- **影响**：
  - 问题难以定位
  - 数据库加列失败、事件发布失败、checkpoints 恢复失败等关键错误被掩盖
  - 测试通过但功能可能已损坏
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P2-4

#### M7. 单文件 6,283 行

- **位置**：`app/main.py`
- **现象**：283 个路由 + 大量业务逻辑挤在一个文件，6,283 行
- **影响**：
  - IDE 索引缓慢
  - Git blame 几乎不可读
  - 多人协作必冲突
  - 新人无法快速定位
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P2-1

#### M8. 已废弃的 `@app.on_event("startup")`

- **位置**：`app/main.py:4891`
- **现象**：FastAPI 已废弃 `on_event`，推荐改用 `lifespan` 上下文管理器
- **影响**：运行时打印大段 DeprecationWarning；未来 FastAPI 版本可能移除
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-8

#### M9. `asyncio.get_event_loop()` 废弃用法

- **位置**：`cognitive_kernel.py:407`、`memory_orchestrator.py:297`、`plugin_sdk.py:211`
- **现象**：Python 3.10+ 在无运行循环时发出 DeprecationWarning，3.14 计划完全移除
- **影响**：未来 Python 版本会失败
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P1-9

#### M10. 数据库迁移无回滚

- **位置**：`app/migrations.py`
- **现象**：仅前向迁移，每个版本只定义 upgrade，无 downgrade
- **影响**：升级失败时只能手动改 schema 或恢复备份
- **建议**：见 `02_IMPROVEMENT_ANALYSIS.md` P2-5

---

### 2.4 低严重度问题（6 项）

#### L1. 仓库根目录无 LICENSE 文件

- README 声明 MIT，但根目录无 LICENSE 文件。法律上不构成有效授权。

#### L2. 无 CI/CD 配置

- 无 `.github/workflows/`，无 lint、无 type check、无自动测试
- 提交 `7b8b5f7` 标题"feat: DSPy 集成 + README/USAGE 完整更新"——README 与 USAGE 由 AI 编写，未人工校对

#### L3. 无 CONTRIBUTING / CODE_OF_CONDUCT

- 社区贡献无指引

#### L4. 无 type hints 在大部分函数

- Pydantic 模型有类型，但普通函数 `def foo(x, y):` 大量存在
- 无 mypy / pyright 配置

#### L5. `docs/USAGE.md` 由 AI 生成，多处与代码不一致

- 例如 §1 写"39 个工具"，实际 48 个
- 例如 §6 写"工作目录（如 /workspace/...）"，实际是 `<repo>/workspace/`
- 用户已明确指出"AI 写的可能有错和幻觉"

#### L6. 前端 `app.js` 5,314 行

- 单文件包含状态管理、事件绑定、UI 渲染、API 调用
- 27 个 modules 通过 IIFE + 全局 `window.App` 通信
- 无组件化、无 virtual DOM、无响应式

---

## 3. 半成品与死代码清单

### 3.1 完全死代码（导入但 0 次调用）

| 模块/函数 | 行数 | 宣传文案 | 实际状态 |
|---|---|---|---|
| `app/agent_loop.py` | 321 | "Plan→Act→Observe→Reflect→Done + checkpoint" | 死代码，仅 docstring 引用 |
| `app/dspy_integration.py` | 148 | "DSPy 签名化 AI 调用" | 死代码，从未调用 |
| `app/main.py::_embed_for_rag` | 24 | "RAG with optional API-based embedding" | 死函数，前端选项无效 |
| `app/main.py` 中 `from app import rule_engine` | 1 | — | 死引用（rule_engine 仅被 memory_governance 使用） |

**小计：~500 行死代码**

### 3.2 业务逻辑被关闭（模块存在但功能 stub）

| 模块 | 现状 |
|---|---|
| `app/complexity_tier.py` | `get_complexity_tier()` 硬编码返回 `"full"`，整个渐进复杂度系统关闭 |
| `app/residents.py:469` | LLM 不可用时直接返回 `"[Architect would run here. Trigger: ...]"`——居民运行变空转 |
| `app/reflection_tree.py:262` | `pass  # Could mark existing reflections as superseded`——supersession 未实现 |

### 3.3 实现存在但功能不可用

| 功能 | 问题 |
|---|---|
| 对话压缩 | 阈值 80k > 模型上下文 32k，永不触发 |
| RAG API embedding | 函数定义但未接入 vector_store |
| `web_search` 工具 | Bing HTML 抓取依赖正则，Bing 页面结构变化即失效 |
| `pip install -e .` | pyproject.toml 配置错误，直接报错 |
| `keepalive.sh` | 硬编码 `/home/z/my-project/ai-chat`，其他机器无法使用 |

### 3.4 宣传特性但无实际接入

| 特性 | 宣传位置 | 实际状态 |
|---|---|---|
| LangGraph 1.0+ | README 技术栈 | `langgraph_integration.py` 实现完整，但仅 1 个路由 `/api/swarm/tasks/{task_id}/execute-langgraph` 暴露，需手动调用 |
| DSPy 3.0+ | README 技术栈 | `dspy_integration.py` 死代码，从未使用 |
| AutoGen | `pyproject.toml` 必装依赖 | `autogen_integration.py` 实现完整，但仅 1 个路由暴露 |
| WebSocket | README 技术栈 | 实际是 SSE |
| MCP 服务器 | README 工具列表 | 实现完整，但默认未配置任何 MCP 服务器 |

---

## 4. 设计冲突与矛盾

### 4.1 "开放引擎" vs "个人品牌"

README 写："Cambium 是一个开放的连续性引擎"。但代码中 14 处硬编码 `CyanX AI` 作为 AI 名字，包括反思 prompt、晨报模板、设置页文案。

**冲突**：开放引擎应支持自定义 AI 身份，但当前实现绑定个人品牌。

### 4.2 "AI 是居民不是工具" vs "AI 全权代理用户"

`philosophy.py` 种子原则第 3 条："AI is Resident, not Tool"。但 `tools_ext.py` 给 AI 提供了 `run_shell`、`run_python`、`install_package`、`save_custom_tool`、`db_execute` 等工具，**没有任何权限校验**——AI 可以完全控制服务器。

**冲突**：理念上强调 AI 的"居民身份"（有限能力 + 独立意志），实际上把 AI 当成"全能管理员"（可执行任意操作）。

### 4.3 "记忆 ≠ 身份 ≠ 连续性" vs "记忆自动抽取一切"

`philosophy.py` 种子原则第 6 条明确区分这三个概念。但 `main.py::_background_reflection_loop` 每 10 分钟自动从对话中抽取记忆、知识图谱三元组、情节记忆——**全部自动入库，无用户确认**。

**冲突**：理念上区分记忆与身份，实际上把所有对话内容无差别地结构化存储。

### 4.4 "Simple > Complex" vs 281 个路由 + 55 个模块

`philosophy.py` 种子原则第 1 条："Simple > Complex"。但项目在 2 天内堆砌了 281 个路由、55 个 Python 模块、27 个前端模块、9 个向量集合、7 个居民、47 个工具、4 层记忆、3 层反思、7 支柱认知、5 层架构...

**冲突**：理念上追求简单，实际上功能堆砌。这是"AI 写代码"的典型症状——LLM 倾向于生成更多模块而非精简。

### 4.5 "Growth over Perfection" vs "0 个 TODO 标记"

`philosophy.py` 种子原则第 7 条："Growth over Perfection"。但代码中 0 个 TODO/FIXME/XXX 标记，所有未完成功能都被 `pass` 静默吞掉或直接删掉。

**冲突**：理念上接受不完美，实际上掩盖不完美。

---

## 5. 与同类项目对比

| 维度 | Cambium | Mem0 | Letta（原 MemGPT）| LangGraph 模板 |
|---|---|---|---|---|
| 定位 | 个人 AI 连续性引擎 | 记忆层 SDK | 有状态的 LLM Agent | 多 Agent 工作流 |
| 安装难度 | ❌ `pip install -e .` 报错 | ✅ `pip install mem0ai` | ✅ `pip install letta` | ✅ 标准 Python 包 |
| 文档可信度 | ❌ README 与代码多处不符 | ✅ 准确 | ✅ 准确 | ✅ 准确 |
| 测试覆盖 | ⚠️ 134 测试 / 22 模块未测 | ✅ >80% | ✅ >80% | ✅ >70% |
| 安全防护 | ❌ 0 防护 | ✅ API key 校验 | ✅ API key 校验 | N/A（库） |
| 单文件最大行数 | 6,283（main.py） | < 500 | < 800 | < 1000 |
| 部署就绪度 | ❌ 无 Docker、无 CI | ✅ Docker、CI | ✅ Docker、CI | ✅ CI |
| 社区就绪度 | ❌ 无 LICENSE 文件 | ✅ MIT + CONTRIBUTING | ✅ Apache 2.0 | ✅ MIT |

**结论**：Cambium 在功能广度上不输任何同类项目，但在工程基础（安装、测试、安全、文档）上落后一个数量级。

---

## 6. 项目阶段定位

按 [Joel Test](https://www.joelonsoftware.com/2000/08/09/the-joel-test-12-steps-to-better-code/) 12 项评估：

| # | 项 | Cambium |
|---|---|---|
| 1 | 版本控制 | ✅ Git |
| 2 | 一键构建 | ❌ `pip install -e .` 报错 |
| 3 | 每日构建 | ❌ 无 CI |
| 4 | 任务清单 | ❌ 无 TODO 标记、无 issue 模板 |
| 5 | 新代码先测试 | ❌ 22 模块 0 测试 |
| 6 | 写代码前先写 spec | ❌ 无 spec |
| 7 | 有 QA 计划 | ❌ 无 |
| 8 | 安静的工作环境 | N/A |
| 9 | 最好的工具 | N/A |
| 10 | 测试人员 | ❌ 无 |
| 11 | 写代码前先面试候选人 | N/A |
| 12 | 走廊可用性测试 | N/A |

**得分：1/12**（仅版本控制）

按 [Production Readiness Levels](https://www.nasa.gov/office-of-chief-technologist/technology-readiness-level/) 评估：

- **TRL 3**：实验性概念验证。多个功能模块实现完整，但存在密钥泄露、安全裸奔、安装报错等阻塞性问题。
- 距离 TRL 6（生产试点）至少还需要：完成 P0 全部 + P1 全部 + P3 测试补齐。

---

## 7. 总体评价

### 7.1 优点（值得肯定）

1. **产品愿景清晰**：Continuity = Identity × Memory × Agency × Shared Experience × Reflection 这个公式有思考，不是堆砌功能
2. **认知内核设计有深度**：七支柱（身份/时间线/叙事/成长/目标/世界/自我）覆盖了"长期连续性"的核心维度
3. **记忆系统分层合理**：四层（工作/短期/长期/永久）+ 衰减 + 治理 + 自适应权重，借鉴了 Mem0 / SSGM / EvolveMem 等论文
4. **居民系统有创意**：不是"一个 AI 戴 7 个面具"，每个居民有独立状态、关注、心情、活动日志
5. **向量索引全覆盖**：9 种数据类型（记忆/聊天/作品/原则/发现/日志/时间线/共同经历/自主目标）都做了向量化，创建时自动索引
6. **插件系统设计良好**：`plugin.yaml` + `tool.py` + `hooks.py` 的三件套清晰
7. **备份/恢复完整**：ZIP 导出/导入，包含全部数据
8. **API 供应商管理灵活**：动态添加任意数量供应商，每个功能可独立分配
9. **Schema 迁移前向完整**：v1→v9 全部有实现，启动时自动执行
10. **真实跑了 134 个测试用例**——虽然覆盖不全，但比"0 测试"强

### 7.2 缺点（必须改进）

1. **安全裸奔**：密钥泄露 + 无认证 + AI 全权 + SQL 注入面，部署即灾难
2. **死代码堆积**：3 个模块 + 1 个函数 + 1 个 import，~500 行无用代码
3. **测试覆盖不足**：22 个核心模块 0 测试，0 个 API 集成测试
4. **文档与代码脱节**：README 多处不符，USAGE.md 由 AI 生成未校对
5. **单文件 6k 行**：main.py 不可维护
6. **品牌名硬编码**：14 处 CyanX AI，与"开放引擎"定位冲突
7. **工程实践缺失**：无 CI、无 LICENSE 文件、无 CONTRIBUTING、无 lint、无 type check
8. **AI 幻觉传播**：默认模型名编造、README 由 AI 生成未校对——这种"AI 写代码 + AI 写文档"的循环让错误自我强化

### 7.3 推荐处理路径

**对原作者**：
1. **立即吊销泄露的 ModelScope API key**
2. 完成 P0 全部 5 项修复
3. 在 README 顶部加 banner："⚠️ 本项目处于早期开发阶段，不可用于生产"
4. 决定项目定位——个人玩具 or 开源项目？前者可以维持现状，后者必须完成 P1-P3

**对潜在用户**：
1. **不要部署到公网**——会有严重安全风险
2. **不要使用默认配置**——API key 与模型名都不可用
3. 如果要本地试用，先完成 P0-1（替换 API key）+ P0-2（替换模型名）+ P0-3（修复安装）
4. 试用范围限于"本地 localhost + 个人 API key + 自有模型"

**对潜在贡献者**：
1. 阅读本文档了解项目真实状态
2. 从 P3 测试补齐入手——这是最低风险的贡献方式
3. 不要相信 README 与 USAGE.md，以源码为准

---

## 8. 后续阅读

- `01_FUNCTIONAL_SPEC.md` — 功能说明书（基于源码重写）
- `02_IMPROVEMENT_ANALYSIS.md` — 改进分析（按优先级排序）
- `04_TESTING_REPORT.md` — 测试报告
