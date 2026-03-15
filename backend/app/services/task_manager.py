import asyncio
import uuid
import os
from typing import Dict, Optional
from datetime import datetime, timezone

from ..core.logger import logger
from ..core.config import settings
from .libreoffice import LibreOfficeService
from .pdf_to_word import PDFToWordService
from ..models.schemas import TaskStatus, TaskInfo, ConversionType
from ..utils.pdf_processor import detect_and_remove_ad

class TaskManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.tasks: Dict[str, TaskInfo] = {}
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)
        self.worker_task = None

    def start(self):
        """Starts the background worker task."""
        self.worker_task = asyncio.create_task(self._worker())
        logger.info(f"Task manager started with max concurrency: {settings.MAX_CONCURRENT_TASKS}")

    async def stop(self):
        """Stops the background worker task."""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Task manager stopped.")

    async def enqueue_task(self, original_filename: str, input_filepath: str, remove_ad: bool = True, conversion_type: ConversionType = ConversionType.WORD_TO_PDF) -> str:
        """Enqueues a new conversion task and returns its task ID."""
        task_id = str(uuid.uuid4())

        # Create an isolated output directory for this task
        task_output_dir = os.path.join(settings.OUTPUT_DIR, task_id)
        os.makedirs(task_output_dir, exist_ok=True)

        task_info = TaskInfo(
            task_id=task_id,
            conversion_type=conversion_type,
            original_filename=original_filename,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            input_filepath=input_filepath,
            output_dir=task_output_dir,
            remove_ad=remove_ad if conversion_type == ConversionType.WORD_TO_PDF else False
        )

        self.tasks[task_id] = task_info
        await self.queue.put(task_id)
        logger.info(f"Enqueued task {task_id} for file {original_filename}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Retrieves the status of a specific task."""
        return self.tasks.get(task_id)

    async def _worker(self):
        """Background worker that pulls tasks from the queue and processes them."""
        while True:
            try:
                task_id = await self.queue.get()
                logger.info(f"Worker picked up task {task_id}")

                # Use semaphore to limit concurrent LibreOffice processes
                async with self.semaphore:
                    await self._process_task(task_id)

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in task worker: {e}")

    async def _process_task(self, task_id: str):
        """Executes the actual conversion logic for a task."""
        task_info = self.tasks.get(task_id)
        if not task_info:
            logger.warning(f"Task {task_id} not found in memory during processing.")
            return

        task_info.status = TaskStatus.PROCESSING

        try:
            conversion_input_path = task_info.input_filepath
            temp_cleaned_docx = None
            output_filepath = None

            logger.info(f"Processing task {task_id} with conversion type {task_info.conversion_type}")

            if task_info.conversion_type == ConversionType.WORD_TO_PDF:
                task_info.ad_removal_enabled = task_info.remove_ad

                # Stage 1: DOCX Pre-cleaning
                if task_info.remove_ad:
                    from .docx_ad_cleaner import clean_trailing_ad_from_docx
                    from pathlib import Path

                    temp_cleaned_docx = os.path.join(settings.OUTPUT_DIR, f"{task_id}_cleaned.docx")
                    try:
                        is_cleaned = clean_trailing_ad_from_docx(
                            Path(task_info.input_filepath),
                            Path(temp_cleaned_docx)
                        )
                        if is_cleaned:
                            conversion_input_path = temp_cleaned_docx
                            task_info.ad_removed = True
                            task_info.ad_remove_stage = "docx"
                    except Exception as docx_err:
                        logger.warning(f"DOCX pre-cleaning failed for task {task_id}: {docx_err}")
                        task_info.ad_remove_error = f"DOCX Stage Error: {docx_err}"

                # Execute conversion
                output_filepath = await LibreOfficeService.convert_to_pdf(
                    input_path=conversion_input_path,
                    output_dir=task_info.output_dir
                )

                # Stage 2: PDF Fallback Cleaning
                if task_info.remove_ad and not task_info.ad_removed:
                    try:
                        is_cleaned_pdf = detect_and_remove_ad(output_filepath)
                        if is_cleaned_pdf:
                            task_info.ad_removed = True
                            task_info.ad_remove_stage = "pdf"
                    except Exception as ad_err:
                        logger.warning(f"Failed to remove ad in PDF stage for task {task_id}: {ad_err}")
                        if not task_info.ad_remove_error:
                            task_info.ad_remove_error = f"PDF Stage Error: {ad_err}"
                        else:
                            task_info.ad_remove_error += f" | PDF Stage Error: {ad_err}"

            elif task_info.conversion_type == ConversionType.PDF_TO_WORD:
                task_info.ad_removal_enabled = False
                logger.info(f"Using pdf2docx for conversion task {task_id}")

                try:
                    output_filepath = await PDFToWordService.convert_to_word(
                        input_path=conversion_input_path,
                        output_dir=task_info.output_dir
                    )
                except Exception as e:
                    task_info.error_code = "conversion_failed"
                    raise Exception(f"转换失败：PDF 内容解析失败。")

                # Post-process to fix hard breaks and common layout issues
                from .docx_postprocessor import postprocess_docx
                postprocess_docx(output_filepath)

                # DOCX Quality Validation
                from ..utils.docx_validator import validate_docx_quality
                quality_report = validate_docx_quality(output_filepath)

                if quality_report.get("final_quality_level") == "failed":
                    task_info.error_code = "quality_validation_failed"
                    logger.error(f"Task {task_id} validation failed: DOCX quality is pseudo-success/blank.")
                    raise Exception(quality_report["warnings"][0])

                if quality_report.get("warnings"):
                    task_info.warnings = quality_report["warnings"]
                if quality_report.get("quality_warnings"):
                    task_info.quality_warnings = quality_report["quality_warnings"]

                # Pass detailed quality scores
                task_info.final_quality_level = quality_report.get("final_quality_level")
                task_info.paragraph_recovery_score = quality_report.get("paragraph_recovery_score")
                task_info.table_recovery_score = quality_report.get("table_recovery_score")
                task_info.math_expression_score = quality_report.get("math_expression_score")
                task_info.spacing_score = quality_report.get("spacing_score")
                task_info.character_cleanliness_score = quality_report.get("character_cleanliness_score")

            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now(timezone.utc)
            task_info.output_filepath = output_filepath

            # Clean up the input files
            try:
                if os.path.exists(task_info.input_filepath):
                    os.remove(task_info.input_filepath)
                if temp_cleaned_docx and os.path.exists(temp_cleaned_docx):
                    os.remove(temp_cleaned_docx)
            except Exception as e:
                logger.warning(f"Failed to remove temp files for task {task_id}: {e}")

        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now(timezone.utc)
            task_info.error_message = str(e)
            if not task_info.error_code:
                task_info.error_code = "conversion_failed"
            logger.error(f"Task {task_id} [{task_info.conversion_type}] for {task_info.original_filename} failed: {e}", exc_info=True)

# Global instance of task manager
task_manager = TaskManager()
