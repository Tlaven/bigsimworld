from flask_caching import Cache

cache = Cache(config = {
    'CACHE_TYPE': 'redis',
    'CACHE_HOST': 'localhost',
    'CACHE_PORT': 6379,
})

py_cache = {}