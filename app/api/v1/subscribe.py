from flask import Blueprint, jsonify, request
import uuid

from app.services.sse_manager import sse_manager

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
        
        # 提取客户端 ID
        client_id = data.get('clientId')
        
        if not client_id:
            return jsonify({'success': False, 'message': 'Missing clientId'}), 400
        
        # 这里可以进行进一步处理，比如记录到日志或数据库
        print(f"Client connected with ID: {client_id}")
        sse_manager.send_initial_data(client_id)

        # 返回成功响应
        return jsonify({'success': True, 'message': 'Connection notification received'}), 200

    except Exception as e:
        print(f"Error processing subscription notification: {e}")
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500

# 根据client_id为路由解除订阅
@subscribe_routes.route('/unsubscribe/<client_id>', methods=['POST'])
def unsubscribe(client_id):
    if client_id in sse_manager.clients:
        sse_manager.unsubscribe(client_id)
    return jsonify({'success': True})

