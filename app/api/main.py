"""FastAPI 应用工厂与 ASGI 入口。

create_app() 组装:lifespan 资源、三层中间件(trace/鉴权/限流)、CORS、
全部业务路由。模块级 app 供 uvicorn 以 app.api.main:app 加载。

中间件执行顺序(starlette 中后注册者先执行):
注册顺序 RateLimit -> Auth -> TraceId -> CORS,使运行时为 CORS -> TraceId
-> Auth -> RateLimit。CORS 必须在最外层,才能先处理浏览器 preflight,
并为鉴权/限流错误补齐跨域响应头。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.lifespan import lifespan
from app.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    TraceIdMiddleware,
)
from app.api.routers import chat, conversations, health, rag, runs, stream
from app.core.config import get_settings


def create_app() -> FastAPI:
    """构建并返回配置完整的 FastAPI 应用。"""
    settings = get_settings()
    app = FastAPI(
        title="General Agent AI",
        version="0.1.0",
        lifespan=lifespan,
    )
    _add_middleware(app)
    _add_cors(app)
    _add_routers(app)
    # 暴露端口配置供入口读取
    app.state.host = settings.app_host
    app.state.port = settings.app_port
    return app


def _add_cors(app: FastAPI) -> None:
    """启用宽松 CORS(demo 用,生产应收敛来源);需最后注册成为最外层。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _add_middleware(app: FastAPI) -> None:
    """按栈式语义注册三层中间件。"""
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(TraceIdMiddleware)


def _add_routers(app: FastAPI) -> None:
    """注册全部业务路由。"""
    app.include_router(health.router)
    app.include_router(conversations.router)
    app.include_router(chat.router)
    app.include_router(stream.router)
    app.include_router(runs.router)
    app.include_router(rag.router)


app = create_app()


def main() -> None:
    """uvicorn 编程式入口(python -m app.api.main)。"""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
