from fastapi import Request, status
from fastapi.responses import JSONResponse
from .logger import logger

class ConversionError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

async def conversion_error_handler(request: Request, exc: ConversionError):
    logger.error(f"ConversionError: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_type": "ConversionError"},
    )

async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please try again later.", "error_type": "InternalError"},
    )
