# utils/redis_cache.py
import redis
import json
import hashlib
from functools import wraps
from flask import request

class RedisCache:
    def __init__(self, host='localhost', port=6379, db=0):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=5
        )
        self.default_timeout = 300  # 5分钟
    
    def get(self, key):
        """获取缓存"""
        try:
            data = self.client.get(key)
            return json.loads(data) if data else None
        except:
            return None
    
    def set(self, key, value, timeout=None):
        """设置缓存"""
        try:
            timeout = timeout or self.default_timeout
            self.client.setex(key, timeout, json.dumps(value, ensure_ascii=False))
            return True
        except:
            return False
    
    def delete(self, key):
        """删除缓存"""
        try:
            self.client.delete(key)
        except:
            pass
    
    def clear_pattern(self, pattern):
        """按模式清除缓存"""
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
        except:
            pass

# 创建全局实例
cache = RedisCache()

def cached(timeout=300, key_prefix='cache'):
    """缓存装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 生成缓存key
            cache_key = f"{key_prefix}:{request.path}:{hashlib.md5(str(request.args).encode()).hexdigest()}"
            
            # 尝试获取缓存
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # 执行原函数
            result = f(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, timeout)
            
            return result
        return decorated_function
    return decorator