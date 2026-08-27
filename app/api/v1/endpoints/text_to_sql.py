"""
Text-to-SQL Embedding API Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.core.security import get_api_key
from app.workers.celery_app import celery_app

router = APIRouter()


class TableInput(BaseModel):
    """Table information"""
    name: str = Field(..., description="Table name")
    description: str = Field(default="", description="Table description (schema, columns, etc.)")


class TextToSqlExampleInput(BaseModel):
    """Single text-to-SQL example"""
    question: str = Field(..., description="Natural language question")
    sql_query: str = Field(..., description="Corresponding SQL query")
    description: Optional[str] = Field(default="", description="Optional description of the query")
    tables: List[TableInput] = Field(default=[], description="Tables used in this query")


class TextToSqlEmbeddingRequest(BaseModel):
    """Request model for text-to-SQL embedding"""
    userId: str = Field(..., description="User ID")
    datasetId: str = Field(..., description="Dataset ID (must be type='sql')")
    examples: List[TextToSqlExampleInput] = Field(..., description="List of question-SQL pairs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "userId": "admin_user",
                "datasetId": "b993df02-5048-465a-8f69-e3bb00d507f3",
                "examples": [
                    {
                        "question": "How many users registered last month?",
                        "sql_query": "SELECT COUNT(*) FROM users WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
                        "description": "Count users registered in the previous calendar month",
                        "tables": [
                            {
                                "name": "users",
                                "description": "User accounts table with registration timestamps"
                            }
                        ]
                    }
                ]
            }
        }


class TextToSqlEmbeddingResponse(BaseModel):
    """Response model for text-to-SQL embedding"""
    taskId: str
    status: str
    message: str
    datasetId: str
    examplesCount: int
    timestamp: str


@router.post(
    "/embedding/text-to-sql",
    response_model=TextToSqlEmbeddingResponse,
    summary="Create Text-to-SQL Embeddings",
    description="""
    Process text-to-SQL examples by generating embeddings for questions and table descriptions.
    These embeddings enable RAG-based SQL query generation using few-shot learning.
    
    The worker will:
    1. Generate embeddings for each question + description
    2. Generate embeddings for table descriptions
    3. Store in bot.text_to_sql and bot.table tables
    4. Create relationships in bot.text_to_sql_tables junction table
    
    **Dataset Requirements:**
    - Dataset must exist in master.dataset table
    - Dataset type should be 'sql'
    
    **Use Case:**
    Upload historical question-SQL pairs to enable the chatbot to generate SQL queries
    from natural language questions using RAG-based few-shot learning.
    """
)
async def create_text_to_sql_embedding(
    request: TextToSqlEmbeddingRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Create text-to-SQL embeddings for RAG-based SQL generation.
    
    This endpoint:
    1. Validates the dataset exists and is type='sql'
    2. Queues the embedding task to 'embedding.text_to_sql' queue
    3. Worker generates embeddings for questions and tables
    4. Stores examples for future SQL generation
    
    Args:
        request: Text-to-SQL embedding request
        api_key: API key for authentication
    
    Returns:
        TextToSqlEmbeddingResponse with task ID and status
    """
    try:
        # Generate task ID
        task_id = f"embed_sql_{uuid.uuid4().hex[:8]}"
        
        # Validate input
        if not request.examples:
            raise HTTPException(status_code=400, detail="At least one example is required")
        
        # Prepare payload for worker
        payload = {
            "taskId": task_id,
            "userId": request.userId,
            "datasetId": request.datasetId,
            "examples": [
                {
                    "question": example.question,
                    "sql_query": example.sql_query,
                    "description": example.description,
                    "tables": [
                        {
                            "name": table.name,
                            "description": table.description
                        }
                        for table in example.tables
                    ]
                }
                for example in request.examples
            ],
            "type": "text_to_sql"
        }
        
        # Send to Celery worker
        task = celery_app.send_task(
            "app.workers.text_to_sql_embedding_tasks.process_text_to_sql_embedding",
            args=[payload],
            queue="embedding.text_to_sql"
        )
        
        return TextToSqlEmbeddingResponse(
            taskId=task_id,
            status="queued",
            message=f"Text-to-SQL embedding task queued successfully. Processing {len(request.examples)} examples.",
            datasetId=request.datasetId,
            examplesCount=len(request.examples),
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue text-to-SQL embedding task: {str(e)}"
        )


@router.post(
    "/query/text-to-sql",
    summary="Generate SQL from Natural Language",
    description="""
    Generate SQL query from natural language question using RAG-based few-shot learning.
    
    This endpoint:
    1. Finds similar question-SQL pairs from the dataset
    2. Uses them as few-shot examples
    3. Generates SQL query using Azure OpenAI
    4. Optionally executes the query and returns results
    
    **Requirements:**
    - Dataset must have text-to-SQL examples (created via /embedding/text-to-sql)
    - Dataset type should be 'sql'
    """
)
async def generate_sql_query(
    question: str = Query(..., description="Natural language question"),
    datasetId: str = Query(..., description="Dataset ID"),
    executeQuery: bool = Query(default=False, description="Whether to execute the generated SQL"),
    maxExamples: int = Query(default=5, description="Maximum number of few-shot examples to use"),
    api_key: str = Depends(get_api_key)
) -> Dict[str, Any]:
    """
    Generate SQL query from natural language question.
    
    Args:
        question: Natural language question
        datasetId: Dataset ID with text-to-SQL examples
        executeQuery: Whether to execute the SQL query
        maxExamples: Maximum few-shot examples to use
        api_key: API key for authentication
    
    Returns:
        Dict containing generated SQL and optionally query results
    """
    try:
        from app.services.text_to_sql_rag_service import text_to_sql_rag_service
        from app.core.config import settings
        
        # Generate SQL query
        result = text_to_sql_rag_service.generate_sql_query(
            question=question,
            dataset_id=datasetId,
            max_examples=maxExamples
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "SQL generation failed"))
        
        response = {
            "success": True,
            "question": question,
            "sql_query": result["sql_query"],
            "examples_used": result["examples_used"],
            "similar_examples": result.get("similar_examples", [])
        }
        
        # Execute query if requested
        if executeQuery:
            execution_result = text_to_sql_rag_service.execute_sql_query(
                sql_query=result["sql_query"],
                connection_string=settings.DATABASE_URL,
                max_rows=100
            )
            
            response["execution"] = execution_result
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate SQL query: {str(e)}"
        )
