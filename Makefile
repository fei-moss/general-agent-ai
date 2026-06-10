# Agent Execution Platform 常用命令
# 用法:make <target>

PY ?= python
PIP ?= pip
APP_MODULE ?= app.api.main:app
CELERY_APP ?= app.tasks.celery_app:celery_app

.PHONY: help up down install run-api run-worker test seed

help:
	@echo "可用目标:"
	@echo "  make up         启动 postgres + redis (docker compose)"
	@echo "  make down       停止并移除容器"
	@echo "  make install    安装 Python 依赖"
	@echo "  make run-api    启动 FastAPI(uvicorn)"
	@echo "  make run-worker 启动 Celery worker(全部队列)"
	@echo "  make test       运行 pytest"
	@echo "  make seed       初始化建表 + 灌入示例数据"

up:
	docker compose up -d

down:
	docker compose down

install:
	$(PIP) install -r requirements.txt

run-api:
	uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

run-worker:
	celery -A $(CELERY_APP) worker -l info -Q q.intent,q.rag,q.tool,q.llm

test:
	pytest -q

seed:
	$(PY) scripts/seed.py
