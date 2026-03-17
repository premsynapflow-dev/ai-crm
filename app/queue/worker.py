import threading
import time

from app.queue.simple_queue import process_jobs
from app.utils.logging import get_logger

logger = get_logger(__name__)
_stop_event = threading.Event()


def worker_loop(interval_seconds=30):
    logger.info("Simple queue worker started")
    while not _stop_event.is_set():
        try:
            processed = process_jobs()
            if processed:
                logger.info("Processed %s queued jobs", processed)
        except Exception as exc:
            logger.exception("Queue worker error: %s", exc)
        _stop_event.wait(interval_seconds)


def start_worker_thread(interval_seconds=30):
    thread = threading.Thread(target=worker_loop, args=(interval_seconds,), daemon=True, name="simple-queue-worker")
    thread.start()
    return thread


def stop_worker():
    _stop_event.set()
