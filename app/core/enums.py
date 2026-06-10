"""核心枚举定义。

集中定义系统中所有跨模块共享的枚举类型,所有枚举均继承 str,
便于直接序列化为 JSON 与存入数据库。
"""

from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    """Agent 运行(AgentRun)的生命周期状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    """单个后台任务(TaskState)的执行状态。"""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class MessageRole(str, Enum):
    """会话消息的角色。"""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


class IntentType(str, Enum):
    """意图识别结果类型,决定后续执行路径。"""

    CHITCHAT = "CHITCHAT"
    KNOWLEDGE_QA = "KNOWLEDGE_QA"
    TOOL_USE = "TOOL_USE"
    MULTI_STEP = "MULTI_STEP"
