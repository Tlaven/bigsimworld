import time

from app.utils.cache import Cache


# 让函数调用的执行时间为指定时间,并更改负载情况
def time_limit(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                raise
            doing_time = time.time() - start_time
            Cache.add(func.__name__, doing_time/seconds)

            if doing_time < seconds:
                time.sleep(seconds - doing_time)
            else:
                print(f"Warning: {func.__name__} execution time exceeds the limit of {seconds} seconds.")
                
            return result

        return wrapper

    return decorator
