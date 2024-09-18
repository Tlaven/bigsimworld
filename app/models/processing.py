from multiprocessing import Process, Manager, Event

from . import crud
from app.utils.logger import setup_logger
from app.utils.decorators import time_limit

logging = setup_logger()

def init_db_queues():
    """ 初始化队列，使用 multiprocessing.Manager """
    manager = Manager()
    db_insert_queue = manager.Queue()
    db_update_queue = manager.Queue()
    db_delete_queue = manager.Queue()

    db_insert_queue.daemon = True
    db_update_queue.daemon = True
    db_delete_queue.daemon = True

    return {'insert': db_insert_queue,
            'update': db_update_queue,
            'delete': db_delete_queue}

class ProcessingDB(Process):
    """
    使用多进程来处理数据库操作任务。
    通过队列从主进程接收插入、更新、删除操作，并批量处理这些任务。
    """
    def __init__(self, db_queues):
        super().__init__()
        self.db_insert_queue = db_queues['insert']
        self.db_update_queue = db_queues['update']
        self.db_delete_queue = db_queues['delete']
        self.stop_event = Event()  # 用于优雅地停止进程

    def db_insert_worker(self):
        """ 批量处理插入操作 """
        insert_data = []
        while not self.db_insert_queue.empty():
            insert_data.append(self.db_insert_queue.get())
        if insert_data:
            logging.info(f'Inserting {len(insert_data)} records...')
            try:
                crud.insert_multiple_characters_by_dict(insert_data)
            except Exception as e:
                logging.error(f"Error in db_insert_worker: {e}")

    def db_update_worker(self):
        """ 批量处理更新操作 """
        update_data = []
        while not self.db_update_queue.empty():
            update_data.append(self.db_update_queue.get())
        if update_data:
            logging.info(f'Updating {len(update_data)} records...')
            try:
                crud.update_multiple_characters_by_dict(update_data)
            except Exception as e:
                logging.error(f"Error in db_update_worker: {e}")

    def db_delete_worker(self):
        """ 批量处理删除操作 """
        delete_data = []
        while not self.db_delete_queue.empty():
            delete_data.append(self.db_delete_queue.get())
        if delete_data:
            logging.info(f'Deleting {len(delete_data)} records...')
            try:
                crud.delete_multiple_characters(delete_data)
            except Exception as e:
                logging.error(f"Error in db_delete_worker: {e}")

    @time_limit(30, "db_processing/30s")
    def step30(self):
        """ 30秒周期的批量任务处理 """
        self.db_insert_worker()
        self.db_update_worker()
        self.db_delete_worker()

    @time_limit(10, "db_processing/10s")
    def step10(self):
        """ 10秒周期的批量任务处理 """
        self.db_insert_worker()
        self.db_update_worker()
        self.db_delete_worker()

    @time_limit(1, "db_processing/1s")
    def step1(self):
        """ 1秒周期的批量任务处理 """
        self.db_insert_worker()
        self.db_update_worker()
        self.db_delete_worker()

    def run(self):
        """ 运行数据库处理进程，监听队列并进行批量处理 """
        logging.info("Database processing started.")
        try:
            while not self.stop_event.is_set():
                db_queue_size = self.db_insert_queue.qsize() + self.db_update_queue.qsize() + self.db_delete_queue.qsize()
                
                if db_queue_size >= 1000:
                    logging.info(f"High load: Processing queue size {db_queue_size}")
                    self.step1()
                elif db_queue_size >= 100:
                    logging.info(f"Medium load: Processing queue size {db_queue_size}")
                    self.step10()
                else:
                    logging.info(f"Low load: Processing queue size {db_queue_size}")
                    self.step30()
                
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Stopping processing...")
            self.step1()  # 处理剩余的任务
        finally:
            self.cleanup()  # 确保退出前清理队列

    def stop(self):
        """ 用于优雅停止进程 """
        self.stop_event.set()

    def cleanup(self):
        """ 清理所有未处理的任务 """
        logging.info("Cleaning up remaining tasks...")
        self.step1()  # 处理剩余的任务
        self.clear_queue(self.db_insert_queue)
        self.clear_queue(self.db_update_queue)
        self.clear_queue(self.db_delete_queue)
        logging.info("All remaining tasks have been processed.")

    def clear_queue(self, queue):
        """ 清空队列中的剩余数据 """
        while not queue.empty():
            queue.get()
