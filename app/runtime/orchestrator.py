"""Agent 编排核心(系统大脑,PydanticAI 驱动)。

AgentOrchestrator.run() 是单次 Agent 运行的异步主控:加载多轮历史 -> 启动
PydanticAI agentic loop(由 LLM 自主决定检索 / 调用工具 / 收尾)-> 把框架事件
流映射为本平台的 AgentEvent 并经 EventBus 广播 -> 落库 -> 收尾。

设计要点:
- 控制流由 LLM 在 loop 中自主决定,而非规则计划;工具与知识检索均以
  @agent.tool 暴露(见 app.runtime.agent_factory)。
- 对外契约保持不变:run() 签名、生命周期事件(RUN_STARTED/RUN_COMPLETED)、
  逐 token 的 TOKEN 事件、最终 assistant 落库,均与既有 tasks/api 层兼容。
- 韧性:任一阶段失败均尽力降级,保证总能给出一个 assistant 回答并把运行
  状态正确收敛;UsageLimits 提供轮数护栏,防止 loop 失控。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic_ai import (
    Agent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
)
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from app.core.enums import MessageRole, RunStatus
from app.core.events import AgentEvent, EventType
from app.core.logging import get_logger, log_with_fields, set_trace_id
from app.runtime.agent_factory import (
    TOOL_SEARCH_KNOWLEDGE,
    AgentDeps,
    build_agent,
    build_model,
)
from app.runtime.deps import RuntimeDeps

logger = get_logger(__name__)

# 读取多轮历史时的最大条数
_HISTORY_LIMIT = 20
# 事件 channel 前缀,与 bus 约定 run:{agent_run_id}
_CHANNEL_PREFIX = "run:"
# 顶层兜底文案
_FATAL_ANSWER = "抱歉,处理过程中发生了内部错误,请稍后重试。"
# 计划快照中记录的工具清单(供回放/观测)
_TOOL_NAMES = (TOOL_SEARCH_KNOWLEDGE, "calculator", "clock", "web_search")


class _EventEmitter:
    """单次运行内的事件发射器,负责 seq 自增与 channel 拼装。"""

    def __init__(self, bus: Any, agent_run_id: str, trace_id: str) -> None:
        self._bus = bus
        self._agent_run_id = agent_run_id
        self._trace_id = trace_id
        self._channel = f"{_CHANNEL_PREFIX}{agent_run_id}"
        self._seq = 0

    async def emit(
        self, type_: EventType, data: dict[str, Any] | None = None
    ) -> None:
        """构造并发布一条事件;发布失败仅记录,不中断主流程。"""
        self._seq += 1
        event = AgentEvent(
            agent_run_id=self._agent_run_id,
            trace_id=self._trace_id,
            type=type_,
            seq=self._seq,
            ts=time.time(),
            data=data or {},
        )
        try:
            await self._bus.publish(self._channel, event)
        except Exception as exc:  # 事件总线故障不应影响业务执行
            log_with_fields(
                logger,
                logging.WARNING,
                "event publish failed",
                event_type=type_.value,
                error=str(exc),
            )


async def run_orchestration(
    *,
    agent_run_id: str,
    conversation_id: str,
    trace_id: str,
    user_message: str,
    emit: Any = None,
) -> dict[str, Any]:
    """tasks 层集成入口(薄适配)。

    装配 RuntimeDeps、构造 AgentOrchestrator 并运行,把最终文本归一化为
    ``{"content", "intent"}`` dict。``emit`` 参数为兼容 tasks 契约而保留;
    AgentOrchestrator 通过自身注入的 event_bus 在同一频道发布事件,故此处不
    复用外部 emit,避免重复发射。
    """
    from app.runtime.deps import build_deps

    deps = build_deps()
    orchestrator = AgentOrchestrator(deps)
    answer = await orchestrator.run(
        agent_run_id=agent_run_id,
        conversation_id=conversation_id,
        trace_id=trace_id,
        user_message=user_message,
    )
    return {"content": answer, "intent": None}


class AgentOrchestrator:
    """编排器。依赖通过 RuntimeDeps 注入;PydanticAI Agent 在构造时装配。"""

    def __init__(
        self, deps: RuntimeDeps, agent: Agent[AgentDeps, str] | None = None
    ) -> None:
        """构造编排器。

        参数:
            deps: 运行依赖容器(检索器 / 工具路由 / 事件总线 / 仓储 / 配置)。
            agent: 可选注入的 PydanticAI Agent(测试用);缺省按配置构建。
        """
        self._deps = deps
        self._agent = agent or build_agent(build_model(deps.settings))

    async def run(
        self,
        agent_run_id: str,
        conversation_id: str,
        trace_id: str,
        user_message: str,
    ) -> str:
        """执行一次完整运行,返回最终 assistant 文本。"""
        set_trace_id(trace_id)
        emitter = _EventEmitter(self._deps.event_bus, agent_run_id, trace_id)
        await emitter.emit(EventType.RUN_STARTED, {"message": user_message})
        try:
            return await self._execute(
                agent_run_id, conversation_id, user_message, emitter
            )
        except Exception as exc:  # 顶层兜底,保证状态收敛为 FAILED
            return await self._handle_fatal(agent_run_id, emitter, exc)

    async def _execute(
        self,
        agent_run_id: str,
        conversation_id: str,
        user_message: str,
        emitter: _EventEmitter,
    ) -> str:
        """主控制流:历史 -> agentic loop -> 落库 -> 成功收尾。"""
        history = await self._load_history(conversation_id)
        await self._safe_run_repo("mark_running", agent_run_id, None)
        await self._persist_plan(agent_run_id)
        await emitter.emit(EventType.PLANNING_STARTED, {})

        answer = await self._run_agent(user_message, history, emitter)

        await emitter.emit(EventType.RESULT_COMPOSED, {"length": len(answer)})
        await self._persist_answer(conversation_id, answer)
        await self._safe_run_repo("mark_succeeded", agent_run_id)
        # 终止事件携带 status 与答案内容,供同步等待路径(stream=False)直接取用。
        await emitter.emit(
            EventType.RUN_COMPLETED,
            {"status": RunStatus.SUCCEEDED.value, "content": answer},
        )
        return answer

    async def _run_agent(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        emitter: _EventEmitter,
    ) -> str:
        """运行 PydanticAI agentic loop,映射事件流,返回最终文本。

        LLM 在 loop 中自主决定是否检索 / 调用工具;失败时降级为兜底文案,
        保证总有回答产出。
        """
        deps = AgentDeps(
            retriever=self._deps.retriever,
            tool_router=self._deps.tool_router,
            retrieval_top_k=self._deps.settings.retrieval_top_k,
        )
        limits = UsageLimits(request_limit=self._deps.settings.max_turns)
        message_history = _to_message_history(history)
        tokens: list[str] = []
        llm_started = False
        try:
            async with self._agent.iter(
                user_message,
                deps=deps,
                message_history=message_history or None,
                usage_limits=limits,
            ) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        llm_started = await self._handle_model_request(
                            node, run, emitter, tokens, llm_started
                        )
                    elif Agent.is_call_tools_node(node):
                        await self._handle_tool_calls(node, run, emitter)
            answer = (run.result.output if run.result else "") or "".join(
                tokens
            )
            return answer.strip() or self._empty_answer(user_message)
        except Exception as exc:
            await self._emit_error(emitter, "agent", exc)
            return "".join(tokens).strip() or self._empty_answer(user_message)

    async def _handle_model_request(
        self,
        node: Any,
        run: Any,
        emitter: _EventEmitter,
        tokens: list[str],
        llm_started: bool,
    ) -> bool:
        """处理模型请求节点:首次发 LLM_GENERATING,最终结果阶段流式 TOKEN。"""
        if not llm_started:
            await emitter.emit(EventType.LLM_GENERATING, {})
            llm_started = True
        async with node.stream(run.ctx) as request_stream:
            final_found = False
            async for event in request_stream:
                if isinstance(event, FinalResultEvent):
                    final_found = True
                    break
            if final_found:
                async for token in request_stream.stream_text(delta=True):
                    if token:
                        tokens.append(token)
                        await emitter.emit(EventType.TOKEN, {"token": token})
        return llm_started

    async def _handle_tool_calls(
        self, node: Any, run: Any, emitter: _EventEmitter
    ) -> None:
        """处理工具调用节点:把 LLM 的工具调用/结果映射为检索或工具事件。"""
        async with node.stream(run.ctx) as handle_stream:
            async for event in handle_stream:
                if isinstance(event, FunctionToolCallEvent):
                    await self._emit_tool_started(emitter, event)
                elif isinstance(event, FunctionToolResultEvent):
                    await self._emit_tool_finished(emitter, event)

    @staticmethod
    async def _emit_tool_started(
        emitter: _EventEmitter, event: FunctionToolCallEvent
    ) -> None:
        """工具调用开始:search_knowledge 映射为检索事件,其余为工具事件。"""
        name = event.part.tool_name
        if name == TOOL_SEARCH_KNOWLEDGE:
            query = ""
            args = event.part.args
            if isinstance(args, dict):
                query = str(args.get("query", ""))
            await emitter.emit(EventType.RETRIEVAL_STARTED, {"query": query})
        else:
            await emitter.emit(
                EventType.TOOL_CALL_STARTED, {"tool_name": name}
            )

    @staticmethod
    async def _emit_tool_finished(
        emitter: _EventEmitter, event: FunctionToolResultEvent
    ) -> None:
        """工具结果返回:对应发出检索完成或工具完成事件。"""
        # 新版用 event.part(ToolReturnPart),旧版用 event.result,做兼容回退。
        part = getattr(event, "part", None) or getattr(event, "result", None)
        name = getattr(part, "tool_name", None)
        if name == TOOL_SEARCH_KNOWLEDGE:
            await emitter.emit(EventType.RETRIEVAL_FINISHED, {})
        else:
            await emitter.emit(
                EventType.TOOL_CALL_FINISHED, {"tool_name": name}
            )

    @staticmethod
    def _empty_answer(user_message: str) -> str:
        """LLM 未产出任何内容时的兜底文案。"""
        return f"抱歉,我暂时无法生成关于「{user_message}」的回答。"

    async def _load_history(
        self, conversation_id: str
    ) -> list[dict[str, Any]]:
        """读取多轮历史并规范为 {role, content};失败降级为空。"""
        try:
            rows = await self._deps.message_repo.list_by_conversation(
                conversation_id, _HISTORY_LIMIT
            )
        except Exception as exc:
            log_with_fields(
                logger,
                logging.WARNING,
                "load history failed",
                conversation_id=conversation_id,
                error=str(exc),
            )
            return []
        return [self._row_to_msg(r) for r in rows]

    @staticmethod
    def _row_to_msg(row: Any) -> dict[str, Any]:
        """把 Message ORM 行转为 {role, content}。"""
        role = getattr(row, "role", MessageRole.USER)
        role_value = role.value if isinstance(role, MessageRole) else str(role)
        return {
            "role": role_value.lower(),
            "content": getattr(row, "content", ""),
        }

    async def _persist_plan(self, agent_run_id: str) -> None:
        """落库一份引擎快照(替代旧的规则计划),失败不阻断。"""
        plan = {"engine": "pydantic-ai", "tools": list(_TOOL_NAMES)}
        await self._safe_run_repo("set_plan", agent_run_id, plan)

    async def _persist_answer(
        self, conversation_id: str, answer: str
    ) -> None:
        """把 assistant 回答落库(失败仅记录,不影响返回)。"""
        try:
            await self._deps.message_repo.add(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=answer,
                token_count=len(answer),
            )
        except Exception as exc:
            log_with_fields(
                logger,
                logging.ERROR,
                "persist answer failed",
                conversation_id=conversation_id,
                error=str(exc),
            )

    async def _handle_fatal(
        self, agent_run_id: str, emitter: _EventEmitter, exc: Exception
    ) -> str:
        """顶层异常处理:发 ERROR、置 FAILED,返回兜底文案。"""
        await self._emit_error(emitter, "fatal", exc)
        await self._safe_run_repo("mark_failed", agent_run_id, str(exc))
        await emitter.emit(
            EventType.RUN_COMPLETED, {"status": RunStatus.FAILED.value}
        )
        return _FATAL_ANSWER

    @staticmethod
    async def _emit_error(
        emitter: _EventEmitter, stage: str, exc: Exception
    ) -> None:
        """发布一条 ERROR 事件并记录日志。"""
        log_with_fields(
            logger, logging.ERROR, "stage error", stage=stage, error=str(exc)
        )
        await emitter.emit(EventType.ERROR, {"stage": stage, "error": str(exc)})

    async def _safe_run_repo(self, method: str, *args: Any) -> None:
        """安全调用 run_repo 的状态更新方法,异常仅记录不抛出。"""
        try:
            await getattr(self._deps.run_repo, method)(*args)
        except Exception as exc:
            log_with_fields(
                logger,
                logging.WARNING,
                "run_repo call failed",
                method=method,
                error=str(exc),
            )


def _to_message_history(
    history: list[dict[str, Any]],
) -> list[ModelMessage]:
    """把 {role, content} 历史转为 PydanticAI message_history。

    user -> ModelRequest(UserPromptPart);assistant -> ModelResponse(TextPart);
    system 由 Agent 自带,这里忽略,空内容过滤。
    """
    out: list[ModelMessage] = []
    for item in history:
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        role = str(item.get("role", "user")).lower()
        if role == "assistant":
            out.append(ModelResponse(parts=[TextPart(content=content)]))
        elif role == "user":
            out.append(ModelRequest(parts=[UserPromptPart(content=content)]))
    return out
