import numpy as np

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
