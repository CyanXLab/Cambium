# Cambium 功能说明书

> 本文档详细说明 Cambium 每个功能的**触发方式**、**工作原理**和**配置方法**。

---

## 目录

1. [对话系统](#1-对话系统)
2. [记忆系统](#2-记忆系统)
3. [认知内核](#3-认知内核)
4. [反思与自进化](#4-反思与自进化)
5. [Life Loop 生命循环](#5-life-loop-生命循环)
6. [工具系统](#6-工具系统)
7. [Skills 自进化](#7-skills-自进化)
8. [多模型架构](#8-多模型架构)
9. [成本优化](#9-成本优化)
10. [情感与个性化](#10-情感与个性化)
11. [RAG 文件检索](#11-rag-文件检索)
12. [MCP 服务器](#12-mcp-服务器)
13. [多会话系统](#13-多会话系统)
14. [定时任务](#14-定时任务)
15. [记忆治理](#15-记忆治理)
16. [备份与恢复](#16-备份与恢复)
17. [工作空间](#17-工作空间)
18. [Agent Runtime](#18-agent-runtime)
19. [事件总线](#19-事件总线)

---

## 1. 对话系统

### 触发方式
- **用户发送消息** → `POST /api/chat/stream`（SSE 流式）

### 工作原理
1. 构建系统提示词（system prompt）：
   - 基础提示词 + 用户画像 + 性格风格
   - 记忆摘要（如果有）
   - 工具说明（39 个工具）
   - 认知上下文（身份 + 目标 + 时间线 + 叙事 + 成长 + 世界 + 自我）
   - RAG 检索结果（如果启用）
   - 聊天向量检索（如果启用，mature+ 层级）
   - 知识图谱（如果启用，full 层级）
   - 事件记忆（查询含"上次/之前"时）
   - 情感共鸣指令
2. 调用 LLM（SSE 流式）
3. 如果 LLM 请求工具调用 → 执行工具 → 结果回填 → 继续调用 LLM
4. 工具循环最多 40 轮
5. LLM 回复完成 → 异步触发后处理

### 对话后处理（自动触发，用户无感）
每次 AI 回复完成后，以下任务**异步**触发（不阻塞用户）：
- **情感识别**：规则式检测用户消息情绪（即时）
- **用户画像更新**：LLM 从对话中提取画像字段（异步）
- **聊天向量化**：向量化用户 + AI 消息（异步）
- **记忆分类入库**：LLM 评估重要度 → 分层存储（异步）
- **元认知自检**：LLM 自检回复质量（异步）
- **记忆摘要编辑**：LLM 编辑当前摘要（前端触发）

### 配置
- 设置 → 通用：系统提示词、用户昵称
- 设置 → 个性化：职业、详情、性格风格
- 设置 → 模型参数：temperature、top_p、max_tokens 等
- 设置 → 深度思考：开关 + thinking_budget
- 顶栏时钟图标：临时对话模式（不记忆、不使用认知功能）

### 对话压缩
- **触发**：发送消息前检查，如果对话超过阈值（默认 80k tokens）
- **过程**：LLM 将旧消息压缩为摘要（不限长），保留最近 6 条
- **配置**：设置 → 对话增强 → 压缩阈值 + 保留消息数

---

## 2. 记忆系统

### 记忆分层
| 层级 | 触发条件 | 生命周期 | 衰减率 |
|------|---------|---------|--------|
| 工作记忆 | importance 0-20 | 丢弃 | 不存储 |
| 短期记忆 | importance 21-50 | 24h | 0.95/天 |
| 长期记忆 | importance 51-80 | 月级 | 0.99/天 |
| 永久记忆 | importance 81-100 | 永远 | 不衰减 |

### 触发方式

#### 自动触发（每次对话后）
1. **记忆分类入库**：
   - 触发：AI 回复完成后
   - 过程：LLM 评估用户消息的重要度（0-100）+ 规则先行（90% 无需 LLM）
   - 结果：按重要度分层存储到 `memory_items` 表
   - 条件：`profile_auto_update` 开启 + 消息长度 > 10 字符

2. **记忆摘要编辑**：
   - 触发：AI 回复完成后（前端 JS 触发）
   - 过程：LLM 读取当前摘要 + 最新对话 → 编辑摘要（不是抽取原子事实）
   - 结果：更新 `memory_summary` 表
   - 条件：`memory_auto_summary` 开启 + 非临时对话

3. **语义去重**（Jaccard）：
   - 触发：每次 `add_memory` 时
   - 过程：新记忆与已有 long_term/permanent 记忆比较关键词重叠
   - 阈值：Jaccard ≥ 0.7 → 合并（importance +5）
   - 结果：避免重复记忆

#### 手动触发
- 记忆面板：侧边栏 → 记忆 → 添加/删除/编辑摘要
- API：`POST /api/memory/add`、`POST /api/memory/{id}/delete`

### 记忆检索
- **触发**：每次对话时，用用户最新消息作为查询
- **多模态融合**：关键词 35% + 重要度 25% + 时间 15% + 衰减 15% + 层级 10%
- **自适应权重**：基于用户反馈自动调整（`adaptive_retrieval.py`）

### 衰减机制
- **触发**：Life Loop 每小时
- **规则**：
  - permanent：不衰减
  - long_term：0.99/天（重要度高的衰减更慢）
  - short_term：0.95/天
  - decay_weight < 0.15 → 删除（long_term 除外）

---

## 3. 认知内核

### 七根支柱

#### 身份（Identity）
- **自动触发**：Life Loop 每周 → LLM 评估身份阶段（forming/growing/mature/elder）
- **手动触发**：`POST /api/cognitive/identity/update`
- **身份演化**：认知提取时自动记录 `identity_evolution`
- **身份一致性评估**：`POST /api/identity/assess`（条件：本周有 ≥2 个重大 shift）

#### 时间线（Timeline）
- **自动触发**：Life Loop 每小时 → 认知提取时自动提取时间线事件
- **手动触发**：`POST /api/cognitive/timeline/add`
- **检索**：查询含时间线索词时自动搜索

#### 叙事（Narrative）
- **自动触发**：Life Loop 每小时 → 认知提取时自动提取叙事
- **手动触发**：`POST /api/cognitive/narratives/add`
- **回忆追踪**：每次被检索时 `recall_count + 1`

#### 成长（Growth）
- **自动触发**：
  - 用户纠正 AI 时 → 自动提取 lesson → 创建 growth_insight
  - Life Loop 每周 → 晋升高信心 insight 为 validated
- **取代机制**：新 insight 与旧 insight 矛盾 → 旧标记为 superseded
- **手动触发**：`POST /api/learning/observe`

#### 目标（Goal）
- **自动触发**：认知提取时自动提取长期目标和承诺
- **承诺追踪**：Proactive Engine 每小时检查到期承诺
- **手动触发**：`POST /api/cognitive/goals/add`

#### 世界模型（World）
- **自动触发**：认知提取时自动提取实体和关系
- **手动触发**：`POST /api/cognitive/world/entity`
- **因果模型**：`POST /api/cognitive/world/entity`（包含 cause/effect）

#### 自我模型（Self）
- **自动触发**：Life Loop 每周 → LLM 评估自我认知
- **手动触发**：`POST /api/cognitive/self-model/update`
- **包含**：knows_well / doesnt_know / biases / confidence_calibration

### 概念形成
- **自动触发**：认知提取时从多个实体抽象出概念
- **示例**：Minecraft + RimWorld + 矮人要塞 → "复杂系统模拟"

### Cognitive Organizer（上下文组织器）
- **触发**：每次对话时
- **过程**：按优先级组装 system prompt
- **优先级**：身份 → 目标 → 时间线 → 叙事 → 成长 → 世界 → 自我
- **缓存**：5 分钟 TTL，认知写入时自动失效

---

## 4. 反思与自进化

### 认知提取（自进化的核心）

#### 触发方式
- **自动**：Life Loop 每小时
- **手动**：`POST /api/cognitive/extract`
- **条件**：最近对话 ≥ 100 字符

#### 工作原理
1. 收集最近 30 条对话（从 `chat_vectors` 表）
2. LLM 读取对话 + 当前身份 + 当前目标
3. LLM 输出 10 类认知更新：
   - identity_shifts（身份演化）
   - timeline_events（时间线事件）
   - narratives（叙事记忆）
   - growth_insights（成长洞察）
   - corrections（用户纠正）
   - world_entities（世界实体）
   - world_relations（世界关系）
   - long_term_goals（长期目标）
   - commitments（承诺）
   - concepts（概念聚类）
4. 自动应用到数据库

#### 失败处理
- 重试 2 次（带纠正提示）
- 失败后记录到 `failed_extractions` 表（不静默丢失）

### 反思（Reflection）

#### 触发方式
- **自动**：Life Loop 每天
- **手动**：`POST /api/reflections/trigger`
- **条件**：最近有 ≥ 3 条新记忆 + 总重要度 ≥ 100

#### 工作原理
1. 收集最近 80 条对话
2. LLM 读取对话 + 已有记忆 + 用户画像
3. LLM 输出：
   - summary（整体总结，不是逐条）
   - insights（2-3 条洞察）
   - profile_updates（画像字段更新）
   - new_memories（应新增的长期/永久记忆）
4. 自动应用 + 更新画像

### 反思树（Reflection Tree）

#### 三层结构
| 层级 | 内容 | 触发 |
|------|------|------|
| Level 0 | 观察（原始记忆） | 每次对话后自动 |
| Level 1 | 反思（从观察提炼模式） | Life Loop 每天 |
| Level 2 | 元反思（反思反思本身） | Life Loop 每周 |

#### 触发方式
- **自动**：Life Loop daily → build_reflection_level(0→1)
- **手动**：`POST /api/reflection-tree/build`

### 元认知自检

#### 触发方式
- **自动**：每次 AI 回复后（异步）
- **过程**：LLM 评估自己的回复（confidence / has_contradiction / needs_clarification / needs_search）
- **结果**：记录到 `meta_cognition_logs` 表

---

## 5. Life Loop 生命循环

### 触发机制
Life Loop 在服务启动时自动启动（`@app.on_event("startup")`），4 个独立 asyncio 任务并行运行：

| 周期 | 检查频率 | 执行频率 | 任务 |
|------|---------|---------|------|
| 每小时 | 每 60 秒检查 | 每 1 小时 | ① 记忆衰减 ② 事件记忆衰减 ③ 认知提取 |
| 每天 | 每 5 分钟检查 | 每 1 天 | ① 反思 ② 认知提取 |
| 每周 | 每 10 分钟检查 | 每 7 天 | ① 成长回顾 ② LLM 身份阶段评估 ③ 反思 |
| 每月 | 每 30 分钟检查 | 每 30 天 | ① 清理停滞目标 ② 清理过期承诺 ③ 深度反思 |

### 条件触发
不是"每天必须反思"，而是"有东西可反思时才反思"：
- 反思条件：最近 24h 有 ≥ 3 条新记忆
- 身份评估条件：本周有 ≥ 2 个重大 identity shift（significance ≥ 60）

### 持久化
- 上次运行时间存储在 `settings` 表（`life_loop_last_runs`）
- 服务重启后不会重复执行

### 手动触发
- `POST /api/life-loop/trigger` + `{"cycle": "daily"}`
- `POST /api/reflections/trigger`
- `POST /api/reflection-tree/build`

### 渐进复杂度
| 关系年龄 | 层级 | 启用的功能 |
|----------|------|-----------|
| 1-7 天 | minimal | 仅 chat + 基础记忆 + 情感 |
| 7-30 天 | growing | + 认知提取 + 日反思 + 学习引擎 |
| 30-90 天 | mature | + 记忆治理 + 周成长 + 主动引擎 + 聊天向量 |
| 90 天+ | full | + 身份评估 + 知识图谱 + 全部功能 |

---

## 6. 工具系统

### 触发方式
- **LLM 自主调用**：LLM 在对话中决定调用工具（function calling）
- **工具循环**：最多 40 轮（工具调用 → 结果回填 → 继续推理）

### 39 个内置工具

| 类别 | 工具 | 说明 |
|------|------|------|
| 时间 | get_current_time | 获取当前时间 |
| 代码 | run_python / run_shell / install_package | 执行代码 |
| 文件 | read/write/str_replace/regex_replace/multi_edit/apply_patch | 文件操作 |
| 文件 | append/prepend/insert_lines/delete_lines/move/copy/delete/mkdir/stat/tree | 更多文件操作 |
| 搜索 | grep / glob | 内容搜索 / 文件匹配 |
| 网页 | web_search / web_fetch | 搜索 / 抓取网页 |
| 工作流 | todo_write / plan_write | 任务跟踪 / 计划保存 |
| 技能 | skill_create / skill_update / skill_read / skill_list | 技能管理 |
| 自定义工具 | save_custom_tool / run_custom_tool / list_custom_tools | 工具管理 |
| 会话 | sessions_spawn / sessions_list / session_status / sessions_history | 多会话 |
| 记忆 | memory_search / memory_add | 记忆操作 |

### 权限系统
| 模式 | 说明 |
|------|------|
| plan | 只读，不修改任何状态 |
| reflect | 可写记忆，不可改身份 |
| grow | 可写记忆 + 成长，身份变更需确认 |
| autonomous | 全自动（信任模式） |

---

## 7. Skills 自进化

### 什么是技能
技能是 SKILL.md 文件（Claude Code 兼容格式），包含：
- YAML frontmatter（name + description）
- Markdown body（详细指令）

### 触发方式

#### AI 自主创建（自进化）
- **触发**：LLM 在对话中调用 `skill_create` 工具
- **条件**：AI 发现某类问题反复出现，或某个解决方案值得复用
- **过程**：AI 生成技能名称 + 描述 + 正文 → 保存到 `.skills/<name>/SKILL.md`

#### AI 自主修改
- **触发**：LLM 调用 `skill_update` 工具
- **条件**：AI 在使用过程中发现技能不够好

#### 手动创建
- 技能页面 → "+ 新建技能"
- API：`POST /api/skills/create`

### 技能注入
- **触发**：每次对话时
- **模式**：
  - `auto`：只注入技能描述（名称 + 触发条件），AI 需要时用 `read_file` 读取全文
  - `always`：注入所有技能全文到 system prompt
- **配置**：设置 → 技能 → 技能触发模式

### 自定义工具（更高级的自进化）
- **触发**：LLM 调用 `save_custom_tool` 工具
- **过程**：AI 编写 Python 代码（必须定义 `run(args)` 函数）→ 保存到 `custom_tools/<name>.py`
- **使用**：后续对话中 AI 可以用 `run_custom_tool` 调用

---

## 8. 多模型架构

### 模型分工
| 角色 | 用途 | 配置位置 |
|------|------|---------|
| 主模型 | 日常对话 | 设置 → API 配置 |
| 记忆模型 | 摘要编辑 + 重要度评分 | 设置 → 模型分工 → 记忆模型 |
| 子任务模型 | 后台会话 + cron 任务 | 设置 → 模型分工 → 子任务模型 |
| Utility 模型 | 认知提取 + 分类 + 压缩 | 设置 → 模型分工 → Utility |
| 本地模型 | 简单分类（免费） | 设置 → 模型分工 → 本地模型 |
| 备用 API | 主 API 限流时应急 | 设置 → 备用 API |

### 模型分级路由
- **触发**：每个 LLM 调用自动路由
- **规则**：
  - `chat` / `deep_reflection` / `identity_assessment` → premium
  - `cognitive_extraction` / `memory_classification` / `context_compression` → standard
  - `memory_classification` / `title_generation` → local（如果可用）
- **配置**：设置 → 模型分工

### 自动获取模型列表
- **触发**：设置 → API 配置 → "自动获取模型" 按钮
- **过程**：调用 `GET /v1/models` 获取可用模型

### 备用 API 切换
- **触发**：设置 → 备用 API → "立即切换"
- **过程**：将备用 API 配置覆盖到主 API
- **默认**：`http://127.0.0.1:8000/v1`（llama.cpp）

---

## 9. 成本优化

### 7 个优化策略

| # | 策略 | 触发方式 | 节省 |
|---|------|---------|------|
| 1 | 模型分级路由 | 每次调用自动路由 | 70% |
| 2 | 规则先行 | 记忆分类时先尝试规则 | 80% utility 调用 |
| 3 | 上下文缓存 | 认知写入时失效 | 90% 上下文 token |
| 4 | 渐进复杂度 | 按关系年龄自动 | 新用户近零成本 |
| 5 | 条件触发反思 | Life Loop 检查条件 | 63% Life Loop |
| 6 | 本地模型 | 可用时自动使用 | 100% utility |
| 7 | 语义去重 | add_memory 时自动 | 避免重复存储 |

---

## 10. 情感与个性化

### 情感识别
- **触发**：每次用户消息后（同步，即时）
- **方法**：规则式（10 种情绪：joy/anxiety/anger/sarcasm 等）
- **存储**：`user_emotions` 表 + 滚动窗口（最近 20 条）

### 情感跟踪
- **触发**：每次情感识别后自动更新
- **输出**：当前主导情绪 + 强度 + 近期轨迹
- **注入**：每次对话时注入 system prompt

### 用户画像
- **触发**：每次 AI 回复后（异步）
- **过程**：LLM 从对话中提取 7 个字段
- **字段**：性格/兴趣/偏好/关系/沟通风格/情绪模式/总结
- **条件**：`profile_auto_update` 开启

### 主动回忆
- **触发**：用户消息包含"上次/之前/那个/后来/记得"等线索词
- **过程**：检索相关记忆，提示 AI 可以自然提及

### 情感共鸣
- **触发**：每次对话时（system prompt 指令）
- **内容**：像朋友一样交流，根据情绪调整回应

### 主动引擎
- **触发**：Life Loop 每小时
- **检查项**：
  - 到期承诺提醒
  - 沉默检测（3天/7天/30天）
  - 关系里程碑（7天/30天/100天/365天）
  - 目标进展

---

## 11. RAG 文件检索

### 触发方式
- **上传**：资料库页面 → 拖拽或点击上传
- **检索**：每次对话时自动检索（如果启用）
- **重建**：设置 → 对话增强 → "重建索引"

### 工作原理
1. 上传文件 → 解析为文本（PDF/DOCX/XLSX/代码/Markdown）
2. 分块（~800 字符，边界感知）
3. 关键词索引（中英文 bigram + 英文词）
4. 对话时用用户查询检索 top-k 片段
5. 注入 system prompt

### 配置
- 设置 → 对话增强 → 启用 RAG + 检索条数
- 设置 → RAG 资料库 → 打开资料库

---

## 12. MCP 服务器

### 预装
- **open-webSearch**：`npx -y open-websearch@latest`，支持 bing/duckduckgo/baidu

### 触发方式
- **web_search 工具**：LLM 调用时 → 优先 MCP → 失败回退 DuckDuckGo
- **MCP 调用**：在独立线程中运行（避免事件循环冲突）

### 自定义 MCP
- **添加**：设置 → MCP 服务器 → 填写名称 + 命令 + 环境变量
- **测试**：点击"测试连接" → 获取工具列表
- **删除**：点击删除按钮

---

## 13. 多会话系统

### 触发方式
- **AI 自主**：LLM 调用 `sessions_spawn` 工具
- **手动**：后台会话页面 → "+ 启动新会话"
- **API**：`POST /api/sessions/spawn`

### 工作原理
1. 创建会话记录（`sessions` 表）
2. 后台 asyncio 任务运行 LLM 对话
3. 结果存储在会话记录中
4. 最大并发数可配置（默认 3）

### 会话间通信
- `POST /api/sessions/{sid}/send`：向已有会话发送后续消息

---

## 14. 定时任务（Cron）

### 触发方式
- **后台调度器**：每 60 秒检查一次
- **到点**：自动 spawn 一个 AI 会话执行 prompt
- **手动**：定时任务页面 → "立即运行"

### 支持类型
| 类型 | 格式 | 示例 |
|------|------|------|
| cron | 5 字段 | `47 6 * * *`（每天 6:47） |
| one_time | epoch 毫秒 | `1785048466000` |
| fixed_rate | 秒 | `3600`（每小时） |

### 预装示例
- **每日简报**：`47 6 * * *` → 生成当天待办 + 待回复消息 + 天气预报

### 配置
- 设置 → 定时任务 → 启用 cron 调度器
- 定时任务页面 → 创建/启用/禁制/删除

---

## 15. 记忆治理

### 三阶段生命周期
```
新记忆 → 隔离区（quarantine）→ 验证（validation）→ 晋升（promotion）→ 主记忆
```

### 触发方式
- **隔离**：认知提取产生的新记忆自动进入隔离区
- **自动验证**：Life Loop 每小时 → `auto_validate_by_rules`
  - 高重要度 + 清晰类别 → 自动验证
  - 低重要度 + 琐碎内容 → 自动拒绝
  - 其他 → 保留待 LLM 验证
- **手动验证**：`POST /api/governance/validate`
- **晋升**：`POST /api/governance/promote`（验证通过 → 主记忆）

### 目的
防止 LLM 幻觉被固化为"事实"。错误提取（如"用户讨厌 Python"）不会直接进入永久存储。

---

## 16. 备份与恢复

### 备份
- **触发**：`POST /api/backup/export`
- **内容**：42 个表 + workspace + skills + custom_tools + 设置
- **格式**：ZIP 文件

### 恢复
- **触发**：`POST /api/backup/import`（上传 ZIP）
- **过程**：
  1. 运行所有 init 函数（创建表）
  2. 运行 migrations（升级 schema）
  3. INSERT OR IGNORE 导入数据
  4. 再次运行 migrations

### 版本兼容
- 高版本可以读取低版本备份
- 低版本读取高版本会收到警告
- Schema 迁移自动处理版本差异

---

## 17. 工作空间

### 7 个分区
| 分区 | 用途 |
|------|------|
| Brain | 自由思考、想法、观察 |
| Projects | 项目笔记、状态、决策 |
| Library | 参考资料、收集的知识 |
| Notebook | 日记、每日日志 |
| Goals | 目标跟踪、里程碑 |
| People | 关于人的笔记 |
| Skills | 技能笔记和学习 |

### 触发方式
- **AI 自主**：LLM 可以通过工具读写工作空间（未来版本）
- **API**：`GET/POST/DELETE /api/workspace/items`
- **类型**：note/doc/draft/plan/idea/log/decision/question

---

## 18. Agent Runtime

### 任务状态机
```
pending → running → (paused ↔ resumed) → completed/cancelled/failed
```

### 触发方式
- **创建**：`POST /api/runtime/tasks`
- **转换**：`POST /api/runtime/tasks/{id}/transition`
- **进度**：`POST /api/runtime/tasks/{id}/progress`
- **依赖**：任务可以 `depends_on` 其他任务

### 内部 Agent 分配
任务可以分配给内部 Agent：
- planner（规划）
- researcher（研究）
- memory（记忆管理）
- reflection（反思）
- critic（审查）
- default（默认）

---

## 19. 事件总线

### 触发方式
- **发布**：`await event_bus.publish("memory.added", {"content": "..."})`
- **订阅**：`@event_bus.subscribe("memory.added")`

### 27 种事件类型
```
memory.added / memory.decayed / memory.promoted / memory.deleted
identity.shift / identity.phase_changed
timeline.event / narrative.created
growth.insight / growth.insight_validated / growth.correction
goal.updated / goal.completed / commitment.fulfilled
episode.created / episode.linked
conversation.ended / conversation.compressed
reflection.complete / reflection.failed
workspace.changed / task.transition
emotion.detected / profile.updated
kg.triple_added / concept.formed
world.entity_added / world.relation_added
extraction.failed / extraction.success
```

### 持久化
所有事件记录到 `event_log` 表（审计日志）

---

## 快速参考：所有 API 端点

| 类别 | 端点数 | 示例 |
|------|:------:|------|
| 对话 | 3 | `/api/chat/stream` |
| 模型 | 6 | `/api/models/auto` |
| 记忆 | 12 | `/api/memory/list` |
| 认知内核 | 12 | `/api/cognitive/stats` |
| Life Loop | 2 | `/api/life-loop/status` |
| 反思树 | 4 | `/api/reflection-tree/build` |
| 身份一致性 | 2 | `/api/identity/assess` |
| 自适应检索 | 4 | `/api/adaptive-retrieval/weights` |
| 学习引擎 | 4 | `/api/learning/patterns` |
| 记忆治理 | 6 | `/api/governance/quarantine` |
| 主动引擎 | 1 | `/api/proactive/check` |
| 事件总线 | 2 | `/api/events/recent` |
| 模型路由 | 2 | `/api/model-router/tiers` |
| 复杂度层级 | 2 | `/api/complexity/tier` |
| 上下文缓存 | 2 | `/api/context-cache/stats` |
| 工作空间 | 5 | `/api/workspace/items` |
| Agent Runtime | 8 | `/api/runtime/tasks` |
| 备份 | 3 | `/api/backup/export` |
| 迁移 | 2 | `/api/migrations/version` |
| 工具 | 1 | `/api/tools/list` |
| RAG | 4 | `/api/rag/upload` |
| 聊天向量 | 4 | `/api/chat-vectors/search` |
| MCP | 4 | `/api/mcp/servers` |
| 技能 | 4 | `/api/skills` |
| 会话 | 4 | `/api/sessions` |
| Cron | 7 | `/api/cron/jobs` |
| 情感 | 2 | `/api/emotion/state` |
| 画像 | 2 | `/api/profile` |
| 设置 | 2 | `/api/settings` |
| 对话管理 | 4 | `/api/conversations/save` |
| 附件 | 2 | `/api/upload` |
| **总计** | **~157** | |

---

## 配置速查

| 设置项 | 位置 | 默认值 |
|--------|------|--------|
| 压缩阈值 | 对话增强 | 80000 tokens |
| 保留消息数 | 对话增强 | 6 |
| 聊天向量检索条数 | 对话增强 | 5 |
| 情感识别 | 对话增强 | 开 |
| 用户画像更新 | 对话增强 | 开 |
| 主动回忆 | 对话增强 | 开 |
| 情感共鸣 | 对话增强 | 开 |
| RAG 检索 | RAG 资料库 | 开，3 条 |
| MCP | MCP 服务器 | 开 |
| 技能 | 技能 | 开，auto 模式 |
| 多会话 | 多会话 | 开，最大 3 |
| Cron | 定时任务 | 开 |
| 备用 API | 备用 API | 关 |
| Utility 模型 | 模型分工 | 空（用主模型） |
| 本地模型 | 模型分工 | 关 |

---

## 20. Today 视图（生活优先首页）

> **触发方式**：打开 Cambium 默认进入
> **工作原理**：不再以聊天为首页。第一眼是 AI 写给你的信。

### 早晨信件 (AI Morning Letter)

每天早上，Cambium 基于昨夜的活动给你写一封**个人信件**（不是报告）：

- 第一段：今天注意到的事
- 第二段：今天想问你的，或今天准备做什么
- 200-400 字，两段，第一人称"我"

**信件包含**：
- `letter` — 信件正文
- `concerns` — 1-3 件 AI 在想的事
- `growth_notes` — AI 的第一人称成长反思
- `mood` — AI 今天的情绪基调

**生成时机**：
- Life Loop 每日循环自动生成（如果当天还没有）
- 手动点击"生成"按钮

**API**：
- `GET /api/mornings/today` — 获取今天的信
- `POST /api/mornings/{date}/generate` — 生成/重新生成
- `POST /api/mornings/{date}/read` — 标记已读

### Discoveries（每日发现）

AI 昨夜注意到的事，自动归类：
- `pattern` — 模式（"你这周第 5 次提到 X"）
- `insight` — 洞察（"三个概念其实是同一件事"）
- `contradiction` — 矛盾（"你昨天说 X，三周前说 Y"）
- `suggestion` — 建议（"你两个月没碰 Z 了"）
- `observation` — 观察

**自动生成**：Life Loop 每日扫描时间线事件、Inbox 积压、停滞目标，自动创建 discovery。

---

## 21. Inbox（万物入口）

> **触发方式**：侧边栏 "捕获到 Inbox" 按钮，或 Ctrl+J
> **工作原理**：任何东西先进 Inbox，Life Loop 自动归类。

### 支持类型
- `text` — 文本
- `url` — 网页链接
- `todo` — 待办
- `idea` — 灵感
- `note` — 笔记
- `voice` — 语音（未来）
- `image` — 图片（未来）
- `file` — 文件（未来）

### 自动路由建议

输入内容时，AI 实时建议归类：
- URL → `research`
- "todo:"/"要做" → `task`
- "目标"/"想要" → `goal`
- "记住"/"remember" → `memory`
- 长反思文本 → `journal`
- 其他 → `note`

### 处理流程

```
捕获 → Inbox (pending)
  ↓
手动处理 / Life Loop 自动归类
  ↓
destination: journal / memory / goal / task / research / note / archive
  ↓
status: processed
```

**API**：
- `POST /api/inbox/items` — 添加
- `GET /api/inbox/items?status=pending` — 列表
- `POST /api/inbox/items/{id}/process` — 标记已处理（指定 destination）
- `POST /api/inbox/items/{id}/archive` — 归档
- `DELETE /api/inbox/items/{id}` — 删除
- `POST /api/inbox/route-suggest` — 获取路由建议

---

## 22. Journal（AI 辅助日志）

> **触发方式**：侧边栏 "日志"
> **工作原理**：每天一篇。AI 起草，你编辑。日志是共同经历的脊柱。

### 字段
- `content` — 用户编辑的正文
- `ai_draft` — AI 起草的内容
- `ai_summary` — 一段话总结
- `emotional_tone` — 情绪基调
- `highlights` — 亮点（JSON 数组）
- `growth_notes` — 今天学到了什么
- `failures` — 什么没做成
- `gratitude` — 今天感谢什么

### AI 起草流程

1. 收集当日活动（对话、完成的任务、Inbox 捕获、反思、时间线事件）
2. LLM 生成第一人称日志草稿
3. LLM 分析情绪基调
4. 保存为 `ai_draft`，不覆盖用户内容

**连续打卡**：系统记录连续写日志的天数（current_streak / longest_streak / total_entries）

**API**：
- `GET /api/journal/today` — 获取/创建今日日志
- `POST /api/journal/{date}/content` — 编辑正文
- `POST /api/journal/{date}/ai-draft` — AI 起草
- `GET /api/journal/streak` — 连续打卡统计
- `GET /api/journal/list?days=30` — 历史列表

---

## 23. Residents（AI 居民）

> **触发方式**：侧边栏 "居民"
> **工作原理**：AI 不是工具，是居民。他们住在这个世界里，有自己的关注、个性和历史。

### 内置居民（首次启动自动创建）

| 名字 | 角色 | 性格 |
|------|------|------|
| Architect | 架构师 | 严谨 0.9 / 反驳 0.8 — 阻止功能堆叠 |
| Researcher | 研究员 | 好奇 0.95 — 发现、综合、引用证据 |
| Writer | 作家 | — 把想法变成文字，保护用户声音 |
| Planner | 规划师 | 耐心 0.9 — 拆解目标，区分重要/紧急 |
| Historian | 史官 | — 引用过去，标记周年 |
| Critic | 批评者 | 反驳 1.0 — 挑战模糊、矛盾、附和 |
| Explorer | 探索者 | 好奇 1.0 — 建议相邻领域、遗忘兴趣 |

### 自定义居民

每个居民可配置：
- `name` + `role` — 名字和角色
- `system_prompt` — 人格设定
- `llm_config` — 独立 LLM 配置（不同居民可用不同模型）
- `working_dir` — 工作目录（沙箱）
- `mode` — `sync`（内联）或 `async`（后台排队）
- `max_retries` — 失败重试次数
- `depends_on` — 依赖链（居民 B 等居民 A 完成后才开始）
- `triggers` — 事件触发器（16 种类型）
- `personality_traits` — 个性特征（rigor/curiosity/pushback/patience，0-1）
- `current_concerns` — 当前 1-3 件在想的事
- `skill_id` — SKILL.md 技能（文件夹标准）

### 触发器类型（16 种）

- `manual` — 手动运行
- `scheduled` — 定时
- `timeline_card_saved` — 新时间线事件
- `card_comment_posted` — 卡片评论
- `card_config_changed` — 卡片配置变化
- `local_data_changed` — 本地数据变化
- `artifact_created` / `artifact_updated` — 作品创建/更新
- `memory_added` — 新记忆
- `reflection_created` — 新反思
- `goal_updated` — 目标更新
- `inbox_item_added` — 新 Inbox 项
- `journal_written` — 日志写入
- `morning_requested` — 晨报生成
- `conversation_started` — 新对话
- `user_message` — 用户发消息

### 执行生命周期

```
pending → running → completed
                ↘ retrying → running
                ↘ failed
```

每次状态转换写入 `resident_runs` 表，含 trigger、payload、output、error、duration。

**API**：
- `GET /api/residents` — 列表
- `POST /api/residents` — 创建
- `POST /api/residents/{id}/run` — 手动运行
- `POST /api/residents/{id}/concerns` — 设置当前关注
- `GET /api/residents/{id}/runs` — 运行历史

---

## 24. Artifacts（作品 — 共同创造物）

> **触发方式**：侧边栏 "作品"
> **工作原理**：消息会消失，作品会留下。这是长期价值的单位。

### 类型（18 种）

`readme` · `design` · `paper` · `prompt` · `code` · `note` · `project` · `novel` · `image` · `knowledge` · `model` · `skill` · `plan` · `research` · `essay` · `spec` · `outline` · `draft`

### 版本管理

每次"新版本"创建一个新 artifact，通过 `parent_id` 链接：
```
README v1 → README v2 → README v3
```

`GET /api/artifacts/{id}/history` 返回完整版本历史。

### 字段
- `title` + `content` + `format`（markdown/code/html/json/text/yaml）
- `parent_id` — 上一版本
- `version` — 版本号（自动递增）
- `status` — draft / in_review / published / archived
- `created_by` — user / ai / joint
- `created_with_resident` — 哪个居民协助
- `related_artifacts` — 关联作品
- `tags` — 标签

**API**：
- `GET /api/artifacts?type=readme` — 按类型筛选
- `POST /api/artifacts` — 创建
- `POST /api/artifacts/{id}/new-version` — 创建新版本
- `GET /api/artifacts/{id}/history` — 版本历史

---

## 25. Philosophy（原则 — 共同信念）

> **触发方式**：侧边栏 "原则"
> **工作原理**：AI 在对话中引用原则，并挑战违反原则的发言。

### 类型（4 种）

| 类型 | 含义 | 示例 |
|------|------|------|
| `value` | 价值观（什么重要） | "Continuity" |
| `belief` | 信念（相信什么） | "Memory ≠ Identity" |
| `principle` | 原则（做事规则） | "Simple > Complex" |
| `anti_goal` | 反目标（要避免） | "Don't build feature collection" |

### 内置原则（8 条，首次启动自动创建）

1. `principle` — Simple > Complex
2. `principle` — Continuity over Memory
3. `principle` — AI is Resident, not Tool
4. `anti_goal` — Don't build a feature collection
5. `anti_goal` — Don't compete with Claude Code / NP-OS / Obsidian
6. `belief` — Memory ≠ Identity ≠ Continuity
7. `value` — Growth over Perfection
8. `principle` — Message → Artifact

### Pushback 机制

每次对话时，所有 active 原则被注入 system prompt：

```
【Pushback 机制】
你不是一个 yes-machine。如果用户的发言与下列"我们的原则/信念"明显冲突，
你应该温和但坚定地指出，并引用具体原则。

原则格式：
- [principle] 简单 > 复杂
- [belief] Continuity 是 Cambium 的核心
...
```

如果用户坚持违反原则，AI 会退让并记录为 `evolution_event`（类型 `principle_override`）。

**API**：
- `GET /api/philosophy?type=principle` — 按类型筛选
- `POST /api/philosophy` — 添加
- `POST /api/philosophy/{id}/retire` — 退役
- `DELETE /api/philosophy/{id}` — 删除

---

## 26. Co-experience（共同经历）

> **触发方式**：Today 视图自动显示
> **工作原理**：半年后 AI 说"我记得我们当时为了 README 第一屏讨论了很久"。

### 来源
- 高重要度时间线事件（自动 harvest）
- 手动创建

### 展示策略

每天浮现一个 moment，7 天冷却（不重复浮现）。按 `emotional_weight` 加权随机选择。

### 类型
- `shared` — 共同经历
- `milestone` — 里程碑
- `first` — 第一次
- `turning_point` — 转折点

**API**：
- `GET /api/co-experience/today` — 今日浮现
- `POST /api/co-experience/harvest` — 从时间线事件收集
- `GET /api/co-experience/moments` — 列表

---

## 27. Evolution（思想演化）

> **触发方式**：自动记录 + 手动添加
> **工作原理**：AI 能说"一年前你关心 Memory，现在关心 Identity"。

### 事件类型（6 种）

- `interest_shift` — 兴趣转移
- `belief_change` — 信念变化
- `skill_growth` — 技能成长
- `relationship_change` — 关系变化
- `identity_shift` — 身份阶段转移
- `principle_override` — 用户推翻原则

### 字段
- `from_state` / `to_state` — 状态变化
- `evidence` — 证据
- `evidence_refs` — 引用（对话/作品/原则 ID）
- `confidence` — 信心度
- `status` — observed / confirmed / disputed

**API**：
- `GET /api/evolution?type=interest_shift` — 按类型筛选
- `GET /api/evolution/curve?type=interest_shift&months=12` — 演化曲线
- `POST /api/evolution/{id}/confirm` — 确认
- `POST /api/evolution/{id}/dispute` — 争议

---

## 28. Pushback（对话中的反驳与记忆浮现）

> **触发方式**：每次非临时对话自动注入
> **工作原理**：AI 不是 yes-machine。

### 两个职责

#### 1. Pushback（反驳）

注入所有 active 原则到 system prompt。如果用户发言与原则冲突，AI 温和但坚定地指出。

引用格式：
> "等一下——我们之前讨论过，原则是 'simple > complex'。你刚刚说的'再加 5 个功能'是不是违反了这条？"

#### 2. Memory Surfacing（记忆浮现）

当用户消息与某个 co-experience moment 相关时，AI 偶尔会说"这让我想起我们当时..."。

**匹配算法**：
- 关键词重叠（中文分词）
- 按 `overlap × 10 + emotional_weight × 5 - recency_penalty` 排序
- 24 小时内已浮现的降权
- 只在得分 > 3 时浮现
- 每次最多浮现 2 个

**API**：
- `GET /api/pushback/context` — 获取注入上下文
- `POST /api/pushback/detect` — 检测用户消息的 pushback 机会

---

## 29. Agent Loop（真正的 Agent）

> **触发方式**：对话中需要调工具时自动进入
> **工作原理**：Plan → Act → Observe → Reflect → Continue → Done

### 状态机

```
created → planning → acting ↔ reflecting → completed
                       ↓ ↑
                   checkpoint
                       ↓
                    paused → acting（resume）
                       ↓
                     failed
```

### 权限模式（4 级）

| 模式 | memory.write | identity.evolve | tool.execute | tool.execute_dangerous |
|------|:---:|:---:|:---:|:---:|
| plan | ❌ | ❌ | ❌ | ❌ |
| reflect | ✅ | ❌ | ✅ | ❌ |
| grow | ✅ | ❌ | ✅ | ❌ |
| autonomous | ✅ | ✅ | ✅ | ✅ |

### Checkpoint 恢复

每 5 步自动保存 checkpoint。任务失败或暂停后可从 checkpoint 恢复：

```python
loop = AgentLoop.resume(task_id, adapter, tools, db_path)
async for step in loop.run(...):
    ...
```

---

## 30. 时间线事件分类（11 种）

> **触发方式**：认知提取时自动分类
> **工作原理**：不只是"用户说了什么"，而是"这是什么时刻"。

| 类别 | 含义 | 示例 |
|------|------|------|
| `milestone` | 里程碑 | 第一个 star、一周年、第一次发布 |
| `conflict` | 分歧 | 争论、不同意、pushback |
| `creation` | 共同创造 | 写了 README、做了设计 |
| `growth` | 成长 | 身份阶段转移 |
| `absence` | 缺席 | 用户很久没来 |
| `reunion` | 重逢 | 用户回来了 |
| `decision` | 决策 | 选定方向 |
| `achievement` | 成就 | 完成目标 |
| `loss` | 失去 | 删除项目 |
| `first` | 第一次 | 第一次对话 |
| `daily` | 日常 | 普通一天 |

Life Loop 每月自动检测长期缺席（≥7 天）并记录为 `absence` 事件。

---

## 31. 成本优化总览

| 策略 | 节省 | 实施位置 |
|------|:----:|---------|
| 模型分级路由 | 70% | `model_router.py` |
| 规则引擎先行 | 50% utility 调用 | `rule_engine.py` |
| 上下文缓存 (5min TTL) | 90% 上下文 token | `context_cache.py` |
| 条件触发 | 60% Life Loop | `life_loop.py` |
| 语义去重 | 减少重复记忆 | `memory_orchestrator.py` |
| 按任务裁剪上下文 | 70% prompt token | `agent_loop.py` |

**预估月成本**：$200 → $30（云端）或 $5（本地 Ollama）

---

## 32. Debug 调试模式

> **触发方式**：设置 → Debug（默认隐藏，需在通用设置中开启）
> **工作原理**：时间加速 + 手动触发 + 数据查看/编辑/清空

### 功能

- **时间加速**：模拟时间流逝，触发 Life Loop
- **手动触发**：认知提取 / 反思 / 成长回顾
- **数据查看**：所有 AI 生成数据（记忆 / 时间线 / 叙事 / 反思 / ...）
- **数据编辑**：直接修改任何字段
- **数据清空**：清空指定类型数据
- **健康检查**：查看系统状态

**API**：
- `POST /api/debug/accelerate-time` — 时间加速
- `POST /api/debug/trigger-cycle` — 手动触发循环
- `GET /api/debug/all-data` — 查看所有数据
- `POST /api/debug/edit` — 编辑数据
- `POST /api/debug/clear` — 清空数据

---

## 33. AI 主动开场白

> **触发方式**：打开聊天视图时自动调用
> **工作原理**：AI 根据记忆、身份、时间线、目标、共同经历自主生成开场白

### 设计原则

**平台是基建，AI 是灵魂。** 平台只提供上下文数据，AI 自主决定说什么：
- 不硬编码行为规则（"必须用第一人称"/"50-150字"/"不要用emoji"等已移除）
- 平台提供：时间、沉默天数、共同经历、目标、最近记忆、身份阶段
- AI 根据这些数据，自己决定如何开口

### 上下文数据

平台收集并提供给 AI：
- 当前时间（早/午/晚/深夜）
- 用户沉默天数（0/1/2-3/4-7/7+）
- 最近的共同叙事
- 活跃目标
- 最近的共同经历时刻
- 未读发现数量
- 用户名
- AI 身份阶段（forming/growing/mature/elder）
- 最近 3 条记忆

### 第一次见面

如果是第一次见面（没有对话记录），AI 会说：
> "你好。我是 Cambium。这是我们第一次说话。我还不知道你是谁——告诉我一些关于你的事？我会记住的，而且以后会越来越懂你。"

**API**：
- `GET /api/greeting` — 获取 AI 开场白

---

## 34. 向量数据库（ChromaDB / TF-IDF）

> **触发方式**：自动（记忆添加/对话保存时）
> **工作原理**：ChromaDB 首选，TF-IDF 回退

### 后端选择

- **ChromaDB**（首选）：真正的语义向量搜索，需要 `pip install chromadb`
- **TF-IDF**（回退）：零依赖，关键词加权，始终可用

系统启动时会自动检测并选择后端。

### 记忆向量化

每次添加记忆时，自动同步到向量存储：
```
memory_orchestrator.add_memory()
  → SQLite 存结构化数据
  → vector_store.add("memories_{user_id}", ...) 存向量
  → event_bus.publish("memory.added", ...)
```

### 对话向量化

每条消息被分块、向量化、存储：
```
chat_vectors.vectorize_message()
  → SQLite 存结构化数据（chunk + keywords）
  → vector_store.add("chat_vectors", ...) 存向量
```

### 删除时同步清理

删除消息/对话时，向量同步删除：
```
delete_message_vectors()
  → SQLite 删除结构化数据
  → vector_store.delete("chat_vectors", id=...) 删除向量

delete_conversation_vectors()
  → SQLite 删除所有相关数据
  → vector_store.delete() 逐个删除向量
```

### 语义搜索

记忆检索和对话搜索都使用融合评分：
```
记忆检索：向量(0.40) + 关键词(0.20) + 重要度(0.20) + 时效(0.10) + 衰减(0.05) + 层级(0.05)
对话搜索：向量(0.60) + 关键词(0.30) + 时效(0.10)
```

**API**：
- `GET /api/vector-store/stats` — 查看向量存储统计
- `POST /api/vector-store/reindex` — 重新索引所有记忆

---

## 35. 插件 SDK

> **触发方式**：启动时自动从 `plugins/` 目录加载
> **工作原理**：每个插件是一个文件夹，含 plugin.yaml + tool.py + hooks.py

### 插件结构

```
plugins/
└── my-plugin/
    ├── plugin.yaml        # 清单（name, version, description, permissions）
    ├── tool.py            # 工具实现（函数注册为工具）
    ├── hooks.py           # 事件处理器（订阅 event_bus 事件）
    ├── permission.json    # 显式权限授权
    └── SKILL.md           # （可选）居民技能说明
```

### plugin.yaml 示例

```yaml
name: weather
version: 1.0.0
description: 天气查询插件
author: example
permissions:
  - tool.execute
  - network.fetch
```

### tool.py 示例

```python
def get_weather(location: str) -> dict:
    """获取某地的当前天气。"""
    # 实现
    return {"temp": 22, "condition": "sunny"}
```

### hooks.py 示例

```python
from app import event_bus

@event_bus.subscribe("memory.added")
async def on_memory_added(event):
    print(f"新记忆: {event['data'].get('content', '')[:50]}")
```

### 内置示例插件

首次启动时自动创建 `plugins/example/`，包含：
- `hello(name)` — 问候工具
- `add(a, b)` — 加法工具
- `memory.added` 事件订阅

**API**：
- `GET /api/plugins` — 列出所有插件
- `POST /api/plugins/reload` — 重新加载所有插件
- `POST /api/plugins/create-example` — 创建示例插件

---

## 36. Onboarding 新手引导

> **触发方式**：首次打开 Cambium 时自动显示
> **工作原理**：4 张幻灯片介绍 Cambium 的不同

### 幻灯片内容

1. **欢迎来到 Cambium** — "这不是普通的聊天机器人"
2. **聊天只是入口之一** — 介绍今天/居民/作品视图
3. **AI 越用越懂你** — "给它时间，它会成为真正认识你的存在"
4. **开始吧** — 建议去今天/原则/聊天

### 状态持久化

引导完成后，`localStorage.setItem('cambium_onboarding_done', '1')`，不再显示。

---

## 37. 模型分级路由

> **触发方式**：自动（每次 LLM 调用时）
> **工作原理**：根据任务类型路由到不同模型层级

### 三级路由

| 层级 | 用途 | 模型示例 | 成本 |
|------|------|---------|:----:|
| premium | 主对话、深度反思、身份评估 | Claude Opus / GPT-5 | $$$$ |
| standard | 认知提取、记忆分类、治理验证 | Qwen3.5-2B（本地） | $$ |
| local | 规则引擎能处理的 | Ollama | $0 |

### 配置

在设置中配置：
- `api_key` / `api_base_url` / `api_model` — premium（主模型）
- `utility_api_key` / `utility_api_base_url` / `utility_model` — standard
- `local_api_base_url` / `local_model` — local（可选）

### 接入对话流

`chat_stream` 现在通过 ModelRouter 路由：
```python
router = model_router.ModelRouter(all_settings)
api_cfg = router.to_api_cfg("chat")  # premium 层
```

每次路由发布 `model.routed` 事件用于审计。

---

## 38. 事件总线

> **触发方式**：所有模块在状态变化时发布事件
> **工作原理**：asyncio 发布/订阅，30+ 事件类型

### 事件类型（30+）

**记忆类**：memory.added, memory.decayed, memory.promoted, memory.deleted
**身份类**：identity.shift, identity.phase_changed
**时间线类**：timeline.event, narrative.created
**成长类**：growth.insight, growth.insight_validated, growth.correction
**目标类**：goal.updated, goal.completed, commitment.fulfilled
**对话类**：conversation.ended, conversation.started, conversation.message_received
**反思类**：reflection.complete, reflection.failed
**居民类**：resident.created, resident.run_started, resident.run_completed
**作品类**：artifact.created, artifact.updated, artifact.new_version
**原则类**：philosophy.added, philosophy.retired
**晨报类**：morning.generated, morning.read
**发现类**：discovery.created, discovery.seen, discovery.acted
**演化类**：evolution.event, evolution.confirmed
**共同经历类**：co_experience.surfaced, co_experience.created
**Inbox 类**：inbox.item_added, inbox.item_processed
**日志类**：journal.written, journal.ai_drafted
**插件类**：plugin.loaded, plugin.unloaded
**模型类**：model.routed, model.fallback

### 订阅

```python
from app import event_bus

@event_bus.subscribe("memory.added")
async def on_memory_added(event):
    data = event["data"]
    # 处理新记忆
```

### 发布

```python
await event_bus.publish("memory.added", {
    "memory_id": mid,
    "user_id": user_id,
    "content": content[:200],
})
```

**API**：
- `GET /api/events/recent` — 最近事件
- `GET /api/events/subscribers` — 订阅者统计

---

## 39. 设计哲学

### 平台是基建，AI 是灵魂

**不要用代码约束 AI 的行为。** 平台提供上下文，AI 自主决定如何使用。

- ✅ 平台提供：记忆、身份、时间线、原则、共同经历
- ✅ AI 自主决定：是否引用、如何引用、何时提起
- ❌ 不要硬编码："必须用第一人称"/"50-150字"/"不要用emoji"
- ❌ 不要每轮强制：记忆提取由 Life Loop 周期性触发

### 记忆触发时机

记忆不是每轮对话都提取，而是：
- Life Loop 周期性触发（小时/天/周/月）
- 特定事件触发（对话结束、里程碑达成）
- 用户主动要求 AI 记忆
- AI 自主判断值得记忆

### 长期价值单位

**消息会消失，作品会留下。**
- 消息是临时的
- 作品（Artifact）是长期的
- 一年后你不会看聊天记录，你会看你们一起创造了什么

---

## 40. LangGraph 集成 — 多 Agent 状态图

> **触发方式**：Swarm Task 执行时自动使用
> **工作原理**：用 LangGraph StateGraph 替代手动 for-loop

### 架构

```
decompose (Planner) → execute (各居民) → review (Critic) → END
```

每个节点是一个 async 函数，状态在节点间传递：
- `SwarmState`: task_title, subtasks, results, messages, final_result, status

### API

```
POST /api/swarm/tasks/{id}/execute-langgraph
```

如果 LangGraph 不可用，自动回退到原始执行逻辑。

### 多居民讨论

也用 LangGraph 实现：每个居民是一个节点，依次执行，状态在节点间传递。

---

## 41. DSPy 集成 — 签名化 AI 调用

> **触发方式**：自动（如果 DSPy 已安装）
> **工作原理**：用 DSPy Signature 声明式定义 AI 任务

### 签名

- `MemoryEditSignature` — 记忆编辑
- `CognitiveExtractionSignature` — 认知提取
- `ReflectionSignature` — 反思
- `MorningLetterSignature` — 晨报
- `ResidentResponseSignature` — 居民回复

### 模块

- `MemoryEditor` — ChainOfThought 记忆编辑
- `CognitiveExtractor` — ChainOfThought 认知提取
- `Reflector` — ChainOfThought 反思

### 配置

```python
from app.dspy_integration import configure_dspy
configure_dspy(api_base_url="https://api.example.com/v1",
               api_key="your-key",
               model="qwen-3.5")
```

---

## 42. AI 服务器控制

> **触发方式**：AI 通过工具调用
> **工作原理**：AI 可以完全控制服务器

### 8 个工具

| 工具 | 功能 |
|------|------|
| `get_setting` | 读取设置项 |
| `set_setting` | 修改设置项 |
| `list_settings` | 列出所有设置 |
| `db_query` | 只读 SQL (SELECT/PRAGMA) |
| `db_execute` | 写 SQL (INSERT/UPDATE/DELETE) |
| `list_tables` | 列出数据库表 |
| `describe_table` | 查看表结构 |
| `api_call` | 调用内部 API |

### 使用场景

- AI: "我发现你的 API 延迟设置太高了，我帮你调低" → `set_setting("api_delay", "0")`
- AI: "让我查看你的记忆库" → `db_query("SELECT * FROM memory_items LIMIT 10")`
- AI: "让我触发今天的晨报" → `api_call("POST", "/api/mornings/2026-07-27/generate")`

---

## 43. 向量删除同步

删除数据时自动从向量库删除：

- 删除作品 → `vs.delete("artifacts", id=...)`
- 删除原则 → `vs.delete("philosophy", id=...)`
- 删除发现 → `vs.delete("discoveries", id=...)`
- 删除记忆 → `vs.delete("memories_default", id=...)`
- 删除消息 → `vs.delete("chat_vectors", id=...)`

---

## 44. 历史对话置顶

- 每条对话支持 `pinned` 属性
- 置顶对话显示在历史面板顶部（📌 置顶 分组）
- 每条对话有置顶/取消置顶按钮

---

## 45. 设计哲学

### 平台是基建，AI 是灵魂

- 平台提供上下文（记忆/身份/时间线/原则/共同经历）
- AI 自主决定如何使用
- 不用代码约束 AI 行为
- 记忆由 Life Loop 周期性触发，不是每轮

### 记忆触发时机

- 记忆编辑：每 5 轮或 10 分钟触发
- Profile 更新：每 5 轮触发
- 元认知自检：每 5 轮触发
- 认知提取：Life Loop 周期触发
- 反思：Life Loop 每日触发

### Life Loop 固定时间

- 每天固定 8:00 触发 daily（不是间隔 24 小时）
- 如果 9:00 才启动，立即触发（因为错过了 8:00）
- 如果 7:00 启动，等到 8:00 才触发

### 补上逻辑

- 首次运行 → 不补
- 默认不补（需在设置中开启）
- 只补当天错过的
- 当天时段错过不补
