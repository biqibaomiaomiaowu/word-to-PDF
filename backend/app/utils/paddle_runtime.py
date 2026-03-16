import json
import os
import subprocess
import sys
import tempfile
import time

CACHE_TTL = 60  # seconds
_PADDLE_CAPABILITIES_CACHE = None
_PADDLE_CHECK_TIME = 0.0

_OCR_MODELS = [
    "PP-OCRv4_server_det",
    "PP-OCRv4_server_rec",
]

_STRUCTURE_MODELS = [
    "PP-DocLayout_plus-L",
    "PP-Chart2Table",
    "PP-OCRv5_server_det",
    "PP-OCRv5_server_rec",
    "PP-LCNet_x1_0_table_cls",
    "SLANeXt_wired",
    "SLANet_plus",
    "RT-DETR-L_wired_table_cell_det",
    "RT-DETR-L_wireless_table_cell_det",
]

_PROBE_SCRIPT = r"""
import json
import os
import traceback
from pathlib import Path

MODEL_FILES = ("inference.json", "inference.yml")
OCR_MODELS = %s
STRUCTURE_MODELS = %s

result = {
    "paddle_import_ok": False,
    "ocr_api_ok": False,
    "structure_api_ok": False,
    "ocr_models_ready": False,
    "structure_models_ready": False,
    "ocr_available": False,
    "structure_available": False,
    "missing_ocr_models": [],
    "missing_structure_models": [],
    "import_error": None,
    "structure_api_error": None,
}

def has_model(cache_root, model_name):
    model_dir = Path(cache_root) / "official_models" / model_name
    return model_dir.is_dir() and any((model_dir / marker).exists() for marker in MODEL_FILES)

cache_root = Path(os.environ.get("PADDLE_PDX_CACHE_HOME", Path.home() / ".paddlex"))
result["paddlex_cache_home"] = str(cache_root)

try:
    import paddle
    import paddleocr

    result["paddle_import_ok"] = True
    result["paddle_version"] = getattr(paddle, "__version__", "unknown")
    result["ocr_version"] = getattr(paddleocr, "__version__", "unknown")

    from paddleocr import PaddleOCR
    result["ocr_api_ok"] = PaddleOCR is not None

    try:
        from paddleocr import PPStructureV3
        result["structure_api_ok"] = PPStructureV3 is not None
    except Exception as exc:
        result["structure_api_error"] = str(exc)
except Exception:
    result["import_error"] = traceback.format_exc()

result["missing_ocr_models"] = [name for name in OCR_MODELS if not has_model(cache_root, name)]
result["missing_structure_models"] = [name for name in STRUCTURE_MODELS if not has_model(cache_root, name)]
result["ocr_models_ready"] = not result["missing_ocr_models"]
result["structure_models_ready"] = not result["missing_structure_models"]
result["ocr_available"] = result["ocr_api_ok"] and result["ocr_models_ready"]
result["structure_available"] = result["structure_api_ok"] and result["structure_models_ready"]

print(json.dumps(result, ensure_ascii=False))
""" % (repr(_OCR_MODELS), repr(_STRUCTURE_MODELS))


def get_workspace_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def build_paddle_env() -> dict[str, str]:
    root = get_workspace_root()
    temp_dir = _pick_temp_dir(root)
    home_dir = os.path.join(root, ".cache", "home")
    os.makedirs(home_dir, exist_ok=True)
    if os.name == "nt":
        os.makedirs(os.path.join(home_dir, "AppData", "Roaming"), exist_ok=True)
        os.makedirs(os.path.join(home_dir, "AppData", "Local"), exist_ok=True)
    env = os.environ.copy()
    env["PADDLE_HOME"] = os.path.join(root, ".paddle_models")
    env["PADDLE_PDX_CACHE_HOME"] = os.path.join(root, ".paddlex")
    env["PADDLE_INFERENCE_MODEL_DIR"] = os.path.join(root, ".paddle_inference")
    env["USERPROFILE"] = home_dir
    env["HOME"] = home_dir
    if os.name == "nt":
        env["APPDATA"] = os.path.join(home_dir, "AppData", "Roaming")
        env["LOCALAPPDATA"] = os.path.join(home_dir, "AppData", "Local")
    env["TEMP"] = temp_dir
    env["TMP"] = temp_dir
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    return env


def _pick_temp_dir(root: str) -> str:
    candidates = []
    if os.name == "nt":
        candidates.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp"))
    candidates.extend(
        [
            os.path.join(root, ".paddlex_runtime_tmp"),
            os.path.join(root, ".cache", "tmp"),
            os.environ.get("TEMP"),
            os.environ.get("TMP"),
        ]
    )

    for candidate in candidates:
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=candidate)
            os.close(fd)
            os.unlink(probe)
            return candidate
        except Exception:
            continue

    return tempfile.gettempdir()


def get_paddle_python_path() -> str | None:
    env_python = os.environ.get("PADDLE_ENV_PYTHON")
    if env_python and os.path.exists(env_python) and os.path.isfile(env_python):
        return env_python

    env_dir = os.environ.get("PADDLE_ENV_DIR")
    base_dir = get_workspace_root()
    paddle_env_dir = env_dir if env_dir else os.path.join(base_dir, ".paddle_env")

    if sys.platform.startswith("win"):
        python_exe = os.path.join(paddle_env_dir, "Scripts", "python.exe")
    else:
        python_exe = os.path.join(paddle_env_dir, "bin", "python")

    return python_exe if os.path.exists(python_exe) else None


def _run_capability_probe() -> dict:
    python_exe = get_paddle_python_path()
    if not python_exe:
        return {
            "paddle_import_ok": False,
            "ocr_api_ok": False,
            "structure_api_ok": False,
            "ocr_available": False,
            "structure_available": False,
            "missing_ocr_models": list(_OCR_MODELS),
            "missing_structure_models": list(_STRUCTURE_MODELS),
            "reason": "独立 Paddle 环境未找到，请检查 .paddle_env 或环境变量。",
        }

    try:
        result = subprocess.run(
            [python_exe, "-c", _PROBE_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            env=build_paddle_env(),
        )
    except subprocess.TimeoutExpired:
        return {
            "paddle_import_ok": False,
            "ocr_api_ok": False,
            "structure_api_ok": False,
            "ocr_available": False,
            "structure_available": False,
            "missing_ocr_models": list(_OCR_MODELS),
            "missing_structure_models": list(_STRUCTURE_MODELS),
            "reason": "Paddle capability probe timed out.",
        }
    except Exception as exc:
        return {
            "paddle_import_ok": False,
            "ocr_api_ok": False,
            "structure_api_ok": False,
            "ocr_available": False,
            "structure_available": False,
            "missing_ocr_models": list(_OCR_MODELS),
            "missing_structure_models": list(_STRUCTURE_MODELS),
            "reason": f"Paddle capability probe failed: {exc}",
        }

    stdout = _decode_output(result.stdout).strip()
    stderr = _decode_output(result.stderr).strip()
    if not stdout:
        return {
            "paddle_import_ok": False,
            "ocr_api_ok": False,
            "structure_api_ok": False,
            "ocr_available": False,
            "structure_available": False,
            "missing_ocr_models": list(_OCR_MODELS),
            "missing_structure_models": list(_STRUCTURE_MODELS),
            "reason": f"Paddle capability probe produced no stdout. stderr={stderr}",
        }

    try:
        capabilities = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return {
            "paddle_import_ok": False,
            "ocr_api_ok": False,
            "structure_api_ok": False,
            "ocr_available": False,
            "structure_available": False,
            "missing_ocr_models": list(_OCR_MODELS),
            "missing_structure_models": list(_STRUCTURE_MODELS),
            "reason": f"Unable to parse capability probe output. stdout={stdout}",
        }

    capabilities["probe_stderr"] = stderr
    capabilities["python_executable"] = python_exe
    capabilities["reason"] = ""
    return capabilities


def get_paddle_capabilities(use_cache: bool = True) -> dict:
    global _PADDLE_CAPABILITIES_CACHE, _PADDLE_CHECK_TIME

    if use_cache and _PADDLE_CAPABILITIES_CACHE is not None:
        if time.time() - _PADDLE_CHECK_TIME < CACHE_TTL:
            return _PADDLE_CAPABILITIES_CACHE

    _PADDLE_CAPABILITIES_CACHE = _run_capability_probe()
    _PADDLE_CHECK_TIME = time.time()
    return _PADDLE_CAPABILITIES_CACHE


def _build_unavailable_reason(capabilities: dict, require_structure: bool) -> str:
    if capabilities.get("reason"):
        return capabilities["reason"]

    if capabilities.get("import_error"):
        return f"Paddle 依赖导入失败: {capabilities['import_error'].splitlines()[-1]}"

    if require_structure:
        if not capabilities.get("structure_api_ok"):
            return "PPStructureV3 API 不可用。"
        missing = capabilities.get("missing_structure_models") or []
        if missing:
            return f"复杂版面模型未就绪: {', '.join(missing)}"
        return "复杂版面能力不可用。"

    if not capabilities.get("ocr_api_ok"):
        return "PaddleOCR API 不可用。"

    missing = capabilities.get("missing_ocr_models") or []
    if missing:
        return f"OCR 模型未就绪: {', '.join(missing)}"

    return "Paddle 环境不可用。"


def check_paddle_available(use_cache: bool = True, require_structure: bool = False) -> tuple[bool, str]:
    capabilities = get_paddle_capabilities(use_cache=use_cache)
    available = capabilities.get("structure_available") if require_structure else capabilities.get("ocr_available")
    if available:
        return True, ""
    return False, _build_unavailable_reason(capabilities, require_structure=require_structure)
