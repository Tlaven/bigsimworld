from app import app, background_runner


if __name__ == '__main__':
    background_runner.start()
    app.run()
    background_runner.stop()