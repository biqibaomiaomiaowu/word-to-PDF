import asyncio
import uuid
import os
from typing import Dict, Optional
from datetime import datetime, timezone

from ..core.logger import logger
from ..core.config import settings
from .libreoffice import LibreOfficeService
from ..models.schemas import TaskStatus, TaskInfo

class TaskManager:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.tasks: Dict[str, TaskInfo] = {}
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)
        self.worker_task = None

    def start(self):
        """Starts the background worker task."""
        self.worker_task = asyncio.create_task(self._worker())
        logger.info(f"Task manager started with max concurrency: {settings.MAX_CONCURRENT_TASKS}")

    async def stop(self):
        """Stops the background worker task."""
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Task manager stopped.")

    async def enqueue_task(self, original_filename: str, input_filepath: str) -> str:
        """Enqueues a new conversion task and returns its task ID."""
        task_id = str(uuid.uuid4())

        # Create an isolated output directory for this task
        task_output_dir = os.path.join(settings.OUTPUT_DIR, task_id)
        os.makedirs(task_output_dir, exist_ok=True)

        task_info = TaskInfo(
            task_id=task_id,
            original_filename=original_filename,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            input_filepath=input_filepath,
            output_dir=task_output_dir
        )

        self.tasks[task_id] = task_info
        await self.queue.put(task_id)
        logger.info(f"Enqueued task {task_id} for file {original_filename}")
        return task_id

    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """Retrieves the status of a specific task."""
        return self.tasks.get(task_id)

    async def _worker(self):
        """Background worker that pulls tasks from the queue and processes them."""
        while True:
            try:
                task_id = await self.queue.get()
                logger.info(f"Worker picked up task {task_id}")

                # Use semaphore to limit concurrent LibreOffice processes
                async with self.semaphore:
                    await self._process_task(task_id)

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in task worker: {e}")

    async def _process_task(self, task_id: str):
        """Executes the actual conversion logic for a task."""
        task_info = self.tasks.get(task_id)
        if not task_info:
            logger.warning(f"Task {task_id} not found in memory during processing.")
            return

        task_info.status = TaskStatus.PROCESSING

        try:
            # Execute conversion
            output_pdf_path = await LibreOfficeService.convert_to_pdf(
                input_path=task_info.input_filepath,
                output_dir=task_info.output_dir
            )

            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now(timezone.utc)
            task_info.output_filepath = output_pdf_path

            # Optionally clean up the input file after successful conversion
            # We delete it to save space in temp_uploads
            try:
                os.remove(task_info.input_filepath)
            except Exception as e:
                logger.warning(f"Failed to remove input file {task_info.input_filepath}: {e}")

        except Exception as e:
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now(timezone.utc)
            task_info.error_message = str(e)
            logger.error(f"Task {task_id} failed: {e}")

# Global instance of task manager
task_manager = TaskManager()
