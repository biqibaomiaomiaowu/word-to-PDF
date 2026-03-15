from fastapi import UploadFile, HTTPException, status
from ..core.config import settings
from ..models.schemas import ConversionType

ALLOWED_MIME_TYPES_WORD = [
    "application/msword", # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", # .docx
]
ALLOWED_EXTENSIONS_WORD = [".doc", ".docx"]

ALLOWED_MIME_TYPES_PDF = ["application/pdf"]
ALLOWED_EXTENSIONS_PDF = [".pdf"]

async def validate_file(file: UploadFile, conversion_type: ConversionType) -> None:
    # Check extension
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = f".{filename.rsplit('.', 1)[-1].lower()}"

    if conversion_type == ConversionType.WORD_TO_PDF:
        if ext not in ALLOWED_EXTENSIONS_WORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"上传失败：当前为 Word 转 PDF 模式，仅支持 .doc/.docx，不支持 {ext}"
            )
        if file.content_type not in ALLOWED_MIME_TYPES_WORD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传失败：文件 MIME 类型不支持"
            )
    elif conversion_type == ConversionType.PDF_TO_WORD:
        if ext not in ALLOWED_EXTENSIONS_PDF:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"上传失败：当前为 PDF 转 Word 模式，仅支持 .pdf，不支持 {ext}"
            )
        if file.content_type not in ALLOWED_MIME_TYPES_PDF:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传失败：文件 MIME 类型不支持"
            )

    # Check file size directly from the UploadFile object
    file_size = file.size

    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size and file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="上传失败：文件大小超出限制"
        )
