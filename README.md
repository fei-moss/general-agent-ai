# Agent Execution Platform

一句话概述:这是一个**异步化的 Agent 执行平台**——客户端提交请求后 API 立即返回 `agent_run_id`(HTTP 202),真正的 **agentic 推理**(由 [PydanticAI](https://ai.pydantic.dev/) 驱动,LLM 在 loop 中自主决定检索知识库 / 调用工具 / 生成回答)在后台 Celery Worker 中执行,执行过程通过 SSE / WebSocket 以事件流实时推送;原生支持多 provider(claude / openai / qwen / gemini),内置零依赖 mock 模型(FunctionModel)与 HashEmbedder,**无需任何 API key 即可端到端跑通**。

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 快速启动(5 步)

```bash
# 1. 准备环境变量(默认 LLM_PROVIDER=mock,零外部依赖)
cp .env.example .env

# 2. 安装依赖
make install

# 3. 启动 Postgres + Redis(端口 55432 / 55379)
make up

# 4. 启动 API(uvicorn)
make run-api

# 5. 另开终端启动 Worker(消费全部队列)
make run-worker
```

## 端到端 demo(curl)

```bash
# 提交一次运行,得到 202 + agent_run_id / stream_url
curl -s -X POST http://localhost:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"message": "你好,介绍一下这个平台", "stream": true}'

# 用返回的 stream_url 订阅 SSE 事件流(逐 token 推送)
curl -N http://localhost:8000/runs/<agent_run_id>/events

# 查询运行状态
curl -s http://localhost:8000/runs/<agent_run_id>
```

## 目录结构

```
app/
  core/      共享契约:enums / events / schemas / models / interfaces / config / ids / logging
  api/       FastAPI 应用与路由(routers/)
  runtime/   Agent 执行编排:PydanticAI agentic loop(agent_factory 选 model + 注册工具,orchestrator 跑 loop 并把事件流映射到 EventBus)
  rag/       Embedder(HashEmbedder)与 VectorStore(numpy 余弦)
  tools/     工具实现(Tool 接口),经 @agent.tool 暴露给 LLM 自主调用
  llm/       遗留的 LLM Provider 直连实现(Mock / OpenAI 兼容 / Anthropic / LiteLLM);运行时已改由 PydanticAI 原生 model 接管
  tasks/     Celery app 与异步任务
  bus/       事件总线(Redis Pub/Sub)
  db/        init.sql 与 async session
docs/        架构文档
scripts/     seed 等脚本
tests/       pytest 用例
```

## Harness 与测试

本项目的 AI-first 治理入口:

- `AGENTS.md`: 项目级 AI 工作规则; `CLAUDE.md` 指向同一文件, 避免不同工具规则分叉。
- `.ai-boundaries.yml`: AI 可编辑、需审批、禁止触碰路径边界。
- `docs/harness-workflows.md`: 动态 Harness workflow 说明。
- `docs/harness-workflows.json`: 可机器校验的 workflow manifest。
- `docs/harness-source-analysis.md`: P0/P1 文章阅读、冲突裁决和采用记录。
- `docs/harness-virtual-requirements.json`: 虚拟需求集合, 用于校验 workflow 覆盖是否落地。
- `docs/specifications/` 与 `docs/implementation-plans/`: 行为规格和实施计划, 非模板文件必须声明 `Workflow Class: HARNESS-*`。

```bash
make test
make check-harness-workflows
make verify-release
```
