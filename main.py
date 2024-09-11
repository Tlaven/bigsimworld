from app.core.generation.human import generate_character
from app.core.simulation.engine import SimulationEngine



if __name__ == '__main__':
    engine = SimulationEngine()
    engine.step()
    engine.create_character(generate_character())