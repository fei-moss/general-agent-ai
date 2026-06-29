"""工具注册表。

ToolRegistry 维护 name -> Tool 的内存映射,提供注册、查找与导出工具
JSON Schema 列表(供 LLM 做工具选择)的能力。模块级单例 registry
供内置工具与运行时统一使用。
"""

from __future__ import annotations

from typing import Any

from app.core.interfaces import Tool
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表:按名称注册、查找与列出工具描述。"""

    def __init__(self) -> None:
        """初始化空注册表。"""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, *, override: bool = False) -> None:
        """注册一个工具。

        参数:
            tool: 实现 Tool 协议的实例。
            override: 同名是否允许覆盖,默认 False(重复注册抛错)。
        """
        name = tool.name
        if not name:
            raise ValueError("工具必须提供非空 name")
        if name in self._tools and not override:
            raise ValueError(f"工具 {name!r} 已注册,如需替换请传 override=True")
        self._tools[name] = tool
        logger.info("已注册工具: %s", name)

    def unregister(self, name: str) -> None:
        """注销一个工具(不存在则忽略)。"""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """按名称查找工具,不存在返回 None。"""
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        """按名称获取工具,不存在抛出 KeyError。"""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"未找到工具: {name!r}")
        return tool

    def names(self) -> list[str]:
        """返回所有已注册工具名称。"""
        return list(self._tools.keys())

    def list_schemas(self) -> list[dict[str, Any]]:
        """导出所有工具的 JSON Schema 描述(供 LLM function-calling)。"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]

    def clear(self) -> None:
        """清空注册表(主要用于测试隔离)。"""
        self._tools.clear()


# 模块级全局注册表单例
registry = ToolRegistry()
