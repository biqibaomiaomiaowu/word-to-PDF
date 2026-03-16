from fastapi import APIRouter
from typing import Dict, Any
import subprocess
import sys
import os
from ..utils.paddle_runtime import check_paddle_available, get_paddle_capabilities

router = APIRouter()

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
    paddle_avail, paddle_reason = check_paddle_available(use_cache=True)
    paddle_structure_avail, paddle_structure_reason = check_paddle_available(use_cache=True, require_structure=True)
    paddle_caps = get_paddle_capabilities(use_cache=True)
    return {
        "paddle_available": paddle_avail,
        "paddle_reason_if_unavailable": paddle_reason if not paddle_avail else None,
        "paddle_structure_available": paddle_structure_avail,
        "paddle_structure_reason_if_unavailable": paddle_structure_reason if not paddle_structure_avail else None,
        "paddle_missing_ocr_models": paddle_caps.get("missing_ocr_models", []),
        "paddle_missing_structure_models": paddle_caps.get("missing_structure_models", []),
        "paddlex_cache_home": paddle_caps.get("paddlex_cache_home"),
        "pdf2docx_available": is_pdf2docx_available(),
        "libreoffice_available": is_libreoffice_available(),
        "word_ad_removal_available": True,
        "pdf_ad_removal_available": True,
        "supported_conversion_types": ["word_to_pdf", "pdf_to_word"],
        "supported_converter_modes": ["auto", "pdf2docx", "paddle"]
    }
