from threading import Thread, Event

from app.core.simulation.engine import SimulationEngine
from app.models.processing import ProcessingDB, init_db_queues
from app.services.publish import sse_publish
from app.utils.decorators import time_limit
from app.utils.cache import py_cache
from flask_sse import sse


class SimulationRunner:
    def __init__(self, app):
        self.app = app
        self.stop_event = Event()  # 用于停止模拟线程的事件
        self.db_queues = init_db_queues()  # 初始化队列
        self.engine = SimulationEngine(self.db_queues)  # 初始化模拟引擎
        self.engine.step_count = 0


    @time_limit(0.01, record_name = "simulation_step/s") # 这里设置的时间限制尽量大于 1 秒，防止线程无法正常结束
    def step(self):
        self.engine.step()
        #sse.publish(self.engine.__publish_json__)

    def start_simulation(self):
        with self.app.app_context():
            while not self.stop_event.is_set():  # 检查是否需要停止
                self.step()

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
        self.stop_event.set()  # 设置停止事件，通知模拟线程停止
        self.simulation_thread.join()  # 等待模拟线程结束
        self.processing_db.join()  # 等待数据库处理进程结束
        self.processing_db.kill()  # 停止数据库处理进程
        self.engine.update_status_in_db()  # 确保在停止时更新状态