#!/usr/bin/env python
"""
Celery Worker Entry Point

Start the Celery worker to process tasks from the chat_incoming queue.

Usage:
    python -m app.workers.worker

Or with specific options:
    celery -A app.workers.celery_app worker --loglevel=info --queues=chat_incoming
"""
import logging
from app.workers.celery_app import celery_app
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Celery worker for chat_incoming queue...")
    logger.info(f"Broker: {settings.CELERY_BROKER_URL}")
    logger.info(f"Backend: {settings.CELERY_RESULT_BACKEND}")
    
    # Start worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--queues=chat_incoming',
        '--concurrency=4',
        '--max-tasks-per-child=1000',
    ])
