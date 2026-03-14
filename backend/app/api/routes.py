import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from typing import Dict

from ..core.config import settings
from ..core.logger import logger
from ..utils.file_validators import validate_file
from ..services.task_manager import task_manager
from ..models.schemas import TaskResponse, TaskStatus

router = APIRouter()

@router.get("/health", summary="Health check endpoint")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}

@router.post("/convert", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED, summary="Upload a Word file for conversion")
async def upload_for_conversion(file: UploadFile = File(...)):
    # 1. Validate file
    await validate_file(file)

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
        input_filepath=input_filepath
    )

    task_info = task_manager.get_task_status(task_id)

    return TaskResponse(
        task_id=task_info.task_id,
        original_filename=task_info.original_filename,
        status=task_info.status,
        created_at=task_info.created_at
    )

@router.get("/tasks/{task_id}", response_model=TaskResponse, summary="Get conversion task status")
async def get_task_status(task_id: str):
    task_info = task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or expired.")

    return TaskResponse(
        task_id=task_info.task_id,
        original_filename=task_info.original_filename,
        status=task_info.status,
        created_at=task_info.created_at,
        completed_at=task_info.completed_at,
        error_message=task_info.error_message
    )

@router.get("/download/{task_id}", summary="Download converted PDF")
async def download_pdf(task_id: str):
    task_info = task_manager.get_task_status(task_id)
    if not task_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or expired.")

    if task_info.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Task is not completed. Current status: {task_info.status}")

    if not task_info.output_filepath or not os.path.exists(task_info.output_filepath):
        logger.error(f"Task {task_id} completed but file not found at {task_info.output_filepath}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Converted file is missing on server.")

    original_name_without_ext = os.path.splitext(task_info.original_filename)[0]
    download_filename = f"{original_name_without_ext}.pdf"

    return FileResponse(
        path=task_info.output_filepath,
        filename=download_filename,
        media_type="application/pdf"
    )
