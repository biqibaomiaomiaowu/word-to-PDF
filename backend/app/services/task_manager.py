import asyncio
import uuid
import os
from typing import Dict, Optional
from datetime import datetime, timezone

from ..core.logger import logger
from ..core.config import settings
from .libreoffice import LibreOfficeService
from .pdf_to_word_pdf2docx import PDFToWordService
from .pdf_to_word_paddle import PDFToWordPaddleService
from .pdf_route_selector import PDFRouteSelector
from ..models.schemas import TaskStatus, TaskInfo, ConversionType, ConverterMode
from ..utils.pdf_processor import detect_and_remove_ad, detect_and_remove_ad_pre_conversion
from ..utils.paddle_env import check_paddle_available

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

    async def enqueue_task(self, original_filename: str, input_filepath: str, remove_ad: bool = True, conversion_type: ConversionType = ConversionType.WORD_TO_PDF, converter_mode: ConverterMode = ConverterMode.AUTO) -> str:
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
            remove_ad=remove_ad,
            converter_mode=converter_mode if conversion_type == ConversionType.PDF_TO_WORD else ConverterMode.AUTO
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
                task_info.ad_removal_enabled = task_info.remove_ad

                # Pre-processing: Ad Removal
                if task_info.remove_ad:
                    logger.info(f"Checking for ad pages in {conversion_input_path} (pre-conversion)")
                    cleaned_pdf_path = os.path.join(task_info.output_dir, f"{task_id}_no_ad.pdf")
                    is_ad_removed = detect_and_remove_ad_pre_conversion(conversion_input_path, cleaned_pdf_path)

                    if is_ad_removed:
                        logger.info(f"Ad page removed, using {cleaned_pdf_path} for conversion.")
                        conversion_input_path = cleaned_pdf_path
                        task_info.ad_removed = True
                        task_info.ad_remove_stage = "pdf_pre_conversion"

                # Routing Logic
                if task_info.converter_mode == ConverterMode.AUTO:
                    converter, reason, stats = PDFRouteSelector.analyze_pdf(conversion_input_path)
                elif task_info.converter_mode == ConverterMode.PDF2DOCX:
                    converter = "pdf2docx"
                    reason = "User selected standard engine."
                elif task_info.converter_mode == ConverterMode.PADDLE:
                    paddle_available, reason = check_paddle_available(use_cache=True)
                    if not paddle_available:
                        task_info.error_code = "conversion_failed"
                        raise Exception(f"复杂版面引擎未配置，无法执行转换: {reason}")
                    converter = "paddle"
                    reason = "User forced complex layout engine."
                else:
                    converter = "pdf2docx"
                    reason = "Unknown converter mode, defaulting to standard engine."

                task_info.primary_converter = converter
                task_info.converter_used = converter
                task_info.route_reason = reason

                logger.info(f"PDF Routing Decision for task {task_id}: Mode: {task_info.converter_mode.value}, Converter: {converter} - Reason: {reason}")

                from ..utils.docx_validator import validate_docx_quality
                from .docx_postprocessor import postprocess_docx

                async def perform_conversion(engine_type: str, input_file: str, out_dir: str):
                    """Helper to execute conversion + postprocess + validation"""
                    if engine_type == 'paddle':
                        out_path = await PDFToWordPaddleService.convert_to_word(input_file, out_dir)
                    else:
                        out_path = await PDFToWordService.convert_to_word(input_file, out_dir)

                    if engine_type == 'pdf2docx':
                        postprocess_docx(out_path)

                    # Validate quality
                    report = validate_docx_quality(out_path)
                    return out_path, report

                try:
                    output_filepath, quality_report = await perform_conversion(converter, conversion_input_path, task_info.output_dir)

                    # Limited fallback mechanism for Paddle
                    if converter == 'paddle' and quality_report.get("final_quality_level") in ["failed", "poor"]:
                        logger.warning(f"Paddle conversion produced poor quality or failed. Attempting fallback to pdf2docx for task {task_id}")
                        task_info.fallback_attempted = True
                        task_info.fallback_reason = "quality_poor_or_failed"

                        fallback_out_dir = os.path.join(task_info.output_dir, "fallback")
                        os.makedirs(fallback_out_dir, exist_ok=True)

                        try:
                            fb_out_path, fb_report = await perform_conversion('pdf2docx', conversion_input_path, fallback_out_dir)

                            fb_score = fb_report.get("paragraph_recovery_score", 0) + fb_report.get("table_recovery_score", 0)
                            primary_score = quality_report.get("paragraph_recovery_score", 0) + quality_report.get("table_recovery_score", 0)

                            if fb_score > primary_score or quality_report.get("final_quality_level") == "failed":
                                logger.info(f"Fallback to pdf2docx produced better results. Using fallback.")
                                output_filepath = fb_out_path
                                quality_report = fb_report
                                task_info.converter_used = 'pdf2docx'
                            else:
                                logger.info(f"Fallback to pdf2docx did not improve results. Keeping Paddle output.")

                        except Exception as fb_err:
                            logger.error(f"Fallback conversion failed: {fb_err}", exc_info=True)
                            if quality_report.get("final_quality_level") == "failed":
                                raise Exception(quality_report.get("warnings", ["Unknown quality error"])[0])

                except Exception as e:
                    if converter == 'paddle':
                        logger.warning(f"Paddle conversion completely failed: {e}. Attempting fallback to pdf2docx for task {task_id}")
                        task_info.fallback_attempted = True
                        task_info.fallback_reason = f"exception: {str(e)}"
                        task_info.converter_used = 'pdf2docx'
                        try:
                            output_filepath, quality_report = await perform_conversion('pdf2docx', conversion_input_path, task_info.output_dir)
                        except Exception as fallback_e:
                            task_info.error_code = "conversion_failed"
                            raise Exception(f"主路线与备用路线转换均失败。最后错误: {str(fallback_e)}")
                    else:
                        task_info.error_code = "conversion_failed"
                        raise Exception(f"转换失败：PDF 内容解析失败。错误信息: {str(e)}")

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
                task_info.numeric_list_recovery_score = quality_report.get("numeric_list_recovery_score")
                task_info.spacing_score = quality_report.get("spacing_score")
                task_info.character_cleanliness_score = quality_report.get("character_cleanliness_score")
                task_info.heading_structure_score = quality_report.get("heading_structure_score")
                task_info.image_anchor_risk = quality_report.get("image_anchor_risk")

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
