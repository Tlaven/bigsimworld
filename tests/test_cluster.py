"""Phase 0：团（Cluster）与分辨率的守恒 / ρ 冒烟测试。"""

import random

from app.core.measure.cluster import (
    ClusterStore,
    IdentityMassRho,
    KINDS,
    TickContext,
    WaterlinePolicy,
    decay,
)
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import measure_from_characters
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import IndividualWindow, WindowEngine
from bench.world import build_engine, make_characters


def _window(n=2000, sample=50, capacity=1000, seed=1):
    space = StateSpace()
    engine = build_engine(n, seed=seed)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=capacity)
    random.seed(7)
    made = window.materialize_sample(sample)
    return space, measure, window, made


def _total(measure, window, store):
    return measure.total() + store.size() + len(window.characters)


def test_family_kind_registered():
    assert "family" in KINDS
    assert KINDS["family"].membership_edges() == {"parent", "child", "spouse"}


def test_coarsen_conserves_and_accumulates_rho():
    space, measure, window, made = _window(sample=50)
    assert made == 50
    store = ClusterStore(measure, window)
    ids = list(window.characters)[:10]
    cluster = store.create("family", set(ids))

    before = _total(measure, window, store)
    store.coarsen(cluster.id)

    assert len(window.characters) == 40
    assert cluster.level == 0
    assert abs(store.size() - 10.0) < 1e-9
    assert store.rho() > 0.0
    assert abs(_total(measure, window, store) - before) < 1e-6


def test_materialize_conserves_and_restores_leaves():
    space, measure, window, made = _window(sample=50)
    store = ClusterStore(measure, window)
    cluster = store.create("family", set(list(window.characters)[:10]))
    store.coarsen(cluster.id)
    before = _total(measure, window, store)

    made_back = store.materialize(cluster.id)

    assert made_back == 10
    assert cluster.level == 1
    assert len(window.characters) == 50
    assert abs(store.size()) < 1e-9
    assert abs(_total(measure, window, store) - before) < 1e-6


def test_waterline_and_decay():
    space, measure, window, made = _window(sample=20)
    store = ClusterStore(measure, window)
    c1 = store.create("family", set(list(window.characters)[:5]))
    c2 = store.create("family", set(list(window.characters)[5:10]))
    attention = {c1.id: 0.9, c2.id: 0.1}
    policy = WaterlinePolicy(theta_base=0.5)

    levels = policy.allocate(list(store.clusters.values()), attention)
    assert levels[c1.id] == 1
    assert levels[c2.id] == 0

    # 衰减：注意力随时间降温
    before = attention[c1.id]
    decay(attention, gamma=0.5)
    assert attention[c1.id] == before * 0.5


def test_coarse_steps_internally_with_inheritance_pool():
    """coarse 团用 mini 引擎演化：只有团内引擎在动账，池作用域在团内。"""
    space, measure, window, made = _window(sample=50)
    store = ClusterStore(measure, window)
    cluster = store.create("family", set(list(window.characters)[:20]))
    store.coarsen(cluster.id)
    mini = cluster.state["engine"].measure
    assert mini.total() == 20.0
    assert mini.yearly_inherited == {}  # 池初始为空且属于本团

    before = _total(measure, window, store)
    window_before = len(window.characters)
    measure_before = measure.total()
    for tick in range(1, 361):
        store.step_coarse(TickContext(tick=tick, measure=measure, rng=random))

    # 只有团内引擎在动账：总量变化 == mini 引擎净变化（出生 − 死亡）
    assert abs(_total(measure, window, store) - before - (mini.total() - 20.0)) < 1e-6
    assert len(window.characters) == window_before
    assert abs(measure.total() - measure_before) < 1e-9
    assert abs(store.size() - mini.total()) < 1e-9



def test_identity_mass_rho_metric():
    metric = IdentityMassRho()
    assert metric.on_merge("family", 1.0) == 0.0
    assert metric.on_split("family", 1.0) == 0.0


def _engine_with_resolution(n=1000, capacity=200, window=200, seed=1):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True)


def test_resolution_pin_holds_and_decay_coarsens():
    engine = _engine_with_resolution()
    window = engine.window
    a, b = list(window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)

    mgr = engine.resolution
    engine.step()  # 首 tick 触发成团
    assert mgr._formed
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)
    assert cluster.level == 1

    # 持续注视 → 保持 resolved
    for _ in range(200):
        mgr.set_attention(cluster.id, 1.0)
        engine.step()
    assert mgr.store.clusters[cluster.id].level == 1

    # 撤走注视 → 衰减 → 粗化（继续衰减则被回收）
    for _ in range(300):
        engine.step()
    live = mgr.store.clusters.get(cluster.id)
    assert live is None or live.level == 0
    assert engine.population() > 0


def test_population_counts_coarse_members():
    engine = _engine_with_resolution()
    window = engine.window
    a, b = list(window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    mgr = engine.resolution
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)

    wc_before = len(window.characters)
    pop_before = engine.population()
    mgr.store.coarsen(cluster.id)
    assert len(window.characters) == wc_before - 2
    assert abs(engine.population() - pop_before) < 1e-6


def test_cluster_snapshot_roundtrip():
    from app.core.measure.measure import measure_to_payload
    from app.models.snapshot import load_latest, save_snapshot

    engine = _engine_with_resolution(capacity=200, window=200)
    window = engine.window
    a, b = list(window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    mgr = engine.resolution
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)
    mgr.store.coarsen(cluster.id)          # 粗化：团聚合态须持久化
    mgr.set_attention(cluster.id, 0.7)

    save_snapshot(measure_to_payload(engine.measure_engine.measure),
                  engine.simulation_time, engine.snapshot_payload())
    snapshot = load_latest()

    restored = WindowEngine.restore(snapshot, capacity=200)
    assert restored.resolution is not None
    assert set(restored.resolution.store.clusters) == set(mgr.store.clusters)
    assert abs(restored.resolution.store.size() - mgr.store.size()) < 1e-3
    assert restored.resolution.attention.get(cluster.id) == 0.7
    assert abs(restored.population() - engine.population()) < 1e-2


def test_formation_is_recurring():
    """成团是周期性的（非一次性）：先后两桩婚姻各成一团。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1

    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    n1 = len(mgr.store.clusters)
    assert n1 >= 1

    floats = [c for c in engine.window.characters.values() if c.id not in mgr.protected_ids()]
    d, e = floats[0], floats[1]
    d.marry_event.happen(e)
    e.marry_event.happen(d)
    engine.step()
    assert len(mgr.store.clusters) >= n1 + 1


def test_budget_forces_coarsen():
    """leaf 数预算只够一个团 → 低注意团被粗化、高注意团保留。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    chars = list(engine.window.characters.values())
    for i in range(0, 8, 2):
        chars[i].marry_event.happen(chars[i + 1])
        chars[i + 1].marry_event.happen(chars[i])
    engine.step()
    assert len(mgr.store.clusters) >= 2

    ids = list(mgr.store.clusters)
    mgr.set_attention(ids[0], 1.0)
    mgr.set_attention(ids[1], 0.6)
    mgr.policy.budget_leaves = 2   # 只保留一个 size-2 团
    engine.step()

    levels = {c.level for c in mgr.store.clusters.values()}
    assert 1 in levels
    assert 0 in levels


def test_refill_after_coarsen():
    """coarsen 让窗口缩水后，下一步回填到容量。"""
    engine = _engine_with_resolution(capacity=150, window=150)
    mgr = engine.resolution
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)
    mgr.store.coarsen(cluster.id)
    mgr.set_attention(cluster.id, 0.0)  # 不让它被重新物化
    assert len(engine.window.characters) == 148

    engine.step()
    assert len(engine.window.characters) == 150


def test_dissolve_conserves_and_keeps_rho():
    space, measure, window, made = _window(sample=50)
    store = ClusterStore(measure, window)
    cluster = store.create("family", set(list(window.characters)[:10]))
    store.coarsen(cluster.id)
    before = _total(measure, window, store)
    rho_before = store.rho()

    assert store.dissolve(cluster.id) is True
    assert cluster.id not in store.clusters
    assert abs(_total(measure, window, store) - before) < 1e-6
    assert abs(store.rho() - rho_before) < 1e-9  # ρ 记入累计，不丢


def test_recycle_frees_slot():
    engine = _engine_with_resolution(capacity=150, window=150)
    mgr = engine.resolution
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)

    mgr.set_attention(cluster.id, 0.0)
    for _ in range(3):
        engine.step()
    assert cluster.id not in mgr.store.clusters   # 已回收
    assert mgr.store.dissolved_rho > 0.0


def test_boundary_closure_pulls_in_floating_kin():
    """C1：团成员的浮层亲属（如新生子）被抽入团。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cluster = next(c for c in mgr.store.clusters.values() if a.id in c.member_ids)

    child = next(x for x in engine.window.characters.values() if x.id not in mgr.protected_ids())
    a.relationships["child"].append(child)
    child.relationships["parent"].append(a)
    engine.step()

    assert child.id in mgr.store.clusters[cluster.id].member_ids


def test_merge_coupled_clusters():
    """D1：同一连通分量内的小团会合并（治愈 ρ）。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    chars = list(engine.window.characters.values())
    a, b, c, d = chars[0], chars[1], chars[2], chars[3]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    c.marry_event.happen(d)
    d.marry_event.happen(c)
    engine.step()
    assert mgr.cluster_of(a.id) != mgr.cluster_of(c.id)

    a.relationships["child"].append(c)
    c.relationships["parent"].append(a)
    engine.step()

    assert mgr.cluster_of(a.id) == mgr.cluster_of(c.id)   # 已合并
    assert len(mgr.store.clusters[mgr.cluster_of(a.id)].member_ids) == 4


def test_interface_when_merge_exceeds_cap():
    """D1：合并会超上限时，跨团边只记接口、不合并。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.max_members = 2  # 两个 size-2 团合并(4) 会超限
    chars = list(engine.window.characters.values())
    a, b, c, d = chars[0], chars[1], chars[2], chars[3]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    c.marry_event.happen(d)
    d.marry_event.happen(c)
    engine.step()
    a_cl = mgr.cluster_of(a.id)
    c_cl = mgr.cluster_of(c.id)
    assert a_cl is not None and c_cl is not None and a_cl != c_cl

    a.relationships["child"].append(c)
    c.relationships["parent"].append(a)
    engine.step()

    assert mgr.cluster_of(a.id) != mgr.cluster_of(c.id)  # 未合并
    assert mgr.store.clusters[a_cl].interface            # 记了接口边


def test_cluster_size_is_bounded():
    """C1：边界闭合有界——任何团不超过 max_members（防渗流）。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    chars = list(engine.window.characters.values())
    for i in range(0, 40, 2):
        chars[i].marry_event.happen(chars[i + 1])
        chars[i + 1].marry_event.happen(chars[i])
    for _ in range(5):
        engine.step()
    for cluster in mgr.store.clusters.values():
        if cluster.level == 1:
            assert len(cluster.member_ids) <= mgr.max_members


def test_family_inheritance_overflow_to_global():
    """C1c：overflow 份额注入全局池；0 时全部留在族内。"""
    from app.core.measure.cluster import family_inheritance
    from app.core.measure.measure import Measure

    space = StateSpace()

    def build():
        family = Measure(space)
        family.add(space.encode(30, 0, 0, 0), 1.0)  # 接收段有人
        family.recent_deaths = [(55, space.wealth_bucket(100000), 1.0)]
        return family, Measure(space)

    family, global_ = build()
    family_inheritance(family, 360, global_measure=global_, overflow=1.0)
    assert sum(global_.yearly_inherited.values()) > 0
    assert sum(family.yearly_inherited.values()) == 0

    family, global_ = build()
    family_inheritance(family, 360, global_measure=global_, overflow=0.0)
    assert sum(global_.yearly_inherited.values()) == 0
    assert sum(family.yearly_inherited.values()) > 0


def test_endogenous_attention_reflects_visibility():
    """D2：社会凝视——被非成员认识越多，内注意力越高。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.endogenous_scale = 2.0
    chars = list(engine.window.characters.values())
    a, b = chars[0], chars[1]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    for x in chars[2:12]:
        a.relationships["friend"].append(x)
        x.relationships["friend"].append(a)
    engine.step()
    cid = mgr.cluster_of(a.id)
    visibility = mgr._endogenous_attention()
    assert visibility.get(cid, 0.0) > 0.0


def test_endogenous_keeps_visible_cluster_alive():
    """D2：被广泛认识的家团靠社会凝视维持更高注意力（无需外部观察者）。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.endogenous_scale = 20.0
    chars = list(engine.window.characters.values())
    a, b, c, d = chars[0], chars[1], chars[2], chars[3]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    c.marry_event.happen(d)
    d.marry_event.happen(c)
    for x in chars[4:40]:  # a/b 广泛交友 → 高社会可见度
        a.relationships["friend"].append(x)
        x.relationships["friend"].append(a)
        b.relationships["friend"].append(x)
        x.relationships["friend"].append(b)
    engine.step()
    a_cl = mgr.cluster_of(a.id)
    c_cl = mgr.cluster_of(c.id)

    for _ in range(60):
        engine.step()

    assert mgr.store.clusters[a_cl].level == 1
    assert mgr.attention.get(a_cl, 0.0) > mgr.attention.get(c_cl, 0.0)


def test_life_log_records_history():
    engine = _engine_with_resolution(capacity=100, window=100)
    for _ in range(5):
        engine.step()
    person_id = next(iter(engine.window.characters))
    log = engine.life_log(person_id)
    assert log is not None and len(log) >= 1
    assert {"tick", "age", "wealth", "friends", "spouses"} <= set(log[-1])


def test_notables_lists_resolved_members():
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    notable_ids = {person["id"] for person in engine.notables(12)}
    assert a.id in notable_ids or b.id in notable_ids









