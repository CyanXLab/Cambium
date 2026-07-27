# Cambium 架构文档

> 本文描述 Cambium v2.0.0 的架构设计、论文映射和设计决策。

---

## 1. 设计哲学

### 1.1 核心公式

```
Continuity = Identity × Memory × Agency × Shared Experience × Reflection
```

这不是功能堆砌，而是一个**乘法关系**——任何一项为零，连续性就为零。

- **Identity（身份）**：AI 有自己的叙事、价值观、成长轨迹，不是空白助手
- **Memory（记忆）**：不是平铺的事实，而是分层、衰减、治理的认知资产
- **Agency（能动性）**：AI 能行动（工具）、能选择（居民）、能协作（Swarm）
- **Shared Experience（共同经历）**：用户和 AI 有"记得当时我们……"的共同历史
- **Reflection（反思）**：AI 会回顾、总结、修正——不是只活在当下

### 1.2 设计原则

1. **本地优先**：所有数据在用户机器上的 SQLite 文件，用户拥有完全控制
2. **认知驱动**：不是"chat + memory + features"，而是"一个有认知状态的存在"
3. **渐进信任**：四级权限模式，从 plan 到 autonomous，用户控制 AI 的自主度
4. **论文奠基**：每个核心模块对应一篇论文，不是凭空设计
5. **简单 > 复杂**：复杂性服务于连续性，不是为复杂而复杂

---

## 2. 五层架构

```
┌─────────────────────────────────────────────────────────┐
│              Interface Layer (交互层)                     │
│   Web UI · CLI · (未来: Telegram · Discord · IDE)        │
├─────────────────────────────────────────────────────────┤
│              API Layer (API 层)                          │
│   283 FastAPI routes · SSE streaming · WebSocket (未来)  │
├─────────────────────────────────────────────────────────┤
│              Agent Layer (能动层)                         │
│   Agent Loop v2 · 7 Residents · Swarm Task              │
│   Tool Registry (47 tools) · MCP · Plugin SDK           │
├─────────────────────────────────────────────────────────┤
│              Cognitive Layer (认知层)                    │
│   ★ Cognitive Kernel (7 pillars) ★                      │
│   Memory Orchestrator · Memory Governance               │
│   Reflection Tree · Identity Consistency                │
│   Adaptive Retrieval · Philosophy                       │
├─────────────────────────────────────────────────────────┤
│              Life Layer (生命层)                         │
│   Life Loop · Mornings · Journal · Co-experience        │
│   Evolution · Discovery · Proactive Engine              │
├─────────────────────────────────────────────────────────┤
│              Infrastructure (基础设施)                    │
│   SQLite WAL · Vector Store · Event Bus · Config        │
│   Logging · Exception Handling · Migrations             │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 论文映射

每个核心模块对应一篇学术论文，确保设计有理论基础：

| 模块 | 论文 | 核心洞察 | Cambium 实现 |
|------|------|---------|-------------|
| `memory_governance.py` | SSGM Framework (2026) | 记忆不是"写入即永久"，需要隔离→验证→晋升 | 三阶段管线 + 矛盾检测 + LLM 验证 + 审计日志 |
| `adaptive_retrieval.py` | EvolveMem (2026) | 检索权重应该进化，不是硬编码 | 反馈驱动 ±0.02 调整 + 边界 [0.05, 0.50] + 归一化 |
| `reflection_tree.py` | Generative Agents (Park et al., 2023) | 三层反思：观察→反思→元反思 | parent_id 树结构 + 重要性/recency/relevance 三因子 |
| `identity_consistency.py` | Identity Layer (2026) | 身份需要一致性度量，不是计数器 | LLM 评估 + 漂移检测 + 快照历史 |
| `agent_loop_v2.py` | CoALA (Sumers et al., 2023) + Claude Code (2026) | Agent 是决策循环：Observe→Retrieve→Reason→Act→Learn | 完整循环 + 四级权限 + 5 层压缩 + checkpoint |
| `memory_orchestrator.py` | Mem0 (2024) | 语义去重 + 记忆合并 | Jaccard 相似度 + 合并时 importance +5 |
| `cognitive_kernel.py` | TSM (2026) | 时间有语义，不是日历时间 | 11 类时间线事件 + 语义时间衰减 |

---

## 4. Agent Loop v2 详细设计

### 4.1 CoALA 决策循环

```
┌──────────────────────────────────────────────────────┐
│                  Agent Loop v2                        │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ Observe  │───▶│ Retrieve │───▶│  Reason  │       │
│  │ (用户消息) │    │ (认知内核) │    │ (LLM思考) │       │
│  └──────────┘    └──────────┘    └────┬─────┘       │
│                                       │              │
│                                       ▼              │
│  ┌──────────┐                   ┌──────────┐        │
│  │  Learn   │◀──────────────────│   Act    │        │
│  │ (认知更新) │                   │ (工具/回复)│        │
│  └──────────┘                   └──────────┘        │
│       │                              │              │
│       │ async                        │              │
│       ▼                              │              │
│  ┌──────────┐                        │              │
│  │ Memory   │                        │              │
│  │ Identity │                        │              │
│  │ Growth   │                        │              │
│  │ Timeline │                        │              │
│  └──────────┘                        │              │
└──────────────────────────────────────┘
```

### 4.2 四级权限模式（Claude Code §3.4）

| 模式 | memory.write | identity.evolve | tool.execute | tool.dangerous |
|------|:---:|:---:|:---:|:---:|
| plan | ❌ | ❌ | ❌ | ❌ |
| reflect | ✅ | ❌ | ✅ | ❌ |
| grow | ✅ | ❌ | ✅ | ❌ |
| autonomous | ✅ | ✅ | ✅ | ✅ |

### 4.3 五层上下文压缩（Claude Code §3.5）

| Layer | 触发 | 动作 |
|-------|------|------|
| 1. 微压缩 | 每次工具调用 | 截断工具输出到 3000 字符 |
| 2. 自动压缩 | 总字符 > 80% 阈值 | 摘要中间消息，保留 system + 最近 10 条 |
| 3. 反应式压缩 | API 报错（超长）| 紧急压缩到 50% |
| 4. 会话内存提取 | 反思触发 | 提取关键事实到记忆系统 |
| 5. 上下文清理 | 反思后 | 删除旧工具调用结果 |

---

## 5. 记忆系统架构

### 5.1 四层记忆（Mem0-inspired）

```
Importance 0-20  →  Working Memory  →  丢弃（不存储）
Importance 21-50 →  Short Term      →  24h, 0.95/天衰减
Importance 51-80 →  Long Term       →  月级, 0.99/天衰减
Importance 81-100→  Permanent       →  永远, 不衰减
```

### 5.2 SSGM 治理管线

```
新提取的记忆
     │
     ▼
┌─────────────┐
│ QUARANTINE  │  ← 矛盾检测（如果有矛盾，confidence 降至 0.2）
│ (隔离区)     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ VALIDATION  │  ← 规则验证（importance ≥ 50 自动验证）
│ (验证)       │  ← LLM 验证（一致性检查）
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
验证通过  拒绝
   │       │
   ▼       ▼
┌─────────┐ ┌─────────┐
│PROMOTION│ │ REJECT  │
│(晋升)    │ │ (拒绝)  │
└─────────┘ └─────────┘
   │
   ▼
主记忆存储
```

### 5.3 EvolveMem 自适应检索

```
用户查询 → retrieve_relevant()
               │
               ▼
         ┌─────────────┐
         │ 计算融合分数  │
         │              │
         │ keyword × W1 │  ← W1 不是硬编码
         │ + imp × W2   │  ← W2 会进化
         │ + rec × W3   │
         │ + decay × W4 │
         │ + layer × W5 │
         └──────┬──────┘
                │
                ▼
         返回 Top-K
                │
                ▼
         用户反馈（positive/negative/neutral）
                │
                ▼
         adjust_weights()
                │
                ▼
         W1...W5 更新（±0.02，归一化到 sum=1.0）
```

---

## 6. 认知内核七支柱

```
┌─────────────────────────────────────────────────────────┐
│                  Cognitive Kernel                        │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Identity   │  │  Timeline   │  │  Narrative  │    │
│  │  (身份)      │  │  (时间线)    │  │  (叙事)      │    │
│  │             │  │  11 类事件   │  │  故事性记忆  │    │
│  │ 自我叙事     │  │  树结构      │  │  非平铺事实  │    │
│  │ 演化日志     │  │             │  │             │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Growth    │  │    Goal     │  │    World    │    │
│  │  (成长)      │  │  (目标)      │  │  (世界)      │    │
│  │             │  │             │  │             │    │
│  │ 策略演化     │  │ 长期目标     │  │ 项目/人物    │    │
│  │ 纠错记录     │  │ 活跃承诺     │  │ 工具/因果    │    │
│  │ 反思驱动     │  │             │  │             │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│              ┌─────────────────┐                       │
│              │   Self Model    │                       │
│              │   (自我模型)     │                       │
│              │                 │                       │
│              │ 知识/未知        │                       │
│              │ 偏差校准         │                       │
│              │ 置信度           │                       │
│              └─────────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

---

## 7. 生命周期管理

### 7.1 Lifespan（v2 新增）

替换废弃的 `@app.on_event("startup")`，使用 FastAPI 现代 lifespan 上下文管理器：

```python
@asynccontextmanager
async def cambium_lifespan(app):
    # ── STARTUP ──
    ensure_directories()
    migrations.run_migrations(DB_PATH)
    _init_module_schemas()
    _load_plugins()
    _init_vector_store()

    # Background tasks
    background_tasks = [
        asyncio.create_task(_start_cron_scheduler()),
        asyncio.create_task(_background_reflection_loop()),
        asyncio.create_task(_start_life_loop()),
        asyncio.create_task(_governance_loop()),
    ]

    yield  # App runs

    # ── SHUTDOWN ──
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
```

### 7.2 后台任务

| 任务 | 间隔 | 功能 |
|------|------|------|
| Cron Scheduler | 按用户配置 | 执行定时任务 |
| Reflection Loop | 10 分钟 | 记忆衰减 + 反思 + KG/episode 提取 |
| Life Loop | 5 分钟检查 | 昼夜节律：hourly/daily/weekly/monthly |
| Governance Loop | 1 小时 | 记忆治理：规则验证 + LLM 验证 + 晋升 |

---

## 8. 配置系统（v2 新增）

### 8.1 分层配置

```python
# 优先级（从高到低）：
# 1. 环境变量（CAMBIUM_ 前缀）
# 2. .env 文件
# 3. SQLite settings 表（用户 UI 覆盖）
# 4. Pydantic Settings 默认值

AppConfig(
    app_name="Cambium",
    app_version="2.0.0",
    ai_name="Cambium",  # 替换硬编码 "CyanX AI"

    api=APIConfig(...),           # LLM API 配置
    chat=ChatConfig(...),         # 对话参数
    memory=MemoryConfig(...),     # 记忆系统
    agent_loop=AgentLoopConfig(...), # Agent Loop
    swarm=SwarmConfig(...),       # Swarm Task
    security=SecurityConfig(...), # 安全配置
    # ... 15+ 子配置
)
```

### 8.2 类型验证

所有配置项都有 Pydantic 类型验证：
- `temperature: float = Field(default=0.6, ge=0.0, le=2.0)`
- `max_tokens: int = Field(default=8192, ge=1, le=131072)`
- `bind_host: str = "127.0.0.1"` （默认仅本地）

---

## 9. 日志系统（v2 新增）

### 9.1 两种格式

**Human 格式**（开发）：
```
2026-07-27 10:00:00 INFO    [app.memory_orchestrator] memory.added  memory_id=abc123  user_id=default
```

**JSON 格式**（生产）：
```json
{"ts": "2026-07-27T10:00:00Z", "level": "info", "module": "app.memory_orchestrator", "event": "memory.added", "memory_id": "abc123", "user_id": "default"}
```

### 9.2 使用方式

```python
from app.logging_config import get_logger
log = get_logger(__name__)

log.info("memory.added", extra={"memory_id": mid, "user_id": uid})
log.error("reflection.failed", extra={"error": str(exc)})
```

---

## 10. 异常处理（v2 新增）

### 10.1 自定义异常层级

```
CambiumError (base)
├── NotFoundError (404)
├── ValidationError (422)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── ConflictError (409)
├── RateLimitError (429)
├── LLMError (502)
├── DatabaseError (500)
└── ToolExecutionError (500)
```

### 10.2 统一错误响应

```json
{
  "error": {
    "code": "not_found",
    "message": "Memory not found",
    "details": {"memory_id": "abc123"},
    "request_id": "req_xyz"
  }
}
```

### 10.3 请求日志中间件

每个 HTTP 请求自动记录：
```json
{"event": "request.completed", "method": "POST", "path": "/api/chat/stream", "status": 200, "duration_ms": 1234.56}
```

---

## 11. 测试架构

### 11.1 测试分层

```
tests/
├── test_cognitive_kernel.py    # 22 个 — 认知内核单元测试
├── test_comprehensive.py       # 72 个 — 全模块单元测试
├── test_life_first_pivot.py    # 18 个 — Life Loop 测试
├── test_residents_pivot.py     # 22 个 — 居民系统测试
├── test_api_integration.py     # 30 个 — v2: API 集成测试
└── test_llm_mock.py            # 12 个 — v2: LLM Mock 测试
```

### 11.2 测试策略

| 层级 | 工具 | 覆盖 |
|------|------|------|
| 单元测试 | pytest | 30/55 模块 |
| API 集成测试 | FastAPI TestClient | 30 个端点 |
| LLM Mock 测试 | unittest.mock + respx | Agent Loop + 治理 + 自适应 |
| 性能测试 | pytest-benchmark | (待添加) |
| E2E 测试 | Playwright | (待添加) |

---

## 12. 部署架构

### 12.1 本地开发

```
用户浏览器 ←→ FastAPI (localhost:3000) ←→ SQLite (app/data/memory.db)
                    ↓
              ModelScope API (或其他 LLM)
```

### 12.2 Docker 部署

```
用户浏览器 ←→ Docker容器 (port 3000)
                    ├── app/data/ (Volume: cambium-data)
                    ├── workspace/ (Volume: cambium-workspace)
                    └── .env (环境变量)
```

### 12.3 未来：多用户部署

```
用户浏览器 ←→ Nginx (反向代理 + TLS)
                    ↓
            Cambium × N (Docker Swarm)
                    ↓
            PostgreSQL (共享数据库)
                    ↓
            Redis (会话 + 缓存)
```

---

## 13. 设计决策记录

### 13.1 为什么用 SQLite 而不是 PostgreSQL？

**决策**：本地优先，单用户场景。

**理由**：
- 用户拥有完全数据控制（可备份、可删除、可迁移）
- 无需数据库运维
- SQLite WAL 模式 + busy_timeout 足够个人使用
- 备份只需复制一个文件

**代价**：多用户场景需要迁移到 PostgreSQL（已在路线图）。

### 13.2 为什么用 SSE 而不是 WebSocket？

**决策**：SSE (Server-Sent Events)。

**理由**：
- SSE 是单向（服务器→客户端），chat 流式正好只需要这个
- SSE 走 HTTP/2，无需协议升级
- 浏览器原生支持，无需额外库
- 调试简单（curl 可直接看流）

**代价**：未来双向通信（如实时工具确认）需要 WebSocket。

### 13.3 为什么保留三种 Agent 引擎？

**决策**：native + LangGraph + AutoGen 并存。

**理由**：
- native：最简单，无外部依赖，适合个人使用
- LangGraph：结构化工作流，适合复杂任务分解
- AutoGen：对话式协作，适合开放讨论

用户通过 `swarm_engine` 配置选择，默认 native。

### 13.4 为什么不删除死代码？

**决策**：保留但标注。

**理由**：
- `dspy_integration.py`：DSPy Signature 设计良好，未来可激活替换硬编码 prompt
- `complexity_tier.py`：渐进复杂度理念有价值，未来可基于用户年龄数据重新激活
- `agent_loop.py` (v1)：保留向后兼容，v2 是新端点

**标注方式**：模块顶部注释明确状态，import 处注释说明。

---

## 14. 路线图

### 短期（v2.1）
- [ ] 拆分 main.py 为 FastAPI routers
- [ ] 增加 WebSocket 推送（Life Loop 结果实时到前端）
- [ ] 真正并行 Swarm（asyncio.gather）
- [ ] 前端框架化（Preact + Signal）

### 中期（v2.5）
- [ ] 多用户支持（PostgreSQL 后端）
- [ ] 多通道网关（Telegram / Discord / CLI）
- [ ] 语音管线（Whisper STT + edge-tts TTS）
- [ ] 评估框架（记忆质量、反思质量自动评估）

### 长期（v3.0）
- [ ] 认知内核独立 PyPI 包
- [ ] OpenTelemetry 可观测性
- [ ] 多设备记忆同步
- [ ] VR/3D 交互界面

---

## 15. 参考文献

| # | 论文 | 模块 |
|---|------|------|
| 1 | SSGM Framework (2026) — Governing Evolving Memory in LLM Agents | `memory_governance.py` |
| 2 | EvolveMem (2026) — Self-Evolving Memory Architecture | `adaptive_retrieval.py` |
| 3 | Generative Agents (Park et al., 2023) | `reflection_tree.py` |
| 4 | Identity Layer (2026) | `identity_consistency.py` |
| 5 | CoALA (Sumers et al., 2023) — Cognitive Architectures for Language Agents | `agent_loop_v2.py` |
| 6 | Claude Code (arXiv:2604.14228, 2026) | `agent_loop_v2.py` |
| 7 | Mem0 (2024) — Building Production-Ready AI Agents with Scalable Long-Term Memory | `memory_orchestrator.py` |
| 8 | TSM (2026) — Beyond Dialogue Time: Temporal Semantic Memory | `cognitive_kernel.py` |
| 9 | OpenClaw (2026) — 网关级能力注册 | (未来: `gateway/`) |
| 10 | N.E.K.O. — 主动性引擎 + 语音 | `proactive_engine.py` |
