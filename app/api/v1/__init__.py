from flask import Blueprint

# 创建蓝图
api_v1 = Blueprint('api_v1', __name__)

# 导入并注册各个模块的蓝图
from .characters import character_routes
from .events import event_routes
from .simulation import simulation_routes

api_v1.register_blueprint(character_routes)
api_v1.register_blueprint(event_routes)
api_v1.register_blueprint(simulation_routes)
# 如果有用户模块或工具模块，类似地注册它们
