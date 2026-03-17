#!/usr/bin/env python3
"""
Standalone worker process for background job processing

Usage:
  python worker_standalone.py

Environment variables:
  - All the same as main app (DATABASE_URL, etc.)
  - WORKER_INTERVAL: seconds between polling (default: 10)
"""

import os
import sys
import signal
from app.queue.worker import worker_loop
from app.utils.logging import configure_logging, get_logger
from app.config import get_settings

configure_logging()
logger = get_logger(__name__)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down worker...")
    sys.exit(0)


def main():
    """Run worker process"""
    try:
        settings = get_settings()
        logger.info("Starting standalone worker process")
        logger.info(f"Environment: {settings.environment}")
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Get worker interval from env
        interval = int(os.getenv("WORKER_INTERVAL", "10"))
        logger.info(f"Worker polling interval: {interval}s")
        
        # Run worker loop
        worker_loop(interval_seconds=interval)
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.exception(f"Worker crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
