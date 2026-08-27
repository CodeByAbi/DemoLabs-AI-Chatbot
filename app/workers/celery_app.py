"""
Celery application entry point for workers
Ensures all tasks are properly imported and registered
"""
from app.core.celery import celery_app

# Import all task modules to register them
from app.workers import chat_tasks  # noqa: F401
from app.workers import embedding_tasks  # noqa: F401
from app.workers import pdf_embedding_tasks  # noqa: F401
from app.workers import text_to_sql_embedding_tasks  # noqa: F401

__all__ = ["celery_app"]
