"""集成适配层(薄胶水)。

各兄弟模块的真实实现与 app.runtime.deps 中声明的协作者契约在方法名/签名/
返回类型上存在差异。这里提供最小适配器,把真实实现包成 deps 契约的形状,
使 Orchestrator 的调用链闭合。适配器只做形状转换,不承载业务逻辑。
"""

from __future__ import annotations

from typing import Any

from app.core.enums import MessageRole, RunStatus
from app.core.ids import _new_id


class RetrieverAdapter:
    """把 app.rag.retriever.RAGRetriever 适配为 retrieve -> list[dict]。"""

    def __init__(self) -> None:
        from app.rag.retriever import RAGRetriever as RealRetriever

        self._impl = RealRetriever()

    async def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """调用真实检索器并把 RetrievalResult.chunks 摊平为 dict 列表。"""
        result = await self._impl.retrieve(query, top_k)
        chunks = getattr(result, "chunks", []) or []
        return [
            {
                "id": getattr(c, "doc_id", ""),
                "text": getattr(c, "text", ""),
                "score": getattr(c, "score", 0.0),
                "source": getattr(c, "meta", {}),
            }
            for c in chunks
        ]


# 工具自动选择的关键词启发式(planner 未显式指定 tool_name 时使用)
_TIME_HINTS = ("时间", "几点", "日期", "现在", "now", "time", "date", "clock")
_MATH_CHARS = set("0123456789+-*/%()")


def _infer_tool_name(query: str) -> str:
    """根据查询内容确定性地推断工具名。

    planner 对 TOOL_USE 默认不指定 tool_name(交由路由决策),这里用轻量规则
    选择:含数学符号 -> calculator;含时间词 -> clock;否则 -> web_search。
    """
    lowered = query.lower()
    has_digit = any(ch.isdigit() for ch in query)
    has_op = any(ch in _MATH_CHARS for ch in query if not ch.isdigit())
    if has_digit and has_op:
        return "calculator"
    if any(hint in lowered for hint in _TIME_HINTS):
        return "clock"
    return "web_search"


class ToolRouterAdapter:
    """把 app.tools.router.ToolRouter 适配为 route(query, tool_name) -> dict。

    真实 ToolRouter.route(plan_step) 仅解析出 Tool,执行在 execute()。
    这里组合两步:用 (tool_name, {"query": query}) 作为 plan_step 解析工具,
    再执行并把返回归一化为含 tool_name/result/status 的 dict。
    tool_name 缺失时用 _infer_tool_name 做确定性自动选择。
    """

    def __init__(self) -> None:
        # 触发内置工具注册到全局 registry(import 即注册),避免 ToolRouter
        # 因外部未导入 builtins 而拿到空注册表(KeyError: 未找到工具)。
        import app.tools.builtins  # noqa: F401
        from app.tools.router import ToolRouter as RealToolRouter

        self._impl = RealToolRouter()

    async def route(
        self, query: str, tool_name: str | None = None
    ) -> dict[str, Any]:
        """解析并执行工具,返回结构化结果。"""
        resolved = tool_name or _infer_tool_name(query)
        # calculator 期望 expression 参数,其余工具用 query。
        args = (
            {"expression": query}
            if resolved == "calculator"
            else {"query": query}
        )
        plan_step = {"tool": resolved, "args": args}
        tool = self._impl.route(plan_step)
        raw = await self._impl.execute(tool, args)
        ok = bool(raw.get("ok"))
        return {
            "tool_name": raw.get("tool", tool_name),
            "result": raw.get("result"),
            "status": "DONE" if ok else "ERROR",
            "error": raw.get("error"),
        }


class _SessionScopedRepo:
    """为仓储适配器提供按调用获取 AsyncSession 的能力。

    build_deps 可能传入 None;此时每次调用从全局 session 工厂开一个短事务,
    用完即关,避免持有跨任务的长连接。若外部注入了 session 则直接复用。
    """

    def __init__(self, session: Any | None) -> None:
        self._session = session

    def _session_ctx(self):
        """返回一个异步上下文管理器,产出可用的 AsyncSession。"""
        if self._session is not None:
            session = self._session

            class _Reuse:
                async def __aenter__(self_inner):
                    return session

                async def __aexit__(self_inner, *exc):
                    return False

            return _Reuse()
        from app.db.session import async_session_factory

        return async_session_factory()


class MessageRepoAdapter(_SessionScopedRepo):
    """适配 MessageRepository:add -> create,list_by_conversation 直透。"""

    async def list_by_conversation(
        self, conversation_id: str, limit: int
    ) -> list[Any]:
        """读取会话历史消息。"""
        from app.db.repositories import MessageRepository

        async with self._session_ctx() as session:
            repo = MessageRepository(session)
            return await repo.list_by_conversation(conversation_id, limit)

    async def add(
        self,
        conversation_id: str,
        role: Any,
        content: str,
        token_count: int = 0,
        meta: dict[str, Any] | None = None,
    ) -> Any:
        """新增消息(契约 add -> 真实 create,补一个 message_id)。"""
        from app.db.repositories import MessageRepository

        role_enum = role if isinstance(role, MessageRole) else MessageRole(role)
        async with self._session_ctx() as session:
            repo = MessageRepository(session)
            return await repo.create(
                message_id=_new_id("msg_"),
                conversation_id=conversation_id,
                role=role_enum,
                content=content,
                token_count=token_count,
                meta=meta,
            )


class RunRepoAdapter(_SessionScopedRepo):
    """适配 AgentRunRepository:mark_* -> update_status / set_plan。"""

    async def mark_running(
        self, agent_run_id: str, intent: Any | None = None
    ) -> None:
        """置运行中,可选写 intent。"""
        from app.db.repositories import AgentRunRepository

        async with self._session_ctx() as session:
            repo = AgentRunRepository(session)
            if intent is not None:
                await repo.set_intent(agent_run_id, intent)
            await repo.update_status(agent_run_id, RunStatus.RUNNING)

    async def set_plan(self, agent_run_id: str, plan: dict[str, Any]) -> None:
        """写入计划快照。"""
        from app.db.repositories import AgentRunRepository

        async with self._session_ctx() as session:
            repo = AgentRunRepository(session)
            await repo.set_plan(agent_run_id, plan)

    async def mark_succeeded(self, agent_run_id: str) -> None:
        """置成功。"""
        from app.db.repositories import AgentRunRepository

        async with self._session_ctx() as session:
            repo = AgentRunRepository(session)
            await repo.update_status(agent_run_id, RunStatus.SUCCEEDED)

    async def mark_failed(self, agent_run_id: str, error: str) -> None:
        """置失败并记录错误。"""
        from app.db.repositories import AgentRunRepository

        async with self._session_ctx() as session:
            repo = AgentRunRepository(session)
            await repo.update_status(
                agent_run_id, RunStatus.FAILED, error=error
            )
