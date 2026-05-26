import sys
import io
import contextlib

def run_python_analysis(code_string: str) -> str:
    """Executes generated Python code dynamically and returns the standard output."""
    clean_code = code_string.replace("```python", "").replace("```", "").strip()
    
    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec_globals = {"pd": __import__("pandas")}
            exec(clean_code, exec_globals)
        return stdout_capture.getvalue().strip()
    except Exception as e:
        return f"Execution Error: {str(e)}"