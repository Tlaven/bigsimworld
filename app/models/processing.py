from multiprocessing import Process, Queue

from . import crud

from app.utils.decorators import time_limit


def init_db_queues():
    db_insert_queue = Queue()
    db_update_queue = Queue()
    db_delete_queue = Queue()

    return {'insert': db_insert_queue,
            'update': db_update_queue,
            'delete': db_delete_queue}


class ProcessingDB(Process):
    """
    利用多进程处理数据库任务
    通过队列获取任务，固定周期对任务进行汇总
    最后统一进行数据库操作
    """
    def __init__(self, db_queues):
        super().__init__()
        self.db_insert_queue = db_queues['insert']
        self.db_update_queue = db_queues['update']
        self.db_delete_queue = db_queues['delete']

    def db_insert_worker(self):
        insert_data = []
        while not self.db_insert_queue.empty():
            insert_data.append(self.db_insert_queue.get())
        if insert_data not in ([], None):
            crud.insert_multiple_characters(insert_data)

    def db_update_worker(self):
        update_data = []
        while not self.db_update_queue.empty():
            update_data.append(self.db_update_queue.get())
        if update_data not in ([], None):
            crud.update_multiple_characters(update_data)

    def db_delete_worker(self):
        delete_data = []
        while not self.db_delete_queue.empty():
            delete_data.append(self.db_delete_queue.get())
        if delete_data not in ([], None):
            crud.delete_multiple_characters(delete_data)

    @time_limit(10, "db_processing/10s")
    def step(self):
        self.db_insert_worker()
        self.db_update_worker()
        self.db_delete_worker()

    def run(self):
        try:
            while True:
                self.step()
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
        finally:
            while not self.db_insert_queue.empty():
                self.db_insert_queue.get()
            while not self.db_update_queue.empty():
                self.db_update_queue.get()
            while not self.db_delete_queue.empty():
                self.db_delete_queue.get()
