from flask import Flask
from flask_cors import CORS
from flask_sse import sse

from .api import api_blueprint  # 导入总的 API 蓝图
from .utils.cache import cache
from .core.simulation.runner import SimulationRunner


def create_app():
    app = Flask(__name__)

    # 配置 Redis 以支持 Flask-SSE
    app.config["REDIS_URL"] = "redis://localhost:6379/0"

    # 配置缓存
    cache.init_app(app)

    # 注册 SSE Blueprint
    app.register_blueprint(sse, url_prefix='/stream')

    # 初始化 CORS，允许前端跨域请求
    CORS(app)

    # 注册 API 蓝图
    app.register_blueprint(api_blueprint, url_prefix='/api')

    # 启动模拟器
    background = SimulationRunner(app)
    background.start()

    return app, background
