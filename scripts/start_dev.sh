#!/bin/bash
# 一键启动开发环境脚本

echo "正在检查环境..."

# 检查 LibreOffice
if ! command -v libreoffice &> /dev/null; then
    echo "警告: 未在 PATH 中找到 'libreoffice' 命令！后端转换可能失败。"
    echo "请确保已安装 LibreOffice 并将其添加至系统环境变量。"
else
    echo "✓ LibreOffice 已安装。"
fi

# 启动后端 (后台)
echo "正在启动 FastAPI 后端 (端口 8000)..."
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# 启动前端 (后台)
echo "正在启动 Vite 前端 (端口 3000)..."
cd frontend
npm run dev > /dev/null 2>&1 &
FRONTEND_PID=$!
cd ..

echo "========================================="
echo "所有服务均已启动。"
echo "前端地址: http://localhost:3000"
echo "后端接口: http://localhost:8000/api"
echo "按 Ctrl+C 停止所有服务"
echo "========================================="

# 捕获 Ctrl+C 并关闭子进程
trap "echo '正在停止服务...'; kill $BACKEND_PID; kill $FRONTEND_PID; exit" SIGINT SIGTERM

# 保持脚本运行
wait
