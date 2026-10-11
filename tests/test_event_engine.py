from app.core.simulation.event_engine import EventEngine
from bench.world import make_characters, make_sink_queues


def test_event_engine_builds_without_db():
    chars = make_characters(100, seed=1)
    engine = EventEngine(make_sink_queues(), characters=chars)
    assert len(engine.characters) == 100
    assert engine.max_id == 100


def test_event_engine_time_advances():
    chars = make_characters(50, seed=1)
    engine = EventEngine(make_sink_queues(), characters=chars)
    for _ in range(37):
        engine.step()
    assert engine.simulation_time == 37
