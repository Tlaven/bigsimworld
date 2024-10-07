

from app import create_app, SimulationRunner


if __name__ == '__main__':
    app, background = create_app()
    app.run(debug=True, use_reloader=False)
    background.stop()