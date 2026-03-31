# start_simple.py
"""
最简单的 Waitress 启动脚本
用于测试基础性能
"""

from waitress import serve
from app import app
import os

# 确保日志目录存在
if not os.path.exists('logs'):
    os.makedirs('logs')

print("="*50)
print("🚀 启动 Waitress 服务器（简单配置版）")
print("="*50)
print("服务器信息:")
print(f"  - 地址: http://127.0.0.1:5000")
print(f"  - 线程数: 20")
print(f"  - 最大连接数: 1000")
print("="*50)
print("按 Ctrl+C 停止服务器")
print("="*50)

# 启动 Waitress - 最简单的配置
serve(
    app,
    host='127.0.0.1',
    port=5000,
    threads=20,           # 增加线程数
    connection_limit=1000,
    channel_timeout=300,
    cleanup_interval=30
)