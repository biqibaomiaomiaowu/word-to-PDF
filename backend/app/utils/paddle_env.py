import os
import sys
import subprocess
import time

# Cache variables
_PADDLE_AVAILABLE_CACHE = None
_PADDLE_REASON_CACHE = None
_PADDLE_CHECK_TIME = 0
CACHE_TTL = 60 # seconds

def get_paddle_python_path() -> str | None:
    """
    Returns the path to the Paddle environment Python executable.
    Checks environment variables first, then default .paddle_env.
    Returns None if not found.
    """
    # 1. Environment variable: Absolute path to Python executable
    env_python = os.environ.get("PADDLE_ENV_PYTHON")
    if env_python and os.path.exists(env_python) and os.path.isfile(env_python):
        return env_python

    # 2. Environment variable: Directory of the Paddle environment
    env_dir = os.environ.get("PADDLE_ENV_DIR")
    # Base dir: backend/app/utils -> backend/app -> backend -> root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    paddle_env_dir = env_dir if env_dir else os.path.join(base_dir, ".paddle_env")

    if sys.platform.startswith("win"):
        python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
    else:
        python_exe = os.path.join(paddle_env_dir, "bin", "python")

    if os.path.exists(python_exe):
        return python_exe

    return None

def force_refresh_paddle_check() -> tuple[bool, str]:
    global _PADDLE_AVAILABLE_CACHE, _PADDLE_REASON_CACHE, _PADDLE_CHECK_TIME
    
    python_exe = get_paddle_python_path()
    
    if not python_exe:
        _PADDLE_AVAILABLE_CACHE = False
        _PADDLE_REASON_CACHE = "独立 Paddle 环境未找到，请检查 .paddle_env 或环境变量"
        _PADDLE_CHECK_TIME = time.time()
        return False, _PADDLE_REASON_CACHE

    test_script = """
import sys
import traceback
try:
    import paddle
    import fitz
    import docx
    import cv2
    import numpy as np
    from paddleocr import PaddleOCR
    # Check instantiation with minimally impacting parameters
    import os
    use_gpu = False
    try:
        use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.get_device() != 'cpu'
    except:
        pass
    _ = PaddleOCR(use_angle_cls=False, lang="ch", use_gpu=use_gpu, show_log=False)
    print("ALL_GOOD")
except Exception as e:
    print(f"IMPORT_ERROR: {traceback.format_exc()}")
    sys.exit(1)
"""
    try:
        result = subprocess.run(
            [python_exe, "-c", test_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and "ALL_GOOD" in result.stdout:
            _PADDLE_AVAILABLE_CACHE = True
            _PADDLE_REASON_CACHE = ""
        else:
            _PADDLE_AVAILABLE_CACHE = False
            if "IMPORT_ERROR" in result.stdout:
                # Extract the error message
                lines = result.stdout.split('\n')
                err = [l for l in lines if l.startswith("IMPORT_ERROR")][0]
                _PADDLE_REASON_CACHE = f"依赖缺失或报错: {err}"
            else:
                _PADDLE_REASON_CACHE = f"子进程执行失败。返回码: {result.returncode}, 错误信息: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        _PADDLE_AVAILABLE_CACHE = False
        _PADDLE_REASON_CACHE = "capability_check_timeout"
    except Exception as e:
        _PADDLE_AVAILABLE_CACHE = False
        _PADDLE_REASON_CACHE = f"检测异常: {str(e)}"
        
    _PADDLE_CHECK_TIME = time.time()
    return _PADDLE_AVAILABLE_CACHE, _PADDLE_REASON_CACHE

def check_paddle_available(use_cache: bool = True) -> tuple[bool, str]:
    global _PADDLE_AVAILABLE_CACHE, _PADDLE_REASON_CACHE, _PADDLE_CHECK_TIME
    
    if use_cache and _PADDLE_AVAILABLE_CACHE is not None:
        if time.time() - _PADDLE_CHECK_TIME < CACHE_TTL:
            return _PADDLE_AVAILABLE_CACHE, _PADDLE_REASON_CACHE

    return force_refresh_paddle_check()
