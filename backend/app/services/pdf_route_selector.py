import fitz
import os
import re
from typing import Tuple, Dict, Any
from ..core.logger import logger
from ..utils.pdf_processor import STRONG_KEYWORDS, contains_strong_keyword, contains_combinations

class PDFRouteSelector:
    @staticmethod
    def analyze_pdf(pdf_path: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Analyzes a PDF file to determine the best conversion route.
        Returns:
            converter (str): 'pdf2docx' or 'paddle'
            reason (str): The reason for the routing decision.
            stats (Dict): Detailed statistics collected during analysis.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            num_pages = doc.page_count
            if num_pages == 0:
                return "pdf2docx", "Empty PDF, defaulting to standard engine.", {}

            total_text_length = 0
            total_images = 0
            total_drawings = 0
            total_blocks = 0
            math_symbols_count = 0
            table_lines_score = 0

            # Mathematical symbols that might indicate complex layout/equations
            math_pattern = re.compile(r'[\u2200-\u22FF\u2A00-\u2AFF\u27E6-\u27EF\u2983-\u2998∑∫∈∉√∞≠≤≥≈∝∠△]')

            # Analyze a sample of pages (up to first 10 pages and last 2 pages for speed)
            pages_to_check = set(range(min(10, num_pages)))
            if num_pages > 10:
                pages_to_check.update(range(num_pages - 2, num_pages))

            for page_num in pages_to_check:
                page = doc[page_num]

                # 1. Text length and math symbols
                text = page.get_text()
                total_text_length += len(text)
                math_symbols_count += len(math_pattern.findall(text))

                # Fraction-like patterns (e.g., a/b with numbers or variables)
                fraction_pattern = re.compile(r'[a-zA-Z0-9]+/[a-zA-Z0-9]+')
                math_symbols_count += len(fraction_pattern.findall(text)) * 0.5 # Give lower weight to simple fractions

                # 2. Page blocks (density/complexity)
                blocks = page.get_text("blocks")
                total_blocks += len(blocks)

                # 3. Images
                images = page.get_images(full=True)
                total_images += len(images)

                # 4. Drawings / Table lines
                # Extract vector graphics (lines, rectangles) which often indicate tables or charts
                drawings = page.get_drawings()
                total_drawings += len(drawings)

                # Count horizontal/vertical lines specifically (strong indicator of tables)
                for path in drawings:
                    for item in path["items"]:
                        if item[0] == "l": # line
                            p1, p2 = item[1], item[2]
                            if abs(p1.x - p2.x) < 2 or abs(p1.y - p2.y) < 2:
                                table_lines_score += 1

            doc.close()

            pages_sampled = len(pages_to_check)
            avg_text_per_page = total_text_length / pages_sampled if pages_sampled else 0
            avg_blocks_per_page = total_blocks / pages_sampled if pages_sampled else 0
            avg_images_per_page = total_images / pages_sampled if pages_sampled else 0
            avg_math_symbols_per_page = math_symbols_count / pages_sampled if pages_sampled else 0
            avg_table_lines_per_page = table_lines_score / pages_sampled if pages_sampled else 0

            stats = {
                "pages_sampled": pages_sampled,
                "avg_text_per_page": avg_text_per_page,
                "avg_blocks_per_page": avg_blocks_per_page,
                "avg_images_per_page": avg_images_per_page,
                "avg_math_symbols_per_page": avg_math_symbols_per_page,
                "avg_table_lines_per_page": avg_table_lines_per_page
            }

            logger.info(f"PDF Analysis stats for {pdf_path}: {stats}")

            # Routing Logic (Heuristics)
            reasons = []

            # Condition 1: Dense Math / Education material
            if avg_math_symbols_per_page > 5:
                reasons.append(f"High density of mathematical symbols ({avg_math_symbols_per_page:.1f}/page)")

            # Condition 2: Complex Tables
            if avg_table_lines_per_page > 30:
                reasons.append(f"High density of table lines/vectors ({avg_table_lines_per_page:.1f}/page)")

            # Condition 3: Highly fragmented layout (many small blocks)
            if avg_blocks_per_page > 40 and avg_text_per_page < 1500:
                reasons.append(f"Highly fragmented layout ({avg_blocks_per_page:.1f} blocks/page)")

            # Condition 4: Image-heavy (often scanned or complex layout)
            if avg_images_per_page > 3 and avg_text_per_page < 500:
                reasons.append(f"Image-heavy with low text ({avg_images_per_page:.1f} imgs/page)")

            # Condition 5: Educational / Mixed content (high images + reasonable text = formulas rendered as images)
            if avg_images_per_page > 10 and avg_text_per_page < 1500:
                reasons.append(f"Mixed content/Educational ({avg_images_per_page:.1f} imgs, {avg_text_per_page:.0f} chars/page)")

            if len(reasons) > 0:
                reason_str = " | ".join(reasons)
                return "paddle", f"Complex layout detected: {reason_str}", stats
            else:
                return "pdf2docx", "Standard text-based PDF layout detected.", stats

        except Exception as e:
            logger.error(f"Error during PDF pre-analysis for {pdf_path}: {e}", exc_info=True)
            # Default to standard if analysis fails
            return "pdf2docx", f"Analysis failed, defaulting to standard engine: {str(e)}", {}
