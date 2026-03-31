# utils/cache_decorator.py
from functools import wraps
from flask import request
import hashlib
import json
from .cache import cache

def cached(timeout=300, key_prefix='cache'):
    """
    缓存装饰器
    :param timeout: 缓存时间（秒）
    :param key_prefix: 缓存key前缀
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 生成缓存key（基于请求路径和参数）
            cache_key = f"{key_prefix}:{request.path}:{hashlib.md5(json.dumps(request.args.to_dict()).encode()).hexdigest()}"
            
            # 尝试获取缓存
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行原函数
            result = f(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, timeout)
            
            return result
        return decorated_function
    return decorator

def clear_cache_by_prefix(prefix):
    """清除指定前缀的缓存"""
    cache.clear_pattern(prefix)