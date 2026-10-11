from threading import Thread, Event

from app.core.simulation.engine import SimulationEngine
from app.core.statistics.surveys import SurveyManager
from app.core.measure.survey import measure_survey
from app.models.processing import ProcessingDB, init_db_queues
from app.services.sse_manager import sse_manager
from app.utils.decorators import time_limit
from app.utils.cache import py_cache
from flask_sse import sse


class SimulationRunner:
    """仿真驱动。mode='individual'（默认，逐个体）或 'measure'（均值场 + 物化窗口）。"""

    def __init__(self, app, mode="individual", capacity=1000, population=5000):
        self.app = app
        self.mode = mode
        self.stop_event = Event()  # 用于停止模拟线程的事件
        self.processing_db = None
        self.db_queues = None
        self.survey_manager = None

        if mode == "measure":
            from app.core.generation.human import generate_characters
            from app.core.measure.engine import MeanFieldEngine
            from app.core.measure.transitions import FULL_FLOWS
            from app.core.measure.window import WindowEngine

            measure_engine = MeanFieldEngine(
                characters=generate_characters(population), flows=FULL_FLOWS)
            self.engine = WindowEngine(measure_engine, capacity=capacity, window=capacity)
        else:
            self.db_queues = init_db_queues()  # 初始化队列
            self.engine = SimulationEngine(self.db_queues)  # 初始化模拟引擎
            self.survey_manager = SurveyManager(self.engine)  # 初始化问卷管理器

    @time_limit(1, record_name="simulation_step/s")  # 这里设置的时间限制尽量大于 1 秒，防止线程无法正常结束
    def step(self):
        if self.mode == "measure":
            population = round(self.engine.population())
        else:
            population = len(self.engine.characters)
        print(f"Step {self.engine.simulation_time}:{py_cache.get('simulation_step/s')[-1]} people:{population}")

        if self.mode == "measure":
            self.engine.step()
            py_cache["survey_data"] = measure_survey(
                self.engine.measure_engine.measure, self.engine.measure_engine.space)
        else:
            if self.engine.simulation_time % 100 == 0:
                self.survey_manager.run()
            self.engine.step()

        payload = {'time': self.engine.UTC,
                   'simulation_load': py_cache.get('simulation_step/s')[-1]}
        if self.mode == "measure":
            payload['people'] = self.engine.sample_people(20)
            survey = py_cache.get("survey_data")
            if survey:
                payload['age'] = survey['age']
                payload['wealth'] = survey['wealth']
        sse_manager.publish(payload, type='data')
        try:
            sse.publish(payload, type='data')
        except Exception:
            pass

    def start_simulation(self):
        with self.app.app_context():
            while not self.stop_event.is_set():  # 检查是否需要停止
                self.step()

    def start(self):
        if self.mode == "individual":
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
        if self.processing_db is not None:
            self.processing_db.join()  # 等待数据库处理进程结束
            self.processing_db.kill()  # 停止数据库处理进程
            self.engine.update_status_in_db()  # 确保在停止时更新状态
