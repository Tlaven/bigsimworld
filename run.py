
from app import app, SimulationRunner


if __name__ == '__main__':
    background = SimulationRunner(app)
    background.start()
    app.run()
    background.stop()