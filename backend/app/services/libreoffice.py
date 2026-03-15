import asyncio
import os
import sys
import subprocess
from ..core.logger import logger
from ..core.exceptions import ConversionError
from ..core.config import settings

class LibreOfficeService:
    @staticmethod
    async def convert_to_pdf(input_path: str, output_dir: str) -> str:
        """
        Converts a document to PDF using LibreOffice headless.
        Returns the path to the converted PDF file.
        """
        return await LibreOfficeService._execute_conversion(input_path, output_dir, "pdf", None)

    @staticmethod
    async def convert_to_word(input_path: str, output_dir: str) -> str:
        """
        Converts a PDF document to Word (DOCX) using LibreOffice headless.
        Returns the path to the converted DOCX file.
        """
        return await LibreOfficeService._execute_conversion(input_path, output_dir, "docx", "writer_pdf_import")

    @staticmethod
    async def _execute_conversion(input_path: str, output_dir: str, output_format: str, infilter: str = None) -> str:
        if not os.path.exists(input_path):
            raise ConversionError(f"Input file not found: {input_path}")

        os.makedirs(output_dir, exist_ok=True)

        # Convert to absolute paths to prevent LibreOffice issues on Windows
        abs_input_path = os.path.abspath(input_path)
        abs_output_dir = os.path.abspath(output_dir)

        # Determine the correct executable name based on the OS
        executable = "soffice" if sys.platform.startswith("win") else "libreoffice"

        # Command line arguments for LibreOffice headless
        cmd = [
            executable,
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--norestore"
        ]

        if infilter:
            cmd.append(f"--infilter={infilter}")

        cmd.extend([
            "--convert-to", output_format,
            "--outdir", abs_output_dir,
            abs_input_path
        ])

        logger.info(f"Executing conversion command: {' '.join(cmd)}")

        try:
            # We run subprocess in a thread pool to not block the async event loop
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.CONVERSION_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                process.kill()
                logger.error(f"LibreOffice conversion timeout for file: {input_path}")
                raise ConversionError("Conversion process timed out.")

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                logger.error(f"LibreOffice conversion failed. Error: {error_msg}")
                raise ConversionError(f"Conversion failed with status {process.returncode}")

            # Check if output file was created
            base_name = os.path.basename(input_path)
            name_without_ext = os.path.splitext(base_name)[0]
            expected_output_path = os.path.join(output_dir, f"{name_without_ext}.{output_format}")

            if not os.path.exists(expected_output_path):
                logger.error(f"Output file not found after conversion: {expected_output_path}")
                raise ConversionError(f"Failed to generate {output_format.upper()} file.")

            logger.info(f"Successfully converted {input_path} to {expected_output_path}")
            return expected_output_path

        except ConversionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error during LibreOffice execution")
            raise ConversionError(f"Unexpected error during conversion: {str(e)}")
