import os
import random

from app import app, SimulationRunner


if __name__ == '__main__':
    # 默认用均值场 + 真个体窗口（可顶到千万级单位）；设 SIM_MODE=individual 可切回逐个体。
    mode = os.environ.get("SIM_MODE", "measure")
    capacity = int(os.environ.get("SIM_CAPACITY", "1000"))
    population = int(os.environ.get("SIM_POPULATION", "5000"))
    resume = os.environ.get("SIM_RESUME", "0") == "1"  # SIM_RESUME=1 从最新快照续跑世界
    seed = os.environ.get("SIM_SEED")  # 设 SIM_SEED 可复现整局随机（否则每次不同）
    if seed not in (None, ""):
        random.seed(int(seed))
    background = SimulationRunner(app, mode=mode, capacity=capacity, population=population,
                                  resume=resume)
    app.extensions['sim_runner'] = background  # 供 /api/v1/simulation 控制路由使用
    background.start()
    app.run()
    background.stop()
