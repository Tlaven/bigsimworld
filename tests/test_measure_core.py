from app.core.measure.measure import Measure, measure_from_characters
from app.core.measure.space import StateSpace
from bench.world import build_engine


def test_add_total_and_occupied():
    space = StateSpace()
    m = Measure(space)
    idx = space.encode(30, 1, space.wealth_bucket(5000), 0)
    m.add(idx, 3)
    assert m.total() == 3
    assert idx in m.occupied


def test_outflow():
    space = StateSpace()
    m = Measure(space)
    idx = space.encode(70, 1, space.wealth_bucket(5000), 0)
    m.add(idx, 100)
    removed = m.outflow(lambda i: space.decode(i)[0] >= 60, 0.01)
    assert abs(removed - 1.0) < 1e-9
    assert abs(m.total() - 99.0) < 1e-9


def test_inflow():
    space = StateSpace()
    m = Measure(space)
    m.inflow(space.encode(0, 0, 0, 0), 5)
    assert m.total() == 5


def test_measure_from_characters():
    space = StateSpace()
    engine = build_engine(300, seed=1)
    m = measure_from_characters(engine.characters.values(), space)
    assert m.total() == len(engine.characters)
