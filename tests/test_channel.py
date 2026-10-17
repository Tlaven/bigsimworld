"""交互通道（InteractionChannel）：守恒 / 可逆 / 配额 / 确定性 / 惰性。

验收手段（见 `docs/modules/interaction-channel.md` 与 `docs-templates/verifying-n2.md`）：

- **不变量 → property**：人头守恒、无幽灵、配额上界、寻址封闭恒成立；
- **approved scenario**：零规则惰性（通道"通电不做功"）；
- mutation：把 `ClusterStore.extract` 的 `-amount` 改成 `0.0`，本文件必须变红（见 L3 验收栏）。

**本期不做交互规则**（`RULES` 为空），也**不做 `transfer`**（质量侧，另有规格）。
"""

import random

import pytest

import app.core.measure.channel as channel_mod
from app.core.measure.channel import (
    RULES,
    Intent,
    InteractionChannel,
    Match,
    compile_match,
)
from app.core.measure.cluster import TickContext
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters

CELL_30M = None      # 惰性初始化（依赖 StateSpace）


def _engine(capacity=100, window=20, n=400, seed=1, rng=None):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True, rng=rng)


def _coarse_cluster(engine, members=5, count=1.0, cell=None):
    """造一个 **coarse** 簇，并往它的 mini 引擎里放一个**已知桶**（供 Match 命中）。"""
    mgr = engine.resolution
    ids = list(engine.window.characters)[:members]
    cluster = mgr.store.create("family", set(ids))
    mgr.store.coarsen(cluster.id)
    space = engine.window.space
    cell = space.encode(30, 0, 10, 0) if cell is None else cell
    mini = cluster.state["engine"].measure
    mini.add(cell, count)
    cluster.state["size"] = mini.total()
    return cluster, cell


def _ctx(engine, tick=0):
    return TickContext(tick=tick, measure=engine.measure_engine.measure, rng=engine.rng)


def _mini(cluster):
    return cluster.state["engine"].measure


def _last_ok(channel):
    return [r for r in channel.ledger if r.status == "ok"][-1]


# ------------------------------------------------------------------ 惰性

def test_zero_rules_channel_is_inert():
    """零规则 ⇒ 通道"通电但不做功"：不产生任何账本记录。"""
    assert RULES == {}, "本期不做交互规则（第 9 缝空注册表）"
    engine = _engine()
    for _ in range(60):
        engine.step()
    channel = engine.resolution.channel
    assert len(channel.ledger) == 0
    assert channel.last_report.get("made", 0) == 0
    assert channel._reserved == 0


def test_transfer_is_out_of_scope_this_phase():
    """`transfer`（质量侧）本期不做：它的财富量化残差池需要独立规格与独立不变量。"""
    assert not hasattr(InteractionChannel, "transfer")


# ------------------------------------------------------------------ bind：守恒 / 建边

def test_bind_conserves_headcount_and_builds_both_edges():
    engine = _engine()
    cluster, cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)

    total_before = mini.total()
    pop_before = engine.population()

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id),
                          match=Match(age=(28, 35), gender=0)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 1
    assert mini.total() == pytest.approx(total_before - 1.0)
    assert abs(engine.population() - pop_before) < 1e-9      # 人头守恒
    assert channel._reserved == 0

    record = _last_ok(channel)
    assert record.delta_mass == -1.0
    # mini 里除注入的桶外还有被粗化的成员，加权抽样可能命中任一**匹配**桶 ⇒ 断言谓词而非具体桶
    assert compile_match(Match(age=(28, 35), gender=0), engine.window.space)(record.cell)
    new = engine.window.characters[record.new_id]
    assert new in r.relationships["probe"] and r in new.relationships["probe"]


def test_c_to_r_extracts_initiator_and_picks_lowest_id():
    """C→R：析出的是**发起者**（代表该簇），对手方是 `id` 最小的匹配窗口角色。"""
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    channel = engine.resolution.channel
    females = sorted((c for c in engine.window.characters.values() if c.gender == "female"),
                     key=lambda c: c.id)
    assert females, "需要窗口内有女性"
    expected_counterparty = females[0]

    channel.submit(Intent(kind="probe", origin=("cluster", cluster.id),
                          scope=("window",), match=Match(gender=1)))
    channel.run(_ctx(engine))

    new = engine.window.characters[_last_ok(channel).new_id]
    assert new in expected_counterparty.relationships["probe"]
    assert expected_counterparty in new.relationships["probe"]


# ------------------------------------------------------------------ unbind：可逆 / 无幽灵

def test_unbind_same_tick_restores_bucket_and_leaves_no_ghost():
    engine = _engine()
    cluster, cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)
    total_before = mini.total()
    pop_before = engine.population()
    window_before = len(engine.window.characters)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    channel.run(_ctx(engine))
    new_id = _last_ok(channel).new_id

    assert channel.unbind(new_id, tick=0) is True

    assert mini.total() == pytest.approx(total_before)      # 同 tick ⇒ mini 无演化 ⇒ 回到原桶
    assert len(engine.window.characters) == window_before
    assert abs(engine.population() - pop_before) < 1e-9
    # 三查：无幽灵
    assert all(c.id != new_id for c in r.relationships["probe"])
    assert new_id not in engine.window.characters


def test_unbind_across_ticks_keeps_headcount():
    """跨 tick 的 unbind 只保证人头守恒 + 无幽灵（coarse 侧在演化，不保证逐桶复原）。"""
    engine = _engine()
    cluster, cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    channel.run(_ctx(engine))
    new_id = _last_ok(channel).new_id

    for _ in range(20):                     # 让 mini 经历 aging / income 的桶位移
        engine.step()
    pop_before = engine.population()
    if new_id in engine.window.characters:
        assert channel.unbind(new_id, tick=engine.simulation_time) is True
        assert abs(engine.population() - pop_before) < 1e-9


def test_unbind_unknown_id_is_false():
    engine = _engine()
    assert engine.resolution.channel.unbind(99999) is False


# ------------------------------------------------------------------ 配额 / 边界

def test_no_match_is_dropped_not_raised():
    engine = _engine()
    cluster, cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    total_before = _mini(cluster).total()

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(200, 210))))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:no_match": 1}
    assert _mini(cluster).total() == pytest.approx(total_before)


def test_quota_per_cluster_limits_extraction():
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine, count=3.0)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    channel.cap_per_cluster = 1

    # 同一 (origin, scope) 但不同 kind ⇒ 不被去重掉，用来压配额闸
    for kind in ("probeA", "probeB"):
        channel.submit(Intent(kind=kind, origin=("character", r.id),
                              scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 1
    assert report["by_status"].get("dropped:quota_cluster") == 1


def test_no_window_headroom_is_dropped():
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    engine.window.capacity = len(engine.window.characters)      # 无 headroom

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    report = channel.run(_ctx(engine))
    assert report["by_status"] == {"dropped:window": 1}


def test_stale_scope_is_dropped():
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    del engine.resolution.store.clusters[cluster.id]

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    assert channel.run(_ctx(engine))["by_status"] == {"dropped:stale": 1}


def test_resolved_cluster_cannot_be_extracted_from():
    """`bind` 只对 **coarse** 簇有效（resolved 簇的成员本就是具名角色，无需析出）。"""
    engine = _engine()
    mgr = engine.resolution
    ids = list(engine.window.characters)[:5]
    cluster = mgr.store.create("family", set(ids))       # level=1，不 coarsen
    r = next(iter(engine.window.characters.values()))
    channel = mgr.channel

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(0, 120))))
    assert channel.run(_ctx(engine))["by_status"] == {"dropped:stale": 1}


# ------------------------------------------------------------------ 寻址封闭

def test_match_rejects_unaddressable_dimension(monkeypatch):
    """不变量 4：引用 ∉ `RECONSTRUCTIBLE` 的维度 ⇒ **立即抛错**。

    本期四个维度（age/gender/wealth/marital）都已在 `RECONSTRUCTIBLE` 里 ⇒ 用**收缩后的集合**
    来证这条守卫仍然有效（否则它就成了一句没有测试的空话）。
    """
    space = StateSpace()
    compile_match(Match(age=(0, 10), gender=0, wealth_bucket=(0, 5), marital=1), space)   # 合法

    monkeypatch.setattr(channel_mod, "RECONSTRUCTIBLE", frozenset({"age"}))
    with pytest.raises(ValueError):
        compile_match(Match(gender=0), space)


def test_invalid_match_raises_out_of_run(monkeypatch):
    """谓词非法 ⇒ **拒绝（抛错）**，不是静默失配。"""
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    monkeypatch.setattr(channel_mod, "RECONSTRUCTIBLE", frozenset({"age"}))
    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(gender=0)))
    with pytest.raises(ValueError):
        channel.run(_ctx(engine))


# ------------------------------------------------------------------ 失败回滚

def test_bind_rolls_back_fully_when_link_fails(monkeypatch):
    """建边失败 ⇒ **逆序全撤**：测度回滚 + 撤销已析出的角色（只回滚测度会留幽灵）。"""
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)
    total_before = mini.total()
    window_before = len(engine.window.characters)

    def boom(*args, **kwargs):
        raise RuntimeError("link boom")

    monkeypatch.setattr(channel_mod, "link", boom)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 0
    assert report["by_status"].get("dropped:error") == 1
    assert mini.total() == pytest.approx(total_before)          # reserve 已回滚
    assert len(engine.window.characters) == window_before       # 析出已撤销
    assert channel._reserved == 0
    assert not any(x.status == "ok" for x in channel.ledger)
    assert "RuntimeError" in _last_record(channel).note


def _last_record(channel):
    return list(channel.ledger)[-1]


# ------------------------------------------------------------------ N2-5：双人析出

def _married_bucket(engine, age=30, gender=0, wealth=10):
    return engine.window.space.encode(age, gender, wealth, 1)


def test_paired_extraction_conserves_headcount_and_builds_spouse_edge():
    """`Match(marital=1)` ⇒ **成对析出**（同一桶取 2.0）+ `link(a, b, "spouse")`。"""
    engine = _engine()
    cell = _married_bucket(engine)
    cluster, _cell = _coarse_cluster(engine, members=0, count=2.0, cell=cell)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)
    pop_before = engine.population()
    window_before = len(engine.window.characters)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 2
    assert mini.counts[cell] == pytest.approx(0.0)              # **同一桶**取 2.0
    assert abs(engine.population() - pop_before) < 1e-9         # 人头守恒
    assert len(engine.window.characters) == window_before + 2

    record = _last_ok(channel)
    assert record.delta_mass == -2.0
    a = engine.window.characters[record.new_id]
    b = engine.window.characters[record.spouse_id]
    assert a in b.relationships["spouse"] and b in a.relationships["spouse"]
    assert r in a.relationships["probe"] and a in r.relationships["probe"]
    assert b not in r.relationships["probe"]                    # 意图边只连 `a`（N2-5 第 5 步）
    assert record.initiator_id == r.id                          # 账本 initiator_id = 窗口侧那一端


def test_paired_extraction_needs_two_in_the_bucket():
    """桶里只有 1 个人 ⇒ 凑不出一对 ⇒ `dropped:no_match`（宁可丢弃也不造假单身）。"""
    engine = _engine()
    cell = _married_bucket(engine)
    cluster, _cell = _coarse_cluster(engine, members=0, count=1.0, cell=cell)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    total_before = _mini(cluster).total()
    pop_before = engine.population()

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    report = channel.run(_ctx(engine))

    assert report["by_status"] == {"dropped:no_match": 1}
    assert _mini(cluster).total() == pytest.approx(total_before)
    assert abs(engine.population() - pop_before) < 1e-9


def test_unspecified_marital_never_extracts_a_married_bucket():
    """**硬规则**：`Match(marital=None)`（不限）在析出域不得命中已婚桶——单人析出 = 造假单身。"""
    engine = _engine()
    cell = _married_bucket(engine)
    cluster, _cell = _coarse_cluster(engine, members=0, count=2.0, cell=cell)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(0, 120))))
    assert channel.run(_ctx(engine))["by_status"] == {"dropped:no_match": 1}

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    assert channel.run(_ctx(engine))["made"] == 2               # 显式 marital=1 才走成对


def test_quota_gate_is_amount_aware():
    """闸必须按 `amount` 判：本 tick 已析出 1 时，双人析出（还需 2）必须被丢弃（不变量 7）。"""
    engine = _engine()
    space = engine.window.space
    cluster, _cell = _coarse_cluster(engine, members=0, count=3.0,
                                     cell=space.encode(30, 0, 10, 0))
    _mini(cluster).add(_married_bucket(engine, wealth=11), 2.0)   # 另有已婚桶可成对
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    assert channel.cap_per_cluster == 2

    # kind 排序（升序）⇒ "aSingle" 先处理
    channel.submit(Intent(kind="aSingle", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(age=(30, 30))))
    channel.submit(Intent(kind="zPair", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 1                                     # 单人那次成功
    assert report["by_status"].get("dropped:quota_cluster") == 1   # 成对那次被闸挡下（1 + 2 > 2）


def test_paired_unbind_severs_both_edges_and_folds_back_both():
    """双人 `unbind`：断两条边（意图边 + spouse），两人各自折算；无幽灵、人头守恒。"""
    engine = _engine()
    cell = _married_bucket(engine)
    cluster, _cell = _coarse_cluster(engine, members=0, count=2.0, cell=cell)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)
    total_before = mini.total()
    pop_before = engine.population()
    window_before = len(engine.window.characters)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    channel.run(_ctx(engine))
    record = _last_ok(channel)
    a_id, b_id = record.new_id, record.spouse_id

    assert channel.unbind(a_id, tick=0) is True

    assert mini.total() == pytest.approx(total_before)          # 同 tick ⇒ 回到原桶
    assert len(engine.window.characters) == window_before
    assert abs(engine.population() - pop_before) < 1e-9
    assert a_id not in engine.window.characters and b_id not in engine.window.characters
    # 三查：无幽灵（两人的边都已解除）
    assert all(c.id not in (a_id, b_id) for c in r.relationships["probe"])
    unbound = [x for x in channel.ledger if x.status == "unbound"][-1]
    assert unbound.delta_mass == 2.0
    assert unbound.spouse_cell is not None


def test_paired_bind_rolls_back_both_when_link_fails(monkeypatch):
    """成对析出失败 ⇒ **逆序全撤**：两人都撤销、测度按 2.0 回滚、`reserved` 配平。"""
    engine = _engine()
    cell = _married_bucket(engine)
    cluster, _cell = _coarse_cluster(engine, members=0, count=2.0, cell=cell)
    r = next(iter(engine.window.characters.values()))
    channel = engine.resolution.channel
    mini = _mini(cluster)
    total_before = mini.total()
    window_before = len(engine.window.characters)

    def boom(*args, **kwargs):
        raise RuntimeError("link boom")

    monkeypatch.setattr(channel_mod, "link", boom)

    channel.submit(Intent(kind="probe", origin=("character", r.id),
                          scope=("cluster", cluster.id), match=Match(marital=1)))
    report = channel.run(_ctx(engine))

    assert report["made"] == 0
    assert report["by_status"].get("dropped:error") == 1
    assert mini.total() == pytest.approx(total_before)
    assert len(engine.window.characters) == window_before
    assert channel._reserved == 0
    assert not any(x.status == "ok" for x in channel.ledger)


# ------------------------------------------------------------------ 确定性

def test_bind_is_deterministic_given_seeded_rng():
    def run(seed):
        engine = _engine(rng=random.Random(seed))
        cluster, _cell = _coarse_cluster(engine, count=3.0)
        r = next(iter(engine.window.characters.values()))
        channel = engine.resolution.channel
        for kind in ("probeA", "probeB"):
            channel.submit(Intent(kind=kind, origin=("character", r.id),
                                  scope=("cluster", cluster.id),
                                  match=Match(age=(28, 35), gender=0)))
        channel.run(_ctx(engine))
        return [(x.status, x.cell, x.new_id) for x in channel.ledger]

    assert run(7) == run(7)


def test_intents_are_processed_in_documented_order():
    """排序键 `(origin_side, origin_id, kind, scope_type, scope_id)` 升序。"""
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine, count=3.0)
    chars = sorted(engine.window.characters.values(), key=lambda c: c.id)
    channel = engine.resolution.channel
    # 故意乱序提交；角色 id 升序 ⇒ 处理序应把小的排前面
    for c in (chars[2], chars[1], chars[0]):
        channel.submit(Intent(kind="k", origin=("character", c.id),
                              scope=("cluster", cluster.id), match=Match()))
    channel.cap_per_tick = 1                     # 只放第一个进来，便于观察顺序
    report = channel.run(_ctx(engine))

    assert report["made"] == 1
    assert _last_ok(channel).origin[1] == chars[0].id          # id 最小者先处理
    # 后两个按同序被配额挡下（账本顺序 = 处理顺序）
    drops = [r.origin[1] for r in channel.ledger if r.status == "dropped:quota_tick"]
    assert drops == [chars[1].id, chars[2].id]


# ------------------------------------------------------------------ 宽限期

def test_grace_freezes_resolution_and_expires():
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    mgr = engine.resolution
    mgr.channel.recently_active[cluster.id] = 0

    assert mgr._grace_ids(1) == {cluster.id}
    assert mgr._grace_ids(mgr.channel.grace_ticks + 5) == set()
    assert cluster.id not in mgr.channel.recently_active


def test_grace_blocks_materialize_of_recently_bound_cluster():
    """宽限期**不得**用"抬注意力"实现——那会让 `allocate` 反过来**物化**该簇（与"别扰动"相反）。"""
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    mgr = engine.resolution
    mgr.channel.recently_active[cluster.id] = 0
    mgr.attention[cluster.id] = 1.0          # 注意力很高 ⇒ 正常会被物化

    mgr.step(_ctx(engine, tick=0))

    assert cluster.id in mgr.store.clusters
    assert mgr.store.clusters[cluster.id].level == 0      # 仍冻结在 coarse


def test_bound_cluster_survives_recycle_within_grace():
    engine = _engine()
    cluster, _cell = _coarse_cluster(engine)
    r = next(iter(engine.window.characters.values()))
    mgr = engine.resolution

    mgr.channel.submit(Intent(kind="probe", origin=("character", r.id),
                              scope=("cluster", cluster.id), match=Match(age=(28, 35), gender=0)))
    mgr.channel.run(_ctx(engine, tick=0))
    assert mgr.channel.recently_active.get(cluster.id) == 0

    mgr.attention[cluster.id] = 0.0
    mgr._recycle(mgr._grace_ids(1))
    assert cluster.id in mgr.store.clusters           # 宽限期内不回收

    mgr._recycle(mgr._grace_ids(mgr.channel.grace_ticks + 5))
    assert cluster.id not in mgr.store.clusters       # 过期即回收（attention=0 < dissolve_floor）


# ------------------------------------------------------------------ 探针规则 + 长跑（接进真实 step 循环）

class _ProbeRule:
    """**仅测试用**的探针规则：确定性地制造 R↔C 双向意图（生产 `RULES` 恒为空）。"""

    def __init__(self, name, direction, every=5, match=None):
        self.name = name
        self.direction = direction            # "r2c" | "c2r"
        self.every = every
        self.match = match or Match(age=(0, 120))

    def offers(self, context):
        if self.every <= 0 or context.tick % self.every:
            return []
        coarse = sorted((c for c in context.store.clusters.values() if c.level == 0),
                        key=lambda c: c.id)
        if not coarse:
            return []
        cluster = coarse[0]                   # 确定性：id 最小的 coarse 簇
        chars = sorted(context.window.characters.values(), key=lambda c: c.id)
        if not chars:
            return []
        if self.direction == "r2c":
            return [Intent(kind=self.name, origin=("character", chars[0].id),
                           scope=("cluster", cluster.id), match=self.match)]
        return [Intent(kind=self.name, origin=("cluster", cluster.id),
                       scope=("window",), match=self.match)]


@pytest.fixture
def probe_rules(monkeypatch):
    rules = {"probe_r2c": _ProbeRule("probe_r2c", "r2c"),
             "probe_c2r": _ProbeRule("probe_c2r", "c2r")}
    for name, rule in rules.items():
        monkeypatch.setitem(RULES, name, rule)      # monkeypatch 自动还原 ⇒ 不影响其它测试
    return rules


def _long_run_engine(seed=11):
    """长跑用引擎：注入 rng、关注意力衰减、并**预置一个 coarse 簇**（保证探针有靶子）。"""
    engine = _engine(capacity=120, window=60, n=800, seed=3, rng=random.Random(seed))
    mgr = engine.resolution
    mgr.gamma = 1.0                              # 关衰减：预置簇不会自行冷却消失
    cluster, _cell = _coarse_cluster(engine, members=8, count=200.0)
    mgr.attention[cluster.id] = 0.2              # < theta_base（不物化）、>= dissolve_floor（不回收）
    return engine, cluster


def test_channel_ops_are_mass_neutral_in_long_run(probe_rules):
    """接进真实 `ResolutionManager.step` 循环后，通道**逐次操作**仍严格守恒。"""
    random.seed(11)
    engine, cluster = _long_run_engine()
    mgr = engine.resolution
    channel = mgr.channel
    mf = engine.measure_engine

    def total():
        return mf.measure.total() + mgr.store.size() + len(engine.window.characters)

    worst = {"dev": 0.0, "calls": 0}
    for name in ("run", "unbind"):
        original = getattr(channel, name)

        def checked(*args, _orig=original, _name=name, **kwargs):
            before = total()
            result = _orig(*args, **kwargs)
            dev = total() - before
            worst["calls"] += 1
            if abs(dev) > abs(worst["dev"]):
                worst["dev"] = dev
            assert abs(dev) < 1e-6, f"channel.{_name} 泄漏 {dev:+.6g}"
            return result

        setattr(channel, name, checked)

    for tick in range(1, 301):
        engine.step()
        assert len(engine.window.characters) <= engine.window.capacity
        if tick % 25 == 0:                        # 周期性逆操作（走 unbind 路径）
            alive = [r.new_id for r in channel.ledger
                     if r.status == "ok" and r.new_id in engine.window.characters]
            for nid in alive[:1]:
                channel.unbind(nid, tick=tick)

    made = sum(1 for r in channel.ledger if r.status == "ok")
    statuses = {r.status for r in channel.ledger}
    assert made > 0, "探针规则没跑出任何绑定 ⇒ 这个测试是空的"
    assert worst["calls"] > 0
    assert abs(worst["dev"]) < 1e-6
    assert {"ok", "unbound"} <= statuses
    assert not any(s.startswith("dropped:error") for s in statuses), statuses


def test_channel_long_run_ledger_is_deterministic(probe_rules):
    """同 `SIM_SEED` ⇒ 同一份意图序列与账本（不变量 5）。

    注意：生成层（`RandomUtil.generate_name`）仍用**模块级** `random`，故长跑重演必须重设全局种子
    ——这与生产里 `SIM_SEED` 的效果一致。
    """
    def run():
        random.seed(5)
        engine, _cluster = _long_run_engine(seed=5)
        channel = engine.resolution.channel
        for _ in range(120):
            engine.step()
        return [(r.tick, r.status, r.kind, r.origin, r.scope, r.cell, r.new_id)
                for r in channel.ledger]

    first, second = run(), run()
    assert first, "长跑未产生任何账本记录 ⇒ 确定性断言是空的"
    assert first == second
