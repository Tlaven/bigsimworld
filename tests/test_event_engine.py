import copy
import random

from app.core.simulation.engine import SimulationEngine
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


def _run(engine, steps, seed):
    random.seed(seed)
    for _ in range(steps):
        engine.step()
    return (
        engine.simulation_time,
        len(engine.characters),
        sum(c.age for c in engine.characters.values()),
        sum(c.wealth for c in engine.characters.values()),
        sum(len(c.relationships["friend"]) for c in engine.characters.values()),
    )


def test_event_engine_matches_legacy():
    chars = make_characters(200, seed=7)
    legacy = SimulationEngine(make_sink_queues(), characters=copy.deepcopy(chars))
    event = EventEngine(make_sink_queues(), characters=copy.deepcopy(chars))
    assert _run(legacy, 300, 999) == _run(event, 300, 999)
