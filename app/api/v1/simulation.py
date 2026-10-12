from flask import Blueprint, current_app, jsonify

simulation_routes = Blueprint('simulation_routes', __name__)


def _runner():
    """run.py 启动时把 SimulationRunner 挂到 app.extensions['sim_runner']。"""
    return current_app.extensions.get("sim_runner")


@simulation_routes.route('/simulation', methods=['GET'])
def simulation_status():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    return jsonify({'success': True, **runner.status()})


@simulation_routes.route('/simulation/start', methods=['POST'])
def start_simulation_route():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    if runner.is_running():
        return jsonify({'success': False, 'message': 'already running', **runner.status()})
    runner.start()
    return jsonify({'success': True, **runner.status()})


@simulation_routes.route('/simulation/stop', methods=['POST'])
def stop_simulation_route():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    if not runner.is_running():
        return jsonify({'success': False, 'message': 'not running', **runner.status()})
    runner.stop()
    return jsonify({'success': True, **runner.status()})
