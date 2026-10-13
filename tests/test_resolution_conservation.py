"""分辨率算子守恒（T0 门禁）：物化 / 粗化在**真实口径**下必须恒等守恒。

背景：曾经有两处泄漏——
  1) ``ClusterStore.materialize`` 无 ``>=1.0`` 守卫，从分数桶（来自 coarse 的
     death/birth）物化整人 → 只扣分数、却生出一整个人；
  2) ``ClusterStore.coarsen`` 用窗口成员重建聚合态，**丢掉**物化后残留的分数质量。
现用探针 ``bench.audit_ledger.run_resolution_probe`` 逐算子守住。
"""

import random

from app.core.measure.cluster import Cluster, ClusterStore  # noqa: F401  (ClusterStore used indirectly)
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import Measure
from app.core.measure.space import StateSpace
from app.core.measure.window import WindowEngine
from bench.audit_ledger import run_resolution_probe


def _mass(mf, engine):
    return (mf.measure.total() + engine.resolution.store.size()
            + len(engine.window.characters))


def test_materialize_skips_fractional_buckets():
    """分数桶（<1 人份额）不得物化整人——否则泄漏质量。"""
    random.seed(0)
    space = StateSpace()
    mf = MeanFieldEngine(space=space, characters=[], flows=())
    engine = WindowEngine(mf, capacity=50, window=50, resolution=True)
    store = engine.resolution.store

    mini = Measure(space)
    a = space.encode(30, 0, space.wealth_bucket(5000.0), 0)
    b = space.encode(31, 1, space.wealth_bucket(7000.0), 0)
    mini.add(a, 0.3)
    mini.add(b, 0.8)
    store.clusters[999] = Cluster(
        id=999, kind="family", level=0,
        state={"engine": MeanFieldEngine(measure=mini, flows=()), "size": mini.total()})

    before = _mass(mf, engine)
    made = store.materialize(999)
    assert made == 0                       # 无 ≥1.0 的桶 → 不析出
    assert _mass(mf, engine) == before     # 且守恒


def test_coarsen_keeps_materialize_residue():
    """物化后的分数残留，再次粗化时必须折回（否则丢质量）。"""
    random.seed(1)
    space = StateSpace()
    mf = MeanFieldEngine(space=space, characters=[], flows=())
    engine = WindowEngine(mf, capacity=100, window=100, resolution=True)
    store = engine.resolution.store

    mini = Measure(space)
    for age, gender in ((30, 0), (40, 1), (50, 0)):
        mini.add(space.encode(age, gender, space.wealth_bucket(5000.0), 0), 1.0)
    mini.add(space.encode(20, 0, space.wealth_bucket(1000.0), 0), 0.4)   # 分数残量
    store.clusters[7] = Cluster(
        id=7, kind="family", level=0,
        state={"engine": MeanFieldEngine(measure=mini, flows=()), "size": mini.total()})

    before = _mass(mf, engine)
    made = store.materialize(7)            # 至多 3 个整人；0.4 残留
    assert made >= 1
    assert abs(_mass(mf, engine) - before) < 1e-9      # 物化守恒
    assert store.clusters[7].state.get("engine") is not None   # 残留仍在共演单元内
    store.coarsen(7)                       # 再粗化：残留必须折回
    assert abs(_mass(mf, engine) - before) < 1e-9


def test_resolution_ops_conserved_under_production_flows():
    """生产口径（coarse 流含 death/birth）下逐算子守恒门禁，防回归。"""
    result = run_resolution_probe(n=1000, steps=1500, capacity=200, seed=3)
    assert result["calls"] > 0
    assert abs(result["worst_dev"]) < 1e-6
