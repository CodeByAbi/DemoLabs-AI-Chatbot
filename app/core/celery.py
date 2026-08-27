"""
Celery application configuration
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "demo_lab_chatbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # In development, allow automatic creation of queues
    # In production, disable to avoid conflicts with existing Azure RabbitMQ setup
    task_create_missing_queues=(settings.ENVIRONMENT == "development"),
)

# Define exchanges and queues
# In development mode, create exchanges and queues dynamically
# In production mode, use existing exchanges and queues (passive mode)
is_production = settings.ENVIRONMENT == "production"

default_exchange = Exchange("default", type="direct", passive=is_production)
chat_exchange = Exchange("demo_labs", type="topic", passive=is_production)

# Configure task queues
# Match existing Azure RabbitMQ queue configuration exactly
# In development, queues are auto-declared. In production, they must exist.
celery_app.conf.task_queues = (
    Queue(
        "chat_incoming",
        exchange=chat_exchange,
        routing_key="chat.incoming",
        passive=is_production,
        auto_declare=not is_production,
        queue_arguments={
            "x-dead-letter-exchange": "demo_labs",
            "x-dead-letter-routing-key": "chat.dlx",
            "x-message-ttl": 60000,
        } if is_production else {},
    ),
    Queue(
        "chat_outgoing",
        exchange=chat_exchange,
        routing_key="chat.outgoing",
        passive=is_production,
        auto_declare=not is_production,
        queue_arguments={},
    ),
    Queue(
        "embedding.qna",
        exchange=chat_exchange,
        routing_key="embedding.qna",
        passive=is_production,
        auto_declare=not is_production,
    ),
    Queue(
        "embedding.pdf",
        exchange=chat_exchange,
        routing_key="embedding.pdf",
        passive=is_production,
        auto_declare=not is_production,
    ),
    Queue(
        "embedding.text_to_sql",
        exchange=chat_exchange,
        routing_key="embedding.text_to_sql",
        passive=is_production,
        auto_declare=not is_production,
    ),
    Queue(
        "default",
        exchange=default_exchange,
        routing_key="default",
        passive=is_production,
        auto_declare=not is_production,
    ),
)

# Default queue configuration
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"
celery_app.conf.task_default_auto_declare = not is_production

# Task routes - route specific tasks to specific queues
celery_app.conf.task_routes = {
    "app.workers.chat_tasks.*": {"queue": "chat_incoming"},
    "app.workers.embedding_tasks.*": {"queue": "embedding.qna"},
    "app.workers.pdf_embedding_tasks.*": {"queue": "embedding.pdf"},
    "app.workers.text_to_sql_embedding_tasks.*": {"queue": "embedding.text_to_sql"},
}

# Import tasks explicitly to ensure they are registered
from app.workers import chat_tasks  # noqa
from app.workers import embedding_tasks  # noqa
from app.workers import pdf_embedding_tasks  # noqa

# Auto-discover tasks from workers module
celery_app.autodiscover_tasks(["app.workers"])
