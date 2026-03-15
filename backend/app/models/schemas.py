from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ConversionType(str, Enum):
    WORD_TO_PDF = "word_to_pdf"
    PDF_TO_WORD = "pdf_to_word"

class TaskInfo(BaseModel):
    task_id: str
    conversion_type: ConversionType = ConversionType.WORD_TO_PDF
    original_filename: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Internal fields, not necessarily exposed to API
    input_filepath: str
    output_dir: str
    output_filepath: Optional[str] = None
    remove_ad: bool = True

    # Ad removal fields
    ad_removal_enabled: bool = True
    ad_removed: bool = False
    ad_remove_stage: Optional[str] = None
    ad_remove_error: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    conversion_type: ConversionType = ConversionType.WORD_TO_PDF
    original_filename: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Ad removal fields
    ad_removal_enabled: bool = True
    ad_removed: bool = False
    ad_remove_stage: Optional[str] = None
    ad_remove_error: Optional[str] = None
