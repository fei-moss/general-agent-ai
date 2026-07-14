# Agent Execution Platform 常用命令
# 用法:make <target>

VENV ?= .venv
PY ?= $(VENV)/bin/python
PIP ?= $(PY) -m pip
APP_MODULE ?= app.api.main:app
CELERY_APP ?= app.tasks.celery_app:celery_app

.PHONY: help up down venv install run-api run-worker test seed check-harness-workflows chat-eval chat-eval-report chat-eval-live verify-release

help:
	@echo "可用目标:"
	@echo "  make up         启动 postgres + redis (docker compose)"
	@echo "  make down       停止并移除容器"
	@echo "  make venv       创建本地 Python 虚拟环境"
	@echo "  make install    安装 Python 依赖"
	@echo "  make run-api    启动 FastAPI(uvicorn)"
	@echo "  make run-worker 启动 Celery worker(全部队列)"
	@echo "  make test       运行 pytest"
	@echo "  make seed       初始化建表 + 灌入示例数据"
	@echo "  make check-harness-workflows 校验 Harness workflow manifest 与 spec/plan 绑定"
	@echo "  make chat-eval 运行 Ask this Agent 聊天效果 deterministic eval"
	@echo "  make chat-eval-report 生成 Ask this Agent 聊天效果 scorecard"
	@echo "  make chat-eval-live 对 DockerHost/API 执行可选 live eval 回放"
	@echo "  make verify-release 运行发布前 Harness 验证并写入 .artifacts/release"

up:
	docker compose up -d

down:
	docker compose down

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt

run-api:
	$(PY) -m uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

run-worker:
	$(PY) -m celery -A $(CELERY_APP) worker -l info -Q q.run,q.intent,q.rag,q.tool,q.llm,q.compose

test:
	$(PY) -m pytest -q

seed:
	$(PY) scripts/seed.py

check-harness-workflows:
	PY="$(PY)" scripts/check_harness_workflows.sh

chat-eval:
	$(PY) -m pytest tests/test_chat_behavior_eval.py tests/test_chat_eval_closure.py -q

chat-eval-report:
	$(PY) -m tests.chat_eval.scorecard --output .artifacts/release/chat_eval_scorecard.json --strict

chat-eval-live:
	@test -n "$$CHAT_EVAL_BASE_URL" || (echo "CHAT_EVAL_BASE_URL is required" >&2; exit 1)
	@test -n "$$CHAT_EVAL_MARKETPLACE_USER_ID" || (echo "CHAT_EVAL_MARKETPLACE_USER_ID is required" >&2; exit 1)
	@test -n "$$CHAT_EVAL_MARKETPLACE_WALLET" || (echo "CHAT_EVAL_MARKETPLACE_WALLET is required" >&2; exit 1)
	$(PY) -m tests.chat_eval.live_runner --base-url "$$CHAT_EVAL_BASE_URL" --marketplace-user-id "$$CHAT_EVAL_MARKETPLACE_USER_ID" --marketplace-wallet "$$CHAT_EVAL_MARKETPLACE_WALLET" --output .artifacts/release/chat_eval_live.json

verify-release:
	PY="$(PY)" scripts/verify_release.sh
