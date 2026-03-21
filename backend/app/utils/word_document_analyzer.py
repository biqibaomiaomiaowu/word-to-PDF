from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from zipfile import BadZipFile, ZipFile


OMML_PATTERN = re.compile(r"<m:oMath(?=[\s>])")
AXMATH_PATTERN = re.compile(r'ProgID="Equation\.AxMath"')
CAMBRIA_MATH_PATTERN = re.compile(r"Cambria Math")


@dataclass(slots=True)
class WordFormulaRiskReport:
    has_formula_risk: bool
    reasons: list[str] = field(default_factory=list)
    stats: dict[str, int | bool | str] = field(default_factory=dict)
    analysis_error: str | None = None


def _read_optional_xml(archive: ZipFile, name: str) -> str:
    try:
        return archive.read(name).decode("utf-8", errors="replace")
    except KeyError:
        return ""


def _iter_word_xml_parts(archive: ZipFile) -> list[str]:
    return [
        name
        for name in archive.namelist()
        if name.startswith("word/")
        and name.endswith(".xml")
        and "/_rels/" not in name
    ]


def analyze_word_document(filepath: str) -> WordFormulaRiskReport:
    ext = os.path.splitext(filepath)[1].lower()
    stats: dict[str, int | bool | str] = {"extension": ext}

    if ext == ".doc":
        return WordFormulaRiskReport(
            has_formula_risk=True,
            reasons=["detected legacy .doc input"],
            stats=stats,
        )

    if ext != ".docx":
        return WordFormulaRiskReport(
            has_formula_risk=False,
            reasons=[],
            stats=stats,
            analysis_error=f"unsupported extension: {ext}",
        )

    try:
        with ZipFile(filepath) as archive:
            part_names = _iter_word_xml_parts(archive)
            part_payloads = [
                _read_optional_xml(archive, name)
                for name in part_names
            ]
    except (OSError, BadZipFile) as exc:
        return WordFormulaRiskReport(
            has_formula_risk=False,
            reasons=[],
            stats=stats,
            analysis_error=str(exc),
        )

    omml_count = 0
    axmath_count = 0
    uses_cambria_math = False
    for xml_payload in part_payloads:
        omml_count += len(OMML_PATTERN.findall(xml_payload))
        axmath_count += len(AXMATH_PATTERN.findall(xml_payload))
        if not uses_cambria_math and CAMBRIA_MATH_PATTERN.search(xml_payload):
            uses_cambria_math = True

    stats.update(
        {
            "parts_scanned": len(part_payloads),
            "omml_count": omml_count,
            "axmath_count": axmath_count,
            "uses_cambria_math": uses_cambria_math,
        }
    )

    reasons: list[str] = []
    if omml_count:
        reasons.append(f"detected {omml_count} OMML formulas")
    if axmath_count:
        reasons.append(f"detected {axmath_count} AxMath objects")
    if uses_cambria_math:
        reasons.append("detected Cambria Math font usage")

    return WordFormulaRiskReport(
        has_formula_risk=bool(reasons),
        reasons=reasons,
        stats=stats,
    )
