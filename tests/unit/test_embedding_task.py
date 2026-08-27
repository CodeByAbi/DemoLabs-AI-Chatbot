"""
Script to test publishing QnA embedding task to the embedding.qna queue

Usage:
    python scripts/test_embedding_task.py
"""
import json
import uuid
import os
import sys
from pathlib import Path
from kombu import Connection, Exchange, Producer

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings

# Azure RabbitMQ configuration from settings
RABBITMQ_URL = settings.CELERY_BROKER_URL

# Sample payload matching your specification
sample_payload = {
    "taskId": "embed_qna_002",
    "userId": "admin_user",
    "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
    "qna_pairs": [
        {
            "question": "What are your business hours?",
            "answer": "We are open Monday to Friday, 9 AM to 5 PM.",
            "metadata": {"category": "general"}
        },
        {
            "question": "How can I contact customer support?",
            "answer": "You can reach our customer support at support@example.com or call 1-800-SUPPORT.",
            "metadata": {"category": "support"}
        },
        {
            "question": "What payment methods do you accept?",
            "answer": "We accept credit cards (Visa, MasterCard, AmEx), PayPal, and bank transfers.",
            "metadata": {"category": "payment"}
        },
        {
            "question": "Do you offer international shipping?",
            "answer": "Yes, we ship to over 100 countries worldwide. Shipping costs vary by location.",
            "metadata": {"category": "shipping"}
        },
        {
            "question": "What is your return policy?",
            "answer": "We offer a 30-day return policy for most items. Items must be in original condition.",
            "metadata": {"category": "returns"}
        }
    ],
    "batch_size": 50,
    "type": "qna_embedding"
}


def publish_embedding_task(payload: dict):
    """
    Publish QnA embedding task to embedding.qna queue.
    
    Args:
        payload: Task payload
    """
    try:
        with Connection(RABBITMQ_URL) as conn:
            exchange = Exchange("demo_labs", type="topic", passive=True)
            
            # Create Celery task message format
            celery_task = {
                "task": "app.workers.embedding_tasks.process_qna_embedding",
                "id": str(uuid.uuid4()),
                "args": [payload],
                "kwargs": {},
                "retries": 0,
            }
            
            # Serialize to JSON
            body = json.dumps(celery_task).encode('utf-8')
            
            with conn.Producer(serializer='json') as producer:
                producer.publish(
                    body,
                    exchange=exchange,
                    routing_key="embedding.qna",
                    content_type="application/json",
                    content_encoding="utf-8",
                    delivery_mode=2,  # persistent
                )
            
            print(f"✅ Successfully published embedding task to queue 'embedding.qna'")
            print(f"📋 Task ID: {celery_task['id']}")
            print(f"📊 Payload: {json.dumps(payload, indent=2)}")
            return True
            
    except Exception as e:
        print(f"❌ Error publishing task: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("Testing QnA Embedding Task Publication")
    print("=" * 80)
    print()
    
    # Publish sample task
    success = publish_embedding_task(sample_payload)
    
    if success:
        print()
        print("=" * 80)
        print("✅ Task published successfully!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Check worker logs: docker logs demo-lab-chatbot-orchestrator-celery_worker_embedding-1 -f")
        print("2. Check database: SELECT * FROM bot.faq WHERE dataset_id = 'b993df02-5048-465a-8f69-e3bb00d507f3';")
        print("3. Monitor Flower: http://localhost:5555")
    else:
        print()
        print("=" * 80)
        print("❌ Task publication failed!")
        print("=" * 80)
