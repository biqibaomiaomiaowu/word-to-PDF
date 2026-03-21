import argparse
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
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


def normalize_preview_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def collapse_obvious_repetition(text: str) -> str:
    compact = normalize_preview_text(text)
    if not compact:
        return ""

    max_unit = len(compact) // 2
    for unit_len in range(1, max_unit + 1):
        if len(compact) % unit_len != 0:
            continue
        unit = compact[:unit_len]
        repeat_count = len(compact) // unit_len
        if repeat_count >= 2 and unit * repeat_count == compact:
            return unit.strip()
    return compact


def extract_docx_paragraphs(docx_path: Path) -> list[str]:
    with ZipFile(docx_path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespaces):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespaces))
        text = normalize_preview_text(text)
        if text:
            paragraphs.append(text)
    return paragraphs


def collect_duplicate_paragraph_examples(paragraphs: list[str], limit: int = 10) -> list[dict]:
    duplicates: list[dict] = []
    previous = ""
    for index, text in enumerate(paragraphs):
        collapsed = collapse_obvious_repetition(text)
        if collapsed and collapsed != text:
            duplicates.append(
                {
                    "index": index,
                    "kind": "self_repeated",
                    "text": text[:180],
                    "collapsed": collapsed[:180],
                }
            )
        elif previous and text == previous:
            duplicates.append(
                {
                    "index": index,
                    "kind": "adjacent_duplicate",
                    "text": text[:180],
                }
            )
        previous = text
        if len(duplicates) >= limit:
            break
    return duplicates


def inspect_docx(docx_path: Path) -> dict:
    with ZipFile(docx_path) as archive:
        names = archive.namelist()
        media = [name for name in names if name.startswith("word/media/")]
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    paragraphs = extract_docx_paragraphs(docx_path)
    duplicate_examples = collect_duplicate_paragraph_examples(paragraphs)

    return {
        "docx_path": str(docx_path),
        "docx_size_bytes": docx_path.stat().st_size,
        "media_files": len(media),
        "xml_tables": xml.count("<w:tbl"),
        "xml_drawings": xml.count("<w:drawing"),
        "xml_omath": xml.count("<m:oMath"),
        "xml_omath_para": xml.count("<m:oMathPara"),
        "paragraph_count": len(paragraphs),
        "paragraph_preview": paragraphs[:12],
        "obvious_duplicate_paragraphs": len(duplicate_examples),
        "duplicate_examples": duplicate_examples,
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

    def run_once(device: str, disable_formula: bool = False):
        command = [
            str(paddle_python),
            str(runner),
            "--device",
            device,
            "--input",
            str(input_pdf),
            "--output_dir",
            str(output_dir),
        ]
        if disable_formula:
            command.append("--disable-formula")
        print(f"[Info] repo_root={repo_root}")
        print(f"[Info] input_pdf={input_pdf}")
        print(f"[Info] output_dir={output_dir}")
        print(f"[Info] command={' '.join(command)}")
        return subprocess.run(
            command,
            cwd=str(repo_root),
            env=build_runner_env(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=7200,
        )

    crash_return_codes = {3221225477, -1073741819}
    attempts: list[tuple[str, bool]] = [(args.device, False)]
    if args.device == "gpu:0":
        attempts.extend([("cpu", False), ("cpu", True)])
    else:
        attempts.append((args.device, True))

    result = None
    final_device = args.device
    final_disable_formula = False
    attempt_log: list[dict] = []
    for index, (device, disable_formula) in enumerate(attempts):
        result = run_once(device, disable_formula=disable_formula)
        attempt_log.append(
            {
                "device": device,
                "disable_formula": disable_formula,
                "returncode": result.returncode,
            }
        )
        final_device = device
        final_disable_formula = disable_formula
        if result.returncode not in crash_return_codes:
            break
        if index < len(attempts) - 1:
            print(
                f"[Warning] Native crash detected ({result.returncode}). "
                f"Retrying with device={attempts[index + 1][0]} disable_formula={attempts[index + 1][1]}."
            )

    assert result is not None
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
        "final_device": final_device,
        "final_disable_formula": final_disable_formula,
        "attempts": attempt_log,
        "parsed_result": parsed_result,
        "docx_files": [str(path) for path in docx_files],
        "stats": stats,
    }
    print("[Summary]")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
