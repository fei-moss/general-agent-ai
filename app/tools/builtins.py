"""内置工具集合。

提供三个零外部依赖、确定性可演示的工具,并在模块导入时注册到全局 registry:

- CalculatorTool: 基于 ast 的安全四则/幂运算求值,严禁任意代码执行。
- ClockTool: 返回当前时间(UTC 与本地,ISO 8601 + Unix 时间戳)。
- MockWebSearchTool: 返回与 query 绑定的确定性假搜索结果。
"""

from __future__ import annotations

import ast
import hashlib
import operator
from datetime import datetime, timezone
from typing import Any, Callable

from app.tools.base import registry

# 允许的二元运算符 -> 实现
_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
# 允许的一元运算符
_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
# 幂运算指数上限,防止 10**10**10 这类资源耗尽攻击
_MAX_POW_EXPONENT = 1000


def _eval_node(node: ast.AST) -> float:
    """递归求值 AST 节点,仅允许数字常量与白名单运算符。"""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            raise ValueError("仅支持数字常量")
        return node.value
    if isinstance(node, ast.BinOp):
        return _eval_binop(node)
    if isinstance(node, ast.UnaryOp):
        return _eval_unaryop(node)
    raise ValueError(f"不支持的表达式元素: {type(node).__name__}")


def _eval_binop(node: ast.BinOp) -> float:
    """求值二元运算节点。"""
    op = _BIN_OPS.get(type(node.op))
    if op is None:
        raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
    left, right = _eval_node(node.left), _eval_node(node.right)
    if isinstance(node.op, ast.Pow) and abs(right) > _MAX_POW_EXPONENT:
        raise ValueError("幂运算指数过大,已拒绝")
    return op(left, right)


def _eval_unaryop(node: ast.UnaryOp) -> float:
    """求值一元运算节点。"""
    op = _UNARY_OPS.get(type(node.op))
    if op is None:
        raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
    return op(_eval_node(node.operand))


def safe_eval(expression: str) -> float:
    """安全求值数学表达式,禁止任意代码执行。"""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression 必须是非空字符串")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"表达式语法错误: {exc.msg}") from exc
    return _eval_node(tree)


class CalculatorTool:
    """安全计算器:支持 + - * / // % ** 与括号、负号。"""

    @property
    def name(self) -> str:
        """工具名称。"""
        return "calculator"

    @property
    def description(self) -> str:
        """工具描述。"""
        return "对数学表达式求值,支持加减乘除、取模、整除、幂与括号。"

    @property
    def parameters(self) -> dict[str, Any]:
        """参数 JSON Schema。"""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "待求值的数学表达式,如 '2 * (3 + 4)'。",
                }
            },
            "required": ["expression"],
        }

    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        """求值并返回结果;表达式非法时返回错误信息。"""
        expression = args.get("expression", "")
        try:
            value = safe_eval(expression)
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            return {"ok": False, "error": str(exc), "expression": expression}
        return {"ok": True, "expression": expression, "result": value}


class ClockTool:
    """时钟工具:返回当前时间。"""

    @property
    def name(self) -> str:
        """工具名称。"""
        return "clock"

    @property
    def description(self) -> str:
        """工具描述。"""
        return "返回当前的 UTC 时间与本地时间(ISO 8601 与 Unix 时间戳)。"

    @property
    def parameters(self) -> dict[str, Any]:
        """参数 JSON Schema(无参数)。"""
        return {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        """返回当前 UTC 与本地时间信息。"""
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now().astimezone()
        return {
            "ok": True,
            "utc_iso": now_utc.isoformat(),
            "local_iso": now_local.isoformat(),
            "unix_ts": now_utc.timestamp(),
        }


# 单条假结果数量上限
_MOCK_RESULT_COUNT = 3


class MockWebSearchTool:
    """离线 Web 搜索:对同一 query 返回确定性假结果。"""

    @property
    def name(self) -> str:
        """工具名称。"""
        return "web_search"

    @property
    def description(self) -> str:
        """工具描述。"""
        return "离线模拟的网页搜索,返回与查询绑定的确定性结果列表(演示用)。"

    @property
    def parameters(self) -> dict[str, Any]:
        """参数 JSON Schema。"""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量,默认 3。",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    async def run(self, args: dict[str, Any]) -> dict[str, Any]:
        """根据 query 生成确定性假结果。"""
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "query 不能为空"}
        top_k = int(args.get("top_k", _MOCK_RESULT_COUNT))
        top_k = max(1, min(top_k, 10))
        results = [_make_mock_result(query, i) for i in range(top_k)]
        return {"ok": True, "query": query, "results": results}


def _make_mock_result(query: str, index: int) -> dict[str, str]:
    """基于 query 与序号生成确定性的单条假结果。"""
    digest = hashlib.sha256(f"{query}:{index}".encode("utf-8")).hexdigest()[:8]
    return {
        "title": f"关于「{query}」的参考资料 #{index + 1}",
        "url": f"https://example.com/{digest}",
        "snippet": (
            f"这是针对「{query}」的第 {index + 1} 条离线模拟搜索结果,"
            "仅用于演示检索-工具链路。"
        ),
    }


def register_builtins(override: bool = True) -> None:
    """将内置工具注册到全局 registry(默认覆盖,便于重复导入/测试)。"""
    for tool in (CalculatorTool(), ClockTool(), MockWebSearchTool()):
        registry.register(tool, override=override)


# 导入即注册,保证运行时拿到的 registry 已含内置工具
register_builtins()
