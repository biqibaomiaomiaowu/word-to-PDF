import asyncio
import os
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
        if not os.path.exists(input_path):
            raise ConversionError(f"Input file not found: {input_path}")

        os.makedirs(output_dir, exist_ok=True)

        # Command line arguments for LibreOffice headless
        cmd = [
            "libreoffice",
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            input_path
        ]

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
            expected_output_path = os.path.join(output_dir, f"{name_without_ext}.pdf")

            if not os.path.exists(expected_output_path):
                logger.error(f"Output file not found after conversion: {expected_output_path}")
                raise ConversionError("Failed to generate PDF file.")

            logger.info(f"Successfully converted {input_path} to {expected_output_path}")
            return expected_output_path

        except ConversionError:
            raise
        except Exception as e:
            logger.exception("Unexpected error during LibreOffice execution")
            raise ConversionError(f"Unexpected error during conversion: {str(e)}")
