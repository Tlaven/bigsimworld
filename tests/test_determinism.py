"""确定性：固定种子 + 固定规则 ⟹ 发展完全可复现（同种子必然同结果）。"""

import random

from app.core.generation.human import generate_characters
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from app.core.simulation.runner import SimulationRunner
from app.utils.cache import py_cache


def _fingerprint(engine):
    measure = engine.measure_engine.measure
    cells = tuple(sorted((idx, round(cnt, 6)) for idx, cnt in measure.iter_occupied()))
    people = tuple(sorted(
        (cid, c.age, round(c.wealth, 3), c.gender, len(c.relationships["friend"]))
        for cid, c in engine.window.characters.items()
    ))
    return engine.simulation_time, engine.population(), cells, people


def _run(seed, steps):
    random.seed(seed)
    engine = WindowEngine(
        MeanFieldEngine(characters=generate_characters(300), flows=FULL_FLOWS),
        capacity=60, window=60, resolution=True,
    )
    engine.resolution.endogenous_scale = 6
    for _ in range(steps):
        engine.step()
    return _fingerprint(engine)


def test_seeded_world_is_reproducible():
    assert _run(42, 150) == _run(42, 150)


def test_different_seeds_diverge():
    assert _run(42, 150) != _run(7, 150)


def test_runner_seed_enables_deterministic_mode(app):
    """设种子 → 确定性模式：跳过墙钟负载反馈（否则同种子不可复现）。"""
    py_cache["simulation_step/s"] = [0.99]  # 超过 step_budget=0.5，会收紧叶子预算
    try:
        seeded = SimulationRunner(app, mode="measure", capacity=50, population=100, seed=1)
        assert seeded.deterministic is True
        before = seeded.engine.resolution.policy.budget_leaves
        seeded._feedback_resolution()
        assert seeded.engine.resolution.policy.budget_leaves == before

        plain = SimulationRunner(app, mode="measure", capacity=50, population=100)
        assert plain.deterministic is False
        before2 = plain.engine.resolution.policy.budget_leaves
        plain._feedback_resolution()
        assert plain.engine.resolution.policy.budget_leaves < before2
    finally:
        py_cache.pop("simulation_step/s", None)
