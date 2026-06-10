"""工具路由与执行。

ToolRouter 负责:
- route: 从计划步骤(plan_step)解析出目标 Tool。
- execute: 校验参数(按 tool.parameters JSON Schema 子集)、施加超时与
  指数退避重试、隔离单工具异常(失败不抛到整个 run),并通过可注入的
  回调写入 ToolCallLog。

为避免引入额外依赖,内置一个仅覆盖 type/required/properties 的最小 JSON
Schema 校验器,满足内置工具的参数约束。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from app.core.enums import TaskStatus
from app.core.ids import _new_id
from app.core.interfaces import Tool
from app.core.logging import get_logger
from app.core.models import ToolCallLog
from app.tools.base import ToolRegistry, registry

logger = get_logger(__name__)

# 写日志回调签名:接收一条已构造好的 ToolCallLog
ToolCallLogSink = Callable[[ToolCallLog], Awaitable[None]]

_DEFAULT_TOOL_TIMEOUT_S = 15.0
_DEFAULT_MAX_RETRIES = 1
_DEFAULT_BASE_DELAY_S = 0.3
_TOOL_LOG_PREFIX = "tcl_"

# JSON Schema type -> Python 类型(用于最小校验)
_JSON_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


class ToolValidationError(ValueError):
    """工具参数校验失败。"""


def validate_args(schema: dict[str, Any], args: dict[str, Any]) -> None:
    """按 JSON Schema 子集校验参数,失败抛 ToolValidationError。"""
    if not isinstance(args, dict):
        raise ToolValidationError("args 必须是 dict")
    for field in schema.get("required", []):
        if field not in args:
            raise ToolValidationError(f"缺少必填参数: {field}")
    props = schema.get("properties", {})
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            continue
        _check_type(key, value, spec)


def _check_type(key: str, value: Any, spec: dict[str, Any]) -> None:
    """校验单个字段类型(含 boolean 与 integer 的区分)。"""
    expected = spec.get("type")
    if expected is None:
        return
    py_types = _JSON_TYPE_MAP.get(expected)
    if py_types is None:
        return
    # bool 是 int 的子类,integer/number 不应接受 bool
    if expected in ("integer", "number") and isinstance(value, bool):
        raise ToolValidationError(f"参数 {key} 类型应为 {expected}")
    if not isinstance(value, py_types):
        raise ToolValidationError(f"参数 {key} 类型应为 {expected}")


def _extract_step(plan_step: Any) -> tuple[str, dict[str, Any]]:
    """从计划步骤中解析 (tool_name, args)。

    支持:dict({"tool"/"name", "args"/"arguments"})、(name, args) 二元组、
    纯字符串(视作 tool 名,无参数)。
    """
    if isinstance(plan_step, str):
        return plan_step, {}
    if isinstance(plan_step, (tuple, list)) and len(plan_step) == 2:
        name, args = plan_step
        return str(name), dict(args or {})
    if isinstance(plan_step, dict):
        name = plan_step.get("tool") or plan_step.get("name")
        args = plan_step.get("args") or plan_step.get("arguments") or {}
        if not name:
            raise ToolValidationError("plan_step 缺少 tool/name 字段")
        return str(name), dict(args)
    raise ToolValidationError(f"无法解析 plan_step: {type(plan_step).__name__}")


class ToolRouter:
    """工具路由器:解析、执行、带韧性与审计落库。"""

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        *,
        log_sink: ToolCallLogSink | None = None,
        timeout_s: float = _DEFAULT_TOOL_TIMEOUT_S,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay_s: float = _DEFAULT_BASE_DELAY_S,
    ) -> None:
        """初始化路由器。

        参数:
            tool_registry: 工具注册表,默认使用全局 registry。
            log_sink: 写 ToolCallLog 的异步回调(依赖注入);None 表示不落库。
            timeout_s/max_retries/base_delay_s: 韧性参数。
        """
        self._registry = tool_registry or registry
        self._log_sink = log_sink
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s

    def route(self, plan_step: Any) -> Tool:
        """从计划步骤解析出目标 Tool,未找到抛 KeyError。"""
        name, _ = _extract_step(plan_step)
        return self._registry.require(name)

    async def execute(
        self,
        tool: Tool,
        args: dict[str, Any],
        *,
        agent_run_id: str = "",
    ) -> dict[str, Any]:
        """执行工具,做参数校验/超时/重试/错误隔离,并写审计日志。

        无论成功或失败都返回结构化 dict(失败时含 ok=False/error),
        不向上抛异常,保证单工具失败不拖垮整个 run。
        """
        started = time.perf_counter()
        try:
            validate_args(tool.parameters, args)
        except ToolValidationError as exc:
            return await self._finalize(
                tool, args, agent_run_id, started, error=str(exc)
            )
        result, error = await self._run_with_retries(tool, args)
        return await self._finalize(
            tool, args, agent_run_id, started, result=result, error=error
        )

    async def _run_with_retries(
        self, tool: Tool, args: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """带超时与指数退避重试地运行工具。"""
        last_error: str | None = None
        for attempt in range(self._max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool.run(args), timeout=self._timeout_s
                )
                return result, None
            except asyncio.TimeoutError:
                last_error = f"工具 {tool.name} 执行超时(>{self._timeout_s}s)"
            except Exception as exc:  # noqa: BLE001 - 错误隔离
                last_error = f"工具 {tool.name} 执行异常: {exc}"
            await self._sleep_before_retry(tool.name, attempt, last_error)
        return None, last_error

    async def _sleep_before_retry(
        self, tool_name: str, attempt: int, error: str | None
    ) -> None:
        """重试前退避等待并记录日志。"""
        if attempt < self._max_retries:
            delay = self._base_delay_s * (2**attempt)
            logger.warning(
                "工具 %s 第 %d 次失败,%.2fs 后重试: %s",
                tool_name,
                attempt + 1,
                delay,
                error,
            )
            await asyncio.sleep(delay)
        else:
            logger.error("工具 %s 重试耗尽: %s", tool_name, error)

    async def _finalize(
        self,
        tool: Tool,
        args: dict[str, Any],
        agent_run_id: str,
        started: float,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """组装返回结果、写审计日志,并返回结构化结果。"""
        latency_ms = int((time.perf_counter() - started) * 1000)
        status = TaskStatus.ERROR if error else TaskStatus.DONE
        await self._write_log(
            tool.name, args, result, error, latency_ms, status, agent_run_id
        )
        if error:
            return {"ok": False, "tool": tool.name, "error": error}
        return {"ok": True, "tool": tool.name, "result": result}

    async def _write_log(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any] | None,
        error: str | None,
        latency_ms: int,
        status: TaskStatus,
        agent_run_id: str,
    ) -> None:
        """通过注入的 sink 写 ToolCallLog;sink 自身异常被隔离。"""
        if self._log_sink is None:
            return
        log = ToolCallLog(
            id=_new_id(_TOOL_LOG_PREFIX),
            agent_run_id=agent_run_id,
            tool_name=tool_name,
            arguments=args,
            result=result if error is None else {"error": error},
            latency_ms=latency_ms,
            status=status,
        )
        try:
            await self._log_sink(log)
        except Exception as exc:  # noqa: BLE001 - 审计失败不影响主流程
            logger.error("写 ToolCallLog 失败(已忽略): %s", exc)
