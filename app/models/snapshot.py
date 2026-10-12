"""测度快照的持久化（替代"每个体一行"）：一次存下整份分布 + 物化窗口。"""

from sqlalchemy import Column, Integer, JSON

from app.models import crud
from app.models.table import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_time = Column(Integer, nullable=False)
    measure = Column(JSON, nullable=False)   # {"size":..., "cells": [[index,count],...]}
    window = Column(JSON, nullable=False)     # 物化个体列表


def save_snapshot(measure_payload, simulation_time, window=None):
    with crud.get_session() as session:
        row = Snapshot(
            simulation_time=simulation_time,
            measure=measure_payload,
            window=window or [],
        )
        session.add(row)
        session.commit()
        return row.id


def load_latest():
    """读最新快照；表不存在或为空时返回 None（调用方走新建世界）。"""
    try:
        with crud.get_session() as session:
            row = session.query(Snapshot).order_by(Snapshot.id.desc()).first()
            if row is None:
                return None
            return {
                "simulation_time": row.simulation_time,
                "measure": row.measure,
                "window": row.window,
            }
    except Exception:
        return None
