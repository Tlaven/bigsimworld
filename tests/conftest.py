import random

import pytest

from app import app as flask_app


@pytest.fixture(autouse=True)
def _isolate_global_random():
    """每个测试固定全局 random 种子：隔离上游测试遗留的随机状态漂移。"""
    random.seed(0x5EED)
    yield
    random.seed(0x5EED)


@pytest.fixture
def app():
    flask_app.extensions.pop("sim_runner", None)
    yield flask_app
    runner = flask_app.extensions.get("sim_runner")
    if runner is not None:
        if runner.is_running():
            runner.stop()
    flask_app.extensions.pop("sim_runner", None)
