from __future__ import annotations

from dataclasses import dataclass, field

from ..core.exceptions import ConversionError
from ..models.schemas import ConverterMode
from ..utils.word_document_analyzer import analyze_word_document
from .word_com import get_word_com_availability


@dataclass(slots=True)
class WordToPdfRouteDecision:
    primary_engine: str
    route_reason: str
    fallback_engine: str | None = None
    formula_risk: bool = False
    formula_risk_reasons: list[str] = field(default_factory=list)


def select_word_to_pdf_engine(
    input_path: str,
    converter_mode: ConverterMode,
) -> WordToPdfRouteDecision:
    word_available, word_reason = get_word_com_availability()

    if converter_mode == ConverterMode.WORD:
        if not word_available:
            raise ConversionError(
                word_reason or "Microsoft Word COM export is unavailable."
            )
        return WordToPdfRouteDecision(
            primary_engine=ConverterMode.WORD.value,
            route_reason="User selected Microsoft Word export engine.",
        )

    if converter_mode == ConverterMode.LIBREOFFICE:
        return WordToPdfRouteDecision(
            primary_engine=ConverterMode.LIBREOFFICE.value,
            route_reason="User selected LibreOffice export engine.",
        )

    report = analyze_word_document(input_path)
    formula_reason = "; ".join(report.reasons)

    if report.has_formula_risk:
        if word_available:
            return WordToPdfRouteDecision(
                primary_engine=ConverterMode.WORD.value,
                route_reason=(
                    f"Detected formula risk ({formula_reason}); "
                    "preferred Microsoft Word export."
                ),
                fallback_engine=ConverterMode.LIBREOFFICE.value,
                formula_risk=True,
                formula_risk_reasons=report.reasons,
            )

        return WordToPdfRouteDecision(
            primary_engine=ConverterMode.LIBREOFFICE.value,
            route_reason=(
                f"Detected formula risk ({formula_reason}) but Microsoft Word export "
                f"is unavailable: {word_reason}"
            ),
            formula_risk=True,
            formula_risk_reasons=report.reasons,
        )

    fallback_engine = ConverterMode.WORD.value if word_available else None
    reason = "No formula risk detected; using LibreOffice export."
    if report.analysis_error:
        reason = f"{reason} Analysis note: {report.analysis_error}"

    return WordToPdfRouteDecision(
        primary_engine=ConverterMode.LIBREOFFICE.value,
        route_reason=reason,
        fallback_engine=fallback_engine,
        formula_risk=False,
        formula_risk_reasons=report.reasons,
    )
