"""
Visualization Service for Text-to-SQL Results

This service handles the visualization pipeline for SQL query results:
1. Visual intent detection (LLM-based YES/NO classification)
2. Visualization code generation (LLM generates Python/matplotlib code)
3. Safe code execution (using code_sandbox)
4. PNG upload to Azure Blob Storage
5. URL generation for frontend rendering

ARCHITECTURE COMPLIANCE:
========================
- SQL layer handles ALL aggregation and row limiting (UNCHANGED)
- Visualization layer ONLY renders data as-is
- Data passed as function parameter (NOT in LLM prompt)
- Blob container: demo-lab/visualizations/
- Output: PNG images with SAS URLs
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.code_sandbox import (
    execute_code_safely,
    get_temp_output_path,
    cleanup_temp_file,
    TEMP_DIR,
)
from app.services.azure_openai_chat import azure_openai_chat_service
from app.services.azure_blob_storage import azure_blob_service

logger = logging.getLogger(__name__)

# CONFIGURATION (LOCKED)
BLOB_CONTAINER = "demo-lab"  # Use existing demo-lab container
BLOB_VISUALIZATION_PATH = "visualizations"  # Path: hugenest/demo-lab/visualizations
DEFAULT_ROW_LIMIT = 10
MAX_SAMPLE_ROWS = 5  # For LLM prompt context
SUPPORTED_CHART_TYPES = ["bar", "line", "pie", "scatter", "histogram", "area"]


class VisualizationService:
    """
    Service for generating data visualizations from SQL query results.
    
    RESPONSIBILITY BOUNDARIES:
    - Detect if visualization is needed (LLM YES/NO)
    - Generate visualization code (LLM)
    - Execute code safely (sandbox)
    - Upload PNG to blob
    - Return image URL
    
    DOES NOT:
    - Aggregate data (SQL layer responsibility)
    - Filter data (SQL layer responsibility)
    - Limit rows (SQL layer responsibility)
    """
    
    def __init__(self):
        self.container = BLOB_CONTAINER
        self.blob_path = BLOB_VISUALIZATION_PATH
        self._ensure_container_exists()
        logger.info("Initialized VisualizationService")
    
    def _ensure_container_exists(self):
        """
        Ensure the visualizations container exists in Azure Blob Storage.
        Creates it if it doesn't exist.
        """
        try:
            container_client = azure_blob_service.blob_service_client.get_container_client(
                self.container
            )
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created blob container: {self.container}")
            else:
                logger.info(f"Blob container already exists: {self.container}")
        except Exception as e:
            logger.warning(f"Could not ensure container exists: {e}")
    
    def detect_visual_intent(
        self,
        user_question: str,
        sql_query: Optional[str] = None,
        result_row_count: int = 0
    ) -> Tuple[bool, str]:
        """
        Detect if user's question requires a visual chart response.
        
        Uses LLM classification to determine if visualization is appropriate.
        
        Args:
            user_question: Original user question
            sql_query: Generated SQL query (for context)
            result_row_count: Number of rows in SQL result
            
        Returns:
            Tuple of (needs_visualization: bool, chart_type: str)
        """
        logger.info(f"Detecting visual intent for: {user_question[:100]}")
        
        # Build intent detection prompt
        system_prompt = """You are a visualization intent classifier.
Your task is to determine if a user's question would benefit from a visual chart.

Rules:
1. Answer with EXACTLY "YES" or "NO" followed by chart type
2. Say YES for questions about:
   - Comparisons between categories (bar chart)
   - Trends over time (line chart)
   - Distribution/percentages/proportions (pie chart)
   - Correlations (scatter plot)
   - Data patterns across groups
3. Say NO for questions about:
   - Single values or counts
   - Specific lookups
   - Yes/no questions
   - Text-based information

Response format:
YES:chart_type or NO

Valid chart types: bar, line, pie, scatter, histogram, area"""

        user_prompt = f"""Question: {user_question}
SQL Query: {sql_query or 'N/A'}
Result rows: {result_row_count}

Does this question require a visual chart? Answer YES:chart_type or NO."""

        try:
            response, _ = azure_openai_chat_service.generate_chat_response(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.0,  # Deterministic
                max_tokens=20
            )
            
            if not response:
                logger.warning("Empty response from intent detection LLM")
                return False, ""
            
            response = response.strip().upper()
            logger.info(f"Intent detection response: {response}")
            
            if response.startswith("YES"):
                # Parse chart type
                parts = response.split(":")
                chart_type = parts[1].lower().strip() if len(parts) > 1 else "bar"
                
                # Validate chart type
                if chart_type not in SUPPORTED_CHART_TYPES:
                    chart_type = "bar"  # Default fallback
                
                logger.info(f"Visual intent detected: YES, chart_type={chart_type}")
                return True, chart_type
            else:
                logger.info("Visual intent detected: NO")
                return False, ""
                
        except Exception as e:
            logger.error(f"Error detecting visual intent: {e}")
            return False, ""  # Default to no visualization on error
    
    def _infer_data_schema(
        self,
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Infer schema and types from SQL result data.
        
        Args:
            data: List of row dictionaries from SQL result
            
        Returns:
            Schema dict with columns, types, and sample
        """
        if not data:
            return {"columns": [], "types": [], "sample_data": []}
        
        columns = list(data[0].keys())
        types = []
        
        # Infer types from first non-null values
        for col in columns:
            col_type = "unknown"
            for row in data[:5]:  # Check first 5 rows
                value = row.get(col)
                if value is not None:
                    if isinstance(value, (int, float)):
                        col_type = "numeric"
                    elif isinstance(value, str):
                        col_type = "string"
                    elif isinstance(value, datetime):
                        col_type = "datetime"
                    elif isinstance(value, bool):
                        col_type = "boolean"
                    break
            types.append(col_type)
        
        # Get sample data (max 5 rows)
        sample_data = data[:MAX_SAMPLE_ROWS]
        
        return {
            "columns": columns,
            "types": types,
            "sample_data": sample_data
        }
    
    def generate_visualization_code(
        self,
        user_question: str,
        data_schema: Dict[str, Any],
        chart_type: str = "bar",
        sql_query: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate Pytfhon visualization code using LLM.
        
        The generated code should:
        1. Accept data as function parameter
        2. Use matplotlib for visualization
        3. Handle null values gracefully
        4. Save to /tmp/visualizations/ directory
        5. Return the output file path
        
        Args:
            user_question: Original user question (for context)
            data_schema: Dict with columns, types, and sample_data
            chart_type: Type of chart to generate
            sql_query: Optional SQL query for context
            
        Returns:
            Tuple of (success, generated_code, error_message)
        """
        logger.info(f"Generating visualization code for chart_type={chart_type}")
        
        # Build code generation prompt
        # IMPORTANT: We only pass schema and sample, NOT full data
        system_prompt = """You are generating Python visualization code that will be executed
in a restricted server environment.

You MUST strictly follow ALL rules below:

ALLOWED LIBRARIES:
- matplotlib
- seaborn
- pandas

IMPORT RULES:
- You may ONLY use modules that are pre-imported:
  - pd (pandas)
  - plt (matplotlib.pyplot)
  - sns (seaborn)
  - uuid
  - TEMP_DIR (constant = "/tmp/visualizations/")
- DO NOT import or reference ANY other libraries.
- DO NOT use numpy, packaging, plotly, sklearn, scipy, or any other package.

DATA ASSUMPTIONS:
- Define a function named `generate_chart(data)` that:
  - Takes `data` as parameter (list of dictionaries)
  - Creates a matplotlib/seaborn chart
  - Saves to a unique file in TEMP_DIR
  - Returns the output file path

VISUALIZATION RULES:
- Use seaborn for styling if needed.
- Use matplotlib.pyplot (`plt`) to render the chart.
- Generate ONLY static charts (no interactive charts).
- Chart types supported: bar, line, pie, scatter.
- Call plt.close() after savefig.

FORBIDDEN (DO NOT USE):
- numpy (np) - use pandas operations instead
- os, sys, subprocess, shutil, pathlib
- plotly, sklearn, scipy, or any other package
- Never use os.path.join() - use f-string concatenation instead

MUST handle edge cases:
- Empty data: return None
- Null values: use df.dropna() or fillna()
- Non-numeric columns: handle appropriately

Output path format (use f-string, NOT os.path.join):
output_path = f"{TEMP_DIR}chart_{uuid.uuid4().hex[:8]}.png"

DO NOT include any imports or explanatory text, only the Python function code.

Example structure:
```python
def generate_chart(data):
    if not data:
        return None
    
    df = pd.DataFrame(data)
    df = df.dropna()
    
    sns.set_style("whitegrid")
    plt.figure(figsize=(10, 6))
    # ... chart logic using plt or sns ...
    
    output_path = f"{TEMP_DIR}chart_{uuid.uuid4().hex[:8]}.png"
    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()
    
    return output_path
```

Any violation of these rules is considered a failure."""

        # Build user prompt with LIMITED context (schema only, not full data)
        columns_info = ", ".join([
            f"{col} ({typ})" 
            for col, typ in zip(data_schema["columns"], data_schema["types"])
        ])
        
        sample_str = str(data_schema["sample_data"][:3])  # Max 3 rows in prompt
        
        user_prompt = f"""Generate a {chart_type} chart for this question:
Question: {user_question}

Data Schema:
- Columns: {columns_info}
- Sample (first 3 rows): {sample_str}

SQL Query (for context): {sql_query or 'N/A'}

Generate ONLY the Python function code, no explanations."""

        try:
            response, _ = azure_openai_chat_service.generate_chat_response(
                system_prompt=system_prompt,
                user_message=user_prompt,
                temperature=0.2,  # Low temperature for consistent code
                max_tokens=1000
            )
            
            if not response:
                return False, "", "Empty response from code generation LLM"
            
            # Clean up the response - extract code from markdown if present
            code = self._extract_code_from_response(response)
            
            if not code:
                return False, "", "Failed to extract valid Python code from response"
            
            # Basic validation
            if "def generate_chart" not in code:
                return False, "", "Generated code does not contain generate_chart function"
            
            logger.info(f"Generated visualization code: {len(code)} chars")
            return True, code, None
            
        except Exception as e:
            logger.error(f"Error generating visualization code: {e}")
            return False, "", str(e)
    
    def _extract_code_from_response(self, response: str) -> str:
        """
        Extract Python code from LLM response.
        Handles markdown code blocks and plain code.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Extracted Python code
        """
        import re
        
        # Try to extract from markdown code block
        code_block_pattern = r'```(?:python)?\s*(.*?)```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # If no code block, assume entire response is code
        # Remove any leading/trailing markdown artifacts
        code = response.strip()
        code = re.sub(r'^```python\s*', '', code)
        code = re.sub(r'\s*```$', '', code)
        
        return code.strip()
    
    def execute_visualization_code(
        self,
        code: str,
        data: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Execute generated visualization code safely.
        
        Uses code_sandbox for restricted execution.
        
        Args:
            code: Generated Python code
            data: Full SQL result data (passed as function parameter)
            
        Returns:
            Tuple of (success, output_path, error_message)
        """
        logger.info(f"Executing visualization code with {len(data)} data rows")
        
        # Validate data
        if not data:
            logger.warning("No data provided for visualization")
            return False, None, "No data available for visualization"
        
        # Execute in sandbox
        try:
            success, output_path, error = execute_code_safely(
                code=code,
                data=data,
                function_name="generate_chart",
                timeout_seconds=30
            )
            
            if success and output_path:
                # Verify file was created
                if os.path.exists(output_path):
                    logger.info(f"Visualization created: {output_path}")
                    return True, output_path, None
                else:
                    return False, None, f"Output file not found: {output_path}"
            else:
                return False, None, error or "Unknown execution error"
                
        except Exception as e:
            logger.error(f"Error executing visualization code: {e}")
            return False, None, str(e)
    
    def upload_chart_to_blob(
        self,
        local_path: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload generated chart PNG to Azure Blob Storage.
        
        Args:
            local_path: Path to local PNG file
            session_id: Optional session ID for organization
            user_id: Optional user ID for organization
            
        Returns:
            Tuple of (success, blob_url_with_sas, error_message)
        """
        logger.info(f"Uploading chart to blob storage: {local_path}")
        
        if not os.path.exists(local_path):
            return False, None, f"Local file not found: {local_path}"
        
        try:
            # Generate unique blob name
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            filename = f"chart_{timestamp}_{unique_id}.png"
            
            # Build blob path: visualizations/YYYY/MM/DD/filename
            date_path = datetime.utcnow().strftime("%Y/%m/%d")
            blob_name = f"{self.blob_path}/{date_path}/{filename}"
            
            # Read file content
            with open(local_path, "rb") as f:
                file_content = f.read()
            
            # Build metadata
            metadata = {
                "created_at": datetime.utcnow().isoformat(),
                "source": "visualization_service",
            }
            if session_id:
                metadata["session_id"] = session_id
            if user_id:
                metadata["user_id"] = user_id
            
            # Upload to blob storage
            blob_url = azure_blob_service.upload_blob(
                blob_name=blob_name,
                data=file_content,
                container_name=self.container,
                overwrite=True,
                metadata=metadata
            )
            
            # Generate URL with SAS token (1 hour expiry for response)
            blob_url_with_sas = azure_blob_service.get_blob_url_with_sas(
                blob_name=blob_name,
                container_name=self.container,
                expiry_hours=1
            )
            
            logger.info(f"Chart uploaded successfully: {blob_name}")
            
            # Cleanup local temp file
            cleanup_temp_file(local_path)
            
            return True, blob_url_with_sas, None
            
        except Exception as e:
            logger.error(f"Error uploading chart to blob: {e}")
            return False, None, str(e)
    
    def generate_visualization(
        self,
        user_question: str,
        sql_query: str,
        sql_result: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        force_chart_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Generate visualization from SQL results.
        
        This is the complete pipeline:
        1. Detect visual intent (unless forced)
        2. Infer data schema
        3. Generate visualization code
        4. Execute code safely
        5. Upload PNG to blob
        6. Return result with image URL
        
        Args:
            user_question: Original user question
            sql_query: Generated SQL query
            sql_result: Full SQL result data (list of dicts)
            session_id: Optional session ID
            user_id: Optional user ID
            force_chart_type: Optional - skip intent detection and use this chart type
            
        Returns:
            Dict containing:
            - success: bool
            - needs_visualization: bool
            - chart_type: str (if visualization needed)
            - image_url: str (if successful)
            - error: str (if failed)
        """
        result = {
            "success": False,
            "needs_visualization": False,
            "chart_type": None,
            "image_url": None,
            "error": None,
            "fallback_to_text": True  # Always allow fallback
        }
        
        logger.info(
            f"Starting visualization pipeline for: {user_question[:50]}... "
            f"({len(sql_result)} rows)"
        )
        
        # Step 1: Check if visualization is appropriate
        if force_chart_type:
            needs_viz = True
            chart_type = force_chart_type
            logger.info(f"Forced chart type: {chart_type}")
        else:
            needs_viz, chart_type = self.detect_visual_intent(
                user_question=user_question,
                sql_query=sql_query,
                result_row_count=len(sql_result)
            )
        
        result["needs_visualization"] = needs_viz
        
        if not needs_viz:
            result["success"] = True
            result["fallback_to_text"] = True
            logger.info("No visualization needed, returning text-only response")
            return result
        
        result["chart_type"] = chart_type
        
        # Step 2: Validate data
        if not sql_result:
            result["error"] = "No data available for visualization"
            result["fallback_to_text"] = True
            return result
        
        # Step 3: Infer data schema (for LLM prompt - LIMITED context)
        data_schema = self._infer_data_schema(sql_result)
        
        # Step 4: Generate visualization code
        gen_success, code, gen_error = self.generate_visualization_code(
            user_question=user_question,
            data_schema=data_schema,
            chart_type=chart_type,
            sql_query=sql_query
        )
        
        if not gen_success:
            logger.error(f"Code generation failed: {gen_error}")
            result["error"] = f"Code generation failed: {gen_error}"
            result["fallback_to_text"] = True
            return result
        
        # Step 5: Execute visualization code (with FULL data)
        exec_success, output_path, exec_error = self.execute_visualization_code(
            code=code,
            data=sql_result  # Full data passed as parameter
        )
        
        if not exec_success:
            logger.error(f"Code execution failed: {exec_error}")
            result["error"] = f"Code execution failed: {exec_error}"
            result["fallback_to_text"] = True
            return result
        
        # Step 6: Upload to blob storage
        upload_success, image_url, upload_error = self.upload_chart_to_blob(
            local_path=output_path,
            session_id=session_id,
            user_id=user_id
        )
        
        if not upload_success:
            logger.error(f"Blob upload failed: {upload_error}")
            result["error"] = f"Upload failed: {upload_error}"
            result["fallback_to_text"] = True
            # Cleanup temp file on upload failure
            cleanup_temp_file(output_path)
            return result
        
        # Success!
        result["success"] = True
        result["image_url"] = image_url
        result["fallback_to_text"] = False
        
        logger.info(f"Visualization generated successfully: {image_url}")
        return result


# Global service instance
visualization_service = VisualizationService()
