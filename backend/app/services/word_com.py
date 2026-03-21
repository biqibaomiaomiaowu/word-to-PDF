from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import sys
import time
from locale import getpreferredencoding

from ..core.exceptions import ConversionError
from ..core.logger import logger
from ..core.config import settings


WORD_EXPORT_FORMAT_PDF = 17
WORD_EXPORT_OPTIMIZE_FOR_PRINT = 0
WORD_EXPORT_RANGE_ALL = 0
WORD_EXPORT_ITEM_DOCUMENT_CONTENT = 0
WORD_EXPORT_CREATE_NO_BOOKMARKS = 0
WORD_DO_NOT_SAVE_CHANGES = 0
WORD_DISPLAY_ALERTS_NONE = 0
WORD_AUTOMATION_SECURITY_FORCE_DISABLE = 3


def _import_word_dependencies():
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise ConversionError(f"pywin32 is not installed: {exc}") from exc
    return pythoncom, win32com.client


def _powershell_executable() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _escape_powershell_string(value: str) -> str:
    return value.replace("'", "''")


def _decode_powershell_output(payload: bytes) -> str:
    if not payload:
        return ""

    for encoding in ("utf-8", getpreferredencoding(False), "utf-16-le"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    return payload.decode("utf-8", errors="replace")


def _run_powershell_script(script: str, timeout_seconds: int) -> subprocess.CompletedProcess[bytes]:
    executable = _powershell_executable()
    if not executable:
        raise ConversionError("PowerShell is unavailable; cannot use Word COM fallback.")

    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        return subprocess.run(
            [
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded_script,
            ],
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConversionError("Microsoft Word PowerShell conversion process timed out.") from exc


def _probe_word_com_via_powershell() -> tuple[bool, str | None]:
    script = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    Write-Output 'WORD_COM_OK'
    exit 0
}
catch {
    Write-Output ('WORD_COM_FAIL:' + $_.Exception.Message)
    exit 1
}
finally {
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
    }
}
"""
    result = _run_powershell_script(script, timeout_seconds=15)
    stdout_text = _decode_powershell_output(result.stdout)
    if result.returncode == 0 or 'WORD_COM_OK' in stdout_text:
        return True, None

    stdout_text = _decode_powershell_output(result.stdout).strip()
    stderr_text = _decode_powershell_output(result.stderr).strip()
    message = stderr_text or stdout_text
    if not message:
        message = "unknown PowerShell COM probe failure"
    return False, f"PowerShell Word COM probe failed: {message}"


def _is_pywin32_available() -> bool:
    try:
        _import_word_dependencies()
        return True
    except ConversionError:
        return False


def get_word_com_availability() -> tuple[bool, str | None]:
    if not sys.platform.startswith("win"):
        return False, "Microsoft Word COM export is only available on Windows."

    try:
        pythoncom, win32com_client = _import_word_dependencies()
    except ConversionError as exc:
        fallback_available, fallback_reason = _probe_word_com_via_powershell()
        if fallback_available:
            logger.info("Microsoft Word COM is available via PowerShell fallback.")
            return True, None
        return False, f"{exc} | {fallback_reason}"

    app = None
    pythoncom.CoInitialize()
    try:
        app = win32com_client.DispatchEx("Word.Application")
        app.DisplayAlerts = WORD_DISPLAY_ALERTS_NONE
        app.Visible = False
        try:
            app.AutomationSecurity = WORD_AUTOMATION_SECURITY_FORCE_DISABLE
        except Exception:
            logger.debug("Failed to set Word automation security during availability probe.", exc_info=True)
        return True, None
    except Exception as exc:
        pywin32_reason = f"Microsoft Word COM is unavailable: {exc}"
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                logger.debug("Failed to quit Word during availability probe.", exc_info=True)
        pythoncom.CoUninitialize()

    fallback_available, fallback_reason = _probe_word_com_via_powershell()
    if fallback_available:
        logger.info("Microsoft Word COM is available via PowerShell fallback.")
        return True, None

    return False, f"{pywin32_reason} | {fallback_reason}"


class WordComService:
    @staticmethod
    async def convert_to_pdf(input_path: str, output_dir: str) -> str:
        if not os.path.exists(input_path):
            raise ConversionError(f"Input file not found: {input_path}")

        os.makedirs(output_dir, exist_ok=True)
        abs_input_path = os.path.abspath(input_path)
        abs_output_dir = os.path.abspath(output_dir)
        name_without_ext = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(abs_output_dir, f"{name_without_ext}.pdf")

        if os.path.exists(output_path):
            os.remove(output_path)

        backend_name = "pywin32" if _is_pywin32_available() else "powershell"
        try:
            await asyncio.wait_for(
                asyncio.to_thread(WordComService._convert_sync, abs_input_path, output_path),
                timeout=settings.CONVERSION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            logger.error("Microsoft Word conversion timed out for file: %s", input_path)
            raise ConversionError("Microsoft Word conversion process timed out.") from exc

        if not os.path.exists(output_path):
            raise ConversionError("Microsoft Word failed to generate the PDF file.")

        logger.info("Microsoft Word conversion successful via %s: %s", backend_name, output_path)
        return output_path

    @staticmethod
    def _convert_sync(input_path: str, output_path: str) -> None:
        if not sys.platform.startswith("win"):
            raise ConversionError("Microsoft Word COM export is only available on Windows.")

        if not _is_pywin32_available():
            WordComService._convert_sync_via_powershell(input_path, output_path)
            return

        try:
            WordComService._convert_sync_via_pywin32(input_path, output_path)
        except ConversionError as exc:
            logger.warning(
                "pywin32 Word export failed for %s; retrying via PowerShell COM fallback: %s",
                input_path,
                exc,
            )
            WordComService._convert_sync_via_powershell(input_path, output_path)

    @staticmethod
    def _convert_sync_via_pywin32(input_path: str, output_path: str) -> None:
        pythoncom, win32com_client = _import_word_dependencies()

        app = None
        document = None
        pythoncom.CoInitialize()
        try:
            started = time.perf_counter()
            app = win32com_client.DispatchEx("Word.Application")
            app.DisplayAlerts = WORD_DISPLAY_ALERTS_NONE
            app.Visible = False
            try:
                app.AutomationSecurity = WORD_AUTOMATION_SECURITY_FORCE_DISABLE
            except Exception:
                logger.debug("Failed to set Word automation security.", exc_info=True)
            try:
                app.Options.UpdateLinksAtOpen = False
            except Exception:
                logger.debug("Failed to disable Word link updates at open.", exc_info=True)

            logger.info("Opening document with Microsoft Word: %s", input_path)
            open_started = time.perf_counter()
            document = app.Documents.Open(
                FileName=input_path,
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Revert=False,
                OpenAndRepair=False,
                NoEncodingDialog=True,
            )
            open_seconds = time.perf_counter() - open_started
            logger.info("Microsoft Word opened %s in %.2fs", input_path, open_seconds)

            export_started = time.perf_counter()
            document.ExportAsFixedFormat(
                OutputFileName=output_path,
                ExportFormat=WORD_EXPORT_FORMAT_PDF,
                OpenAfterExport=False,
                OptimizeFor=WORD_EXPORT_OPTIMIZE_FOR_PRINT,
                Range=WORD_EXPORT_RANGE_ALL,
                Item=WORD_EXPORT_ITEM_DOCUMENT_CONTENT,
                IncludeDocProps=True,
                KeepIRM=True,
                CreateBookmarks=WORD_EXPORT_CREATE_NO_BOOKMARKS,
                DocStructureTags=True,
                BitmapMissingFonts=False,
                UseISO19005_1=False,
            )
            export_seconds = time.perf_counter() - export_started
            total_seconds = time.perf_counter() - started
            logger.info(
                "Microsoft Word finished %s (open %.2fs, export %.2fs, total %.2fs)",
                output_path,
                open_seconds,
                export_seconds,
                total_seconds,
            )
        except ConversionError:
            raise
        except Exception as exc:
            logger.error("Microsoft Word conversion failed for %s: %s", input_path, exc, exc_info=True)
            raise ConversionError(f"Microsoft Word conversion failed: {exc}") from exc
        finally:
            if document is not None:
                try:
                    document.Close(SaveChanges=WORD_DO_NOT_SAVE_CHANGES)
                except Exception:
                    logger.debug("Failed to close Microsoft Word document cleanly.", exc_info=True)
            if app is not None:
                try:
                    app.Quit()
                except Exception:
                    logger.debug("Failed to quit Microsoft Word cleanly.", exc_info=True)
            pythoncom.CoUninitialize()

    @staticmethod
    def _convert_sync_via_powershell(input_path: str, output_path: str) -> None:
        escaped_input = _escape_powershell_string(input_path)
        escaped_output = _escape_powershell_string(output_path)
        script = f"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$inputPath = '{escaped_input}'
$outputPath = '{escaped_output}'
$word = $null
$document = $null
try {{
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {{ $word.AutomationSecurity = {WORD_AUTOMATION_SECURITY_FORCE_DISABLE} }} catch {{}}
    try {{ $word.Options.UpdateLinksAtOpen = $false }} catch {{}}
    $document = $word.Documents.Open($inputPath, $false, $true)
    $document.ExportAsFixedFormat($outputPath, {WORD_EXPORT_FORMAT_PDF})
    Write-Output 'EXPORT_OK'
    exit 0
}}
catch {{
    Write-Output ('EXPORT_FAIL:' + $_.Exception.ToString())
    exit 1
}}
finally {{
    if ($document -ne $null) {{
        try {{ $document.Close({WORD_DO_NOT_SAVE_CHANGES}) }} catch {{}}
    }}
    if ($word -ne $null) {{
        try {{ $word.Quit() }} catch {{}}
    }}
}}
"""
        result = _run_powershell_script(script, timeout_seconds=settings.CONVERSION_TIMEOUT_SECONDS)
        stdout_text = _decode_powershell_output(result.stdout)
        stderr_text = _decode_powershell_output(result.stderr)
        if result.returncode != 0 and 'EXPORT_OK' not in stdout_text:
            message = (stderr_text or stdout_text).strip()
            if not message:
                message = "unknown PowerShell export failure"
            raise ConversionError(f"Microsoft Word PowerShell conversion failed: {message}")
