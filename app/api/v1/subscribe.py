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