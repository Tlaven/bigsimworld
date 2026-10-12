from flask import Blueprint, current_app, jsonify, request

resolution_routes = Blueprint('resolution_routes', __name__)


def _runner():
    return current_app.extensions.get("sim_runner")


@resolution_routes.route('/resolution', methods=['GET'])
def resolution_status():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    summary = runner.resolution_summary()
    if summary is None:
        return jsonify({'success': False, 'message': 'resolution disabled'}), 404
    return jsonify({'success': True, **summary})


@resolution_routes.route('/attention', methods=['GET'])
def get_attention():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    engine = getattr(runner, "engine", None)
    resolution = getattr(engine, "resolution", None)
    if resolution is None:
        return jsonify({'success': False, 'message': 'resolution disabled'}), 404
    return jsonify({'success': True,
                    'attention': {str(k): v for k, v in resolution.attention.items()}})


@resolution_routes.route('/attention', methods=['POST'])
def set_attention():
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    data = request.get_json() or {}
    value = float(data.get('value', 1.0))
    cluster_id = data.get('cluster_id')
    person_id = data.get('person_id')
    if cluster_id is not None:
        ok = runner.set_cluster_attention(int(cluster_id), value)
        return jsonify({'success': ok, 'cluster_id': int(cluster_id) if ok else None})
    if person_id is not None:
        resolved = runner.set_person_attention(int(person_id), value)
        if resolved is None:
            return jsonify({'success': False, 'message': 'person not in a cluster'}), 404
        return jsonify({'success': True, 'cluster_id': resolved})
    return jsonify({'success': False, 'message': 'need cluster_id or person_id'}), 400


@resolution_routes.route('/life/<int:person_id>', methods=['GET'])
def person_life_log(person_id):
    runner = _runner()
    if runner is None:
        return jsonify({'success': False, 'message': 'sim runner not attached'}), 503
    log = runner.life_log(person_id)
    if log is None:
        return jsonify({'success': False, 'message': 'no such individual'}), 404
    return jsonify({'success': True, 'person_id': person_id, 'life': log})
