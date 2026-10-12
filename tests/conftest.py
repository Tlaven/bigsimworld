import pytest

from app import app as flask_app


@pytest.fixture
def app():
    flask_app.extensions.pop("sim_runner", None)
    yield flask_app
    runner = flask_app.extensions.get("sim_runner")
    if runner is not None:
        if runner.is_running():
            runner.stop()
        flask_app.extensions.pop("sim_runner", None)
    else:
        flask_app.extensions.pop("sim_runner", None)
