from flask import Blueprint
from flask import jsonify
import uuid

from app.services.sse_manager import sse_manager

subscribe_routes = Blueprint('sse', __name__)

@subscribe_routes.route('/get-client-id')
def get_client_id():
    client_id = str(uuid.uuid4())
    sse_manager.subscribe(client_id)
    return jsonify({'client_id': client_id})

# 根据client_id为路由解除订阅
@subscribe_routes.route('/unsubscribe/<client_id>', methods=['POST'])
def unsubscribe(client_id):
    if client_id in sse_manager.clients:
        sse_manager.unsubscribe(client_id)
    return jsonify({'success': True})