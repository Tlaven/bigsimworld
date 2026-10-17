"""质量侧 `transfer`（N2-6）：财富守恒 / 清算 / 投递 / 生命周期折叠 / 配额豁免。

规格见 `docs/modules/interaction-channel.md` N2-6 与
`docs/decisions/adr-005-transfer-quality-side.md`。

口径：`W = 全局 measure + Σ 簇 mini + Σ 池 + Σ yearly_inherited + Σ 窗口 wealth`
（每项 `count×桶中心`）。`transfer` / 清算 / 投递 / 折叠必须 **W-中性**。

注意：本文件的夹具把族群建好后**先记录 W0 再做 transfer**——`coarsen` 自身会把
精确财富折成桶中心（≤ w/2 量化差，ADR-005 方案 H 的已知边界），不属于 transfer 的账。
"""

import math
import random

import pytest

from app.core.measure.channel import (
    RULES,
    Intent,
    InteractionChannel,
    Match,
)
from app.core.measure.cluster import TickContext
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import Measure, measure_from_payload, measure_to_payload
from app.core.measure.space import StateSpace
from app.core.measure.transitions import (
    FULL_FLOWS,
    _shift_age_wealth,
    deliver_transfer_pool,
)
from app.core.measure.window import WindowEngine
from bench.world import make_characters


# ------------------------------------------------------------------ 夹具

def _engine(capacity=100, window=20, n=400, seed=1, rng=None, flows=FULL_FLOWS):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=flows)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True, rng=rng)


def _coarse_cluster(engine, members=0):
    """造一个 **coarse** 簇（默认空 mini，便于放已知桶）。"""
    mgr = engine.resolution
    ids = list(engine.window.characters)[:members]
    cluster = mgr.store.create("family", set(ids))
    mgr.store.coarsen(cluster.id)
    return cluster


def _ctx(engine, tick=0):
    return TickContext(tick=tick, measure=engine.measure_engine.measure, rng=engine.rng)


def _mini(cluster):
    return cluster.state["engine"].measure


def _cell(engine, wealth, age=30, gender=0, marital=0):
    return engine.window.space.encode(age, gender, wealth, marital)


def _put(cluster, engine, wealth, count, age=30, gender=0, marital=0):
    mini = _mini(cluster)
    mini.add(_cell(engine, wealth, age, gender, marital), count)
    cluster.state["size"] = mini.total()
    return mini


def _world_wealth(engine):
    """全世界财富（含池）——见 N2-6 不变量 9。"""
    total = engine.measure_engine.measure.wealth()
    for cluster in engine.resolution.store.clusters.values():
        engine_obj = cluster.state.get("engine")
        if engine_obj is not None:
            total += engine_obj.measure.wealth()
    total += sum(c.wealth for c in engine.window.characters.values())
    return total


def _first_character(engine):
    return sorted(engine.window.characters.values(), key=lambda c: c.id)[0]


def _r2c(engine, cluster, character, amount, kind="gift", op="transfer"):
    return Intent(op=op, kind=kind, origin=("character", character.id),
                  scope=("cluster", cluster.id), match=Match(),
                  payload={"amount": amount})


def _c2r(engine, cluster, amount, kind="grant", match=None):
    return Intent(op="transfer", kind=kind, origin=("cluster", cluster.id),
                  scope=("window",), match=match or Match(age=(0, 120)),
                  payload={"amount": amount})


# ------------------------------------------------------------------ R→C

def test_r2c_debits_exactly_and_credits_pool():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    mini = _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 3000.0

    w0 = _world_wealth(engine)
    mass0 = mini.mass()
    channel = engine.resolution.channel
    channel.submit(_r2c(engine, cluster, r, 2500.0))
    report = channel.run(_ctx(engine))

    assert report["transferred"] == pytest.approx(2500.0)
    assert report["made"] == 0
    assert r.wealth == pytest.approx(500.0)
    assert mini.transfer_pool == pytest.approx(2500.0)
    assert mini.mass() == pytest.approx(mass0)          # 分布不动
    assert _world_wealth(engine) == pytest.approx(w0)   # W 中性

    record = channel.ledger[-1]
    assert (record.status, record.op) == ("ok", "transfer")
    assert record.wealth_delta == pytest.approx(-2500.0)
    assert record.pool_after == pytest.approx(2500.0)
    assert record.delta_mass == 0.0
    assert record.new_id is None                        # 不产生身份
    assert channel._reserved == 0


def test_r2c_insufficient_funds_is_zero_side_effect():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 100.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)

    channel = engine.resolution.channel
    channel.submit(_r2c(engine, cluster, r, 200.0))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:insufficient_funds": 1}
    assert r.wealth == pytest.approx(100.0)
    assert mini.transfer_pool == pytest.approx(0.0)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_r2c_rejects_match():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 1000.0
    channel = engine.resolution.channel
    intent = Intent(op="transfer", kind="gift", origin=("character", r.id),
                    scope=("cluster", cluster.id), match=Match(age=(20, 40)),
                    payload={"amount": 100.0})
    channel.submit(intent)
    assert channel.run(_ctx(engine))["by_status"] == {"dropped:unsupported_match": 1}
    assert r.wealth == pytest.approx(1000.0)


# ------------------------------------------------------------------ C→R

def test_c2r_pays_exactly_from_pool():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    mini = _put(cluster, engine, wealth=10, count=1.0)
    mini.transfer_pool = 2500.0
    recipient = _first_character(engine)
    recipient.wealth = 0.0
    w0 = _world_wealth(engine)

    channel = engine.resolution.channel
    channel.submit(_c2r(engine, cluster, 500.0))
    report = channel.run(_ctx(engine))

    assert report["transferred"] == pytest.approx(500.0)
    assert mini.transfer_pool == pytest.approx(2000.0)
    assert recipient.wealth == pytest.approx(500.0)
    assert _world_wealth(engine) == pytest.approx(w0)
    record = channel.ledger[-1]
    assert record.op == "transfer"
    assert record.wealth_delta == pytest.approx(500.0)
    assert record.pool_after == pytest.approx(2000.0)
    assert record.note == ""                            # 没清算就不写 note


def test_c2r_liquidates_count_one_bucket_first():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=3.0)         # 3 人 @ 10500
    _put(cluster, engine, wealth=5, count=1.0)          # 1 人 @ 5500
    recipient = _first_character(engine)
    recipient.wealth = 0.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)
    mass0 = mini.mass()

    channel = engine.resolution.channel
    channel.submit(_c2r(engine, cluster, 500.0))
    channel.run(_ctx(engine))

    # 人数最少优先 ⇒ 命中 count=1 的桶：5 → 4（一步 = 1000），超取 500 留池
    assert mini.counts[_cell(engine, 5)] == pytest.approx(0.0)
    assert mini.counts[_cell(engine, 4)] == pytest.approx(1.0)
    assert mini.counts[_cell(engine, 10)] == pytest.approx(3.0)
    assert mini.transfer_pool == pytest.approx(500.0)
    assert mass0 - mini.mass() == pytest.approx(1000.0)
    assert recipient.wealth == pytest.approx(500.0)
    assert _world_wealth(engine) == pytest.approx(w0)
    assert channel.ledger[-1].note.startswith("liquidated:")


def test_c2r_overdraw_bound_is_largest_liquidated_count():
    """反例夹具：超取上界 = 被清算桶中**最大 count × w**（不是"最小 count"）。"""
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=5, count=1.0)          # 先被命中
    _put(cluster, engine, wealth=6, count=3.0)          # 后命中，count 更大
    recipient = _first_character(engine)
    recipient.wealth = 0.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)
    mass0 = mini.mass()

    channel = engine.resolution.channel
    channel.submit(_c2r(engine, cluster, 6000.0))
    channel.run(_ctx(engine))

    # 计划：5 → 0（5 步 = 5000），6 → 5（1 步 = 3000）⇒ 实付 8000、超取 2000
    assert mini.transfer_pool == pytest.approx(2000.0)
    assert mass0 - mini.mass() == pytest.approx(8000.0)
    assert recipient.wealth == pytest.approx(6000.0)
    assert _world_wealth(engine) == pytest.approx(w0)
    # 升序应用：桶 5（原 count=1）被清空，桶 6 的 3 人移到桶 5
    assert mini.counts[_cell(engine, 6)] == pytest.approx(0.0)
    assert mini.counts[_cell(engine, 5)] == pytest.approx(3.0)
    assert mini.counts[_cell(engine, 0)] == pytest.approx(1.0)


def test_c2r_illiquid_when_only_bucket_zero():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=0, count=4.0)          # mass 2000（桶中心 500）
    recipient = _first_character(engine)
    recipient.wealth = 0.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)

    channel = engine.resolution.channel
    channel.submit(_c2r(engine, cluster, 500.0))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:illiquid": 1}    # 总额够，但无桶可下移
    assert mini.transfer_pool == pytest.approx(0.0)
    assert mini.counts[_cell(engine, 0)] == pytest.approx(4.0)
    assert recipient.wealth == pytest.approx(0.0)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_c2r_insufficient_funds_is_zero_side_effect():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=1, count=1.0)          # mass 1500
    recipient = _first_character(engine)
    recipient.wealth = 0.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)

    channel = engine.resolution.channel
    channel.submit(_c2r(engine, cluster, 999999.0))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:insufficient_funds": 1}
    assert mini.counts[_cell(engine, 1)] == pytest.approx(1.0)
    assert mini.transfer_pool == pytest.approx(0.0)
    assert _world_wealth(engine) == pytest.approx(w0)


# ------------------------------------------------------------------ 金额 / op 校验

@pytest.mark.parametrize("amount", [0.0, -5.0, float("nan"), float("inf"), "100", None, True])
def test_bad_amount_is_dropped_without_side_effect(amount):
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 1000.0
    mini = _mini(cluster)
    w0 = _world_wealth(engine)

    channel = engine.resolution.channel
    channel.submit(Intent(op="transfer", kind="gift", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(),
                          payload={"amount": amount}))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:bad_amount": 1}
    assert r.wealth == pytest.approx(1000.0)
    assert mini.transfer_pool == pytest.approx(0.0)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_unknown_op_is_dropped():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    r = _first_character(engine)
    channel = engine.resolution.channel
    channel.submit(Intent(op="teleport", kind="x", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(),
                          payload={"amount": 1.0}))
    assert channel.run(_ctx(engine))["by_status"] == {"dropped:bad_op": 1}


def test_duplicate_intent_is_recorded_not_silently_swallowed():
    """不变量 8：去重（含 `op`）也要留记录；bind 与 transfer 不互撞。"""
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 5000.0
    channel = engine.resolution.channel
    channel.submit(_r2c(engine, cluster, r, 100.0, kind="dup"))
    channel.submit(_r2c(engine, cluster, r, 100.0, kind="dup"))
    report = channel.run(_ctx(engine))

    assert report["by_status"].get("dropped:duplicate") == 1
    assert report["transferred"] == pytest.approx(100.0)    # 只执行第一条


def test_dedupe_key_includes_op():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 5000.0
    channel = engine.resolution.channel
    channel.submit(_r2c(engine, cluster, r, 100.0, kind="same"))
    # 同 (origin, kind, scope) 但 op 不同 ⇒ 不得被去重掉
    channel.submit(Intent(op="bind", kind="same", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(30, 30),
                                                                    gender=0)))
    report = channel.run(_ctx(engine))

    assert report["by_status"].get("dropped:duplicate", 0) == 0


# ------------------------------------------------------------------ 配额 / headroom 豁免

def test_transfer_bypasses_identity_quota_and_window_headroom():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=10, count=1.0)
    r = _first_character(engine)
    r.wealth = 1e6
    channel = engine.resolution.channel
    channel.cap_per_cluster = 0
    channel.cap_per_tick = 0
    engine.window.capacity = len(engine.window.characters)   # 无 headroom

    channel.submit(_r2c(engine, cluster, r, 100.0))
    report = channel.run(_ctx(engine))

    assert report["transferred"] == pytest.approx(100.0)
    assert not any(s.startswith("dropped:quota") or s == "dropped:window"
                   for s in report["by_status"])


# ------------------------------------------------------------------ 投递（settle）

def test_deliver_pool_poorest_first():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=1, count=1.0)
    _put(cluster, engine, wealth=10, count=1.0)
    mini = _mini(cluster)
    mini.transfer_pool = 2500.0
    w0 = _world_wealth(engine)
    mass0 = mini.mass()

    delivered = deliver_transfer_pool(mini)

    assert delivered == pytest.approx(2000.0)
    assert mini.transfer_pool == pytest.approx(500.0)
    assert mini.counts[_cell(engine, 3)] == pytest.approx(1.0)
    assert mini.counts[_cell(engine, 1)] == pytest.approx(0.0)
    assert mini.mass() - mass0 == pytest.approx(2000.0)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_deliver_applies_descending_to_avoid_cascade():
    """相邻目标夹具：`3@9 + 1@10`、池 4500 ⇒ 降序应用实付 4000；升序会级联并造负池。"""
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=9, count=3.0)
    _put(cluster, engine, wealth=10, count=1.0)
    mini = _mini(cluster)
    mini.transfer_pool = 4500.0
    w0 = _world_wealth(engine)
    mass0 = mini.mass()

    delivered = deliver_transfer_pool(mini)

    assert delivered == pytest.approx(4000.0)
    assert mini.transfer_pool == pytest.approx(500.0)
    assert mini.counts[_cell(engine, 10)] == pytest.approx(3.0)   # 原 9 的 3 人
    assert mini.counts[_cell(engine, 11)] == pytest.approx(1.0)   # 原 10 的 1 人
    assert mini.mass() - mass0 == pytest.approx(4000.0)
    assert _world_wealth(engine) == pytest.approx(w0)


def test_deliver_skips_fractional_buckets():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=5, count=0.5)          # 残留质量，不是整人桶
    mini = _mini(cluster)
    mini.transfer_pool = 1000.0
    assert deliver_transfer_pool(mini) == pytest.approx(0.0)
    assert mini.transfer_pool == pytest.approx(1000.0)


def test_settle_runs_on_year_boundary():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    _put(cluster, engine, wealth=1, count=1.0)
    mini = _mini(cluster)
    mini.transfer_pool = 1000.0
    mgr = engine.resolution
    mgr._settle_transfer_pools(359)
    assert mini.transfer_pool == pytest.approx(1000.0)   # 非年界：不动
    mgr._settle_transfer_pools(360)
    assert mini.transfer_pool == pytest.approx(0.0)      # 年界：投递


def test_shift_age_wealth_refuses_to_cross_bucket_zero():
    """下界守卫（正确性前提）：`steps < -wealth_bucket` 必须不支付、且不串桶。"""
    space = StateSpace()
    measure = Measure(space)
    index = space.encode(30, 0, 1, 0)
    measure.add(index, 1.0)
    assert _shift_age_wealth(measure, space, [index], -5) == pytest.approx(0.0)
    assert measure.counts[index] == pytest.approx(1.0)
    assert measure.total() == pytest.approx(1.0)


# ------------------------------------------------------------------ 生命周期折叠

def test_dissolve_folds_pools_into_global():
    engine = _engine()
    cluster = _coarse_cluster(engine)
    mini = _put(cluster, engine, wealth=10, count=2.0)
    mini.transfer_pool = 700.0
    mini.yearly_inherited[5] = 300.0
    global_measure = engine.measure_engine.measure
    pool0 = global_measure.transfer_pool
    inh0 = global_measure.yearly_inherited.get(5, 0.0)

    assert engine.resolution.store.dissolve(cluster.id) is True

    assert global_measure.transfer_pool == pytest.approx(pool0 + 700.0)
    assert global_measure.yearly_inherited[5] == pytest.approx(inh0 + 300.0)
    assert mini.transfer_pool == pytest.approx(0.0)      # 源侧清空，防双折


def test_merge_folds_pools_of_both_clusters():
    engine = _engine()
    a = _coarse_cluster(engine)
    b = _coarse_cluster(engine)
    _put(a, engine, wealth=10, count=1.0)
    _put(b, engine, wealth=10, count=1.0)
    _mini(a).transfer_pool = 100.0
    _mini(b).transfer_pool = 250.0
    _mini(b).yearly_inherited[7] = 50.0

    merged = engine.resolution.store.merge(a.id, b.id)

    assert merged == a.id
    assert _mini(a).transfer_pool == pytest.approx(350.0)
    assert _mini(a).yearly_inherited[7] == pytest.approx(50.0)
    assert _mini(b).transfer_pool == pytest.approx(0.0)


def test_merge_resolved_fast_path_keeps_leftover_pools():
    """resolved+resolved 快路径会 `del` 掉 b：b 的 mini 残留与池必须先折走。"""
    engine = _engine()
    a = _coarse_cluster(engine, members=2)
    b = _coarse_cluster(engine, members=2)
    _put(a, engine, wealth=10, count=3.0)
    _put(b, engine, wealth=10, count=3.0)
    engine.resolution.store.materialize(a.id)        # level=1（保留 mini 残量）
    engine.resolution.store.materialize(b.id)
    _mini(a).transfer_pool = 10.0
    _mini(b).transfer_pool = 40.0

    global_measure = engine.measure_engine.measure
    global_pool0 = global_measure.transfer_pool
    engine.resolution.store.merge(a.id, b.id)

    assert a.id in engine.resolution.store.clusters
    assert b.id not in engine.resolution.store.clusters
    assert _mini(a).transfer_pool == pytest.approx(50.0)
    assert global_measure.transfer_pool == pytest.approx(global_pool0)   # 没漏到全局


def test_split_folds_leftover_pools_into_global():
    engine = _engine()
    cluster = _coarse_cluster(engine, members=3)
    _put(cluster, engine, wealth=10, count=3.0)
    engine.resolution.store.materialize(cluster.id)
    _mini(cluster).transfer_pool = 500.0
    global_measure = engine.measure_engine.measure
    pool0 = global_measure.transfer_pool
    kept = sorted(engine.resolution.store.clusters[cluster.id].member_ids)[:1]

    engine.resolution.store.split(cluster.id, [kept])

    assert cluster.id not in engine.resolution.store.clusters
    assert global_measure.transfer_pool == pytest.approx(pool0 + 500.0)


# ------------------------------------------------------------------ 快照 / 确定性

def test_snapshot_roundtrip_keeps_pools():
    space = StateSpace()
    measure = Measure(space)
    measure.add(space.encode(30, 0, 10, 0), 2.0)
    measure.transfer_pool = 1234.5
    measure.yearly_inherited[6] = 250.25

    restored = measure_from_payload(measure_to_payload(measure), space)

    assert restored.total() == pytest.approx(2.0)
    assert restored.transfer_pool == pytest.approx(1234.5)
    assert restored.yearly_inherited[6] == pytest.approx(250.25)


def test_snapshot_old_payload_without_pools_defaults_to_zero():
    space = StateSpace()
    payload = {"size": space.size, "cells": [[space.encode(30, 0, 10, 0), 1.0]]}
    restored = measure_from_payload(payload, space)
    assert restored.transfer_pool == pytest.approx(0.0)
    assert restored.yearly_inherited == {}


def test_transfer_sequence_is_deterministic():
    def run(seed):
        engine = _engine(rng=random.Random(seed))
        cluster = _coarse_cluster(engine)
        _put(cluster, engine, wealth=10, count=3.0)
        _put(cluster, engine, wealth=5, count=1.0)
        r = _first_character(engine)
        r.wealth = 5000.0
        channel = engine.resolution.channel
        channel.submit(_r2c(engine, cluster, r, 2500.0))
        channel.submit(_c2r(engine, cluster, 5000.0, kind="grant2"))
        channel.submit(_r2c(engine, cluster, r, 900.0, kind="gift3"))
        channel.run(_ctx(engine, tick=360))
        deliver_transfer_pool(_mini(cluster))
        return [(x.status, x.op, x.wealth_delta, x.pool_after, x.note)
                for x in channel.ledger]

    assert run(7) == run(7)


# ------------------------------------------------------------------ 长跑（接进真实 step 循环）

class _TransferRule:
    """测试用探针：R→C 与 C→R 交替发起；**不发 bind**（`emits_bind=False`）。"""

    def __init__(self, name, every=3):
        self.name = name
        self.every = every
        self.emits_bind = False

    def offers(self, context):
        if self.every <= 0 or context.tick % self.every:
            return []
        coarse = sorted((c for c in context.store.clusters.values() if c.level == 0),
                        key=lambda c: c.id)
        chars = sorted(context.window.characters.values(), key=lambda c: c.id)
        if not coarse or not chars:
            return []
        cluster = coarse[0]
        rich = max(chars, key=lambda c: c.wealth)
        out = [Intent(op="transfer", kind="gift", origin=("character", rich.id),
                      scope=("cluster", cluster.id), match=Match(),
                      payload={"amount": 300.0})]
        if _mini_of(context, cluster.id).transfer_pool > 0.0:
            # 金额刻意大于小额赠予 ⇒ 池不够时走清算（否则清算路径在长跑里是空的）
            out.append(Intent(op="transfer", kind="grant", origin=("cluster", cluster.id),
                              scope=("window",), match=Match(age=(0, 120)),
                              payload={"amount": 2000.0}))
        return out


def _mini_of(context, cluster_id):
    """从只读上下文里取 mini（规则视角：`store.clusters[cid].state["engine"]`）。"""
    return context.store.clusters[cluster_id].state["engine"].measure


@pytest.fixture
def transfer_rule(monkeypatch):
    monkeypatch.setitem(RULES, "probe_transfer", _TransferRule("probe_transfer", every=3))


def test_transfer_ops_are_wealth_neutral_in_long_run(transfer_rule):
    random.seed(11)
    engine = _engine(capacity=120, window=60, n=800, seed=3, rng=random.Random(11))
    mgr = engine.resolution
    mgr.gamma = 1.0
    cluster = _coarse_cluster(engine, members=6)
    _put(cluster, engine, wealth=10, count=200.0)
    _put(cluster, engine, wealth=5, count=100.0, age=31)
    engine.window.characters[_first_character(engine).id].wealth = 1e6
    mgr.attention[cluster.id] = 0.2            # 保持 coarse、不被回收

    channel = mgr.channel
    worst = {"dev": 0.0, "calls": 0}
    original_run = channel.run

    def checked(ctx):
        before = _world_wealth(engine)
        result = original_run(ctx)
        dev = _world_wealth(engine) - before
        worst["calls"] += 1
        if abs(dev) > abs(worst["dev"]):
            worst["dev"] = dev
        assert abs(dev) < 1e-6, f"channel.run 泄漏财富 {dev:+.6g}"
        return result

    channel.run = checked
    for _ in range(120):
        engine.step()

    ok = [r for r in channel.ledger if r.status == "ok" and r.op == "transfer"]
    assert ok, "探针规则没跑出任何 transfer ⇒ 这个测试是空的"
    assert any(r.wealth_delta < 0 for r in ok), "没有 R→C"
    assert any(r.wealth_delta > 0 for r in ok), "没有 C→R"
    assert any(r.note.startswith("liquidated:") for r in ok), "长跑里没触发清算 ⇒ 清算路径没被验到"
    assert worst["calls"] > 0
    assert not any(r.status.startswith("dropped:error") for r in channel.ledger)
    assert channel.pool_total() >= 0.0
