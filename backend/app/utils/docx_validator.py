import xml.etree.ElementTree as ET
from docx import Document
from ..core.logger import logger

def validate_docx_quality(filepath: str) -> bool:
    """
    Validates the quality of a DOCX file generated from PDF.
    Returns False if the file exhibits high-risk structural patterns
    (e.g., relying heavily on behindDoc anchors, textboxes, and shapes
    without standard paragraph text) which would make it appear blank in MS Word.
    """
    try:
        doc = Document(filepath)
    except Exception as e:
        logger.error(f"Error reading docx for validation: {e}")
        return False

    paragraphs = list(doc.paragraphs)

    # Extract standard text content
    text_content = [p.text for p in paragraphs if p.text.strip()]

    drawing_count = 0
    shape_count = 0
    textbox_count = 0
    behind_doc_count = 0

    for p in paragraphs:
        p_xml = p._element.xml
        drawing_count += p_xml.count('<w:drawing>')
        shape_count += p_xml.count('<v:shape')
        textbox_count += p_xml.count('<v:textbox') + p_xml.count('<w:txbxContent')
        behind_doc_count += p_xml.count('behindDoc="1"')

    logger.info(
        f"DOCX Validation: {len(text_content)} standard paragraphs, "
        f"{drawing_count} drawings, {shape_count} shapes, "
        f"{textbox_count} textboxes, {behind_doc_count} behindDoc."
    )

    # If there are virtually no standard text paragraphs, but a large number of
    # absolute positioned shapes or textboxes (specifically behindDoc which obscures text),
    # this is a pseudo-success (visually blank in Word).
    # Heuristics:
    if len(text_content) < 5 and (drawing_count > 10 or shape_count > 10 or textbox_count > 10):
        logger.warning(f"DOCX Quality Validation FAILED: Detected high-risk pseudo-success structure.")
        return False

    return True
