import sys

sys.setrecursionlimit(1500)  # 设置更大的递归深度

from app import app, SimulationRunner


if __name__ == '__main__':
    background = SimulationRunner(app)
    background.start()
    app.run()
    background.stop()