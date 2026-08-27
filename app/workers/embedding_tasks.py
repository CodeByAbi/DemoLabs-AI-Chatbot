"""
Embedding tasks for processing QnA pairs and generating embeddings

WORKER ARCHITECTURE:
====================
This worker listens to 'embedding.qna' queue and processes QnA embedding tasks.
It generates embeddings using Azure OpenAI and stores them in PostgreSQL.

FLOW:
1. Worker consumes message from 'embedding.qna' queue
2. Generates embeddings for questions using Azure OpenAI
3. Stores QnA pairs with embeddings in bot.faq table
4. Returns processing results

PAYLOAD FORMAT:
===============
{
    "taskId": "demo_qna_webhook_001",
    "userId": "Marsudi",
    "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
    "qna_pairs": [
        {
            "question": "Apa jam operasional?",
            "answer": "Kami buka Senin-Jumat, jam 9 pagi sampai 5 sore."
        },
        {
            "question": "Bagaimana cara menghubungi customer service?",
            "answer": "Anda bisa menghubungi kami via email support@demo.com atau telepon 021-12345678."
        }
    ],
    "type": "qna_embedding"
}
"""
import logging
from datetime import datetime
from typing import Dict, Any
import uuid
from sqlalchemy.exc import OperationalError

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models.faq import FAQ
from app.services.azure_openai import azure_openai_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.embedding_tasks.process_qna_embedding",
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_qna_embedding(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process QnA embedding task from the embedding.qna queue.
    
    WORKER RESPONSIBILITY:
    1. Listen to 'embedding.qna' queue
    2. Generate embeddings for questions using Azure OpenAI
    3. Store QnA pairs with embeddings in bot.faq table
    4. Return processing results
    
    Args:
        self: Task instance (bound)
        payload: Dictionary containing embedding task information
            - taskId: Task identifier
            - userId: User who initiated the task
            - datasetId: Dataset identifier
            - qna_pairs: List of question-answer pairs
            - batch_size: Number of items to process in each batch
            - type: Task type (qna_embedding)
    
    Returns:
        Dict containing processing result
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(f"[Task {task_id}] Processing QnA embedding task: {payload.get('taskId')}")
    
    db = SessionLocal()
    
    try:
        # Extract payload data
        user_name = payload.get("userName")  # Use userName instead of userId
        dataset_id = payload.get("datasetId")
        qna_pairs = payload.get("qna_pairs", [])
        batch_size = payload.get("batch_size", 50)
        
        # ============================================================
        # WEBHOOK: Update status to "On Progress" at task start
        # ============================================================
        from app.services.webhook_service import webhook_service
        
        logger.info(f"[Task {task_id}] Updating dataset status to 'On Progress'")
        webhook_service.update_dataset_status(
            dataset_id=dataset_id,
            status="On Progress"
        )
        
        if not dataset_id:
            raise ValueError("datasetId is required")
        
        if not qna_pairs:
            raise ValueError("qna_pairs list is empty")
        
        logger.info(
            f"[Task {task_id}] Processing {len(qna_pairs)} QnA pairs for dataset {dataset_id}"
        )
        
        # Convert dataset_id to UUID if it's a string
        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError as e:
            logger.error(f"[Task {task_id}] Invalid dataset_id format: {dataset_id}")
            raise ValueError(f"Invalid dataset_id format: {dataset_id}") from e
        
        # Process QnA pairs in batches
        total_processed = 0
        total_failed = 0
        failed_items = []
        
        for i in range(0, len(qna_pairs), batch_size):
            batch = qna_pairs[i:i + batch_size]
            logger.info(f"[Task {task_id}] Processing batch {i // batch_size + 1}, size: {len(batch)}")
            
            # Extract questions for batch embedding generation
            questions = [pair.get("question", "") for pair in batch]
            
            # Generate embeddings for all questions in batch
            embeddings = azure_openai_service.generate_embeddings_batch(questions)
            
            if embeddings is None:
                logger.error(f"[Task {task_id}] Failed to generate embeddings for batch")
                total_failed += len(batch)
                failed_items.extend([{"index": i + j, "reason": "Embedding generation failed"} for j in range(len(batch))])
                continue
            
            # Store each QnA pair with its embedding (upsert logic)
            for j, (pair, embedding) in enumerate(zip(batch, embeddings)):
                try:
                    question = pair.get("question", "")
                    answer = pair.get("answer", "")
                    if not question or not answer:
                        logger.warning(f"[Task {task_id}] Skipping pair {i + j}: missing question or answer")
                        total_failed += 1
                        failed_items.append({
                            "index": i + j,
                            "reason": "Missing question or answer"
                        })
                        continue

                    # Check if question already exists for this dataset (not deleted)
                    existing_faq = db.query(FAQ).filter(
                        FAQ.question == question,
                        FAQ.dataset_id == dataset_uuid,
                        FAQ.deleted_at.is_(None)
                    ).first()

                    if existing_faq:
                        # Update embedding and answer if changed
                        logger.info(f"[Task {task_id}] Updating existing FAQ entry for question: {question[:50]}...")
                        existing_faq.embedding = embedding
                        if existing_faq.answer != answer:
                            existing_faq.answer = answer
                        existing_faq.updated_by = user_name
                        total_processed += 1
                    else:
                        # Create new FAQ entry
                        faq_entry = FAQ(
                            question=question,
                            answer=answer,
                            dataset_id=dataset_uuid,
                            embedding=embedding,
                            created_by=user_name,
                            updated_by=user_name
                        )
                        db.add(faq_entry)
                        total_processed += 1
                        logger.info(
                            f"[Task {task_id}] Added FAQ entry {i + j + 1}/{len(qna_pairs)}: "
                            f"Q: {question[:50]}..."
                        )
                except Exception as e:
                    logger.error(
                        f"[Task {task_id}] Error processing QnA pair {i + j}: {str(e)}",
                        exc_info=True
                    )
                    total_failed += 1
                    failed_items.append({
                        "index": i + j,
                        "reason": str(e)
                    })
            
            # Commit batch to database
            try:
                db.commit()
                logger.info(f"[Task {task_id}] Committed batch {i // batch_size + 1} to database")
            except Exception as e:
                logger.error(f"[Task {task_id}] Error committing batch: {str(e)}", exc_info=True)
                db.rollback()
                raise
        
        # Calculate metrics
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result = {
            "task_id": task_id,
            "user_task_id": payload.get("taskId"),
            "status": "success" if total_failed == 0 else "partial_success",
            "dataset_id": dataset_id,
            "total_items": len(qna_pairs),
            "processed": total_processed,
            "failed": total_failed,
            "failed_items": failed_items if failed_items else None,
            "processing_time_ms": processing_time_ms,
            "timestamp": end_time.isoformat() + "Z"
        }
        
        logger.info(
            f"[Task {task_id}] Successfully processed {total_processed}/{len(qna_pairs)} QnA pairs "
            f"in {processing_time_ms}ms"
        )
        
        # ============================================================
        # WEBHOOK: Update status to "Completed" after successful processing
        # ============================================================
        logger.info(f"[Task {task_id}] Calling webhook to update dataset status to 'Completed'")
        
        webhook_result = webhook_service.update_dataset_status(
            dataset_id=dataset_id,
            status="Completed"
        )
        
        if webhook_result.get("success"):
            logger.info(
                f"[Task {task_id}] ✓ Webhook call successful for dataset {dataset_id} "
                f"(status: {webhook_result.get('status_code')}, "
                f"duration: {webhook_result.get('duration_ms', 0):.2f}ms)"
            )
        else:
            logger.error(
                f"[Task {task_id}] ✗ Webhook call failed for dataset {dataset_id}. "
                f"Error: {webhook_result.get('error')} - {webhook_result.get('message')}"
            )
        
        # Add webhook result to response
        result["webhook"] = webhook_result
        
        return result
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error processing QnA embedding task: {str(e)}", exc_info=True)
        db.rollback()
        
        # ============================================================
        # WEBHOOK: Update status to "Failed" on error
        # ============================================================
        try:
            logger.info(f"[Task {task_id}] Updating dataset status to 'Failed' due to error")
            webhook_service.update_dataset_status(
                dataset_id=payload.get("datasetId"),
                status="Failed"
            )
        except Exception as webhook_error:
            logger.error(f"[Task {task_id}] Failed to send failure webhook: {str(webhook_error)}")
        
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=60, max_retries=3)
        
    finally:
        db.close()


@celery_app.task(name="app.workers.embedding_tasks.health_check_embedding")
def health_check_embedding() -> Dict[str, str]:
    """
    Simple health check task for testing embedding worker connectivity.
    
    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "embedding_qna_worker"
    }


@celery_app.task(name="app.workers.embedding_tasks.test_azure_openai_connection")
def test_azure_openai_connection() -> Dict[str, Any]:
    """
    Test Azure OpenAI connection and embedding generation.
    
    Returns:
        Dict with connection test results
    """
    try:
        test_text = "This is a test message for embedding generation."
        embedding = azure_openai_service.generate_embedding(test_text)
        
        if embedding:
            return {
                "status": "success",
                "message": "Azure OpenAI connection successful",
                "embedding_dimension": len(embedding),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "failed",
                "message": "Failed to generate embedding",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error testing Azure OpenAI connection: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
