from flask import Blueprint

# 创建蓝图
api_v1 = Blueprint('api_v1', __name__)

# 导入并注册 v1 下的蓝图
from .simulation import simulation_routes
from .subscribe import subscribe_routes
from .resolution import resolution_routes

api_v1.register_blueprint(simulation_routes)
api_v1.register_blueprint(subscribe_routes)
api_v1.register_blueprint(resolution_routes)
