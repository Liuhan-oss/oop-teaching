import logging
import os
import sqlite3
import datetime
import json
import random
import time
from functools import wraps
import atexit
import requests
import base64

from utils.db_pool import get_db_pool, db_pools, close_all_pools
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from flask_mail import Mail, Message
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jieba
import jieba.analyse

# 添加路径到系统路径
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入新模块
from config import Config
from models import db

# 导入 utils 模块
try:
    from utils.auth import teacher_required, student_required
    from utils.ai_grader import ai_grader
    from utils.storage import storage
    from utils.cache import cache
    from utils.cache_decorator import cached, clear_cache_by_prefix
    from utils.ai_agent import AgentFactory
    print("✅ 成功导入 utils 模块")
except ImportError as e:
    print(f"⚠️ 警告: 导入utils模块失败: {e}")
    print("使用备用的简单装饰器...")
    
    from functools import wraps
    
    def teacher_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated
    
    def student_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated
    
    ai_grader = None
    
    class SimpleStorage:
        def upload_file(self, file_data, filename=None):
            return None
    
    storage = SimpleStorage()
    
    class SimpleCache:
        def get(self, key):
            return None
        def set(self, key, value, timeout=300):
            pass
        def delete(self, key):
            pass
    
    cache = SimpleCache()
    
    def cached(timeout=300):
        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated
        return decorator
    
    def clear_cache_by_prefix(prefix):
        pass


# ==================== 基础配置 ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(PROJECT_ROOT, 'pages')
UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'uploads')
COURSEWARE_DIR = os.path.join(PROJECT_ROOT, 'courseware')  # 课件存储目录

# 创建必要的目录
os.makedirs(PAGES_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COURSEWARE_DIR, exist_ok=True)

# 打印路径信息（用于调试）
print("="*50)
print(f"项目根目录: {PROJECT_ROOT}")
print(f"页面目录: {PAGES_DIR}")
print(f"上传目录: {UPLOAD_DIR}")
print(f"课件目录: {COURSEWARE_DIR}")
print("="*50)

# 检查页面文件是否存在
student_page = os.path.join(PAGES_DIR, 'student_index.html')
teacher_page = os.path.join(PAGES_DIR, 'teacher_index.html')
login_page = os.path.join(PAGES_DIR, 'login.html')

print(f"学生页面存在: {os.path.exists(student_page)} - {student_page}")
print(f"教师页面存在: {os.path.exists(teacher_page)} - {teacher_page}")
print(f"登录页面存在: {os.path.exists(login_page)} - {login_page}")
print("="*50)

app = Flask(__name__)
app.config.from_object(Config)

# 初始化扩展
CORS(app, supports_credentials=True)
db.init_app(app)
jwt = JWTManager(app)
mail = Mail(app)

app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB 最大上传大小

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================= 邮箱配置 =======================
reset_codes = {}

# ==================== 登录缓存 ====================
login_cache = {}
login_cache_time = {}
user_cache = {}

# ==================== PPT知识点定义 ====================
PPT_KNOWLEDGE_NODES = [
    # 第一章：C++语言编程入门
    {"id": "cpp_origin", "name": "C++语言产生", "category": 0, "size": 55, "difficulty": 1, "chapter": 1, "description": "由AT&T贝尔实验室Bjarne Stroustrup博士在C语言基础上开发"},
    {"id": "cpp_vs_c", "name": "C++与C语言关系", "category": 0, "size": 50, "difficulty": 1, "chapter": 1, "description": "C++兼容C语言，增加了面向对象特性"},
    {"id": "development_steps", "name": "开发步骤", "category": 0, "size": 45, "difficulty": 1, "chapter": 1, "description": "编辑→编译→链接→运行"},
    {"id": "program_composition", "name": "程序组成", "category": 0, "size": 48, "difficulty": 1, "chapter": 1, "description": "预处理指令、main函数、变量定义、语句序列、返回值"},
    {"id": "lexical_tokens", "name": "词法记号", "category": 0, "size": 52, "difficulty": 2, "chapter": 1, "description": "关键字、标识符、运算符、分隔符、常量、注释符"},
    {"id": "data_types", "name": "数据类型", "category": 0, "size": 60, "difficulty": 2, "chapter": 1, "description": "char、int、float、double、void"},
    {"id": "variables", "name": "变量", "category": 0, "size": 48, "difficulty": 2, "chapter": 1, "description": "声明格式：数据类型 变量名"},
    {"id": "constants", "name": "常量", "category": 0, "size": 45, "difficulty": 1, "chapter": 1, "description": "整型常量、字符常量、字符串常量、符号常量"},
    {"id": "arrays", "name": "数组", "category": 0, "size": 55, "difficulty": 2, "chapter": 1, "description": "一维、二维、多维数组，字符数组与字符串"},
    {"id": "operators", "name": "运算符", "category": 0, "size": 58, "difficulty": 2, "chapter": 1, "description": "算术、关系、逻辑、赋值、sizeof、条件运算符"},
    {"id": "expressions", "name": "表达式", "category": 0, "size": 50, "difficulty": 2, "chapter": 1, "description": "算术表达式、赋值表达式、逗号表达式"},
    {"id": "type_conversion", "name": "类型转换", "category": 0, "size": 42, "difficulty": 2, "chapter": 1, "description": "隐含转换、强制转换"},
    {"id": "control_statements", "name": "控制语句", "category": 0, "size": 56, "difficulty": 2, "chapter": 1, "description": "if、switch、while、do-while、for、break、continue"},
    
    # 第二章：函数
    {"id": "function_definition", "name": "函数定义", "category": 1, "size": 58, "difficulty": 2, "chapter": 2, "description": "类型、函数名、参数表、函数体"},
    {"id": "function_declaration", "name": "函数声明", "category": 1, "size": 52, "difficulty": 2, "chapter": 2, "description": "函数原型"},
    {"id": "function_call", "name": "函数调用", "category": 1, "size": 54, "difficulty": 2, "chapter": 2, "description": "实参、形参"},
    {"id": "parameter_passing", "name": "参数传递", "category": 1, "size": 56, "difficulty": 2, "chapter": 2, "description": "传值、传址"},
    {"id": "return_value", "name": "返回值", "category": 1, "size": 48, "difficulty": 1, "chapter": 2, "description": "return语句"},
    {"id": "inline_function", "name": "内联函数", "category": 1, "size": 42, "difficulty": 2, "chapter": 2, "description": "inline关键字"},
    {"id": "default_parameters", "name": "默认形参值", "category": 1, "size": 45, "difficulty": 2, "chapter": 2, "description": "从右向左设置默认值"},
    {"id": "scope", "name": "作用域", "category": 1, "size": 50, "difficulty": 2, "chapter": 2, "description": "全局、局部、块作用域、函数作用域"},
    {"id": "recursion", "name": "递归调用", "category": 1, "size": 55, "difficulty": 3, "chapter": 2, "description": "函数调用自身"},
    {"id": "function_overloading", "name": "函数重载", "category": 1, "size": 60, "difficulty": 3, "chapter": 2, "description": "参数列表不同，同名函数"},
    {"id": "system_functions", "name": "系统函数", "category": 1, "size": 40, "difficulty": 1, "chapter": 2, "description": "库函数"},
    
    # 第三章：类与对象
    {"id": "class_declaration", "name": "类的声明", "category": 2, "size": 65, "difficulty": 3, "chapter": 3, "description": "class、public、protected、private"},
    {"id": "object_declaration", "name": "对象的声明", "category": 2, "size": 58, "difficulty": 3, "chapter": 3, "description": "类名 对象名"},
    {"id": "constructor", "name": "构造函数", "category": 2, "size": 62, "difficulty": 3, "chapter": 3, "description": "与类同名、可重载、可设默认参数"},
    {"id": "destructor", "name": "析构函数", "category": 2, "size": 58, "difficulty": 3, "chapter": 3, "description": "~类名"},
    {"id": "class_composition", "name": "类的组合", "category": 2, "size": 55, "difficulty": 3, "chapter": 3, "description": "对象成员"},
    {"id": "static_members", "name": "静态成员", "category": 2, "size": 54, "difficulty": 3, "chapter": 3, "description": "static数据成员、static成员函数"},
    {"id": "friend", "name": "友元", "category": 2, "size": 50, "difficulty": 3, "chapter": 3, "description": "friend函数、friend类"},
    {"id": "const_object", "name": "常对象", "category": 2, "size": 48, "difficulty": 3, "chapter": 3, "description": "const对象"},
    {"id": "const_member", "name": "常数据成员", "category": 2, "size": 46, "difficulty": 3, "chapter": 3, "description": "const数据成员"},
    {"id": "class_scope", "name": "类作用域", "category": 2, "size": 52, "difficulty": 2, "chapter": 3, "description": "类内成员可见性"},
    {"id": "object_lifetime", "name": "对象生存期", "category": 2, "size": 50, "difficulty": 2, "chapter": 3, "description": "静态生存期、动态生存期"},
    {"id": "object_pointer", "name": "对象指针", "category": 2, "size": 54, "difficulty": 3, "chapter": 3, "description": "->、*"},
    
    # 第四章：指针与引用
    {"id": "pointer_declaration", "name": "指针声明", "category": 1, "size": 56, "difficulty": 3, "chapter": 4, "description": "数据类型 *标识符"},
    {"id": "pointer_operations", "name": "指针运算", "category": 1, "size": 52, "difficulty": 3, "chapter": 4, "description": "++、--、+、-"},
    {"id": "const_pointer", "name": "const指针", "category": 1, "size": 50, "difficulty": 3, "chapter": 4, "description": "指向常量的指针、指针常量"},
    {"id": "void_pointer", "name": "void指针", "category": 1, "size": 42, "difficulty": 3, "chapter": 4, "description": "通用指针类型"},
    {"id": "dynamic_memory", "name": "动态内存分配", "category": 1, "size": 58, "difficulty": 3, "chapter": 4, "description": "new、delete"},
    {"id": "array_pointer", "name": "数组指针", "category": 1, "size": 54, "difficulty": 3, "chapter": 4, "description": "指向数组的指针"},
    {"id": "pointer_array", "name": "指针数组", "category": 1, "size": 52, "difficulty": 3, "chapter": 4, "description": "存储指针的数组"},
    {"id": "pointer_parameter", "name": "指针作函数参数", "category": 1, "size": 56, "difficulty": 3, "chapter": 4, "description": "传址调用"},
    {"id": "pointer_return", "name": "返回指针的函数", "category": 1, "size": 50, "difficulty": 3, "chapter": 4, "description": "函数返回指针类型"},
    {"id": "string", "name": "字符串", "category": 1, "size": 48, "difficulty": 2, "chapter": 4, "description": "字符数组、字符串常量"},
    {"id": "reference", "name": "引用", "category": 1, "size": 54, "difficulty": 3, "chapter": 4, "description": "&，别名"},
    {"id": "reference_parameter", "name": "引用作函数参数", "category": 1, "size": 56, "difficulty": 3, "chapter": 4, "description": "避免拷贝，可修改实参"},
    {"id": "reference_return", "name": "返回引用的函数", "category": 1, "size": 52, "difficulty": 3, "chapter": 4, "description": "函数返回引用类型"},
    {"id": "linked_list", "name": "链表", "category": 1, "size": 60, "difficulty": 4, "chapter": 4, "description": "Node、List、插入、删除、排序"},
    
    # 第五章：继承
    {"id": "inheritance", "name": "继承", "category": 2, "size": 68, "difficulty": 4, "chapter": 5, "description": "基类、派生类"},
    {"id": "single_inheritance", "name": "单继承", "category": 2, "size": 62, "difficulty": 3, "chapter": 5, "description": "一个派生类只有一个基类"},
    {"id": "multiple_inheritance", "name": "多继承", "category": 2, "size": 65, "difficulty": 4, "chapter": 5, "description": "一个派生类有多个基类"},
    {"id": "public_derived", "name": "公有派生", "category": 2, "size": 58, "difficulty": 3, "chapter": 5, "description": "基类public→派生类public"},
    {"id": "private_derived", "name": "私有派生", "category": 2, "size": 56, "difficulty": 3, "chapter": 5, "description": "基类public→派生类private"},
    {"id": "protected_derived", "name": "保护派生", "category": 2, "size": 56, "difficulty": 3, "chapter": 5, "description": "基类public→派生类protected"},
    {"id": "derived_constructor", "name": "派生类构造函数", "category": 2, "size": 62, "difficulty": 4, "chapter": 5, "description": "调用顺序：基类→对象成员→派生类"},
    {"id": "derived_destructor", "name": "派生类析构函数", "category": 2, "size": 60, "difficulty": 4, "chapter": 5, "description": "调用顺序与构造函数相反"},
    {"id": "ambiguity", "name": "二义性问题", "category": 2, "size": 58, "difficulty": 4, "chapter": 5, "description": "同名成员、作用域分辨符::"},
    {"id": "virtual_base", "name": "虚基类", "category": 2, "size": 64, "difficulty": 5, "chapter": 5, "description": "virtual继承，解决菱形继承"},
    {"id": "assignment_compatibility", "name": "赋值兼容原则", "category": 2, "size": 54, "difficulty": 3, "chapter": 5, "description": "派生类对象→基类对象、指针、引用"},
    
    # 第六章：运算符重载
    {"id": "operator_overloading", "name": "运算符重载", "category": 2, "size": 66, "difficulty": 4, "chapter": 6, "description": "operator关键字"},
    {"id": "overloading_rules", "name": "重载规则", "category": 2, "size": 58, "difficulty": 4, "chapter": 6, "description": "不改变优先级、结合性、操作数个数"},
    {"id": "unary_operator", "name": "一元运算符重载", "category": 2, "size": 60, "difficulty": 4, "chapter": 6, "description": "++、--、-、!、~"},
    {"id": "binary_operator", "name": "二元运算符重载", "category": 2, "size": 62, "difficulty": 4, "chapter": 6, "description": "+、-、*、/"},
    {"id": "assignment_overload", "name": "赋值运算符重载", "category": 2, "size": 58, "difficulty": 4, "chapter": 6, "description": "="},
    {"id": "increment_overload", "name": "++/--重载", "category": 2, "size": 56, "difficulty": 4, "chapter": 6, "description": "前缀和后缀的区别"},
    {"id": "new_delete_overload", "name": "new/delete重载", "category": 2, "size": 54, "difficulty": 5, "chapter": 6, "description": "自定义内存管理"},
    {"id": "member_vs_friend", "name": "成员函数与友元函数", "category": 2, "size": 52, "difficulty": 3, "chapter": 6, "description": "重载方式的选择"},
    
    # 第七章：多态与虚函数
    {"id": "polymorphism", "name": "多态性", "category": 3, "size": 70, "difficulty": 5, "chapter": 7, "description": "编译时多态、运行时多态"},
    {"id": "static_binding", "name": "静态联编", "category": 3, "size": 58, "difficulty": 4, "chapter": 7, "description": "早期联编，编译时确定"},
    {"id": "dynamic_binding", "name": "动态联编", "category": 3, "size": 62, "difficulty": 5, "chapter": 7, "description": "晚期联编，运行时确定"},
    {"id": "virtual_function", "name": "虚函数", "category": 3, "size": 68, "difficulty": 5, "chapter": 7, "description": "virtual关键字"},
    {"id": "pure_virtual", "name": "纯虚函数", "category": 3, "size": 64, "difficulty": 5, "chapter": 7, "description": "virtual 函数名()=0"},
    {"id": "abstract_class", "name": "抽象类", "category": 3, "size": 66, "difficulty": 5, "chapter": 7, "description": "含纯虚函数的类，不能实例化"},
    {"id": "inclusion_polymorphism", "name": "包含多态", "category": 3, "size": 60, "difficulty": 5, "chapter": 7, "description": "基类指针指向派生类对象"},
    {"id": "overload_polymorphism", "name": "重载多态", "category": 3, "size": 58, "difficulty": 4, "chapter": 7, "description": "函数重载"},
    {"id": "coercion_polymorphism", "name": "强制转换多态", "category": 3, "size": 52, "difficulty": 4, "chapter": 7, "description": "类型转换"}
]

PPT_KNOWLEDGE_LINKS = [
    # 第一章内部链接
    {"source": "cpp_origin", "target": "cpp_vs_c", "relation": "对比"},
    {"source": "cpp_origin", "target": "development_steps", "relation": "包含"},
    {"source": "development_steps", "target": "program_composition", "relation": "产生"},
    {"source": "program_composition", "target": "lexical_tokens", "relation": "包括"},
    {"source": "lexical_tokens", "target": "data_types", "relation": "定义"},
    {"source": "data_types", "target": "variables", "relation": "声明"},
    {"source": "data_types", "target": "constants", "relation": "定义"},
    {"source": "data_types", "target": "arrays", "relation": "组合"},
    {"source": "arrays", "target": "operators", "relation": "操作"},
    {"source": "operators", "target": "expressions", "relation": "组成"},
    {"source": "expressions", "target": "type_conversion", "relation": "可能发生"},
    {"source": "type_conversion", "target": "control_statements", "relation": "用于"},
    
    # 第二章内部链接
    {"source": "function_definition", "target": "function_declaration", "relation": "区分"},
    {"source": "function_declaration", "target": "function_call", "relation": "调用"},
    {"source": "function_call", "target": "parameter_passing", "relation": "涉及"},
    {"source": "parameter_passing", "target": "return_value", "relation": "返回"},
    {"source": "function_definition", "target": "inline_function", "relation": "可优化为"},
    {"source": "function_declaration", "target": "default_parameters", "relation": "可设置"},
    {"source": "function_definition", "target": "scope", "relation": "定义在"},
    {"source": "function_definition", "target": "recursion", "relation": "可形成"},
    {"source": "function_overloading", "target": "function_definition", "relation": "多版本"},
    {"source": "system_functions", "target": "function_call", "relation": "可直接调用"},
    
    # 第三章内部链接
    {"source": "class_declaration", "target": "object_declaration", "relation": "实例化"},
    {"source": "class_declaration", "target": "constructor", "relation": "包含"},
    {"source": "class_declaration", "target": "destructor", "relation": "包含"},
    {"source": "class_declaration", "target": "class_composition", "relation": "可组合"},
    {"source": "class_declaration", "target": "static_members", "relation": "可声明"},
    {"source": "class_declaration", "target": "friend", "relation": "可声明"},
    {"source": "class_declaration", "target": "const_object", "relation": "可创建"},
    {"source": "class_declaration", "target": "const_member", "relation": "可包含"},
    {"source": "class_declaration", "target": "class_scope", "relation": "定义"},
    {"source": "object_declaration", "target": "object_lifetime", "relation": "具有"},
    {"source": "object_declaration", "target": "object_pointer", "relation": "可指向"},
    
    # 第四章内部链接
    {"source": "pointer_declaration", "target": "pointer_operations", "relation": "可进行"},
    {"source": "pointer_declaration", "target": "const_pointer", "relation": "可修饰为"},
    {"source": "pointer_declaration", "target": "void_pointer", "relation": "可声明为"},
    {"source": "pointer_declaration", "target": "dynamic_memory", "relation": "用于"},
    {"source": "pointer_declaration", "target": "array_pointer", "relation": "可指向"},
    {"source": "pointer_declaration", "target": "pointer_array", "relation": "可组成"},
    {"source": "pointer_declaration", "target": "pointer_parameter", "relation": "用作"},
    {"source": "pointer_declaration", "target": "pointer_return", "relation": "可返回"},
    {"source": "pointer_declaration", "target": "string", "relation": "可操作"},
    {"source": "reference", "target": "reference_parameter", "relation": "用作"},
    {"source": "reference", "target": "reference_return", "relation": "可返回"},
    {"source": "pointer_declaration", "target": "linked_list", "relation": "实现"},
    
    # 第五章内部链接
    {"source": "inheritance", "target": "single_inheritance", "relation": "分为"},
    {"source": "inheritance", "target": "multiple_inheritance", "relation": "分为"},
    {"source": "inheritance", "target": "public_derived", "relation": "可有"},
    {"source": "inheritance", "target": "private_derived", "relation": "可有"},
    {"source": "inheritance", "target": "protected_derived", "relation": "可有"},
    {"source": "inheritance", "target": "derived_constructor", "relation": "需要"},
    {"source": "inheritance", "target": "derived_destructor", "relation": "需要"},
    {"source": "multiple_inheritance", "target": "ambiguity", "relation": "可能产生"},
    {"source": "ambiguity", "target": "virtual_base", "relation": "解决用"},
    {"source": "inheritance", "target": "assignment_compatibility", "relation": "遵循"},
    
    # 第六章内部链接
    {"source": "operator_overloading", "target": "overloading_rules", "relation": "遵循"},
    {"source": "operator_overloading", "target": "unary_operator", "relation": "包括"},
    {"source": "operator_overloading", "target": "binary_operator", "relation": "包括"},
    {"source": "operator_overloading", "target": "assignment_overload", "relation": "包括"},
    {"source": "operator_overloading", "target": "increment_overload", "relation": "包括"},
    {"source": "operator_overloading", "target": "new_delete_overload", "relation": "包括"},
    {"source": "operator_overloading", "target": "member_vs_friend", "relation": "可选择"},
    
    # 第七章内部链接
    {"source": "polymorphism", "target": "static_binding", "relation": "实现"},
    {"source": "polymorphism", "target": "dynamic_binding", "relation": "实现"},
    {"source": "dynamic_binding", "target": "virtual_function", "relation": "需要"},
    {"source": "virtual_function", "target": "pure_virtual", "relation": "可声明为"},
    {"source": "pure_virtual", "target": "abstract_class", "relation": "定义"},
    {"source": "virtual_function", "target": "inclusion_polymorphism", "relation": "实现"},
    {"source": "polymorphism", "target": "overload_polymorphism", "relation": "包括"},
    {"source": "polymorphism", "target": "coercion_polymorphism", "relation": "包括"},
    
    # 跨章节链接
    {"source": "cpp_vs_c", "target": "function_definition", "relation": "支持"},
    {"source": "class_declaration", "target": "inheritance", "relation": "可继承"},
    {"source": "class_declaration", "target": "polymorphism", "relation": "支持"},
    {"source": "virtual_function", "target": "inheritance", "relation": "基于"},
    {"source": "abstract_class", "target": "inheritance", "relation": "常用于"},
    {"source": "pointer_declaration", "target": "dynamic_memory", "relation": "管理"},
    {"source": "reference", "target": "function_call", "relation": "用作参数"},
    {"source": "operator_overloading", "target": "class_declaration", "relation": "应用于"},
    {"source": "function_overloading", "target": "polymorphism", "relation": "是一种"}
]

# ==================== 工具函数 =====================
def get_db_connection(db_name: str) -> sqlite3.Connection:
    """
    获取数据库连接（使用连接池）
    
    参数:
        db_name: 数据库文件名
        
    返回:
        sqlite3.Connection 对象
    """
    try:
        pool = get_db_pool(db_name)
        return pool.get_connection()
    except Exception as e:
        logger.error(f"从连接池获取连接失败: {str(e)}")
        # 降级：直接创建连接
        conn = sqlite3.connect(db_name)
        conn.row_factory = sqlite3.Row
        return conn

def close_db_connection(conn: sqlite3.Connection) -> None:
    """
    归还连接到连接池
    
    参数:
        conn: 数据库连接对象
    """
    if not conn:
        return
    
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"提交数据库事务失败: {str(e)}")
    finally:
        # 标记是否已处理
        handled = False
        
        # 尝试归还到连接池
        for db_name, pool in db_pools.items():
            try:
                # 检查这个连接是否属于当前池
                if hasattr(pool, 'pool'):
                    try:
                        # 获取队列中的连接列表
                        queue_list = list(pool.pool.queue)
                        if conn in queue_list:
                            pool.return_connection(conn)
                            handled = True
                            break
                    except Exception as e:
                        logger.error(f"检查连接池队列时出错: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"处理连接池 {db_name} 时出错: {str(e)}")
                continue
        
        # 如果不在任何池中，直接关闭
        if not handled:
            try:
                logger.debug("连接不在池中，直接关闭")
                conn.close()
            except Exception as e:
                logger.error(f"关闭连接失败: {str(e)}")

def calculate_knowledge_mastery(student_name: str, knowledge_id: str) -> int:
    """计算学生知识点掌握度（基于错题记录）"""
    try:
        conn = get_db_connection('knowledge_mastery.db')
        if conn is None:
            return 70  # 默认掌握度
        
        c = conn.cursor()
        # 查询该知识点的错误次数
        c.execute('''SELECT error_count FROM knowledge_mastery 
                    WHERE student_name=? AND knowledge_id=?''', (student_name, knowledge_id))
        row = c.fetchone()
        close_db_connection(conn)
        
        if row:
            error_count = row[0]
            # 掌握度 = max(30, 100 - error_count * 10)
            mastery = max(30, 100 - error_count * 10)
            return mastery
        else:
            # 没有错误记录，默认掌握度70
            return 70
    except Exception as e:
        logger.error(f"计算掌握度失败: {str(e)}")
        return 70

def role_required(allowed_roles):
    """权限校验装饰器（兼容旧代码）"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == 'GET':
                role = request.args.get('role')
                username = request.args.get('username')
            else:
                data = request.get_json() or {}
                role = data.get('role')
                username = data.get('username')
            
            if not role or role not in allowed_roles:
                return jsonify({'code': 403, 'msg': '权限不足，仅允许' + ','.join(allowed_roles) + '访问'}), 403
            
            try:
                conn = get_db_connection('users.db')
                if conn is None:
                    return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
                c = conn.cursor()
                c.execute('SELECT 1 FROM sys_user WHERE username=? AND role=?', (username, role))
                if not c.fetchone():
                    close_db_connection(conn)
                    return jsonify({'code': 401, 'msg': '用户不存在或角色不匹配'}), 401
                close_db_connection(conn)
            except Exception as e:
                logger.error(f"权限校验失败: {str(e)}")
                return jsonify({'code': 500, 'msg': '权限校验异常'}), 500
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== 数据库优化 ====================
def optimize_database():
    """优化数据库性能 - 方案二：创建索引"""
    conn = None
    try:
        conn = get_db_connection('users.db')
        if conn is None:
            return
        c = conn.cursor()
        
        # 为 username 字段创建索引（大幅提升查询速度）
        c.execute('CREATE INDEX IF NOT EXISTS idx_username ON sys_user(username)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_role ON sys_user(role)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_username_role ON sys_user(username, role)')
        
        conn.commit()
        print("✅ 数据库索引创建成功")
    except Exception as e:
        logger.error(f"创建索引失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 数据库初始化 ====================
def init_knowledge_mastery() -> None:
    """初始化知识点掌握度表"""
    conn = None
    try:
        conn = get_db_connection('knowledge_mastery.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_mastery
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            knowledge_id TEXT,
            error_count INTEGER DEFAULT 0,
            last_error_time TEXT,
            UNIQUE(student_name, knowledge_id))''')
        conn.commit()
    except Exception as e:
        logger.error(f"初始化知识点掌握度表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_class() -> None:
    """初始化班级表"""
    conn = None
    try:
        conn = get_db_connection('class.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS class
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_username TEXT,
            class_name TEXT,
            class_code TEXT UNIQUE,
            course TEXT DEFAULT '',
            student_count INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS class_student
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            student_username TEXT,
            UNIQUE(class_id, student_username))''')
        conn.commit()
    except Exception as e:
        logger.error(f"初始化班级表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_user() -> None:
    """初始化用户表"""
    conn = None
    try:
        conn = get_db_connection('users.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sys_user
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, 
            password_hash TEXT, 
            role TEXT, 
            email TEXT,
            name TEXT DEFAULT '')''')
        # 初始化测试用户
        try:
            c.execute("INSERT OR IGNORE INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("2024215612", generate_password_hash("123456"), "student", "test@qq.com", "张三"))
            c.execute("INSERT OR IGNORE INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("2024215613", generate_password_hash("123456"), "student", "test@qq.com", "李四"))
            c.execute("INSERT OR IGNORE INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("T2024001", generate_password_hash("123456"), "teacher", "test@qq.com", "张老师"))
        except sqlite3.IntegrityError:
            pass
        conn.commit()
    except Exception as e:
        logger.error(f"初始化用户表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_notification() -> None:
    """初始化消息通知表"""
    conn = None
    try:
        conn = get_db_connection('notifications.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS notifications
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            content TEXT,
            type TEXT,
            is_read INTEGER DEFAULT 0,
            create_time TEXT)''')
        conn.commit()
    except Exception as e:
        logger.error(f"初始化通知表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_course() -> None:
    """初始化课程表"""
    conn = None
    try:
        conn = get_db_connection('courses.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS course
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, 
            filename TEXT, 
            knowledge_tags TEXT,
            hotwords TEXT DEFAULT '')''')
        try:
            c.execute("INSERT OR IGNORE INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("OOP三大特性详解", "oop_features.pdf", "封装,继承,多态", "类,对象,方法,属性"))
            c.execute("INSERT OR IGNORE INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("类与对象实战", "class_object.pdf", "类,对象,实例化", "构造函数,实例,属性"))
            c.execute("INSERT OR IGNORE INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("抽象类与接口", "abstract_interface.pdf", "抽象类,接口", "抽象,实现,多态"))
        except sqlite3.IntegrityError:
            pass
        conn.commit()
    except Exception as e:
        logger.error(f"初始化课程表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_homework() -> None:
    """初始化作业表"""
    conn = None
    try:
        conn = get_db_connection('homework.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS homework
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, 
            content TEXT, 
            knowledge_tag TEXT,
            class_id INTEGER,
            username TEXT,
            deadline TEXT,
            publish_time TEXT,
            hotwords TEXT DEFAULT '')''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS homework_submit
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER, 
            student_name TEXT, 
            answer TEXT, 
            is_correct INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            submit_time TEXT)''')
        conn.commit()
    except Exception as e:
        logger.error(f"初始化作业表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_courseware() -> None:
    """初始化课件表"""
    conn = None
    try:
        conn = get_db_connection('courseware.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS courseware
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_username TEXT,
            title TEXT,
            description TEXT,
            knowledge_tag TEXT,
            class_id TEXT,
            filename TEXT,
            filesize TEXT,
            file_path TEXT,
            upload_time TEXT)''')
        conn.commit()
        print("✅ 课件表初始化成功")
    except Exception as e:
        logger.error(f"初始化课件表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

def init_knowledge_graph() -> None:
    """初始化知识图谱表（基于PPT知识点）"""
    conn = None
    try:
        conn = get_db_connection('knowledge_graph.db')
        if conn is None:
            logger.error("无法获取数据库连接")
            return
        c = conn.cursor()
        
        # 创建知识点节点表
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_nodes
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT UNIQUE,
            name TEXT,
            category INTEGER,
            size INTEGER,
            difficulty INTEGER,
            chapter INTEGER,
            description TEXT)''')
        
        # 创建知识点关系表
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_links
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            target TEXT,
            relation TEXT,
            description TEXT,
            UNIQUE(source, target))''')
        
        # 初始化PPT知识点数据
        for node in PPT_KNOWLEDGE_NODES:
            c.execute('''INSERT OR IGNORE INTO knowledge_nodes 
                (node_id, name, category, size, difficulty, chapter, description) 
                VALUES (?,?,?,?,?,?,?)''',
                (node["id"], node["name"], node["category"], node["size"], 
                 node["difficulty"], node["chapter"], node["description"]))
        
        for link in PPT_KNOWLEDGE_LINKS:
            c.execute('''INSERT OR IGNORE INTO knowledge_links 
                (source, target, relation, description) 
                VALUES (?,?,?,?)''',
                (link["source"], link["target"], link["relation"], link.get("description", "")))
        
        conn.commit()
        print("✅ PPT知识图谱初始化完成")
    except Exception as e:
        logger.error(f"初始化知识图谱表失败: {str(e)}")
    finally:
        if conn:
            close_db_connection(conn)

# 执行所有表初始化
init_user()
init_course()
init_homework()
init_class()
init_knowledge_mastery()
init_notification()
init_knowledge_graph()
init_courseware()  # 新增课件表初始化

# 执行数据库优化（创建索引）
optimize_database()

# ==================== 静态文件路由 ====================
@app.route('/')
def index():
    """根路径重定向到登录页"""
    return redirect('/pages/login.html')

@app.route('/pages/<path:filename>')
def serve_page(filename):
    """提供页面文件服务"""
    try:
        if '..' in filename or filename.startswith('/'):
            return jsonify({'code': 400, 'msg': '非法路径'}), 400
        
        file_path = os.path.join(PAGES_DIR, filename)
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return jsonify({'code': 404, 'msg': f'页面不存在: {filename}'}), 404
        
        return send_from_directory(PAGES_DIR, filename)
    except Exception as e:
        logger.error(f"访问页面失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'服务器错误: {str(e)}'}), 500

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传文件服务"""
    try:
        return send_from_directory(UPLOAD_DIR, filename)
    except Exception as e:
        logger.error(f"访问上传文件失败: {str(e)}")
        return jsonify({'code': 404, 'msg': '文件不存在'}), 404

@app.route('/courseware/<path:filename>')
def serve_courseware(filename):
    """提供课件文件服务"""
    try:
        return send_from_directory(COURSEWARE_DIR, filename)
    except Exception as e:
        logger.error(f"访问课件文件失败: {str(e)}")
        return jsonify({'code': 404, 'msg': '文件不存在'}), 404

# ==================== JWT认证接口（新） ====================
@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """JWT登录（新接口）"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        conn = get_db_connection('users.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash, role, name FROM sys_user WHERE username=?', (username,))
        row = c.fetchone()
        close_db_connection(conn)
        
        if row and check_password_hash(row[2], password):
            # 生成JWT token
            access_token = create_access_token(identity=row[0])
            
            return jsonify({
                'code': 200,
                'data': {
                    'token': access_token,
                    'user': {
                        'id': row[0],
                        'username': row[1],
                        'role': row[3],
                        'name': row[4]
                    }
                }
            })
        return jsonify({'code': 400, 'msg': '用户名或密码错误'}), 400
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

# ==================== 调试路由 ====================
@app.route('/api/check_files', methods=['GET'])
@cached(timeout=60, key_prefix='check_files')
def check_files():
    """检查文件是否存在（调试用）"""
    files_to_check = {
        'pages/login.html': os.path.exists(os.path.join(PAGES_DIR, 'login.html')),
        'pages/student_index.html': os.path.exists(os.path.join(PAGES_DIR, 'student_index.html')),
        'pages/teacher_index.html': os.path.exists(os.path.join(PAGES_DIR, 'teacher_index.html')),
        'pages_dir_exists': os.path.exists(PAGES_DIR),
        'pages_dir': PAGES_DIR,
        'project_root': PROJECT_ROOT,
        'current_dir': os.getcwd()
    }
    
    return jsonify({
        'code': 200,
        'data': files_to_check
    })

# ==================== 教师班级接口 ====================
@app.route('/api/teacher/classes', methods=['POST'])
@role_required(['teacher'])
def teacher_classes():
    """获取教师创建的所有班级"""
    d = request.json or request.form
    teacher = d.get('username')
    conn = get_db_connection('class.db')
    if conn is None:
        return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
    c = conn.cursor()
    c.execute('SELECT id, class_name, student_count, course, class_code FROM class WHERE teacher_username=?', (teacher,))
    rows = c.fetchall()
    close_db_connection(conn)
    return jsonify([{'id': x[0], 'name': x[1], 'studentCount': x[2], 'course': x[3], 'inviteCode': x[4]} for x in rows])

# ==================== 知识图谱接口（基于PPT）====================
@app.route('/api/graph/data')
@cached(timeout=300, key_prefix='graph')
def get_graph_data():
    """获取PPT知识图谱数据"""
    conn = None
    try:
        conn = get_db_connection('knowledge_graph.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        # 获取所有节点
        c.execute('SELECT node_id, name, category, size, difficulty, chapter, description FROM knowledge_nodes')
        nodes = [{
            'id': row[0],
            'name': row[1], 
            'category': row[2], 
            'size': row[3], 
            'difficulty': row[4],
            'chapter': row[5],
            'description': row[6]
        } for row in c.fetchall()]
        
        # 获取所有链接
        c.execute('SELECT source, target, relation, description FROM knowledge_links')
        links = [{
            'source': row[0], 
            'target': row[1], 
            'name': row[2], 
            'desc': row[3]
        } for row in c.fetchall()]
        
        # 章节分类
        categories = [
            {'name': '第一章 基础入门'},
            {'name': '第二章 函数'},
            {'name': '第三章 类与对象'},
            {'name': '第四章 指针与引用'},
            {'name': '第五章 继承'},
            {'name': '第六章 运算符重载'},
            {'name': '第七章 多态与虚函数'}
        ]
        
        return jsonify({
            'code': 200,
            'data': {
                'nodes': nodes,
                'links': links,
                'categories': categories
            }
        })
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/student/knowledge_mastery', methods=['POST'])
@role_required(['student'])
def get_student_knowledge_mastery():
    """获取学生知识点掌握度（用于图谱染色）"""
    conn = None
    try:
        data = request.json
        student_name = data.get('student_name')
        
        conn = get_db_connection('knowledge_mastery.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        # 获取所有知识点的掌握度
        c.execute('''SELECT knowledge_id, error_count FROM knowledge_mastery 
                     WHERE student_name=?''', (student_name,))
        mastery_records = {row[0]: row[1] for row in c.fetchall()}
        
        # 计算每个知识点的掌握度（0-100）
        result = {}
        for node in PPT_KNOWLEDGE_NODES:
            node_id = node["id"]
            if node_id in mastery_records:
                error_count = mastery_records[node_id]
                # 掌握度 = max(30, 100 - error_count * 8)
                mastery = max(30, 100 - error_count * 8)
            else:
                mastery = 70  # 默认掌握度
            result[node_id] = mastery
        
        return jsonify({'code': 200, 'data': result})
    except Exception as e:
        logger.error(f"获取学生知识点掌握度失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/update_knowledge_mastery', methods=['POST'])
def update_knowledge_mastery():
    """更新学生知识点掌握度（作业错误时调用）"""
    conn = None
    try:
        data = request.json
        student_name = data.get('student_name')
        knowledge_id = data.get('knowledge_id')
        
        conn = get_db_connection('knowledge_mastery.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 更新或插入错误记录
        c.execute('''INSERT INTO knowledge_mastery 
                     (student_name, knowledge_id, error_count, last_error_time)
                     VALUES (?,?,1,?)
                     ON CONFLICT(student_name, knowledge_id) 
                     DO UPDATE SET error_count = error_count + 1, last_error_time = ?''',
                  (student_name, knowledge_id, now, now))
        
        conn.commit()
        
        return jsonify({'code': 200, 'msg': '知识点掌握度更新成功'})
    except Exception as e:
        logger.error(f"更新知识点掌握度失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/student/personalized_recommend', methods=['POST'])
@role_required(['student'])
def get_personalized_recommend():
    """获取个性化推荐（基于薄弱知识点）"""
    conn_mastery = None
    conn_video = None
    conn_course = None
    
    try:
        data = request.json
        student_name = data.get('student_name')
        
        conn_mastery = get_db_connection('knowledge_mastery.db')
        if conn_mastery is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c_mastery = conn_mastery.cursor()
        
        # 获取学生薄弱知识点（错误次数最多的5个）
        c_mastery.execute('''SELECT knowledge_id, error_count FROM knowledge_mastery 
                             WHERE student_name=? AND error_count > 0
                             ORDER BY error_count DESC LIMIT 5''', (student_name,))
        weak_records = c_mastery.fetchall()
        
        weak_points = []
        for record in weak_records:
            # 获取知识点名称
            node = next((n for n in PPT_KNOWLEDGE_NODES if n["id"] == record[0]), None)
            if node:
                weak_points.append({
                    'id': record[0],
                    'name': node["name"],
                    'count': record[1]
                })
        
        # 如果没有薄弱点，使用默认推荐
        if not weak_points:
            weak_points = [
                {'id': 'virtual_function', 'name': '虚函数', 'count': 3},
                {'id': 'polymorphism', 'name': '多态性', 'count': 2},
                {'id': 'inheritance', 'name': '继承', 'count': 1}
            ]
        
        # 推荐视频（根据薄弱知识点）
        conn_video = get_db_connection('videos.db')
        if conn_video is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c_video = conn_video.cursor()
        recommend_videos = []
        
        for wp in weak_points[:3]:
            c_video.execute('''SELECT id, title, description, knowledge_tag, filename 
                               FROM videos WHERE knowledge_tag LIKE ? 
                               ORDER BY upload_time DESC LIMIT 3''', (f'%{wp["name"]}%',))
            videos = c_video.fetchall()
            for video in videos:
                recommend_videos.append({
                    'id': video[0],
                    'title': video[1],
                    'description': video[2],
                    'knowledge_tag': video[3],
                    'filename': video[4],
                    'reason': f'针对「{wp["name"]}」薄弱点的教学视频',
                    'priority': wp['count']
                })
        
        # 推荐课程（根据薄弱知识点）
        conn_course = get_db_connection('courses.db')
        if conn_course is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c_course = conn_course.cursor()
        recommend_courses = []
        
        for wp in weak_points[:3]:
            c_course.execute('''SELECT id, name, knowledge_tags, hotwords 
                               FROM course WHERE knowledge_tags LIKE ? 
                               LIMIT 3''', (f'%{wp["name"]}%',))
            courses = c_course.fetchall()
            for course in courses:
                recommend_courses.append({
                    'id': course[0],
                    'name': course[1],
                    'knowledge_tags': course[2],
                    'hotwords': course[3].split(',') if course[3] else [],
                    'reason': f'针对「{wp["name"]}」薄弱点的专项课程',
                    'priority': wp['count']
                })
        
        # 去重并排序
        unique_videos = []
        seen_videos = set()
        for video in sorted(recommend_videos, key=lambda x: -x['priority']):
            if video['title'] not in seen_videos:
                unique_videos.append(video)
                seen_videos.add(video['title'])
        
        unique_courses = []
        seen_courses = set()
        for course in sorted(recommend_courses, key=lambda x: -x['priority']):
            if course['name'] not in seen_courses:
                unique_courses.append(course)
                seen_courses.add(course['name'])
        
        return jsonify({
            'code': 200,
            'data': {
                'weak_points': weak_points,
                'recommend_videos': unique_videos[:5],
                'recommend_courses': unique_courses[:5]
            }
        })
    except Exception as e:
        logger.error(f"获取个性化推荐失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn_mastery:
            close_db_connection(conn_mastery)
        if conn_video:
            close_db_connection(conn_video)
        if conn_course:
            close_db_connection(conn_course)

# ==================== NLP热词提取接口 ====================
@app.route('/api/nlp/extract_hotwords', methods=['POST'])
def extract_hotwords():
    """提取文本热词"""
    try:
        data = request.json
        text = data.get('text', '')
        top_k = data.get('top_k', 10)
        
        if not text:
            return jsonify({'code': 400, 'msg': '文本不能为空'})
        
        # 使用jieba提取关键词
        keywords = jieba.analyse.textrank(text, topK=top_k, withWeight=True, allowPOS=('n', 'vn', 'v', 'nz'))
        
        hotwords = [{'word': k, 'weight': round(w * 100, 2)} for k, w in keywords]
        
        return jsonify({'code': 200, 'data': hotwords})
    except Exception as e:
        logger.error(f"提取热词失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

# ==================== 用户认证接口（旧，兼容前端）====================
@app.route('/api/login', methods=['POST'])
def login():
    """用户登录（兼容旧前端）"""
    try:
        d = request.json
        u = d.get('username')
        p = d.get('password')
        r = d.get('role')
        
        if not all([u, p, r]):
            return jsonify({'code':400, 'msg': '账号/密码/角色不能为空'})
        
        # 检查登录缓存
        cache_key = f"{u}_{p}_{r}"
        if cache_key in login_cache:
            cache_time, cache_result = login_cache[cache_key]
            if time.time() - cache_time < 5:
                return cache_result
        
        # 检查用户信息缓存
        user_cache_key = f"{u}_{r}"
        if user_cache_key in user_cache:
            cached_pwd_hash, cached_name = user_cache[user_cache_key]
            if check_password_hash(cached_pwd_hash, p):
                result = jsonify({'code':200, 'data': {'username': u, 'role': r, 'name': cached_name}})
                login_cache[cache_key] = (time.time(), result)
                return result
        
        # 数据库查询
        conn = get_db_connection('users.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('SELECT password_hash, name FROM sys_user WHERE username=? AND role=?', (u, r))
        row = c.fetchone()
        close_db_connection(conn)
        
        if row and check_password_hash(row[0], p):
            user_cache[user_cache_key] = (row[0], row[1])
            result = jsonify({'code':200, 'data': {'username': u, 'role': r, 'name': row[1]}})
            login_cache[cache_key] = (time.time(), result)
            return result
        
        result = jsonify({'code':400, 'msg': '账号或密码错误'})
        return result
        
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'登录失败: {str(e)}'}), 500

@app.route('/api/register', methods=['POST'])
def reg():
    """用户注册"""
    conn = None
    try:
        d = request.json
        u = d.get('username')
        p = d.get('password')
        r = d.get('role')
        name = d.get('name', u)
        e = d.get('email', '')
        
        if not all([u, p, r]):
            return jsonify({'code':400, 'msg': '账号/密码/角色不能为空'})
        
        conn = get_db_connection('users.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('INSERT INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)',
            (u, generate_password_hash(p), r, e, name))
        conn.commit()
        
        # 注册成功后清除相关缓存
        cache_keys = [k for k in user_cache.keys() if k.startswith(f"{u}_")]
        for k in cache_keys:
            user_cache.pop(k, None)
        
        return jsonify({'code':200, 'msg': '注册成功', 'data': {'username': u, 'role': r, 'name': name}})
    except sqlite3.IntegrityError:
        return jsonify({'code':400, 'msg': '账号已存在'})
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'注册失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 课程接口 ====================
@app.route('/api/course/list')
@cached(timeout=60, key_prefix='course')
def clist():
    """获取课程列表"""
    conn = None
    try:
        conn = get_db_connection('courses.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('SELECT id, name, filename, knowledge_tags, hotwords FROM course')
        rows = c.fetchall()
        return jsonify([{
            'id': x[0],
            'name': x[1],
            'filename': x[2],
            'knowledge_tags': x[3],
            'hotwords': x[4].split(',') if x[4] else []
        } for x in rows])
    except Exception as e:
        logger.error(f"获取课程列表失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取课程列表失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/course/upload', methods=['POST'])
@role_required(['teacher'])
def upload_course():
    """上传课程"""
    conn = None
    try:
        name = request.form.get('name')
        tags = request.form.get('knowledge_tags', '')
        f = request.files.get('file')
        
        if not name:
            return jsonify({'code':400, 'msg': '课程名称不能为空'})
        if not f:
            return jsonify({'code':400, 'msg': '请选择文件'})
            
        fn = secure_filename(f.filename)
        f.save(os.path.join(UPLOAD_DIR, fn))
        
        conn = get_db_connection('courses.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('INSERT INTO course (name, filename, knowledge_tags) VALUES (?,?,?)', (name, fn, tags))
        conn.commit()
        return jsonify({'code':200, 'msg': '上传成功'})
    except Exception as e:
        logger.error(f"上传课程失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'上传课程失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 课件管理接口 ====================
@app.route('/api/courseware/upload', methods=['POST'])
@role_required(['teacher'])
def upload_courseware():
    """教师上传课件"""
    conn = None
    try:
        teacher = request.form.get('username')
        title = request.form.get('title')
        description = request.form.get('description', '')
        knowledge_tag = request.form.get('knowledge_tag', '')
        class_id = request.form.get('class_id', '')
        file = request.files.get('file')
        
        if not teacher or not title or not file:
            return jsonify({'code': 400, 'msg': '参数不完整'}), 400
        
        # 保存文件
        original_filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{original_filename}"
        file_path = os.path.join(COURSEWARE_DIR, filename)
        file.save(file_path)
        
        # 获取文件大小
        filesize = os.path.getsize(file_path)
        filesize_str = f"{filesize / 1024:.2f} KB" if filesize < 1024 * 1024 else f"{filesize / (1024 * 1024):.2f} MB"
        
        # 读取文件为Base64（用于前端预览）
        with open(file_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')
        
        # 根据文件类型添加data URL前缀
        if original_filename.endswith('.pdf'):
            file_data = f"data:application/pdf;base64,{file_data}"
        elif original_filename.endswith('.ppt') or original_filename.endswith('.pptx'):
            file_data = f"data:application/vnd.ms-powerpoint;base64,{file_data}"
        elif original_filename.endswith('.doc') or original_filename.endswith('.docx'):
            file_data = f"data:application/msword;base64,{file_data}"
        elif original_filename.endswith('.txt') or original_filename.endswith('.md'):
            file_data = f"data:text/plain;base64,{file_data}"
        else:
            file_data = f"data:application/octet-stream;base64,{file_data}"
        
        upload_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存到数据库
        conn = get_db_connection('courseware.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('''INSERT INTO courseware 
                     (teacher_username, title, description, knowledge_tag, class_id, 
                      filename, filesize, file_path, upload_time)
                     VALUES (?,?,?,?,?,?,?,?,?)''',
                  (teacher, title, description, knowledge_tag, class_id,
                   original_filename, filesize_str, filename, upload_time))
        courseware_id = c.lastrowid
        conn.commit()
        
        # 返回课件数据（包含Base64用于前端预览）
        courseware_data = {
            'id': courseware_id,
            'title': title,
            'description': description,
            'knowledge_tag': knowledge_tag,
            'class_id': class_id,
            'fileName': original_filename,
            'fileSize': filesize_str,
            'fileData': file_data,
            'uploadTime': upload_time
        }
        
        # 如果是特定班级，发送通知给学生
        if class_id and class_id != 'all':
            conn_class = get_db_connection('class.db')
            if conn_class:
                c_class = conn_class.cursor()
                c_class.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
                students = [row[0] for row in c_class.fetchall()]
                close_db_connection(conn_class)
                
                conn_notify = get_db_connection('notifications.db')
                if conn_notify:
                    c_notify = conn_notify.cursor()
                    for student in students:
                        c_notify.execute('''INSERT INTO notifications 
                                           (username, title, content, type, is_read, create_time) 
                                           VALUES (?,?,?,?,?,?)''',
                                        (student, '📚 新课件发布', 
                                         f'老师发布了新课件《{title}》，知识点：{knowledge_tag}', 
                                         'courseware', 0, upload_time))
                    conn_notify.commit()
                    close_db_connection(conn_notify)
        
        return jsonify({
            'code': 200,
            'msg': '上传成功',
            'data': courseware_data
        })
        
    except Exception as e:
        logger.error(f"上传课件失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/courseware/list', methods=['POST'])
def get_courseware_list():
    """获取课件列表（教师或学生）"""
    conn = None
    try:
        data = request.json
        role = data.get('role')
        username = data.get('username')
        class_id = data.get('class_id')
        
        conn = get_db_connection('courseware.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        if role == 'teacher':
            # 教师获取自己上传的所有课件
            c.execute('''SELECT id, title, description, knowledge_tag, class_id, 
                               filename, filesize, file_path, upload_time
                        FROM courseware 
                        WHERE teacher_username=?
                        ORDER BY upload_time DESC''', (username,))
        else:
            # 学生获取可见的课件
            # 如果没有传 class_id，尝试从数据库获取
            if not class_id and username:
                # 尝试获取学生班级ID
                conn_class = get_db_connection('class.db')
                if conn_class:
                    c_class = conn_class.cursor()
                    c_class.execute('''SELECT c.id
                                       FROM class c
                                       JOIN class_student cs ON c.id = cs.class_id
                                       WHERE cs.student_username=?''', (username,))
                    class_row = c_class.fetchone()
                    if class_row:
                        class_id = class_row[0]
                    close_db_connection(conn_class)
            
            if class_id:
                # 有班级ID，获取该班级的课件 + 全部班级的课件
                c.execute('''SELECT id, title, description, knowledge_tag, class_id, 
                                   filename, filesize, file_path, upload_time
                            FROM courseware 
                            WHERE class_id=? OR class_id='' OR class_id IS NULL OR class_id='all'
                            ORDER BY upload_time DESC''', (class_id,))
            else:
                # 没有班级ID，只获取全部班级的课件
                c.execute('''SELECT id, title, description, knowledge_tag, class_id, 
                                   filename, filesize, file_path, upload_time
                            FROM courseware 
                            WHERE class_id='' OR class_id IS NULL OR class_id='all'
                            ORDER BY upload_time DESC''')
        
        rows = c.fetchall()
        
        courseware_list = []
        for row in rows:
            # 读取文件内容为Base64
            file_path = os.path.join(COURSEWARE_DIR, row[6])
            file_data = None
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    file_data = base64.b64encode(f.read()).decode('utf-8')
                    # 添加data URL前缀
                    filename = row[5]
                    if filename.endswith('.pdf'):
                        file_data = f"data:application/pdf;base64,{file_data}"
                    elif filename.endswith('.ppt') or filename.endswith('.pptx'):
                        file_data = f"data:application/vnd.ms-powerpoint;base64,{file_data}"
                    elif filename.endswith('.doc') or filename.endswith('.docx'):
                        file_data = f"data:application/msword;base64,{file_data}"
                    elif filename.endswith('.txt') or filename.endswith('.md'):
                        file_data = f"data:text/plain;base64,{file_data}"
                    else:
                        file_data = f"data:application/octet-stream;base64,{file_data}"
            
            courseware_list.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'knowledge_tag': row[3],
                'class_id': row[4],
                'fileName': row[5],
                'fileSize': row[6],
                'fileData': file_data,
                'uploadTime': row[8]
            })
        
        return jsonify({
            'code': 200,
            'data': courseware_list
        })
        
    except Exception as e:
        logger.error(f"获取课件列表失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/courseware/delete', methods=['POST'])
@role_required(['teacher'])
def delete_courseware():
    """删除课件"""
    conn = None
    try:
        data = request.json
        courseware_id = data.get('courseware_id')
        teacher = data.get('username')
        
        if not courseware_id:
            return jsonify({'code': 400, 'msg': '课件ID不能为空'}), 400
        
        conn = get_db_connection('courseware.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        # 获取文件路径
        c.execute('SELECT file_path, teacher_username FROM courseware WHERE id=?', (courseware_id,))
        row = c.fetchone()
        if not row:
            return jsonify({'code': 404, 'msg': '课件不存在'}), 404
        
        if row[1] != teacher:
            return jsonify({'code': 403, 'msg': '无权删除此课件'}), 403
        
        # 删除文件
        file_path = os.path.join(COURSEWARE_DIR, row[0])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除数据库记录
        c.execute('DELETE FROM courseware WHERE id=?', (courseware_id,))
        conn.commit()
        
        return jsonify({'code': 200, 'msg': '删除成功'})
        
    except Exception as e:
        logger.error(f"删除课件失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/courseware/preview', methods=['POST'])
def preview_courseware():
    """预览课件（获取文件内容）"""
    conn = None
    try:
        data = request.json
        courseware_id = data.get('courseware_id')
        
        if not courseware_id:
            return jsonify({'code': 400, 'msg': '课件ID不能为空'}), 400
        
        conn = get_db_connection('courseware.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        c.execute('SELECT file_path, filename FROM courseware WHERE id=?', (courseware_id,))
        row = c.fetchone()
        if not row:
            return jsonify({'code': 404, 'msg': '课件不存在'}), 404
        
        file_path = os.path.join(COURSEWARE_DIR, row[0])
        if not os.path.exists(file_path):
            return jsonify({'code': 404, 'msg': '文件不存在'}), 404
        
        # 返回文件
        return send_from_directory(COURSEWARE_DIR, row[0])
        
    except Exception as e:
        logger.error(f"预览课件失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 作业接口 ====================
@app.route('/api/homework/publish', methods=['POST'])
@role_required(['teacher'])
def hw_pub():
    """发布作业"""
    conn = None
    conn_class = None
    conn_notify = None
    try:
        d = request.json
        title = d.get('title')
        content = d.get('content')
        tag = d.get('knowledge_tag', '')
        class_id = d.get('class_id')
        username = d.get('username')
        deadline = d.get('deadline', '')
        
        if not title or not content:
            return jsonify({'code':400, 'msg': '作业标题和内容不能为空'})
        
        publish_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 提取作业热词
        keywords = jieba.analyse.textrank(content, topK=10, withWeight=True, allowPOS=('n', 'vn', 'v'))
        hotwords = ','.join([k for k, _ in keywords])
        
        conn = get_db_connection('homework.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('''INSERT INTO homework (title, content, knowledge_tag, class_id, username, deadline, publish_time, hotwords) 
                     VALUES (?,?,?,?,?,?,?,?)''',
            (title, content, tag, class_id, username, deadline, publish_time, hotwords))
        homework_id = c.lastrowid
        conn.commit()
        
        # 发送通知
        if class_id and class_id != 'all':
            conn_class = get_db_connection('class.db')
            if conn_class is None:
                return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
            c_class = conn_class.cursor()
            c_class.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
            students = [row[0] for row in c_class.fetchall()]
            
            conn_notify = get_db_connection('notifications.db')
            if conn_notify is None:
                return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
            c_notify = conn_notify.cursor()
            for student in students:
                c_notify.execute('''INSERT INTO notifications (username, title, content, type, is_read, create_time) 
                                   VALUES (?,?,?,?,?,?)''',
                    (student, '📢 新作业发布', f'老师发布了新作业《{title}》，核心知识点：{tag}', 'homework', 0, publish_time))
            conn_notify.commit()
        
        return jsonify({'code':200, 'msg': '作业发布成功', 'data': {'id': homework_id, 'hotwords': hotwords.split(',')}})
    except Exception as e:
        logger.error(f"发布作业失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'发布作业失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)
        if conn_class:
            close_db_connection(conn_class)
        if conn_notify:
            close_db_connection(conn_notify)

@app.route('/api/homework/submit', methods=['POST'])
@role_required(['student'])
def hw_sub():
    """提交作业"""
    conn = None
    conn_problem = None
    conn_hw = None
    try:
        d = request.json or request.form
        hw_id = d.get('homework_id')
        answer = d.get('answer')
        student = d.get('student_name', '学生')
        is_correct = d.get('is_correct', 0)
        score = d.get('score', 0)
        knowledge_points = d.get('knowledge_points', [])  # 相关知识点列表

        if not hw_id or not answer:
            return jsonify({'code':400, 'msg': '作业ID和答案不能为空'})

        submit_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection('homework.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('''INSERT INTO homework_submit (homework_id, student_name, answer, is_correct, score, submit_time) 
                     VALUES (?,?,?,?,?,?)''',
            (hw_id, student, answer, is_correct, score, submit_time))

        # 记录错题并更新知识点掌握度
        if is_correct == 0 or score < 60:  # 60分以下视为错误
            # 获取作业关联的知识点
            c.execute('SELECT knowledge_tag FROM homework WHERE id=?', (hw_id,))
            tag_row = c.fetchone()
            tag = tag_row[0] if tag_row else ''
            
            tags = tag.split(',') if tag else []
            # 合并传入的知识点列表
            if knowledge_points:
                tags.extend(knowledge_points)
            
            for t in tags:
                t = t.strip()
                if t:
                    # 查找知识点ID
                    node = next((n for n in PPT_KNOWLEDGE_NODES if n["name"] == t or n["id"] == t), None)
                    if node:
                        knowledge_id = node["id"]
                        
                        # 更新知识点掌握度
                        conn_problem = get_db_connection('knowledge_mastery.db')
                        if conn_problem is None:
                            continue
                        c_problem = conn_problem.cursor()
                        c_problem.execute('''SELECT id FROM knowledge_mastery 
                                             WHERE student_name=? AND knowledge_id=?''', (student, knowledge_id))
                        existing = c_problem.fetchone()
                        if existing:
                            c_problem.execute('''UPDATE knowledge_mastery 
                                                 SET error_count = error_count + 1, last_error_time=?
                                                 WHERE student_name=? AND knowledge_id=?''',
                                              (submit_time, student, knowledge_id))
                        else:
                            c_problem.execute('''INSERT INTO knowledge_mastery 
                                                 (student_name, knowledge_id, error_count, last_error_time)
                                                 VALUES (?,?,1,?)''', (student, knowledge_id, submit_time))
                        conn_problem.commit()
                        close_db_connection(conn_problem)
                        conn_problem = None

        conn.commit()

        return jsonify({
            'code':200,
            'msg': '提交成功',
            'data': {
                'score': score,
                'submit_time': submit_time
            }
        })
    except Exception as e:
        logger.error(f"提交作业失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'提交作业失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)
        if conn_problem:
            close_db_connection(conn_problem)
        if conn_hw:
            close_db_connection(conn_hw)

# ==================== 班级接口 ====================
@app.route('/api/class/create', methods=['POST'])
@role_required(['teacher'])
def class_create():
    """创建班级"""
    conn = None
    try:
        d = request.json
        teacher = d.get('username')
        name = d.get('class_name')
        code = d.get('class_code')
        course = d.get('course', '面向对象程序设计')
        
        if not all([teacher, name, code]):
            return jsonify({'code':400,'msg':'参数不全'})
        
        conn = get_db_connection('class.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('''INSERT INTO class (teacher_username, class_name, class_code, course, student_count) 
                     VALUES (?,?,?,?,0)''',
            (teacher, name, code, course))
        conn.commit()
        class_id = c.lastrowid
        return jsonify({'code':200,'msg':'创建成功', 'data': {'id': class_id, 'inviteCode': code}})
    except sqlite3.IntegrityError:
        return jsonify({'code':400,'msg':'班级码已存在'})
    except Exception as e:
        logger.error(f"创建班级失败: {str(e)}")
        return jsonify({'code':500,'msg':'创建失败：'+str(e)})
    finally:
        if conn:
            close_db_connection(conn)

@app.route('/api/class/join', methods=['POST'])
@role_required(['student'])
def class_join():
    """学生加入班级"""
    conn = None
    try:
        d = request.json
        student = d.get('username')
        code = d.get('class_code')
        
        conn = get_db_connection('class.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('SELECT id FROM class WHERE class_code=?', (code,))
        clz = c.fetchone()
        if not clz:
            return jsonify({'code':400,'msg':'班级码错误'})
        
        class_id = clz[0]
        c.execute('INSERT INTO class_student (class_id, student_username) VALUES (?,?)',
            (class_id, student))
        c.execute('UPDATE class SET student_count = student_count + 1 WHERE id=?', (class_id,))
        conn.commit()
        return jsonify({'code':200,'msg':'加入成功', 'data': {'class_id': class_id}})
    except sqlite3.IntegrityError:
        return jsonify({'code':400,'msg':'已加入该班级'})
    except Exception as e:
        logger.error(f"加入班级失败: {str(e)}")
        return jsonify({'code':500,'msg':'加入失败：'+str(e)})
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 获取学生班级信息接口 ====================
@app.route('/api/student/class', methods=['POST'])
def get_student_class():
    """获取学生所在班级信息"""
    conn = None
    try:
        data = request.json
        student_name = data.get('username')
        
        if not student_name:
            return jsonify({'code': 400, 'msg': '学生名不能为空'}), 400
        
        conn = get_db_connection('class.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        
        # 查询学生所在的班级
        c.execute('''SELECT c.id, c.class_name, c.class_code, c.course
                     FROM class c
                     JOIN class_student cs ON c.id = cs.class_id
                     WHERE cs.student_username=?''', (student_name,))
        row = c.fetchone()
        
        if row:
            return jsonify({
                'code': 200,
                'data': {
                    'class_id': row[0],
                    'class_name': row[1],
                    'class_code': row[2],
                    'course': row[3]
                }
            })
        else:
            return jsonify({
                'code': 200,
                'data': None,
                'msg': '学生未加入任何班级'
            })
        
    except Exception as e:
        logger.error(f"获取学生班级失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 消息通知接口 ====================
@app.route('/api/notification/list', methods=['GET'])
def get_notifications():
    """获取消息通知"""
    conn = None
    try:
        username = request.args.get('username')
        role = request.args.get('role')
        if not username or not role:
            return jsonify({'code': 400, 'msg': '缺少用户名/角色参数'})
        
        conn = get_db_connection('notifications.db')
        if conn is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c = conn.cursor()
        c.execute('''SELECT id, title, content, type, is_read, create_time 
                     FROM notifications 
                     WHERE username=? 
                     ORDER BY create_time DESC''', (username,))
        rows = c.fetchall()
        
        notifications = [{
            'id': row[0],
            'title': row[1],
            'content': row[2],
            'type': row[3],
            'is_read': row[4],
            'create_time': row[5]
        } for row in rows]
        
        return jsonify({
            'code': 200,
            'data': {
                'notifications': notifications,
                'unread_count': len([n for n in notifications if n['is_read'] == 0])
            }
        })
    except Exception as e:
        logger.error(f"获取通知失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取通知失败: {str(e)}'}), 500
    finally:
        if conn:
            close_db_connection(conn)

# ==================== 班级学情分析接口 ====================
@app.route('/api/teacher/class_analysis')
@role_required(['teacher'])
def class_analysis():
    """班级学情大盘"""
    conn_class = None
    conn_hw = None
    conn_stu = None
    conn_mastery = None
    try:
        class_id = request.args.get('class_id')
        teacher_name = request.args.get('username')
        if not class_id:
            return jsonify({'code':400, 'msg':'班级ID不能为空'}), 400
        
        conn_class = get_db_connection('class.db')
        if conn_class is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c_class = conn_class.cursor()
        c_class.execute('''SELECT c.class_name, c.course, COUNT(s.student_username) as student_count
                     FROM class c
                     LEFT JOIN class_student s ON c.id = s.class_id
                     WHERE c.id=? AND c.teacher_username=?''', (class_id, teacher_name))
        class_info = c_class.fetchone()
        if not class_info:
            return jsonify({'code':403, 'msg':'无该班级权限'}), 403
        
        class_name = class_info[0]
        course = class_info[1]
        student_count = class_info[2] or 0

        # 获取该班级学生列表
        c_class.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
        students = [row[0] for row in c_class.fetchall()]

        conn_hw = get_db_connection('homework.db')
        if conn_hw is None:
            return jsonify({'code': 500, 'msg': '数据库连接失败'}), 500
        c_hw = conn_hw.cursor()
        c_hw.execute('SELECT COUNT(*) FROM homework WHERE class_id=? OR class_id="all"', (class_id,))
        hw_total = c_hw.fetchone()[0]
        
        # 获取该班级知识点掌握情况
        conn_mastery = get_db_connection('knowledge_mastery.db')
        if conn_mastery is not None:
            c_mastery = conn_mastery.cursor()
            
            # 计算每个知识点的平均掌握度
            knowledge_mastery = {}
            for node in PPT_KNOWLEDGE_NODES[:10]:  # 取前10个核心知识点
                total_mastery = 0
                count = 0
                for student in students:
                    c_mastery.execute('''SELECT error_count FROM knowledge_mastery 
                                         WHERE student_name=? AND knowledge_id=?''', (student, node["id"]))
                    row = c_mastery.fetchone()
                    if row:
                        mastery = max(30, 100 - row[0] * 8)
                    else:
                        mastery = 70
                    total_mastery += mastery
                    count += 1
                
                avg_mastery = round(total_mastery / count) if count > 0 else 70
                knowledge_mastery[node["name"]] = avg_mastery
        
        # 找出薄弱知识点（掌握度<60）
        weak_knowledges = [k for k, v in knowledge_mastery.items() if v < 60] if 'knowledge_mastery' in locals() else []

        return jsonify({
            'code': 200,
            'data': {
                'class_name': class_name,
                'course': course,
                'student_count': student_count,
                'hw_total': hw_total,
                'knowledge_mastery': knowledge_mastery if 'knowledge_mastery' in locals() else {},
                'weak_knowledges': weak_knowledges
            }
        })
    except Exception as e:
        logger.error(f"班级学情分析失败：{str(e)}")
        return jsonify({'code':500, 'msg':f'获取学情数据失败：{str(e)}'}), 500
    finally:
        if conn_class:
            close_db_connection(conn_class)
        if conn_hw:
            close_db_connection(conn_hw)
        if conn_mastery:
            close_db_connection(conn_mastery)

# ==================== 缓存管理接口 ====================
@app.route('/api/cache/clear', methods=['POST'])
@role_required(['teacher'])
def clear_cache():
    """清除缓存（教师专用）"""
    try:
        data = request.json
        prefix = data.get('prefix', '')
        if prefix:
            clear_cache_by_prefix(prefix)
            return jsonify({'code': 200, 'msg': f'缓存已清除: {prefix}'})
        return jsonify({'code': 400, 'msg': '请指定缓存前缀'})
    except Exception as e:
        logger.error(f"清除缓存失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

# ==================== 清除用户缓存接口 ====================
@app.route('/api/cache/clear_user', methods=['POST'])
@role_required(['teacher'])
def clear_user_cache():
    """清除用户缓存"""
    global user_cache, login_cache
    user_cache.clear()
    login_cache.clear()
    return jsonify({'code': 200, 'msg': '用户缓存已清除'})

# ==================== 智谱API配置 ====================
ZHIPU_API_KEY = "e01146d8789f4c17a7e3c2524c94be1c.70vePpdokdFJAONp"  
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# ==================== 初始化AI评分器 ====================
def init_ai_grader():
    """初始化AI评分器"""
    try:
        from utils.ai_grader import ai_grader
        ai_grader.set_api_key(ZHIPU_API_KEY)
        print("✅ AI评分器初始化成功，使用免费模型 glm-4.7-flash")
    except Exception as e:
        print(f"⚠️ AI评分器初始化失败: {e}")

# 调用初始化
init_ai_grader()

def call_zhipu_api(messages, temperature=0.7, max_tokens=2000):
    """
    调用智谱GLM-4.7-Flash API的通用函数
    """
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "glm-4.7-flash",  # 统一使用最新免费模型
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 0.9
    }
    
    try:
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'content': result['choices'][0]['message']['content'],
                'model': result.get('model', 'glm-4.7-flash')
            }
        else:
            error_msg = f"API错误: {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = error_data['error'].get('message', error_msg)
            except:
                pass
            logger.error(f"智谱API调用失败: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except requests.exceptions.Timeout:
        logger.error("智谱API请求超时")
        return {'success': False, 'error': '请求超时'}
    except Exception as e:
        logger.error(f"智谱API异常: {str(e)}")
        return {'success': False, 'error': str(e)}

@app.route('/api/agent/ask', methods=['POST'])
def agent_ask():
    """
    智能体问答接口（使用智谱GLM-4.7-Flash）
    """
    try:
        data = request.json
        role = data.get('role')
        question = data.get('question')
        context = data.get('context', {})
        
        if not role or not question:
            return jsonify({'code': 400, 'msg': '缺少必要参数'}), 400
        
        # 获取对应的智能体实例
        agent = AgentFactory.get_agent(role, ZHIPU_API_KEY)
        
        # 调用智能体的ask方法
        result = agent.ask(question, context)
        
        return jsonify({
            'code': 200,
            'data': result
        })
            
    except Exception as e:
        logger.error(f"智能体问答失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/check_code', methods=['POST'])
def agent_check_code():
    """代码检查接口"""
    try:
        data = request.json
        code = data.get('code')
        role = data.get('role', 'student')
        
        if not code:
            return jsonify({'code': 400, 'msg': '代码不能为空'}), 400
        
        system_prompt = """你是一个C++代码检查专家。请检查以下代码，找出语法错误、逻辑问题、代码规范问题，并提供改进建议。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请检查这段C++代码：\n```cpp\n{code}\n```"}
        ]
        
        result = call_zhipu_api(messages, temperature=0.3)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'data': {
                    'analysis': result['content'],
                    'model': result['model']
                }
            })
        else:
            return jsonify({'code': 500, 'msg': result['error']}), 500
            
    except Exception as e:
        logger.error(f"代码检查失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/explain_error', methods=['POST'])
def agent_explain_error():
    """错误解释接口"""
    try:
        data = request.json
        error = data.get('error')
        code = data.get('code', '')
        role = data.get('role', 'student')
        
        if not error:
            return jsonify({'code': 400, 'msg': '错误信息不能为空'}), 400
        
        system_prompt = """你是一个C++错误解释专家。请解释以下编译错误或运行时错误的含义、产生原因，并提供解决方案。"""
        
        user_content = f"错误信息：{error}\n"
        if code:
            user_content += f"相关代码：\n```cpp\n{code}\n```\n"
        user_content += "请解释这个错误的原因和解决方法。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        result = call_zhipu_api(messages, temperature=0.4)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'data': {
                    'explanation': result['content'],
                    'model': result['model']
                }
            })
        else:
            return jsonify({'code': 500, 'msg': result['error']}), 500
            
    except Exception as e:
        logger.error(f"错误解释失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/generate_quiz', methods=['POST'])
@role_required(['teacher'])
def agent_generate_quiz():
    """生成测验题目（教师专用）"""
    try:
        data = request.json
        topic = data.get('topic', '类与对象')
        difficulty = data.get('difficulty', 'medium')
        count = data.get('count', 3)
        
        agent = AgentFactory.get_agent('teacher', ZHIPU_API_KEY)
        questions = agent.generate_quiz(topic, difficulty, count)
        
        return jsonify({
            'code': 200,
            'data': questions
        })
            
    except Exception as e:
        logger.error(f"生成题目失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/grade_code', methods=['POST'])
@role_required(['teacher', 'student'])
def agent_grade_code():
    """AI批改作业接口"""
    try:
        data = request.json
        code = data.get('code')
        question = data.get('question', '')
        knowledge_point = data.get('knowledge_point', '')
        
        if not code:
            return jsonify({'code': 400, 'msg': '代码不能为空'}), 400
        
        from utils.ai_grader import ai_grader
        result = ai_grader.grade_homework(question, code, knowledge_point)
        
        grade_result = {
            'totalScore': result['total_score'],
            'dimensions': {
                'syntax': {'score': result['dimensions'].get('correctness', 0) // 2, 'issues': result.get('weaknesses', [])[:2]},
                'logic': {'score': result['dimensions'].get('completeness', 0) // 2, 'issues': []},
                'standard': {'score': result['dimensions'].get('style', 0), 'issues': []},
                'knowledge': {'score': result['dimensions'].get('knowledge', 0), 'issues': []}
            },
            'suggestions': result.get('suggestions', []),
            'feedback': result.get('feedback', ''),
            'code': code,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify({
            'code': 200,
            'data': grade_result
        })
            
    except Exception as e:
        logger.error(f"AI批改失败: {str(e)}")
        fallback_result = {
            'totalScore': 60,
            'dimensions': {
                'syntax': {'score': 15, 'issues': ['AI服务异常，使用规则评分']},
                'logic': {'score': 15, 'issues': []},
                'standard': {'score': 15, 'issues': []},
                'knowledge': {'score': 15, 'issues': []}
            },
            'suggestions': ['请稍后重试AI批改'],
            'feedback': 'AI批改服务暂时异常，使用基础规则评分。',
            'code': code,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return jsonify({
            'code': 200,
            'data': fallback_result
        })

@app.route('/api/nlp/analyze', methods=['POST'])
def nlp_analyze():
    """NLP文本分析接口"""
    try:
        data = request.json
        text = data.get('text', '')
        analysis_type = data.get('analysis_type', 'keywords')
        
        if not text:
            return jsonify({'code': 400, 'msg': '文本不能为空'})
        
        if analysis_type == 'keywords' and len(text) < 1000:
            keywords = jieba.analyse.textrank(text, topK=10, withWeight=True, allowPOS=('n', 'vn', 'v', 'nz'))
            hotwords = [{'word': k, 'weight': round(w * 100, 2)} for k, w in keywords]
            return jsonify({'code': 200, 'data': hotwords})
        
        system_prompts = {
            'keywords': '请提取以下文本的关键词，返回JSON格式的关键词列表。',
            'summary': '请对以下文本进行摘要总结，用100字左右概括主要内容。',
            'sentiment': '请分析以下文本的情感倾向（积极/消极/中性），并给出理由。',
            'topic': '请分析以下文本的主要主题和子主题。'
        }
        
        system_prompt = system_prompts.get(analysis_type, '请分析以下文本。')
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        result = call_zhipu_api(messages, temperature=0.5)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'data': {
                    'result': result['content'],
                    'type': analysis_type,
                    'model': result['model']
                }
            })
        else:
            if analysis_type == 'keywords':
                keywords = jieba.analyse.textrank(text, topK=10, withWeight=True, allowPOS=('n', 'vn', 'v', 'nz'))
                hotwords = [{'word': k, 'weight': round(w * 100, 2)} for k, w in keywords]
                return jsonify({'code': 200, 'data': hotwords})
            else:
                return jsonify({'code': 500, 'msg': result['error']}), 500
            
    except Exception as e:
        logger.error(f"NLP分析失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/history', methods=['POST'])
def agent_history():
    """获取对话历史"""
    try:
        data = request.json
        role = data.get('role')
        
        if not role:
            return jsonify({'code': 400, 'msg': '缺少角色参数'}), 400
        
        agent = AgentFactory.get_agent(role, ZHIPU_API_KEY)
        history = agent.get_history()
        
        return jsonify({
            'code': 200,
            'data': history
        })
    except Exception as e:
        logger.error(f"获取历史失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/agent/clear', methods=['POST'])
def agent_clear():
    """清空对话历史"""
    try:
        data = request.json
        role = data.get('role')
        
        if not role:
            return jsonify({'code': 400, 'msg': '缺少角色参数'}), 400
        
        agent = AgentFactory.get_agent(role, ZHIPU_API_KEY)
        agent.clear_history()
        
        return jsonify({
            'code': 200,
            'msg': '历史已清空'
        })
    except Exception as e:
        logger.error(f"清空历史失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500
@app.route('/api/student/learning_stats', methods=['POST'])
def get_learning_stats():
    """获取学生学习统计（能量值、连击、成就）"""
    try:
        data = request.json
        student_id = data.get('student_id')
        
        # 从localStorage模拟数据（实际可从数据库读取）
        return jsonify({
            'code': 200,
            'data': {
                'energy': {'points': 150, 'level': 2},
                'streak': 5,
                'achievements': ['初试锋芒', '七连击']
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/class/progress', methods=['POST'])
@role_required(['teacher'])
def get_class_progress():
    """获取班级整体学习进度"""
    try:
        data = request.json
        class_id = data.get('class_id')
        
        # 计算班级平均掌握度
        return jsonify({
            'code': 200,
            'data': {
                'avg_mastery': 72,
                'completed_rate': 65,
                'weak_points': ['指针', '多态', '虚函数']
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)}), 500
# ==================== 注册退出时的清理函数 ====================
atexit.register(close_all_pools)

# ==================== 启动程序 ====================
if __name__ == '__main__':
    with app.app_context():
        # 创建新数据库表
        # db.create_all()
        pass
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)