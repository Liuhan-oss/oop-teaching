# utils/cache.py
import json
from datetime import datetime, timedelta

class SimpleCache:
    """简单内存缓存"""
    
    def __init__(self):
        self.cache = {}
        self.timeouts = {}
    
    def get(self, key):
        """获取缓存"""
        if key in self.cache:
            if key in self.timeouts and datetime.now() > self.timeouts[key]:
                self.delete(key)
                return None
            return self.cache[key]
        return None
    
    def set(self, key, value, timeout=300):
        """设置缓存（timeout秒）"""
        self.cache[key] = value
        if timeout:
            self.timeouts[key] = datetime.now() + timedelta(seconds=timeout)
    
    def delete(self, key):
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timeouts:
            del self.timeouts[key]
    
    def clear_pattern(self, pattern):
        """清除匹配模式的缓存"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            self.delete(key)

# 创建全局实例
cache = SimpleCache()