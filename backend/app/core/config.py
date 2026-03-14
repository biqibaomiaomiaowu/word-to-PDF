from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Word to PDF Converter"
    API_V1_STR: str = "/api"

    # Files & Paths
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "temp_uploads")
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output_pdfs")

    # Limitations
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", 50))
    CONVERSION_TIMEOUT_SECONDS: int = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", 120))

    # Concurrency
    MAX_CONCURRENT_TASKS: int = int(os.getenv("MAX_CONCURRENT_TASKS", 1))

    # Cleanup
    FILE_RETENTION_SECONDS: int = int(os.getenv("FILE_RETENTION_SECONDS", 3600)) # 1 hour default
    ENABLE_AUTO_CLEANUP: bool = os.getenv("ENABLE_AUTO_CLEANUP", "True").lower() in ("true", "1", "t")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
