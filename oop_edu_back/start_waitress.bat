@echo off
chcp 65001 >nul
title OOP教学平台 - Waitress服务器

echo ================================
echo    OOP教学平台启动程序
echo ================================
echo.

cd /d C:\Users\lh\Documents\opp_edu_back

echo 当前目录: %CD%
echo.

echo 1. 检查日志目录...
if not exist logs (
    mkdir logs
    echo ✅ 创建 logs 文件夹
) else (
    echo ℹ️ logs 文件夹已存在
)

echo.
echo 2. 启动 Waitress 服务器...
echo.

python start_waitress.py

pause