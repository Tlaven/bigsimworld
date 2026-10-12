from app import app
from app.core.simulation.runner import SimulationRunner


def _client():
    app.extensions["sim_runner"] = SimulationRunner(app, mode="measure", capacity=100, population=200)
    runner = app.extensions["sim_runner"]
    runner.save_snapshot = lambda: None
    return app.test_client(), runner


def test_resolution_status(app):
    client, _ = _client()
    response = client.get("/api/v1/resolution")
    assert response.status_code == 200
    body = response.json
    assert body["success"] is True
    assert "theta_base" in body
    assert "clusters" in body
    assert body["cluster_count"] == 0


def test_attention_requires_target(app):
    client, _ = _client()
    response = client.post("/api/v1/attention", json={})
    assert response.status_code == 400


def test_attention_person_not_in_cluster(app):
    client, _ = _client()
    response = client.post("/api/v1/attention", json={"person_id": 1, "value": 1.0})
    assert response.status_code == 404


def test_attention_unknown_cluster(app):
    client, _ = _client()
    response = client.post("/api/v1/attention", json={"cluster_id": 999, "value": 1.0})
    assert response.status_code == 200
    assert response.json["success"] is False


def test_life_log_endpoint(app):
    client, runner = _client()
    assert client.get("/api/v1/life/999999").status_code == 404

    for _ in range(5):
        runner.engine.step()
    person_id = next(iter(runner.engine.window.characters))
    response = client.get(f"/api/v1/life/{person_id}")
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["life"]
