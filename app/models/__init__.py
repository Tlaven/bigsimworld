"""数据模型初始化。

显式调用 `init_db()` 建表；模块导入本身不建库/建表（无导入副作用）。
"""

from .table import Base, engine


def init_db():
    """确保所有表存在：先导入各模型模块以注册 metadata，再统一建表。"""
    from . import snapshot  # noqa: F401  导入以注册 snapshots 表
    Base.metadata.create_all(engine)
