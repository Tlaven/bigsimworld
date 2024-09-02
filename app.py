from flask import Flask, render_template,jsonify,Response
from simulation_engine import SimulationEngine



app = Flask(__name__)


@app.route('/')
def index():

    return render_template('index.html')

@app.route('/api')
def api():
    engine = SimulationEngine()
    return Response(engine.run_simulation(), content_type='text/event-stream')
 


if __name__ == "__main__":
    app.run(use_reloader=False)
