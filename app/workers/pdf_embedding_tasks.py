"""
PDF Document Embedding Worker

WORKER ARCHITECTURE:
====================
This worker listens to 'embedding.pdf' queue and processes PDF document embedding tasks.
It extracts text from PDFs, creates intelligent chunks, generates embeddings using Azure OpenAI,
and stores them in PostgreSQL.

FLOW:
1. Worker consumes message from 'embedding.pdf' queue
2. Downloads PDF from blob storage (if URL provided)
3. Extracts text and metadata from PDF
4. Creates intelligent chunks using advanced chunking strategies
5. Generates embeddings for each chunk using Azure OpenAI
6. Stores document and chunks with embeddings in database
7. Returns processing results

PAYLOAD FORMAT:
===============
{
    "taskId": "demo_pdf_webhook_001",
    "userId": "Marsudi",
    "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
    "documents": [
        {
            "title": "Demo Test PDF",
            "file_name": "demo.pdf",
            "file_url": "https://hugenest.blob.core.windows.net/demo-lab/documents/679268ef-cd35-4881-a7e4-a5253ca76b17.pdf"
        }
    ],
    "type": "pdf"
}

CHUNKING STRATEGIES:
====================
1. recursive (default): Hierarchical splitting by paragraphs, sentences, words
2. fixed: Fixed-size chunks with overlap
3. page: One chunk per page
4. semantic: Semantic similarity-based chunking (future)
"""
import logging
from datetime import datetime
from typing import Dict, Any
import uuid
import json
from sqlalchemy.exc import OperationalError
from azure.core.exceptions import AzureError as BlobServiceError

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk
from app.models.dataset import Dataset
from app.services.azure_openai import azure_openai_service
from app.services.pdf_processor import pdf_processor
from app.services.azure_blob_storage import azure_blob_service
from app.services.webhook_service import webhook_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.pdf_embedding_tasks.process_pdf_embedding",
    bind=True,
    autoretry_for=(OperationalError, ConnectionError, BlobServiceError),
    max_retries=5,
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True
)
def process_pdf_embedding(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process PDF embedding task from the embedding.pdf queue.
    
    WORKER RESPONSIBILITY:
    1. Listen to 'embedding.pdf' queue
    2. Extract text from PDF documents
    3. Create intelligent chunks using advanced strategies
    4. Generate embeddings for chunks using Azure OpenAI
    5. Store document and chunks with embeddings in bot.document and bot.document_chunk tables
    6. Return processing results
    
    Args:
        self: Task instance (bound)
        payload: Dictionary containing PDF embedding task information
            - taskId: Task identifier
            - userId: User who initiated the task
            - datasetId: Dataset identifier
            - documents: List of PDF documents to process
            - chunking_config: Chunking configuration (strategy, size, overlap)
            - type: Task type (pdf)
    
    Returns:
        Dict containing processing result
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(f"[Task {task_id}] Processing PDF embedding task: {payload.get('taskId')}")
    
    db = SessionLocal()
    
    try:
        # Extract payload data
        user_name = payload.get("userName")  # Use userName instead of userId
        dataset_id = payload.get("datasetId")
        documents = payload.get("documents", [])
        chunking_config = payload.get("chunking_config", {})
        
        # ============================================================
        # WEBHOOK: Update status to "On Progress" at task start
        # ============================================================
        logger.info(f"[Task {task_id}] Updating dataset status to 'On Progress'")
        webhook_service.update_dataset_status(
            dataset_id=dataset_id,
            status="On Progress"
        )
        
        if not dataset_id:
            raise ValueError("datasetId is required")
        
        if not documents:
            raise ValueError("documents list is empty")
        
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
                    f"Please create the dataset before uploading documents."
                )
                logger.error(f"[Task {task_id}] {error_msg}")
                raise ValueError(error_msg)
            
            logger.info(f"[Task {task_id}] Dataset '{dataset_id}' validated successfully")
            
        except ValueError:
            # Re-raise ValueError (dataset not found)
            raise
        except Exception as e:
            error_msg = f"Error validating dataset: {str(e)}"
            logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e
        
        # Extract chunking configuration
        chunk_strategy = chunking_config.get("strategy", "recursive")
        chunk_size = chunking_config.get("chunk_size", 1000)
        chunk_overlap = chunking_config.get("chunk_overlap", 200)
        
        logger.info(
            f"[Task {task_id}] Processing {len(documents)} PDF documents for dataset {dataset_id}"
        )
        logger.info(
            f"[Task {task_id}] Chunking config: strategy={chunk_strategy}, "
            f"size={chunk_size}, overlap={chunk_overlap}"
        )
        
        # Process each document
        total_documents = 0
        total_chunks = 0
        total_failed = 0
        failed_items = []
        document_results = []
        
        for doc_index, doc_data in enumerate(documents):
            try:
                result = _process_single_pdf(
                    db=db,
                    task_id=task_id,
                    doc_index=doc_index,
                    doc_data=doc_data,
                    dataset_uuid=dataset_uuid,
                    user_name=user_name,
                    chunk_strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                
                total_documents += 1
                total_chunks += result["chunks_created"]
                document_results.append(result)
                
                logger.info(
                    f"[Task {task_id}] Document {doc_index + 1}/{len(documents)} completed: "
                    f"{result['chunks_created']} chunks created"
                )
                
            except Exception as e:
                logger.error(
                    f"[Task {task_id}] Error processing document {doc_index}: {str(e)}",
                    exc_info=True
                )
                total_failed += 1
                failed_items.append({
                    "index": doc_index,
                    "file_name": doc_data.get("file_name", "unknown"),
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
            "total_documents": len(documents),
            "documents_processed": total_documents,
            "documents_failed": total_failed,
            "total_chunks_created": total_chunks,
            "chunking_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "failed_items": failed_items if failed_items else None,
            "document_results": document_results,
            "processing_time_ms": processing_time_ms,
            "timestamp": end_time.isoformat() + "Z"
        }
        
        logger.info(
            f"[Task {task_id}] Successfully processed {total_documents}/{len(documents)} documents "
            f"with {total_chunks} total chunks in {processing_time_ms}ms"
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
        logger.error(f"[Task {task_id}] Error processing PDF embedding task: {str(e)}", exc_info=True)
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


def _get_blob_url_with_sas(file_url: str, task_id: str) -> str:
    """
    Generate SAS token for Azure Blob Storage URL.
    
    If the URL is from Azure Blob Storage, generates a SAS token for secure access.
    If the URL is from another source, returns it unchanged.
    
    Args:
        file_url: Original file URL
        task_id: Task ID for logging
        
    Returns:
        URL with SAS token (if Azure Blob) or original URL
    """
    if not file_url:
        raise ValueError("file_url is required")
    
    try:
        # Check if URL is from Azure Blob Storage
        if ".blob.core.windows.net" in file_url:
            logger.info(f"[Task {task_id}] Generating SAS token for Azure Blob URL")
            
            # Check if URL already has SAS token (contains ?)
            if '?' in file_url:
                logger.info(f"[Task {task_id}] URL already contains query params, refreshing SAS token")
                url_with_sas = azure_blob_service.add_sas_to_blob_url(
                    file_url,
                    expiry_hours=2  # 2 hours expiry for PDF processing
                )
            else:
                # Parse URL and add SAS token
                url_with_sas = azure_blob_service.add_sas_to_blob_url(
                    file_url,
                    expiry_hours=2
                )
            
            logger.info(f"[Task {task_id}] Successfully generated SAS token for blob URL")
            return url_with_sas
        else:
            # Not an Azure Blob URL, return as-is
            logger.info(f"[Task {task_id}] URL is not from Azure Blob Storage, using as-is")
            return file_url
            
    except Exception as e:
        logger.error(f"[Task {task_id}] Error generating SAS token: {str(e)}")
        # If SAS generation fails, try to use original URL
        logger.warning(f"[Task {task_id}] Falling back to original URL")
        return file_url


def _process_single_pdf(
    db,
    task_id: str,
    doc_index: int,
    doc_data: Dict[str, Any],
    dataset_uuid: uuid.UUID,
    user_name: str,
    chunk_strategy: str,
    chunk_size: int,
    chunk_overlap: int
) -> Dict[str, Any]:
    """
    Process a single PDF document.
    
    Args:
        db: Database session
        task_id: Celery task ID
        doc_index: Document index in batch
        doc_data: Document data from payload
        dataset_uuid: Dataset UUID
        user_name: User name who initiated the task
        chunk_strategy: Chunking strategy
        chunk_size: Chunk size in characters
        chunk_overlap: Overlap between chunks
        
    Returns:
        Dict with processing results
    """
    title = doc_data.get("title", "Untitled Document")
    file_name = doc_data.get("file_name")
    file_url = doc_data.get("file_url")
    doc_metadata = doc_data.get("metadata", {})
    
    logger.info(f"[Task {task_id}] Processing document: {title} ({file_name})")
    
    # Generate SAS token if URL is from Azure Blob Storage
    pdf_url_with_sas = _get_blob_url_with_sas(file_url, task_id)
    
    logger.info(f"[Task {task_id}] Using PDF URL: {pdf_url_with_sas[:100]}...")
    
    # Extract text and chunk the PDF
    full_text, num_pages, chunks_with_metadata = pdf_processor.process_and_chunk_pdf(
        file_path=pdf_url_with_sas,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=chunk_strategy
    )
    
    logger.info(
        f"[Task {task_id}] Extracted {num_pages} pages, created {len(chunks_with_metadata)} chunks"
    )
    
    # Create document entry
    document = Document(
        title=title,
        content=full_text[:10000] if full_text else None,  # Store first 10k chars as preview
        file_name=file_name,
        file_url=file_url,
        number_of_pages=num_pages,
        dataset_id=dataset_uuid,
        created_by=user_name,
        updated_by=user_name
    )
    
    db.add(document)
    db.flush()  # Get document.id without committing
    
    logger.info(f"[Task {task_id}] Created document entry: {document.id}")
    
    # Process chunks in batches for embedding generation
    chunks_created = 0
    batch_size = 50  # Process embeddings in batches
    
    for i in range(0, len(chunks_with_metadata), batch_size):
        batch = chunks_with_metadata[i:i + batch_size]
        
        # Extract chunk texts for batch embedding
        chunk_texts = [chunk_text for chunk_text, _ in batch]
        
        # Generate embeddings for all chunks in batch
        embeddings = azure_openai_service.generate_embeddings_batch(chunk_texts)
        
        if embeddings is None:
            logger.error(f"[Task {task_id}] Failed to generate embeddings for chunk batch")
            continue
        
        # Create DocumentChunk entries with embeddings
        for j, ((chunk_text, chunk_meta), embedding) in enumerate(zip(batch, embeddings)):
            # Prepare metadata JSON
            metadata_json = json.dumps({
                "original_metadata": doc_metadata,
                "extraction_info": {
                    "batch_index": i // batch_size,
                    "chunk_in_batch": j
                }
            })
            
            chunk_entry = DocumentChunk(
                document_id=document.id,
                dataset_id=dataset_uuid,
                chunk_text=chunk_text,
                chunk_index=chunk_meta.chunk_index,
                chunk_size=chunk_meta.chunk_size,
                page_number=chunk_meta.page_number,
                page_range=str(chunk_meta.page_number) if chunk_meta.page_number else None,
                embedding=embedding,
                chunking_strategy=chunk_strategy,
                overlap_size=chunk_meta.overlap_size,
                section_title=chunk_meta.section_title,
                metadata=metadata_json,
                created_by=user_name,
                updated_by=user_name
            )
            
            db.add(chunk_entry)
            chunks_created += 1
        
        # Commit each batch
        db.commit()
        
        logger.info(
            f"[Task {task_id}] Processed chunk batch {i // batch_size + 1}, "
            f"total chunks: {chunks_created}"
        )
    
    return {
        "document_id": str(document.id),
        "title": title,
        "file_name": file_name,
        "pages": num_pages,
        "chunks_created": chunks_created,
        "status": "success"
    }


@celery_app.task(name="app.workers.pdf_embedding_tasks.health_check_pdf_embedding")
def health_check_pdf_embedding() -> Dict[str, str]:
    """
    Simple health check task for testing PDF embedding worker connectivity.
    
    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "pdf_embedding_worker"
    }


@celery_app.task(name="app.workers.pdf_embedding_tasks.test_pdf_chunking")
def test_pdf_chunking(
    test_text: str = "This is a test document. " * 100,
    chunk_size: int = 200,
    chunk_overlap: int = 50,
    strategy: str = "recursive"
) -> Dict[str, Any]:
    """
    Test PDF chunking with sample text.
    
    Args:
        test_text: Sample text to chunk
        chunk_size: Chunk size
        chunk_overlap: Overlap size
        strategy: Chunking strategy
        
    Returns:
        Dict with chunking test results
    """
    try:
        from app.services.pdf_processor import PDFChunker
        
        chunker = PDFChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strategy=strategy
        )
        
        chunks = chunker.chunk_text(test_text)
        
        return {
            "status": "success",
            "message": "Chunking test successful",
            "input_length": len(test_text),
            "num_chunks": len(chunks),
            "strategy": strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "sample_chunks": [
                {
                    "index": meta.chunk_index,
                    "size": meta.chunk_size,
                    "text": text[:100] + "..." if len(text) > 100 else text
                }
                for text, meta in chunks[:3]  # Show first 3 chunks
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error testing PDF chunking: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
