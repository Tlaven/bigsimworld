from flask import Blueprint, jsonify
from app.core import start_simulation, stop_simulation


simulation_routes = Blueprint('simulation_routes', __name__)

@simulation_routes.route('/simulation', methods=['GET'])
def get_simulation_status():
    # TODO: Implement this
    return jsonify({"message": "Simulation status"}), 200

@simulation_routes.route('/simulation/start', methods=['POST', 'GET'])
def start_simulation_route():
    start_simulation()
    return jsonify({"message": "Simulation started"}), 200

@simulation_routes.route('/simulation/stop', methods=['POST', 'GET'])
def stop_simulation_route():
    stop_simulation()
    return jsonify({"message": "Simulation stopped"}), 200