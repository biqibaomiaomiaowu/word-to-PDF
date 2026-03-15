import asyncio
import os
from typing import Optional
from pdf2docx import Converter
from ..core.logger import logger

class PDFToWordService:
    @staticmethod
    async def convert_to_word(input_path: str, output_dir: str) -> str:
        """
        Converts a PDF file to a DOCX file using pdf2docx.
        Runs the conversion in a separate thread to avoid blocking the event loop.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        filename = os.path.basename(input_path)
        name, _ = os.path.splitext(filename)
        output_filepath = os.path.join(output_dir, f"{name}.docx")

        def _convert():
            try:
                cv = Converter(input_path)
                cv.convert(output_filepath, start=0, end=None)
                cv.close()
            except Exception as e:
                logger.error(f"pdf2docx conversion failed for {input_path}: {e}", exc_info=True)
                raise Exception(f"pdf2docx 转换异常: {str(e)}")

        # Run synchronous pdf2docx conversion in a thread pool
        try:
            logger.info(f"Starting pdf2docx conversion: {input_path} -> {output_filepath}")
            await asyncio.to_thread(_convert)

            if not os.path.exists(output_filepath):
                raise Exception("Conversion completed but output file is missing.")

            logger.info(f"pdf2docx conversion successful: {output_filepath}")
            return output_filepath

        except Exception as e:
            logger.error(f"Error during PDF to Word conversion: {e}", exc_info=True)
            raise e
