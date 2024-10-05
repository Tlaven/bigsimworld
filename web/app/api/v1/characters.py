from flask import Blueprint, jsonify

character_routes = Blueprint('character_routes1', __name__)

@character_routes.route('/characters', methods=['GET'])
def get_characters():
    # 获取所有角色的逻辑
    return jsonify({"message": "List of characters"})

@character_routes.route('/characters/<id>', methods=['GET'])
def get_character(id):
    # 获取指定角色的逻辑
    return jsonify({"message": f"Character {id}"})
