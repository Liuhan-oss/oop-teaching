import logging
import os
import sqlite3
import datetime
import json
import random
import time
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jieba
import jieba.analyse

# ==================== 基础配置 ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(PROJECT_ROOT, 'pages')
UPLOAD_DIR = os.path.join(PROJECT_ROOT, 'uploads')
VIDEO_DIR = os.path.join(PROJECT_ROOT, 'videos')

# 创建必要的目录
os.makedirs(PAGES_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# 打印路径信息（用于调试）
print("="*50)
print(f"项目根目录: {PROJECT_ROOT}")
print(f"页面目录: {PAGES_DIR}")
print(f"上传目录: {UPLOAD_DIR}")
print(f"视频目录: {VIDEO_DIR}")
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
CORS(app, supports_credentials=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['VIDEO_FOLDER'] = VIDEO_DIR
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================= 邮箱配置 =======================
app.config['MAIL_SERVER'] = 'smtp.163.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = '18531321074@163.com'  
app.config['MAIL_PASSWORD'] = 'UTPBNMkgMer8SrFP'        
app.config['MAIL_DEFAULT_SENDER'] = '18531321074@163.com'

mail = Mail(app)
reset_codes = {}

# ==================== 工具函数 =====================
def get_db_connection(db_name):
    """获取数据库连接"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def close_db_connection(conn):
    """关闭数据库连接"""
    if conn:
        try:
            conn.commit()
        except Exception as e:
            logger.error(f"提交数据库事务失败: {str(e)}")
        finally:
            conn.close()

def calculate_mastery_level(student_name, knowledge):
    """计算学生知识点掌握度"""
    try:
        conn = get_db_connection('mastery.db')
        c = conn.cursor()
        c.execute('''SELECT COUNT(*) FROM knowledge_mastery 
                    WHERE student_name=? AND weak_knowledge=?''', (student_name, knowledge))
        error_count = c.fetchone()[0]
        close_db_connection(conn)
        mastery_level = max(0, 100 - error_count * 10)
        return mastery_level
    except Exception as e:
        logger.error(f"计算掌握度失败: {str(e)}")
        return 0

def role_required(allowed_roles):
    """权限校验装饰器"""
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
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute('SELECT 1 FROM sys_user WHERE username=? AND role=?', (username, role))
                if not c.fetchone():
                    conn.close()
                    return jsonify({'code': 401, 'msg': '用户不存在或角色不匹配'}), 401
                conn.close()
            except Exception as e:
                logger.error(f"权限校验失败: {str(e)}")
                return jsonify({'code': 500, 'msg': '权限校验异常'}), 500
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== 数据库初始化 ====================
def init_class():
    """初始化班级表"""
    try:
        conn = sqlite3.connect('class.db')
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
        conn.close()
    except Exception as e:
        logger.error(f"初始化班级表失败: {str(e)}")

def init_mastery():
    """初始化知识点掌握度表"""
    try:
        conn = sqlite3.connect('mastery.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_mastery
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            wrong_hw_id INTEGER,
            weak_knowledge TEXT,
            mastery_level INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"初始化掌握度表失败: {str(e)}")

def init_user():
    """初始化用户表"""
    try:
        conn = sqlite3.connect('users.db')
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
            c.execute("INSERT INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("2024215612", generate_password_hash("123456"), "student", "test@qq.com", "张三"))
            c.execute("INSERT INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("2024215613", generate_password_hash("123456"), "student", "test@qq.com", "李四"))
            c.execute("INSERT INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)",
                ("T2024001", generate_password_hash("123456"), "teacher", "test@qq.com", "张老师"))
        except sqlite3.IntegrityError:
            pass
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"初始化用户表失败: {str(e)}")

def init_notification():
    """初始化消息通知表"""
    try:
        conn = sqlite3.connect('notifications.db')
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
        conn.close()
    except Exception as e:
        logger.error(f"初始化通知表失败: {str(e)}")

def init_course():
    """初始化课程表"""
    try:
        conn = sqlite3.connect('courses.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS course
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, 
            filename TEXT, 
            knowledge_tags TEXT,
            hotwords TEXT DEFAULT '')''')
        try:
            c.execute("INSERT INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("OOP三大特性详解", "oop_features.pdf", "封装,继承,多态", "类,对象,方法,属性"))
            c.execute("INSERT INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("类与对象实战", "class_object.pdf", "类,对象,实例化", "构造函数,实例,属性"))
            c.execute("INSERT INTO course (name, filename, knowledge_tags, hotwords) VALUES (?,?,?,?)",
                ("抽象类与接口", "abstract_interface.pdf", "抽象类,接口", "抽象,实现,多态"))
        except sqlite3.IntegrityError:
            pass
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"初始化课程表失败: {str(e)}")

def init_homework():
    """初始化作业表"""
    try:
        conn = sqlite3.connect('homework.db')
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
        conn.close()
    except Exception as e:
        logger.error(f"初始化作业表失败: {str(e)}")

def init_video():
    """初始化视频表"""
    try:
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS videos
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            filename TEXT,
            knowledge_tag TEXT,
            class_id INTEGER,
            teacher_username TEXT,
            upload_time TEXT,
            file_size TEXT,
            duration TEXT DEFAULT '')''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"初始化视频表失败: {str(e)}")

def init_knowledge_graph():
    """初始化知识图谱表"""
    try:
        conn = sqlite3.connect('knowledge_graph.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_nodes
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category INTEGER,
            size INTEGER,
            difficulty INTEGER,
            description TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS knowledge_links
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            target TEXT,
            relation TEXT,
            description TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS student_problem_graph
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            knowledge_point TEXT,
            error_count INTEGER DEFAULT 0,
            last_error_time TEXT,
            recommended_count INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"初始化知识图谱表失败: {str(e)}")

# 执行所有表初始化
init_user()
init_course()
init_homework()
init_class()
init_mastery()
init_notification()
init_video()
init_knowledge_graph()

# ==================== 静态文件路由 ====================
@app.route('/')
def index():
    """根路径重定向到登录页"""
    return redirect('/pages/login.html')

@app.route('/pages/<path:filename>')
def serve_page(filename):
    """提供页面文件服务"""
    try:
        # 安全处理，防止路径遍历
        if '..' in filename or filename.startswith('/'):
            return jsonify({'code': 400, 'msg': '非法路径'}), 400
        
        # 检查文件是否存在
        file_path = os.path.join(PAGES_DIR, filename)
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return jsonify({'code': 404, 'msg': f'页面不存在: {filename}'}), 404
        
        # 发送文件
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

@app.route('/videos/<path:filename>')
def serve_video(filename):
    """提供视频文件服务"""
    try:
        return send_from_directory(VIDEO_DIR, filename)
    except Exception as e:
        logger.error(f"访问视频文件失败: {str(e)}")
        return jsonify({'code': 404, 'msg': '视频不存在'}), 404

# ==================== 调试路由 ====================
@app.route('/api/check_files', methods=['GET'])
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
    c = conn.cursor()
    c.execute('SELECT id, class_name, student_count, course, class_code FROM class WHERE teacher_username=?', (teacher,))
    rows = c.fetchall()
    close_db_connection(conn)
    return jsonify([{'id': x[0], 'name': x[1], 'studentCount': x[2], 'course': x[3], 'inviteCode': x[4]} for x in rows])

# ==================== 知识图谱接口 ====================
@app.route('/api/graph/data')
def get_graph_data():
    """获取知识图谱数据"""
    try:
        conn = get_db_connection('knowledge_graph.db')
        c = conn.cursor()
        c.execute('SELECT name, category, size, difficulty, description FROM knowledge_nodes')
        nodes = [{'name': row[0], 'category': row[1], 'size': row[2], 'difficulty': row[3], 'description': row[4]} for row in c.fetchall()]
        
        if not nodes:
            # 初始化默认图谱数据
            default_nodes = [
                ('面向对象基础', 0, 60, 1, 'OOP的入门概念'),
                ('类', 0, 40, 2, '对象的蓝图和模板'),
                ('对象', 0, 40, 2, '类的实例'),
                ('封装', 1, 45, 3, '隐藏内部实现细节'),
                ('继承', 1, 45, 3, '子类继承父类特性'),
                ('多态', 1, 45, 4, '同一接口不同实现'),
                ('接口', 2, 35, 4, '定义行为规范'),
                ('抽象类', 2, 35, 4, '不能实例化的类'),
                ('方法重写', 1, 30, 3, '子类重新定义父类方法'),
                ('方法重载', 1, 30, 3, '同名方法不同参数'),
                ('构造函数', 0, 30, 2, '对象创建时调用'),
                ('访问修饰符', 0, 30, 2, '控制访问权限')
            ]
            for node in default_nodes:
                c.execute('INSERT OR IGNORE INTO knowledge_nodes (name, category, size, difficulty, description) VALUES (?,?,?,?,?)',
                         node)
            
            default_links = [
                ('面向对象基础', '类', '包含', '面向对象基础包含类'),
                ('面向对象基础', '对象', '包含', '面向对象基础包含对象'),
                ('类', '对象', '实例化', '类可以创建对象'),
                ('类', '封装', '实现', '类通过封装实现'),
                ('类', '继承', '关系', '类之间可以继承'),
                ('类', '多态', '实现', '多态基于继承'),
                ('继承', '方法重写', '需要', '子类可以重写父类方法'),
                ('多态', '方法重载', '形式', '重载是多态的一种'),
                ('继承', '接口', '对比', '接口vs抽象类'),
                ('继承', '抽象类', '对比', '抽象类vs接口')
            ]
            for link in default_links:
                c.execute('INSERT OR IGNORE INTO knowledge_links (source, target, relation, description) VALUES (?,?,?,?)',
                         link)
            conn.commit()
            
            c.execute('SELECT name, category, size, difficulty, description FROM knowledge_nodes')
            nodes = [{'name': row[0], 'category': row[1], 'size': row[2], 'difficulty': row[3], 'description': row[4]} for row in c.fetchall()]
        
        c.execute('SELECT source, target, relation, description FROM knowledge_links')
        links = [{'source': row[0], 'target': row[1], 'name': row[2], 'desc': row[3]} for row in c.fetchall()]
        
        close_db_connection(conn)
        
        return jsonify({
            'code': 200,
            'data': {
                'nodes': nodes,
                'links': links,
                'categories': [
                    {'name': '基础'},
                    {'name': '核心'},
                    {'name': '高级'}
                ]
            }
        })
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/student/problem_graph', methods=['POST'])
@role_required(['student'])
def get_student_problem_graph():
    """获取学生问题图谱"""
    try:
        data = request.json
        student_name = data.get('student_name')
        
        conn = get_db_connection('knowledge_graph.db')
        c = conn.cursor()
        c.execute('''SELECT knowledge_point, error_count, recommended_count 
                     FROM student_problem_graph 
                     WHERE student_name=? AND error_count > 0
                     ORDER BY error_count DESC''', (student_name,))
        problems = [{'knowledge': row[0], 'errorCount': row[1], 'recommended': row[2]} for row in c.fetchall()]
        close_db_connection(conn)
        
        return jsonify({'code': 200, 'data': problems})
    except Exception as e:
        logger.error(f"获取学生问题图谱失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/student/personalized_recommend', methods=['POST'])
@role_required(['student'])
def get_personalized_recommend():
    """获取个性化推荐（包含视频）"""
    try:
        data = request.json
        student_name = data.get('student_name')
        
        conn = get_db_connection('knowledge_graph.db')
        c = conn.cursor()
        
        # 获取学生薄弱知识点
        c.execute('''SELECT knowledge_point, error_count 
                     FROM student_problem_graph 
                     WHERE student_name=? AND error_count > 0
                     ORDER BY error_count DESC LIMIT 5''', (student_name,))
        weak_points = [{'point': row[0], 'count': row[1]} for row in c.fetchall()]
        
        # 如果没有薄弱点，使用默认推荐
        if not weak_points:
            weak_points = [
                {'point': '多态', 'count': 3},
                {'point': '接口', 'count': 2},
                {'point': '继承', 'count': 1}
            ]
        
        # 从知识图谱获取相关知识点
        recommendations = []
        for wp in weak_points:
            c.execute('''SELECT target, relation FROM knowledge_links 
                         WHERE source=? OR target=?''', (wp['point'], wp['point']))
            related = c.fetchall()
            for rel in related:
                related_point = rel[0] if rel[0] != wp['point'] else rel[1]
                if related_point not in [r['point'] for r in weak_points]:
                    recommendations.append({
                        'point': related_point,
                        'reason': f'与您的薄弱知识点「{wp["point"]}」相关（{rel[1]}关系）',
                        'priority': wp['count']
                    })
        
        # 推荐视频（根据薄弱知识点）
        conn_video = get_db_connection('videos.db')
        c_video = conn_video.cursor()
        recommend_videos = []
        for wp in weak_points[:3]:
            c_video.execute('SELECT id, title, description, knowledge_tag, filename FROM videos WHERE knowledge_tag LIKE ?', (f'%{wp["point"]}%',))
            videos = c_video.fetchall()
            for video in videos:
                recommend_videos.append({
                    'id': video[0],
                    'title': video[1],
                    'description': video[2],
                    'knowledge_tag': video[3],
                    'filename': video[4],
                    'reason': f'针对「{wp["point"]}」薄弱点的教学视频',
                    'priority': wp['count']
                })
        close_db_connection(conn_video)
        
        # 推荐课程
        conn_course = get_db_connection('courses.db')
        c_course = conn_course.cursor()
        recommend_courses = []
        for wp in weak_points[:3]:
            c_course.execute('SELECT id, name, hotwords FROM course WHERE knowledge_tags LIKE ?', (f'%{wp["point"]}%',))
            courses = c_course.fetchall()
            for course in courses:
                recommend_courses.append({
                    'id': course[0],
                    'name': course[1],
                    'hotwords': course[2].split(',') if course[2] else [],
                    'reason': f'针对「{wp["point"]}」薄弱点的专项课程',
                    'priority': wp['count']
                })
        close_db_connection(conn_course)
        
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
        
        close_db_connection(conn)
        
        return jsonify({
            'code': 200,
            'data': {
                'weak_points': weak_points,
                'related_points': recommendations[:5],
                'recommend_videos': unique_videos[:5],
                'recommend_courses': unique_courses[:5]
            }
        })
    except Exception as e:
        logger.error(f"获取个性化推荐失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/update_problem_graph', methods=['POST'])
def update_problem_graph():
    """更新学生问题图谱"""
    try:
        data = request.json
        student_name = data.get('student_name')
        knowledge_point = data.get('knowledge_point')
        
        conn = get_db_connection('knowledge_graph.db')
        c = conn.cursor()
        
        c.execute('''SELECT id, error_count FROM student_problem_graph 
                     WHERE student_name=? AND knowledge_point=?''', (student_name, knowledge_point))
        existing = c.fetchone()
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if existing:
            c.execute('''UPDATE student_problem_graph 
                         SET error_count = error_count + 1, last_error_time = ?
                         WHERE student_name=? AND knowledge_point=?''',
                      (now, student_name, knowledge_point))
        else:
            c.execute('''INSERT INTO student_problem_graph 
                         (student_name, knowledge_point, error_count, last_error_time, recommended_count)
                         VALUES (?,?,1,?,0)''', (student_name, knowledge_point, now))
        
        conn.commit()
        close_db_connection(conn)
        
        return jsonify({'code': 200, 'msg': '问题图谱更新成功'})
    except Exception as e:
        logger.error(f"更新问题图谱失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

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

@app.route('/api/nlp/extract_hotwords_simple', methods=['POST'])
def extract_hotwords_simple():
    """简单的热词提取（用于前端快速测试）"""
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'code': 400, 'msg': '文本不能为空'})
        
        # 简单分词统计
        words = jieba.cut(text)
        word_count = {}
        stop_words = {'的', '了', '是', '在', '和', '与', '有', '我', '你', '他', '她', '它', '我们', '你们', '他们', '这个', '那个', '这些', '那些'}
        
        for word in words:
            if len(word) > 1 and word not in stop_words:
                word_count[word] = word_count.get(word, 0) + 1
        
        # 排序取前10
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]
        hotwords = [{'word': w[0], 'count': w[1]} for w in sorted_words]
        
        return jsonify({'code': 200, 'data': hotwords})
    except Exception as e:
        logger.error(f"简单热词提取失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

# ==================== 知识点掌握度接口 ====================
@app.route('/api/student/knowledge_mastery')
@role_required(['student'])
def knowledge_mastery():
    """获取学生知识点掌握度"""
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({'code':400, 'msg':'学生ID不能为空'}), 400
        
        core_knowledges = ["类", "对象", "封装", "继承", "多态", "接口"]
        mastery_values = []
        for knowledge in core_knowledges:
            mastery_level = calculate_mastery_level(student_id, knowledge)
            mastery_values.append(mastery_level)
        
        result = {
            "indicator": [{"name": k, "max": 100} for k in core_knowledges],
            "data": [{"value": mastery_values, "name": "我的掌握度"}]
        }
        
        return jsonify({'code':200, 'data': result})
    except Exception as e:
        logger.error(f"获取掌握度失败: {str(e)}")
        return jsonify({'code':500, 'msg':f'获取数据失败：{str(e)}'}), 500

# ==================== 用户认证接口 ====================
@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        d = request.json
        u = d.get('username')
        p = d.get('password')
        r = d.get('role')
        
        if not all([u, p, r]):
            return jsonify({'code':400, 'msg': '账号/密码/角色不能为空'})
            
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT password_hash, name FROM sys_user WHERE username=? AND role=?', (u,r))
        row = c.fetchone()
        conn.close()
        
        if row and check_password_hash(row[0], p):
            return jsonify({'code':200, 'data': {'username': u, 'role': r, 'name': row[1]}})
        return jsonify({'code':400, 'msg': '账号或密码错误'})
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'登录失败: {str(e)}'}), 500

@app.route('/api/register', methods=['POST'])
def reg():
    """用户注册"""
    try:
        d = request.json
        u = d.get('username')
        p = d.get('password')
        r = d.get('role')
        name = d.get('name', u)
        e = d.get('email', '')
        
        if not all([u, p, r]):
            return jsonify({'code':400, 'msg': '账号/密码/角色不能为空'})
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO sys_user (username, password_hash, role, email, name) VALUES (?,?,?,?,?)',
            (u, generate_password_hash(p), r, e, name))
        conn.commit()
        conn.close()
        
        return jsonify({'code':200, 'msg': '注册成功', 'data': {'username': u, 'role': r, 'name': name}})
    except sqlite3.IntegrityError:
        return jsonify({'code':400, 'msg': '账号已存在'})
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'注册失败: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """退出登录"""
    return jsonify({'code':200, 'msg': '退出登录成功'})

@app.route('/api/forget/send_code', methods=['POST'])
def forget_send_code():
    """发送重置密码验证码"""
    try:
        d = request.json
        username = d.get('username')
        role = d.get('role')

        if not username or not role:
            return jsonify({'code':400,'msg':'账号和角色不能为空'})

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT email FROM sys_user WHERE username=? AND role=?',(username,role))
        row = c.fetchone()
        conn.close()

        if not row or not row[0]:
            return jsonify({'code':400,'msg':'该用户未绑定邮箱'})

        email = row[0]
        code = str(random.randint(100000, 999999))
        reset_codes[f'{username}_{role}'] = {'code': code, 'expire': time.time() + 300}

        msg = Message('OOP教学平台 - 密码重置验证码', recipients=[email])
        msg.body = f'你的验证码是：{code}，5分钟内有效。'
        mail.send(msg)
        return jsonify({'code':200,'msg':'验证码已发送至邮箱'})
    except Exception as ex:
        logger.error(f"发送验证码失败: {str(ex)}")
        return jsonify({'code':500,'msg':'发送失败：'+str(ex)})

@app.route('/api/forget/reset', methods=['POST'])
def forget_reset():
    """重置密码"""
    try:
        d = request.json
        username = d.get('username')
        role = d.get('role')
        code = d.get('code')
        new_pwd = d.get('new_pwd')

        if not all([username,role,code,new_pwd]):
            return jsonify({'code':400,'msg':'参数不全'})

        key = f'{username}_{role}'
        if key not in reset_codes or reset_codes[key]['code'] != code:
            return jsonify({'code':400,'msg':'验证码错误'})
        
        if time.time() > reset_codes[key]['expire']:
            return jsonify({'code':400,'msg':'验证码已过期'})

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('UPDATE sys_user SET password_hash=? WHERE username=? AND role=?',
            (generate_password_hash(new_pwd), username, role))
        conn.commit()
        conn.close()

        del reset_codes[key]
        return jsonify({'code':200,'msg':'密码重置成功'})
    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'重置失败: {str(e)}'}), 500

@app.route('/api/user/info', methods=['GET'])
def get_user_info():
    """获取用户信息"""
    try:
        username = request.args.get('username')
        role = request.args.get('role')
        if not username or not role:
            return jsonify({'code': 400, 'msg': '缺少用户名/角色参数'})
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT username, role, name FROM sys_user WHERE username=? AND role=?', (username, role))
        row = c.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                'code': 200,
                'data': {
                    'username': row[0],
                    'role': row[1],
                    'name': row[2] or row[0],
                    'avatar': '/static/default-avatar.png'
                }
            })
        return jsonify({'code': 400, 'msg': '用户不存在'})
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取用户信息失败: {str(e)}'}), 500

@app.route('/api/user/change_pwd', methods=['POST'])
def change_pwd():
    """修改密码"""
    try:
        data = request.json
        username = data.get('username')
        role = data.get('role')
        old_pwd = data.get('old_pwd')
        new_pwd = data.get('new_pwd')
        
        if not all([username, role, new_pwd]):
            return jsonify({'code': 400, 'msg': '参数不完整'})
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT password_hash FROM sys_user WHERE username=? AND role=?', (username, role))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'code': 400, 'msg': '用户不存在'})
        
        if old_pwd and not check_password_hash(row[0], old_pwd):
            conn.close()
            return jsonify({'code': 400, 'msg': '原密码错误'})
        
        c.execute('UPDATE sys_user SET password_hash=? WHERE username=? AND role=?',
                  (generate_password_hash(new_pwd), username, role))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 200, 'msg': '密码修改成功'})
    except Exception as e:
        logger.error(f"修改密码失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'修改密码失败: {str(e)}'}), 500

# ==================== 课程接口 ====================
@app.route('/api/course/list')
def clist():
    """获取课程列表"""
    try:
        conn = sqlite3.connect('courses.db')
        c = conn.cursor()
        c.execute('SELECT id, name, filename, knowledge_tags, hotwords FROM course')
        rows = c.fetchall()
        conn.close()
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

@app.route('/api/course/upload', methods=['POST'])
@role_required(['teacher'])
def upload_course():
    """上传课程"""
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
        
        conn = sqlite3.connect('courses.db')
        c = conn.cursor()
        c.execute('INSERT INTO course (name, filename, knowledge_tags) VALUES (?,?,?)', (name, fn, tags))
        conn.commit()
        conn.close()
        return jsonify({'code':200, 'msg': '上传成功'})
    except Exception as e:
        logger.error(f"上传课程失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'上传课程失败: {str(e)}'}), 500

@app.route('/api/course/delete', methods=['POST'])
@role_required(['teacher'])
def delete_course():
    """删除课程"""
    try:
        id = request.json.get('id')
        if not id:
            return jsonify({'code':400, 'msg': '课程ID不能为空'})
            
        conn = sqlite3.connect('courses.db')
        c = conn.cursor()
        c.execute('DELETE FROM course WHERE id=?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'code':200, 'msg': '删除成功'})
    except Exception as e:
        logger.error(f"删除课程失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'删除课程失败: {str(e)}'}), 500

# ==================== 视频管理接口 ====================
@app.route('/api/video/list', methods=['GET'])
def get_video_list():
    """获取视频列表"""
    try:
        class_id = request.args.get('class_id')
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        
        if class_id and class_id != 'all':
            c.execute('SELECT id, title, description, filename, knowledge_tag, class_id, teacher_username, upload_time, file_size, duration FROM videos WHERE class_id=? OR class_id IS NULL ORDER BY upload_time DESC', (class_id,))
        else:
            c.execute('SELECT id, title, description, filename, knowledge_tag, class_id, teacher_username, upload_time, file_size, duration FROM videos ORDER BY upload_time DESC')
        
        rows = c.fetchall()
        conn.close()
        
        videos = []
        for row in rows:
            videos.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'filename': row[3],
                'knowledge_tag': row[4],
                'class_id': row[5],
                'teacher_username': row[6],
                'upload_time': row[7],
                'file_size': row[8],
                'duration': row[9],
                'url': f'/videos/{row[3]}'
            })
        
        return jsonify({'code': 200, 'data': videos})
    except Exception as e:
        logger.error(f"获取视频列表失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/video/upload', methods=['POST'])
@role_required(['teacher'])
def upload_video():
    """上传视频"""
    try:
        title = request.form.get('title')
        description = request.form.get('description', '')
        knowledge_tag = request.form.get('knowledge_tag', '')
        class_id = request.form.get('class_id')
        teacher_username = request.form.get('username')
        video_file = request.files.get('video')
        
        if not title or not video_file:
            return jsonify({'code': 400, 'msg': '标题和视频文件不能为空'})
        
        # 检查文件类型
        filename = video_file.filename.lower()
        if not (filename.endswith('.mp4') or filename.endswith('.avi') or filename.endswith('.mov') or filename.endswith('.wmv')):
            return jsonify({'code': 400, 'msg': '请上传有效的视频文件'})
        
        # 保存文件
        safe_filename = secure_filename(video_file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{safe_filename}"
        file_path = os.path.join(VIDEO_DIR, saved_filename)
        video_file.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        if file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        
        # 保存到数据库
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        c.execute('''INSERT INTO videos 
                    (title, description, filename, knowledge_tag, class_id, teacher_username, upload_time, file_size)
                    VALUES (?,?,?,?,?,?,?,?)''',
                  (title, description, saved_filename, knowledge_tag, class_id, teacher_username, 
                   datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), size_str))
        video_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'code': 200,
            'msg': '视频上传成功',
            'data': {
                'id': video_id,
                'title': title,
                'url': f'/videos/{saved_filename}'
            }
        })
    except Exception as e:
        logger.error(f"上传视频失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/video/delete', methods=['POST'])
@role_required(['teacher'])
def delete_video():
    """删除视频"""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return jsonify({'code': 400, 'msg': '视频ID不能为空'})
        
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        
        # 获取文件名
        c.execute('SELECT filename FROM videos WHERE id=?', (video_id,))
        row = c.fetchone()
        if row:
            filename = row[0]
            file_path = os.path.join(VIDEO_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        c.execute('DELETE FROM videos WHERE id=?', (video_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 200, 'msg': '删除成功'})
    except Exception as e:
        logger.error(f"删除视频失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/video/update', methods=['POST'])
@role_required(['teacher'])
def update_video():
    """更新视频信息"""
    try:
        data = request.json
        video_id = data.get('video_id')
        title = data.get('title')
        description = data.get('description')
        knowledge_tag = data.get('knowledge_tag')
        
        if not video_id or not title:
            return jsonify({'code': 400, 'msg': '视频ID和标题不能为空'})
        
        conn = sqlite3.connect('videos.db')
        c = conn.cursor()
        c.execute('''UPDATE videos 
                     SET title=?, description=?, knowledge_tag=?
                     WHERE id=?''',
                  (title, description, knowledge_tag, video_id))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 200, 'msg': '更新成功'})
    except Exception as e:
        logger.error(f"更新视频失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

@app.route('/api/video/recommend', methods=['POST'])
@role_required(['student'])
def recommend_videos():
    """根据薄弱知识点推荐视频"""
    try:
        data = request.json
        student_name = data.get('student_name')
        
        # 获取学生薄弱知识点
        conn_problem = get_db_connection('knowledge_graph.db')
        c_problem = conn_problem.cursor()
        c_problem.execute('''SELECT knowledge_point, error_count 
                             FROM student_problem_graph 
                             WHERE student_name=? AND error_count > 0
                             ORDER BY error_count DESC LIMIT 3''', (student_name,))
        weak_points = [row[0] for row in c_problem.fetchall()]
        close_db_connection(conn_problem)
        
        if not weak_points:
            weak_points = ['多态', '继承', '接口']
        
        # 根据薄弱点推荐视频
        conn_video = get_db_connection('videos.db')
        c_video = conn_video.cursor()
        recommend_videos = []
        
        for point in weak_points:
            c_video.execute('''SELECT id, title, description, knowledge_tag, filename 
                               FROM videos WHERE knowledge_tag LIKE ? ORDER BY upload_time DESC LIMIT 3''', 
                            (f'%{point}%',))
            videos = c_video.fetchall()
            for video in videos:
                recommend_videos.append({
                    'id': video[0],
                    'title': video[1],
                    'description': video[2],
                    'knowledge_tag': video[3],
                    'url': f'/videos/{video[4]}'
                })
        
        close_db_connection(conn_video)
        
        # 去重
        unique_videos = []
        seen = set()
        for v in recommend_videos:
            if v['title'] not in seen:
                unique_videos.append(v)
                seen.add(v['title'])
        
        return jsonify({'code': 200, 'data': unique_videos[:5]})
    except Exception as e:
        logger.error(f"推荐视频失败: {str(e)}")
        return jsonify({'code': 500, 'msg': str(e)}), 500

# ==================== 作业接口 ====================
@app.route('/api/homework/publish', methods=['POST'])
@role_required(['teacher'])
def hw_pub():
    """发布作业"""
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
        
        conn = sqlite3.connect('homework.db')
        c = conn.cursor()
        c.execute('''INSERT INTO homework (title, content, knowledge_tag, class_id, username, deadline, publish_time, hotwords) 
                     VALUES (?,?,?,?,?,?,?,?)''',
            (title, content, tag, class_id, username, deadline, publish_time, hotwords))
        homework_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # 发送通知
        if class_id and class_id != 'all':
            conn_class = sqlite3.connect('class.db')
            c_class = conn_class.cursor()
            c_class.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
            students = [row[0] for row in c_class.fetchall()]
            conn_class.close()
            
            conn_notify = sqlite3.connect('notifications.db')
            c_notify = conn_notify.cursor()
            for student in students:
                c_notify.execute('''INSERT INTO notifications (username, title, content, type, is_read, create_time) 
                                   VALUES (?,?,?,?,?,?)''',
                    (student, '📢 新作业发布', f'老师发布了新作业《{title}》，核心知识点：{tag}', 'homework', 0, publish_time))
            conn_notify.commit()
            conn_notify.close()
        
        return jsonify({'code':200, 'msg': '作业发布成功', 'data': {'id': homework_id, 'hotwords': hotwords.split(',')}})
    except Exception as e:
        logger.error(f"发布作业失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'发布作业失败: {str(e)}'}), 500

@app.route('/api/homework/teacher/list')
@role_required(['teacher'])
def hw_list_tea():
    """教师查看作业列表"""
    try:
        conn = sqlite3.connect('homework.db')
        c = conn.cursor()
        c.execute('SELECT id, title, content, knowledge_tag, class_id, username, deadline, publish_time, hotwords FROM homework ORDER BY publish_time DESC')
        rows = c.fetchall()
        conn.close()
        return jsonify([{
            'id': x[0],
            'title': x[1],
            'content': x[2],
            'knowledge_tag': x[3],
            'class_id': x[4],
            'username': x[5],
            'deadline': x[6],
            'publish_time': x[7],
            'hotwords': x[8].split(',') if x[8] else []
        } for x in rows])
    except Exception as e:
        logger.error(f"获取作业列表失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取作业列表失败: {str(e)}'}), 500

@app.route('/api/homework/student/list')
@role_required(['student'])
def hw_list_stu():
    """学生查看作业列表"""
    try:
        student = request.args.get('username')
        conn_class = sqlite3.connect('class.db')
        c_class = conn_class.cursor()
        c_class.execute('''SELECT c.id 
                     FROM class_student s
                     JOIN class c ON s.class_id = c.id
                     WHERE s.student_username=?''', (student,))
        cls_row = c_class.fetchone()
        class_id = cls_row[0] if cls_row else None
        conn_class.close()

        conn = sqlite3.connect('homework.db')
        c = conn.cursor()
        if class_id:
            c.execute('''SELECT id, title, content, knowledge_tag, deadline, publish_time, username, hotwords 
                         FROM homework 
                         WHERE class_id=? OR class_id IS NULL OR class_id='all'
                         ORDER BY publish_time DESC''', (class_id,))
        else:
            c.execute('''SELECT id, title, content, knowledge_tag, deadline, publish_time, username, hotwords 
                         FROM homework 
                         WHERE class_id IS NULL OR class_id='all'
                         ORDER BY publish_time DESC''')
        rows = c.fetchall()
        conn.close()
        
        return jsonify([{
            'id': x[0],
            'title': x[1],
            'content': x[2],
            'knowledge_tag': x[3],
            'deadline': x[4],
            'publish_time': x[5],
            'username': x[6],
            'hotwords': x[7].split(',') if x[7] else []
        } for x in rows])
    except Exception as e:
        logger.error(f"获取作业列表失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取作业列表失败: {str(e)}'}), 500

@app.route('/api/homework/submit', methods=['POST'])
@role_required(['student'])
def hw_sub():
    """提交作业"""
    try:
        d = request.json or request.form
        hw_id = d.get('homework_id')
        answer = d.get('answer')
        student = d.get('student_name', '学生')
        is_correct = d.get('is_correct', 0)
        score = d.get('score', 0)

        if not hw_id or not answer:
            return jsonify({'code':400, 'msg': '作业ID和答案不能为空'})

        submit_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db_connection('homework.db')
        c = conn.cursor()
        c.execute('''INSERT INTO homework_submit (homework_id, student_name, answer, is_correct, score, submit_time) 
                     VALUES (?,?,?,?,?,?)''',
            (hw_id, student, answer, is_correct, score, submit_time))
        submit_id = c.lastrowid

        # 记录错题
        if is_correct == 0:
            c.execute('SELECT knowledge_tag FROM homework WHERE id=?', (hw_id,))
            tag_row = c.fetchone()
            tag = tag_row[0] if tag_row else '核心知识点'
            
            tags = tag.split(',') if tag else ['核心知识点']
            for t in tags:
                t = t.strip()
                if t:
                    conn_problem = get_db_connection('knowledge_graph.db')
                    c_problem = conn_problem.cursor()
                    c_problem.execute('''SELECT id FROM student_problem_graph 
                                         WHERE student_name=? AND knowledge_point=?''', (student, t))
                    existing = c_problem.fetchone()
                    if existing:
                        c_problem.execute('''UPDATE student_problem_graph 
                                             SET error_count = error_count + 1, last_error_time=?
                                             WHERE student_name=? AND knowledge_point=?''',
                                          (submit_time, student, t))
                    else:
                        c_problem.execute('''INSERT INTO student_problem_graph 
                                             (student_name, knowledge_point, error_count, last_error_time, recommended_count)
                                             VALUES (?,?,1,?,0)''', (student, t, submit_time))
                    close_db_connection(conn_problem)

        close_db_connection(conn)

        conn_hw = get_db_connection('homework.db')
        c_hw = conn_hw.cursor()
        c_hw.execute('SELECT title FROM homework WHERE id=?', (hw_id,))
        hw_title = c_hw.fetchone()[0]
        close_db_connection(conn_hw)

        if score >= 90:
            comment = "语法正常，逻辑合理，结构良好，抄袭风险：低"
        elif score >= 60:
            comment = "语法正常，逻辑基本合理，结构良好，抄袭风险：低"
        else:
            comment = "存在语法或逻辑错误，建议检查后重写，抄袭风险：低"

        return jsonify({
            'code':200,
            'msg': '提交成功',
            'data': {
                'score': score,
                'hw_title': hw_title,
                'comment': comment
            }
        })
    except Exception as e:
        logger.error(f"提交作业失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'提交作业失败: {str(e)}'}), 500

@app.route('/api/homework/submit/list', methods=['POST'])
@role_required(['teacher'])
def sub_list():
    """查看作业提交列表"""
    try:
        hid = request.json.get('homework_id')
        if not hid:
            return jsonify({'code':400, 'msg': '作业ID不能为空'})
            
        conn = sqlite3.connect('homework.db')
        c = conn.cursor()
        c.execute('SELECT student_name, answer, is_correct, score, submit_time FROM homework_submit WHERE homework_id=?', (hid,))
        rows = c.fetchall()
        conn.close()
        return jsonify([{
            'student': x[0],
            'answer': x[1],
            'is_correct': x[2],
            'score': x[3],
            'submit_time': x[4]
        } for x in rows])
    except Exception as e:
        logger.error(f"获取提交列表失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'获取提交列表失败: {str(e)}'}), 500

# ==================== 班级接口 ====================
@app.route('/api/class/create', methods=['POST'])
@role_required(['teacher'])
def class_create():
    """创建班级"""
    d = request.json
    teacher = d.get('username')
    name = d.get('class_name')
    code = d.get('class_code')
    course = d.get('course', '面向对象程序设计')
    
    if not all([teacher, name, code]):
        return jsonify({'code':400,'msg':'参数不全'})
    
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO class (teacher_username, class_name, class_code, course, student_count) 
                     VALUES (?,?,?,?,0)''',
            (teacher, name, code, course))
        conn.commit()
        class_id = c.lastrowid
        conn.close()
        return jsonify({'code':200,'msg':'创建成功', 'data': {'id': class_id, 'inviteCode': code}})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'code':400,'msg':'班级码已存在'})
    except Exception as e:
        logger.error(f"创建班级失败: {str(e)}")
        conn.close()
        return jsonify({'code':500,'msg':'创建失败：'+str(e)})

@app.route('/api/class/my', methods=['POST'])
@role_required(['teacher'])
def my_class():
    """教师查看自己的班级"""
    d = request.json
    teacher = d.get('username')
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('SELECT id, class_name, class_code, course, student_count FROM class WHERE teacher_username=?', (teacher,))
    rows = c.fetchall()
    conn.close()
    return jsonify([{'id':x[0],'name':x[1],'code':x[2],'course':x[3],'studentCount':x[4]} for x in rows])

@app.route('/api/class/join', methods=['POST'])
@role_required(['student'])
def class_join():
    """学生加入班级"""
    d = request.json
    student = d.get('username')
    code = d.get('class_code')
    
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('SELECT id FROM class WHERE class_code=?', (code,))
    clz = c.fetchone()
    if not clz:
        conn.close()
        return jsonify({'code':400,'msg':'班级码错误'})
    
    class_id = clz[0]
    try:
        c.execute('INSERT INTO class_student (class_id, student_username) VALUES (?,?)',
            (class_id, student))
        c.execute('UPDATE class SET student_count = student_count + 1 WHERE id=?', (class_id,))
        conn.commit()
        conn.close()
        return jsonify({'code':200,'msg':'加入成功', 'data': {'class_id': class_id}})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'code':400,'msg':'已加入该班级'})
    except Exception as e:
        logger.error(f"加入班级失败: {str(e)}")
        conn.close()
        return jsonify({'code':500,'msg':'加入失败：'+str(e)})

@app.route('/api/student/class', methods=['POST'])
@role_required(['student'])
def student_class():
    """查看学生所在班级"""
    d = request.json
    student = d.get('username')
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('''SELECT c.id, c.class_name, c.teacher_username, c.course, c.student_count
                 FROM class_student s
                 JOIN class c ON s.class_id = c.id
                 WHERE s.student_username=?''', (student,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'id':row[0],'name':row[1],'teacher':row[2],'course':row[3],'studentCount':row[4]})
    return jsonify({})

@app.route('/api/class/students', methods=['POST'])
@role_required(['teacher'])
def class_students():
    """教师查看班级学生"""
    d = request.json
    class_id = d.get('class_id')
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
    rows = c.fetchall()
    conn.close()
    return jsonify([x[0] for x in rows])

@app.route('/api/class/remove_student', methods=['POST'])
@role_required(['teacher'])
def class_remove_student():
    """从班级移除学生"""
    d = request.json
    class_id = d.get('class_id')
    student = d.get('student_username')
    
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('DELETE FROM class_student WHERE class_id=? AND student_username=?', (class_id, student))
    c.execute('UPDATE class SET student_count = student_count - 1 WHERE id=?', (class_id,))
    conn.commit()
    conn.close()
    return jsonify({'code':200,'msg':'移除成功'})

@app.route('/api/class/delete', methods=['POST'])
@role_required(['teacher'])
def class_delete():
    """删除班级"""
    d = request.json
    class_id = d.get('class_id')
    
    conn = sqlite3.connect('class.db')
    c = conn.cursor()
    c.execute('DELETE FROM class_student WHERE class_id=?', (class_id,))
    c.execute('DELETE FROM class WHERE id=?', (class_id,))
    conn.commit()
    conn.close()
    return jsonify({'code':200,'msg':'删除成功'})

# ==================== 消息通知接口 ====================
@app.route('/api/notification/list', methods=['GET'])
def get_notifications():
    """获取消息通知"""
    try:
        username = request.args.get('username')
        role = request.args.get('role')
        if not username or not role:
            return jsonify({'code': 400, 'msg': '缺少用户名/角色参数'})
        
        conn = sqlite3.connect('notifications.db')
        c = conn.cursor()
        c.execute('''SELECT id, title, content, type, is_read, create_time 
                     FROM notifications 
                     WHERE username=? 
                     ORDER BY create_time DESC''', (username,))
        rows = c.fetchall()
        conn.close()
        
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

@app.route('/api/notification/read', methods=['POST'])
def mark_notification_read():
    """标记通知为已读"""
    try:
        data = request.json
        notify_id = data.get('id')
        if not notify_id:
            return jsonify({'code': 400, 'msg': '缺少通知ID'})
        
        conn = sqlite3.connect('notifications.db')
        c = conn.cursor()
        c.execute('UPDATE notifications SET is_read=1 WHERE id=?', (notify_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 200, 'msg': '标记已读成功'})
    except Exception as e:
        logger.error(f"标记已读失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'标记已读失败: {str(e)}'}), 500

@app.route('/api/notification/clear', methods=['POST'])
def clear_notifications():
    """清空所有通知"""
    try:
        data = request.json
        username = data.get('username')
        if not username:
            return jsonify({'code': 400, 'msg': '缺少用户名'})
        
        conn = sqlite3.connect('notifications.db')
        c = conn.cursor()
        c.execute('DELETE FROM notifications WHERE username=?', (username,))
        conn.commit()
        conn.close()
        
        return jsonify({'code': 200, 'msg': '清空成功'})
    except Exception as e:
        logger.error(f"清空通知失败: {str(e)}")
        return jsonify({'code':500, 'msg': f'清空通知失败: {str(e)}'}), 500

# ==================== 班级学情分析接口 ====================
@app.route('/api/teacher/class_analysis')
@role_required(['teacher'])
def class_analysis():
    """班级学情大盘"""
    try:
        class_id = request.args.get('class_id')
        teacher_name = request.args.get('username')
        if not class_id:
            return jsonify({'code':400, 'msg':'班级ID不能为空'}), 400
        
        conn_class = get_db_connection('class.db')
        c_class = conn_class.cursor()
        c_class.execute('''SELECT c.class_name, c.course, COUNT(s.student_username) as student_count
                     FROM class c
                     LEFT JOIN class_student s ON c.id = s.class_id
                     WHERE c.id=? AND c.teacher_username=?''', (class_id, teacher_name))
        class_info = c_class.fetchone()
        if not class_info:
            close_db_connection(conn_class)
            return jsonify({'code':403, 'msg':'无该班级权限'}), 403
        
        class_name = class_info['class_name']
        course = class_info['course']
        student_count = class_info['student_count'] or 0
        close_db_connection(conn_class)

        conn_hw = get_db_connection('homework.db')
        c_hw = conn_hw.cursor()
        c_hw.execute('SELECT COUNT(*) FROM homework WHERE class_id=? OR class_id="all"', (class_id,))
        hw_total = c_hw.fetchone()[0]
        
        c_hw.execute('''SELECT COUNT(DISTINCT hs.homework_id || hs.student_name)
                     FROM homework_submit hs
                     JOIN homework h ON hs.homework_id = h.id
                     WHERE h.class_id=? OR h.class_id="all"''', (class_id,))
        submit_total = c_hw.fetchone()[0]
        complete_rate = round((submit_total / (student_count * hw_total) * 100), 1) if (student_count * hw_total) > 0 else 0
        
        c_hw.execute('''SELECT AVG(hs.score), MAX(hs.score), MIN(hs.score)
                     FROM homework_submit hs
                     JOIN homework h ON hs.homework_id = h.id
                     WHERE (h.class_id=? OR h.class_id="all") AND hs.score IS NOT NULL''', (class_id,))
        score_stats = c_hw.fetchone()
        avg_score = round(score_stats[0], 1) if score_stats[0] else 0
        max_score = score_stats[1] if score_stats[1] else 0
        min_score = score_stats[2] if score_stats[2] else 0
        close_db_connection(conn_hw)

        score_ranges = ['0-59', '60-74', '75-89', '90-100']
        score_range_count = [0, 0, 0, 0]
        conn_score = get_db_connection('homework.db')
        c_score = conn_score.cursor()
        c_score.execute('''SELECT hs.score
                     FROM homework_submit hs
                     JOIN homework h ON hs.homework_id = h.id
                     WHERE (h.class_id=? OR h.class_id="all") AND hs.score IS NOT NULL''', (class_id,))
        scores = [row[0] for row in c_score.fetchall()]
        close_db_connection(conn_score)
        for score in scores:
            if score < 60:
                score_range_count[0] += 1
            elif score <= 74:
                score_range_count[1] += 1
            elif score <= 89:
                score_range_count[2] += 1
            else:
                score_range_count[3] += 1

        core_knowledges = ["类", "对象", "封装", "继承", "多态", "接口"]
        class_knowledge_mastery = []
        
        conn_stu = get_db_connection('class.db')
        c_stu = conn_stu.cursor()
        c_stu.execute('SELECT student_username FROM class_student WHERE class_id=?', (class_id,))
        students = [row['student_username'] for row in c_stu.fetchall()]
        close_db_connection(conn_stu)
        
        for knowledge in core_knowledges:
            total_level = 0
            count = 0
            for student in students:
                level = calculate_mastery_level(student, knowledge)
                total_level += level
                count += 1
            avg_level = round(total_level / count, 1) if count > 0 else 0
            class_knowledge_mastery.append(avg_level)

        knowledge_pairs = list(zip(core_knowledges, class_knowledge_mastery))
        knowledge_pairs.sort(key=lambda x: x[1])
        weak_knowledges = [pair[0] for pair in knowledge_pairs[:3]]

        warning_students = []
        if student_count > 0 and len(students) > 0:
            conn_problem = get_db_connection('knowledge_graph.db')
            c_problem = conn_problem.cursor()
            for student in students[:2]:
                c_problem.execute('''SELECT knowledge_point, error_count 
                                     FROM student_problem_graph 
                                     WHERE student_name=? ORDER BY error_count DESC LIMIT 1''', (student,))
                worst = c_problem.fetchone()
                if worst and worst[1] >= 3:
                    warning_students.append({
                        'name': student,
                        'reason': f'「{worst[0]}」知识点连续{worst[1]}次出错'
                    })
            close_db_connection(conn_problem)

        return jsonify({
            'code': 200,
            'data': {
                'class_name': class_name,
                'course': course,
                'student_count': student_count,
                'hw_total': hw_total,
                'complete_rate': complete_rate,
                'score_stats': {
                    'avg_score': avg_score,
                    'max_score': max_score,
                    'min_score': min_score
                },
                'score_range': {
                    'labels': score_ranges,
                    'counts': score_range_count
                },
                'knowledge_mastery': {
                    'knowledges': core_knowledges,
                    'avg_levels': class_knowledge_mastery
                },
                'weak_knowledges': weak_knowledges,
                'warning_students': warning_students
            }
        })
    except Exception as e:
        logger.error(f"班级学情分析失败：{str(e)}")
        return jsonify({'code':500, 'msg':f'获取学情数据失败：{str(e)}'}), 500

# ==================== 数据重置接口 ====================
@app.route('/api/reset_data', methods=['POST'])
def reset_data():
    """重置数据（仅用于测试）"""
    try:
        # 清空班级表和关联表
        conn_class = get_db_connection('class.db')
        c_class = conn_class.cursor()
        c_class.execute('DELETE FROM class')
        c_class.execute('DELETE FROM class_student')
        close_db_connection(conn_class)

        # 清空学生用户（保留教师）
        conn_user = get_db_connection('users.db')
        c_user = conn_user.cursor()
        c_user.execute('DELETE FROM sys_user WHERE role = "student"')
        close_db_connection(conn_user)

        return jsonify({'code': 200, 'msg': '数据重置成功'})
    except Exception as e:
        logger.error(f"重置数据失败: {str(e)}")
        return jsonify({'code': 500, 'msg': '重置失败'}), 500

# ==================== 启动程序 ====================
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)