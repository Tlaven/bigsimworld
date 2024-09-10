import threading
import time
from app.core.simulation.engine import SimulationEngine
from flask_sse import sse

def start_simulation():
    engine = SimulationEngine()
    while True:
        engine.step()
        #sse.publish({"data": time.time()}, type='simulation_update')
        time.sleep(1)  # 间隔1秒执行一次step

def run_simulation_in_background():
    simulation_thread = threading.Thread(target=start_simulation, daemon=True)
    simulation_thread.start()
