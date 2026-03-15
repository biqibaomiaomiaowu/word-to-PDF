import asyncio
import os
import cv2
import numpy as np
from typing import Optional
from ..core.logger import logger
import fitz

# Global engine instance
_paddle_engine = None

def get_paddle_engine():
    global _paddle_engine
    if _paddle_engine is None:
        logger.info("Initializing PaddleOCR PP-Structure layout recovery engine...")
        try:
            from paddleocr import PPStructure
            _paddle_engine = PPStructure(
                show_log=False,
                recovery=True, # Important: enables recovery to docx
                lang='ch', # Chinese support
                use_gpu=False, # Use CPU for local POC
                layout=True,
                table=True,
                ocr=True
            )
            logger.info("PaddleOCR PP-Structure engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR engine: {e}")
            raise
    return _paddle_engine

class PDFToWordPaddleService:
    @staticmethod
    async def convert_to_word(input_path: str, output_dir: str) -> str:
        """
        Converts a complex layout PDF file to a DOCX file using PaddleOCR PP-Structure.
        Since PP-Structure typically operates on images and creates one DOCX per image,
        we convert the PDF to images, run the recovery, and then merge the resulting DOCX files.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        filename = os.path.basename(input_path)
        name, _ = os.path.splitext(filename)
        output_filepath = os.path.join(output_dir, f"{name}.docx")

        # Temp dir for intermediate files
        temp_dir = os.path.join(output_dir, f"paddle_temp_{name}")
        os.makedirs(temp_dir, exist_ok=True)

        def _convert():
            from paddleocr import save_structure_res
            import docx
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn

            try:
                engine = get_paddle_engine()
                doc = fitz.open(input_path)
                logger.info(f"PaddleOCR processing {doc.page_count} pages for {input_path}")

                generated_docx_paths = []

                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    # Render page to image at high resolution (e.g., 200 DPI) for better OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))

                    # Convert fitz pixmap to numpy array (cv2 format)
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

                    # Convert RGB to BGR for cv2 if needed
                    if pix.n == 3:
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    elif pix.n == 4: # RGBA
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

                    # Run PP-Structure layout recovery on the image
                    logger.info(f"Running layout recovery on page {page_num+1}/{doc.page_count}")
                    result = engine(img_array)

                    # Save the recovery result to a DOCX file for this page
                    # save_structure_res handles the recovery logic
                    save_folder = os.path.join(temp_dir, f"page_{page_num}")
                    os.makedirs(save_folder, exist_ok=True)
                    img_name = f"page_{page_num}"

                    save_structure_res(result, save_folder, img_name)

                    # PP-Structure recovery saves it as '{save_folder}/{img_name}_recovery.docx'
                    page_docx_path = os.path.join(save_folder, f"{img_name}_recovery.docx")

                    if os.path.exists(page_docx_path):
                        generated_docx_paths.append(page_docx_path)
                    else:
                        logger.warning(f"PaddleOCR failed to generate DOCX for page {page_num+1}")

                doc.close()

                if not generated_docx_paths:
                    raise Exception("No pages were successfully recovered by PaddleOCR.")

                # Merge the generated DOCX files into one
                logger.info(f"Merging {len(generated_docx_paths)} recovered DOCX pages into {output_filepath}")
                merged_doc = docx.Document(generated_docx_paths[0])

                for path in generated_docx_paths[1:]:
                    if not os.path.exists(path):
                        continue

                    # Add a page break
                    merged_doc.add_page_break()

                    sub_doc = docx.Document(path)
                    for element in sub_doc.element.body:
                        # Copy elements (paragraphs, tables) from sub_doc to merged_doc
                        if element.tag.endswith('sectPr'):
                            continue # Skip section properties of the sub doc
                        merged_doc.element.body.append(element)

                merged_doc.save(output_filepath)
                logger.info(f"PaddleOCR layout recovery completed successfully: {output_filepath}")

            except Exception as e:
                logger.error(f"PaddleOCR conversion failed for {input_path}: {e}", exc_info=True)
                raise Exception(f"复杂版面恢复引擎(PaddleOCR)转换异常: {str(e)}")
            finally:
                # Cleanup temporary directories
                import shutil
                if os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        logger.warning(f"Failed to clean up PaddleOCR temp dir {temp_dir}: {e}")

        # Run synchronous conversion in a thread pool
        try:
            logger.info(f"Starting PaddleOCR layout recovery: {input_path} -> {output_filepath}")
            await asyncio.to_thread(_convert)

            if not os.path.exists(output_filepath):
                raise Exception("Conversion completed but output file is missing.")

            return output_filepath

        except Exception as e:
            logger.error(f"Error during PDF to Word conversion (Paddle): {e}", exc_info=True)
            raise e
