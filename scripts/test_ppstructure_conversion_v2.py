from pathlib import Path as _Path
import runpy as _runpy

if __name__ == "__main__":
    _runpy.run_path(str(_Path(__file__).with_name("test_ppstructure_conversion_v3.py")), run_name="__main__")
    raise SystemExit(0)

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_paddle_python(repo_root: Path) -> Path:
    if sys.platform.startswith("win"):
        return repo_root / ".paddle_env" / "Scripts" / "python.exe"
    return repo_root / ".paddle_env" / "bin" / "python"


def build_runner_env(repo_root: Path) -> dict[str, str]:
    home_dir = repo_root / ".cache" / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        (home_dir / "AppData" / "Roaming").mkdir(parents=True, exist_ok=True)
        (home_dir / "AppData" / "Local").mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PADDLE_HOME"] = str(repo_root / ".paddle_models")
    env["PADDLE_PDX_CACHE_HOME"] = str(repo_root / ".paddlex")
    env["PADDLE_INFERENCE_MODEL_DIR"] = str(repo_root / ".paddle_inference")
    env["USERPROFILE"] = str(home_dir)
    env["HOME"] = str(home_dir)
    if os.name == "nt":
        env["APPDATA"] = str(home_dir / "AppData" / "Roaming")
        env["LOCALAPPDATA"] = str(home_dir / "AppData" / "Local")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    return env


def find_default_pdf(repo_root: Path) -> Path | None:
    for pattern in ("专题10.3*.pdf", "*10.3*.pdf", "*.pdf"):
        matches = sorted(repo_root.glob(pattern))
        if matches:
            return matches[0]
    return None


def inspect_docx(docx_path: Path) -> dict:
    with ZipFile(docx_path) as archive:
        names = archive.namelist()
        media = [name for name in names if name.startswith("word/media/")]
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")

    return {
        "docx_path": str(docx_path),
        "docx_size_bytes": docx_path.stat().st_size,
        "media_files": len(media),
        "xml_tables": xml.count("<w:tbl"),
        "xml_drawings": xml.count("<w:drawing"),
        "xml_omath": xml.count("<m:oMath"),
        "xml_omath_para": xml.count("<m:oMathPara"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PPStructureV4 conversion and print DOCX structure stats.")
    parser.add_argument("--input", help="Input PDF path. Defaults to a sample PDF in repo root.")
    parser.add_argument("--device", choices=["auto", "cpu", "gpu:0"], default="auto", help="Execution device")
    parser.add_argument("--output-dir", default="tmp_structure_test", help="Output directory")
    args = parser.parse_args()

    repo_root = get_repo_root()
    paddle_python = get_paddle_python(repo_root)
    runner = repo_root / "backend" / "app" / "services" / "run_paddle_structure_v4.py"

    if not paddle_python.exists():
        print(json.dumps({"success": False, "error": f"Missing Paddle python: {paddle_python}"}, ensure_ascii=False))
        return 1

    if not runner.exists():
        print(json.dumps({"success": False, "error": f"Missing runner script: {runner}"}, ensure_ascii=False))
        return 1

    input_pdf = Path(args.input).resolve() if args.input else find_default_pdf(repo_root)
    if input_pdf is None or not input_pdf.exists():
        print(json.dumps({"success": False, "error": "Input PDF not found."}, ensure_ascii=False))
        return 1

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(paddle_python),
        str(runner),
        "--device",
        args.device,
        "--input",
        str(input_pdf),
        "--output_dir",
        str(output_dir),
    ]

    print(f"[Info] repo_root={repo_root}")
    print(f"[Info] input_pdf={input_pdf}")
    print(f"[Info] output_dir={output_dir}")
    print(f"[Info] command={' '.join(command)}")

    result = subprocess.run(
        command,
        cwd=str(repo_root),
        env=build_runner_env(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=7200,
    )

    stdout_text = decode_output(result.stdout).strip()
    stderr_text = decode_output(result.stderr).strip()

    print("[RunnerStdout]")
    print(stdout_text or "<empty>")
    if stderr_text:
        print("[RunnerStderr]")
        print(stderr_text)

    parsed_result = None
    json_start = stdout_text.rfind("{")
    json_end = stdout_text.rfind("}")
    if json_start != -1 and json_end != -1 and json_end > json_start:
        try:
            parsed_result = json.loads(stdout_text[json_start : json_end + 1])
        except json.JSONDecodeError:
            parsed_result = None

    docx_files = sorted(output_dir.glob("*.docx"))
    stats = inspect_docx(docx_files[0]) if docx_files else None

    payload = {
        "success": result.returncode == 0 and bool(docx_files),
        "returncode": result.returncode,
        "parsed_result": parsed_result,
        "docx_files": [str(path) for path in docx_files],
        "stats": stats,
    }
    print("[Summary]")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
