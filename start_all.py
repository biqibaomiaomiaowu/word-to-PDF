import os
import sys
import subprocess
import argparse
import threading
import shutil
import venv
import time
from pathlib import Path

# ==========================================
# 辅助函数: 日志打印
# ==========================================
def log_info(msg):
    print(f"\033[94m[Info]\033[0m {msg}")

def log_success(msg):
    print(f"\033[92m[Success]\033[0m {msg}")

def log_warn(msg):
    print(f"\033[93m[Warning]\033[0m {msg}")

def log_error(msg):
    print(f"\033[91m[Error]\033[0m {msg}")

# ==========================================
# 辅助函数: 实时输出子进程日志并带前缀
# ==========================================
def pipe_stream(stream, prefix, color_code):
    """读取流并打印带前缀的内容"""
    try:
        for line in iter(stream.readline, ''):
            if not line:
                break
            print(f"\033[{color_code}m{prefix}\033[0m {line.rstrip()}")
    except ValueError:
        pass
    finally:
        stream.close()

def run_service(cmd, cwd, env, prefix, color_code):
    """启动常驻服务并实时输出日志"""
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1, # 行缓冲
        universal_newlines=True
    )

    thread = threading.Thread(target=pipe_stream, args=(process.stdout, prefix, color_code))
    thread.daemon = True
    thread.start()
    return process

# ==========================================
# 后端环境准备
# ==========================================
def setup_backend(backend_dir: Path):
    log_info("正在检查后端环境...")
    venv_dir = backend_dir / "venv"

    # 1. 创建虚拟环境
    if not venv_dir.exists():
        log_info("未检测到虚拟环境，正在创建...")
        try:
            venv.create(venv_dir, with_pip=True)
            log_success("后端虚拟环境创建成功")
        except Exception as e:
            log_error(f"创建虚拟环境失败: {e}")
            sys.exit(1)

    # 获取 Python 解释器路径
    if os.name == "nt":
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        python_exe = venv_dir / "bin" / "python"

    if not python_exe.exists():
        log_error(f"找不到虚拟环境的 Python 解释器: {python_exe}")
        sys.exit(1)

    # 2. 安装依赖
    log_info("正在检查并安装后端依赖...")
    req_file = backend_dir / "requirements.txt"
    if not req_file.exists():
        log_error(f"未找到后端依赖文件: {req_file}")
        sys.exit(1)

    pip_cmd = [str(python_exe), "-m", "pip", "install", "-r", str(req_file)]

    # 动态显示进度 (简单的点)
    print("  安装中，请稍候...", flush=True)

    # 执行安装
    process = subprocess.run(
        pip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if process.returncode == 0:
        log_success("后端依赖安装成功")
    else:
        log_error("后端依赖安装失败，详细日志如下:")
        print(process.stdout)
        sys.exit(1)

    return python_exe

# ==========================================
# 前端环境准备
# ==========================================
def setup_frontend(frontend_dir: Path):
    log_info("正在检查前端环境...")

    # 检查 npm 是否存在
    if not shutil.which("npm"):
        log_error("未检测到 npm，请确保已安装 Node.js")
        sys.exit(1)

    node_modules_dir = frontend_dir / "node_modules"

    # 无论 node_modules 是否存在，尝试执行 npm install --legacy-peer-deps 确保最新
    log_info("正在执行 npm install --legacy-peer-deps (可能需要几分钟)...")

    npm_cmd = ["npm", "install", "--legacy-peer-deps"]
    # Windows 下 subprocess.Popen 调用 npm 最好用 shell=True 或 npm.cmd
    if os.name == "nt":
        npm_cmd[0] = "npm.cmd"

    print("  安装中，请稍候...", flush=True)

    process = subprocess.run(
        npm_cmd,
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if process.returncode == 0:
        log_success("前端依赖安装成功")
    else:
        log_error("前端依赖安装失败，详细日志如下:")
        print(process.stdout)
        sys.exit(1)

# ==========================================
# 主流程
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="一键启动本地 Word 转 PDF 服务")
    parser.add_argument("--backend-port", type=int, default=8000, help="后端 FastAPI 服务端口 (默认: 8000)")
    parser.add_argument("--frontend-port", type=int, default=3000, help="前端 Vite 服务端口 (默认: 3000)")
    parser.add_argument("--disable-ad-removal", action="store_true", help="禁用智能去除末尾广告 (默认开启)")
    args = parser.parse_args()

    # 确定目录
    base_dir = Path(__file__).resolve().parent
    backend_dir = base_dir / "backend"
    frontend_dir = base_dir / "frontend"

    if not backend_dir.exists() or not frontend_dir.exists():
        log_error("脚本必须存放在项目根目录。找不到 backend/ 或 frontend/ 目录。")
        sys.exit(1)

    # 1. 检查环境与安装依赖
    python_exe = setup_backend(backend_dir)
    setup_frontend(frontend_dir)

    # 2. 准备环境变量
    env = os.environ.copy()

    # 前端环境变量: 指向后端的绝对地址 (解决端口变更时的访问问题)
    # Vite 会通过 import.meta.env 读取 VITE_ 前缀的变量
    env["VITE_API_URL"] = f"http://127.0.0.1:{args.backend_port}/api"
    env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{args.backend_port}/api"

    # 传递是否开启去除广告到前端环境变量
    # 实际上后端是在上传接口里接收 remove_ad 参数，我们可以通过 VITE_ 环境变量控制前端的默认勾选状态
    if args.disable_ad_removal:
        env["VITE_DEFAULT_REMOVE_AD"] = "false"
        log_info("智能去除末尾广告已禁用(前端默认不勾选)")
    else:
        env["VITE_DEFAULT_REMOVE_AD"] = "true"
        log_info("智能去除末尾广告已开启(前端默认勾选)")

    processes = []

    try:
        # 3. 启动后端
        log_info(f"正在启动后端服务 (端口: {args.backend_port})...")
        backend_cmd = [str(python_exe), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.backend_port)]
        p_backend = run_service(backend_cmd, str(backend_dir), env, "[Backend]", "36") # 青色
        processes.append(p_backend)

        # 稍微等后端一下
        time.sleep(2)

        # 4. 启动前端
        log_info(f"正在启动前端服务 (端口: {args.frontend_port})...")
        npm_cmd = ["npm", "run", "dev", "--", "--port", str(args.frontend_port)]
        if os.name == "nt":
            npm_cmd[0] = "npm.cmd"

        p_frontend = run_service(npm_cmd, str(frontend_dir), env, "[Frontend]", "35") # 紫色
        processes.append(p_frontend)

        print("\n=========================================")
        log_success("所有服务均已启动！")
        print(f"前端访问地址: \033[4mhttp://localhost:{args.frontend_port}\033[0m")
        print(f"后端接口地址: \033[4mhttp://127.0.0.1:{args.backend_port}/api\033[0m")
        print("按 Ctrl+C 停止所有服务")
        print("=========================================\n")

        # 保持主线程存活，等待退出
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n")
        log_info("检测到退出信号，正在优雅关闭服务...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
        log_success("服务已完全停止。")

if __name__ == "__main__":
    # 为了兼容 Windows 终端的 ANSI 转义颜色序列
    if os.name == "nt":
        os.system("color")
    main()
