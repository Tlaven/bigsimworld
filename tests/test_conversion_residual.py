"""分辨率折算的财富残差（ADR-006 / L4 N2-5）：符号账 + 全局 W 严格。

口径：`W = Σ_测度 [count×桶中心 + transfer_pool + conversion_residual + Σ yearly_inherited] + Σ 窗口 wealth`。
三个**损失点**记残差（`dematerialize` / `coarsen` / `unbind`）；四个**精确点**不记
（`materialize` / `materialize_sample` / `ClusterStore.materialize` / `bind`+`extract`）。
"""

import random

import pytest

from app.core.measure.channel import Intent, Match
from app.core.measure.cluster import TickContext
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import (
    Measure,
    fold_pools,
    measure_from_payload,
    measure_to_payload,
    record_conversion,
)
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def _engine(capacity=100, window=20, n=400, seed=1, rng=None):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True, rng=rng)


def _ctx(engine, tick=0):
    return TickContext(tick=tick, measure=engine.measure_engine.measure, rng=engine.rng)


def _world_wealth(engine):
    total = engine.measure_engine.measure.wealth()
    for cluster in engine.resolution.store.clusters.values():
        obj = cluster.state.get("engine")
        if obj is not None:
            total += obj.measure.wealth()
    total += sum(c.wealth for c in engine.window.characters.values())
    return total


def _cluster(engine, members=0):
    mgr = engine.resolution
    ids = list(engine.window.characters)[:members]
    cluster = mgr.store.create("family", set(ids))
    mgr.store.coarsen(cluster.id)
    return cluster


def _mini(cluster):
    return cluster.state["engine"].measure


# ------------------------------------------------------------------ 唯一写法的算术

def test_record_conversion_sign_and_magnitude():
    space = StateSpace()
    measure = Measure(space)
    record_conversion(measure, space, 1537.2)       # bucket 1, center 1500
    record_conversion(measure, space, 999.0)        # bucket 0, center 500
    record_conversion(measure, space, 100.0)        # bucket 0, center 500
    assert measure.conversion_residual == pytest.approx(37.2 + 499.0 - 400.0)


def test_wealth_includes_conversion_residual():
    space = StateSpace()
    measure = Measure(space)
    measure.add(space.encode(30, 0, 10, 0), 1.0)    # mass 10500
    measure.conversion_residual = -250.0
    assert measure.wealth() == pytest.approx(10500.0 - 250.0)
    # 可花费量不是 wealth()：残差不可花（N2-6）
    assert measure.mass() + measure.transfer_pool == pytest.approx(10500.0)


# ------------------------------------------------------------------ 三个损失点

def test_dematerialize_records_residual_and_keeps_w_exact():
    engine = _engine()
    character = sorted(engine.window.characters.values(), key=lambda c: c.id)[0]
    character.wealth = 1537.2
    w0 = _world_wealth(engine)
    measure = engine.measure_engine.measure
    r0 = measure.conversion_residual

    assert engine.window.dematerialize(character.id) is True

    assert measure.conversion_residual == pytest.approx(r0 + 37.2)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_coarsen_records_residual_per_member_and_keeps_w_exact():
    engine = _engine()
    ids = list(engine.window.characters)[:3]
    for cid, wealth in zip(ids, (1537.2, 100.0, 999.0)):
        engine.window.characters[cid].wealth = wealth
    w0 = _world_wealth(engine)

    cluster = _cluster(engine, members=3)

    expected = (1537.2 - 1500.0) + (100.0 - 500.0) + (999.0 - 500.0)
    assert _mini(cluster).conversion_residual == pytest.approx(expected)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_unbind_records_residual_and_keeps_w_exact():
    engine = _engine()
    cluster = _cluster(engine)
    space = engine.window.space
    _mini(cluster).add(space.encode(30, 0, 1, 0), 1.0)      # bucket 1，center 1500
    cluster.state["size"] = _mini(cluster).total()
    r = sorted(engine.window.characters.values(), key=lambda c: c.id)[0]
    channel = engine.resolution.channel
    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    channel.run(_ctx(engine))
    new_id = [x.new_id for x in channel.ledger if x.status == "ok"][-1]
    engine.window.characters[new_id].wealth = 1537.2        # 造一个非桶中心的精确值

    w0 = _world_wealth(engine)
    mini = _mini(cluster)
    assert channel.unbind(new_id, tick=0) is True

    assert mini.conversion_residual == pytest.approx(37.2)
    assert _world_wealth(engine) == pytest.approx(w0)


# ------------------------------------------------------------------ 精确点不记

def test_materialize_is_exact_and_records_nothing():
    engine = _engine()
    measure = engine.measure_engine.measure
    space = engine.window.space
    measure.add(space.encode(30, 0, 1, 0), 1.0)
    r0 = measure.conversion_residual
    w0 = _world_wealth(engine)

    cid = engine.window.materialize(30, 0, 1, 0)

    assert cid is not None
    assert engine.window.characters[cid].wealth == pytest.approx(space.wealth_value(1))
    assert measure.conversion_residual == pytest.approx(r0)     # 精确点：不记
    assert _world_wealth(engine) == pytest.approx(w0)


def test_materialize_sample_uses_bucket_center():
    engine = _engine(capacity=200, window=0)
    space = engine.window.space
    before = engine.measure_engine.measure.conversion_residual
    engine.window.materialize_sample(30)
    assert engine.window.characters
    for character in engine.window.characters.values():
        assert character.wealth == pytest.approx(space.wealth_value(space.wealth_bucket(character.wealth)))
    assert engine.measure_engine.measure.conversion_residual == pytest.approx(before)


def test_bind_is_exact_and_records_nothing():
    engine = _engine()
    cluster = _cluster(engine)
    space = engine.window.space
    _mini(cluster).add(space.encode(30, 0, 1, 0), 1.0)
    cluster.state["size"] = _mini(cluster).total()
    r = sorted(engine.window.characters.values(), key=lambda c: c.id)[0]
    channel = engine.resolution.channel
    w0 = _world_wealth(engine)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    channel.run(_ctx(engine))

    assert _mini(cluster).conversion_residual == pytest.approx(0.0)   # 精确点：不记
    assert _world_wealth(engine) == pytest.approx(w0)


# ------------------------------------------------------------------ 折叠 / 快照

def test_fold_pools_folds_residual_too():
    space = StateSpace()
    src, dst = Measure(space), Measure(space)
    src.conversion_residual = 123.4
    dst.conversion_residual = -3.4
    src.transfer_pool = 50.0
    src.yearly_inherited[5] = 10.0
    fold_pools(src, dst)
    assert dst.conversion_residual == pytest.approx(120.0)
    assert src.conversion_residual == pytest.approx(0.0)
    assert dst.transfer_pool == pytest.approx(50.0)
    assert dst.yearly_inherited[5] == pytest.approx(10.0)


def test_lifecycle_folds_residual_into_global_and_target():
    engine = _engine()
    a = _cluster(engine)
    b = _cluster(engine)
    _mini(a).transfer_pool = 0.0
    _mini(a).conversion_residual = 100.0
    _mini(b).conversion_residual = 25.0
    global_measure = engine.measure_engine.measure
    g0 = global_measure.conversion_residual

    engine.resolution.store.merge(a.id, b.id)
    assert _mini(a).conversion_residual == pytest.approx(125.0)

    assert engine.resolution.store.dissolve(a.id) is True
    assert global_measure.conversion_residual == pytest.approx(g0 + 125.0)


def test_snapshot_roundtrip_and_old_payload_default():
    space = StateSpace()
    measure = Measure(space)
    measure.add(space.encode(30, 0, 10, 0), 1.0)
    measure.conversion_residual = -37.5
    restored = measure_from_payload(measure_to_payload(measure), space)
    assert restored.conversion_residual == pytest.approx(-37.5)

    old = measure_from_payload({"size": space.size,
                                "cells": [[space.encode(30, 0, 10, 0), 1.0]]}, space)
    assert old.conversion_residual == pytest.approx(0.0)
    assert old.transfer_pool == pytest.approx(0.0)
