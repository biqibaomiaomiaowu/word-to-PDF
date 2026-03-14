from fastapi import UploadFile, HTTPException, status
from ..core.config import settings

ALLOWED_MIME_TYPES = [
    "application/msword", # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", # .docx
]

ALLOWED_EXTENSIONS = [".doc", ".docx"]

async def validate_file(file: UploadFile) -> None:
    # Check extension
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = f".{filename.rsplit('.', 1)[-1].lower()}"

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension. Allowed extensions are: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Only Word documents are allowed."
        )

    # Check file size directly from the UploadFile object
    file_size = file.size

    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size and file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File is too large. Max size is {settings.MAX_FILE_SIZE_MB}MB."
        )
