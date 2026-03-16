import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import venv
from pathlib import Path


PADDLE_IMPORT_PACKAGE_MAP = {
    "paddle": lambda args: args.paddle_core_package,
    "paddleocr": lambda args: "paddleocr==3.4.0",
    "fitz": lambda args: "PyMuPDF",
    "cv2": lambda args: "opencv-python-headless",
    "docx": lambda args: "python-docx",
    "numpy": lambda args: "numpy",
}

PADDLE_MODEL_SOURCES = ["BOS", "ModelScope", "AIStudio"]
PADDLE_MODEL_MARKERS = ("inference.json", "inference.yml")
PADDLE_OPTIONAL_FORMULA_MODELS = ("PP-FormulaNet_plus-L",)


def configure_console_encoding():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def colorize(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def log_info(message: str):
    print(f"{colorize('[Info]', '94')} {message}")


def log_success(message: str):
    print(f"{colorize('[Success]', '92')} {message}")


def log_warn(message: str):
    print(f"{colorize('[Warning]', '93')} {message}")


def log_error(message: str):
    print(f"{colorize('[Error]', '91')} {message}")


def pipe_stream(stream, prefix: str, color_code: str):
    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            print(f"{colorize(prefix, color_code)} {line.rstrip()}")
    except ValueError:
        pass
    finally:
        stream.close()


def run_service(cmd: list[str], cwd: Path, env: dict[str, str], prefix: str, color_code: str):
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        universal_newlines=True,
    )
    thread = threading.Thread(target=pipe_stream, args=(process.stdout, prefix, color_code), daemon=True)
    thread.start()
    return process


def get_venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_virtualenv(venv_dir: Path, label: str) -> Path:
    if not venv_dir.exists():
        log_info(f"Creating {label} virtualenv: {venv_dir}")
        venv.create(venv_dir, with_pip=True)
        log_success(f"{label} virtualenv created")

    python_exe = get_venv_python(venv_dir)
    if not python_exe.exists():
        raise RuntimeError(f"Python executable not found for {label}: {python_exe}")
    return python_exe


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    kwargs = {
        "cwd": str(cwd) if cwd else None,
        "env": env,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT
    return subprocess.run(cmd, **kwargs)


def install_backend_requirements(backend_dir: Path, python_exe: Path):
    req_file = backend_dir / "requirements.txt"
    if not req_file.exists():
        raise RuntimeError(f"Backend requirements file not found: {req_file}")

    stamp_file = backend_dir / "venv" / ".requirements.sha256"
    current_hash = hash_file(req_file)
    installed_hash = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.exists() else ""
    if installed_hash == current_hash:
        log_success("Backend requirements already up to date")
        return

    log_info("Installing backend requirements...")
    result = run_command([str(python_exe), "-m", "pip", "install", "-r", str(req_file)], cwd=backend_dir, capture=True)
    if result.returncode != 0:
        raise RuntimeError(f"Backend dependency installation failed:\n{result.stdout}")

    stamp_file.write_text(current_hash, encoding="utf-8")
    log_success("Backend requirements installed")


def setup_backend(backend_dir: Path) -> Path:
    log_info("Checking backend environment...")
    python_exe = ensure_virtualenv(backend_dir / "venv", "backend")
    install_backend_requirements(backend_dir, python_exe)
    return python_exe


def setup_frontend(frontend_dir: Path):
    log_info("Checking frontend environment...")
    npm_executable = "npm.cmd" if os.name == "nt" else "npm"
    if not shutil.which(npm_executable):
        raise RuntimeError("npm was not found in PATH. Please install Node.js first.")

    if (frontend_dir / "node_modules").exists():
        log_success("Frontend node_modules already present")
        return

    log_info("Installing frontend dependencies with npm install --legacy-peer-deps ...")
    result = run_command([npm_executable, "install", "--legacy-peer-deps"], cwd=frontend_dir, capture=True)
    if result.returncode != 0:
        raise RuntimeError(f"Frontend dependency installation failed:\n{result.stdout}")
    log_success("Frontend dependencies installed")


def check_libreoffice():
    candidates = ["soffice", "soffice.exe", "libreoffice"]
    for executable in candidates:
        if shutil.which(executable):
            log_success(f"Detected LibreOffice command: {executable}")
            return
    log_warn("LibreOffice was not found in PATH. Word/PDF conversion may fail.")


def pick_temp_dir(base_dir: Path) -> Path:
    candidates: list[Path | None] = []
    if os.name == "nt":
        candidates.append(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Temp")
    candidates.extend(
        [
            base_dir / ".paddlex_runtime_tmp",
            base_dir / ".cache" / "tmp",
            Path(os.environ["TEMP"]) if os.environ.get("TEMP") else None,
            Path(os.environ["TMP"]) if os.environ.get("TMP") else None,
        ]
    )

    for candidate in candidates:
        if not candidate:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=str(candidate))
            os.close(fd)
            os.unlink(probe)
            return candidate
        except Exception:
            continue

    return Path(tempfile.gettempdir())


def get_workspace_home(base_dir: Path) -> Path:
    home_dir = base_dir / ".cache" / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        (home_dir / "AppData" / "Roaming").mkdir(parents=True, exist_ok=True)
        (home_dir / "AppData" / "Local").mkdir(parents=True, exist_ok=True)
    return home_dir


def build_workspace_env(base_dir: Path, paddle_python: Path | None = None) -> dict[str, str]:
    temp_root = base_dir / ".cache"
    temp_dir = pick_temp_dir(base_dir)
    home_dir = get_workspace_home(base_dir)
    for path in (
        temp_root / "hf",
        temp_root / "modelscope",
        base_dir / ".paddlex",
        base_dir / ".paddle_models",
        base_dir / ".paddle_inference",
    ):
        path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PADDLE_HOME"] = str(base_dir / ".paddle_models")
    env["PADDLE_PDX_CACHE_HOME"] = str(base_dir / ".paddlex")
    env["PADDLE_INFERENCE_MODEL_DIR"] = str(base_dir / ".paddle_inference")
    env["USERPROFILE"] = str(home_dir)
    env["HOME"] = str(home_dir)
    if os.name == "nt":
        env["APPDATA"] = str(home_dir / "AppData" / "Roaming")
        env["LOCALAPPDATA"] = str(home_dir / "AppData" / "Local")
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["HF_HOME"] = str(temp_root / "hf")
    env["MODELSCOPE_CACHE"] = str(temp_root / "modelscope")
    env["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    env["PADDLE_ENV_DIR"] = str(base_dir / ".paddle_env")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if paddle_python:
        env["PADDLE_ENV_PYTHON"] = str(paddle_python)
    return env


def probe_paddle_imports(python_exe: Path, env: dict[str, str]) -> dict:
    script = r"""
import importlib
import json

modules = ["paddle", "paddleocr", "fitz", "cv2", "docx", "numpy"]
missing = []
versions = {}
for name in modules:
    try:
        module = importlib.import_module(name)
        versions[name] = getattr(module, "__version__", "ok")
    except Exception:
        missing.append(name)

print(json.dumps({"missing_modules": missing, "versions": versions}, ensure_ascii=False))
"""
    result = run_command([str(python_exe), "-c", script], env=env, capture=True)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"Failed to probe Paddle imports:\n{result.stdout}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def install_paddle_dependencies(python_exe: Path, env: dict[str, str], missing_modules: list[str], args):
    packages = []
    for module_name in missing_modules:
        resolver = PADDLE_IMPORT_PACKAGE_MAP.get(module_name)
        if resolver:
            packages.append(resolver(args))

    unique_packages: list[str] = []
    seen = set()
    for package in packages:
        if package not in seen:
            unique_packages.append(package)
            seen.add(package)

    if not unique_packages:
        return

    log_info(f"Installing .paddle_env dependencies: {', '.join(unique_packages)}")
    result = run_command([str(python_exe), "-m", "pip", "install", *unique_packages], env=env, capture=True)
    if result.returncode != 0:
        raise RuntimeError(f".paddle_env dependency installation failed:\n{result.stdout}")
    log_success(".paddle_env dependencies installed")


def ensure_formula_dependency(python_exe: Path, env: dict[str, str]):
    required = {
        "latex2mathml": "latex2mathml",
        "lxml": "lxml",
    }
    missing_packages = []

    for module_name, package_name in required.items():
        probe = run_command([str(python_exe), "-c", f"import {module_name}"], env=env, capture=True)
        if probe.returncode != 0:
            missing_packages.append(package_name)

    if not missing_packages:
        log_success("Formula conversion dependencies already installed in .paddle_env")
        return

    log_info(f"Installing formula conversion dependencies: {', '.join(missing_packages)}")
    result = run_command([str(python_exe), "-m", "pip", "install", *missing_packages], env=env, capture=True)
    if result.returncode != 0:
        log_warn(f"Failed to install formula conversion dependencies. Formulas will stay as linear text. {result.stdout}")
        return
    log_success("Formula conversion dependencies installed")


def import_paddle_runtime(base_dir: Path):
    backend_path = str(base_dir / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.utils.paddle_runtime import get_paddle_capabilities

    return get_paddle_capabilities


def is_valid_model_dir(model_dir: Path) -> bool:
    return model_dir.is_dir() and any((model_dir / marker).exists() for marker in PADDLE_MODEL_MARKERS)


def get_missing_formula_models(base_dir: Path, include_formula: bool) -> list[str]:
    if not include_formula:
        return []
    missing = []
    for model_name in PADDLE_OPTIONAL_FORMULA_MODELS:
        if not is_valid_model_dir(base_dir / ".paddlex" / "official_models" / model_name):
            missing.append(model_name)
    return missing


def log_paddle_capabilities(capabilities: dict, missing_formula: list[str] | None = None):
    log_info(f"PaddleX cache: {capabilities.get('paddlex_cache_home')}")
    log_info(f"OCR models ready: {'yes' if capabilities.get('ocr_models_ready') else 'no'}")
    log_info(f"Structure API available: {'yes' if capabilities.get('structure_api_ok') else 'no'}")
    log_info(f"Structure models ready: {'yes' if capabilities.get('structure_models_ready') else 'no'}")
    log_info(f"Structure pipeline available: {'yes' if capabilities.get('structure_available') else 'no'}")
    if capabilities.get("missing_ocr_models"):
        log_warn(f"Missing OCR models: {', '.join(capabilities['missing_ocr_models'])}")
    if capabilities.get("missing_structure_models"):
        log_warn(f"Missing structure models: {', '.join(capabilities['missing_structure_models'])}")
    if missing_formula:
        log_warn(f"Missing optional formula models: {', '.join(missing_formula)}")


def clean_interrupted_paddle_state(base_dir: Path, model_names: list[str]):
    for path in (
        base_dir / ".paddlex" / "temp",
        base_dir / ".paddlex" / "locks",
        base_dir / ".cache" / "hf",
        base_dir / ".cache" / "modelscope",
    ):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    official_models_dir = base_dir / ".paddlex" / "official_models"
    for model_name in model_names:
        model_dir = official_models_dir / model_name
        if model_dir.exists() and not is_valid_model_dir(model_dir):
            shutil.rmtree(model_dir, ignore_errors=True)


def build_ocr_download_script(device: str) -> str:
    return f"""
from paddleocr import PaddleOCR

engine = PaddleOCR(
    lang="ch",
    device="{device}",
    use_doc_orientation_classify=False,
    use_textline_orientation=False,
    use_doc_unwarping=False,
    text_detection_model_name="PP-OCRv4_server_det",
    text_recognition_model_name="PP-OCRv4_server_rec",
)

print("PaddleOCR init ok")
"""


def build_structure_download_script(device: str) -> str:
    return f"""
from paddleocr import PPStructureV3

engine = PPStructureV3(
    device="{device}",
    layout_detection_model_name="PP-DocLayout_plus-L",
    chart_recognition_model_name="PP-Chart2Table",
    text_detection_model_name="PP-OCRv5_server_det",
    text_recognition_model_name="PP-OCRv5_server_rec",
    table_classification_model_name="PP-LCNet_x1_0_table_cls",
    wired_table_structure_recognition_model_name="SLANeXt_wired",
    wireless_table_structure_recognition_model_name="SLANet_plus",
    wired_table_cells_detection_model_name="RT-DETR-L_wired_table_cell_det",
    wireless_table_cells_detection_model_name="RT-DETR-L_wireless_table_cell_det",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_table_recognition=True,
    use_formula_recognition=False,
    use_chart_recognition=False,
    use_seal_recognition=False,
    use_region_detection=False,
)

print("PPStructureV3 init ok")
"""


def build_formula_download_script(device: str) -> str:
    return f"""
from paddleocr import PPStructureV3

engine = PPStructureV3(
    device="{device}",
    layout_detection_model_name="PP-DocLayout_plus-L",
    chart_recognition_model_name="PP-Chart2Table",
    text_detection_model_name="PP-OCRv5_server_det",
    text_recognition_model_name="PP-OCRv5_server_rec",
    table_classification_model_name="PP-LCNet_x1_0_table_cls",
    wired_table_structure_recognition_model_name="SLANeXt_wired",
    wireless_table_structure_recognition_model_name="SLANet_plus",
    wired_table_cells_detection_model_name="RT-DETR-L_wired_table_cell_det",
    wireless_table_cells_detection_model_name="RT-DETR-L_wireless_table_cell_det",
    formula_recognition_model_name="PP-FormulaNet_plus-L",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_table_recognition=True,
    use_formula_recognition=True,
    use_chart_recognition=False,
    use_seal_recognition=False,
    use_region_detection=False,
)

print("PPStructureV3 formula init ok")
"""


def run_model_download(python_exe: Path, base_dir: Path, env: dict[str, str], script: str, title: str) -> bool:
    for source in PADDLE_MODEL_SOURCES:
        source_env = env.copy()
        source_env["PADDLE_PDX_MODEL_SOURCE"] = source
        log_info(f"{title}: trying model source {source}")
        result = subprocess.run(
            [str(python_exe), "-c", script],
            cwd=str(base_dir),
            env=source_env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            log_success(f"{title}: download complete")
            return True
        log_warn(f"{title}: source {source} failed, trying next source")
    return False


def prompt_for_model_download(capabilities: dict, missing_formula: list[str]) -> bool:
    missing_ocr = capabilities.get("missing_ocr_models") or []
    missing_structure = capabilities.get("missing_structure_models") or []
    if not sys.stdin.isatty():
        log_warn("Not running in an interactive terminal. Skipping Paddle model download.")
        return False

    print("")
    print("Missing Paddle models were detected:")
    if missing_ocr:
        print(f"  OCR models: {', '.join(missing_ocr)}")
    if missing_structure:
        print(f"  Structure models: {', '.join(missing_structure)}")
    if missing_formula:
        print(f"  Optional formula models: {', '.join(missing_formula)}")
    estimated_size = "about 170MB for OCR and about 0.9GB for structure"
    if missing_formula:
        estimated_size += ", plus about 225MB for formula"
    print(f"  Estimated download size: {estimated_size}")
    answer = input("Download missing Paddle models now? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def ensure_paddle_environment(base_dir: Path, args) -> Path:
    log_info("Checking Paddle standalone environment...")
    paddle_python = ensure_virtualenv(base_dir / ".paddle_env", ".paddle_env")
    env = build_workspace_env(base_dir, paddle_python)

    probe = probe_paddle_imports(paddle_python, env)
    missing_modules = probe.get("missing_modules") or []
    if missing_modules:
        install_paddle_dependencies(paddle_python, env, missing_modules, args)
        probe = probe_paddle_imports(paddle_python, env)
        missing_modules = probe.get("missing_modules") or []
        if missing_modules:
            raise RuntimeError(f".paddle_env is still missing dependencies: {', '.join(missing_modules)}")
    else:
        log_success(".paddle_env core dependencies are ready")

    if args.paddle_include_formula_models:
        ensure_formula_dependency(paddle_python, env)

    get_paddle_capabilities = import_paddle_runtime(base_dir)
    capabilities = get_paddle_capabilities(use_cache=False)
    missing_formula = get_missing_formula_models(base_dir, args.paddle_include_formula_models)
    log_paddle_capabilities(capabilities, missing_formula)

    missing_ocr = capabilities.get("missing_ocr_models") or []
    missing_structure = capabilities.get("missing_structure_models") or []
    if not missing_ocr and not missing_structure and not missing_formula:
        return paddle_python

    should_download = False
    if args.paddle_models == "download":
        should_download = True
    elif args.paddle_models == "ask":
        should_download = prompt_for_model_download(capabilities, missing_formula)

    if not should_download:
        if args.require_paddle and (missing_ocr or missing_structure or missing_formula):
            raise RuntimeError("Paddle models are not ready and --require-paddle is enabled")
        log_warn("Skipping Paddle model download. Structure recovery may be unavailable.")
        return paddle_python

    clean_interrupted_paddle_state(base_dir, missing_ocr + missing_structure + missing_formula)

    if missing_ocr:
        if not run_model_download(
            paddle_python,
            base_dir,
            env,
            build_ocr_download_script(args.paddle_device),
            "OCR models",
        ):
            if args.require_paddle:
                raise RuntimeError("Failed to download OCR models")
            log_warn("Failed to download OCR models")

    if missing_structure:
        if not run_model_download(
            paddle_python,
            base_dir,
            env,
            build_structure_download_script(args.paddle_device),
            "Structure models",
        ):
            if args.require_paddle:
                raise RuntimeError("Failed to download structure models")
            log_warn("Failed to download structure models")

    if missing_formula:
        ensure_formula_dependency(paddle_python, env)
        if not run_model_download(
            paddle_python,
            base_dir,
            env,
            build_formula_download_script(args.paddle_device),
            "Formula models",
        ):
            if args.require_paddle:
                raise RuntimeError("Failed to download formula models")
            log_warn("Failed to download optional formula models")

    capabilities = get_paddle_capabilities(use_cache=False)
    missing_formula = get_missing_formula_models(base_dir, args.paddle_include_formula_models)
    log_paddle_capabilities(capabilities, missing_formula)

    if args.require_paddle and not capabilities.get("ocr_available"):
        raise RuntimeError("Paddle OCR is still unavailable and --require-paddle is enabled")
    if args.require_paddle and not capabilities.get("structure_available"):
        raise RuntimeError("Paddle structure pipeline is still unavailable and --require-paddle is enabled")
    if args.require_paddle and missing_formula:
        raise RuntimeError("Formula models are still missing and --require-paddle is enabled")

    return paddle_python


def build_service_env(base_dir: Path, args, paddle_python: Path | None) -> dict[str, str]:
    env = build_workspace_env(base_dir, paddle_python)
    env["VITE_API_URL"] = f"http://127.0.0.1:{args.backend_port}/api"
    env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{args.backend_port}/api"
    env["VITE_DEFAULT_REMOVE_AD"] = "false" if args.disable_ad_removal else "true"
    return env


def parse_args():
    parser = argparse.ArgumentParser(description="One-click starter for the local Word/PDF conversion service")
    parser.add_argument("--backend-port", type=int, default=8000, help="Backend port, default 8000")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Frontend port, default 3000")
    parser.add_argument("--disable-ad-removal", action="store_true", help="Disable default ad-removal toggle in frontend")
    parser.add_argument(
        "--paddle-models",
        choices=["ask", "download", "skip"],
        default="ask",
        help="How to handle missing Paddle models at startup: ask/download/skip",
    )
    parser.add_argument(
        "--paddle-device",
        choices=["cpu", "gpu:0"],
        default="cpu",
        help="Device used while initializing or downloading Paddle models",
    )
    parser.add_argument(
        "--paddle-core-package",
        default=os.environ.get("PADDLE_CORE_PACKAGE", "paddlepaddle==3.2.0"),
        help="pip package to install when paddle itself is missing",
    )
    parser.add_argument(
        "--paddle-include-formula-models",
        action="store_true",
        help="Also install the optional PP-FormulaNet_plus-L model and OMML conversion dependencies",
    )
    parser.add_argument(
        "--require-paddle",
        action="store_true",
        help="Exit instead of continuing when Paddle dependencies or required models are not ready",
    )
    return parser.parse_args()


def main() -> int:
    configure_console_encoding()
    if os.name == "nt":
        os.system("color >nul")

    args = parse_args()
    base_dir = Path(__file__).resolve().parent.parent
    backend_dir = base_dir / "backend"
    frontend_dir = base_dir / "frontend"
    if not backend_dir.exists() or not frontend_dir.exists():
        raise RuntimeError("This script must run from the project root with backend/ and frontend/ present")

    processes = []
    exit_code = 0

    try:
        check_libreoffice()
        backend_python = setup_backend(backend_dir)
        setup_frontend(frontend_dir)
        paddle_python = ensure_paddle_environment(base_dir, args)
        env = build_service_env(base_dir, args, paddle_python)

        log_info(f"Starting backend on port {args.backend_port}")
        backend_cmd = [
            str(backend_python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.backend_port),
        ]
        processes.append(run_service(backend_cmd, backend_dir, env, "[Backend]", "36"))

        time.sleep(2)

        log_info(f"Starting frontend on port {args.frontend_port}")
        npm_executable = "npm.cmd" if os.name == "nt" else "npm"
        frontend_cmd = [npm_executable, "run", "dev", "--", "--port", str(args.frontend_port)]
        processes.append(run_service(frontend_cmd, frontend_dir, env, "[Frontend]", "35"))

        print("")
        print("=" * 48)
        log_success("All services started")
        print(f"Frontend: {colorize(f'http://localhost:{args.frontend_port}', '4')}")
        print(f"Backend:  {colorize(f'http://127.0.0.1:{args.backend_port}/api', '4')}")
        print("Press Ctrl+C to stop all services")
        print("=" * 48)
        print("")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("")
        log_info("Stopping services...")
    except Exception as exc:
        log_error(str(exc))
        exit_code = 1
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
