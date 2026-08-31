# Agent Execution Platform 常用命令
# 用法:make <target>

VENV ?= .venv
PY ?= $(VENV)/bin/python
PIP ?= $(PY) -m pip
APP_MODULE ?= app.api.main:app
CELERY_APP ?= app.tasks.celery_app:celery_app
MARKETPLACE_QNA_BASE_URL ?=
MARKETPLACE_QNA_KNOWLEDGE_BASE_ID ?=
MARKETPLACE_QNA_INGESTION_SUMMARY ?= .artifacts/release/marketplace_qna_ingestion_summary.json
MARKETPLACE_QNA_AUDIT_OUTPUT ?= .artifacts/release/marketplace_qna_golden_query_audit.json
MARKETPLACE_QNA_PREFLIGHT_OUTPUT ?= .artifacts/release/marketplace_qna_gemini_preflight.json
MARKETPLACE_QNA_PROMPTFOO_OUTPUT ?= .artifacts/release/marketplace_qna_promptfoo_eval.json
MARKETPLACE_QNA_STATUS_OUTPUT ?= .artifacts/release/marketplace_qna_acceptance_status.json

.PHONY: help up down venv install run-api run-worker test seed check-spec-registry verify-change verify-candidate verify-suite chat-eval chat-eval-report chat-eval-live verify-release marketplace-qna-preflight marketplace-qna-local marketplace-qna-live marketplace-qna-final marketplace-qna-acceptance

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
	@echo "  make check-spec-registry 校验四类 Harness workflow 与新规格注册表"
	@echo "  make verify-change 校验相对 VERIFY_COMPARE_REF 的完整开发改动"
	@echo "  make chat-eval 运行 Ask this Agent 聊天效果 deterministic eval"
	@echo "  make chat-eval-report 生成 Ask this Agent 聊天效果 scorecard"
	@echo "  make chat-eval-live 对 DockerHost/API 执行可选 live eval 回放"
	@echo "  make verify-release 运行发布前 Harness 验证并写入 .artifacts/release"
	@echo "  make marketplace-qna-preflight 校验输入、摄取证据和本地契约"
	@echo "  make marketplace-qna-local 运行 Gemini preflight 和 150 条本地检索"
	@echo "  make marketplace-qna-live 运行 150 条线上检索和 20 条聊天"
	@echo "  make marketplace-qna-final 运行 release gate 和最终验收器"
	@echo "  make marketplace-qna-acceptance 按顺序运行完整 Marketplace QnA 验收"

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
	scripts/with_test_resources.sh -- python3 scripts/test_resource_env.py $(PY) -m pytest -q

seed:
	$(PY) scripts/seed.py

check-spec-registry:
	scripts/harnessctl.sh check spec-registry

verify-change:
	PY="$(PY)" harness/repository_verification.py verify change

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
	PY="$(PY)" harness/repository_verification.py verify release

marketplace-qna-preflight:
	@test -n "$$GEMINI_API_KEY" || (echo "GEMINI_API_KEY is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_BASE_URL)" || (echo "MARKETPLACE_QNA_BASE_URL is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" || (echo "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID is required" >&2; exit 1)
	@test -f "$(MARKETPLACE_QNA_INGESTION_SUMMARY)" || (echo "Marketplace QnA ingestion summary is required" >&2; exit 1)
	$(PY) tests/rag_eval/marketplace_qna_fixture_builder.py
	$(PY) -m tests.rag_eval.marketplace_qna_golden_query_audit --output "$(MARKETPLACE_QNA_AUDIT_OUTPUT)"
	$(PY) -m pytest -q tests/test_marketplace_qna_eval.py tests/test_rag_promptfoo_eval.py

marketplace-qna-local:
	@test -n "$$GEMINI_API_KEY" || (echo "GEMINI_API_KEY is required" >&2; exit 1)
	$(PY) -m tests.rag_eval.moss_gemini_preflight --output "$(MARKETPLACE_QNA_PREFLIGHT_OUTPUT)" --model gemini-embedding-2 --dimension 256
	PROMPTFOO_PYTHON=$(PY) npx --yes promptfoo@latest eval -c tests/rag_eval/marketplace_qna_promptfooconfig.yaml --no-cache --output "$(MARKETPLACE_QNA_PROMPTFOO_OUTPUT)"

marketplace-qna-live:
	@test -n "$(MARKETPLACE_QNA_BASE_URL)" || (echo "MARKETPLACE_QNA_BASE_URL is required" >&2; exit 1)
	@test -n "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" || (echo "MARKETPLACE_QNA_KNOWLEDGE_BASE_ID is required" >&2; exit 1)
	$(PY) -m tests.rag_eval.marketplace_qna_live_eval --base-url "$(MARKETPLACE_QNA_BASE_URL)" --knowledge-base-id "$(MARKETPLACE_QNA_KNOWLEDGE_BASE_ID)" --retrieval-workers 4 --chat-timeout-s 120

marketplace-qna-final:
	$(MAKE) verify-release
	$(PY) -m tests.rag_eval.marketplace_qna_acceptance_validator
	$(PY) -m tests.rag_eval.marketplace_qna_acceptance_status --output "$(MARKETPLACE_QNA_STATUS_OUTPUT)"

marketplace-qna-acceptance:
	$(MAKE) marketplace-qna-preflight
	$(MAKE) marketplace-qna-local
	$(MAKE) marketplace-qna-live
	$(MAKE) marketplace-qna-final

verify-candidate:
	PY="$(PY)" harness/repository_verification.py verify candidate

verify-suite:
	harness/suite_conformance.py gate
