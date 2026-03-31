@echo off
echo 创建 utils 文件夹中的 Python 文件...

REM 创建 auth.py
echo from functools import wraps > utils\auth.py
echo from flask import request, jsonify >> utils\auth.py
echo from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity >> utils\auth.py
echo import sys >> utils\auth.py
echo import os >> utils\auth.py
echo. >> utils\auth.py
echo sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) >> utils\auth.py
echo. >> utils\auth.py
echo try: >> utils\auth.py
echo     from models import User >> utils\auth.py
echo except ImportError: >> utils\auth.py
echo     class User: >> utils\auth.py
echo         id = None >> utils\auth.py
echo         role = None >> utils\auth.py
echo         query = None >> utils\auth.py
echo. >> utils\auth.py
echo def teacher_required(f): >> utils\auth.py
echo     @wraps(f) >> utils\auth.py
echo     def decorated(*args, **kwargs): >> utils\auth.py
echo         try: >> utils\auth.py
echo             verify_jwt_in_request() >> utils\auth.py
echo             return f(*args, **kwargs) >> utils\auth.py
echo         except Exception as e: >> utils\auth.py
echo             return jsonify({'code': 401, 'msg': '请先登录'}), 401 >> utils\auth.py
echo     return decorated >> utils\auth.py
echo. >> utils\auth.py
echo def student_required(f): >> utils\auth.py
echo     @wraps(f) >> utils\auth.py
echo     def decorated(*args, **kwargs): >> utils\auth.py
echo         try: >> utils\auth.py
echo             verify_jwt_in_request() >> utils\auth.py
echo             return f(*args, **kwargs) >> utils\auth.py
echo         except Exception as e: >> utils\auth.py
echo             return jsonify({'code': 401, 'msg': '请先登录'}), 401 >> utils\auth.py
echo     return decorated >> utils\auth.py

REM 创建 ai_grader.py
echo import json > utils\ai_grader.py
echo import re >> utils\ai_grader.py
echo. >> utils\ai_grader.py
echo class AIGrader: >> utils\ai_grader.py
echo     def __init__(self): >> utils\ai_grader.py
echo         pass >> utils\ai_grader.py
echo. >> utils\ai_grader.py
echo     def grade_homework(self, question, answer, knowledge_point): >> utils\ai_grader.py
echo         return self._rule_based_grade(answer) >> utils\ai_grader.py
echo. >> utils\ai_grader.py
echo     def _rule_based_grade(self, answer): >> utils\ai_grader.py
echo         score = 60 >> utils\ai_grader.py
echo         suggestions = [] >> utils\ai_grader.py
echo         if re.search(r'class\s+\w+', answer): >> utils\ai_grader.py
echo             score += 10 >> utils\ai_grader.py
echo         else: >> utils\ai_grader.py
echo             suggestions.append("建议定义类") >> utils\ai_grader.py
echo         if re.search(r'def\s+\w+\s*\(', answer) or re.search(r'public\s+\w+\s+\w+\s*\(', answer): >> utils\ai_grader.py
echo             score += 10 >> utils\ai_grader.py
echo         else: >> utils\ai_grader.py
echo             suggestions.append("建议定义方法") >> utils\ai_grader.py
echo         if '{' in answer and '}' in answer: >> utils\ai_grader.py
echo             score += 5 >> utils\ai_grader.py
echo         else: >> utils\ai_grader.py
echo             suggestions.append("代码块需要完整") >> utils\ai_grader.py
echo         if re.search(r'return', answer): >> utils\ai_grader.py
echo             score += 5 >> utils\ai_grader.py
echo         score = min(100, score) >> utils\ai_grader.py
echo         return { >> utils\ai_grader.py
echo             'total_score': score, >> utils\ai_grader.py
echo             'dimensions': { >> utils\ai_grader.py
echo                 'syntax': min(30, score * 0.3), >> utils\ai_grader.py
echo                 'logic': min(30, score * 0.3), >> utils\ai_grader.py
echo                 'standard': min(20, score * 0.2), >> utils\ai_grader.py
echo                 'knowledge': min(20, score * 0.2) >> utils\ai_grader.py
echo             }, >> utils\ai_grader.py
echo             'feedback': f'评分完成，得分{score}分', >> utils\ai_grader.py
echo             'suggestions': suggestions[:3] >> utils\ai_grader.py
echo         } >> utils\ai_grader.py
echo. >> utils\ai_grader.py
echo ai_grader = AIGrader() >> utils\ai_grader.py

REM 创建 storage.py
echo import os > utils\storage.py
echo import uuid >> utils\storage.py
echo from datetime import datetime >> utils\storage.py
echo. >> utils\storage.py
echo class LocalStorage: >> utils\storage.py
echo     def __init__(self): >> utils\storage.py
echo         self.upload_folder = 'uploads' >> utils\storage.py
echo         os.makedirs(self.upload_folder, exist_ok=True) >> utils\storage.py
echo. >> utils\storage.py
echo     def upload_file(self, file_data, filename=None): >> utils\storage.py
echo         try: >> utils\storage.py
echo             ext = os.path.splitext(filename)[1] if filename else '' >> utils\storage.py
echo             new_filename = f"{uuid.uuid4().hex}{ext}" >> utils\storage.py
echo             date_path = datetime.now().strftime('%%Y/%%m/%%d') >> utils\storage.py
echo             save_dir = os.path.join(self.upload_folder, date_path) >> utils\storage.py
echo             os.makedirs(save_dir, exist_ok=True) >> utils\storage.py
echo             file_path = os.path.join(save_dir, new_filename) >> utils\storage.py
echo             with open(file_path, 'wb') as f: >> utils\storage.py
echo                 f.write(file_data) >> utils\storage.py
echo             return { >> utils\storage.py
echo                 'url': f'/uploads/{date_path}/{new_filename}', >> utils\storage.py
echo                 'path': file_path >> utils\storage.py
echo             } >> utils\storage.py
echo         except Exception as e: >> utils\storage.py
echo             print(f"保存失败: {e}") >> utils\storage.py
echo             return None >> utils\storage.py
echo. >> utils\storage.py
echo storage = LocalStorage() >> utils\storage.py

REM 创建 cache.py
echo import json > utils\cache.py
echo from datetime import datetime, timedelta >> utils\cache.py
echo. >> utils\cache.py
echo class SimpleCache: >> utils\cache.py
echo     def __init__(self): >> utils\cache.py
echo         self.cache = {} >> utils\cache.py
echo         self.timeouts = {} >> utils\cache.py
echo. >> utils\cache.py
echo     def get(self, key): >> utils\cache.py
echo         if key in self.cache: >> utils\cache.py
echo             if key in self.timeouts and datetime.now() ^> self.timeouts[key]: >> utils\cache.py
echo                 self.delete(key) >> utils\cache.py
echo                 return None >> utils\cache.py
echo             return self.cache[key] >> utils\cache.py
echo         return None >> utils\cache.py
echo. >> utils\cache.py
echo     def set(self, key, value, timeout=300): >> utils\cache.py
echo         self.cache[key] = value >> utils\cache.py
echo         if timeout: >> utils\cache.py
echo             self.timeouts[key] = datetime.now() + timedelta(seconds=timeout) >> utils\cache.py
echo. >> utils\cache.py
echo     def delete(self, key): >> utils\cache.py
echo         if key in self.cache: >> utils\cache.py
echo             del self.cache[key] >> utils\cache.py
echo         if key in self.timeouts: >> utils\cache.py
echo             del self.timeouts[key] >> utils\cache.py
echo. >> utils\cache.py
echo     def clear_pattern(self, pattern): >> utils\cache.py
echo         keys_to_delete = [k for k in self.cache.keys() if pattern in k] >> utils\cache.py
echo         for key in keys_to_delete: >> utils\cache.py
echo             self.delete(key) >> utils\cache.py
echo. >> utils\cache.py
echo cache = SimpleCache() >> utils\cache.py

REM 创建 cache_decorator.py
echo from functools import wraps > utils\cache_decorator.py
echo from flask import request >> utils\cache_decorator.py
echo import hashlib >> utils\cache_decorator.py
echo import json >> utils\cache_decorator.py
echo from .cache import cache >> utils\cache_decorator.py
echo. >> utils\cache_decorator.py
echo def cached(timeout=300, key_prefix='cache'): >> utils\cache_decorator.py
echo     def decorator(f): >> utils\cache_decorator.py
echo         @wraps(f) >> utils\cache_decorator.py
echo         def decorated_function(*args, **kwargs): >> utils\cache_decorator.py
echo             cache_key = f"{key_prefix}:{request.path}:{hashlib.md5(json.dumps(request.args.to_dict()).encode()).hexdigest()}" >> utils\cache_decorator.py
echo             cached_result = cache.get(cache_key) >> utils\cache_decorator.py
echo             if cached_result is not None: >> utils\cache_decorator.py
echo                 return cached_result >> utils\cache_decorator.py
echo             result = f(*args, **kwargs) >> utils\cache_decorator.py
echo             cache.set(cache_key, result, timeout) >> utils\cache_decorator.py
echo             return result >> utils\cache_decorator.py
echo         return decorated_function >> utils\cache_decorator.py
echo     return decorator >> utils\cache_decorator.py
echo. >> utils\cache_decorator.py
echo def clear_cache_by_prefix(prefix): >> utils\cache_decorator.py
echo     cache.clear_pattern(prefix) >> utils\cache_decorator.py

REM 创建 __init__.py
echo """Utils package for OOP education platform""" > utils\__init__.py
echo. >> utils\__init__.py
echo from .auth import teacher_required, student_required >> utils\__init__.py
echo from .ai_grader import ai_grader >> utils\__init__.py
echo from .storage import storage >> utils\__init__.py
echo from .cache import cache >> utils\__init__.py
echo from .cache_decorator import cached, clear_cache_by_prefix >> utils\__init__.py
echo. >> utils\__init__.py
echo __all__ = [ >> utils\__init__.py
echo     'teacher_required', >> utils\__init__.py
echo     'student_required', >> utils\__init__.py
echo     'ai_grader', >> utils\__init__.py
echo     'storage', >> utils\__init__.py
echo     'cache', >> utils\__init__.py
echo     'cached', >> utils\__init__.py
echo     'clear_cache_by_prefix' >> utils\__init__.py
echo ] >> utils\__init__.py

echo ✅ utils 文件夹所有文件创建完成！