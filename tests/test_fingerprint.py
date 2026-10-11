from bench.fingerprint import fingerprint, gini
from bench.world import build_engine


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
