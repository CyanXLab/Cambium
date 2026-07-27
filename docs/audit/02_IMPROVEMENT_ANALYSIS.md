# Cambium 项目改进分析

> 本文档基于 `01_FUNCTIONAL_SPEC.md` 的事实，给出按优先级排序的改进路径。
> 每个改进项标注：**严重度**（致命/高/中/低）、**改动范围**、**建议方案**、**预期收益**。

---

## P0 — 必须立即修复（阻碍项目可用 / 严重安全风险）

### P0-1 移除硬编码的 ModelScope API Key

**严重度**：致命（密钥泄露）  
**改动范围**：6 个文件

**现状**：API Key `ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9` 在以下位置硬编码：

```
app/main.py:125              MODELSCOPE_API_KEY = os.getenv("MODELSCOPE_API_KEY", "ms-a300ec43-...")
app/model_router.py:80       env_api_key = os.getenv("MODELSCOPE_API_KEY", "ms-a300ec43-...")
scripts/keepalive.sh:3       export MODELSCOPE_API_KEY="ms-a300ec43-..."
scripts/daemon.sh:17         export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-ms-a300ec43-...}"
scripts/run.sh:14            export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-ms-a300ec43-...}"
.env.example:5               MODELSCOPE_API_KEY=ms-a300ec43-...
```

**建议方案**：

1. **立即吊销该 key**（在 ModelScope 控制台）
2. 全部改为 `os.getenv("MODELSCOPE_API_KEY", "")`，启动时若为空则**报错退出**
3. `.env.example` 改为占位符 `MODELSCOPE_API_KEY=your-key-here`
4. 在 `main.py` 启动时增加 `assert MODELSCOPE_API_KEY, "MODELSCOPE_API_KEY must be set"`
5. CI 中加 git hook 检查正则 `ms-[a-f0-9-]{36}` 不出现在任何提交里

**预期收益**：消除密钥泄露风险；强制用户配置自己的 key。

---

### P0-2 修正不存在的默认模型名

**严重度**：致命（开箱即不可用）  
**改动范围**：6 个文件

**现状**：默认模型名 `Qwen/Qwen3.5-397B-A17B` 与 `Qwen/Qwen3.5-122B-A10B` 在 ModelScope 上**不存在**。Qwen 系列从未发布过 `Qwen3.5` 这个版本号，且 397B-A17B / 122B-A10B 这种参数规格也是编造的。

出现位置：
```
app/main.py:3,127,831,832    # 4 处
app/model_router.py:82
scripts/daemon.sh:19
scripts/keepalive.sh:5
scripts/run.sh:16
.env.example:7
```

**建议方案**：

1. 改为真实存在的模型，例如：
   - `Qwen/Qwen3-235B-A22B-Instruct-2507`（Qwen3 旗舰）
   - `Qwen/Qwen3-30B-A3B-Instruct-2507`（Qwen3 小型）
   - `Qwen/Qwen2.5-72B-Instruct`（兼容旧版本）
2. 或者将默认值留空，由用户在首次启动时通过 onboarding 配置
3. 在 README 中明确列出已测试的模型清单

**预期收益**：新用户开箱即用，不再因 404 模型错误而困惑。

---

### P0-3 修复 `pip install -e .` 失败

**严重度**：高（README 推荐的安装方式直接报错）  
**改动范围**：`pyproject.toml`

**现状**：`pyproject.toml` 使用 flat-layout 但未声明 package discovery，导致 setuptools 检测到 `app/`、`plugins/`、`workspace/`、`custom_tools/` 四个顶级包时拒绝构建。

**建议方案**：

```toml
[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["workspace*", "custom_tools*", "plugins*", "tests*"]
```

或显式声明：

```toml
[tool.setuptools]
packages = ["app", "app.static", "app.templates"]
```

（注意：`app.static` 等子包需要 `package-data` 配置才能包含非 .py 文件）

**预期收益**：README 的 `pip install -e .` 真正可用。

---

### P0-4 为 FastAPI 应用增加最基本的安全防护

**严重度**：致命（任意访问者可读写所有数据）  
**改动范围**：`app/main.py`

**现状**：
- 未配置 CORS——任意源都能跨域访问
- 未配置任何认证中间件——281 个 API 端点完全开放
- `db_query`、`db_execute` 工具允许 AI 直接执行 SQL（读所有表、写所有表）
- `set_setting` 工具允许 AI 修改 API key、系统提示词等所有配置

**建议方案**（最小可行安全）：

1. **绑定监听地址**：默认 `--host 127.0.0.1`，仅在显式配置时才 `0.0.0.0`
2. **CORS 白名单**：默认仅允许 `http://localhost:*`，可通过 `CAMBIUM_CORS_ORIGINS` 配置
3. **API Token 中间件**：增加 `X-Cambium-Token` header 校验，token 在首次启动时随机生成并写入 `.env`
4. **危险工具白名单**：`db_query/db_execute/set_setting/install_package/save_custom_tool/run_shell` 必须用户在前端**显式确认**才执行
5. **审计日志**：所有危险工具调用写入 `audit_log` 表（user_id / tool_name / args / timestamp / approved_by）

**预期收益**：从"部署即裸奔"提升到"最小可信部署"。

---

### P0-5 修复 `keepalive.sh` 硬编码路径

**严重度**：高（脚本在其他机器无法使用）  
**改动范围**：`scripts/keepalive.sh`

**现状**：第 2 行 `cd /home/z/my-project/ai-chat` 是开发者私有路径，但仓库根目录其实是 `Cambium/`。

**建议方案**：

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"
```

**预期收益**：脚本可在任意机器运行。

---

## P1 — 重要改进（影响生产可用性）

### P1-1 删除或激活死代码

**严重度**：高（增加维护成本、误导读者）  
**改动范围**：3 个模块

**现状**：

| 模块 | 行数 | 状态 |
|---|---|---|
| `agent_loop.py` | 321 | 导入但 0 次调用 |
| `dspy_integration.py` | 148 | 导入但 0 次调用 |
| `complexity_tier.py` | 全部业务逻辑 | 被硬编码 stub 替代 |
| `main.py::_embed_for_rag` | 24 | 定义但 0 次调用 |
| `main.py` 中 `from app import rule_engine` | 1 行 | 死引用 |

**建议方案**：二选一

**方案 A（推荐）— 删除**：
- 删除 `agent_loop.py`、`dspy_integration.py`
- 删除 `complexity_tier.py`，同时移除 main.py 中的 2 处引用
- 删除 `_embed_for_rag`，同时移除前端 RAG provider 选项
- 移除 main.py 中所有未使用的 import

**方案 B — 激活**：
- 把 `agent_loop.AgentLoop` 接入 `chat_stream`，让 Plan/Act/Observe/Reflect 真正运行
- 把 `dspy_integration` 接入 prompt 调用，替换硬编码 prompt
- 重新打开 `complexity_tier` 的 tier 切换逻辑，配合用户年龄数据
- 把 `_embed_for_rag` 接入 `vector_store`，支持 OpenAI 兼容的 embedding API

**预期收益**：减少 ~500 行无用代码 / 或获得对应功能。

---

### P1-2 工具沙箱强化

**严重度**：高（AI 可执行任意代码）  
**改动范围**：`app/tools_ext.py`

**现状**：

1. `run_python`：调用 `subprocess.run([sys.executable, script_path])`，**完全无沙箱**——`import os; os.system("rm -rf ~")` 可执行
2. `run_shell`：黑名单仅 16 项，且基于子串匹配——`rm --recursive --force $HOME` 完全绕过
3. `install_package`：无白名单——可安装任意恶意包
4. `save_custom_tool` / `run_custom_tool`：可保存任意 Python 文件并执行——等价于任意代码执行
5. `_safe_resolve` 允许 `custom_tools/` 和 `.skills/` 两个目录——AI 可修改自己的工具代码

**建议方案**：

1. **Python 沙箱**：用 `bubblewrap`（Linux）或 `firejail` 在子进程级隔离：
   ```python
   subprocess.run(["firejail", "--quiet", "--private=" + str(workspace),
                   "--net=none", "--nosound", "--x11=none",
                   sys.executable, script_path], ...)
   ```
2. **Shell 白名单**：改为白名单模式，仅允许 `ls/cat/grep/find/git/python/npm/pip/curl/wget` 等明确命令
3. **Package 白名单**：仅允许预定义的安全包列表
4. **Custom tools 隔离**：所有 `custom_tools/` 下的代码运行前必须用户在前端确认
5. **路径限制**：`_safe_resolve` 仅允许 workspace 内，移除 `custom_tools/` 与 `.skills/` 例外

**预期收益**：把"AI 全权代理用户"降为"AI 在受限环境内运行"。

---

### P1-3 移除 `CyanX AI` 硬编码

**严重度**：中（项目身份混乱）  
**改动范围**：14 处

**现状**：项目命名为 `Cambium`，但内部 14 处硬编码 `CyanX AI` 作为 AI 的名字：
- `app/main.py:3203,4044,4967` — 反思/晨报 prompt 中
- `app/memory_orchestrator.py:14,899` — 模块文档与反思 prompt
- `app/advanced_memory.py:3` 等多个模块顶部 docstring
- `app/templates/index.html:1628` — 用户可见的设置页文案

**建议方案**：

1. 引入 `AI_NAME` 配置项（默认 `Cambium`），写入 `DEFAULT_SETTINGS`
2. 所有 prompt 模板使用 `{ai_name}` 占位符，运行时 `.format(ai_name=...)`
3. 模块顶部 docstring 改为 `Cambium` 或移除品牌名
4. 前端设置页文案改为可配置

**预期收益**：项目可被社区复用、二次开发，不再绑定个人品牌。

---

### P1-4 修正 SSE/WebSocket 描述

**严重度**：低（文档不一致）  
**改动范围**：`README.md`

**现状**：README 在技术栈表格中写 `Web | FastAPI + WebSocket`，但实际使用 SSE。

**建议方案**：改为 `Web | FastAPI + SSE (Server-Sent Events)`。

**预期收益**：技术栈描述准确，避免误导贡献者。

---

### P1-5 修正版本号不一致

**严重度**：低（元信息混乱）  
**改动范围**：`README.md` 或 `pyproject.toml`

**现状**：`README.md` 头部写 `v1.3.0`，`pyproject.toml` 写 `1.4.0`。

**建议方案**：以 `pyproject.toml` 为准，更新 README 到 `v1.4.0`。建议引入 `bumpversion` 或 `setuptools-scm` 自动同步。

**预期收益**：版本管理一致。

---

### P1-6 反思流程加开关

**严重度**：中（隐私 / 资源消耗）  
**改动范围**：`app/main.py::_background_reflection_loop`

**现状**：后台反思循环每 10 分钟检查一次，触发条件为 `chat_vectors` 自上次反思以来新增 ≥ 30 条。**用户无法单独关闭反思**——`profile_auto_update` 开关同时关闭画像更新等其他功能。

**建议方案**：

1. 新增独立设置项 `background_reflection_enabled`（默认 true）
2. 新增 `background_reflection_trigger_msgs`（默认 30，可调）
3. 新增 `background_reflection_interval_sec`（默认 600，可调）
4. 在设置页"高级"分区暴露这三个开关

**预期收益**：用户可单独控制反思行为，节省 LLM 调用费用。

---

### P1-7 修正对话压缩阈值

**严重度**：中（功能实际不生效）  
**改动范围**：`DEFAULT_SETTINGS`

**现状**：`compress_threshold_tokens` 默认 `80000`，但 Qwen 系列模型上下文窗口最大 32k（部分新模型 128k）。**对于 32k 模型，阈值永远不可能触发**，因为请求会先因超长而报错。

**建议方案**：

1. 默认阈值改为 `24000`（保留余量给系统 prompt + 工具说明）
2. 启动时根据当前模型的 `context_window`（来自 `model_adapter.detect_capabilities`）自动计算建议阈值
3. 设置页提示用户："当前模型上下文窗口 X，建议阈值 ≤ X × 0.75"

**预期收益**：对话压缩真正生效，避免长对话失败。

---

### P1-8 替换已废弃的 `@app.on_event`

**严重度**：低（运行时 DeprecationWarning）  
**改动范围**：`app/main.py`

**现状**：第 4891 行使用 `@app.on_event("startup")`，FastAPI 已废弃，运行时打印大段 DeprecationWarning。

**建议方案**：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await _start_cron_scheduler()
    yield
    # shutdown
    ...

app = FastAPI(title="Cambium", lifespan=lifespan, docs_url=None, redoc_url=None)
```

**预期收益**：消除 DeprecationWarning；获得优雅关闭能力。

---

### P1-9 修正 `asyncio.get_event_loop()` 废弃用法

**严重度**：低（未来 Python 3.14 会失败）  
**改动范围**：5 个文件

**现状**：

```
app/cognitive_kernel.py:407     loop = asyncio.get_event_loop()
app/memory_orchestrator.py:297  loop = asyncio.get_event_loop()
app/plugin_sdk.py:211           loop = asyncio.get_event_loop()
```

Python 3.10+ 在无运行循环时 `get_event_loop()` 会发出 DeprecationWarning，3.14 计划完全移除。

**建议方案**：

```python
try:
    loop = asyncio.get_running_loop()
    loop.create_task(event_bus.publish(...))
except RuntimeError:
    # No running loop — fire-and-forget in new thread
    import threading
    threading.Thread(
        target=lambda: asyncio.run(event_bus.publish(...)),
        daemon=True
    ).start()
```

**预期收益**：兼容未来 Python 版本。

---

## P2 — 架构改进（中期重构）

### P2-1 拆分 `main.py`

**严重度**：高（可维护性）  
**改动范围**：`app/main.py`（6,283 行）

**现状**：单文件包含 283 个路由 + 大量业务逻辑，6,283 行，远超人类维护极限。

**建议方案**：按功能域拆分为 FastAPI Router：

```
app/api/
├── __init__.py
├── chat.py            # /api/chat/* (2 routes)
├── memory.py          # /api/memory/* (16 routes)
├── cognitive.py       # /api/cognitive/* (14 routes)
├── residents.py       # /api/residents/* (12 routes)
├── artifacts.py       # /api/artifacts/* (8 routes)
├── philosophy.py      # /api/philosophy/* (7 routes)
├── evolution.py       # /api/evolution/* (6 routes)
├── discovery.py       # /api/discoveries/* (7 routes)
├── swarm.py           # /api/swarm/* + /api/self-goals/* (13 routes)
├── mornings.py        # /api/mornings/* (5 routes)
├── journal.py         # /api/journal/* (8 routes)
├── co_experience.py   # /api/co-experience/* (8 routes)
├── providers.py       # /api/providers/* (6 routes)
├── workspace.py       # /api/workspace/* (6 routes)
├── governance.py      # /api/governance/* (6 routes)
├── sessions.py        # /api/sessions/* + /api/runtime/* (11 routes)
├── plugins.py         # /api/plugins/* (3 routes)
├── prompts.py         # /api/prompts/* (5 routes)
├── vector.py          # /api/vector-store/* + /api/vector-search/* (4 routes)
├── mcp.py             # /api/mcp/* (4 routes)
├── settings.py        # /api/settings/* + /api/test (3 routes)
├── backup.py          # /api/backup/* (3 routes)
├── debug.py           # /api/debug/* (3 routes)
├── misc.py            # /api/health, /api/upload, /api/attachments, ... (剩余)
└── deps.py            # 共享依赖（DB_PATH、settings_get_all 等）
```

`main.py` 仅保留 app 实例化、lifespan、router 挂载，控制在 200 行以内。

**预期收益**：单文件 < 500 行，每个路由文件独立可测；可以并行开发。

---

### P2-2 引入依赖注入

**严重度**：中（可测试性）  
**改动范围**：全局

**现状**：所有模块直接 `from app.main import DB_PATH` 等全局变量，路由直接调用模块级函数。无法在不修改全局状态的情况下测试单个路由。

**建议方案**：用 FastAPI 的 `Depends`：

```python
def get_db_path() -> Path:
    return DB_PATH

@app.get("/api/memory")
async def list_memory(db_path: Path = Depends(get_db_path), ...):
    ...
```

测试时通过 `app.dependency_overrides[get_db_path] = lambda: test_db_path` 替换。

**预期收益**：API 层可独立测试，无需启动整个应用。

---

### P2-3 引入结构化日志

**严重度**：中（运维）  
**改动范围**：全局

**现状**：全项目使用 `print()`（197 处），无日志级别、无结构化、无文件输出。

**建议方案**：

```python
import structlog
log = structlog.get_logger()

log.info("memory.added", memory_id=mid, user_id=user_id, content_len=len(content))
log.warning("vector_store.fallback", backend="tfidf", reason="chromadb not installed")
log.error("reflection.failed", error=str(e), conversation_id=conv_id)
```

配置 `structlog` 输出 JSON 到 stdout，由 systemd / docker logs 收集。

**预期收益**：日志可搜索、可聚合、可告警。

---

### P2-4 收敛异常处理

**严重度**：中（健壮性）  
**改动范围**：全局

**现状**：`except Exception` 出现 364 处，`except:` 或 `except Exception: pass` 出现 152 处。大量错误被静默吞掉，问题难以定位。

**建议方案**：

1. **禁止 bare `except:`**——CI 中加 ruff 规则 `E722`
2. **每个 `except Exception` 必须至少 `log.exception(...)`**
3. **可恢复的预期错误**用具体异常类型（`sqlite3.OperationalError`、`httpx.HTTPError` 等）
4. **不可恢复的错误**让它抛出，由 FastAPI 全局异常处理器统一返回 500

**预期收益**：问题可定位，不再"静默失败"。

---

### P2-5 数据库迁移增加回滚

**严重度**：中（运维）  
**改动范围**：`app/migrations.py`

**现状**：仅前向迁移，每个版本只定义 `upgrade`，无 `downgrade`。出问题时只能手动改 schema 或恢复备份。

**建议方案**：

1. 借鉴 Alembic 的设计，每个迁移定义 `upgrade()` 和 `downgrade()`
2. 增加 `migrations.rollback(db_path, target_version)` API
3. 在 `/api/migrations/run` 端点支持 `direction` 参数

或者直接引入 Alembic 替换自研迁移系统。

**预期收益**：升级失败可回滚；社区贡献的迁移更安全。

---

### P2-6 把死代码模块转化为可选功能

**严重度**：中  
**改动范围**：`pyproject.toml` + 死代码模块

**现状**：`dspy_integration`、`langgraph_integration`、`autogen_integration` 都是 `try/except ImportError` 守卫，但只有后两者被实际调用。`dspy` 和 `autogen` 是 `pyproject.toml` 的必装依赖，体积大、安装慢。

**建议方案**：

```toml
[project.optional-dependencies]
langgraph = ["langgraph>=1.0.0"]
dspy = ["dspy>=3.0.0"]
autogen = ["autogen-agentchat>=0.7.0", "autogen-ext>=0.7.0"]
all = ["langgraph>=1.0.0", "dspy>=3.0.0", "autogen-agentchat>=0.7.0", "autogen-ext>=0.7.0", "chromadb>=0.5.0"]
```

主依赖仅保留 FastAPI、httpx、jinja2、pydantic。

**预期收益**：基础安装从 ~500MB 降到 ~50MB；用户按需安装。

---

## P3 — 测试改进

### P3-1 增加 API 集成测试

**严重度**：高（覆盖率严重不足）  
**改动范围**：`tests/`

**现状**：134 个测试全部是单元测试（直接调用模块函数），**0 个 HTTP 集成测试**。283 个路由完全未测。

**建议方案**：用 FastAPI TestClient：

```python
# tests/test_api_chat.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_memory_crud():
    # Create
    r = client.post("/api/memory/add", json={"content": "test memory"})
    assert r.status_code == 200
    mid = r.json()["id"]
    # List
    r = client.get("/api/memory")
    assert any(m["id"] == mid for m in r.json()["memories"])
    # Delete
    r = client.post(f"/api/memory/{mid}/delete")
    assert r.status_code == 200
```

目标：覆盖至少 50% 的 API 路由（约 140 个）。

**预期收益**：API 层回归保护；重构 P2-1 时有安全网。

---

### P3-2 补齐 22 个未测试模块的单元测试

**严重度**：高  
**改动范围**：`tests/`

**现状**：55 个模块中 22 个完全没有测试：

```
advanced_memory, api_providers, autogen_integration, context_cache, cron,
debug_mode, episodic_memory, identity_consistency, knowledge_graph,
langgraph_integration, life_loop, llm_utils, main, meta_cognition,
proactive_engine, reflection_tree, rule_engine, sessions, swarm,
tool_registry, tools_ext, vector_indexer
```

其中包括核心模块：`main.py`（283 路由）、`tools_ext.py`（47 工具）、`swarm.py`（多 Agent 协作）、`life_loop.py`（昼夜节律）。

**建议方案**：按优先级补齐：

| 优先级 | 模块 | 测试要点 |
|---|---|---|
| P0 | `tools_ext.py` | 47 个工具逐一测 happy path + 边界 |
| P0 | `llm_utils.py` | JSON 抽取、内容提取的边界情况 |
| P0 | `swarm.py` | 任务分解、居民分配、Critic 审查 |
| P1 | `life_loop.py` | hourly/daily/weekly/monthly 触发逻辑 |
| P1 | `sessions.py` | 后台会话创建、超时、并发上限 |
| P1 | `cron.py` | cron 表达式解析、下次触发计算 |
| P1 | `vector_indexer.py` | 9 个集合的索引/搜索/删除 |
| P1 | `knowledge_graph.py` | 三元组 CRUD、实体搜索 |
| P1 | `episodic_memory.py` | 情节 CRUD、因果链、衰减 |
| P1 | `meta_cognition.py` | 自评打分、阈值触发 |
| P2 | `reflection_tree.py` | 三层反思、observation → reflection → meta |
| P2 | `identity_consistency.py` | should_assess、评估历史 |
| P2 | `proactive_engine.py` | 主动联系触发条件 |
| P2 | `context_cache.py` | 缓存命中/失效 |
| P2 | `rule_engine.py` | 5 个规则函数的边界 |
| P2 | `debug_mode.py` | 时间加速 |
| P3 | `main.py` | 通过 TestClient 测关键路由 |
| P3 | `langgraph_integration.py` | LANGGRAPH_AVAILABLE=False 时的回退路径 |
| P3 | `autogen_integration.py` | AUTOGEN_AVAILABLE=False 时的回退路径 |
| P3 | `api_providers.py` | 供应商 CRUD、模型获取 |
| P3 | `tool_registry.py` | 工具列表、自定义工具注册 |
| P3 | `advanced_memory.py` | 情感识别、画像更新 |

**预期收益**：测试覆盖率从 ~55% 提升到 80%+。

---

### P3-3 增加 LLM Mock 测试

**严重度**：中  
**改动范围**：`tests/`

**现状**：所有涉及 LLM 的功能（记忆抽取、反思、晨报、居民运行、Swarm 任务）都没有测试，因为测试环境没有 LLM。`residents.py:469` 显式 `# No LLM available — mark as completed with stub output`。

**建议方案**：引入 `respx` 或自写 mock 拦截 httpx 请求：

```python
# tests/conftest.py
import respx
import httpx

@pytest.fixture
def mock_llm():
    with respx.mock(base_url="https://api-inference.modelscope.cn/v1") as m:
        m.post("/chat/completions").respond(json={
            "choices": [{"message": {"content": "mocked response"}}]
        })
        yield m
```

**预期收益**：LLM 依赖功能可测试；CI 可完整跑测试套件。

---

### P3-4 增加性能基准测试

**严重度**：低  
**改动范围**：`tests/`

**现状**：无性能基准。`memory_orchestrator` 在大量记忆时的检索性能、`vector_store` TF-IDF 在大量文档时的查询性能、`chat_stream` 在长对话时的 token 计算性能，均无数据。

**建议方案**：用 `pytest-benchmark`：

```python
def test_memory_search_1000(benchmark):
    # 预置 1000 条记忆
    for i in range(1000):
        memory_orchestrator.add_memory(test_db, content=f"memory {i}")
    # benchmark 检索
    result = benchmark(memory_orchestrator.retrieve_relevant, test_db, "query")
    assert len(result) > 0
```

**预期收益**：发现性能瓶颈；重构时有量化对比。

---

## P4 — 功能补全与体验改进

### P4-1 用户系统（多租户隔离）

**严重度**：中  
**改动范围**：全局

**现状**：所有表都有 `user_id` 列，但所有路由都硬编码 `user_id="default"`。无法支持多用户。

**建议方案**：

1. 引入 `User` 表（id, name, api_key_hash, created_at）
2. API Token 中间件解析 token → user_id
3. 所有路由的 `user_id` 从 `Depends(get_current_user)` 获取
4. 数据库索引确保 `user_id` 查询性能

**预期收益**：真正多用户支持；可部署为家庭/团队服务。

---

### P4-2 前端框架化

**严重度**：中  
**改动范围**：`app/static/js/`

**现状**：5,314 行的 `app.js` + 27 个 IIFE 模块，全部基于原生 DOM 操作。状态管理靠全局 `state` 对象，UI 更新靠手动 `renderXXX()` 调用。

**建议方案**：迁移到 Preact + Signal（轻量）或 Vue 3 + Pinia：

- 体积增加 ~30KB（gzip）
- 状态变更自动 UI 更新
- 组件化后 `app.js` 可拆为 50+ 个 < 100 行的组件
- 保留 SSE 流式逻辑（用 `useEffect` + `fetch`）

**预期收益**：前端可维护性提升 10 倍；新功能开发速度提升。

---

### P4-3 配置项分组与文档化

**严重度**：低  
**改动范围**：`DEFAULT_SETTINGS` + 设置页

**现状**：100+ 配置项扁平排列在 `DEFAULT_SETTINGS` 字典中，前端设置页按"通用/个性化/模型参数/深度思考/对话增强/高级记忆/RAG/MCP/会话/Cron"分区，但分区与字典无对应关系。

**建议方案**：

1. 改为 Pydantic Settings 模型：

```python
class ChatSettings(BaseModel):
    temperature: float = 0.6
    top_p: float = 0.9
    max_tokens: int = 8192
    ...

class MemorySettings(BaseModel):
    enable_memory: bool = True
    auto_extract: bool = False
    auto_summary: bool = True
    inject_count: int = 0
    ...

class Settings(BaseModel):
    chat: ChatSettings
    memory: MemorySettings
    api: ApiSettings
    rag: RagSettings
    ...
```

2. 自动生成设置页 UI（基于 Pydantic schema）
3. 自动生成 `.env.example`（基于字段默认值 + 注释）

**预期收益**：配置项有类型校验；新增配置自动出现在 UI；文档与代码不漂移。

---

### P4-4 移除前端 onboarding 中的硬编码引导

**严重度**：低  
**改动范围**：`app/static/js/modules/onboarding.js`

**现状**：onboarding 流程包含 `CyanX AI` 品牌文案，假设用户使用 ModelScope + Qwen。

**建议方案**：onboarding 改为：

1. 选择 LLM 供应商（ModelScope / OpenAI / Anthropic / 本地 Ollama / 自定义）
2. 输入 API key（带连通性测试按钮）
3. 选择模型（从 `/api/models/auto` 拉取）
4. 设置 AI 名字（默认 `Cambium`）
5. 可选：导入备份

**预期收益**：新用户引导适配多供应商。

---

### P4-5 国际化（i18n）

**严重度**：低  
**改动范围**：全局

**现状**：UI 文案全中文，prompt 全中文。无 i18n 框架。

**建议方案**：

1. 后端 prompt 模板用 `{lang}` 变量区分中英文版本
2. 前端引入 `i18next`，所有文案改用 `t("key")`
3. 提取所有文案到 `locales/zh-CN.json` 和 `locales/en.json`
4. 设置页可切换语言

**预期收益**：项目可被非中文用户使用。

---

### P4-6 增加 LICENSE 文件

**严重度**：低  
**改动范围**：仓库根目录

**现状**：README 声明 MIT 许可证，但仓库根目录**没有 LICENSE 文件**。法律上不构成有效授权。

**建议方案**：在仓库根目录创建 `LICENSE` 文件，内容为标准 MIT 文本，年份填 2026，版权人填 `CyanXLab`。

**预期收益**：法律合规；社区可安全使用。

---

### P4-7 增加 CONTRIBUTING 与 CODE_OF_CONDUCT

**严重度**：低  
**改动范围**：仓库根目录

**建议方案**：

- `CONTRIBUTING.md`：开发环境搭建、代码风格、提交规范、PR 流程
- `CODE_OF_CONDUCT.md`：贡献者行为准则
- `.github/PULL_REQUEST_TEMPLATE.md`：PR 模板
- `.github/ISSUE_TEMPLATE/bug_report.md` & `feature_request.md`

**预期收益**：社区贡献门槛降低。

---

## P5 — 长期方向

### P5-1 抽离认知内核为独立 PyPI 包

**严重度**：低  
**改动范围**：`cognitive_kernel.py`、`memory_orchestrator.py`、`reflection_tree.py`、`memory_governance.py`、`adaptive_retrieval.py`、`identity_consistency.py`

把这些与 Cambium 业务无关的、通用的"AI 记忆与认知"模块抽离为独立包 `cambium-kernel`，可被其他 AI 项目复用。

### P5-2 支持 PostgreSQL 后端

**严重度**：低  
**改动范围**：`db_utils.py` + 全部 SQL

当前 SQLite 单文件部署无法支持多实例横向扩展。引入 SQLAlchemy ORM 后可切换 PostgreSQL，支持团队部署。

### P5-3 提供 Docker 镜像与 docker-compose

**严重度**：低  
**改动范围**：新增 `Dockerfile`、`docker-compose.yml`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .[all]
EXPOSE 3000
VOLUME ["/app/data", "/app/workspace"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
```

### P5-4 引入 Observability（OpenTelemetry）

为 LLM 调用、工具调用、数据库查询、向量检索等关键路径加 OpenTelemetry trace，集成到 Jaeger / Grafana Tempo。

### P5-5 评估模块安全沙箱化

`run_python` 改用 WebAssembly（如 `pyodide`）或 `nsjail`，提供真正的强隔离。`run_shell` 改用 `bpftrace` + seccomp 过滤系统调用。

---

## 改进优先级路线图

```
Week 1 (P0):
  - 吊销并移除硬编码 API key
  - 修正默认模型名
  - 修复 pip install -e .
  - 增加最小安全防护（绑定 127.0.0.1 + CORS + Token）
  - 修复 keepalive.sh 硬编码路径

Week 2-3 (P1):
  - 删除死代码（agent_loop / dspy_integration / _embed_for_rag）
  - 工具沙箱强化
  - 移除 CyanX AI 硬编码
  - 反思流程加独立开关
  - 修正压缩阈值
  - 替换 @app.on_event
  - 修正 SSE/WebSocket 文档
  - 修正版本号

Week 4-6 (P2):
  - 拆分 main.py 为路由模块
  - 引入依赖注入
  - 引入 structlog
  - 收敛异常处理
  - 迁移系统增加回滚
  - 把可选依赖拆出

Week 7-10 (P3):
  - 增加 API 集成测试（覆盖 50% 路由）
  - 补齐 22 个未测试模块
  - 增加 LLM Mock 测试
  - 增加性能基准测试

Week 11+ (P4-P5):
  - 多用户系统
  - 前端框架化
  - 配置项 Pydantic 化
  - i18n
  - LICENSE / CONTRIBUTING
  - 抽离认知内核为独立包
  - PostgreSQL 支持
  - Docker 镜像
  - OpenTelemetry
```

---

## 后续阅读

- `01_FUNCTIONAL_SPEC.md` — 功能说明书
- `03_PROJECT_EVALUATION.md` — 项目评估报告
- `04_TESTING_REPORT.md` — 测试报告
