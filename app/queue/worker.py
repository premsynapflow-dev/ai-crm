import threading
import time

from app.queue.simple_queue import process_jobs
from app.utils.logging import get_logger

logger = get_logger(__name__)
_stop_event = threading.Event()
_worker_thread = None


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
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return _worker_thread
    _worker_thread = threading.Thread(target=worker_loop, args=(interval_seconds,), daemon=True, name="simple-queue-worker")
    _worker_thread.start()
    return _worker_thread


def is_worker_alive():
    return bool(_worker_thread and _worker_thread.is_alive() and not _stop_event.is_set())


def stop_worker():
    _stop_event.set()
