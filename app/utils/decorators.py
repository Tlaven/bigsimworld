import time
import asyncio
from collections import deque

from app.utils.cache import py_cache


# 让函数调用的执行时间为指定时间,并更改负载情况
def time_limit(seconds, record_name):
    async def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            if py_cache.get(record_name) is None:
                py_cache[record_name] = deque([0], maxlen=60)
            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                raise
            doing_time = time.time() - start_time
            py_cache[record_name].append(doing_time)

            if doing_time < seconds:
                await asyncio.sleep(seconds - doing_time)
            return result

        return wrapper
    return decorator
