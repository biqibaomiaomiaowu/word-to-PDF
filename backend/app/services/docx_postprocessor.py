import re
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
from ..core.logger import logger

def is_sentence_end(text: str) -> bool:
    if not text:
        return True
    end_chars = ('.', '。', '!', '！', '?', '？', ';', '；', ':', '：', '”', '"', "'", '’', '】', ']', ')')
    return text.strip().endswith(end_chars)

def is_heading_or_list(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    # Added robust patterns as requested
    patterns = [
        r'^\d+[\.\u3001]',                # 1. 2. 3. 1、 2、
        r'^\(\d+\)',                      # (1) (2)
        r'^[\u2460-\u2473]',              # ①-⑳
        r'^[A-D][\.\u3001\uff0e]',        # A. B. C. D. A．B．C．D．
        r'^(专题|知识点|题型|例|变式|解|分析)\s*\d*', # Headings like 专题, 知识点, 例1, 解
        r'^【.*?】',                       # 【考点】
        r'^如图所示',                        # 如图所示
        r'^解：',                         # 解：
        r'^故答案为',                       # 故答案为
        r'^所以',                         # 所以
        r'^\$\$.*?\$\$',                  # obvious isolated math block
        r'^\\\[.*?\\\]'                   # obvious isolated math block
    ]
    for p in patterns:
        if re.match(p, text):
            return True
    return False

def should_force_merge(t1: str, t2: str) -> bool:
    """Check for strong signals that two lines should be merged."""
    # Previous line ends with math operator or open bracket
    if re.search(r'([\+\-\*\/\=\(\[\{,，、]|1/)$', t1):
        return True
    # Previous line ends with incomplete fraction/interval and next starts with rest
    if re.search(r'\d+\s*/$', t1) and re.match(r'^\s*\d+', t2):
         return True
    # English word broken
    if re.search(r'[A-Za-z\-]$', t1) and re.match(r'^[A-Za-z\-]', t2):
         return True
    return False

def clean_repeated_chars(text: str) -> str:
    """Cleans obviously repeated characters/words like '概概率'"""
    # Fix repeated Chinese chars (2 or more identical Chinese chars)
    # Be careful: some are valid like "看看", "常常". We limit to a small blacklist of common errors.
    text = re.sub(r'(概率|频数|频率|长度|高度)\1+', r'\1', text)
    text = re.sub(r'概概率', '概率', text)
    text = re.sub(r'频频数', '频数', text)
    text = re.sub(r'高高度', '高度', text)
    text = re.sub(r'长长度', '长度', text)
    return text

def fix_chinese_english_spacing(text: str) -> str:
    # Character level cleaning first
    text = clean_repeated_chars(text)

    # Fix English word gluing commonly found in OCR/PDF parsing
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    safe_prefixes = ['You', 'I', 'We', 'They', 'He', 'She', 'It', 'The', 'A', 'An', 'In', 'On', 'At', 'To', 'For', 'With', 'By', 'About', 'From', 'Into']
    safe_suffixes = ['the', 'a', 'an', 'and', 'or', 'but', 'if', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'from', 'into', 'is', 'are', 'was', 'were', 'am', 'be', 'been', 'being', 'do', 'does', 'did', 'have', 'has', 'had']

    # We do NOT want to space out P(A) -> P (A) by doing prefix stuff on single letters aggressively
    for prefix in safe_prefixes:
        # Avoid matching 'P' if it's followed by '('
        if prefix != 'I' and prefix != 'A':
            text = re.sub(rf'\b({prefix})([a-z]+)\b', r'\1 \2', text)

    for suffix in safe_suffixes:
        if suffix not in ['a', 'an']:
            text = re.sub(rf'\b([a-zA-Z]+)({suffix})\b', r'\1 \2', text)

    # Add space between Chinese and English/Number (ignore spaces inside math)
    text = re.sub(r'([\u4e00-\u9fa5])([a-zA-Z0-9])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fa5])', r'\1 \2', text)

    # Fix percentages (e.g. 20 % -> 20%)
    text = re.sub(r'(\d+)\s*%', r'\1%', text)

    # Fix ratios (e.g. 1 : 2 -> 1:2)
    text = re.sub(r'(\d+)\s*[:∶]\s*(\d+)', r'\1:\2', text)

    # Fix decimals mixed with intervals (e.g. 0.5 ~ 0.8 -> 0.5~0.8)
    text = re.sub(r'(\d+\.\d+)\s*~\s*(\d+\.\d+)', r'\1~\2', text)

    # Fix inequality chains (e.g. a < b < c -> a<b<c)
    text = re.sub(r'([a-zA-Z0-9])\s*([<≤>≥])\s*([a-zA-Z0-9])', r'\1\2\3', text)
    text = re.sub(r'([a-zA-Z0-9])\s*([<≤>≥])\s*([a-zA-Z0-9])', r'\1\2\3', text)

    # Fix math probabilities (e.g., P (A) -> P(A))
    text = re.sub(r'([PCE])\s*\(\s*([A-Za-z0-9_\|\.\s]+)\s*\)', r'\1(\2)', text)

    # Clean spaces inside the probability parenthesis P( A|B ) -> P(A|B)
    text = re.sub(r'(P\()\s*(.*?)\s*(\))', r'\1\2\3', text)

    # Fix math intervals (e.g., [ 10 , 20 ) -> [10, 20))
    text = re.sub(r'(\[|\()\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*(\)|\])', r'\1\2, \3\4', text)

    # Fix infinite intervals (-∞, 1]
    text = re.sub(r'(\[|\()\s*(-?∞)\s*,\s*(-?\d+\.?\d*)\s*(\)|\])', r'\1\2, \3\4', text)
    text = re.sub(r'(\[|\()\s*(-?\d+\.?\d*)\s*,\s*(\+?∞)\s*(\)|\])', r'\1\2, \3\4', text)

    # Fix fractions (e.g., 1 / 6 -> 1/6)
    text = re.sub(r'(\d+)\s*/\s*(\d+)', r'\1/\2', text)

    # Fix option formatting (e.g. A. 1/2 B. 1/3)
    # Ensure space after dot
    text = re.sub(r'([A-D])\.', r'\1. ', text)

    # Fix English words broken by spaces (basic heuristic)
    text = re.sub(r'\b([A-Za-z])\s+([A-Za-z])\b', r'\1\2', text)
    text = re.sub(r'\b([A-Za-z])\s+([A-Za-z])\s+([A-Za-z])\b', r'\1\2\3', text)

    # Extract squashed numbers (e.g. 108610138 -> 10 8 6 10 13 8 or random array 412451312)
    # Only try to unsquash if it's very long and lacks spacing completely.
    if re.search(r'\b\d{8,}\b', text):
        # Specific heuristic for squashed numbers in the provided document:
        # 10861013... are 1-2 digit numbers
        # 412451312... are 3 digit chunks
        # Let's try splitting 3-digit chunks if it starts with 412 or similar (random array)
        if len(re.findall(r'\b\d{9,}\b', text)) > 0:
            for match in re.findall(r'\b\d{9,}\b', text):
                if len(match) % 3 == 0:
                    split_num = " ".join([match[i:i+3] for i in range(0, len(match), 3)])
                    text = text.replace(match, split_num)

    # Extra cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def apply_heading_styles(paragraph):
    text = paragraph.text.strip()
    if not text:
        return

    # Check for specific headings
    is_h1 = bool(re.match(r'^(专题\s*\d+|第.*?部分)', text))
    is_h2 = bool(re.match(r'^(【知识点.*?】|【题型.*?】|一、|二、|三、|四、|五、)', text))
    is_h3 = bool(re.match(r'^(【例.*?】|【变式.*?】|考点.*?)', text))
    is_bold_only = bool(re.match(r'^(解：|分析：|故答案为|所以)', text))

    if is_h1:
        paragraph.style = 'Heading 1'
        paragraph.paragraph_format.space_before = Pt(18)
        paragraph.paragraph_format.space_after = Pt(6)
    elif is_h2:
        paragraph.style = 'Heading 2'
        paragraph.paragraph_format.space_before = Pt(12)
        paragraph.paragraph_format.space_after = Pt(6)
    elif is_h3:
        paragraph.style = 'Heading 3'
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(6)
    elif is_bold_only:
        for run in paragraph.runs:
            run.font.bold = True

    # Note: the text might have existing runs with font properties set by pdf2docx.
    # We shouldn't strip them completely as it might contain math variables, but
    # applying the heading style to the paragraph level ensures structural mapping.

def split_glued_toc(text: str) -> list[str]:
    """
    Detects glued TOC lines (e.g. "Section 1...1 Section 2...2")
    and splits them into a list of strings.
    """
    # A typical glued TOC might have dots followed by digits and then more text
    # Let's split by pattern: ...<digits>
    parts = re.split(r'((?:\.{3,}|…+)\s*\d+)', text)
    toc_lines = []
    current_line = ""
    for part in parts:
        current_line += part
        if re.search(r'(?:\.{3,}|…+)\s*\d+$', part):
            toc_lines.append(current_line.strip())
            current_line = ""

    if current_line.strip():
        # Might not have a page number at the very end
        if toc_lines:
             toc_lines[-1] += " " + current_line.strip()
        else:
             toc_lines.append(current_line.strip())

    return toc_lines

def is_known_table_header(text: str) -> bool:
    """Check if the text matches known table headers in Chinese educational materials."""
    patterns = [
        r'高度.*?频数',
        r'长度.*?件数',
        r'字母.*?频数',
        r'游戏.*?取球方式.*?结果',
        r'名称.*?频数',
        r'区间.*?频数',
        r'项目.*?结果',
        r'项目.*?概率',
        r'编号.*?条件.*?结果',
        r'游戏.*?方式.*?结论',
        r'组别.*?数据.*?频率',
        r'高度/cm',
        r'长度\(cm\)',
        r'时间/min',
        r'频率/概率'
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False

def is_multi_column_data(text: str) -> bool:
    """Detect lines like A, B, C, D spaced options or plain multi-columns"""
    if re.search(r'\s{2,}|\t+', text) and len(text) > 2:
         return True
    return False

def convert_to_table(doc, paras_to_convert: list):
    """
    Converts a list of consecutive paragraphs that look like tabular data into a Word table.
    """
    if not paras_to_convert:
        return

    # Heuristic: split each paragraph by large spaces or tabs, or dash for known headers
    table_data = []
    max_cols = 0

    first_row_text = paras_to_convert[0].text.strip()
    is_special = is_known_table_header(first_row_text)

    for p in paras_to_convert:
        text = p.text.strip()
        # For known headers like "高度/cm—频数", we might need to split by EM dash or EN dash as well if space is missing
        # We also need to be careful not to split negative numbers or intervals if we just split by "-" indiscriminately.
        if is_special and ('—' in text or '-' in text) and not re.search(r'\d-\d', text):
             cols = re.split(r'\s{2,}|\t+|—|-', text)
        else:
             # Split by tab or multiple spaces, or even wide ideographic spaces
             cols = re.split(r'\s{2,}|\t+|\u3000+', text)

        cols = [c.strip() for c in cols if c.strip()]
        if cols:
             table_data.append(cols)
             max_cols = max(max_cols, len(cols))

    if max_cols < 2 or not table_data:
        return # Not a table

    # Insert table before the first paragraph
    p_element = paras_to_convert[0]._element
    table = doc.add_table(rows=len(table_data), cols=max_cols)
    table.style = 'Table Grid'

    # Move the new table XML immediately before the first paragraph
    p_element.getparent().insert(p_element.getparent().index(p_element), table._element)

    for r_idx, row_data in enumerate(table_data):
        for c_idx, cell_text in enumerate(row_data):
            if c_idx < len(table.columns):
                table.cell(r_idx, c_idx).text = cell_text

    # Delete original paragraphs
    for p in paras_to_convert:
        p_element = p._element
        p_element.getparent().remove(p_element)

def postprocess_docx(filepath: str) -> bool:
    """
    Applies heuristic post-processing to a DOCX file generated by pdf2docx
    to fix common issues with Chinese educational materials (hard breaks, spacing, headers).
    Returns True if processed successfully.
    """
    try:
        doc = Document(filepath)
    except Exception as e:
        logger.error(f"Failed to open DOCX for post-processing: {e}")
        return False

    logger.info("Starting DOCX post-processing heuristics...")

    try:
        # Pass 1: TOC Split and Spacing/Text Replacements
        paras = list(doc.paragraphs)
        i = 0
        while i < len(paras):
            para = paras[i]
            original_text = para.text.strip()
            if not original_text:
                i += 1
                continue

            # 1. Split glued TOC
            # If we see multiple dots...page number...dots...page number in the same para
            if len(re.findall(r'(?:\.{3,}|…+)\s*\d+', original_text)) > 1:
                toc_lines = split_glued_toc(original_text)
                if len(toc_lines) > 1:
                    # Replace current para with first line
                    para.text = fix_chinese_english_spacing(toc_lines[0])
                    # Insert subsequent lines as new paragraphs right after
                    for j in range(1, len(toc_lines)):
                        new_p = doc.add_paragraph(fix_chinese_english_spacing(toc_lines[j]))
                        # Move new_p right after para
                        para._element.getparent().insert(para._element.getparent().index(para._element) + j, new_p._element)
                        paras.insert(i + j, new_p)

                    # Ensure TOC dots are treated reasonably (we won't build a full Word TOC field for now,
                    # but splitting them makes them legible)
                    i += len(toc_lines)
                    continue

            # 2. Regular Spacing
            new_text = fix_chinese_english_spacing(original_text)
            if new_text != original_text:
                para.text = new_text

            apply_heading_styles(para)
            i += 1

        # Pass 2: Table Recovery
        # Detect sequential paragraphs that have 2+ columns separated by large spaces
        paras = list(doc.paragraphs)
        table_buffer = []

        i = 0
        while i < len(paras):
            p = paras[i]
            text = p.text.strip()

            # If it has tabular structure (multiple columns split by space) or matches known header
            if is_multi_column_data(text) or is_known_table_header(text):
                table_buffer.append(p)
            else:
                # Flush table buffer if it has 2+ rows
                if len(table_buffer) >= 2:
                    convert_to_table(doc, table_buffer)
                elif len(table_buffer) == 1 and is_known_table_header(table_buffer[0].text.strip()):
                    # Sometimes headers are followed directly by data on the next paragraph, even if it lacks obvious columns initially
                    # Try lookahead if next line is data
                    if i + 1 < len(paras) and paras[i+1].text.strip():
                        table_buffer.append(paras[i+1])
                        i += 1
                        convert_to_table(doc, table_buffer)
                table_buffer = []
            i += 1

        # Flush at the end
        if len(table_buffer) >= 2:
            convert_to_table(doc, table_buffer)

        # Pass 3: Ad cleanup
        # If there's an image at the very end of the document, try to clean it
        from .docx_ad_cleaner import clean_trailing_ad_from_docx
        doc.save(filepath)
        clean_trailing_ad_from_docx(filepath, filepath)

        # Reload doc
        doc = Document(filepath)

        # Pass 4: Paragraph merging (Hard Break Fixes)
        # Re-fetch paragraphs since we deleted/added some
        paras = list(doc.paragraphs)
        i = 0
        merged_count = 0

        while i < len(paras) - 1:
            p1 = paras[i]
            p2 = paras[i+1]

            t1 = p1.text.strip()
            t2 = p2.text.strip()

            # Decide if we should merge
            can_merge = False

            # If t1 and t2 are not empty
            if t1 and t2:
                # 1. Force merge signals (e.g. math broken, sentence clearly broken)
                if should_force_merge(t1, t2) and not is_heading_or_list(t2):
                     can_merge = True
                # 2. Heuristic merge: t1 doesn't end with sentence terminator, t2 is not a heading/list, t1 is not heading
                elif not is_sentence_end(t1) and not is_heading_or_list(t2) and not is_heading_or_list(t1):
                     can_merge = True

            if can_merge:
                join_char = " " if re.match(r'[a-zA-Z0-9]', t1[-1]) and re.match(r'[a-zA-Z0-9]', t2[0]) else ""
                p1.add_run(join_char + t2)

                p_element = p2._element
                p_element.getparent().remove(p_element)

                paras.pop(i+1)
                merged_count += 1
            else:
                i += 1

        logger.info(f"Post-processing complete. Merged {merged_count} paragraphs.")

        doc.save(filepath)
        return True

    except Exception as e:
        logger.error(f"Error during DOCX post-processing: {e}", exc_info=True)
        return False
