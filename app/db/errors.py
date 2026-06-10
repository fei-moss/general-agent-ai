"""数据访问层领域错误。

将底层 SQLAlchemy 异常统一封装为业务可理解的领域错误,
避免上层耦合具体 ORM 实现细节。
"""

from __future__ import annotations


class RepositoryError(Exception):
    """数据访问层通用错误基类。"""


class EntityNotFoundError(RepositoryError):
    """按主键查询的实体不存在。"""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} not found: {entity_id}")


class DuplicateEntityError(RepositoryError):
    """违反唯一约束,实体已存在。"""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} already exists: {entity_id}")


class InvalidStatusTransitionError(RepositoryError):
    """非法的状态机流转。"""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"invalid status transition: {current} -> {target}")


class PersistenceError(RepositoryError):
    """读写数据库时发生的其他持久化错误。"""
