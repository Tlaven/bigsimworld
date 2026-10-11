def test_runner_measure_mode_builds_and_steps():
    from app.core.simulation.runner import SimulationRunner

    runner = SimulationRunner(None, mode="measure", capacity=500, population=2000)
    assert runner.mode == "measure"
    for _ in range(100):
        runner.engine.step()
    assert runner.engine.simulation_time == 100
    assert len(runner.engine.layer.agents) <= 500
    assert runner.engine.population() > 0
