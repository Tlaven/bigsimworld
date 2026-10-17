"""第一条交互规则：跨分辨率婚配（MarriageRule，ADR-007 / L3 N2-7）。

验收要点：规则**只发意图**（不碰边/分布）、`bind` 落地配偶边、人头守恒、
不重复婚配、计数加权抽样确定性、分数桶不计权重、默认关（未注册）。
"""

import random

import pytest

import app.core.measure.channel as channel_mod
from app.core.measure.channel import RULES, ChannelContext, Intent, Match
from app.core.measure.cluster import TickContext
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.rules import MarriageRule
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def _engine(capacity=100, window=20, n=400, seed=1, rng=None):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True, rng=rng)


def _ctx(engine, tick=0):
    return TickContext(tick=tick, measure=engine.measure_engine.measure, rng=engine.rng)


def _cctx(engine, rng=None):
    return ChannelContext(tick=0, window=engine.window,
                          store=engine.resolution.store, rng=rng or engine.rng)


def _cluster(engine):
    mgr = engine.resolution
    cluster = mgr.store.create("family", set())
    mgr.store.coarsen(cluster.id)
    return cluster


def _mini(cluster):
    return cluster.state["engine"].measure


def _put(cluster, engine, wealth=10, count=1.0, age=30, marital=0):
    mini = _mini(cluster)
    mini.add(engine.window.space.encode(age, 0, wealth, marital), count)
    cluster.state["size"] = mini.total()
    return mini


class _SeqRng:
    """确定性假 rng：按给定序列返回 `random()`；用尽后返回 0.0。"""

    def __init__(self, values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0) if self.values else 0.0


def _submit_and_run(engine, rule, rng=None):
    channel = engine.resolution.channel
    for intent in rule.offers(_cctx(engine, rng=rng)):
        channel.submit(intent)
    return channel.run(_ctx(engine, tick=0))


# ------------------------------------------------------------------ 建边 + 守恒

def test_rule_builds_spouse_edge_and_conserves_headcount(monkeypatch):
    engine = _engine()
    cluster = _cluster(engine)
    _put(cluster, engine, count=10.0)
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)

    pop0 = engine.population()
    window0 = len(engine.window.characters)
    report = _submit_and_run(engine, rule)

    oks = [r for r in engine.resolution.channel.ledger if r.status == "ok"]
    assert oks, "规则没有产出任何成功绑定"
    assert all(r.kind == "spouse" for r in oks)
    assert report["made"] == len(oks)
    assert engine.population() == pytest.approx(pop0)          # 人头守恒
    assert len(engine.window.characters) == window0 + len(oks)
    for record in oks:
        head = engine.window.characters[record.new_id]
        initiator = engine.window.characters[record.initiator_id]
        assert head in initiator.relationships["spouse"]
        assert initiator in head.relationships["spouse"]
    assert cluster.id in engine.resolution.channel.recently_active  # 宽限期登记


def test_rule_only_emits_intents_no_side_effects(monkeypatch):
    """规则**只发意图**：调用 `offers` 不得改边、不得改分布。"""
    engine = _engine()
    cluster = _cluster(engine)
    mini = _put(cluster, engine, count=10.0)
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)

    counts0 = dict(mini.counts.items())
    window0 = len(engine.window.characters)
    edge0 = sum(len(c.relationships.get("spouse", []))
                for c in engine.window.characters.values())

    intents = rule.offers(_cctx(engine))

    assert intents, "rate=1 且房源充足时应产出意图"
    assert all(isinstance(i, Intent) and i.op == "bind" and i.kind == "spouse"
               and i.match == Match(marital=0, age=(18, 59)) for i in intents)
    assert dict(mini.counts.items()) == counts0            # 分布未动
    assert len(engine.window.characters) == window0        # 窗口未动
    assert sum(len(c.relationships.get("spouse", []))
               for c in engine.window.characters.values()) == edge0   # 边未动


# ------------------------------------------------------------------ 不重复婚配

def test_married_single_is_not_offered_again(monkeypatch):
    engine = _engine()
    cluster = _cluster(engine)
    _put(cluster, engine, count=10.0)
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)

    oks_before = 0
    for _ in range(2):                       # 连跑两次：第二次不得重复嫁已嫁的人
        _submit_and_run(engine, rule)
        oks = [r for r in engine.resolution.channel.ledger if r.status == "ok"]
        assert len(oks) >= oks_before
        oks_before = len(oks)

    married = {c.id for c in engine.window.characters.values()
               if c.relationships.get("spouse")}
    assert married, "需要至少一桩跨婚配"
    origins = {i.origin[1] for i in rule.offers(_cctx(engine))}
    assert not (origins & married), "已婚后仍被发起婚配"


def test_no_eligible_mass_means_no_intents(monkeypatch):
    engine = _engine()
    cluster = _cluster(engine)
    _put(cluster, engine, count=5.0, marital=1)          # 只有已婚桶
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)
    assert rule.offers(_cctx(engine)) == []
    assert _submit_and_run(engine, rule)["by_status"] == {}


def test_fractional_bucket_is_not_counted_as_weight(monkeypatch):
    engine = _engine()
    cluster = _cluster(engine)
    _put(cluster, engine, count=0.5)                      # 分数残留，不是整人
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)
    assert rule.offers(_cctx(engine)) == []


# ------------------------------------------------------------------ 抽样确定性

def test_weighted_target_sampling_is_deterministic(monkeypatch):
    engine = _engine(window=1)                            # 只物化 1 个角色，便于隔离
    only = next(iter(engine.window.characters.values()))
    only.age = 30
    only.relationships["spouse"] = []
    c1 = _cluster(engine)
    c2 = _cluster(engine)
    _put(c1, engine, count=3.0)
    _put(c2, engine, count=7.0)
    assert c1.id < c2.id
    rule = MarriageRule(rate=1.0)
    monkeypatch.setitem(RULES, rule.name, rule)

    # 概率骰 0.5（<1 ⇒ 发起）+ 抽样骰：roll*10 < 3 ⇒ c1，>=3 ⇒ c2
    low = rule.offers(_cctx(engine, rng=_SeqRng([0.5, 0.29])))
    high = rule.offers(_cctx(engine, rng=_SeqRng([0.5, 0.31])))

    assert [i.scope[1] for i in low] == [c1.id]
    assert [i.scope[1] for i in high] == [c2.id]


def test_rule_is_deterministic_in_long_run(monkeypatch):
    rule = MarriageRule(rate=0.05)
    monkeypatch.setitem(RULES, rule.name, rule)

    def run():
        random.seed(13)
        engine = _engine(capacity=80, window=40, n=600, seed=4, rng=random.Random(13))
        cluster = _cluster(engine)
        _put(cluster, engine, count=200.0)
        engine.resolution.attention[cluster.id] = 0.2
        engine.resolution.gamma = 1.0
        for _ in range(60):
            engine.step()
        return [(r.tick, r.status, r.kind, r.origin, r.new_id)
                for r in engine.resolution.channel.ledger]

    first = run()
    second = run()
    assert first == second
    assert any(x[1] == "ok" for x in first), "长跑没有产出婚配 ⇒ 确定性断言是空的"


# ------------------------------------------------------------------ 默认关

def test_rule_is_not_registered_by_default():
    assert "cross_marriage" not in channel_mod.RULES
