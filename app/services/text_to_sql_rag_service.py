"""
Text-to-SQL RAG Service

This service provides RAG-based SQL query generation using few-shot learning.
It retrieves similar question-SQL pairs from the database and uses them as examples
for generating SQL queries from natural language questions.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid

from app.db.session import SessionLocal
from app.models.text_to_sql import Table, TextToSql, TextToSqlTables
from app.services.azure_openai import azure_openai_service
from app.services.azure_openai_chat import azure_openai_chat_service
from sqlalchemy import text

logger = logging.getLogger(__name__)


class TextToSqlRagService:
    """
    Service for generating SQL queries from natural language using RAG.
    """
    
    def __init__(self):
        self.embedding_dimension = 1536  # Azure OpenAI ada-002 dimension
    
    def find_similar_examples(
        self,
        question: str,
        dataset_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar question-SQL examples using vector similarity search.
        
        Args:
            question: Natural language question
            dataset_id: Dataset identifier
            top_k: Number of examples to retrieve
            similarity_threshold: Minimum similarity score (0-1)
        
        Returns:
            List of similar examples with SQL queries and similarity scores
        """
        db = SessionLocal()
        
        try:
            # Generate embedding for the question
            question_embedding = azure_openai_service.generate_embedding(question)
            
            if not question_embedding:
                logger.error("Failed to generate embedding for question")
                return []
            
            # Use pgvector's cosine distance operator for efficient similarity search
            # Note: cosine distance = 1 - cosine similarity, so we calculate similarity from distance
            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(str(x) for x in question_embedding) + "]"
            
            similarity_query = text("""
                SELECT 
                    t.id,
                    t.question,
                    t.sql_query,
                    t.description,
                    t.dataset_id,
                    -- pgvector cosine distance: 1 - cosine_similarity
                    -- So similarity = 1 - (embedding <=> query_embedding)
                    1 - (t.embedding <=> CAST(:embedding AS vector(1536))) AS similarity
                FROM bot.text_to_sql t
                WHERE 
                    t.dataset_id = CAST(:dataset_id AS uuid)
                    AND t.deleted_at IS NULL
                    AND t.embedding IS NOT NULL
                ORDER BY t.embedding <=> CAST(:embedding AS vector(1536))
                LIMIT :top_k
            """)
            
            results = db.execute(
                similarity_query,
                {
                    "embedding": embedding_str,
                    "dataset_id": dataset_id,
                    "top_k": top_k
                }
            ).fetchall()
            
            # Filter by similarity threshold and format results
            similar_examples = []
            
            for row in results:
                similarity = float(row.similarity) if row.similarity else 0.0
                
                if similarity >= similarity_threshold:
                    # Get associated tables
                    tables = self._get_example_tables(db, str(row.id))
                    
                    similar_examples.append({
                        "id": str(row.id),
                        "question": row.question,
                        "sql_query": row.sql_query,
                        "description": row.description,
                        "similarity": round(similarity, 4),
                        "tables": tables
                    })
            
            logger.info(
                f"Found {len(similar_examples)} similar examples for question "
                f"(threshold: {similarity_threshold})"
            )
            
            return similar_examples
            
        except Exception as e:
            logger.error(f"Error finding similar examples: {str(e)}", exc_info=True)
            return []
        finally:
            db.close()
    
    def _get_example_tables(self, db, text_to_sql_id: str) -> List[Dict[str, str]]:
        """
        Get tables associated with a text-to-SQL example.
        
        Args:
            db: Database session
            text_to_sql_id: Text-to-SQL entry ID
        
        Returns:
            List of tables with names and descriptions
        """
        try:
            query = text("""
                SELECT 
                    t.id,
                    t.name,
                    t.description,
                    t.schema_name
                FROM bot.table t
                JOIN bot.text_to_sql_tables tst ON t.id = tst.table_id
                WHERE 
                    tst.text_to_sql_id = CAST(:text_to_sql_id AS uuid)
                    AND t.deleted_at IS NULL
                    AND tst.deleted_at IS NULL
            """)
            
            results = db.execute(
                query,
                {"text_to_sql_id": text_to_sql_id}
            ).fetchall()
            
            return [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "description": row.description or "",
                    "schema_name": row.schema_name or ""
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Error getting example tables: {str(e)}")
            return []
    
    def generate_sql_query(
        self,
        question: str,
        dataset_id: str,
        database_schema: Optional[str] = None,
        max_examples: int = 5
    ) -> Dict[str, Any]:
        """
        Generate SQL query from natural language question using RAG.
        
        Args:
            question: Natural language question
            dataset_id: Dataset identifier
            database_schema: Optional database schema information
            max_examples: Maximum number of few-shot examples to use
        
        Returns:
            Dict containing generated SQL query and metadata
        """
        try:
            # Step 1: Find similar examples
            similar_examples = self.find_similar_examples(
                question=question,
                dataset_id=dataset_id,
                top_k=max_examples
            )
            
            # Step 2: Build few-shot prompt
            few_shot_prompt = self._build_few_shot_prompt(
                question=question,
                examples=similar_examples,
                database_schema=database_schema
            )
            
            # Step 3: Generate SQL using Azure OpenAI
            logger.info(f"Generating SQL query for: {question}")
            
            system_prompt = (
                "You are an expert SQL query generator. "
                "Generate syntactically correct SQL queries based on natural language questions. "
                "Use the provided examples as reference. "
                "Return ONLY the SQL query, no explanations or markdown formatting."
            )
            
            sql_query = azure_openai_chat_service.generate_chat_response(
                system_prompt=system_prompt,
                user_message=few_shot_prompt,
                temperature=0.0,  # Deterministic for SQL generation
                max_tokens=500
            )
            
            # Handle case where LLM returns (sql, metadata) tuple
            if isinstance(sql_query, tuple):
                sql_query = sql_query[0]
            
            # Clean up the generated SQL using utility function
            from app.core.markdown_utils import clean_markdown_formatting
            sql_query = clean_markdown_formatting(
                sql_query,
                clean_headings=True,
                clean_code_blocks=True
            )
            
            logger.info(f"Generated SQL query successfully")
            
            return {
                "success": True,
                "sql_query": sql_query,
                "question": question,
                "examples_used": len(similar_examples),
                "similar_examples": similar_examples
            }
            
        except Exception as e:
            logger.error(f"Error generating SQL query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "question": question
            }
    
    def _build_few_shot_prompt(
        self,
        question: str,
        examples: List[Dict[str, Any]],
        database_schema: Optional[str] = None
    ) -> str:
        """
        Build few-shot prompt with examples.
        
        Args:
            question: User's question
            examples: Similar question-SQL pairs
            database_schema: Optional schema information
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # Add database schema if provided
        if database_schema:
            prompt_parts.append("DATABASE SCHEMA:")
            prompt_parts.append(database_schema)
            prompt_parts.append("")
        
        # Add few-shot examples
        if examples:
            prompt_parts.append("EXAMPLES:")
            prompt_parts.append("")
            
            for i, example in enumerate(examples, 1):
                # Add table context
                if example.get("tables"):
                    table_info = ", ".join([
                        f"{t['name']}" + (f" ({t['description']})" if t['description'] else "")
                        for t in example["tables"]
                    ])
                    prompt_parts.append(f"Example {i} - Tables: {table_info}")
                
                prompt_parts.append(f"Example {i} - Question: {example['question']}")
                
                if example.get("description"):
                    prompt_parts.append(f"Example {i} - Description: {example['description']}")
                
                prompt_parts.append(f"Example {i} - SQL Query:")
                prompt_parts.append(example['sql_query'])
                prompt_parts.append("")
        
        # Add the actual question
        prompt_parts.append("NOW GENERATE SQL FOR:")
        prompt_parts.append(f"Question: {question}")
        prompt_parts.append("")
        prompt_parts.append("SQL Query:")
        
        return "\n".join(prompt_parts)
    
    def execute_sql_query(
        self,
        sql_query: str,
        connection_string: str,
        max_rows: int = 100
    ) -> Dict[str, Any]:
        """
        Execute generated SQL query safely.
        
        Args:
            sql_query: SQL query to execute
            connection_string: Database connection string
            max_rows: Maximum number of rows to return
        
        Returns:
            Dict containing query results or error
        """
        db = SessionLocal()
        
        try:
            # Validate query (basic security check)
            sql_lower = sql_query.lower().strip()
            
            # Only allow SELECT queries
            if not sql_lower.startswith('select'):
                return {
                    "success": False,
                    "error": "Only SELECT queries are allowed"
                }
            
            # Block dangerous keywords
            dangerous_keywords = ['drop', 'delete', 'truncate', 'insert', 'update', 'alter', 'create']
            if any(keyword in sql_lower for keyword in dangerous_keywords):
                return {
                    "success": False,
                    "error": "Query contains dangerous operations"
                }
            
            # Add LIMIT if not present
            if 'limit' not in sql_lower:
                sql_query = f"{sql_query.rstrip(';')} LIMIT {max_rows}"
            
            # Execute query
            logger.info(f"Executing SQL query: {sql_query[:200]}")
            result = db.execute(text(sql_query))
            
            # Fetch results
            rows = result.fetchall()
            columns = result.keys() if result.returns_rows else []
            
            # Convert to list of dicts
            results = [
                {col: value for col, value in zip(columns, row)}
                for row in rows
            ]
            
            logger.info(f"Query executed successfully, returned {len(results)} rows")
            
            return {
                "success": True,
                "results": results,
                "row_count": len(results),
                "columns": list(columns)
            }
            
        except Exception as e:
            logger.error(f"Error executing SQL query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            db.close()


# Global service instance
text_to_sql_rag_service = TextToSqlRagService()
