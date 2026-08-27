"""
Chat-related Celery tasks for processing incoming messages

WORKER ARCHITECTURE:
====================
This worker listens to 'chat_incoming' queue and processes messages.
After processing, it publishes results to 'chat_outgoing' queue for BE consumption.

FLOW:
1. Worker consumes message from 'chat_incoming' queue
2. Processes the message (AI response, database operations, etc.)
3. Publishes result to 'chat_outgoing' queue
4. Backend (BE) consumes from 'chat_outgoing' queue to get results

STANDARDIZED RESPONSE FORMAT:
==============================
All responses published to chat_outgoing must follow this structure:
- status: "success" | "error"
- metadata: session_id, persona_id, dataset_id, conversation_id, user_id, etc.
- message: type, text, quickReplies
- confidence: relevanceScore (RAGAS evaluation schema)
- context: intent, entities, sentiment, language
- sources: list of source documents
- suggestions: list of follow-up suggestions
- metrics: processing times and token usage (input/output/total)
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from kombu import Connection, Exchange, Queue, Producer
from sqlalchemy import text as sql_text
from sqlalchemy.exc import OperationalError

from app.core.celery import celery_app
from app.core.config import settings
from app.services.rag_service import rag_service
from app.services.context_manager import context_manager
from app.services.text_to_sql_rag_service import text_to_sql_rag_service
from app.services.visualization_service import visualization_service

logger = logging.getLogger(__name__)


def build_standardized_response(
    status: str,
    message_data: Dict[str, Any],
    response_text: str,
    task_id: str,
    quick_replies: Optional[List[Dict[str, str]]] = None,
    intent: Optional[str] = None,
    entities: Optional[Dict[str, Any]] = None,
    confidence_scores: Optional[Dict[str, float]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    suggestions: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    images: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Build standardized response format for chat_outgoing queue.
    
    Args:
        status: "success" or "error"
        message_data: Original message data from chat_incoming
        response_text: AI/Bot response text
        task_id: Celery task ID
        quick_replies: List of quick reply options
        intent: Detected user intent
        entities: Extracted entities
        confidence_scores: Confidence metrics
        sources: Source documents used
        suggestions: Follow-up suggestions
        metrics: Performance metrics
        error_message: Error message if status is "error"
        images: List of image dicts for visualizations (url, type, chart_type)
        
    Returns:
        Standardized response dictionary
    """
    # timestamp_in: Use the timestamp set in process_incoming_message (when message arrived at worker)
    # This was set at line 250: message_data["timestamp"] = start_time.isoformat() + "Z"
    timestamp_in = message_data.get("timestamp")
    
    # timestamp_out is when we're building and sending the response (now)
    timestamp_out = datetime.utcnow().isoformat() + "Z"
    
    # Build response structure
    response = {
        "status": status,
        "metadata": {
            "sessionId": message_data.get("session_id", ""),
            "personaId": message_data.get("persona_id", ""),
            "datasetId": message_data.get("dataset_id", ""),
            "conversationId": message_data.get("conversation_id", ""),
            "userId": message_data.get("user_id", ""),
            "timestamp": {
                "in": timestamp_in,
                "out": timestamp_out
            },
            "timezone": message_data.get("timezone", "UTC"),
            "locale": message_data.get("locale", "en_US"),
            "channel": message_data.get("channel", "web"),
            "taskId": task_id,
        }
    }
    
    if status == "success":
        # Determine message type based on images
        message_type = "text"
        if images and len(images) > 0:
            message_type = "text_with_visualization"
        
        # Success response - includes both user question and bot answer
        response["message"] = {
            "type": message_type,
            "question": message_data.get("message", ""),  # User's original question
            "answer": response_text,  # Bot's answer/response
            "text": response_text,  # Backward compatibility
            "quickReplies": quick_replies or []
        }
        
        # Add images INSIDE message object 
        if images and len(images) > 0:
            response["message"]["images"] = images
        
        response["confidence"] = {
            "relevanceScore": confidence_scores.get("relevance", 0.0) if confidence_scores else 0.0
        }
        
        response["context"] = {
            "intent": intent or "unknown",
            "entities": entities or {},
            "sentiment": "neutral",  # TODO: Implement sentiment analysis
            "language": message_data.get("locale", "en_US").split("_")[0]
        }
        
        response["sources"] = sources or []
        response["suggestions"] = suggestions or []
        
        # Metrics with simplified token structure
        default_metrics = metrics or {}
        response["metrics"] = {
            "processingTimeMs": default_metrics.get("processingTimeMs", 0),
            "llmLatencyMs": default_metrics.get("llmLatencyMs", 0),
            "retrievalLatencyMs": default_metrics.get("retrievalLatencyMs", 0),
            "totalTokens": {
                "input": default_metrics.get("promptTokens", 0),
                "output": default_metrics.get("completionTokens", 0),
                "total": default_metrics.get("totalTokens", 0)
            }
        }
    else:
        # Error response
        response["error"] = {
            "message": error_message or "Unknown error",
            "timestamp": timestamp_out,  # Use timestamp_out for error timestamp
            "taskId": task_id
        }
    
    return response


def publish_to_outgoing_queue(result_data: Dict[str, Any]) -> bool:
    """
    Publish processing result to chat_outgoing queue for BE consumption.
    
    NOTE: We don't declare queue arguments here because the queue already exists
    in Azure RabbitMQ. We just publish to the existing queue.
    
    Args:
        result_data: Processing result to publish
        
    Returns:
        True if published successfully, False otherwise
    """
    try:
        import json
        import pika
        from pika.credentials import PlainCredentials
        import logging
        
        # Disable pika verbose logging
        logging.getLogger('pika').setLevel(logging.WARNING)
        
        # Use pika for direct publishing to ensure message persistence
        # Credentials from environment variables
        credentials = PlainCredentials(
            settings.RABBITMQ_USERNAME,
            settings.RABBITMQ_PASSWORD
        )
        parameters = pika.ConnectionParameters(
            host=settings.RABBITMQ_AMQP_HOST,
            port=settings.RABBITMQ_AMQP_PORT,
            credentials=credentials,
            virtual_host='/'
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # In development, create queue if it doesn't exist
        # In production, check that queue exists (passive=True)
        is_production = settings.ENVIRONMENT == "production"
        
        if is_production:
            # Production: queue must exist
            channel.queue_declare(queue='chat_outgoing', passive=True)
        else:
            # Development: create queue if needed
            # Declare exchange first
            channel.exchange_declare(
                exchange='demo_labs',
                exchange_type='topic',
                durable=True
            )
            
            # Declare queue
            channel.queue_declare(
                queue='chat_outgoing',
                durable=True,
                arguments={}
            )
            
            # Bind queue to exchange
            channel.queue_bind(
                queue='chat_outgoing',
                exchange='demo_labs',
                routing_key='chat.outgoing'
            )
        
        # Publish message
        json_payload = json.dumps(result_data, ensure_ascii=False)
        
        # Publish via demo_labs exchange with correct routing key (chat.outgoing with DOT)
        channel.basic_publish(
            exchange='demo_labs',
            routing_key='chat.outgoing',  # Use DOT not underscore (based on RabbitMQ binding)
            body=json_payload,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                content_encoding='utf-8'
            )
        )
        
        connection.close()
        
        logger.info(f"Published result to chat_outgoing queue: {result_data.get('metadata', {}).get('taskId')}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to publish to chat_outgoing queue: {str(e)}", exc_info=True)
        return False


@celery_app.task(
    name="app.workers.chat_tasks.process_incoming_message",
    bind=True,
    autoretry_for=(OperationalError, ConnectionError),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_incoming_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming chat message from the chat_incoming queue.
    
    WORKER RESPONSIBILITY:
    1. Listen to 'chat_incoming' queue
    2. Process the message (AI, database, etc.)
    3. Publish STANDARDIZED result to 'chat_outgoing' queue
    4. Backend (BE) will consume from 'chat_outgoing' queue
    
    Args:
        self: Task instance (bound)
        message_data: Dictionary containing message information
            - user_id: User identifier
            - message: Message text
            - session_id: Chat session identifier
            - conversation_id: Conversation identifier
            - persona_id: Bot persona identifier
            - dataset_id: Dataset/KB identifier
            - timezone: User timezone
            - locale: User locale
            - channel: Communication channel
            - metadata: Additional metadata
    
    Returns:
        Dict containing processing result (for Celery result backend)
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    # Capture timestamp_in when message arrives at worker (not from payload)
    message_data["timestamp"] = start_time.isoformat() + "Z"
    
    logger.info(f"[Task {task_id}] Processing incoming message: {message_data}")
    
    try:
        # Extract message data
        user_id = message_data.get("user_id")
        message_text = message_data.get("message")
        session_id = message_data.get("session_id")
        conversation_id = message_data.get("conversation_id")
        persona_id = message_data.get("persona_id")
        dataset_id = message_data.get("dataset_id")
        
        logger.info(
            f"[Task {task_id}] User: {user_id}, Session: {session_id}, "
            f"Conversation: {conversation_id}, Persona: {persona_id}, "
            f"Dataset: {dataset_id}, Message: {message_text}"
        )
        
        # ============================================================
        # CONTEXT MANAGEMENT LAYER
        # ============================================================
        # Build conversation context from chat history before RAG:
        # 1. Retrieve recent chat history from Redis
        # 2. Build conversation context for continuity
        # 3. Enhance current question with context (for follow-ups)
        # 4. Get session statistics
        # ============================================================
        
        logger.info(f"[Task {task_id}] Building conversation context...")
        
        # Get chat history and build context
        conversation_context, history = context_manager.build_conversation_context(
            session_id=session_id,
            user_id=user_id,
            current_question=message_text,
            max_history=5,  # Include last 5 turns
            include_metadata=True
        )
        
        # Build enhanced question for better RAG retrieval (handles follow-ups)
        enhanced_question = context_manager.build_enhanced_question(
            session_id=session_id,
            user_id=user_id,
            current_question=message_text,
            max_history=3
        )
        
        # Get session stats
        session_stats = context_manager.get_session_stats(session_id, user_id)
        
        logger.info(
            f"[Task {task_id}] Context built: {len(history)} history messages, "
            f"session has {session_stats.get('message_count', 0)} total messages"
        )
        
        if enhanced_question != message_text:
            logger.info(
                f"[Task {task_id}] Enhanced question for follow-up: "
                f"'{message_text}' -> '{enhanced_question[:100]}...'"
            )
        
        # ============================================================
        # RAG-BASED MESSAGE PROCESSING WITH ADVANCED TECHNIQUES
        # ============================================================
        # Supports multiple dataset types with automatic detection:
        # 
        # 1. QnA Datasets: Traditional FAQ-based retrieval
        #    - Vector similarity search on questions
        #    - Direct question-answer mapping
        # 
        # 2. PDF Datasets: Advanced document retrieval
        #    - Semantic search on document chunks
        #    - Context window with surrounding text
        #    - Source diversity (MMR-like reranking)
        #    - Metadata enrichment (pages, sections)
        # 
        # 3. SQL Datasets: Text-to-SQL with RAG-based few-shot learning
        #    - Find similar question-SQL pairs
        #    - Generate SQL query using few-shot examples
        #    - Execute SQL query safely
        #    - Format results as natural language response
        # 
        # 4. Mixed Datasets: Hybrid retrieval
        #    - Combines multiple source types
        #    - Balanced source distribution
        # 
        # Process Flow:
        # 1. Auto-detect dataset type (QnA, PDF, SQL, or Mixed)
        # 2. Generate embedding for user's question
        # 3. Search similar content using vector similarity
        # 4. Apply advanced RAG techniques (reranking, diversity)
        # 5. Retrieve persona prompt as system prompt
        # 6. Build enriched context from top sources
        # 7. Generate response using Azure OpenAI with RAG context
        # 8. Calculate confidence scores and metrics
        # 9. Return sources with metadata for transparency
        # ============================================================
        
        logger.info(f"[Task {task_id}] Starting advanced RAG-based processing...")
        
        # Initialize visualization_images for all dataset types
        # (only SQL datasets may populate this, others will be empty)
        visualization_images = []
        
        # Check if dataset is SQL type - handle separately
        from app.db.session import SessionLocal
        db = SessionLocal()
        
        try:
            dataset_type_check = db.execute(
                sql_text("SELECT type FROM master.dataset WHERE id = :dataset_id AND deleted_at IS NULL"),
                {"dataset_id": dataset_id}
            ).fetchone()
            
            actual_dataset_type = dataset_type_check.type if dataset_type_check else None
            
        except Exception as e:
            logger.warning(f"[Task {task_id}] Could not check dataset type: {str(e)}")
            actual_dataset_type = None
        finally:
            db.close()
        
        # ============================================================
        # SQL DATASET TYPE HANDLING
        # ============================================================
        if actual_dataset_type == "sql":
            logger.info(f"[Task {task_id}] Processing SQL dataset type")
            
            try:
                # Step 1: Generate SQL query using RAG-based few-shot learning
                sql_generation_result = text_to_sql_rag_service.generate_sql_query(
                    question=enhanced_question,
                    dataset_id=dataset_id,
                    max_examples=5
                )
                
                if not sql_generation_result["success"]:
                    raise Exception(f"SQL generation failed: {sql_generation_result.get('error')}")
                
                generated_sql = sql_generation_result["sql_query"]
                similar_examples = sql_generation_result.get("similar_examples", [])
                
                logger.info(
                    f"[Task {task_id}] Generated SQL query: {generated_sql[:200]}, "
                    f"using {len(similar_examples)} examples"
                )
                
                # Step 2: Execute the SQL query
                execution_result = text_to_sql_rag_service.execute_sql_query(
                    sql_query=generated_sql,
                    connection_string=settings.DATABASE_URL,
                    max_rows=100
                )
                
                if not execution_result["success"]:
                    raise Exception(f"SQL execution failed: {execution_result.get('error')}")
                
                query_results = execution_result["results"]
                row_count = execution_result["row_count"]
                
                logger.info(f"[Task {task_id}] SQL executed successfully: {row_count} rows returned")
                
                # ============================================================
                # STEP 2.5: VISUALIZATION PIPELINE (NEW)
                # ============================================================
                # After SQL execution, detect if visualization is needed.
                # If YES: generate chart, upload to blob, include image URL
                # If NO: continue with text-only response
                # Fallback: always fall back to text on any visualization error
                # ============================================================
                
                visualization_images = []  # Will hold image data if visualization succeeds
                
                try:
                    logger.info(f"[Task {task_id}] Starting visualization pipeline...")
                    
                    viz_result = visualization_service.generate_visualization(
                        user_question=message_text,
                        sql_query=generated_sql,
                        sql_result=query_results,
                        session_id=session_id,
                        user_id=user_id
                    )
                    
                    if viz_result["success"] and viz_result.get("image_url"):
                        # Visualization generated successfully
                        visualization_images.append({
                            "url": viz_result["image_url"],
                            "type": "chart",
                            "chart_type": viz_result.get("chart_type", "bar")
                        })
                        logger.info(
                            f"[Task {task_id}] Visualization generated: "
                            f"chart_type={viz_result.get('chart_type')}, "
                            f"url={viz_result['image_url'][:80]}..."
                        )
                    elif viz_result.get("needs_visualization") and viz_result.get("error"):
                        # Visualization was needed but failed - log error and fall back to text
                        logger.warning(
                            f"[Task {task_id}] Visualization failed, falling back to text: "
                            f"{viz_result.get('error')}"
                        )
                    else:
                        # No visualization needed
                        logger.info(f"[Task {task_id}] No visualization needed for this query")
                        
                except Exception as viz_error:
                    # Visualization pipeline error - graceful fallback to text-only
                    logger.error(
                        f"[Task {task_id}] Visualization pipeline error (falling back to text): "
                        f"{str(viz_error)}",
                        exc_info=True
                    )
                    # Continue with text-only response
                
                # Step 3: Format results as natural language response
                from app.services.azure_openai_chat import azure_openai_chat_service
                
                formatting_prompt = f"""Based on the following SQL query and results, provide a clear, natural language response to the user's question.

User's Question: {message_text}

Generated SQL Query:
{generated_sql}

Query Results ({row_count} rows):
{query_results[:10]}  # Show first 10 rows

Please provide a conversational response that:
1. Directly answers the user's question
2. Highlights key findings from the data
3. Presents numbers clearly
4. Is easy to understand

Response:"""
                
                system_prompt = "You are a helpful data analyst assistant. Convert SQL query results into clear, natural language responses."
                
                response_text = azure_openai_chat_service.generate_chat_response(
                    system_prompt=system_prompt,
                    user_message=formatting_prompt,
                    temperature=0.7,
                    max_tokens=500
                )
                
                # Build sources from similar examples
                sources = [
                    {
                        "type": "text_to_sql",
                        "question": ex["question"],
                        "sql_query": ex["sql_query"],
                        "similarity": ex["similarity"],
                        "description": ex.get("description", "")
                    }
                    for ex in similar_examples[:3]  # Top 3 examples
                ]
                
                # Add the generated SQL as a source
                sources.insert(0, {
                    "type": "generated_sql",
                    "sql_query": generated_sql,
                    "row_count": row_count,
                    "execution_time": execution_result.get("execution_time", 0)
                })
                
                # RAGAS Evaluation Schema - only relevance score
                confidence_scores = {
                    "relevance": similar_examples[0]["similarity"] if similar_examples else 0.80
                }
                
                dataset_type = "sql"
                detected_intent = "sql_query"
                extracted_entities = {
                    "sql_query": generated_sql,
                    "row_count": row_count,
                    "examples_used": len(similar_examples),
                    "has_results": row_count > 0,
                    "has_visualization": len(visualization_images) > 0,
                    "visualization_chart_type": visualization_images[0].get("chart_type") if visualization_images else None
                }
                
                rag_metrics = {
                    "retrieval_time_ms": sql_generation_result.get("generation_time_ms", 0),
                    "generation_time_ms": 0,
                    "total_time_ms": sql_generation_result.get("total_time_ms", 0),
                    "num_sources": len(similar_examples),
                    "tokens_used": 0
                }
                
                logger.info(f"[Task {task_id}] SQL query processed successfully")
                
            except Exception as e:
                logger.error(f"[Task {task_id}] Error processing SQL dataset: {str(e)}", exc_info=True)
                response_text = f"I encountered an error while processing your SQL query: {str(e)}"
                sources = []
                visualization_images = []  # Reset on error
                # RAGAS Evaluation Schema - only relevance score
                confidence_scores = {
                    "relevance": 0.3
                }
                dataset_type = "sql"
                detected_intent = "sql_query_error"
                extracted_entities = {"error": str(e)}
                rag_metrics = {}
        
        # ============================================================
        # REGULAR DATASET TYPES (QnA, PDF, Mixed)
        # ============================================================
        else:
            # Use hybrid RAG service with automatic dataset type detection
            # Use enhanced question for better context-aware retrieval
            rag_result = rag_service.generate_hybrid_rag_response(
                question=enhanced_question,  # Use enhanced question with context
                persona_id=persona_id,
                dataset_id=dataset_id,
                dataset_type="auto",  # Auto-detect: "qna", "pdf", or "mixed"
                top_k=5,  # Use top 5 most similar sources (will be diversified for PDF)
                similarity_threshold=0.7,  # Minimum 70% similarity
                temperature=0.7,
                max_tokens=800  # Increased for more comprehensive answers from PDFs
            )
            
            if rag_result["status"] == "error":
                logger.error(f"[Task {task_id}] RAG processing failed: {rag_result.get('error')}")
                raise Exception(f"RAG processing failed: {rag_result.get('error')}")
            
            # Extract RAG results
            response_text = rag_result["response"]
            sources = rag_result["sources"]
            confidence_scores = rag_result["confidence"]
            rag_metrics = rag_result["metrics"]
            dataset_type = rag_result.get("dataset_type", "unknown")
            
            logger.info(
                f"[Task {task_id}] RAG response generated: "
                f"{len(response_text)} chars, {len(sources)} sources, "
                f"dataset_type: {dataset_type}, "
                f"relevance: {confidence_scores.get('relevance', 0.0):.2f}"
            )
            
            # Determine intent based on context and dataset type
            if dataset_type == "pdf":
                detected_intent = "document_search"
            elif dataset_type == "qna":
                detected_intent = "qna_search"
            elif dataset_type == "sql":
                detected_intent = "sql_query"
            elif dataset_type == "mixed":
                detected_intent = "hybrid_search"
            else:
                detected_intent = "general_inquiry"
            
            # Extract entities (enhanced with dataset type info)
            extracted_entities = {
                "has_context": rag_result.get("context_used", False),
                "num_sources": rag_result.get("num_sources", 0),
                "dataset_type": dataset_type,
                "source_types": list(set(s.get("type", "unknown") for s in sources)),
                "has_history": len(history) > 0,
                "history_count": len(history)
            }
        
        # ============================================================
        # STORE CONVERSATION HISTORY
        # ============================================================
        # Store both user question and assistant response in Redis
        # for future context building
        # ============================================================
        
        # Store user message
        context_manager.add_message_to_history(
            session_id=session_id,
            user_id=user_id,
            role="user",
            message=message_text,  # Store original question, not enhanced
            metadata={
                "conversation_id": conversation_id,
                "dataset_id": dataset_id,
                "persona_id": persona_id,
                "intent": detected_intent,
                "entities": extracted_entities
            },
            ttl_hours=24
        )
        
        # Store assistant response
        context_manager.add_message_to_history(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            message=response_text,
            metadata={
                "sources_count": len(sources),
                "dataset_type": dataset_type,
                "confidence": confidence_scores,
                "intent": detected_intent
            },
            ttl_hours=24
        )
        
        logger.info(f"[Task {task_id}] Stored conversation in history (Redis)")
        
        # Generate quick replies based on dataset (future enhancement)
        quick_replies = [
            {"label": "Tanya Lagi", "value": "ask_more"},
            {"label": "Hubungi Support", "value": "contact_support"}
        ]
        
        # Generate suggestions (future enhancement - could be from related FAQs)
        suggestions = []
        
        # Calculate metrics
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Merge RAG metrics with overall processing time
        # Token metrics: input (prompt) + output (completion) = total
        metrics = {
            "processingTimeMs": processing_time_ms,
            "llmLatencyMs": rag_metrics.get("llmLatencyMs", 0),
            "retrievalLatencyMs": rag_metrics.get("retrievalLatencyMs", 0),
            "promptTokens": rag_metrics.get("promptTokens", 0),  # Will be mapped to input
            "completionTokens": rag_metrics.get("completionTokens", 0),  # Will be mapped to output
            "totalTokens": rag_metrics.get("totalTokens", 0)
        }
        
        # Build standardized response
        standardized_response = build_standardized_response(
            status="success",
            message_data=message_data,
            response_text=response_text,
            task_id=task_id,
            quick_replies=quick_replies,
            intent=detected_intent,
            entities=extracted_entities,
            confidence_scores=confidence_scores,
            sources=sources,
            suggestions=suggestions,
            metrics=metrics,
            images=visualization_images if visualization_images else None
        )
        
        logger.info(f"[Task {task_id}] Successfully processed message")
        
        # Publish standardized result to chat_outgoing queue
        publish_success = publish_to_outgoing_queue(standardized_response)
        
        if publish_success:
            logger.info(f"[Task {task_id}] Standardized result published to chat_outgoing queue")
            return {
                "task_id": task_id,
                "status": "success",
                "published_to_outgoing": True,
                "processing_time_ms": processing_time_ms
            }
        else:
            logger.warning(f"[Task {task_id}] Failed to publish result to chat_outgoing queue")
            return {
                "task_id": task_id,
                "status": "success",
                "published_to_outgoing": False,
                "processing_time_ms": processing_time_ms
            }
        
    except Exception as e:
        logger.error(f"[Task {task_id}] Error processing message: {str(e)}", exc_info=True)
        
        # Build standardized error response
        error_response = build_standardized_response(
            status="error",
            message_data=message_data,
            response_text="",
            task_id=task_id,
            error_message=str(e)
        )
        
        # Publish error to chat_outgoing queue
        publish_to_outgoing_queue(error_response)
        
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(
    name="app.workers.chat_tasks.process_batch_messages",
    autoretry_for=(OperationalError, ConnectionError),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_batch_messages(messages: list) -> Dict[str, Any]:
    """
    Process multiple messages in batch.
    
    Args:
        messages: List of message dictionaries
    
    Returns:
        Dict containing batch processing results
    """
    logger.info(f"Processing batch of {len(messages)} messages")
    
    results = []
    for message_data in messages:
        try:
            # Process each message
            result = process_incoming_message.apply_async(
                args=[message_data],
                queue="chat_incoming"
            )
            results.append({
                "message_id": message_data.get("message_id"),
                "task_id": result.id,
                "status": "queued"
            })
        except Exception as e:
            logger.error(f"Error queuing message: {str(e)}")
            results.append({
                "message_id": message_data.get("message_id"),
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "total": len(messages),
        "queued": len([r for r in results if r["status"] == "queued"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }


@celery_app.task(name="app.workers.chat_tasks.health_check")
def health_check() -> Dict[str, str]:
    """
    Simple health check task for testing worker connectivity.
    
    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "chat_incoming_worker"
    }
