from bench.cluster_inheritance import run_comparison


def test_family_scope_concentrates_inheritance():
    """族内池 vs 全局池：同段接收者，家族人均留存显著更高（"富族恒富"）。"""
    result = run_comparison(peers=120, dead_wealth=100_000_000)
    assert result["family_per_capita"] > 0
    assert result["ratio"] > 10
