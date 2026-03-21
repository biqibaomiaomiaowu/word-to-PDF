import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form
from fastapi.responses import FileResponse
from typing import Dict

from ..core.config import settings
from ..core.logger import logger
from ..utils.file_validators import validate_file
from ..services.task_manager import task_manager
from ..services.word_com import get_word_com_availability
from ..models.schemas import TaskResponse, TaskStatus, ConversionType, ConverterMode
from ..utils.converter_modes import build_invalid_converter_mode_message, is_converter_mode_supported
from ..utils.paddle_runtime import check_paddle_available

router = APIRouter()

@router.get("/health", summary="Health check endpoint")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}

@router.post("/convert", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED, summary="Upload a file for conversion")
async def upload_for_conversion(
    file: UploadFile = File(...),
    remove_ad: bool = Form(True, description="Whether to detect and remove ads from the last page"),
    conversion_type: ConversionType = Form(ConversionType.WORD_TO_PDF, description="The type of conversion to perform"),
    converter_mode: ConverterMode = Form(ConverterMode.AUTO, description="The converter engine to use")
):
    if not is_converter_mode_supported(conversion_type, converter_mode):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_invalid_converter_mode_message(conversion_type, converter_mode)
        )

    if converter_mode == ConverterMode.PADDLE:
        paddle_available, reason = check_paddle_available(use_cache=True)
        if not paddle_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"复杂版面引擎未正确配置: {reason}"
            )

    if conversion_type == ConversionType.WORD_TO_PDF and converter_mode == ConverterMode.WORD:
        word_available, reason = get_word_com_availability()
        if not word_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Microsoft Word export is unavailable: {reason}"
            )

    # 1. Validate file
    await validate_file(file, conversion_type)

    # 2. Save file locally
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    input_filepath = os.path.join(settings.UPLOAD_DIR, safe_filename)

    try:
        with open(input_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save uploaded file.")

    # 3. Enqueue task
    task_id = await task_manager.enqueue_task(
        original_filename=file.filename,
        input_filepath=input_filepath,
        remove_ad=remove_ad,
        conversion_type=conversion_type,
        converter_mode=converter_mode
    )

    task_info = task_manager.get_task_status(task_id)

    return TaskResponse(
        task_id=task_info.task_id,
        conversion_type=task_info.conversion_type,
        original_filename=task_info.original_filename,
        status=task_info.status,
        created_at=task_info.created_at,
        converter_mode=task_info.converter_mode
    )

@router.get("/tasks/{task_id}", response_model=TaskResponse, summary="Get conversion task status")
async def get_task_status(task_id: str):
    task_info = task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or expired.")

    return TaskResponse(
        task_id=task_info.task_id,
        conversion_type=task_info.conversion_type,
        original_filename=task_info.original_filename,
        status=task_info.status,
        created_at=task_info.created_at,
        completed_at=task_info.completed_at,
        error_message=task_info.error_message,
        error_code=task_info.error_code,
        ad_removal_enabled=task_info.ad_removal_enabled,
        ad_removed=task_info.ad_removed,
        ad_remove_stage=task_info.ad_remove_stage,
        ad_remove_error=task_info.ad_remove_error,
        converter_mode=task_info.converter_mode,
        converter_used=task_info.converter_used,
        route_reason=task_info.route_reason,
        primary_converter=task_info.primary_converter,
        fallback_attempted=task_info.fallback_attempted,
        fallback_reason=task_info.fallback_reason,
        warnings=task_info.warnings,
        quality_warnings=task_info.quality_warnings,
        final_quality_level=task_info.final_quality_level,
        paragraph_recovery_score=task_info.paragraph_recovery_score,
        table_recovery_score=task_info.table_recovery_score,
        math_expression_score=task_info.math_expression_score,
        numeric_list_recovery_score=task_info.numeric_list_recovery_score,
        spacing_score=task_info.spacing_score,
        character_cleanliness_score=task_info.character_cleanliness_score,
        heading_structure_score=task_info.heading_structure_score,
        image_anchor_risk=task_info.image_anchor_risk
    )

@router.get("/download/{task_id}", summary="Download converted file")
async def download_file(task_id: str):
    task_info = task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or expired.")

    if task_info.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Task is not completed. Current status: {task_info.status}")

    if not task_info.output_filepath or not os.path.exists(task_info.output_filepath):
        logger.error(f"Task {task_id} completed but file not found at {task_info.output_filepath}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Converted file is missing on server.")

    original_name_without_ext = os.path.splitext(task_info.original_filename)[0]

    if task_info.conversion_type == ConversionType.WORD_TO_PDF:
        ext = ".pdf"
        media_type = "application/pdf"
    elif task_info.conversion_type == ConversionType.PDF_TO_WORD:
        ext = ".docx"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        ext = ".bin"
        media_type = "application/octet-stream"

    download_filename = f"{original_name_without_ext}{ext}"

    return FileResponse(
        path=task_info.output_filepath,
        filename=download_filename,
        media_type=media_type
    )
