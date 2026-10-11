from app.core.measure import transitions as T
from app.core.measure.measure import Measure
from app.core.measure.space import StateSpace


def test_aging_on_boundary():
    space = StateSpace()
    m = Measure(space)
    origin = space.encode(30, 1, space.wealth_bucket(5000), 0)
    m.add(origin, 10)
    T.aging(m, 360)
    assert m.counts[space.encode(31, 1, space.wealth_bucket(5000), 0)] == 10
    assert m.total() == 10
    assert origin not in m.occupied


def test_aging_off_boundary_noop():
    space = StateSpace()
    m = Measure(space)
    origin = space.encode(30, 1, 0, 0)
    m.add(origin, 5)
    T.aging(m, 359)
    assert origin in m.occupied
    assert m.total() == 5


def test_death_rate():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(70, 1, space.wealth_bucket(5000), 0), 1000)
    T.death(m, 1)
    assert abs(m.total() - 1000 * (1 - T.DEATH_RATE)) < 1e-6


def test_death_ignores_young():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 1, space.wealth_bucket(5000), 0), 1000)
    T.death(m, 1)
    assert abs(m.total() - 1000) < 1e-9


def test_birth_rate():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 1, space.wealth_bucket(5000), 1), 1000)
    before = m.total()
    T.birth(m, 1)
    assert abs(m.total() - before - 1000 * T.BIRTH_RATE) < 1e-6


def test_income_moves_wealth_up():
    space = StateSpace()
    m = Measure(space)
    origin_bucket = space.wealth_bucket(5000)
    m.add(space.encode(30, 0, origin_bucket, 0), 1)
    T.income(m, 30)
    assert m.total() == 1
    new_index = next(iter(m.occupied))
    age, gender, wealth, marital = space.decode(new_index)
    assert age == 30 and gender == 0 and wealth >= origin_bucket
