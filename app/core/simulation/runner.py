from threading import Thread, Event

from app.core.simulation.engine import SimulationEngine
from app.core.statistics.surveys import SurveyManager
from app.core.measure.survey import measure_survey
from app.models.processing import ProcessingDB, init_db_queues
from app.services.sse_manager import sse_manager
from app.utils.decorators import time_limit
from app.utils.cache import py_cache


class SimulationRunner:
    """仿真驱动。mode='individual'（高保真逐个体）或 'measure'（均值场 + 真个体窗口）。

    可通过 start()/stop() 反复启停：stop 停线程（measure 模式落一份测度快照），
    start 清除停止标志后重建工作线程，引擎状态原地保留。
    """

    def __init__(self, app, mode="individual", capacity=1000, population=5000,
                 resume=False):
        self.app = app
        self.mode = mode
        self.resume = resume
        self.stop_event = Event()  # 用于停止模拟线程的事件
        self.processing_db = None
        self.db_queues = None
        self.survey_manager = None
        self.simulation_thread = None
        self.step_budget = 0.5  # 分辨率水位线的负载目标（秒；实测 compute 时间）

        if mode == "measure":
            from app.core.generation.human import generate_characters
            from app.core.measure.engine import MeanFieldEngine
            from app.core.measure.transitions import FULL_FLOWS
            from app.core.measure.window import WindowEngine

            engine = self._try_restore(capacity)
            if engine is not None:
                self.engine = engine
            else:
                measure_engine = MeanFieldEngine(
                    characters=generate_characters(population), flows=FULL_FLOWS)
                self.engine = WindowEngine(measure_engine, capacity=capacity,
                                           window=capacity, resolution=True)
            if getattr(self.engine, "resolution", None) is not None:
                # D2/L1 社会凝视：随窗口规模缩放（大窗口边更多，阈值同向放大）
                self.engine.resolution.endogenous_scale = max(6.0, capacity / 25.0)
        else:
            self.db_queues = init_db_queues()  # 初始化队列
            self.engine = SimulationEngine(self.db_queues)  # 初始化模拟引擎
            self.survey_manager = SurveyManager(self.engine)  # 初始化问卷管理器

    def _try_restore(self, capacity):
        """resume 时从最新快照恢复世界；无快照/无表/非 measure 模式返回 None（走新建）。"""
        if not self.resume or self.mode != "measure":
            return None
        from app.models.snapshot import load_latest

        snapshot = load_latest()
        if snapshot is None:
            return None

        from app.core.measure.window import WindowEngine

        engine = WindowEngine.restore(snapshot, capacity=capacity)
        print(f"Restored world from snapshot at t={engine.simulation_time} "
              f"(population={engine.population()}).")
        return engine

    @time_limit(1, record_name="simulation_step/s")  # 这里设置的时间限制尽量大于 1 秒，防止线程无法正常结束
    def step(self):
        if self.mode == "measure":
            self.engine.step()
            self._feedback_resolution()
            py_cache["survey_data"] = measure_survey(
                self.engine.measure_engine.measure, self.engine.measure_engine.space)
        else:
            if self.engine.simulation_time % 100 == 0:
                self.survey_manager.run()
            self.engine.step()

        self.publish_step()

    def _feedback_resolution(self):
        """把上一 tick 的实测负载反馈给分辨率调度（水位线 θ）。"""
        if not hasattr(self.engine, "feedback"):
            return
        load = py_cache.get("simulation_step/s")
        if load:
            self.engine.feedback(load[-1], self.step_budget)

    # ------------------------------------------------------------------ 发布

    def sample_people(self, k=20):
        """individual 模式直接取样前 k 个角色（measure 模式引擎自带）。"""
        return [character.__publish_dict__
                for character in list(self.engine.characters.values())[:k]]

    def publish_step(self):
        """统一两模式的 SSE payload：时间/人口/负载/窗口个体/分布。"""
        payload = {
            'time': self.engine.UTC,
            'population': self.population(),
            'simulation_load': py_cache.get('simulation_step/s')[-1],
            'people': (self.engine.sample_people(20)
                       if self.mode == "measure" else self.sample_people(20)),
        }
        survey = py_cache.get("survey_data")
        if survey:
            payload['age'] = survey['age']
            payload['wealth'] = survey['wealth']
        resolution = self.resolution_summary()
        if resolution is not None:
            payload['resolution'] = resolution
        notables = self.notables(12)
        if notables:
            payload['notables'] = notables
        sse_manager.publish(payload, type='data')

    # ------------------------------------------------------------------ 分辨率 / 注意度

    def resolution_summary(self):
        engine = getattr(self, "engine", None)
        return engine.resolution_summary() if hasattr(engine, "resolution_summary") else None

    def set_cluster_attention(self, cluster_id, value):
        engine = getattr(self, "engine", None)
        if not hasattr(engine, "set_cluster_attention"):
            return False
        return engine.set_cluster_attention(cluster_id, value)

    def set_person_attention(self, person_id, value):
        engine = getattr(self, "engine", None)
        if not hasattr(engine, "set_person_attention"):
            return None
        return engine.set_person_attention(person_id, value)

    def notables(self, k=12):
        engine = getattr(self, "engine", None)
        return engine.notables(k) if hasattr(engine, "notables") else []

    def life_log(self, person_id):
        engine = getattr(self, "engine", None)
        return engine.life_log(person_id) if hasattr(engine, "life_log") else None

    def population(self):
        if self.mode == "measure":
            return int(round(self.engine.population()))
        return len(self.engine.characters)

    def status(self):
        return {
            'running': self.is_running(),
            'mode': self.mode,
            'simulation_time': self.engine.simulation_time,
            'population': self.population(),
        }

    # ------------------------------------------------------------------ 生命周期

    def is_running(self):
        thread = self.simulation_thread
        return thread is not None and thread.is_alive() and not self.stop_event.is_set()

    def start_simulation(self):
        with self.app.app_context():
            while not self.stop_event.is_set():  # 检查是否需要停止
                self.step()

    def start(self):
        self.stop_event.clear()  # 允许 stop() 后再次 start()
        if self.mode == "individual":
            # 启动数据库处理进程
            self.processing_db = ProcessingDB(self.db_queues)
            self.processing_db.daemon = True
            self.processing_db.start()

        # 启动模拟线程
        self.simulation_thread = Thread(target=self.start_simulation)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        return True

    def stop(self):
        self.stop_event.set()  # 设置停止事件，通知模拟线程停止
        thread = self.simulation_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)  # 等待模拟线程结束
        self.simulation_thread = None

        if self.processing_db is not None:
            if self.processing_db.is_alive():
                self.processing_db.kill()  # 停止数据库处理进程
            self.processing_db.join(timeout=5)
            self.processing_db = None
            if self.mode == "individual":
                self.engine.update_status_in_db()  # 确保在停止时更新状态

        if self.mode == "measure":
            self.save_snapshot()
        return True

    def save_snapshot(self):
        """measure 模式：一份快照存下整份测度 + 物化窗口（models.snapshot）。"""
        from app.core.measure.measure import measure_to_payload
        from app.models.snapshot import save_snapshot

        try:
            measure = self.engine.measure_engine.measure
            save_snapshot(measure_to_payload(measure), self.engine.simulation_time,
                          self.engine.snapshot_payload())
        except Exception as exc:  # 快照失败绝不阻塞停止流程
            print(f"Snapshot save skipped: {exc}")
