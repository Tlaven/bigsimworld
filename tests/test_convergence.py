from bench.convergence import compare_fingerprint
from bench.fingerprint import fingerprint
from bench.world import build_engine


def test_compare_identical_is_zero():
    fp = fingerprint(build_engine(300, seed=1))
    d = compare_fingerprint(fp, fp)
    for key, value in d.items():
        assert value == 0.0, (key, value)


def test_compare_detects_difference():
    a = fingerprint(build_engine(300, seed=1))
    b = fingerprint(build_engine(300, seed=99, age_range=(30, 60)))
    d = compare_fingerprint(a, b)
    assert d["age_l1"] > 0.0


def test_compare_metrics_in_unit_range():
    a = fingerprint(build_engine(300, seed=1))
    b = fingerprint(build_engine(300, seed=2))
    for value in compare_fingerprint(a, b).values():
        assert 0.0 <= value <= 1.0


def test_degree_l1_undefined_across_measure_boundary():
    """测度层无图 ⇒ 跨层比"度分布"是**类别错误**，返回 None（而不是 0）。"""
    from bench.convergence import run_measure_full

    diff = compare_fingerprint(fingerprint(build_engine(300, seed=1)),
                               run_measure_full(500, 200, 42))
    assert diff["degree_l1"] is None


def test_degree_l1_defined_between_graph_bearing_sides():
    """窗口 ↔ 个体：双方都有图 ⇒ degree_l1 是真数字（这才是"度指标复活"的意义）。"""
    from bench.convergence import run_individual, run_window_fingerprint

    ind = run_individual(600, 800, 42)
    win = run_window_fingerprint(600, 800, capacity=600, seed=42)
    diff = compare_fingerprint(ind, win)
    assert diff["degree_l1"] is not None
    assert 0.0 <= diff["degree_l1"] <= 1.0
