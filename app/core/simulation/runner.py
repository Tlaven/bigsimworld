from threading import Thread
# import time

from app.core.simulation.engine import SimulationEngine
from app.models.processing import ProcessingDB, init_db_queues
# from flask_sse import sse


class SimulationRunner:
    def __init__(self):
        self.db_queues = init_db_queues()  # 初始化队列

    def start_simulation(self):
        self.engine = SimulationEngine(self.db_queues)
        while self.simulation_thread.is_alive():
            self.engine.step()
                # 模拟的状态更新推送给客户端（可选）
                # sse.publish({"data": time.time()}, type='simulation_update')

    def start(self):
        # 启动数据库处理进程
        self.processing_db = ProcessingDB(self.db_queues)
        self.processing_db.daemon = True
        self.processing_db.start()

        # 启动模拟线程
        self.simulation_thread = Thread(target=self.start_simulation)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()

    def stop(self):
        self.processing_db.kill()
        self.engine.update_status_in_db()
