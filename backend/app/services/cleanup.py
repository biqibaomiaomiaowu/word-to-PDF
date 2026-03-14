import os
import shutil
import asyncio
from datetime import datetime, timezone
from ..core.logger import logger
from ..core.config import settings
from .task_manager import task_manager
from ..models.schemas import TaskStatus

async def run_cleanup_loop():
    """Periodically cleans up old tasks and their files."""
    if not settings.ENABLE_AUTO_CLEANUP:
        logger.info("Auto-cleanup is disabled.")
        return

    logger.info(f"Starting cleanup loop. Retention: {settings.FILE_RETENTION_SECONDS} seconds.")

    while True:
        try:
            # Run cleanup every N minutes (e.g., half the retention time, minimum 1 min)
            sleep_time = max(settings.FILE_RETENTION_SECONDS // 2, 60)
            await asyncio.sleep(sleep_time)

            now = datetime.now(timezone.utc)
            expired_tasks = []

            # Find expired tasks
            for task_id, task_info in list(task_manager.tasks.items()):
                # Only clean up completed or failed tasks
                if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    if task_info.completed_at:
                        age_seconds = (now - task_info.completed_at).total_seconds()
                        if age_seconds > settings.FILE_RETENTION_SECONDS:
                            expired_tasks.append(task_id)

            # Process cleanup
            for task_id in expired_tasks:
                task_info = task_manager.tasks.pop(task_id, None)
                if task_info:
                    # Clean up input file if it exists
                    if os.path.exists(task_info.input_filepath):
                        try:
                            os.remove(task_info.input_filepath)
                        except Exception as e:
                            logger.error(f"Cleanup error (input file {task_info.input_filepath}): {e}")

                    # Clean up output directory
                    if os.path.exists(task_info.output_dir):
                        try:
                            shutil.rmtree(task_info.output_dir)
                        except Exception as e:
                            logger.error(f"Cleanup error (output dir {task_info.output_dir}): {e}")

            if expired_tasks:
                logger.info(f"Cleaned up {len(expired_tasks)} expired tasks: {expired_tasks}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Unexpected error in cleanup loop: {e}")
