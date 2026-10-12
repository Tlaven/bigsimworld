import random

import numpy as np

from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import measure_from_characters
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import IndividualWindow, WindowEngine
from bench.world import build_engine, make_characters


def _seeded_window(n_chars=3000, capacity=800, sample=500, seed=1):
    space = StateSpace()
    engine = build_engine(n_chars, seed=seed)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=capacity)
    random.seed(7)
    window.materialize_sample(sample)
    return window


def test_window_forms_real_relationships():
    window = _seeded_window()
    for tick in range(1, 1501):
        window.step(tick)
    friends = sum(len(c.relationships["friend"]) for c in window.characters.values())
    acquaintances = sum(len(c.relationships["acquaintance"]) for c in window.characters.values())
    assert friends > 0
    assert acquaintances > friends


def test_window_conserves_population():
    window = _seeded_window()
    initial = window.population()
    for tick in range(1, 1501):
        window.step(tick)
    expected = initial + window.stats["births"] - window.stats["deaths"]
    assert abs(window.population() - expected) < 1.0
    assert len(window.characters) <= window.capacity


def test_window_has_marriages_and_births():
    window = _seeded_window(capacity=800, sample=600)
    for tick in range(1, 3001):
        window.step(tick)
    married = sum(1 for c in window.characters.values() if c.relationships["spouse"])
    assert married > 0
    assert window.stats["births"] > 0


def test_materialize_requires_a_full_count():
    """从测度引出个体要求对应桶至少满 1。"""
    space = StateSpace()
    measure = measure_from_characters(build_engine(20, seed=1).characters.values(), space)
    window = IndividualWindow(measure, capacity=100)
    before = window.population()
    cid = window.materialize(30, 0, space.wealth_bucket(100000), 0)
    assert cid is None  # 没有这个桶 -> 引不出
    assert window.population() == before


def test_materialize_dematerialize_conserves():
    """物化/退物化前后 Σ测度 + len(窗口) 不变。"""
    space = StateSpace()
    engine = build_engine(100, seed=1)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=100)
    before = window.population()
    total_before = measure.total()

    cid = None
    for index in sorted(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        cid = window.materialize(age, gender, wealth, marital)
        if cid is not None:
            break
    assert cid is not None
    assert len(window.characters) == 1
    assert abs(measure.total() - (total_before - 1.0)) < 1e-9
    assert window.population() == before

    assert window.dematerialize(cid) is True
    assert len(window.characters) == 0
    assert abs(measure.total() - total_before) < 1e-9
    assert window.population() == before


def test_capacity_enforced():
    space = StateSpace()
    engine = build_engine(2000, seed=1)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=5)
    random.seed(3)
    made = window.materialize_sample(50)
    assert made > 0
    window.enforce_capacity()
    assert len(window.characters) <= 5
    assert window.population() == 2000


def test_step_conserves_population():
    window = _seeded_window(n_chars=3000, capacity=1000, sample=500, seed=1)
    initial = window.population()
    for tick in range(1, 2001):
        window.step(tick)
    expected = initial + window.stats["births"] - window.stats["deaths"]
    assert abs(window.population() - expected) < 1.0


def test_sample_matches_measure_age_distribution():
    space = StateSpace()
    engine = build_engine(20000, seed=2)
    measure = measure_from_characters(engine.characters.values(), space)
    window = IndividualWindow(measure, capacity=100000)
    random.seed(5)
    made = window.materialize_sample(5000)
    assert made == 5000

    sample_hist = np.zeros(space.age_buckets)
    for character in window.characters.values():
        sample_hist[character.age] += 1
    sample_hist /= sample_hist.sum()

    measure_hist = np.zeros(space.age_buckets)
    for index in measure.occupied:
        age = space.decode(index)[0]
        measure_hist[age] += measure.counts[index]
    measure_hist /= measure_hist.sum()

    # 有限样本的抽样噪声：5000 抽样下 L1 应远小于 0.1
    l1 = np.abs(sample_hist - measure_hist).sum() / 2.0
    assert l1 < 0.07


def test_window_engine_conserves_over_long_run():
    mf = MeanFieldEngine(characters=make_characters(5000, seed=1), flows=())
    engine = WindowEngine(mf, capacity=500, window=500)
    random.seed(2)
    initial = engine.population()
    for _ in range(5000):
        engine.step()
        assert len(engine.window.characters) <= 500
    # mf 无流算子，总量只应由窗口个体的出生/死亡改变
    expected = initial + engine.window.stats["births"] - engine.window.stats["deaths"]
    assert abs(engine.population() - expected) < 1.0


def test_window_engine_sample_people_and_utc():
    mf = MeanFieldEngine(characters=make_characters(2000, seed=1), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=300, window=300)
    for _ in range(200):
        engine.step()
    people = engine.sample_people(10)
    assert isinstance(people, list)
    assert 0 < len(people) <= 10
    person = people[0]
    for key in ("id", "name", "gender", "age", "wealth", "relationships"):
        assert key in person
    assert isinstance(engine.UTC, str) and "-" in engine.UTC
