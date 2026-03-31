@echo off
chcp 65001 >nul
title 安装 Redis for Windows

echo ================================
echo    安装 Redis for Windows
echo ================================
echo.

cd /d C:\

echo 1. 创建 Redis 目录...
if not exist redis mkdir redis
cd redis

echo 2. 下载 Redis 3.2.100...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/microsoftarchive/redis/releases/download/win-3.2.100/Redis-x64-3.2.100.zip' -OutFile 'redis.zip'"

echo 3. 解压文件...
powershell -Command "Expand-Archive -Path 'redis.zip' -DestinationPath '.' -Force"

echo 4. 清理临时文件...
del redis.zip

echo 5. 添加到系统 PATH...
setx PATH "%PATH%;C:\redis" /M

echo.
echo ================================
echo ✅ Redis 安装完成！
echo.
echo 启动 Redis 服务器:
echo   cd C:\redis ^&^& .\redis-server.exe
echo.
echo 测试连接（新开窗口）:
echo   cd C:\redis ^&^& .\redis-cli.exe ping
echo ================================

pause