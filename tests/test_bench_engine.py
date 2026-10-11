from bench.measure import measure_steps
from bench.world import build_engine


def test_build_engine_population():
    engine = build_engine(50, seed=1)
    assert len(engine.characters) == 50
    assert engine.max_id == 50


def test_step_advances_time_and_is_stable():
    engine = build_engine(50, seed=1)
    for _ in range(20):
        engine.step()
    assert engine.simulation_time == 20


def test_measure_returns_per_step_durations():
    engine = build_engine(30, seed=2)
    result = measure_steps(engine, 10)
    assert len(result["durations"]) == 10
    assert result["avg"] > 0
    assert result["population"] >= 30
