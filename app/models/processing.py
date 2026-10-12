from multiprocessing import Process, Manager, Event

from . import crud
from app.utils.logger import setup_logger

logging = setup_logger()


def init_db_queues():
    """ 初始化队列，使用 multiprocessing.Manager """
    manager = Manager()
    return {
        'insert': manager.Queue(),
        'update': manager.Queue(),
    }


class ProcessingDB(Process):
    """
    使用多进程批量处理数据库**写**操作（插入/更新）。

    通过队列从主进程接收数据；按队列水位决定刷新频率，空闲时用
    ``stop_event.wait`` 轮询——``stop()`` 可立即唤醒并在退出前 flush 剩余任务。
    """

    def __init__(self, db_queues):
        super().__init__()
        self.db_insert_queue = db_queues['insert']
        self.db_update_queue = db_queues['update']
        self.stop_event = Event()  # 用于优雅地停止进程

    def _drain(self, queue, handler, label):
        """ 取空一个队列并把整批交给 handler（批量写库） """
        batch = []
        while not queue.empty():
            batch.append(queue.get())
        if batch:
            logging.info(f'{label} {len(batch)} records...')
            try:
                handler(batch)
            except Exception as e:
                logging.error(f"Error in db {label.lower()} worker: {e}")

    def flush(self):
        """ 落库当前所有待处理的插入与更新 """
        self._drain(self.db_insert_queue, crud.insert_multiple_characters_by_dict, 'Inserting')
        self._drain(self.db_update_queue, crud.update_multiple_characters_by_dict, 'Updating')

    def run(self):
        """ 监听队列并批量处理；停止时先 flush 再退出 """
        logging.info("Database processing started.")
        try:
            while not self.stop_event.is_set():
                pending = self.db_insert_queue.qsize() + self.db_update_queue.qsize()
                self.flush()
                if pending >= 1000:
                    interval = 0.1
                elif pending >= 100:
                    interval = 0.5
                else:
                    interval = 5.0
                self.stop_event.wait(interval)  # stop() 立即唤醒，无需 kill
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Stopping processing...")
        finally:
            self.flush()  # 退出前处理剩余任务
            logging.info("All remaining tasks have been processed.")

    def stop(self):
        """ 优雅停止：置标志并唤醒等待（退出前会 flush 剩余任务） """
        self.stop_event.set()
