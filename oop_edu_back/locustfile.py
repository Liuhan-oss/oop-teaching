# locustfile.py
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """用户启动时登录"""
        self.login()
    
    def login(self):
        """登录"""
        response = self.client.post("/api/login", json={
            "username": "2024215612",
            "password": "123456",
            "role": "student"
        })
        if response.status_code == 200:
            self.token = response.json().get('data', {}).get('token')
    
    @task(3)
    def view_courses(self):
        """查看课程列表"""
        self.client.get("/api/course/list")
    
    @task(2)
    def view_videos(self):
        """查看视频列表"""
        self.client.get("/api/video/list")
    
    @task(1)
    def get_graph_data(self):
        """获取知识图谱"""
        self.client.get("/api/graph/data")
    
    @task(1)
    def check_files(self):
        """检查文件"""
        self.client.get("/api/check_files")