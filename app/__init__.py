import os

from flask import Flask
from flask_cors import CORS
from flask_sse import sse

from .api import api_blueprint  # 导入总的 API 蓝图
from .core.simulation.runner import SimulationRunner as SimulationRunner  # 显式再导出（run.py 使用）
from .models import init_db


def create_app():
    app = Flask(__name__)

    # Redis（SSE 依赖）：可用 REDIS_URL 覆盖
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # 显式建表（不在模块导入时产生副作用）
    init_db()

    # 注册 SSE Blueprint
    app.register_blueprint(sse, url_prefix='/stream')

    # 初始化 CORS：默认放开（本地观测）；可用 CORS_ORIGINS 指定
    CORS(app, origins=os.environ.get("CORS_ORIGINS", "*"))

    # 注册 API 蓝图
    app.register_blueprint(api_blueprint, url_prefix='/api')

    return app


app = create_app()
