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

class ConverterMode(str, Enum):
    AUTO = "auto"
    PDF2DOCX = "pdf2docx"
    PADDLE = "paddle"

class TaskInfo(BaseModel):
    task_id: str
    conversion_type: ConversionType = ConversionType.WORD_TO_PDF
    original_filename: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None

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

    # Route info
    converter_mode: ConverterMode = ConverterMode.AUTO
    converter_used: Optional[str] = None
    route_reason: Optional[str] = None
    primary_converter: Optional[str] = None
    fallback_attempted: bool = False
    fallback_reason: Optional[str] = None

    # Quality info (for PDF to Word)
    warnings: Optional[list[str]] = None
    quality_warnings: Optional[list[str]] = None
    final_quality_level: Optional[str] = None
    paragraph_recovery_score: Optional[float] = None
    table_recovery_score: Optional[float] = None
    math_expression_score: Optional[float] = None
    numeric_list_recovery_score: Optional[float] = None
    spacing_score: Optional[float] = None
    character_cleanliness_score: Optional[float] = None
    heading_structure_score: Optional[float] = None
    image_anchor_risk: Optional[bool] = None

class TaskResponse(BaseModel):
    task_id: str
    conversion_type: ConversionType = ConversionType.WORD_TO_PDF
    original_filename: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Ad removal fields
    ad_removal_enabled: bool = True
    ad_removed: bool = False
    ad_remove_stage: Optional[str] = None
    ad_remove_error: Optional[str] = None

    # Route info
    converter_mode: ConverterMode = ConverterMode.AUTO
    converter_used: Optional[str] = None
    route_reason: Optional[str] = None
    primary_converter: Optional[str] = None
    fallback_attempted: bool = False
    fallback_reason: Optional[str] = None

    # Quality info
    warnings: Optional[list[str]] = None
    quality_warnings: Optional[list[str]] = None
    final_quality_level: Optional[str] = None
    paragraph_recovery_score: Optional[float] = None
    table_recovery_score: Optional[float] = None
    math_expression_score: Optional[float] = None
    numeric_list_recovery_score: Optional[float] = None
    spacing_score: Optional[float] = None
    character_cleanliness_score: Optional[float] = None
    heading_structure_score: Optional[float] = None
    image_anchor_risk: Optional[bool] = None
