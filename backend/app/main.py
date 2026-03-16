import asyncio
import os
import sys
from contextlib import asynccontextmanager

# On Windows, the default event loop policy (SelectorEventLoop) does not
# support subprocesses. We must use ProactorEventLoop to run asyncio.create_subprocess_exec.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.exceptions import ConversionError, conversion_error_handler, global_exception_handler
from .api import routes
from .services.task_manager import task_manager
from .services.cleanup import run_cleanup_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    # Pre-check Paddle availability on startup
    from .utils.paddle_runtime import get_paddle_capabilities
    import threading
    import asyncio
    # Run it in a thread to not block the main event loop startup for 8s
    def pre_check():
        try:
            get_paddle_capabilities(use_cache=False)
        except Exception:
            pass
    threading.Thread(target=pre_check, daemon=True).start()

    # Start background tasks
    task_manager.start()
    cleanup_task = asyncio.create_task(run_cleanup_loop())

    yield

    # Shutdown logic
    await task_manager.stop()
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, configure this via settings
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(ConversionError, conversion_error_handler)
app.add_exception_handler(Exception, global_exception_handler)

# Routers
app.include_router(routes.router, prefix=settings.API_V1_STR)

from .api import capabilities
app.include_router(capabilities.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
