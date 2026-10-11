import random

from app.core.generation.human import generate_character
from app.core.simulation.engine import SimulationEngine
from bench.sinks import SinkQueue


def make_sink_queues():
    return {"insert": SinkQueue(), "update": SinkQueue(), "delete": SinkQueue()}


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
        characters.append(character)
    return characters


def build_engine(n, seed=None, age_range=(0, 80)):
    return SimulationEngine(
        make_sink_queues(),
        characters=make_characters(n, seed=seed, age_range=age_range),
    )
