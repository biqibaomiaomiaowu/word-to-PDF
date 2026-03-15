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

    # 4. 深度检查（可选）
    is_deep = "--deep" in sys.argv
    
    if not is_deep:
        print("\n[4] 深度检查: 已跳过 (当前为纯本地依赖检查)")
        print("  💡 提示: 若要实际实例化引擎、检测模型可用性并自动下载缺失模型，请在此命令后加上 `--deep` 参数。")
        print("     示例: python check_paddle_env.py --deep")
        print("\n" + "="*50)
        print("本地自检完成！(基础环境一切正常)")
        print("="*50)
        return

    print("\n[4] 深度检查 PaddleOCR 3.4.0 实例化及 GPU 状态 (可能会下载官方模型，请耐心等待)")
    
    # 动态获取项目根目录，避免中文路径问题
    workspace_root = os.path.dirname(os.path.abspath(__file__))
    paddle_home = os.path.join(workspace_root, ".paddle_models").replace("\\", "\\\\")
    paddlex_home = os.path.join(workspace_root, ".paddlex_models").replace("\\", "\\\\")
    
    pp_script = """
import sys
import os
import traceback

# 强制注入自定义路径，避开 C盘/Users/中文用户名 造成的 C++ 路径读取截断 Bug
os.environ["PADDLE_HOME"] = "%s"
os.environ["PADDLEX_HOME"] = "%s"
# 彻底欺骗 Python 的 os.path.expanduser("~") 避免老版本写死 C盘
os.environ["USERPROFILE"] = "%s"
os.environ["HOME"] = "%s"

def safe_print(msg):
""" % (paddle_home, paddlex_home, workspace_root.replace("\\", "\\\\"), workspace_root.replace("\\", "\\\\"))

    pp_script += """
    # 强制将我们的标记写入真正的 stdout 并且即时刷新
    sys.__stdout__.write(msg + '\\n')
    sys.__stdout__.flush()

try:
    import paddle
    import paddleocr
    from paddleocr import PaddleOCR
    safe_print(f"INFO|PaddleOCR Version: {paddleocr.__version__}")

    use_gpu = False
    try:
        use_gpu = paddle.device.is_compiled_with_cuda() and paddle.device.get_device() != 'cpu'
    except: pass
    device_str = 'gpu' if use_gpu else 'cpu'

    try:
        if getattr(paddleocr, '__version__', '').startswith('3.'):      
            engine = PaddleOCR(lang='ch', device=device_str, use_doc_orientation_classify=False, use_textline_orientation=False, use_doc_unwarping=False, text_detection_model_name='PP-OCRv4_server_det', text_recognition_model_name='PP-OCRv4_server_rec')
        else:
            engine = PaddleOCR(lang='ch', use_gpu=use_gpu, show_log=False)
        safe_print(f"ENGINE_INIT_OK|USE_GPU={use_gpu}")
    except ValueError as e:
        if 'Unknown argument' in str(e):
            safe_print("ENGINE_INIT_FAIL|PARAM_INCOMPATIBLE|参数不兼容。检测到传递了旧版参数。详情: " + str(e))
        else:
            safe_print("ENGINE_INIT_FAIL|VALUE_ERROR|" + str(e))
    except Exception as e:
        err_str = str(e).replace('\\n', '  ')
        if 'inference.json' in err_str or 'inference.yml' in err_str:   
            s = f"ENGINE_INIT_FAIL|MODEL_CORRUPTED|模型未下载完整 或 模型目录结构不匹配 (找不到 inference 配置文件)。  --> [修复建议]: 请删除当前配置的新缓存目录然后重试！  --> [详情]: {err_str}"
            safe_print(s)
        else:
            safe_print(f"ENGINE_INIT_FAIL|UNKNOWN|{err_str}  Traceback: {traceback.format_exc().replace('\\n', '  ')}")

except Exception as e:
    safe_print(f"ENGINE_INIT_FAIL|INIT|{traceback.format_exc().replace('\\n', '  ')}")
sys.exit(0)
"""
    try:
        res = subprocess.run([python_exe, "-c", pp_script], capture_output=True, text=True, timeout=300)
        out = res.stdout
        err = res.stderr

        # 我们只需判断是否包含 ENGINE_INIT_OK
        if "ENGINE_INIT_OK|" in out or "ENGINE_INIT_OK|" in err:
            gpu_state = "开启" if "USE_GPU=True" in out or "USE_GPU=True" in err else "未开启 (CPU模式)"
            print("  ✅ 深度自检成功！(PaddleOCR 实例化正常)")
            print(f"  👉 GPU 加速状态: {gpu_state}")
            print(f"  💡 (提示: 子进程返回了 {res.returncode}, 即使 stderr 有大量警告/日志，也被认定为成功)")
            # 只有在明确失败或者有特别长的异常时才打印 stderr
        else:
            print(f"  ❌ 深度自检失败:")
            
            # 解析到底是哪种失败
            found_marker = False
            for line in (out + "\n" + err).splitlines():
                if "ENGINE_INIT_FAIL|" in line:
                    found_marker = True
                    parts = line.split("|", 2)
                    err_type = parts[1] if len(parts) > 1 else "未分类"
                    err_detail = parts[2] if len(parts) > 2 else "未知"
                    print(f"     👉 [{err_type}] 真实抛出的异常: {err_detail}")
            
            if not found_marker:
                print("     👉 [CRASH] 没有捕获到明确的 Python 异常标记，可能是底层 C++ 崩溃、内存不足或强行退出。")
                print(f"     [子进程退出码]: {res.returncode}")
                if err.strip():
                    print(f"\n  [标准错误流内容 (stderr)]:\n{err.strip()}")
                if out.strip():
                    print(f"\n  [标准输出流内容 (stdout)]:\n{out.strip()}")

    except subprocess.TimeoutExpired:
        print("  ❌ 深度自检超时 (超过5分钟)。模型可能在艰难下载中，或进程卡死。")
    except Exception as e:
        print(f"  ❌ 探测异常: {e}")

    print("\n" + "="*50)
    print("深度自检完成！")
    print("="*50)
    
if __name__ == "__main__":
    run_self_check()
