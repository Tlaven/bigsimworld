from flask import Blueprint, jsonify

chart_routes = Blueprint('character_routes', __name__)

@chart_routes.route('/charts')
def charts():
    return jsonify({'charts': ['bar', 'line', 'pie']})