from flask import Blueprint, jsonify, request
import uuid

from app.services.sse_manager import sse_manager
from app.utils.logger import setup_logger

logger = setup_logger()

subscribe_routes = Blueprint('sse', __name__)

@subscribe_routes.route('/get-client-id')
def get_client_id():
    client_id = str(uuid.uuid4())
    sse_manager.subscribe(client_id)
    return jsonify({'client_id': client_id})

# 接受客户端发来的订阅情况消息
@subscribe_routes.route('/notify-connection', methods=['POST'])
def notify_connection():
    try:
        # 获取请求中的 JSON 数据
        data = request.get_json()
        
        # 提取客户端 ID 和通知类型
        client_id = data.get('clientId')
        notification_type = data.get('type')  # 新增获取 type 字段

        if not client_id:
            return jsonify({'success': False, 'message': 'Missing clientId'}), 400

        # 记录到日志
        logger.info(f"Received subscription notification from client ID: {client_id}, type: {notification_type}")


        if notification_type == 'connect':
            # 处理连接建立的情况
            sse_manager.send_initial_data(client_id)
            logger.info(f"Initial data sent to client ID: {client_id}")
        
        elif notification_type == 'keepalive':
            # 处理保持连接的情况
            sse_manager.send_keepalive(client_id)
            logger.info(f"Keepalive sent to client ID: {client_id}")
        
        # 返回成功响应
        return jsonify({'success': True, 'message': 'Connection notification received'}), 200

    except Exception as e:
        logger.exception(f"Error processing subscription notification from client ID: {client_id}, type: {notification_type}")
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500

# 根据client_id为路由解除订阅
@subscribe_routes.route('/unsubscribe/<client_id>', methods=['POST'])
def unsubscribe(client_id):
    if client_id in sse_manager.clients:
        sse_manager.unsubscribe(client_id)
    return jsonify({'success': True})


