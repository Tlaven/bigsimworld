import time
from collections import deque

from app.utils.cache import py_cache
from app.utils.logger import setup_logger

logger = setup_logger()


# 把一个函数调用**节流**到至少 seconds 秒，并记录其耗时到 py_cache。
# 仅用于主进程/主线程（py_cache 为进程内共享；子进程不共享）。
def time_limit(seconds, record_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            if py_cache.get(record_name) is None:
                py_cache[record_name] = deque([0], maxlen=60)
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Error in {func.__name__}: {e}")
                raise
            doing_time = time.time() - start_time
            py_cache[record_name].append(doing_time)

            if doing_time < seconds:
                time.sleep(seconds - doing_time)
            return result

        return wrapper
    return decorator
