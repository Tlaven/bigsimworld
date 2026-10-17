"""第 0 步基础设施：`link`/`unlink` 单入口、`extract`（谓词 + 注入 rng）、person→cluster 反向索引。

验收手段（见 `docs-templates/verifying-n2.md`）：

- **不变量 → property**：`link`/`unlink` 双向对称、`extract` 恰好扣 amount、绝不从分数桶取人；
- **differential**：反向索引与暴力扫描在长跑中逐一致（覆盖 coarsen/materialize/merge/dissolve）。

本文件不涉及任何交互语义——规则尚未定义。
"""

import random

import pytest

from app.core.generation.human import generate_character
from app.core.measure.cluster import ClusterStore
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import Measure, measure_from_characters
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import IndividualWindow, WindowEngine
from app.core.person.links import link, neighbors, unlink
from bench.world import build_engine, make_characters


# ------------------------------------------------------------------ helpers

def _window(n=200, sample=20, capacity=100, rng=None):
    space = StateSpace()
    engine = build_engine(n, seed=1)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=capacity, rng=rng)
    random.seed(7)
    window.materialize_sample(sample)
    return window


def _pair(window):
    a = window.attach(generate_character(age=30, gender="male"))
    b = window.attach(generate_character(age=28, gender="female"))
    return a, b


# ------------------------------------------------------------------ link / unlink

def test_link_symmetric_is_bidirectional():
    window = _window()
    a, b = _pair(window)
    link(a, b, "acquaintance")
    assert b in a.relationships["acquaintance"]
    assert a in b.relationships["acquaintance"]


def test_link_asymmetric_child_parent():
    """非对称关系：parent 侧写 child、child 侧写 parent。"""
    window = _window()
    a, b = _pair(window)
    link(a, b, "child", "parent")
    assert b in a.relationships["child"]
    assert a in b.relationships["parent"]
    assert b not in a.relationships["parent"]
    assert a not in b.relationships["child"]


def test_unlink_roundtrip_removes_both_sides():
    window = _window()
    a, b = _pair(window)
    link(a, b, "friend")
    unlink(a, b, "friend")
    assert b not in a.relationships["friend"]
    assert a not in b.relationships["friend"]


def test_unlink_records_relation_record():
    """`record=True` 与退场断链 / 死亡通知的记档语义一致（双向）。"""
    window = _window()
    a, b = _pair(window)
    link(a, b, "child", "parent")
    unlink(a, b, "child", "parent", record=True)
    assert b.id in a.relation_record["child"]
    assert a.id in b.relation_record["parent"]


def test_unlink_missing_edge_is_noop():
    window = _window()
    a, b = _pair(window)
    unlink(a, b, "spouse")          # 没有这条边
    assert a.relationships["spouse"] == []
    assert b.relationships["spouse"] == []


def test_neighbors_is_the_relation_truth_source():
    """关系人的唯一真相源是 `relationships`（经 `links.neighbors`）。

    已删除的 `relatives` 只在构造时填充、构造后从不更新 —— 正是度指标恒为 0 与 ρ 退化成
    "簇成员数"的根因（见 `docs/history.md` Stage 1 编注）。本测试把新决策钉住。
    """
    window = _window()
    a, b = _pair(window)
    assert neighbors(a) == set()
    link(a, b, "friend")
    assert b in neighbors(a) and a in neighbors(b)
    unlink(a, b, "friend")
    assert neighbors(a) == set()


def test_identity_mass_rho_counts_relations_not_headcount():
    """ρ 必须反映**关系度**，而不是退化成"簇成员数"。

    旧实现取死字段 `relatives`（恒空）⇒ ρ = Σ1 = 人数（实测 `rho = 118`；修正后 2143 ≈ 人数 ×(1+平均度)）。
    """
    from app.core.measure.cluster import IdentityMassRho

    window = _window()
    a, b = _pair(window)
    link(a, b, "friend")
    metric = IdentityMassRho()
    assert metric.on_coarsen("family", {a.id: a}) == 2.0            # 1 基 + 1 个关系人
    assert metric.on_coarsen("family", {a.id: a, b.id: b}) == 4.0   # 各 1 关系人


# ------------------------------------------------------------------ extract

def test_extract_refuses_fractional_bucket():
    """分数桶不可整人取出：强行取会只扣分数、却生出整个人（质量泄漏）。"""
    space = StateSpace()
    measure = Measure(space)
    window = IndividualWindow(measure, capacity=10)
    mini = Measure(space)
    mini.add(space.encode(30, 0, 10, 0), 0.4)

    store = ClusterStore(measure, window, rng=random.Random(1))
    assert store.extract(mini) is None
    assert mini.total() == pytest.approx(0.4)      # 未扣减


def test_extract_deducts_exactly_amount_and_is_deterministic():
    space = StateSpace()
    measure = Measure(space)
    window = IndividualWindow(measure, capacity=10)

    def build():
        mini = Measure(space)
        for age in (20, 30, 40):
            mini.add(space.encode(age, 0, 10, 0), 3.0)
        return mini

    store1 = ClusterStore(measure, window, rng=random.Random(11))
    store2 = ClusterStore(measure, window, rng=random.Random(11))
    mini1, mini2 = build(), build()

    seq1 = [store1.extract(mini1) for _ in range(6)]
    seq2 = [store2.extract(mini2) for _ in range(6)]

    assert None not in seq1
    assert seq1 == seq2                        # 同 seed ⇒ 同序列（确定性）
    assert mini1.total() == pytest.approx(9.0 - 6.0)
    assert mini2.total() == pytest.approx(9.0 - 6.0)


def test_extract_respects_predicate():
    """谓词式寻址：只从满足谓词的桶析出；抽空后返回 None。"""
    space = StateSpace()
    measure = Measure(space)
    window = IndividualWindow(measure, capacity=10)
    mini = Measure(space)
    old_cell = space.encode(70, 0, 10, 0)
    mini.add(old_cell, 2.0)
    mini.add(space.encode(30, 0, 10, 0), 2.0)

    store = ClusterStore(measure, window, rng=random.Random(3))
    is_old = lambda index: index == old_cell      # noqa: E731  （桶索引判定，非闭包式寻址的正式形态）
    assert store.extract(mini, predicate=is_old) == old_cell
    assert store.extract(mini, predicate=is_old) == old_cell
    assert store.extract(mini, predicate=is_old) is None
    assert mini.total() == pytest.approx(2.0)     # 年轻人未被动


def test_materialize_sample_uses_injected_rng():
    """注入 rng 后不再依赖模块级 random：同 seed 复现、异 seed 不同。"""
    space = StateSpace()

    def run(seed):
        engine = build_engine(500, seed=1)
        measure = measure_from_characters(engine.characters.values(), space)
        window = IndividualWindow(measure, capacity=50, rng=random.Random(seed))
        window.materialize_sample(30)
        return sorted((c.age, c.gender) for c in window.characters.values())

    assert run(5) == run(5)
    assert run(5) != run(6)


# ------------------------------------------------------------------ 反向索引

def _bruteforce_owner(store):
    owner = {}
    for cid, cluster in store.clusters.items():
        if cluster.level == 1:
            for mid in cluster.member_ids:
                owner[mid] = cid
    return owner


def test_owner_index_matches_bruteforce_over_long_run():
    """differential：反向索引必须与暴力扫描逐一致。

    主动驱动 粗化 ⇄ 再物化 与 dissolve，覆盖 create / coarsen / materialize / merge /
    split / dissolve 六类结构变更（任一处漏 touch，本测试变红）。
    """
    mf = MeanFieldEngine(characters=make_characters(1000, seed=1), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=200, window=200, resolution=True)
    mgr = engine.resolution
    mgr.form_interval = 1

    for step in range(120):
        if step % 20 == 0:
            level = 1.0 if (step // 20) % 2 == 0 else 0.0
            for cid in list(mgr.store.clusters):
                mgr.set_attention(cid, level)
        engine.step()

        expected = _bruteforce_owner(mgr.store)
        for pid in list(engine.window.characters):
            assert mgr.cluster_of(pid) == expected.get(pid), f"tick {step}, person {pid}"


def test_cluster_of_none_for_unclustered():
    mf = MeanFieldEngine(characters=make_characters(400, seed=3), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=100, window=100, resolution=True)
    engine.resolution.form_interval = 1
    engine.step()
    mgr = engine.resolution
    mgr.store.clusters.clear()
    mgr.store.touch()
    for pid in engine.window.characters:
        assert mgr.cluster_of(pid) is None
