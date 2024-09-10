from flask import Blueprint

# 创建一个总的 API 蓝图
api_blueprint = Blueprint('api', __name__)

from .v1 import api_v1  # 导入 v1 版本的 API 蓝图

# 注册 v1 版本的蓝图到总的 API 蓝图中
api_blueprint.register_blueprint(api_v1, url_prefix='/v1')
