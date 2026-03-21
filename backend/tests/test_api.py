import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_convert_rejects_invalid_mode_for_word_to_pdf():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/convert",
            files={
                "file": (
                    "test.docx",
                    b"not-a-real-docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={
                "conversion_type": "word_to_pdf",
                "converter_mode": "paddle",
                "remove_ad": "true",
            },
        )

    assert response.status_code == 400
    assert "word_to_pdf" in response.json()["detail"]


@pytest.mark.asyncio
async def test_convert_rejects_invalid_mode_for_pdf_to_word():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/convert",
            files={
                "file": (
                    "test.pdf",
                    b"%PDF-1.4\n",
                    "application/pdf",
                )
            },
            data={
                "conversion_type": "pdf_to_word",
                "converter_mode": "word",
                "remove_ad": "true",
            },
        )

    assert response.status_code == 400
    assert "pdf_to_word" in response.json()["detail"]
