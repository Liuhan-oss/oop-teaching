# monitor.py
import psutil
import time
import requests

def monitor():
    """监控系统性能"""
    print("开始监控系统性能...")
    print("="*50)
    
    while True:
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用
        memory = psutil.virtual_memory()
        
        # 进程数
        process_count = len(psutil.pids())
        
        # 网络连接
        connections = len(psutil.net_connections())
        
        # 测试API响应
        try:
            start = time.time()
            r = requests.get('http://localhost:5000/api/check_files', timeout=2)
            response_time = (time.time() - start) * 1000
        except:
            response_time = -1
        
        print(f"CPU: {cpu_percent}% | 内存: {memory.percent}% | 进程: {process_count} | 连接: {connections} | API响应: {response_time:.0f}ms")
        
        time.sleep(5)

if __name__ == '__main__':
    monitor()