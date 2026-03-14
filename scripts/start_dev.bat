@echo off
REM 一键启动开发环境脚本 (Windows)
chcp 65001 > nul

echo 正在检查环境...

REM 检查 LibreOffice
where libreoffice >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 警告: 未在 PATH 中找到 'libreoffice' 命令！后端转换可能失败。
    echo 请确保已安装 LibreOffice 并将其添加至系统环境变量。
) else (
    echo ✓ LibreOffice 已安装。
)

REM 启动后端 (新窗口)
echo 正在启动 FastAPI 后端 (端口 8000)...
start "FastAPI Backend" cmd /c "cd backend && call venv\Scripts\activate && uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM 启动前端 (新窗口)
echo 正在启动 Vite 前端 (端口 3000)...
start "Vite Frontend" cmd /c "cd frontend && npm run dev"

echo =========================================
echo 所有服务均已启动。
echo 前端地址: http://localhost:3000
echo 后端接口: http://localhost:8000/api
echo 请在弹出的命令提示符窗口中查看运行日志。
echo 关闭弹出的窗口即可停止服务。
echo =========================================
pause
