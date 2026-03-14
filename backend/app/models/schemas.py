from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskInfo(BaseModel):
    task_id: str
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

class TaskResponse(BaseModel):
    task_id: str
    original_filename: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
