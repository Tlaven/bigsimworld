import random

from app.core.generation.human import generate_character
from app.core.simulation.engine import SimulationEngine
from bench.sinks import SinkQueue


def make_sink_queues():
    return {"insert": SinkQueue(), "update": SinkQueue()}


def make_characters(n, seed=None, age_range=(0, 80)):
    if seed is not None:
        random.seed(seed)
    characters = []
    for i in range(1, n + 1):
        character = generate_character(
            age=random.randint(*age_range),
            wealth=random.gauss(10000, 1000),
        )
        character["id"] = i
        # 随机的个人相位：不同角色的事件落在不同 tick，贴近真实世界
        character["pedometer"] = {"step": random.randint(0, 359), "step_threshold": 10}
        characters.append(character)
    return characters


def build_engine(n, seed=None, age_range=(0, 80), engine="legacy", rare_stride=1, n_cells=1):
    characters = make_characters(n, seed=seed, age_range=age_range)
    if engine == "event":
        from app.core.simulation.event_engine import EventEngine

        return EventEngine(make_sink_queues(), characters=characters,
                           rare_stride=rare_stride, n_cells=n_cells)
    return SimulationEngine(make_sink_queues(), characters=characters, n_cells=n_cells)
