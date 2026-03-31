from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student/teacher
    name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    avatar = db.Column(db.String(200))  # 七牛云URL
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联
    classes_taught = db.relationship('Class', backref='teacher', lazy='dynamic')
    homework_submissions = db.relationship('HomeworkSubmission', backref='student', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'name': self.name,
            'email': self.email,
            'avatar': self.avatar
        }

class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(100))
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    student_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联
    students = db.relationship('ClassStudent', backref='class_info', lazy='dynamic')
    homeworks = db.relationship('Homework', backref='class_info', lazy='dynamic')

class ClassStudent(db.Model):
    __tablename__ = 'class_students'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('class_id', 'student_id'),)

class Homework(db.Model):
    __tablename__ = 'homeworks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    knowledge_tag = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    deadline = db.Column(db.DateTime)
    hotwords = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联
    submissions = db.relationship('HomeworkSubmission', backref='homework', lazy='dynamic')

class HomeworkSubmission(db.Model):
    __tablename__ = 'homework_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homeworks.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    answer = db.Column(db.Text)
    score = db.Column(db.Integer)
    ai_score = db.Column(db.Integer)  # AI评分
    ai_feedback = db.Column(db.Text)  # AI反馈
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('homework_id', 'student_id'),)

class Video(db.Model):
    __tablename__ = 'videos'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_url = db.Column(db.String(200))  # 七牛云URL
    cover_url = db.Column(db.String(200))  # 封面图
    knowledge_tag = db.Column(db.String(100))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)