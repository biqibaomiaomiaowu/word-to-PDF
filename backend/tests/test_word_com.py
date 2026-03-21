from pathlib import Path
import subprocess

from app.core.exceptions import ConversionError
from app.services.word_com import WordComService, get_word_com_availability


def test_get_word_com_availability_uses_powershell_fallback(monkeypatch):
    monkeypatch.setattr("app.services.word_com.sys.platform", "win32")

    def raise_import_error():
        raise ConversionError("pywin32 is not installed")

    monkeypatch.setattr("app.services.word_com._import_word_dependencies", raise_import_error)
    monkeypatch.setattr(
        "app.services.word_com._probe_word_com_via_powershell",
        lambda: (True, None),
    )

    available, reason = get_word_com_availability()

    assert available is True
    assert reason is None


def test_get_word_com_availability_reports_combined_probe_failure(monkeypatch):
    monkeypatch.setattr("app.services.word_com.sys.platform", "win32")

    def raise_import_error():
        raise ConversionError("pywin32 is not installed")

    monkeypatch.setattr("app.services.word_com._import_word_dependencies", raise_import_error)
    monkeypatch.setattr(
        "app.services.word_com._probe_word_com_via_powershell",
        lambda: (False, "PowerShell Word COM probe failed: class not registered"),
    )

    available, reason = get_word_com_availability()

    assert available is False
    assert "pywin32 is not installed" in reason
    assert "class not registered" in reason



def test_convert_sync_retries_powershell_after_pywin32_failure(monkeypatch):
    monkeypatch.setattr("app.services.word_com.sys.platform", "win32")
    monkeypatch.setattr("app.services.word_com._is_pywin32_available", lambda: True)

    pywin32_calls = {"count": 0}
    powershell_calls = {"count": 0}

    def fail_pywin32(input_path, output_path):
        pywin32_calls["count"] += 1
        raise ConversionError("pywin32 export failed")

    def succeed_powershell(input_path, output_path):
        powershell_calls["count"] += 1

    monkeypatch.setattr("app.services.word_com.WordComService._convert_sync_via_pywin32", fail_pywin32)
    monkeypatch.setattr("app.services.word_com.WordComService._convert_sync_via_powershell", succeed_powershell)

    WordComService._convert_sync("input.docx", "output.pdf")

    assert pywin32_calls["count"] == 1
    assert powershell_calls["count"] == 1



def test_convert_sync_via_powershell_accepts_success_marker_even_if_returncode_is_nonzero(monkeypatch):
    monkeypatch.setattr(
        "app.services.word_com._run_powershell_script",
        lambda script, timeout_seconds: subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=1,
            stdout=b"EXPORT_OK\r\n",
            stderr=b"",
        ),
    )

    WordComService._convert_sync_via_powershell("input.docx", "output.pdf")



def test_convert_to_pdf_normalizes_output_dir_to_absolute_path(monkeypatch, tmp_path):
    input_path = tmp_path / "input.docx"
    input_path.write_text("dummy", encoding="utf-8")
    relative_output_dir = tmp_path / "nested" / "relative-out"

    seen = {}

    def fake_convert_sync(abs_input_path, output_path):
        seen["input"] = abs_input_path
        seen["output"] = output_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("pdf", encoding="utf-8")

    monkeypatch.setattr("app.services.word_com.WordComService._convert_sync", fake_convert_sync)

    import asyncio
    out = asyncio.run(WordComService.convert_to_pdf(str(input_path), str(relative_output_dir)))

    assert Path(out).is_absolute()
    assert Path(seen["output"]).is_absolute()
