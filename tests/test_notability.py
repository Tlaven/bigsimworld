"""显要（notability）：判据 = 财富高位分位（可审计）；显要者受保护（不逐出、不粗化）。

设计意图（与产品目标一致）：世界中出现"对世界影响极大"的个体时，不能把他并入粗化的共演单元而
失去特殊性；同时微观窗口要让人感到"确实存在大量独立单位"。故对显要者：①绝不逐出，
②其所在共演单元保持 resolved（无视预算）。判据与保护策略均可插拔。
"""

from app.core.measure.cluster import WealthNotability
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def _engine(n=1000, capacity=200, window=200, seed=1):
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    return WindowEngine(mf, capacity=capacity, window=window, resolution=True)


def test_wealth_notability_threshold():
    """判据可审计：阈值 = 全人口财富降序累计到 top q 处的桶中心。"""
    space = StateSpace()
    mf = MeanFieldEngine(space=space, characters=[], flows=())
    for _ in range(100):
        mf.measure.add(space.encode(30, 0, space.wealth_bucket(1500.0), 0), 1.0)
    for _ in range(10):
        mf.measure.add(space.encode(30, 0, space.wealth_bucket(20000.0), 0), 1.0)

    metric = WealthNotability()
    threshold = metric.threshold(mf.measure, space, 0.05)   # top 5.5/110 → 落在 20000 段
    assert threshold == space.wealth_value(space.wealth_bucket(20000.0))

    class _C:
        def __init__(self, wealth):
            self.wealth = wealth

    assert metric.is_notable(_C(30000.0), threshold) is True
    assert metric.is_notable(_C(5000.0), threshold) is False
    assert metric.is_notable(_C(5000.0), None) is False


def test_notability_disabled_by_default():
    """默认关闭：未给分位时不产生显要（现有语义不变）。"""
    engine = _engine(capacity=100, window=100, seed=1)
    mgr = engine.resolution
    assert mgr.notable_fraction is None
    assert mgr.notable_threshold is None
    assert mgr.notable_ids() == set()
    engine.step()
    assert mgr.notable_ids() == set()


def test_notables_lists_floating_notable():
    """未纳入共演单元的浮层显要个体也必须出现在 notables 里（否则"看不见"）。"""
    engine = _engine(capacity=100, window=100, seed=5)
    mgr = engine.resolution
    mgr.set_notable_fraction(0.5)
    engine.step()
    floating = next((c for c in engine.window.characters.values()
                     if mgr.cluster_of(c.id) is None), None)
    assert floating is not None
    floating.wealth = 10_000_000.0

    listed = {person["id"]: person for person in engine.notables(100)}
    assert floating.id in listed
    assert listed[floating.id]["notable"] is True
    assert listed[floating.id]["cluster_id"] is None


def test_notable_cluster_survives_tight_budget():
    """极端收紧预算 + 撤走注意力：普通共演单元被粗化，显要共演单元仍 resolved 且个体不被逐出。"""
    engine = _engine(capacity=200, window=200, seed=2)
    mgr = engine.resolution
    mgr.form_interval = 1
    mgr.set_notable_fraction(0.5)

    a, b = list(engine.window.characters.values())[:2]
    a.marry_event.happen(b)
    b.marry_event.happen(a)
    a.age = b.age = 30                       # 避免测试期内自然死亡
    a.wealth = 10_000_000.0                  # 极端富裕 → 必为显要
    engine.step()
    cid = mgr.cluster_of(a.id)
    assert cid is not None

    mgr.policy.budget_leaves = 0             # 谁都别想 resolved
    mgr.set_attention(cid, 0.0)              # 也不许靠注意力
    for _ in range(80):
        engine.step()

    live = mgr.store.clusters.get(cid)
    assert live is not None and live.level == 1     # 显要共演单元未被粗化
    assert a.id in engine.window.characters         # 显要个体未被逐出
