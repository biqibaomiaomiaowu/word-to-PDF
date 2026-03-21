import pytest

from app.core.exceptions import ConversionError
from app.models.schemas import ConverterMode
from app.services.word_to_pdf_router import select_word_to_pdf_engine
from app.utils.word_document_analyzer import WordFormulaRiskReport


def test_select_word_to_pdf_engine_prefers_word_for_formula_docs(monkeypatch):
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.get_word_com_availability",
        lambda: (True, None),
    )
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.analyze_word_document",
        lambda _: WordFormulaRiskReport(
            has_formula_risk=True,
            reasons=["detected 2 OMML formulas"],
        ),
    )

    decision = select_word_to_pdf_engine("dummy.docx", ConverterMode.AUTO)

    assert decision.primary_engine == "word"
    assert decision.fallback_engine == "libreoffice"
    assert decision.formula_risk is True


def test_select_word_to_pdf_engine_uses_libreoffice_when_word_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.get_word_com_availability",
        lambda: (False, "missing pywin32"),
    )
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.analyze_word_document",
        lambda _: WordFormulaRiskReport(
            has_formula_risk=True,
            reasons=["detected 1 AxMath objects"],
        ),
    )

    decision = select_word_to_pdf_engine("dummy.docx", ConverterMode.AUTO)

    assert decision.primary_engine == "libreoffice"
    assert decision.fallback_engine is None
    assert "missing pywin32" in decision.route_reason


def test_select_word_to_pdf_engine_defaults_to_libreoffice_for_plain_doc(monkeypatch):
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.get_word_com_availability",
        lambda: (True, None),
    )
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.analyze_word_document",
        lambda _: WordFormulaRiskReport(
            has_formula_risk=False,
            reasons=[],
        ),
    )

    decision = select_word_to_pdf_engine("dummy.docx", ConverterMode.AUTO)

    assert decision.primary_engine == "libreoffice"
    assert decision.fallback_engine == "word"


def test_select_word_to_pdf_engine_rejects_explicit_word_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.word_to_pdf_router.get_word_com_availability",
        lambda: (False, "word not installed"),
    )

    with pytest.raises(ConversionError):
        select_word_to_pdf_engine("dummy.docx", ConverterMode.WORD)
