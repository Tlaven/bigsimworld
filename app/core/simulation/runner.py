import threading
import time

from app.core.simulation.engine import SimulationEngine
from flask_sse import sse

def start_simulation():
    engine = SimulationEngine()
    for _ in range(3):
        engine.step()
        #sse.publish({"data": time.time()}, type='simulation_update')

def run_simulation_in_background():
    simulation_thread = threading.Thread(target=start_simulation, daemon=True)
    simulation_thread.start()
