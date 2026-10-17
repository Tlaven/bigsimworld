from bench.fingerprint import fingerprint, gini
from bench.world import build_engine, make_characters


def test_fingerprint_deterministic():
    a = fingerprint(build_engine(500, seed=1))
    b = fingerprint(build_engine(500, seed=1))
    assert a == b


def test_gini_bounds():
    assert gini([5, 5, 5]) == 0.0
    assert 0.0 <= gini([1, 2, 100]) <= 1.0


def test_age_hist_sums_to_population():
    fp = fingerprint(build_engine(500, seed=2))
    assert sum(fp["age_hist"]) == fp["population"]


def test_fingerprint_keys():
    fp = fingerprint(build_engine(100, seed=3))
    for key in ("population", "total_wealth", "age_hist", "wealth_quantiles",
                "degree_hist", "gini_wealth", "mean_age"):
        assert key in fp


def test_degree_reflects_real_relationships_not_dead_field():
    """度必须来自真实关系。

    `Character.relatives` 只在构造时填充、构造后从不更新 —— 取它会让度分布恒为单桶
    （"人人度 0"），使 `degree_l1` 结构性恒为 0（假绿灯，见 docs/history.md Stage 1 编注）。
    """
    engine = build_engine(400, seed=5)
    for _ in range(2000):
        engine.step()
    fp = fingerprint(engine)
    assert sum(fp["degree_hist"]) == fp["population"]
    assert sum(fp["degree_hist"][1:]) > 0, "长跑后仍无任何关系 ⇒ 度指标又退化成了单桶"


def test_measure_fingerprint_has_no_degree_graph():
    """测度层**无图**（状态空间不含度维度）：degree_hist 必须是 None，不是 [pop] 的伪单桶。"""
    from app.core.measure.engine import MeanFieldEngine
    from bench.fingerprint import measure_fingerprint

    mf = MeanFieldEngine(characters=make_characters(500, seed=1))
    assert measure_fingerprint(mf.measure, mf.space)["degree_hist"] is None
