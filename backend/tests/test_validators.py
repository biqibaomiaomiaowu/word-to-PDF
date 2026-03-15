import pytest
from fastapi import UploadFile, HTTPException
from fastapi.datastructures import Headers
from app.utils.file_validators import validate_file

@pytest.mark.asyncio
async def test_validate_file_invalid_extension():
    # Create a mock file with invalid extension
    class MockFile:
        def __init__(self):
            self.filename = "test.txt"
            self.content_type = "text/plain"

    mock_upload = UploadFile(file=None, filename="test.txt", size=10, headers=Headers({"content-type": "text/plain"}))
    with pytest.raises(HTTPException) as exc_info:
        from app.models.schemas import ConversionType
        await validate_file(mock_upload, conversion_type=ConversionType.WORD_TO_PDF)
    assert exc_info.value.status_code == 400
    assert "上传失败：文件类型不支持" in exc_info.value.detail

@pytest.mark.asyncio
async def test_validate_file_invalid_mime():
    mock_upload = UploadFile(file=None, filename="test.doc", size=10, headers=Headers({"content-type": "image/png"}))
    with pytest.raises(HTTPException) as exc_info:
        from app.models.schemas import ConversionType
        await validate_file(mock_upload, conversion_type=ConversionType.WORD_TO_PDF)
    assert exc_info.value.status_code == 400
    assert "上传失败：文件类型不支持" in exc_info.value.detail
