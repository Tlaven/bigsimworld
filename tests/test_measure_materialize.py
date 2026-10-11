import random

import numpy as np

from app.core.measure.materialize import MaterializationLayer
from app.core.measure.measure import Measure, measure_from_characters
from app.core.measure.space import StateSpace
from bench.world import build_engine


def test_conservation_under_materialize_dematerialize():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 0, space.wealth_bucket(5000), 0), 10)
    layer = MaterializationLayer(m, capacity=100)
    before = layer.population()
    aid = layer.materialize(30, 0, space.wealth_bucket(5000), 0)
    assert aid is not None
    assert layer.population() == before
    layer.dematerialize(aid)
    assert layer.population() == before


def test_capacity_enforced():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 0, space.wealth_bucket(5000), 0), 100)
    layer = MaterializationLayer(m, capacity=5)
    layer.materialize_sample(50)
    layer.enforce_capacity()
    assert len(layer.agents) <= 5
    assert layer.population() == 100


def test_focus_predicate():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 0, space.wealth_bucket(5000), 0), 10)
    m.add(space.encode(5, 0, space.wealth_bucket(5000), 0), 10)
    layer = MaterializationLayer(m, capacity=10, focus=lambda s: s[0] < 10)
    assert layer.materialize(30, 0, space.wealth_bucket(5000), 0) is None
    assert layer.materialize(5, 0, space.wealth_bucket(5000), 0) is not None


def test_step_conserves_population():
    space = StateSpace()
    engine = build_engine(2000, seed=1)
    m = measure_from_characters(engine.characters.values(), space)
    layer = MaterializationLayer(m, capacity=1000)
    layer.materialize_sample(500)
    initial = layer.population()
    random.seed(3)
    for tick in range(1, 2001):
        layer.step(tick)
    expected = initial + layer.stats["births"] - layer.stats["deaths"]
    assert abs(layer.population() - expected) < 1.0


def test_sample_matches_measure_age_distribution():
    space = StateSpace()
    engine = build_engine(20000, seed=2)
    m = measure_from_characters(engine.characters.values(), space)
    layer = MaterializationLayer(m, capacity=100000)
    random.seed(5)
    made = layer.materialize_sample(5000)
    assert made == 5000

    sample_hist = np.zeros(space.age_buckets)
    for agent in layer.agents.values():
        sample_hist[agent["age"]] += 1
    sample_hist /= sample_hist.sum()

    measure_hist = np.zeros(space.age_buckets)
    for index in m.occupied:
        age = space.decode(index)[0]
        measure_hist[age] += m.counts[index]
    measure_hist /= measure_hist.sum()

    # 有限样本的抽样噪声：5000 抽样下 L1 应远小于 0.1
    l1 = np.abs(sample_hist - measure_hist).sum() / 2.0
    assert l1 < 0.07


def test_materialized_engine_conserves_over_long_run():
    from app.core.measure.engine import MeanFieldEngine
    from app.core.measure.materialize import MaterializedEngine
    from bench.world import make_characters

    mf = MeanFieldEngine(characters=make_characters(5000, seed=1), flows=())
    engine = MaterializedEngine(mf, capacity=500, window=500)
    random.seed(2)
    initial = engine.population()
    for _ in range(20000):
        engine.step()
        assert len(engine.layer.agents) <= 500
    # mf 无流算子，总量只应由物化个体的出生/死亡改变
    expected = initial + engine.layer.stats["births"] - engine.layer.stats["deaths"]
    assert abs(engine.population() - expected) < 1.0

