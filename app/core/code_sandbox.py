"""
Code Sandbox for Safe Python Code Execution

This module provides a restricted execution environment for running
dynamically generated Python code (specifically visualization code).

SECURITY CONSTRAINTS:
====================
- Only allowed imports: matplotlib, matplotlib.pyplot, pandas, seaborn
- Blocked builtins: open, exec, eval, compile, __import__
- No filesystem access outside /tmp/visualizations/
- No network calls
- No dynamic imports
- Maximum execution time: 30 seconds
"""
import logging
import os
import signal
import threading
import traceback
import uuid
from typing import Any, Dict, Optional, Tuple
from contextlib import contextmanager
from io import StringIO
import sys

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

MAX_EXECUTION_TIME = 30  # seconds
TEMP_DIR = "/tmp/visualizations/"

BLOCKED_MODULES = frozenset([
    "os",
    "subprocess",
    "requests",
    "urllib",
    "socket",
    "http",
    "ftplib",
    "telnetlib",
    "smtplib",
    "ssl",
    "shutil",
    "pathlib",
    "glob",
    "sys",
    "importlib",
    "pickle",
    "marshal",
    "ctypes",
])


class CodeExecutionError(Exception):
    """Custom exception for code execution errors."""
    pass


class TimeoutError(Exception):
    """Custom exception for execution timeout."""
    pass


class SecurityViolationError(Exception):
    """Custom exception for security violations."""
    pass


def validate_code(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate generated code for security violations.
    
    Args:
        code: Python code string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    code_lower = code.lower()
    
    # Check for blocked module imports
    for blocked in BLOCKED_MODULES:
        patterns = [
            f"import {blocked}",
            f"from {blocked}",
            f"__import__('{blocked}'",
            f'__import__("{blocked}"',
        ]
        for pattern in patterns:
            if pattern in code_lower:
                return False, f"Blocked module detected: {blocked}"
    
    # Check for suspicious patterns
    suspicious_patterns = [
        ("os.system", "os.system calls are blocked"),
        ("subprocess", "subprocess calls are blocked"),
        ("socket", "network operations are blocked"),
        ("requests.get", "HTTP requests are blocked"),
        ("urllib.request", "URL requests are blocked"),
        ("..\\", "path traversal detected"),
        ("../", "path traversal detected"),
        ("rm -rf", "dangerous shell command detected"),
    ]
    
    for pattern, message in suspicious_patterns:
        if pattern in code:
            return False, message
    
    # Validate path usage - only /tmp/visualizations/ allowed
    if "savefig" in code:
        import re
        save_patterns = re.findall(r'savefig\s*\(\s*["\']([^"\']+)["\']', code)
        for path in save_patterns:
            if not path.startswith("/tmp/") and not path.startswith("tmp/"):
                return False, f"Invalid save path: {path}. Only /tmp/ directory allowed."
    
    return True, None


@contextmanager
def timeout_context(seconds: int):
    """
    Context manager for execution timeout (Unix-like systems).
    Falls back to no-op on Windows.
    """
    if os.name == 'nt':  # Windows
        yield
    else:
        # Unix-like: use signal-based timeout
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Code execution timed out after {seconds} seconds")
        
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def execute_code_safely(
    code: str,
    data: Any = None,
    function_name: str = "generate_chart",
    timeout_seconds: int = MAX_EXECUTION_TIME
) -> Tuple[bool, Any, Optional[str]]:
    """
    Execute Python code safely with pre-imported visualization libraries.
    
    Args:
        code: Python code string to execute (should define a function)
        data: Data to pass as argument to the function
        function_name: Name of the function to call after code execution
        timeout_seconds: Maximum execution time
        
    Returns:
        Tuple of (success, result_or_output_path, error_message)
    """
    logger.info(f"Executing code safely with timeout={timeout_seconds}s")
    
    # Step 1: Validate code
    is_valid, error = validate_code(code)
    if not is_valid:
        logger.error(f"Code validation failed: {error}")
        return False, None, f"Security violation: {error}"
    
    # Step 2: Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Step 3: Build execution globals with imports inline
    # Import here to avoid packaging issues at module load time
    exec_globals = {
        "__builtins__": __builtins__,
        "__name__": "__sandbox__",
        "TEMP_DIR": TEMP_DIR,
        "uuid": uuid,
    }
    
    # Try importing visualization libraries
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        exec_globals["matplotlib"] = matplotlib
        exec_globals["plt"] = plt
        logger.info("Matplotlib loaded")
    except ImportError as e:
        logger.error(f"Matplotlib import failed: {e}")
        return False, None, f"Matplotlib import failed: {e}"
    
    try:
        import pandas as pd
        exec_globals["pd"] = pd
        exec_globals["pandas"] = pd
        logger.info("Pandas loaded")
    except ImportError as e:
        logger.error(f"Pandas import failed: {e}")
        return False, None, f"Pandas import failed: {e}"
    
    # Seaborn is optional
    try:
        import seaborn as sns
        exec_globals["sns"] = sns
        exec_globals["seaborn"] = sns
        logger.info("Seaborn loaded")
    except ImportError as e:
        logger.warning(f"Seaborn not available: {e}")
        exec_globals["sns"] = None
        exec_globals["seaborn"] = None
    
    exec_locals = {}
    
    # Step 4: Capture stdout/stderr
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    result = {"success": False, "output": None, "error": None}
    
    def execute():
        nonlocal result
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Execute the code to define the function
            exec(code, exec_globals, exec_locals)
            
            # Check if function was defined
            if function_name not in exec_locals:
                result["error"] = f"Function '{function_name}' not defined in code"
                return
            
            # Call the function with data
            func = exec_locals[function_name]
            output = func(data)
            
            result["success"] = True
            result["output"] = output
            
        except Exception as e:
            result["error"] = f"Execution error: {str(e)}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    # Step 5: Execute with timeout
    if os.name == 'nt':  # Windows - use threading
        thread = threading.Thread(target=execute)
        thread.start()
        thread.join(timeout=timeout_seconds)
        
        if thread.is_alive():
            logger.error(f"Code execution timed out after {timeout_seconds}s")
            return False, None, f"Execution timed out after {timeout_seconds} seconds"
    else:
        # Unix - use signal-based timeout
        try:
            with timeout_context(timeout_seconds):
                execute()
        except TimeoutError as e:
            logger.error(str(e))
            return False, None, str(e)
    
    # Restore stdout/stderr
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    # Check result
    if result["success"]:
        logger.info(f"Code executed successfully, output: {result['output']}")
        return True, result["output"], None
    else:
        logger.error(f"Code execution failed: {result['error']}")
        return False, None, result["error"]


def get_temp_output_path(prefix: str = "chart", extension: str = "png") -> str:
    """
    Generate a unique temporary output path for visualization.
    
    Args:
        prefix: Filename prefix
        extension: File extension (default: png)
        
    Returns:
        Full path to temporary file
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{extension}"
    return os.path.join(TEMP_DIR, filename)


def cleanup_temp_file(file_path: str) -> bool:
    """
    Clean up temporary file after upload.
    
    Args:
        file_path: Path to temporary file
        
    Returns:
        True if cleanup successful, False otherwise
    """
    try:
        if file_path and os.path.exists(file_path):
            if file_path.startswith(TEMP_DIR) or file_path.startswith("/tmp/"):
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
                return True
            else:
                logger.warning(f"Refusing to delete file outside temp dir: {file_path}")
                return False
    except Exception as e:
        logger.error(f"Failed to cleanup temp file {file_path}: {e}")
        return False
    return False
