"""
Text-to-SQL Embedding Worker

WORKER ARCHITECTURE:
====================
This worker listens to 'embedding.text_to_sql' queue and processes text-to-SQL examples
by generating embeddings for questions and table descriptions. These embeddings enable
RAG-based few-shot learning for SQL query generation.

FLOW:
1. Worker consumes message from 'embedding.text_to_sql' queue
2. Generates embeddings for question + description (stored in text_to_sql table)
3. Generates embeddings for table descriptions (stored in table table)
4. Links text_to_sql entries with tables via text_to_sql_tables junction table
5. Returns processing results

PAYLOAD FORMAT:
===============
{
    "taskId": "demo_text2sql_webhook_001",
    "userId": "Marsudi",
    "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
    "examples": [
        {
            "question": "Berapa total user yang terdaftar bulan lalu?",
            "sql_query": "SELECT COUNT(*) FROM users WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
            "description": "Hitung jumlah user yang terdaftar pada bulan sebelumnya",
            "tables": [
                {
                    "name": "users",
                    "description": "Tabel akun user dengan timestamp registrasi"
                }
            ]
        }
    ],
    "type": "text_to_sql"
}
"""
import logging
from datetime import datetime
from typing import Dict, Any
import uuid
from sqlalchemy.exc import OperationalError

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models.text_to_sql import Table, TextToSql, TextToSqlTables
from app.models.dataset import Dataset
from app.services.azure_openai import azure_openai_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.text_to_sql_embedding_tasks.process_text_to_sql_embedding",
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_text_to_sql_embedding(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process text-to-SQL embedding task from the embedding.text_to_sql queue.
    
    WORKER RESPONSIBILITY:
    1. Listen to 'embedding.text_to_sql' queue
    2. Generate embeddings for question + description
    3. Generate embeddings for table descriptions
    4. Store in bot.text_to_sql and bot.table tables
    5. Create relationships in bot.text_to_sql_tables
    6. Return processing results
    
    Args:
        self: Task instance (bound)
        payload: Dictionary containing text-to-SQL embedding task information
            - taskId: Task identifier
            - userId: User who initiated the task
            - datasetId: Dataset identifier
            - examples: List of question-SQL pairs with table info
            - type: Task type (text_to_sql)
    
    Returns:
        Dict containing processing result
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(f"[Task {task_id}] Processing text-to-SQL embedding task: {payload.get('taskId')}")
    
    db = SessionLocal()
    
    try:
        # Extract payload data
        user_name = payload.get("userName")  # Use userName instead of userId
        dataset_id = payload.get("datasetId")
        examples = payload.get("examples", [])
        
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
        
        if not examples:
            raise ValueError("examples list is empty")
        
        # Convert dataset_id to UUID
        try:
            dataset_uuid = uuid.UUID(dataset_id)
        except ValueError as e:
            logger.error(f"[Task {task_id}] Invalid dataset_id format: {dataset_id}")
            raise ValueError(f"Invalid dataset_id format: {dataset_id}") from e
        
        # Validate dataset exists in master.dataset table
        try:
            dataset_check = db.query(Dataset).filter(
                Dataset.id == dataset_uuid,
                Dataset.deleted_at.is_(None)
            ).first()
            
            if not dataset_check:
                error_msg = (
                    f"Dataset '{dataset_id}' not found in master.dataset table. "
                    f"Please create the dataset before uploading text-to-SQL examples."
                )
                logger.error(f"[Task {task_id}] {error_msg}")
                raise ValueError(error_msg)
            
            logger.info(f"[Task {task_id}] Dataset '{dataset_id}' validated successfully")
            
        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Error validating dataset: {str(e)}"
            logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e
        
        logger.info(
            f"[Task {task_id}] Processing {len(examples)} text-to-SQL examples for dataset {dataset_id}"
        )
        
        # Process each example
        total_examples = 0
        total_tables = 0
        total_failed = 0
        failed_items = []
        example_results = []
        
        for example_index, example_data in enumerate(examples):
            try:
                result = _process_single_example(
                    db=db,
                    task_id=task_id,
                    example_index=example_index,
                    example_data=example_data,
                    dataset_uuid=dataset_uuid,
                    user_name=user_name
                )
                
                total_examples += 1
                total_tables += result["tables_processed"]
                example_results.append(result)
                
                logger.info(
                    f"[Task {task_id}] Example {example_index + 1}/{len(examples)} completed: "
                    f"{result['tables_processed']} tables processed"
                )
                
            except Exception as e:
                logger.error(
                    f"[Task {task_id}] Error processing example {example_index}: {str(e)}",
                    exc_info=True
                )
                total_failed += 1
                failed_items.append({
                    "index": example_index,
                    "question": example_data.get("question", "unknown")[:100],
                    "reason": str(e)
                })
        
        # Calculate metrics
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result = {
            "task_id": task_id,
            "user_task_id": payload.get("taskId"),
            "status": "success" if total_failed == 0 else "partial_success",
            "dataset_id": dataset_id,
            "total_examples": len(examples),
            "examples_processed": total_examples,
            "examples_failed": total_failed,
            "total_tables_processed": total_tables,
            "failed_items": failed_items if failed_items else None,
            "example_results": example_results,
            "processing_time_ms": processing_time_ms,
            "timestamp": end_time.isoformat() + "Z"
        }
        
        logger.info(
            f"[Task {task_id}] Successfully processed {total_examples}/{len(examples)} examples "
            f"with {total_tables} tables in {processing_time_ms}ms"
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
        logger.error(f"[Task {task_id}] Error processing text-to-SQL embedding task: {str(e)}", exc_info=True)
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


def _process_single_example(
    db,
    task_id: str,
    example_index: int,
    example_data: Dict[str, Any],
    dataset_uuid: uuid.UUID,
    user_name: str
) -> Dict[str, Any]:
    """
    Process a single text-to-SQL example.
    
    Args:
        db: Database session
        task_id: Task identifier
        example_index: Index of example in batch
        example_data: Example data containing question, SQL, and tables
        dataset_uuid: Dataset UUID
        user_name: User name who created the task
    
    Returns:
        Dict containing processing result
    """
    question = example_data.get("question")
    sql_query = example_data.get("sql_query")
    description = example_data.get("description", "")
    tables_data = example_data.get("tables", [])
    
    if not question:
        raise ValueError("question is required")
    
    if not sql_query:
        raise ValueError("sql_query is required")
    
    logger.info(
        f"[Task {task_id}] Processing example {example_index + 1}: {question[:100]}"
    )
    
    # Step 1: Generate embedding for question + description
    embedding_text = f"{question}\n{description}" if description else question
    
    logger.info(f"[Task {task_id}] Generating embedding for question")
    question_embedding = azure_openai_service.generate_embedding(embedding_text)
    
    if not question_embedding:
        raise ValueError("Failed to generate embedding for question")
    
    logger.info(
        f"[Task {task_id}] Generated embedding for question: {len(question_embedding)} dimensions"
    )
    
    # Step 2: Upsert text_to_sql entry (update if question exists, else insert)
    existing_text_to_sql = db.query(TextToSql).filter(
        TextToSql.question == question,
        TextToSql.dataset_id == dataset_uuid,
        TextToSql.deleted_at.is_(None)
    ).first()

    if existing_text_to_sql:
        logger.info(f"[Task {task_id}] Updating existing TextToSql entry for question: {question[:50]}")
        existing_text_to_sql.embedding = question_embedding
        if existing_text_to_sql.sql_query != sql_query:
            existing_text_to_sql.sql_query = sql_query
        if existing_text_to_sql.description != description:
            existing_text_to_sql.description = description
        existing_text_to_sql.updated_by = user_name
        text_to_sql = existing_text_to_sql
    else:
        text_to_sql = TextToSql(
            id=uuid.uuid4(),
            question=question,
            sql_query=sql_query,
            description=description,
            dataset_id=dataset_uuid,
            embedding=question_embedding,
            created_by=user_name,
            updated_by=user_name
        )
        db.add(text_to_sql)
        db.flush()  # Get the ID for relationships
        logger.info(f"[Task {task_id}] Created text_to_sql entry: {text_to_sql.id}")
    
    # Step 3: Process tables and create relationships
    tables_processed = 0
    table_ids = []
    
    for table_data in tables_data:
        table_name = table_data.get("name")
        table_description = table_data.get("description", "")
        
        if not table_name:
            logger.warning(f"[Task {task_id}] Skipping table without name")
            continue
        
        # Check if table already exists
        existing_table = db.query(Table).filter(
            Table.name == table_name,
            Table.deleted_at.is_(None)
        ).first()
        
        if existing_table:
            logger.info(f"[Task {task_id}] Using existing table: {table_name}")
            table_id = existing_table.id
            
            # Update embedding if description changed
            if table_description and table_description != existing_table.description:
                logger.info(f"[Task {task_id}] Updating table description and embedding")
                table_embedding = azure_openai_service.generate_embedding(table_description)
                existing_table.description = table_description
                existing_table.embedding = table_embedding
                existing_table.updated_by = user_name
                
        else:
            # Create new table entry
            logger.info(f"[Task {task_id}] Creating new table: {table_name}")
            
            # Generate embedding for table description
            table_embedding = None
            if table_description:
                table_embedding = azure_openai_service.generate_embedding(table_description)
            
            new_table = Table(
                id=uuid.uuid4(),
                name=table_name,
                description=table_description,
                embedding=table_embedding,
                created_by=user_name,
                updated_by=user_name
            )
            
            db.add(new_table)
            db.flush()
            table_id = new_table.id
        
        # Create relationship in text_to_sql_tables
        relationship_entry = TextToSqlTables(
            table_id=table_id,
            text_to_sql_id=text_to_sql.id,
            created_by=user_name,
            updated_by=user_name
        )
        
        db.add(relationship_entry)
        table_ids.append(table_id)
        tables_processed += 1
    
    # Commit all changes
    db.commit()
    
    logger.info(
        f"[Task {task_id}] Successfully processed example: "
        f"question_id={text_to_sql.id}, tables={tables_processed}"
    )
    
    return {
        "text_to_sql_id": str(text_to_sql.id),
        "question": question[:100],
        "tables_processed": tables_processed,
        "table_ids": [str(tid) for tid in table_ids],
        "embedding_dimensions": len(question_embedding)
    }
