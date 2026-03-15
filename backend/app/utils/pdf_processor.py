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

def detect_large_ad_image(page: fitz.Page) -> float | None:
    """
    Checks for a large ad image in the bottom 55% of the page.
    Criteria:
    - y_center or bottom of image is in the bottom 55% (y >= 0.45 * page_height)
    - Image width >= 40% page width
    - Image height >= 15% page height
    Returns the y0 coordinate of the top of the image to crop if found, else None.
    """
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height

    # Bottom 55% area threshold
    y_threshold = page_height * 0.45

    crop_y0 = None

    for img in page.get_images(full=True):
        xref = img[0]
        rects = page.get_image_rects(xref)
        for rect in rects:
            img_width = rect.width
            img_height = rect.height

            # Check size constraints
            is_large_enough = (img_width >= page_width * 0.40) and (img_height >= page_height * 0.15)

            # Check location constraint (the image must have substantial presence in bottom 55%)
            # e.g., image bottom edge is below the y_threshold
            is_in_bottom = rect.y1 >= y_threshold

            if is_large_enough and is_in_bottom:
                # To be conservative, ensure the top of the image is also relatively low
                # e.g. at least 30% from top of page, so we don't crop top-level content
                if rect.y0 >= page_height * 0.30:
                    # Found an ad-like large image
                    # Find the minimum y0 among all such large images
                    if crop_y0 is None or rect.y0 < crop_y0:
                        crop_y0 = rect.y0

    return crop_y0

def detect_and_remove_ad_pre_conversion(pdf_path: str, output_path: str) -> bool:
    """
    Detects if the last page has an ad. If it does, removes/crops it and saves to output_path.
    Used for pre-processing before PDF->Word conversion.
    Returns True if ad was found and removed, False otherwise.
    """
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            doc.close()
            return False

        last_page_idx = doc.page_count - 1
        page = doc[last_page_idx]
        page_rect = page.rect
        page_height = page_rect.height

        crop_y_threshold = page_height * 0.45
        bottom_rect = fitz.Rect(0, crop_y_threshold, page_rect.width, page_height)
        text = page.get_text("text", clip=bottom_rect).replace("\n", "").replace(" ", "")

        is_ad = False
        ad_crop_y = None

        if contains_strong_keyword(text) or contains_combinations(text):
            is_ad = True
            ad_crop_y = crop_y_threshold

        if not is_ad:
            image_crop_y = detect_large_ad_image(page)
            if image_crop_y is not None:
                is_ad = True
                ad_crop_y = image_crop_y

        if is_ad:
            safe_crop_y = max(0, ad_crop_y - 5)
            top_rect = fitz.Rect(0, 0, page_rect.width, safe_crop_y)
            top_text = page.get_text("text", clip=top_rect).strip()

            has_top_images = False
            for img in page.get_images(full=True):
                xref = img[0]
                rects = page.get_image_rects(xref)
                for rect in rects:
                    if rect.y0 < safe_crop_y and rect.y1 > 0:
                        has_top_images = True
                        break
                if has_top_images:
                    break

            if not top_text and not has_top_images:
                doc.delete_page(last_page_idx)
                logger.info(f"Pre-conversion: Deleted last page of {pdf_path} due to ad.")
            else:
                page.set_cropbox(top_rect)
                logger.info(f"Pre-conversion: Cropped last page of {pdf_path} to remove ad at y={safe_crop_y}.")

            doc.save(output_path)
            doc.close()
            return True

        doc.close()
        return False

    except Exception as e:
        logger.error(f"Error processing PDF for pre-conversion ad removal {pdf_path}: {e}")
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

        # Define bottom 55% area for text checking
        crop_y_threshold = page_height * 0.45
        bottom_rect = fitz.Rect(0, crop_y_threshold, page_rect.width, page_height)

        # Extract text in the bottom 55%
        text = page.get_text("text", clip=bottom_rect).replace("\n", "").replace(" ", "")

        is_ad = False
        ad_crop_y = None

        # 1. Check strong text keywords
        if contains_strong_keyword(text) or contains_combinations(text):
            is_ad = True
            ad_crop_y = crop_y_threshold

        # 2. Check for large ad poster image (Fallback)
        # Even if no keywords found in text layer, a big poster image is enough to trigger removal
        if not is_ad:
            image_crop_y = detect_large_ad_image(page)
            if image_crop_y is not None:
                is_ad = True
                ad_crop_y = image_crop_y

        if is_ad:
            # Check if there is text below the ad we are cropping.
            # If there is substantial text below it, we shouldn't crop there.
            # However, for an ad image, usually there's no text below.

            # Add a small padding to the crop line (so we don't cut right on the pixel)
            safe_crop_y = max(0, ad_crop_y - 5)

            top_rect = fitz.Rect(0, 0, page_rect.width, safe_crop_y)
            top_text = page.get_text("text", clip=top_rect).strip()

            has_top_images = False
            for img in page.get_images(full=True):
                xref = img[0]
                rects = page.get_image_rects(xref)
                for rect in rects:
                    if rect.y0 < safe_crop_y and rect.y1 > 0: # image is partially or fully in top area
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
                logger.info(f"Cropped last page of {pdf_path} to remove ad at y={safe_crop_y}.")

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
