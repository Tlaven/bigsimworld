class SinkQueue:
    """空队列：让引擎在没有真实 DB 写入进程时也能运行。"""

    def __init__(self):
        self.count = 0

    def put(self, item):
        self.count += 1

    def get(self):
        raise IndexError("SinkQueue is empty")

    def empty(self):
        return True

    def qsize(self):
        return 0
