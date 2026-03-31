# utils/db_pool.py
"""
数据库连接池模块
"""

import sqlite3
from queue import Queue
import threading
import os
import logging

logger = logging.getLogger(__name__)

class SQLiteConnectionPool:
    """SQLite连接池"""
    
    def __init__(self, db_path, max_connections=10):
        self.db_path = db_path
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        self._create_connections()
    
    def _create_connections(self):
        """创建连接池"""
        for i in range(self.max_connections):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30)
                conn.row_factory = sqlite3.Row
                # 设置连接属性
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")  # 写前日志，提高并发
                conn.execute("PRAGMA synchronous = NORMAL")
                self.pool.put(conn)
                logger.debug(f"创建数据库连接 {i+1}/{self.max_connections}: {self.db_path}")
            except Exception as e:
                logger.error(f"创建数据库连接失败: {e}")
    
    def get_connection(self):
        """获取连接"""
        try:
            conn = self.pool.get(timeout=10)
            # 测试连接是否有效
            conn.execute("SELECT 1").fetchone()
            return conn
        except Exception as e:
            logger.error(f"获取数据库连接失败: {e}")
            # 创建新连接作为备用
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            return conn
    
    def return_connection(self, conn):
        """归还连接"""
        try:
            # 回滚未提交的事务
            conn.rollback()
            self.pool.put(conn, timeout=5)
        except Exception as e:
            logger.error(f"归还数据库连接失败: {e}")
            try:
                conn.close()
            except:
                pass
    
    def close_all(self):
        """关闭所有连接"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except:
                pass

# 全局连接池字典
db_pools = {}

def get_db_pool(db_name):
    """获取数据库连接池"""
    if db_name not in db_pools:
        # 获取数据库文件的绝对路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, db_name)
        db_pools[db_name] = SQLiteConnectionPool(db_path)
        logger.info(f"创建连接池: {db_name} -> {db_path}")
    return db_pools[db_name]

def close_all_pools():
    """关闭所有连接池"""
    for db_name, pool in db_pools.items():
        pool.close_all()
        logger.info(f"关闭连接池: {db_name}")