import os
import shutil
from pathlib import Path
from docx import Document
from ..core.logger import logger

def _is_image_only_paragraph(paragraph) -> bool:
    """
    Check if a paragraph contains mainly an image (drawing or inline shape)
    and very little or no actual text.
    """
    # Exclude paragraphs with substantial text
    text = paragraph.text.strip()
    if len(text) > 20: # arbitrary small threshold for occasional random characters
        return False

    # Check underlying XML for drawing elements
    p_xml = paragraph._element

    # Namespaces
    nsmap = p_xml.nsmap

    # w:drawing, w:inline, a:blip
    drawings = p_xml.xpath('.//w:drawing')
    inlines = p_xml.xpath('.//w:inline')
    blips = p_xml.xpath('.//a:blip')

    if drawings or inlines or blips:
        return True

    # Also check w:pict for older word formats embedded in docx
    picts = p_xml.xpath('.//w:pict')
    if picts:
        return True

    return False

def _delete_paragraph(paragraph):
    """
    Delete a paragraph element entirely from the document XML tree.
    """
    p = paragraph._element
    p.getparent().remove(p)
    # Clear the reference to the paragraph's element to prevent use-after-free issues
    paragraph._p = paragraph._element = None

def clean_trailing_ad_from_docx(input_path: Path, output_path: Path) -> bool:
    """
    Stage 1: Clean trailing ad image paragraph from DOCX.
    Returns True if an ad was detected and removed, False otherwise.
    """
    try:
        # docx needs string paths
        doc = Document(str(input_path))

        # Look for the last non-empty paragraph (or a sequence of trailing empty paragraphs)
        paragraphs = doc.paragraphs
        if not paragraphs:
            return False

        # 1. Look for trailing image paragraphs (can be more than one at the end)
        trailing_ad_indices = []
        for i in range(len(paragraphs) - 1, -1, -1):
            p = paragraphs[i]
            text = p.text.strip()
            if not text and not _is_image_only_paragraph(p):
                trailing_ad_indices.append(i) # Empty paragraph, queue for deletion
                continue
            elif _is_image_only_paragraph(p):
                trailing_ad_indices.append(i) # Image paragraph, queue for deletion
            elif text:
                break # Reached actual text content

        if not trailing_ad_indices:
            return False

        last_non_empty_idx = min(trailing_ad_indices) - 1 if trailing_ad_indices else -1

        # Determine if we actually found any images to delete (not just empty lines)
        found_image = any(_is_image_only_paragraph(paragraphs[idx]) for idx in trailing_ad_indices)
        if not found_image:
            return False

        # 3. Check context (optional but good for safety):
        has_preceding_text = False
        if last_non_empty_idx >= 0:
            for i in range(max(0, last_non_empty_idx - 5), last_non_empty_idx + 1):
                if len(paragraphs[i].text.strip()) > 5:
                    has_preceding_text = True
                    break

        if not has_preceding_text and last_non_empty_idx > 0:
            logger.info(f"DOCX pre-cleaner: Found image at end, but no preceding text in the last 5 paragraphs. Skipping deletion for safety. {input_path}")
            return False

        # 4. Delete the trailing image paragraph and all trailing empty paragraphs
        for idx in trailing_ad_indices:
            _delete_paragraph(paragraphs[idx])

        # Optional: delete any trailing completely empty paragraphs that might precede it
        while last_non_empty_idx > 0:
            last_non_empty_idx -= 1
            p = paragraphs[last_non_empty_idx]
            if not p.text.strip() and not _is_image_only_paragraph(p):
                _delete_paragraph(p)
            else:
                break

        # Save modified document
        doc.save(str(output_path))
        logger.info(f"DOCX ad cleaner: Successfully removed trailing ad image from {input_path}")
        return True

    except Exception as e:
        logger.error(f"Error in DOCX pre-cleaner for {input_path}: {e}")
        # Return False to indicate we didn't clean it, so fallback or main process can continue
        return False
