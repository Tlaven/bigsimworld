from app.core.simulation.engine import SimulationEngine
from app.core.generation.human import generate_character


def create_peoples(engine):
    engine.create_character(generate_character(age=25, gender="male"))
    engine.create_character(generate_character(age=30, gender="female"))


if __name__ == "__main__":
    engine = SimulationEngine()
    for i in range(1):
        engine.step()
    #create_peoples(engine)
    engine.update_status_in_db()
