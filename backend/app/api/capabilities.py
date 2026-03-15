from fastapi import APIRouter
from typing import Dict, Any
import subprocess
import sys

router = APIRouter()

def is_paddle_available() -> bool:
    try:
        import paddleocr
        from paddleocr import PPStructure
        return True
    except ImportError:
        return False
    except Exception:
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
