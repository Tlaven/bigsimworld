from flask import Blueprint, jsonify

event_routes = Blueprint('events_routes', __name__)

@event_routes.route('/events', methods=['GET'])
def get_eventss():
    # 获取所有角色的逻辑
    return jsonify({"message": "List of eventss"})

@event_routes.route('/events/<id>', methods=['GET'])
def get_events(id):
    # 获取指定角色的逻辑
    return jsonify({"message": f"events {id}"})
