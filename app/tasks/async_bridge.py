"""Celery 同步上下文 <-> asyncio 桥接。

Celery worker 任务体是同步函数,而 orchestrator / 事件总线 / DB 全部为
async。这里提供在同步上下文中安全运行协程的入口。

设计要点:
- 每次调用创建并销毁一个事件循环,避免跨任务复用循环导致的状态污染
  (worker 子进程内并发由 Celery 控制,单任务串行执行其协程)。
- 若当前线程已存在运行中的事件循环(异常场景,如被嵌入到 async 框架),
  退化为在新线程中运行,避免 ``asyncio.run`` 报错。
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_coro(coro: Coroutine[Any, Any, T]) -> T:
    """在同步上下文中运行一个协程并返回其结果。

    优先使用 ``asyncio.run``;若检测到当前线程已有运行中的事件循环,
    则在独立线程中新建循环运行,以保证可用性。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 正常路径:当前无运行中的循环
        return asyncio.run(coro)
    # 退化路径:已在事件循环内,转交独立线程执行
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()
