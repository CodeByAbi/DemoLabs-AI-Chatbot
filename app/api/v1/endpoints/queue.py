"""
API endpoints for queue management and monitoring

ARCHITECTURE NOTES:
===================
This is a WORKER ORCHESTRATOR service that manages Celery task queues.

FLOW:
1. Backend (BE) submits tasks to this API endpoint (/api/v1/queue/submit)
2. This API queues the task to 'chat_incoming' queue (RabbitMQ)
3. Celery workers listen to 'chat_incoming' queue and process tasks
4. After processing, workers publish results to 'chat_outgoing' queue
5. Backend (BE) consumes results from 'chat_outgoing' queue

IMPORTANT:
- These API endpoints are for BE to SUBMIT tasks and MONITOR queues
- The actual message processing happens in Celery workers
- Workers automatically publish results to 'chat_outgoing' queue
- BE should implement a consumer to listen to 'chat_outgoing' queue
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends
from pydantic import BaseModel, Field

from app.workers.queue_manager import queue_manager
from app.workers.chat_tasks import process_incoming_message, health_check
from app.workers.embedding_tasks import process_qna_embedding, health_check_embedding
from app.workers.pdf_embedding_tasks import process_pdf_embedding, health_check_pdf_embedding
from app.workers.text_to_sql_embedding_tasks import process_text_to_sql_embedding
from app.core.security import get_api_key

router = APIRouter()


class MessageData(BaseModel):
    """
    Schema for incoming message data.
    
    NOTE: This schema is used by Backend (BE) to SUBMIT tasks to the worker.
    The worker will process this and publish results to 'chat_outgoing' queue.
    BE should not remove this schema - it's the contract for task submission.
    
    Required fields for chat_outgoing standardization:
    - session_id: Chat session identifier
    - user_id: User identifier
    - conversation_id: Conversation identifier
    - dataset_id: Dataset/knowledge base identifier
    - persona_id: Bot persona/agent identifier
    """
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., description="Message text")
    session_id: str = Field(..., description="Chat session identifier")
    conversation_id: str = Field(..., description="Conversation identifier")
    persona_id: str = Field(..., description="Bot persona/agent identifier")
    dataset_id: str = Field(..., description="Dataset/knowledge base identifier")
    timestamp: Optional[str] = Field(None, description="Message timestamp (ISO 8601)")
    timezone: Optional[str] = Field(default="UTC", description="User timezone")
    locale: Optional[str] = Field(default="en_US", description="User locale")
    channel: Optional[str] = Field(default="web", description="Communication channel")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class QnAPair(BaseModel):
    """Schema for a single QnA pair."""
    question: str = Field(..., description="Question text")
    answer: str = Field(..., description="Answer text")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class QnAEmbeddingData(BaseModel):
    """
    Schema for QnA embedding task data.
    
    This schema is used to submit QnA pairs for embedding generation.
    The worker will process these pairs and store them with embeddings in the database.
    """
    taskId: str = Field(..., description="Task identifier")
    userName: str = Field(..., description="User name who initiated the task (for audit fields)")
    datasetId: str = Field(..., description="Dataset/knowledge base identifier")
    qna_pairs: List[QnAPair] = Field(..., description="List of question-answer pairs to process")
    batch_size: Optional[int] = Field(default=50, description="Number of items to process in each batch")
    type: str = Field(default="qna_embedding", description="Task type")


class PDFDocument(BaseModel):
    """Schema for a single PDF document."""
    title: str = Field(..., description="Document title")
    file_name: str = Field(..., description="PDF file name")
    file_url: str = Field(..., description="URL or path to the PDF file")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class ChunkingConfig(BaseModel):
    """Schema for chunking configuration."""
    strategy: str = Field(default="recursive", description="Chunking strategy: recursive, fixed, page")
    chunk_size: int = Field(default=1000, description="Size of each chunk in characters")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks in characters")


class PDFEmbeddingData(BaseModel):
    """
    Schema for PDF embedding task data.
    
    This schema is used to submit PDF documents for text extraction, chunking, and embedding generation.
    The worker will process PDFs and store chunks with embeddings in the database.
    Dataset will be auto-created in master.dataset if not exists.
    """
    taskId: str = Field(..., description="Task identifier")
    userName: str = Field(..., description="User name who initiated the task (for audit fields)")
    datasetId: str = Field(..., description="Dataset/knowledge base identifier (UUID)")
    datasetName: Optional[str] = Field(None, description="Dataset name (auto-generated if not provided)")
    datasetDescription: Optional[str] = Field(None, description="Dataset description")
    documents: List[PDFDocument] = Field(..., description="List of PDF documents to process")
    chunking_config: Optional[ChunkingConfig] = Field(default_factory=ChunkingConfig, description="Chunking configuration")
    type: str = Field(default="pdf", description="Task type")


class TableSchema(BaseModel):
    """Schema for a database table."""
    name: str = Field(..., description="Table name")
    description: str = Field(..., description="Table description")


class Text2SQLExample(BaseModel):
    """Schema for a single text-to-SQL example."""
    question: str = Field(..., description="Natural language question")
    sql_query: str = Field(..., description="Corresponding SQL query")
    description: str = Field(..., description="Description of what the query does")
    tables: List[TableSchema] = Field(..., description="List of tables used in the query")


class Text2SQLEmbeddingData(BaseModel):
    """
    Schema for Text-to-SQL embedding task data.
    
    This schema is used to submit text-to-SQL examples for embedding generation.
    The worker will process examples and store them with embeddings in the database.
    """
    taskId: str = Field(..., description="Task identifier")
    userName: str = Field(..., description="User name who initiated the task (for audit fields)")
    datasetId: str = Field(..., description="Dataset/knowledge base identifier (UUID)")
    examples: List[Text2SQLExample] = Field(..., description="List of text-to-SQL examples to process")
    type: str = Field(default="text_to_sql", description="Task type")


class TaskResponse(BaseModel):
    """Schema for task submission response."""
    task_id: str
    status: str
    queue: str
    message: str


@router.post("/submit", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_message_to_queue(
    message_data: MessageData,
    api_key: str = Depends(get_api_key)
):
    """
    Submit a message to the chat_incoming queue for processing.
    
    NOTE FOR BACKEND (BE):
    - Use this endpoint to submit tasks to the worker
    - Worker will process the message and publish results to 'chat_outgoing' queue
    - BE should consume from 'chat_outgoing' queue to get processing results
    - This is an async operation - you'll get a task_id immediately
    - Use GET /task/{task_id} to check status, or consume 'chat_outgoing' queue
    
    Args:
        message_data: Message data to process
        
    Returns:
        Task submission confirmation with task_id
    """
    try:
        # Submit task to chat_incoming queue
        task = process_incoming_message.apply_async(
            args=[message_data.model_dump()],
            queue="chat_incoming"
        )
        
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue="chat_incoming",
            message="Message successfully queued for processing"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting message to queue: {str(e)}"
        )


@router.post("/submit/qna-embedding", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_qna_embedding_to_queue(
    embedding_data: QnAEmbeddingData,
    api_key: str = Depends(get_api_key)
):
    """
    Submit QnA pairs to the embedding.qna queue for processing.
    
    This endpoint allows you to submit question-answer pairs for embedding generation.
    The worker will:
    1. Generate embeddings for questions using Azure OpenAI
    2. Store QnA pairs with embeddings in the bot.faq table
    3. Return processing results
    
    Args:
        embedding_data: QnA embedding task data containing pairs to process
        
    Returns:
        Task submission confirmation with task_id
        
    Example payload:
    ```json
    {
        "taskId": "embed_qna_001",
        "userName": "John Doe",
        "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
        "qna_pairs": [
            {
                "question": "What are your business hours?",
                "answer": "We are open Monday to Friday, 9 AM to 5 PM.",
                "metadata": {"category": "general"}
            },
            {
                "question": "How do I contact support?",
                "answer": "You can reach support at support@company.com or call 1-800-SUPPORT.",
                "metadata": {"category": "support"}
            }
        ],
        "batch_size": 50,
        "type": "qna_embedding"
    }
    ```
    """
    try:
        # Validate required fields
        if not embedding_data.qna_pairs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="qna_pairs list cannot be empty"
            )
        
        # Validate each QnA pair
        for i, pair in enumerate(embedding_data.qna_pairs):
            if not pair.question.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Question at index {i} cannot be empty"
                )
            if not pair.answer.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Answer at index {i} cannot be empty"
                )
        
        # Submit task to embedding.qna queue
        task = process_qna_embedding.apply_async(
            args=[embedding_data.model_dump()],
            queue="embedding.qna"
        )
        
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue="embedding.qna",
            message=f"QnA embedding task successfully queued for processing ({len(embedding_data.qna_pairs)} pairs)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting QnA embedding task to queue: {str(e)}"
        )


@router.post("/submit/pdf-embedding", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_pdf_embedding_to_queue(
    embedding_data: PDFEmbeddingData,
    api_key: str = Depends(get_api_key)
):
    """
    Submit PDF documents to the embedding.pdf queue for processing.
    
    This endpoint allows you to submit PDF documents for text extraction, chunking, and embedding generation.
    The worker will:
    1. Auto-create dataset in master.dataset with status 'Processing' (if not exists)
    2. Download/access PDF from the provided URL
    3. Extract text and metadata from the PDF
    4. Create intelligent chunks using the specified strategy
    5. Generate embeddings for each chunk using Azure OpenAI
    6. Store document and chunks with embeddings in the database
    7. Call webhook to notify external system
    8. Update dataset status to 'Completed' in database
    
    Args:
        embedding_data: PDF embedding task data containing documents to process
        
    Returns:
        Task submission confirmation with task_id
        
    Example payload:
    ```json
    {
        "taskId": "embed_pdf_001",
        "userName": "John Doe",
        "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
        "datasetName": "Product Manual Dataset",
        "datasetDescription": "Technical documentation embeddings",
        "documents": [
            {
                "title": "Product Manual v2.0",
                "file_name": "manual.pdf",
                "file_url": "https://storage.blob.core.windows.net/demo-lab/docs/manual.pdf",
                "metadata": {"category": "technical", "language": "en"}
            }
        ],
        "chunking_config": {
            "strategy": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200
        },
        "type": "pdf"
    }
    ```
    
    Chunking Strategies:
    - recursive: Hierarchical splitting by paragraphs, sentences, words (default)
    - fixed: Fixed-size chunks with specified overlap
    - page: One chunk per page
    """
    from app.db.session import SessionLocal
    from sqlalchemy import text
    import uuid
    
    try:
        # Validate required fields
        if not embedding_data.documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="documents list cannot be empty"
            )
        
        # Auto-create dataset in master.dataset if not exists
        db = SessionLocal()
        try:
            dataset_id = embedding_data.datasetId
            dataset_uuid = uuid.UUID(dataset_id)
            
            # Check if dataset exists
            existing_dataset = db.execute(
                text("SELECT id FROM master.dataset WHERE id = :dataset_id AND deleted_at IS NULL"),
                {"dataset_id": str(dataset_uuid)}
            ).fetchone()
            
            if not existing_dataset:
                # Auto-create dataset with status 'Processing'
                dataset_name = getattr(embedding_data, 'datasetName', f"PDF Dataset {dataset_id[:8]}")
                dataset_description = getattr(embedding_data, 'datasetDescription', f"Auto-created for PDF embedding task {embedding_data.taskId}")
                
                db.execute(
                    text("""
                        INSERT INTO master.dataset 
                        (id, name, type, status, description, created_by, updated_by, created_at, updated_at)
                        VALUES 
                        (:id, :name, :type, :status, :description, :created_by, :updated_by, NOW(), NOW())
                    """),
                    {
                        "id": str(dataset_uuid),
                        "name": dataset_name,
                        "type": "pdf",
                        "status": "Processing",
                        "description": dataset_description,
                        "created_by": embedding_data.userName or "system",
                        "updated_by": embedding_data.userName or "system"
                    }
                )
                db.commit()
                print(f"[API] Auto-created dataset {dataset_id} with status 'Processing'")
            else:
                print(f"[API] Dataset {dataset_id} already exists, skipping creation")
                
        except Exception as db_error:
            print(f"[API] Error creating dataset: {str(db_error)}")
            db.rollback()
            # Don't fail the request, worker will validate dataset anyway
        finally:
            db.close()
        
        # Validate each document
        for i, doc in enumerate(embedding_data.documents):
            if not doc.title.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document title at index {i} cannot be empty"
                )
            if not doc.file_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document file_name at index {i} cannot be empty"
                )
            if not doc.file_url.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document file_url at index {i} cannot be empty"
                )
        
        # Validate chunking strategy
        valid_strategies = ["recursive", "fixed", "page"]
        if embedding_data.chunking_config.strategy not in valid_strategies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid chunking strategy. Must be one of: {', '.join(valid_strategies)}"
            )
        
        # Submit task to embedding.pdf queue
        task = process_pdf_embedding.apply_async(
            args=[embedding_data.model_dump()],
            queue="embedding.pdf"
        )
        
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue="embedding.pdf",
            message=f"PDF embedding task successfully queued for processing ({len(embedding_data.documents)} document(s))"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting PDF embedding task to queue: {str(e)}"
        )


@router.post("/submit/text-to-sql-embedding", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def submit_text_to_sql_embedding_to_queue(
    embedding_data: Text2SQLEmbeddingData,
    api_key: str = Depends(get_api_key)
):
    """
    Submit text-to-SQL examples to the embedding.text_to_sql queue for processing.
    
    This endpoint allows you to submit text-to-SQL examples for embedding generation.
    The worker will:
    1. Generate embeddings for question + description
    2. Generate embeddings for table descriptions
    3. Store in bot.text_to_sql and bot.table tables
    4. Create relationships in bot.text_to_sql_tables
    5. Call webhook to notify external system
    6. Update dataset status to 'Completed' in database
    
    Args:
        embedding_data: Text-to-SQL embedding task data containing examples to process
        
    Returns:
        Task submission confirmation with task_id
        
    Example payload:
    ```json
    {
        "taskId": "demo_text2sql_webhook_001",
        "userName": "John Doe",
        "datasetId": "f1a8c3d7-9e4b-4f2a-8d5c-1b7e9f3a6c2d",
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
    ```
    """
    try:
        # Validate required fields
        if not embedding_data.examples:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="examples list cannot be empty"
            )
        
        # Submit task to embedding.text_to_sql queue
        task = process_text_to_sql_embedding.apply_async(
            args=[embedding_data.model_dump()],
            queue="embedding.text_to_sql"
        )
        
        return TaskResponse(
            task_id=task.id,
            status="submitted",
            queue="embedding.text_to_sql",
            message=f"Text-to-SQL embedding task successfully queued for processing ({len(embedding_data.examples)} example(s))"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting text-to-SQL embedding task to queue: {str(e)}"
        )


@router.get("/list")
async def list_queue_tasks(
    queue_name: str = Query("chat_incoming", description="Queue name to inspect"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    List all tasks currently in the specified queue.
    
    Args:
        queue_name: Name of the queue to inspect
        
    Returns:
        Dictionary containing task list and statistics
    """
    try:
        tasks = queue_manager.list_tasks_in_queue(queue_name)
        queue_length = queue_manager.get_queue_length(queue_name)
        
        return {
            "queue_name": queue_name,
            "total_tasks": len(tasks),
            "queue_length": queue_length,
            "tasks": tasks
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing queue tasks: {str(e)}"
        )


@router.get("/stats")
async def get_queue_statistics(
    queue_name: str = Query("chat_incoming", description="Queue name to inspect"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get comprehensive statistics for the specified queue.
    
    Args:
        queue_name: Name of the queue to inspect
        
    Returns:
        Queue statistics including message counts and worker information
    """
    try:
        stats = queue_manager.get_queue_stats(queue_name)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting queue statistics: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Get the status and result of a specific task.
    
    Args:
        task_id: Task ID to retrieve
        
    Returns:
        Task status and result information
    """
    try:
        result = queue_manager.get_task_result(task_id)
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting task status: {str(e)}"
        )


@router.post("/purge")
async def purge_queue(
    queue_name: str = Query("chat_incoming", description="Queue name to purge"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Purge (clear) all messages from the specified queue.
    
    ⚠️ WARNING: This will delete all pending messages!
    
    Args:
        queue_name: Name of the queue to purge
        
    Returns:
        Number of messages purged
    """
    try:
        purged_count = queue_manager.purge_queue(queue_name)
        
        return {
            "queue_name": queue_name,
            "purged_messages": purged_count,
            "message": f"Successfully purged {purged_count} messages from {queue_name}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error purging queue: {str(e)}"
        )


@router.post("/health-check")
async def test_worker_health(
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Submit a health check task to verify worker connectivity.
    
    Returns:
        Health check task submission confirmation
    """
    try:
        task = health_check.apply_async(queue="chat_incoming")
        
        return {
            "task_id": task.id,
            "status": "submitted",
            "message": "Health check task submitted to workers"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting health check: {str(e)}"
        )


@router.post("/health-check/embedding")
async def test_embedding_worker_health(
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Submit a health check task to verify embedding worker connectivity.
    
    Returns:
        Health check task submission confirmation
    """
    try:
        task = health_check_embedding.apply_async(queue="embedding.qna")
        
        return {
            "task_id": task.id,
            "status": "submitted",
            "queue": "embedding.qna",
            "message": "Health check task submitted to embedding workers"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting embedding health check: {str(e)}"
        )


@router.post("/health-check/pdf-embedding")
async def test_pdf_embedding_worker_health(
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Submit a health check task to verify PDF embedding worker connectivity.
    
    Returns:
        Health check task submission confirmation
    """
    try:
        task = health_check_pdf_embedding.apply_async(queue="embedding.pdf")
        
        return {
            "task_id": task.id,
            "status": "submitted",
            "queue": "embedding.pdf",
            "message": "Health check task submitted to PDF embedding workers"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting PDF embedding health check: {str(e)}"
        )
