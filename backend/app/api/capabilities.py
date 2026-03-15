from fastapi import APIRouter
from typing import Dict, Any
import subprocess
import sys
import os

router = APIRouter()

_PADDLE_AVAILABLE_CACHE = None

def is_paddle_available() -> bool:
    global _PADDLE_AVAILABLE_CACHE
    if _PADDLE_AVAILABLE_CACHE is not None:
        return _PADDLE_AVAILABLE_CACHE

    # check if .paddle_env exists in project root
    # Project root should be one level up from backend
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    paddle_env_dir = os.path.join(base_dir, ".paddle_env")

    if sys.platform.startswith("win"):
        python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
    else:
        python_exe = os.path.join(paddle_env_dir, "bin", "python")

    if not os.path.exists(python_exe):
        _PADDLE_AVAILABLE_CACHE = False
        return False

    try:
        # Check if paddle is importable and prints version successfully
        result = subprocess.run(
            [python_exe, "-c", "import paddle; print(paddle.__version__)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            _PADDLE_AVAILABLE_CACHE = True
            return True
        else:
            _PADDLE_AVAILABLE_CACHE = False
            return False
    except Exception:
        _PADDLE_AVAILABLE_CACHE = False
        return False

def is_pdf2docx_available() -> bool:
    try:
        import pdf2docx
        from pdf2docx import Converter
        return True
    except ImportError:
        return False
    except Exception:
        return False

def is_libreoffice_available() -> bool:
    executable = "soffice" if sys.platform.startswith("win") else "libreoffice"
    try:
        result = subprocess.run([executable, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False

@router.get("/capabilities", summary="Get system capabilities and configurations", response_model=Dict[str, Any])
async def get_capabilities() -> Dict[str, Any]:
    return {
        "paddle_available": is_paddle_available(),
        "pdf2docx_available": is_pdf2docx_available(),
        "libreoffice_available": is_libreoffice_available(),
        "word_ad_removal_available": True,
        "pdf_ad_removal_available": True,
        "supported_conversion_types": ["word_to_pdf", "pdf_to_word"],
        "supported_converter_modes": ["auto", "pdf2docx", "paddle"]
    }
