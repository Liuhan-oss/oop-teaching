# waitress.conf.py
"""
Waitress配置文件 - Windows生产环境部署
位置：与 app.py 同一目录
"""

# 绑定地址和端口
host = "127.0.0.1"
port = 5000

# 线程数（建议 CPU核心数 * 2）
threads = 8

# 连接超时设置
connection_limit = 1000
channel_timeout = 300

# 日志设置
log_file = "./logs/waitress.log"  # 访问日志
log_level = "info"  # 日志级别

# 清理日志（避免磁盘满）
clear_untrusted_proxy_headers = True

# 输出配置信息
if __name__ == "__main__":
    print("="*50)
    print("Waitress配置文件")
    print(f"服务器将运行在: http://{host}:{port}")
    print(f"线程数: {threads}")
    print(f"最大连接数: {connection_limit}")
    print("="*50)