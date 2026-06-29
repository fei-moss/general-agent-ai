"""运行 / 任务状态机定义与校验。

集中定义 RunStatus 与 TaskStatus 的合法流转图,供仓储层在更新状态前
做幂等校验:相同状态(自环)视为幂等放行,非法流转抛出领域错误。
"""

from __future__ import annotations

from app.core.enums import RunStatus, TaskStatus
from app.db.errors import InvalidStatusTransitionError

# AgentRun 合法流转:PENDING -> RUNNING -> (SUCCEEDED|FAILED);任意非终态可被 CANCELLED。
_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED}
    ),
    RunStatus.RUNNING: frozenset(
        {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
    ),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

# TaskState 合法流转:QUEUED -> RUNNING -> (DONE|ERROR);ERROR 可回到 QUEUED 以支持重试。
_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.ERROR}),
    TaskStatus.RUNNING: frozenset({TaskStatus.DONE, TaskStatus.ERROR}),
    TaskStatus.DONE: frozenset(),
    TaskStatus.ERROR: frozenset({TaskStatus.QUEUED, TaskStatus.RUNNING}),
}

_TERMINAL_RUN_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


def is_terminal_run_status(status: RunStatus) -> bool:
    """判断运行状态是否为终态(不可再流转)。"""
    return status in _TERMINAL_RUN_STATES


def assert_run_transition(current: RunStatus, target: RunStatus) -> None:
    """校验 AgentRun 状态流转合法性。

    自环(current == target)视为幂等,直接放行;否则必须在允许集合内,
    不合法则抛出 InvalidStatusTransitionError。
    """
    if current == target:
        return
    if target not in _RUN_TRANSITIONS.get(current, frozenset()):
        raise InvalidStatusTransitionError(current.value, target.value)


def assert_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    """校验 TaskState 状态流转合法性,规则同 assert_run_transition。"""
    if current == target:
        return
    if target not in _TASK_TRANSITIONS.get(current, frozenset()):
        raise InvalidStatusTransitionError(current.value, target.value)
