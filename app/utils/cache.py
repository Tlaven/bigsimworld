"""进程内共享缓存。

用一把轻量锁封装 dict：仿真线程写、Flask 请求线程读，避免无同步竞态。
注意跨进程**不共享**（DB 写入另有自己的队列）。
"""

import threading


class ThreadSafeCache(dict):
    """带读写锁的 dict：``[]`` / ``get`` 读，``[]=`` / ``setdefault`` 写。"""

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def setdefault(self, key, default=None):
        with self._lock:
            return super().setdefault(key, default)


py_cache = ThreadSafeCache()
