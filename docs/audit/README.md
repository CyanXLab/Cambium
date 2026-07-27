# Cambium 源码审计文档

> 本目录由源码审计生成，不依赖原 README 与 docs/USAGE.md 的描述。
> 用户明确指出"README 和功能介绍不是最新的，而且是 AI 写的可能有错误和幻觉"，因此本目录所有数据均来自对 `app/` 目录 25,763 行 Python、`app/static/js/` 8,796 行 JS、`tests/` 2,199 行测试、`pyproject.toml`、`scripts/` 启动脚本的逐文件核查。

## 文档清单

| 编号 | 文件 | 内容 |
|---|---|---|
| 01 | [FUNCTIONAL_SPEC.md](./01_FUNCTIONAL_SPEC.md) | 功能说明书——基于源码重写的真实功能清单 |
| 02 | [IMPROVEMENT_ANALYSIS.md](./02_IMPROVEMENT_ANALYSIS.md) | 项目改进分析——按优先级排序的 30+ 改进项 |
| 03 | [PROJECT_EVALUATION.md](./03_PROJECT_EVALUATION.md) | 项目评估报告——问题清单、半成品清单、综合评分 |
| 04 | [TESTING_REPORT.md](./04_TESTING_REPORT.md) | 测试报告——134 测试用例的深度分析 |

## 关键发现摘要

### 致命问题（5 项）

1. **ModelScope API Key 全仓库泄露**——`ms-a300ec43-a4f3-49d2-9044-2fdbc269f3b9` 在 6 个文件中硬编码
2. **默认模型名 `Qwen/Qwen3.5-397B-A17B` 不存在**——Qwen 从未发布过这个型号，是 AI 幻觉
3. **FastAPI 应用零安全防护**——281 个 API 端点完全开放，无 CORS、无认证
4. **AI 工具完全无沙箱**——`run_python`/`run_shell`/`save_custom_tool` 等于任意代码执行
5. **`pip install -e .` 直接报错**——pyproject.toml 缺少 package discovery 配置

### 死代码（~500 行）

- `app/agent_loop.py`（321 行）——导入但 0 次调用
- `app/dspy_integration.py`（148 行）——导入但 0 次调用
- `app/complexity_tier.py`——业务逻辑被硬编码 stub 替代
- `app/main.py::_embed_for_rag`——定义但从未调用

### 测试覆盖

- 134 测试用例全部通过，但：
  - 55 个模块中 22 个完全无测试（40%）
  - 0 个 HTTP 集成测试
  - 60% 断言是"形状检查"，不验证具体值
  - 1 个测试占总耗时 94%（30 秒卡顿）
  - 所有 LLM 依赖功能无测试

### 综合评分

**3.8 / 10**（按 Joel Test 仅得 1/12）

项目处于**早期原型阶段**，功能广度优秀但工程基础严重不足，**不可用于任何形式的生产部署**。
