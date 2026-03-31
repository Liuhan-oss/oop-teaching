# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 基础配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = True
    
    # ===== 数据库配置（MySQL）=====
    # 密码: Lxq7911051105
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:Lxq7911051105@localhost/oop_edu'
    
    # 连接池配置（重要！提高并发性能）
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,           # 连接池大小
        'pool_recycle': 3600,       # 连接回收时间（秒）
        'pool_pre_ping': True,      # 连接前测试
        'max_overflow': 20          # 最大溢出连接数
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT配置
    JWT_SECRET_KEY = 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = 7 * 24 * 60 * 60  # 7天
    
    # 文件上传
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    
    # 邮件配置
    MAIL_SERVER = 'smtp.163.com'
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = '18531321074@163.com'
    MAIL_PASSWORD = 'UTPBNMkgMer8SrFP'
    MAIL_DEFAULT_SENDER = '18531321074@163.com'
    
    # ==================== 智谱AI配置（统一使用免费模型）====================
    # 智谱AI API密钥
    ZHIPUAI_API_KEY = os.getenv('ZHIPUAI_API_KEY', "2e0af7231fec40f5a667adfd536537a7.L4F0x6GD0QYRT4zS")
    
    # 智谱AI API地址
    ZHIPUAI_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    # 使用的免费模型 - GLM-4.7-Flash（永久免费）
    # 2026年1月20日发布，替代GLM-4.5-Flash，完全免费
    ZHIPUAI_MODEL = "glm-4.7-flash"
    
    # 默认API调用参数
    ZHIPUAI_DEFAULT_TEMPERATURE = 0.7
    ZHIPUAI_DEFAULT_MAX_TOKENS = 2000
    ZHIPUAI_DEFAULT_TOP_P = 0.9
    ZHIPUAI_TIMEOUT = 30  # 请求超时时间（秒）
    
    # ==================== 缓存配置 ====================
    CACHE_TYPE = 'simple'  # 开发环境使用简单缓存
    CACHE_DEFAULT_TIMEOUT = 300  # 默认缓存时间5分钟
    
    # ==================== 跨域配置 ====================
    CORS_ORIGINS = ['http://localhost:5000', 'http://127.0.0.1:5000']
    CORS_SUPPORTS_CREDENTIALS = True
    
    # ==================== 日志配置 ====================
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'app.log'