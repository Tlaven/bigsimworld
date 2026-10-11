import random

from app.core.measure.measure import measure_from_characters
from app.core.measure.space import StateSpace
from app.core.measure.window import IndividualWindow
from bench.world import build_engine


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
