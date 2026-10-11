from app.core.measure import transitions
from app.core.measure.engine import MeanFieldEngine
from bench.world import build_engine


def _seed_engine(**kwargs):
    chars = build_engine(500, seed=1).characters.values()
    return MeanFieldEngine(characters=chars, **kwargs)


def test_step_advances_time():
    engine = _seed_engine()
    engine.step()
    assert engine.simulation_time == 1


def test_run_until():
    engine = _seed_engine()
    engine.run_until(500)
    assert engine.simulation_time == 500


def test_aging_income_conserve_population():
    engine = _seed_engine(flows=(transitions.aging, transitions.income))
    before = engine.measure.total()
    engine.run_until(2000)
    assert abs(engine.measure.total() - before) < 1e-6


def test_default_flows_run():
    engine = _seed_engine()
    engine.run_until(1000)
    assert engine.measure.total() > 0
