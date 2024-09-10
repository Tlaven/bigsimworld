
from .engine import SimulationEngine





def __init__():
    global engine_running
    engine_running = True
    engine = SimulationEngine()
    simulate_running(engine)

async def simulate_running(engine):
    while engine_running:
        engine.step()

def start_simulation():
    global engine_running
    engine_running = True
    print("Starting simulation...")

def stop_simulation():
    global engine_running
    engine_running = False
    print("Stopping simulation...")
