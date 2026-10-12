import os

from sqlalchemy import create_engine, Column, Integer, String, Index, JSON
from sqlalchemy.orm import declarative_base

# 数据库路径：可用 SIM_DB_PATH 覆盖（默认工作目录下 db.sqlite3）
DB_PATH = os.environ.get("SIM_DB_PATH", "db.sqlite3")

# 创建数据库引擎
engine = create_engine(f"sqlite:///{DB_PATH}")
Base = declarative_base()


class Table(Base):
    __tablename__ = 'characters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=4), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(length=6), nullable=True)
    xing = Column(String(length=2), nullable=True)
    DOB = Column(String(length=10), nullable=True)
    wealth = Column(Integer, nullable=True)
    relationships = Column(JSON, nullable=True, default={})  # 使用 JSON 类型
    start_time = Column(Integer, nullable=True)
    end_time = Column(Integer, nullable=True)
    status = Column(String(length=10), default='active')
    pedometer = Column(JSON, nullable=True, default={})
    relation_record = Column(JSON, nullable=True, default={})

    __table_args__ = (
        Index('idx_status_end_time', 'status', 'end_time'),
    )
