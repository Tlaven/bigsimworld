from threading import Thread, Event

from app.core.simulation.engine import SimulationEngine
from app.models.processing import ProcessingDB, init_db_queues

class SimulationRunner:
    def __init__(self):
        self.stop_event = Event()  # 用于停止模拟线程的事件

    def start_simulation(self):
        self.engine = SimulationEngine(self.db_queues)
        while not self.stop_event.is_set():  # 检查是否需要停止
            self.engine.step()

    def start(self):
        self.db_queues = init_db_queues()  # 初始化队列
        # 启动数据库处理进程
        self.processing_db = ProcessingDB(self.db_queues)
        self.processing_db.daemon = True
        self.processing_db.start()

        # 启动模拟线程
        self.simulation_thread = Thread(target=self.start_simulation)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()

    def stop(self):
        self.stop_event.set()  # 设置停止事件，通知模拟线程停止
        self.simulation_thread.join()  # 等待模拟线程结束
        self.processing_db.kill()  # 停止数据库处理进程
        self.engine.update_status_in_db()  # 确保在停止时更新状态