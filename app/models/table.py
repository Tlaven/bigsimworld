from sqlalchemy import create_engine, Column, Integer, String, Index, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base

# 创建数据库引擎
engine = create_engine('sqlite:///db.sqlite3')
Base = declarative_base()

from sqlalchemy import JSON

class Table(Base):
    __tablename__ = 'characters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=4), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(length=6), nullable=True)
    xing = Column(String(length=2), nullable=True)
    property = Column(Integer, nullable=True)
    relationships = Column(JSON, nullable=True)  # 使用 JSON 类型
    start_time = Column(Integer, nullable=True)
    end_time = Column(Integer, nullable=True) 
    status = Column(String(length=10), default='active')
    
    __table_args__ = (
        Index('idx_status_end_time', 'status', 'end_time'),
        CheckConstraint('status = \'active\'', name='status_check')
    )


def create_table():
    Base.metadata.create_all(engine)
    print('Table created successfully.')
