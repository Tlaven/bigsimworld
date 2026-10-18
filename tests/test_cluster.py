"""Phase 0：共演单元（Cluster）与分辨率的守恒 / ρ 冒烟测试。"""

import random

import app.core.measure.cluster as cluster_mod
from app.core.measure.cluster import (
    ClusterStore,
    IdentityMassRho,
    KINDS,
    TickContext,
    WaterlinePolicy,
    decay,
)
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import (Measure, fold_pools, measure_from_characters,
                                      measure_from_payload, measure_to_payload)
from app.core.measure.space import StateSpace
from app.core.measure.transitions import (BIRTH_RATE, FULL_FLOWS, integer_death,
                                          integer_marriage)
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
    """coarse 共演单元用 mini 引擎演化：只有共演单元内引擎在动账，池作用域在共演单元内。"""
    space, measure, window, made = _window(sample=50)
    store = ClusterStore(measure, window)
    cluster = store.create("family", set(list(window.characters)[:20]))
    store.coarsen(cluster.id)
    mini = cluster.state["engine"].measure
    assert mini.total() == 20.0
    assert mini.yearly_inherited == {}  # 池初始为空且属于本共演单元

    before = _total(measure, window, store)
    window_before = len(window.characters)
    measure_before = measure.total()
    for tick in range(1, 361):
        store.step_coarse(TickContext(tick=tick, measure=measure, rng=random))

    # 只有共演单元内引擎在动账：总量变化 == mini 引擎净变化（出生 − 死亡）
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
    engine.step()  # 首 tick 触发形成共演单元
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
    mgr.store.coarsen(cluster.id)          # 粗化：共演单元聚合态须持久化
    mgr.set_attention(cluster.id, 0.7)
    mgr._last_switch[cluster.id] = 123     # 换档纪律簿记随快照往返
    mgr._switch_count[cluster.id] = 3
    mgr._risk[cluster.id] = 0.42           # 误差触发观测值（缺省关）同样往返

    save_snapshot(measure_to_payload(engine.measure_engine.measure),
                  engine.simulation_time, engine.snapshot_payload())
    snapshot = load_latest()

    restored = WindowEngine.restore(snapshot, capacity=200)
    assert restored.resolution is not None
    assert set(restored.resolution.store.clusters) == set(mgr.store.clusters)
    assert abs(restored.resolution.store.size() - mgr.store.size()) < 1e-3
    assert restored.resolution.attention.get(cluster.id) == 0.7
    assert abs(restored.population() - engine.population()) < 1e-2
    assert restored.resolution._last_switch.get(cluster.id) == 123
    assert restored.resolution._switch_count.get(cluster.id) == 3
    assert restored.resolution._risk.get(cluster.id) == 0.42


def test_formation_is_recurring():
    """形成共演单元是周期性的（非一次性）：先后两桩婚姻各自形成一个共演单元。"""
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
    """leaf 数预算只够一个共演单元 → 低注意共演单元被粗化、高注意共演单元保留。"""
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
    mgr.policy.budget_leaves = 2   # 只保留一个 size-2 共演单元
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
    """C1：共演单元成员的浮层亲属（如新生子）被抽入共演单元。"""
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
    """D1：同一连通分量内的小共演单元会合并（治愈 ρ）。"""
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
    """D1：合并会超上限时，跨共演单元边只记接口、不合并。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.max_members = 2  # 两个 size-2 共演单元合并(4) 会超限
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
    """C1：边界闭合有界——任何共演单元不超过 max_members（防渗流）。"""
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
    """D2：被广泛认识的家族共演单元靠社会凝视维持更高注意力（无需外部观察者）。"""
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


# ---------------------------------------------------------------- 换档纪律（B1）

def test_waterline_hysteresis_between_thresholds():
    """滞回：已 resolved 的簇在 [theta_down, theta_base) 区间保持；跌穿下阈才降档；

    缺省 `theta_down = theta_base` ⇒ 与无滞回逐位一致。"""
    space, measure, window, made = _window(sample=20)
    store = ClusterStore(measure, window)
    c1 = store.create("family", set(list(window.characters)[:5]))
    c2 = store.create("family", set(list(window.characters)[5:10]))
    store.coarsen(c2.id)                     # c2 供"升级阈值"对照
    attention = {c1.id: 0.45, c2.id: 0.45}

    hyst = WaterlinePolicy(theta_base=0.5, theta_down=0.4)
    levels = hyst.allocate(list(store.clusters.values()), attention)
    assert levels[c1.id] == 1                # 已 resolved：0.45 ≥ 0.4 ⇒ 保持
    assert levels[c2.id] == 0                # 未 resolved：0.45 < 0.5 ⇒ 不升级

    attention[c1.id] = 0.39                  # 跌穿下阈 ⇒ 降档
    levels = hyst.allocate(list(store.clusters.values()), attention)
    assert levels[c1.id] == 0

    attention[c1.id] = 0.45
    plain = WaterlinePolicy(theta_base=0.5)  # 缺省：无滞回
    levels = plain.allocate(list(store.clusters.values()), attention)
    assert levels[c1.id] == 0 and levels[c2.id] == 0


def test_min_dwell_limits_switch_frequency():
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.min_dwell_ticks = 30
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cid = mgr.cluster_of(a.id)
    assert cid is not None and mgr.store.clusters[cid].level == 1

    mgr.set_attention(cid, 0.2)              # 撤注视（> dissolve_floor=0.1，防回收）⇒ 降档
    engine.step()
    assert mgr.store.clusters[cid].level == 0
    switch_tick = mgr._last_switch[cid]

    for _ in range(10):                      # 驻留期内：无法换回
        mgr.set_attention(cid, 1.0)
        engine.step()
    assert mgr.store.clusters[cid].level == 0

    while engine.simulation_time - switch_tick < mgr.min_dwell_ticks:
        mgr.set_attention(cid, 1.0)
        engine.step()
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.store.clusters[cid].level == 1
    assert mgr.telemetry()[cid]["switches"] == 2


def test_min_dwell_default_is_thirty():
    """adr-011：缺省驻留闸 = 30——降档后 30 tick 内不得换回；传 0 可关闭。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    assert mgr.min_dwell_ticks == 30
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cid = mgr.cluster_of(a.id)

    mgr.set_attention(cid, 0.2)              # 撤注视（> dissolve_floor，防回收）⇒ 降档
    engine.step()
    assert mgr.store.clusters[cid].level == 0
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.store.clusters[cid].level == 0     # 驻留期内不换回（缺省即生效）

    mgr.min_dwell_ticks = 0                       # 回退开关仍可用
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.store.clusters[cid].level == 1


# ---------------------------------------------------------------- 通量遥测（B2）

def _resolved_family_engine():
    """一家三口（夫妻 a/b + 孩子 c）的 resolved 共演单元。

    四人个体事件评估已停用（`step_threshold=3600`）⇒ 遥测对拍不被自发事件污染。"""
    random.seed(23)
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    a, b, c, d = list(engine.window.characters.values())[:4]
    for character in (a, b, c, d):
        character.age = 30
        character.pedometer["step_threshold"] = 3600
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    c.relationships["parent"].append(a)
    a.relationships["child"].append(c)
    c.relationships["parent"].append(b)
    b.relationships["child"].append(c)
    engine.step()
    cid = mgr.cluster_of(a.id)
    assert cid is not None and mgr.store.clusters[cid].level == 1
    assert c.id in mgr.store.clusters[cid].member_ids
    return engine, mgr, cid, (a, b, c, d)


def test_flux_telemetry_expected_matches_rate_model():
    engine, mgr, cid, (a, b, c, d) = _resolved_family_engine()
    for _ in range(5):
        mgr.set_attention(cid, 1.0)
        engine.step()

    tel = mgr.telemetry()[cid]
    ticks = tel["ticks"]
    assert ticks >= 1
    # 期望侧 = 粗模型速率（与 transitions 同源）：已婚且 18≤age≤50 的两人 ⇒ 2×BIRTH_RATE/tick
    assert abs(tel["expected"]["births"] - ticks * 2 * BIRTH_RATE) < 1e-12
    assert tel["expected"]["deaths"] == 0.0          # 无 60+
    assert tel["expected"]["marriages"] == 0.0       # 单身 ≤1
    assert tel["real"]["deaths"] == 0 and tel["real"]["marriages"] == 0
    assert tel["switches"] == 0


def test_flux_telemetry_detects_realized_events():
    """实测侧逐项对拍：婚姻（成员×浮层）+1、出生 +1、死亡 +1。"""
    engine, mgr, cid, (a, b, c, d) = _resolved_family_engine()
    mgr.set_attention(cid, 1.0)
    engine.step()                            # 建立遥测基线（无事件）

    c.marry_event.happen(d)                  # 婚姻：成员 c 与浮层 d
    d.marry_event.happen(c)
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.telemetry()[cid]["real"]["marriages"] == 1

    c.childbirth_event.happen(d)             # 生育：新生儿的父/母含成员 c
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.telemetry()[cid]["real"]["births"] == 1

    b.death_event.happen()                   # 死亡：成员消失（受保护 ⇒ 排除逐出）
    mgr.set_attention(cid, 1.0)
    engine.step()
    assert mgr.telemetry()[cid]["real"]["deaths"] == 1


def test_singles_mini_stays_materializable():
    """整数语义（adr-010）：单身迷你粗化后仍可物化——不再出现「幽灵换档」。"""
    random.seed(41)
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    a, c = list(engine.window.characters.values())[:2]
    for character in (a, c):
        character.age = 30
        character.pedometer["step_threshold"] = 3600
    c.relationships["parent"].append(a)      # 亲子边（两者皆单身）
    a.relationships["child"].append(c)
    engine.step()
    cid = mgr.cluster_of(a.id)
    assert cid is not None

    mgr.store.coarsen(cid)                   # 收编：mini = 两个 1.0 单身桶
    mgr.set_attention(cid, 1.0)
    engine.step()                            # mini 整数语义演化一步 ⇒ 桶保持整人
    assert mgr.store.clusters[cid].level == 1
    tel = mgr.telemetry()[cid]
    assert tel["blocked"] == 0
    assert tel["switches"] == 1
    assert mgr._last_switch.get(cid) == engine.simulation_time


def test_blocked_still_counted_without_whole_buckets():
    """`blocked` 观测面仍有效：手工造全分数迷你（无可析出整人桶）⇒ 物化失败如实计数。"""
    random.seed(43)
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    mgr.form_interval = 1
    a, c = list(engine.window.characters.values())[:2]
    for character in (a, c):
        character.age = 30
        character.pedometer["step_threshold"] = 3600
    c.relationships["parent"].append(a)
    a.relationships["child"].append(c)
    engine.step()
    cid = mgr.cluster_of(a.id)

    mgr.store.coarsen(cid)
    mini = mgr.store.clusters[cid].state["engine"].measure
    for index in list(mini.occupied):        # 测试专用：抽到 0.3（无整人桶可析出）
        mini.add(index, -(mini.counts[index] - 0.3))
    mgr.set_attention(cid, 1.0)
    engine.step()
    tel = mgr.telemetry()[cid]
    assert tel["blocked"] == 1
    assert tel["switches"] == 0
    assert cid not in mgr._last_switch


def test_telemetry_is_observationally_noop(monkeypatch):
    """遥测是纯观测：no-op 掉遥测钩子与开启遥测，引擎可见状态逐位一致。"""

    def run():
        random.seed(31)
        engine = _engine_with_resolution(capacity=120, window=120)
        mgr = engine.resolution
        mgr.form_interval = 1
        chars = list(engine.window.characters.values())
        for i in range(0, 8, 2):             # 造几个家庭共演单元，制造换档压力
            chars[i].marry_event.happen(chars[i + 1])
            chars[i + 1].marry_event.happen(chars[i])
        for tick in range(12):
            for cid in list(mgr.store.clusters):
                mgr.set_attention(cid, 0.6 if tick % 4 < 2 else 0.4)
            engine.step()
        return (
            round(engine.population(), 9),
            len(engine.window.characters),
            round(engine.measure_engine.measure.total(), 9),
            tuple(sorted((cid, c.level, len(c.member_ids))
                         for cid, c in mgr.store.clusters.items())),
            tuple(sorted((cid, round(mgr.attention.get(cid, 0.0), 9))
                         for cid in mgr.store.clusters)),
        )

    observed = run()
    monkeypatch.setattr(cluster_mod.ResolutionManager, "_scan_flux", lambda self: None)
    monkeypatch.setattr(cluster_mod.ResolutionManager, "_snapshot_flux", lambda self: None)
    assert run() == observed


# ---------------------------------------------------------------- 整数语义发放（adr-010）

def test_integer_marriage_fires_whole_pairs():
    """信用发放（adr-010）：期望通量累积、积满 2 人整人成对；整人桶从不被削到 (0,1)。"""
    space = StateSpace()
    mini = Measure(space)
    i_male = space.encode(30, 0, 10, 0)
    i_female = space.encode(30, 1, 10, 0)
    mini.add(i_male, 1.0)
    mini.add(i_female, 1.0)

    fired_tick = None
    for tick in range(1, 2601):
        before = mini.total()
        integer_marriage(mini, tick)
        assert abs(mini.total() - before) < 1e-12       # 发放严格计数中性
        for index in (i_male, i_female):
            count = mini.counts[index]
            assert count == 0.0 or count >= 1.0          # 永不进入 (0,1)
        married = (mini.counts[space.encode(30, 0, 10, 1)]
                   + mini.counts[space.encode(30, 1, 10, 1)])
        if married == 2.0:
            fired_tick = tick
            break
    assert fired_tick is not None
    # 期望通量 = MARRIAGE_RATE × 2 人 × q(=1) × 2 / tick ⇒ 约 1800 tick 首发
    assert 1700 <= fired_tick <= 1900
    assert mini.counts[i_male] == 0.0 and mini.counts[i_female] == 0.0
    assert mini.total() == 2.0


def test_integer_death_fires_whole_removals():
    """信用发放（adr-010）：死亡按整人移除、`recent_deaths` 记整额；桶保持整数。"""
    space = StateSpace()
    mini = Measure(space)
    i_old_a = space.encode(70, 0, 10, 1)
    i_old_b = space.encode(75, 1, 12, 1)
    mini.add(i_old_a, 1.0)
    mini.add(i_old_b, 1.0)

    fired = []
    for tick in range(1, 4001):
        integer_death(mini, tick)
        fired.extend(mini.recent_deaths)
        for index in (i_old_a, i_old_b):
            count = mini.counts[index]
            assert count == 0.0 or count >= 1.0
    assert len(fired) >= 1
    assert all(abs(amount - 1.0) < 1e-12 for _age, _wealth, amount in fired)
    assert abs(mini.total() - (2.0 - len(fired))) < 1e-12


def test_credits_roundtrip_fold_and_defaults():
    """信用是发放器状态（adr-010）：payload 往返、旧档缺字段按 0、fold_pools 求和。"""
    space = StateSpace()
    measure = Measure(space)
    measure.marriage_credit = 1.5
    measure.death_credit = 0.25
    restored = measure_from_payload(measure_to_payload(measure), space)
    assert restored.marriage_credit == 1.5
    assert restored.death_credit == 0.25

    old = measure_from_payload(
        {"size": space.size, "cells": [[space.encode(30, 0, 10, 0), 1.0]]}, space)
    assert old.marriage_credit == 0.0 and old.death_credit == 0.0

    target = Measure(space)
    target.marriage_credit = 0.75
    target.death_credit = 1.0
    fold_pools(measure, target)
    assert target.marriage_credit == 2.25 and target.death_credit == 1.25
    assert measure.marriage_credit == 0.0 and measure.death_credit == 0.0


def test_fold_pools_canonicalizes_age_order():
    """折叠按段升序（遍历序纪律）：源段池的插入序不同 ⇒ 目标段序一致。"""
    space = StateSpace()
    first = Measure(space)
    second = Measure(space)
    source_a = Measure(space)
    source_a.yearly_inherited = {45: 1.0, 30: 2.0, 60: 3.0}
    source_b = Measure(space)
    source_b.yearly_inherited = {60: 3.0, 30: 2.0, 45: 1.0}

    fold_pools(source_a, first)
    fold_pools(source_b, second)
    assert list(first.yearly_inherited) == list(second.yearly_inherited) == [30, 45, 60]
    assert first.yearly_inherited == second.yearly_inherited
    assert first.yearly_inherited[30] == 2.0


# ---------------------------------------------------------------- 误差触发（候选，缺省关）

def test_risk_alert_default_off_and_floor_when_enabled():
    """`risk_alert` 缺省关（不动行为）；启用时，上次观测的相位离散度 ≥ 阈值 ⇒ 注意力地板。"""
    engine = _engine_with_resolution(capacity=200, window=200)
    mgr = engine.resolution
    assert mgr.risk_alert is None
    mgr.form_interval = 1
    mgr.min_dwell_ticks = 0                  # 隔离驻留闸
    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    engine.step()
    cid = mgr.cluster_of(a.id)

    mgr.store.coarsen(cid)                   # 手工降档
    mgr._risk[cid] = 0.9                     # 人造"上次观测离散度高"
    mgr.set_attention(cid, 0.2)
    engine.step()
    assert mgr.store.clusters[cid].level == 0      # 缺省关：地板不生效

    mgr.risk_alert = 0.5
    mgr.set_attention(cid, 0.2)
    engine.step()
    assert mgr.store.clusters[cid].level == 1      # 启用：地板把注意力抬到 θ ⇒ 升档









