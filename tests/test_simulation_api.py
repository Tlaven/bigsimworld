from app.core.simulation.runner import SimulationRunner

from app import app


def _make_client():
    app.extensions["sim_runner"] = SimulationRunner(app, mode="measure", capacity=100, population=200)
    runner = app.extensions["sim_runner"]
    runner.save_snapshot = lambda: None  # 测试里不落库
    return app.test_client(), runner


def test_status_without_runner(app):
    app.extensions["sim_runner"] = None
    response = app.test_client().get("/api/v1/simulation")
    assert response.status_code == 503


def test_start_stop_control(app):
    client, runner = _make_client()

    response = client.get("/api/v1/simulation")
    assert response.status_code == 200
    body = response.json
    assert body["mode"] == "measure"
    assert body["running"] is False
    assert body["simulation_time"] == 0

    response = client.post("/api/v1/simulation/start")
    assert response.status_code == 200
    assert response.json["success"] is True
    assert client.get("/api/v1/simulation").json["running"] is True

    response = client.post("/api/v1/simulation/stop")
    assert response.status_code == 200
    if runner.simulation_thread is not None:
        runner.simulation_thread.join(timeout=6)
    assert client.get("/api/v1/simulation").json["running"] is False


def test_stop_when_not_running(app):
    client, _ = _make_client()
    response = client.post("/api/v1/simulation/stop")
    assert response.status_code == 200
    assert response.json["success"] is False
    assert response.json["message"] == "not running"
