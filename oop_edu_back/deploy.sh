#!/bin/bash

# deploy.sh - 一键部署脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}   OOP智慧教学平台 - 一键部署脚本     ${NC}"
echo -e "${BLUE}========================================${NC}"

# 检查Docker
echo -e "${YELLOW}🔍 检查Docker环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker未安装，请先安装Docker${NC}"
    exit 1
fi

# 检查docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose未安装，请先安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker环境正常${NC}"

# 创建必要的目录
echo -e "${YELLOW}📁 创建必要的目录...${NC}"
mkdir -p uploads videos pages mysql-init
echo -e "${GREEN}✅ 目录创建完成${NC}"

# 复制前端文件（假设前端文件在../frontend/）
echo -e "${YELLOW}📄 复制前端文件...${NC}"
if [ -d "../frontend" ]; then
    cp -r ../frontend/* ./pages/ 2>/dev/null || true
    echo -e "${GREEN}✅ 前端文件复制完成${NC}"
else
    echo -e "${YELLOW}⚠️ 未找到前端文件夹，跳过复制${NC}"
fi

# 停止并删除旧容器
echo -e "${YELLOW}🛑 停止旧容器...${NC}"
docker-compose down -v 2>/dev/null

# 构建新镜像
echo -e "${YELLOW}🏗️  构建Docker镜像...${NC}"
docker-compose build --no-cache

# 启动服务
echo -e "${YELLOW}🚀 启动服务...${NC}"
docker-compose up -d

# 等待数据库启动
echo -e "${YELLOW}⏳ 等待数据库启动（30秒）...${NC}"
sleep 30

# 初始化数据库
echo -e "${YELLOW}🗄️  初始化数据库...${NC}"
docker-compose exec -T web python -c "
from app import app
from models import db
with app.app_context():
    db.create_all()
    print('✅ 数据库初始化完成')
"

# 检查服务状态
echo -e "${YELLOW}🔍 检查服务状态...${NC}"
docker-compose ps

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "📊 访问地址: ${GREEN}http://localhost:5000${NC}"
echo -e "👤 测试账号: ${YELLOW}2024215612 / 123456${NC}"
echo -e "👤 教师账号: ${YELLOW}T2024001 / 123456${NC}"
echo -e "${BLUE}========================================${NC}"

# 显示容器日志
echo -e "${YELLOW}📋 查看容器日志（按Ctrl+C退出）${NC}"
docker-compose logs -f