from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import fitz

from app.models.schemas import ConverterMode
from app.services.docx_formula_normalizer import DocxFormulaNormalizer
from app.services.libreoffice import LibreOfficeService
from app.services.word_com import WordComService, get_word_com_availability
from app.services.word_to_pdf_router import select_word_to_pdf_engine


WEIRD_CHARS = {"¿", "\ufffd", "￿"}


def inspect_pdf(pdf_path: Path) -> dict:
    if not pdf_path.exists():
        return {"exists": False}

    doc = fitz.open(str(pdf_path))
    font_counter: Counter[str] = Counter()
    weird_pages: list[dict] = []
    weird_samples: list[dict] = []
    opensymbol_spans = 0

    for page_index in range(doc.page_count):
        page = doc[page_index]
        page_samples: list[dict] = []
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    font = span.get("font", "")
                    text = span.get("text", "")
                    font_counter[font] += max(1, len(text))
                    if font == "OpenSymbol":
                        opensymbol_spans += 1
                    if any(ch in text for ch in WEIRD_CHARS):
                        sample = {"font": font, "text": text}
                        if len(page_samples) < 5:
                            page_samples.append(sample)
                        if len(weird_samples) < 20:
                            weird_samples.append({"page": page_index + 1, **sample})
        if page_samples:
            weird_pages.append({"page": page_index + 1, "samples": page_samples})

    return {
        "exists": True,
        "page_count": doc.page_count,
        "weird_page_count": len(weird_pages),
        "weird_pages": weird_pages,
        "weird_samples": weird_samples,
        "opensymbol_spans": opensymbol_spans,
        "top_fonts": font_counter.most_common(12),
    }


async def convert_once(engine: str, input_path: Path, output_root: Path) -> dict:
    target_dir = output_root / engine
    target_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    try:
        if engine == "word":
            output_pdf = await WordComService.convert_to_pdf(str(input_path), str(target_dir))
            engine_used = "word"
        elif engine == "libreoffice":
            output_pdf = await LibreOfficeService.convert_to_pdf(str(input_path), str(target_dir))
            engine_used = "libreoffice"
        elif engine == "auto":
            decision = select_word_to_pdf_engine(str(input_path), ConverterMode.AUTO)
            if decision.primary_engine == "word":
                output_pdf = await WordComService.convert_to_pdf(str(input_path), str(target_dir))
            else:
                output_pdf = await LibreOfficeService.convert_to_pdf(str(input_path), str(target_dir))
            engine_used = decision.primary_engine
        else:
            raise ValueError(f"Unsupported engine: {engine}")
    except Exception as exc:
        return {
            "requested_engine": engine,
            "success": False,
            "duration_seconds": round(time.perf_counter() - started, 2),
            "error": str(exc),
        }

    pdf_path = Path(output_pdf)
    return {
        "requested_engine": engine,
        "engine_used": engine_used,
        "success": True,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "output_pdf": str(pdf_path),
        "pdf_inspection": inspect_pdf(pdf_path),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test Word->PDF formula export and inspect the output PDFs."
    )
    parser.add_argument("--input", required=True, help="Absolute path to the source .doc or .docx file.")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["auto", "libreoffice"],
        choices=["auto", "word", "libreoffice"],
        help="Engines to test. Default: auto libreoffice",
    )
    parser.add_argument(
        "--output-root",
        default=str(BACKEND_ROOT / "output_pdfs" / "formula_fix_smoke"),
        help="Directory used to store generated PDFs.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    prepared_input_path = input_path
    normalization_report = None

    if input_path.exists():
        prepared_dir = output_root / "_prepared"
        prepared_dir.mkdir(parents=True, exist_ok=True)
        normalization_report = DocxFormulaNormalizer.flatten_axmath_to_images(
            str(input_path),
            str(prepared_dir / input_path.name),
        )
        prepared_input_path = Path(normalization_report.output_path)

    word_available, word_reason = get_word_com_availability()
    auto_decision = None
    auto_decision_error = None
    try:
        auto_decision = select_word_to_pdf_engine(str(prepared_input_path), ConverterMode.AUTO)
    except Exception as exc:
        auto_decision_error = str(exc)

    report = {
        "input_path": str(input_path),
        "input_exists": input_path.exists(),
        "prepared_input_path": str(prepared_input_path),
        "formula_preprocessing": {
            "normalized": normalization_report.normalized if normalization_report else False,
            "flattened_axmath_count": normalization_report.flattened_axmath_count if normalization_report else 0,
            "modified_parts": normalization_report.modified_parts if normalization_report else [],
            "dropped_embed_parts": normalization_report.dropped_embed_parts if normalization_report else [],
        },
        "word_com_available": word_available,
        "word_com_reason_if_unavailable": word_reason,
        "auto_decision": (
            {
                "primary_engine": auto_decision.primary_engine,
                "fallback_engine": auto_decision.fallback_engine,
                "formula_risk": auto_decision.formula_risk,
                "formula_risk_reasons": auto_decision.formula_risk_reasons,
                "route_reason": auto_decision.route_reason,
            }
            if auto_decision is not None
            else None
        ),
        "auto_decision_error": auto_decision_error,
        "results": [],
    }

    if not input_path.exists():
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    for engine in args.engines:
        report["results"].append(await convert_once(engine, prepared_input_path, output_root))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
