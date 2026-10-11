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
