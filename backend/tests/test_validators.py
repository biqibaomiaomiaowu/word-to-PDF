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
        await validate_file(mock_upload)
    assert exc_info.value.status_code == 400
    assert "Invalid file extension" in exc_info.value.detail

@pytest.mark.asyncio
async def test_validate_file_invalid_mime():
    mock_upload = UploadFile(file=None, filename="test.doc", size=10, headers=Headers({"content-type": "image/png"}))
    with pytest.raises(HTTPException) as exc_info:
        await validate_file(mock_upload)
    assert exc_info.value.status_code == 400
    assert "Invalid file type" in exc_info.value.detail
