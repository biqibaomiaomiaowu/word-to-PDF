import fitz  # PyMuPDF
import os
from ..core.logger import logger

STRONG_KEYWORDS = [
    "五星好评",
    "免费领取",
    "扫码加微信",
    "持续免费更新",
    "教培合集",
    "教辅合集",
    "精品教培合集",
    "各大品牌知名教辅合集"
]

def contains_strong_keyword(text: str) -> bool:
    for kw in STRONG_KEYWORDS:
        if kw in text:
            return True
    return False

def contains_combinations(text: str) -> bool:
    combinations = [
        ("扫码", "微信"),
        ("免费", "领取"),
        ("合集", "免费更新"),
        ("二维码", "微信"),
        ("目录", "扫码领取")
    ]
    for w1, w2 in combinations:
        if w1 in text and w2 in text:
            return True
    return False

def contains_large_qr_and_keywords(page: fitz.Page, text: str) -> bool:
    """
    Checks for a large image (>= 20% width, >= 2% area) in the bottom 40%
    AND the presence of specific keywords in the text.
    """
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height
    page_area = page_width * page_height

    bottom_40_y = page_height * 0.60

    has_large_image = False
    for img in page.get_images(full=True):
        xref = img[0]
        # Get bounding box of the image on the page
        rects = page.get_image_rects(xref)
        for rect in rects:
            # Check if image is in the bottom 40%
            if rect.y1 > bottom_40_y:
                img_width = rect.width
                img_area = rect.width * rect.height
                if img_width >= page_width * 0.20 and img_area >= page_area * 0.02:
                    has_large_image = True
                    break
        if has_large_image:
            break

    if has_large_image:
        qr_keywords = ["扫码", "微信", "领取", "免费"]
        for kw in qr_keywords:
            if kw in text:
                return True
    return False

def detect_and_remove_ad(pdf_path: str) -> bool:
    """
    Detects if the last page has an ad at the bottom.
    If so, crops the ad or removes the page.
    Returns True if the file was modified, False otherwise.
    """
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            return False

        last_page_idx = doc.page_count - 1
        page = doc[last_page_idx]
        page_rect = page.rect
        page_height = page_rect.height

        # Define bottom 35% area
        crop_y_threshold = page_height * 0.65
        bottom_rect = fitz.Rect(0, crop_y_threshold, page_rect.width, page_height)

        # Extract text in the bottom 35%
        text = page.get_text("text", clip=bottom_rect).replace("\n", "").replace(" ", "")

        is_ad = False
        if contains_strong_keyword(text):
            is_ad = True
        elif contains_combinations(text):
            is_ad = True
        elif contains_large_qr_and_keywords(page, text):
            is_ad = True

        if is_ad:
            # Find the top-most y coordinate of any ad-related text/image in the bottom area
            # To be safe, we just crop at crop_y_threshold
            # However, if the ad is small, we could crop lower. But 65% is a good safe line.

            # Let's verify if the entire page is an ad (or becomes empty if we crop)
            # If we crop to crop_y_threshold, is there any content above it?
            top_rect = fitz.Rect(0, 0, page_rect.width, crop_y_threshold)
            top_text = page.get_text("text", clip=top_rect).strip()

            has_top_images = False
            for img in page.get_images(full=True):
                xref = img[0]
                rects = page.get_image_rects(xref)
                for rect in rects:
                    if rect.y0 < crop_y_threshold: # image is at least partially in the top area
                        has_top_images = True
                        break
                if has_top_images:
                    break

            if not top_text and not has_top_images:
                # Top area is empty, meaning the whole page was just the ad at the bottom
                # (or the ad occupied the whole page). Delete the page.
                doc.delete_page(last_page_idx)
                logger.info(f"Deleted last page of {pdf_path} due to ad.")
            else:
                # Crop the page to keep only the top part
                page.set_cropbox(top_rect)
                logger.info(f"Cropped last page of {pdf_path} to remove ad at bottom.")

            # Save changes. Save to a temporary file then replace to avoid inplace issues if any
            temp_path = pdf_path + ".tmp.pdf"
            doc.save(temp_path)
            doc.close()
            os.replace(temp_path, pdf_path)
            return True

        doc.close()
        return False

    except Exception as e:
        logger.error(f"Error processing PDF for ad removal {pdf_path}: {e}")
        return False
