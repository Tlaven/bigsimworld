import time
from collections import deque

from app.utils.cache import cache


# 让函数调用的执行时间为指定时间,并更改负载情况
def time_limit(seconds, record_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            if cache.get(record_name) is None:
                cache.set(record_name, deque([0], maxlen=60))
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                raise
            doing_time = time.time() - start_time
            new_record = cache.get(record_name)
            new_record.append(doing_time)
            cache.set(record_name, new_record)

            if doing_time < seconds:
                time.sleep(seconds - doing_time)
            return result

        return wrapper

    return decorator
