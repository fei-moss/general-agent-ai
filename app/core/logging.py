"""结构化 JSON 日志。

基于标准库 logging 实现 structlog 风格的 JSON 单行日志,支持通过
contextvar 注入 trace_id,使同一链路的日志可被串联检索。
"""

from __future__ import annotations

import contextvars
import json
import logging
import time
from typing import Any

# 当前链路的 trace_id,跨 await 边界传播
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)


def set_trace_id(trace_id: str | None) -> None:
    """绑定当前上下文的 trace_id,后续日志自动带上。"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str | None:
    """读取当前上下文的 trace_id。"""
    return _trace_id_var.get()


class JsonFormatter(logging.Formatter):
    """将日志记录序列化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        trace_id = get_trace_id()
        if trace_id:
            payload["trace_id"] = trace_id
        # 透传 extra 中的结构化字段
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """配置根 logger 输出 JSON 到标准输出。幂等可重复调用。"""
    root = logging.getLogger()
    root.setLevel(level.upper())
    # 清理旧 handler,避免重复输出
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(JsonFormatter())
    root.addHandler(stream)


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)


def log_with_fields(
    logger: logging.Logger, level: int, msg: str, **fields: Any
) -> None:
    """记录一条带结构化字段的日志。"""
    logger.log(level, msg, extra={"extra_fields": fields})
