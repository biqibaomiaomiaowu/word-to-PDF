import os
import sys
import subprocess

def run_self_check():
    print("="*50)
    print("Paddle 复杂版面引擎 环境完整自检工具")
    print("="*50)

    # 1. 查找 .paddle_env 路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    paddle_env_dir = os.environ.get("PADDLE_ENV_DIR", os.path.join(base_dir, ".paddle_env"))
    
    print(f"\n[1] 检查独立环境目录: {paddle_env_dir}")
    if os.path.exists(paddle_env_dir):
        print("  ✅ 目录存在")
    else:
        print("  ❌ 目录不存在! 请运行 `python -m venv .paddle_env` 创建")
        return

    # 2. 检查 Python 解释器
    if sys.platform.startswith("win"):
        python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
    else:
        python_exe = os.path.join(paddle_env_dir, "bin", "python")
        
    env_python = os.environ.get("PADDLE_ENV_PYTHON")
    if env_python and os.path.exists(env_python):
        python_exe = env_python

    print(f"\n[2] 检查可执行文件: {python_exe}")
    if os.path.exists(python_exe):
        print("  ✅ Python 执行文件存在")
    else:
        print("  ❌ Python 执行文件不存在!")
        return

    # 3. 检查基础依赖导入
    print("\n[3] 检查 Python 依赖导入")
    check_script = """
import sys
missing = []
try: import paddle
except: missing.append("paddlepaddle (GPU/CPU)")

try: import paddleocr
except: missing.append("paddleocr")

try: import fitz
except: missing.append("PyMuPDF (fitz)")

try: import cv2
except: missing.append("opencv-python-headless (cv2)")

try: import docx
except: missing.append("python-docx (docx)")

try: import numpy
except: missing.append("numpy")

if missing:
    print("MISSING:", ", ".join(missing))
    sys.exit(1)
print("OK")
"""
    try:
        res = subprocess.run([python_exe, "-c", check_script], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and "OK" in res.stdout:
            print("  ✅ 所有基础依赖导入成功 (paddle, paddleocr, fitz, cv2, docx, numpy)")
        else:
            print(f"  ❌ 依赖缺失: {res.stdout.strip()} {res.stderr.strip()}")
            return
    except Exception as e:
        print(f"  ❌ 探测子进程失败: {e}")
        return

    # 4. 检查 PaddleOCR 3.x 实例化及 GPU 状态
    print("\n[4] 检查 PaddleOCR 3.4.0 实例化及 GPU 状态 (这可能需要几秒到十几秒)")
    pp_script = """
import sys
import traceback
try:
    import paddle
    import paddleocr
    from paddleocr import PaddleOCR
    print(f"INFO|PaddleOCR Version: {paddleocr.__version__}")
    
    use_gpu = False
    try:
        use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.get_device() != 'cpu'
    except:
        pass
        
    engine = PaddleOCR(show_log=False, lang='ch', use_gpu=use_gpu)
    print(f"SUCCESS|USE_GPU={use_gpu}")
except Exception as e:
    print("FAILED|\\n" + traceback.format_exc())
"""
    try:
        res = subprocess.run([python_exe, "-c", pp_script], capture_output=True, text=True, timeout=30)
        out = res.stdout.strip()
        
        last_line = out.split("\\n")[-1] if out else ""
        if "SUCCESS" in out:
            print("  ✅ PaddleOCR 3.x 实例化成功！")
            if "USE_GPU=True" in out:
                print("  ✅ GPU 硬件加速已 [开启]")
            else:
                print("  ⚠️ GPU 硬件加速未开启 (运行模式: CPU)。如果是带独立显卡的机器，建议安装 paddlepaddle-gpu 加速。")
        else:
            print(f"  ❌ PaddleOCR 实例化失败\\n{out}\\n{res.stderr}")
    except subprocess.TimeoutExpired:
        print("  ❌ PaddleOCR 实例化超时 (超过30秒)，这通常是因为缺少底层动态链接库或内存不足。")
    except Exception as e:
        print(f"  ❌ 探测异常: {e}")

    print("\n" + "="*50)
    print("自检完成！")
    print("="*50)

if __name__ == "__main__":
    run_self_check()
