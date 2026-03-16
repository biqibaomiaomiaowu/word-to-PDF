import os
import subprocess
import sys


def _configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _decode_output(data):
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def _run_import_probe(python_exe: str):
    check_script = """
import sys
missing = []
try: import paddle
except Exception: missing.append("paddlepaddle (GPU/CPU)")

try: import paddleocr
except Exception: missing.append("paddleocr")

try: import fitz
except Exception: missing.append("PyMuPDF (fitz)")

try: import cv2
except Exception: missing.append("opencv-python-headless (cv2)")

try: import docx
except Exception: missing.append("python-docx (docx)")

try: import numpy
except Exception: missing.append("numpy")

if missing:
    print("MISSING:", ", ".join(missing))
    sys.exit(1)
print("OK")
"""
    result = subprocess.run([python_exe, "-c", check_script], capture_output=True, timeout=45)
    return result.returncode, _decode_output(result.stdout), _decode_output(result.stderr)


def run_self_check():
    _configure_console_encoding()
    print("=" * 50)
    print("Paddle complex-layout environment self-check")
    print("=" * 50)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    paddle_env_dir = os.environ.get("PADDLE_ENV_DIR", os.path.join(base_dir, ".paddle_env"))

    print(f"\n[1] Check standalone env dir: {paddle_env_dir}")
    if os.path.exists(paddle_env_dir):
        print("  OK: directory exists")
    else:
        print("  FAIL: directory does not exist. Run `python -m venv .paddle_env` first.")
        return

    if sys.platform.startswith("win"):
        python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
    else:
        python_exe = os.path.join(paddle_env_dir, "bin", "python")

    env_python = os.environ.get("PADDLE_ENV_PYTHON")
    if env_python and os.path.exists(env_python):
        python_exe = env_python

    print(f"\n[2] Check Python executable: {python_exe}")
    if os.path.exists(python_exe):
        print("  OK: Python executable exists")
    else:
        print("  FAIL: Python executable does not exist")
        return

    print("\n[3] Check Python dependency imports")
    try:
        returncode, stdout, stderr = _run_import_probe(python_exe)
        if returncode == 0 and "OK" in stdout:
            print("  OK: imported paddle, paddleocr, fitz, cv2, docx, numpy")
        else:
            print(f"  FAIL: dependency probe failed: {stdout.strip()} {stderr.strip()}")
            return
    except Exception as exc:
        print(f"  FAIL: subprocess probe failed: {exc}")
        return

    is_deep = "--deep" in sys.argv
    backend_dir = os.path.join(base_dir, "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    caps = None
    caps_error = None
    try:
        from app.utils.paddle_runtime import get_paddle_capabilities

        caps = get_paddle_capabilities(use_cache=False)
    except Exception as exc:
        caps_error = str(exc)

    if not is_deep:
        print("\n[4] Deep check: skipped")
        print("  Tip: run `python check_paddle_env.py --deep` to verify structure API and models.")
        if caps:
            print(f"  PaddleX cache: {caps.get('paddlex_cache_home')}")
            print(f"  OCR models ready: {'yes' if caps.get('ocr_models_ready') else 'no'}")
            print(f"  Structure models ready: {'yes' if caps.get('structure_models_ready') else 'no'}")
            if caps.get("missing_structure_models"):
                print(f"  Missing structure models: {', '.join(caps['missing_structure_models'])}")
        elif caps_error:
            print(f"  Warning: unable to load structure capability info: {caps_error}")
        print("\n" + "=" * 50)
        print("Local self-check finished")
        print("=" * 50)
        return

    print("\n[4] Deep check: Paddle OCR / Structure capability")
    if caps_error:
        print(f"  FAIL: capability probe failed: {caps_error}")
        print("\n" + "=" * 50)
        print("Deep self-check finished")
        print("=" * 50)
        return

    if caps.get("import_error"):
        print(f"  FAIL: Paddle import failed: {caps['import_error'].splitlines()[-1]}")
    else:
        print(f"  OK: Paddle import succeeded: Paddle {caps.get('paddle_version')} / OCR {caps.get('ocr_version')}")
        print(f"  PaddleX cache: {caps.get('paddlex_cache_home')}")
        print(f"  OCR models ready: {'yes' if caps.get('ocr_models_ready') else 'no'}")
        if caps.get("missing_ocr_models"):
            print(f"    Missing OCR models: {', '.join(caps['missing_ocr_models'])}")
        print(f"  Structure API available: {'yes' if caps.get('structure_api_ok') else 'no'}")
        print(f"  Structure models ready: {'yes' if caps.get('structure_models_ready') else 'no'}")
        if caps.get("missing_structure_models"):
            print(f"    Missing structure models: {', '.join(caps['missing_structure_models'])}")
        print(f"  Structure pipeline available: {'yes' if caps.get('structure_available') else 'no'}")

    print("\n" + "=" * 50)
    print("Deep self-check finished")
    print("=" * 50)


if __name__ == "__main__":
    run_self_check()
