import pytest
from datetime import datetime, timezone

from app.models.schemas import ConversionType, ConverterMode, TaskInfo, TaskStatus
from app.services.docx_formula_normalizer import DocxFormulaNormalizationReport
from app.services.task_manager import TaskManager
from app.services.word_to_pdf_router import WordToPdfRouteDecision


@pytest.mark.asyncio
async def test_word_to_pdf_fallback_uses_original_input_after_word_normalization(monkeypatch, tmp_path):
    manager = TaskManager()
    source_docx = tmp_path / "source.docx"
    source_docx.write_text("dummy", encoding="utf-8")
    normalized_docx = tmp_path / "normalized.docx"
    normalized_docx.write_text("normalized", encoding="utf-8")
    output_dir = tmp_path / "task-output"
    output_dir.mkdir()
    fallback_pdf = tmp_path / "fallback.pdf"

    task = TaskInfo(
        task_id="task-1",
        conversion_type=ConversionType.WORD_TO_PDF,
        original_filename="source.docx",
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        input_filepath=str(source_docx),
        output_dir=str(output_dir),
        remove_ad=False,
        converter_mode=ConverterMode.AUTO,
    )
    manager.tasks[task.task_id] = task

    monkeypatch.setattr(
        "app.services.task_manager.select_word_to_pdf_engine",
        lambda input_path, converter_mode: WordToPdfRouteDecision(
            primary_engine="word",
            fallback_engine="libreoffice",
            route_reason="formula risk",
            formula_risk=True,
            formula_risk_reasons=["detected formulas"],
        ),
    )
    monkeypatch.setattr(
        "app.services.task_manager.DocxFormulaNormalizer.flatten_axmath_to_images",
        lambda input_path, output_path: DocxFormulaNormalizationReport(
            output_path=str(normalized_docx),
            normalized=True,
            flattened_axmath_count=1,
        ),
    )

    calls = {}

    async def fail_word(input_file, out_dir):
        calls["word_input"] = input_file
        raise Exception("word failed")

    async def succeed_libreoffice(input_file, out_dir):
        calls["libreoffice_input"] = input_file
        fallback_pdf.write_text("pdf", encoding="utf-8")
        return str(fallback_pdf)

    monkeypatch.setattr("app.services.task_manager.WordComService.convert_to_pdf", fail_word)
    monkeypatch.setattr("app.services.task_manager.LibreOfficeService.convert_to_pdf", succeed_libreoffice)
    monkeypatch.setattr("app.services.task_manager.detect_and_remove_ad", lambda _: False)

    await manager._process_task(task.task_id)

    assert calls["word_input"] == str(normalized_docx)
    assert calls["libreoffice_input"] == str(source_docx)
    assert task.status == TaskStatus.COMPLETED
    assert task.converter_used == "libreoffice"
