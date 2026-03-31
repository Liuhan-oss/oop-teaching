# start_waitress.py
from waitress import serve
from app import app
import os

# 确保日志目录存在
if not os.path.exists('logs'):
    os.makedirs('logs')

print("="*50)
print("🚀 启动OOP教学平台 - Waitress服务器")
print("="*50)
print("服务器信息:")
print("  - 地址: http://127.0.0.1:5000 (仅本机访问)")
print("  - 线程数: 8")
print("  - 最大连接数: 1000")
print("  - 日志文件: logs/waitress.log")
print("="*50)
print("Nginx 将在端口 80 提供外部服务")
print("访问地址: http://localhost")
print("="*50)

# 只监听本地，不对外暴露
serve(
    app,
    host='127.0.0.1',  # 只监听本地
    port=5000,
    threads=8,
    connection_limit=1000
)