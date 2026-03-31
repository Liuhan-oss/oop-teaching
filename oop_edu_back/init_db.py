import sqlite3
import os

def init_all_databases():
    """初始化所有数据库文件"""
    
    # 删除已存在的数据库文件（可选）
    db_files = ['users.db', 'courses.db', 'homework.db', 'class.db', 'mastery.db', 'notifications.db']
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"已删除 {db_file}")
    
    # 1. 用户数据库
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sys_user
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, 
        password_hash TEXT, 
        role TEXT, 
        email TEXT,
        name TEXT DEFAULT '')''')
    conn.commit()
    conn.close()
    print("✅ users.db 初始化完成")
    
    # 2. 课程数据库
    conn = sqlite3.connect('courses.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS course
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT, 
        filename TEXT, 
        knowledge_tags TEXT)''')
    conn.commit()
    conn.close()
    print("✅ courses.db 初始化完成")
    
    # 3. 作业数据库
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
        publish_time TEXT)''')
    
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
    print("✅ homework.db 初始化完成")
    
    # 4. 班级数据库
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
    print("✅ class.db 初始化完成")
    
    # 5. 掌握度数据库
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
    print("✅ mastery.db 初始化完成")
    
    # 6. 通知数据库
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
    print("✅ notifications.db 初始化完成")
    
    print("\n🎉 所有数据库初始化完成！")

if __name__ == '__main__':
    init_all_databases()