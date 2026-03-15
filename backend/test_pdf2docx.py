import asyncio
import os
import shutil
from app.services.pdf_to_word import PDFToWordService
from app.utils.docx_validator import validate_docx_quality

async def main():
    try:
        shutil.copy("fake.pdf", "test_fake.pdf")
        os.makedirs("test_output", exist_ok=True)
        out_path = await PDFToWordService.convert_to_word("test_fake.pdf", "test_output")
        print("Output created at:", out_path)
        is_valid = validate_docx_quality(out_path)
        print("Is DOCX valid:", is_valid)
    except Exception as e:
        print("Exception occurred:", e)

if __name__ == "__main__":
    asyncio.run(main())
