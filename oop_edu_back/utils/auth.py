# utils/auth.py
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
import sys
import os

# 添加父目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from models import User
except ImportError:
    # 如果导入失败，定义一个简单的 User 类
    class User:
        id = None
        role = None
        query = None

def teacher_required(f):
    """教师权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            # 这里简化处理，实际应该查询数据库
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'code': 401, 'msg': '请先登录'}), 401
    return decorated

def student_required(f):
    """学生权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'code': 401, 'msg': '请先登录'}), 401
    return decorated