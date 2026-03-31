# utils/storage.py
import os
import uuid
from datetime import datetime

class LocalStorage:
    """本地文件存储"""
    
    def __init__(self):
        self.upload_folder = 'uploads'
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def upload_file(self, file_data, filename=None):
        """保存文件到本地"""
        try:
            # 生成唯一文件名
            ext = os.path.splitext(filename)[1] if filename else ''
            new_filename = f"{uuid.uuid4().hex}{ext}"
            
            # 按日期分类
            date_path = datetime.now().strftime('%Y/%m/%d')
            save_dir = os.path.join(self.upload_folder, date_path)
            os.makedirs(save_dir, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(save_dir, new_filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # 返回访问URL
            return {
                'url': f'/uploads/{date_path}/{new_filename}',
                'path': file_path
            }
        except Exception as e:
            print(f"保存失败: {e}")
            return None

# 创建全局实例
storage = LocalStorage()