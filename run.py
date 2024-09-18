import asyncio

from app import app, background_runner


if __name__ == '__main__':
    asyncio.run(background_runner.start())
    app.run()
    background_runner.stop()