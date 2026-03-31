@echo off
echo 🚀 启动OOP智慧教学平台（生产模式）
echo ====================================

REM 设置环境变量
set FLASK_ENV=production
set PYTHONUNBUFFERED=1

REM 检查Redis是否运行
echo 🔍 检查Redis...
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Redis未运行，尝试启动...
    start /B redis-server
    timeout /t 3
) else (
    echo ✅ Redis已运行
)

REM 创建日志目录
if not exist logs mkdir logs

REM 启动Gunicorn
echo 🚀 启动Gunicorn服务器（4进程x2线程）...
gunicorn -c gunicorn.conf.py app:app

pause