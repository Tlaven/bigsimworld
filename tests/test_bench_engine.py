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
