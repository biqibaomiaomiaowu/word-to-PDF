from pathlib import Path as _Path
import runpy as _runpy

if __name__ == "__main__":
    _runpy.run_path(str(_Path(__file__).with_name("check_paddle_env_v2.py")), run_name="__main__")
    raise SystemExit(0)

import os
import sys
import subprocess

def _configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

def run_self_check():
    _configure_console_encoding()
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

    # 4. 深度检查（可选）
    is_deep = "--deep" in sys.argv
    backend_dir = os.path.join(base_dir, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    caps = None
    caps_error = None
    try:
        from app.utils.paddle_runtime import get_paddle_capabilities
        caps = get_paddle_capabilities(use_cache=False)
    except Exception as e:
        caps_error = str(e)
    
    if not is_deep:
        print("\n[4] 深度检查: 已跳过 (当前为纯本地依赖检查)")
        print("  💡 提示: 若要实际实例化引擎、检测模型可用性并自动下载缺失模型，请在此命令后加上 `--deep` 参数。")
        print("     示例: python check_paddle_env.py --deep")
        if caps:
            print(f"  👉 PaddleX 缓存目录: {caps.get('paddlex_cache_home')}")
            print(f"  👉 OCR 模型就绪: {'是' if caps.get('ocr_models_ready') else '否'}")
            print(f"  👉 复杂版面模型就绪: {'是' if caps.get('structure_models_ready') else '否'}")
            if caps.get("missing_structure_models"):
                print(f"  👉 缺失的复杂版面模型: {', '.join(caps['missing_structure_models'])}")
        elif caps_error:
            print(f"  ⚠️ 无法读取结构化能力信息: {caps_error}")
        print("\n" + "="*50)
        print("本地自检完成！(基础环境一切正常)")
        print("="*50)
        return

    print("\n[4] 深度检查 Paddle OCR / Structure 能力状态")
    if caps_error:
        print(f"  ❌ 无法执行能力探测: {caps_error}")
        print("\n" + "="*50)
        print("深度自检完成！")
        print("="*50)
        return

    if caps.get("import_error"):
        print(f"  ❌ Paddle 依赖导入失败: {caps['import_error'].splitlines()[-1]}")
    else:
        print(f"  ✅ Paddle 依赖导入成功: Paddle {caps.get('paddle_version')} / OCR {caps.get('ocr_version')}")
        print(f"  👉 PaddleX 缓存目录: {caps.get('paddlex_cache_home')}")
        print(f"  👉 OCR 模型就绪: {'是' if caps.get('ocr_models_ready') else '否'}")
        if caps.get("missing_ocr_models"):
            print(f"     缺失 OCR 模型: {', '.join(caps['missing_ocr_models'])}")
        print(f"  👉 复杂版面 API 可用: {'是' if caps.get('structure_api_ok') else '否'}")
        print(f"  👉 复杂版面模型就绪: {'是' if caps.get('structure_models_ready') else '否'}")
        if caps.get("missing_structure_models"):
            print(f"     缺失复杂版面模型: {', '.join(caps['missing_structure_models'])}")
        print(f"  👉 复杂版面链路可用: {'是' if caps.get('structure_available') else '否'}")

    print("\n" + "="*50)
    print("深度自检完成！")
    print("="*50)
    return

if __name__ == "__main__":
    run_self_check()
