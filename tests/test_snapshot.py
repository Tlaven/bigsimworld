from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import measure_from_payload, measure_to_payload
from app.core.measure.transitions import FULL_FLOWS
from app.models.snapshot import load_latest, save_snapshot
from bench.world import make_characters


def test_measure_payload_roundtrip():
    engine = MeanFieldEngine(characters=make_characters(500, seed=1))
    payload = measure_to_payload(engine.measure)
    restored = measure_from_payload(payload, engine.space)
    assert abs(restored.total() - engine.measure.total()) < 1e-6
    assert restored.occupied == engine.measure.occupied


def test_snapshot_save_and_load():
    engine = MeanFieldEngine(characters=make_characters(300, seed=2), flows=FULL_FLOWS)
    engine.run_until(1000)
    payload = measure_to_payload(engine.measure)
    save_snapshot(payload, engine.simulation_time, window=[{"age": 30, "gender": 0}])
    loaded = load_latest()
    assert loaded is not None
    assert loaded["simulation_time"] >= 1000
    restored = measure_from_payload(loaded["measure"], engine.space)
    assert abs(restored.total() - engine.measure.total()) < 1e-3


def test_window_engine_restore_roundtrip():
    from app.core.measure.window import WindowEngine

    engine = WindowEngine(
        MeanFieldEngine(characters=make_characters(2000, seed=1), flows=FULL_FLOWS),
        capacity=300, window=300)
    for _ in range(500):
        engine.step()
    population_before = engine.population()

    payload = measure_to_payload(engine.measure_engine.measure)
    window_payload = [character.__dict__ for character in engine.window.characters.values()]
    save_snapshot(payload, engine.simulation_time, window_payload)
    snapshot = load_latest()

    restored = WindowEngine.restore(snapshot, capacity=300)
    assert restored.simulation_time == engine.simulation_time
    assert abs(restored.measure_engine.measure.total()
               - engine.measure_engine.measure.total()) < 1e-3
    assert set(restored.window.characters) == set(engine.window.characters)
    assert restored.window.max_id == engine.window.max_id
    # 关系图保真（好友边按 id 全部接回）
    assert sum(len(c.relationships["friend"]) for c in restored.window.characters.values()) \
        == sum(len(c.relationships["friend"]) for c in engine.window.characters.values())
    assert abs(restored.population() - population_before) < 1e-2  # 序列化每桶 round(6) 的累积误差

    # 续跑守恒：清空测度层流算子（流算子自身的守恒已由 measure 测试覆盖），
    # 这里专门验证"恢复过程不破坏窗口的出生/死亡守恒"
    restored.measure_engine.flows = ()
    initial = restored.population()
    for _ in range(200):
        restored.step()
    expected = initial + restored.window.stats["births"] - restored.window.stats["deaths"]
    assert abs(restored.population() - expected) < 1.0
