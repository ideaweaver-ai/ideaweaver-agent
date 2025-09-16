#!/usr/bin/env python3
"""
Code execution engine for iagent.

Provides safe Python code execution with security features.
"""

import ast
import logging
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Exception raised during code execution."""
    pass


class SecurityError(Exception):
    """Exception raised for security violations."""
    pass


class PythonExecutor(ABC):
    """Abstract base class for Python code executors."""
    
    @abstractmethod
    def execute(self, code: str, variables: Optional[Dict[str, Any]] = None) -> Tuple[Any, str]:
        """Execute Python code and return result and output."""
        pass


class LocalPythonExecutor(PythonExecutor):
    """Local Python code executor with security features."""
    
    def __init__(self, 
                 allowed_imports: Optional[List[str]] = None,
                 max_execution_time: int = 30,
                 max_output_length: int = 10000,
                 dry_run: bool = True):
        self.allowed_imports = allowed_imports or [
            'math', 'random', 'datetime', 'json', 're', 'collections', 'itertools'
        ]
        self.max_execution_time = max_execution_time
        self.max_output_length = max_output_length
        self.dry_run = dry_run
        self.variables: Dict[str, Any] = {}
    
    def execute(self, code: str, variables: Optional[Dict[str, Any]] = None) -> Tuple[Any, str]:
        """Execute Python code safely."""
        # Update variables
        if variables:
            self.variables.update(variables)
        
        # Validate code
        self._validate_code(code)
        
        # DRY RUN MODE: Just return the code without executing
        if self.dry_run:
            return None, f"🔍 DRY RUN MODE - Code Preview:\n\n```python\n{code}\n```\n\n📝 This code would be executed with the following variables:\n{self._format_variables_preview()}"
        
        # Capture output
        output_buffer = StringIO()
        error_buffer = StringIO()
        
        try:
            # Execute with timeout
            start_time = time.time()
            
            with redirect_stdout(output_buffer), redirect_stderr(error_buffer):
                # Create execution environment with all variables in one namespace
                exec_globals = {
                    '__builtins__': self._get_safe_builtins(),
                    **self.variables
                }
                
                # Execute code in the same namespace
                exec(code, exec_globals)
                
                # Update variables from the execution namespace
                self.variables.update({k: v for k, v in exec_globals.items() if not k.startswith('_')})
                
                # Check timeout
                if time.time() - start_time > self.max_execution_time:
                    raise ExecutionError("Code execution timed out")
                
                # Get output
                output = output_buffer.getvalue()
                error_output = error_buffer.getvalue()
                
                # Truncate output if too long
                if len(output) > self.max_output_length:
                    output = output[:self.max_output_length] + "... (truncated)"
                
                # Check for errors
                if error_output:
                    raise ExecutionError(f"Code execution error: {error_output}")
                
                return None, output
                
        except Exception as e:
            if isinstance(e, (ExecutionError, SecurityError)):
                raise
            raise ExecutionError(f"Code execution failed: {str(e)}")
    
    def _validate_code(self, code: str):
        """Validate code for security."""
        try:
            tree = ast.parse(code)
            self._check_ast_security(tree)
        except SyntaxError as e:
            raise ExecutionError(f"Syntax error: {str(e)}")
    
    def _check_ast_security(self, tree: ast.AST):
        """Check AST for security violations."""
        for node in ast.walk(tree):
            # Check for import statements
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._is_import_allowed(alias.name):
                            raise SecurityError(f"Import not allowed: {alias.name}")
                else:  # ast.ImportFrom
                    if not self._is_import_allowed(node.module):
                        raise SecurityError(f"Import not allowed: {node.module}")
            
            # Check for potentially dangerous operations
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'compile']:
                        raise SecurityError(f"Dangerous function call: {node.func.id}")
    
    def _is_import_allowed(self, module_name: str) -> bool:
        """Check if import is allowed."""
        if module_name is None:
            return True
        
        # Allow built-in modules
        if module_name in self.allowed_imports:
            return True
        
        # Allow submodules of allowed modules
        for allowed in self.allowed_imports:
            if module_name.startswith(f"{allowed}."):
                return True
        
        return False
    
    def _get_safe_builtins(self) -> Dict[str, Any]:
        """Get safe built-in functions."""
        safe_builtins = {
            'abs': abs,
            'all': all,
            'any': any,
            'bin': bin,
            'bool': bool,
            'chr': chr,
            'dict': dict,
            'enumerate': enumerate,
            'filter': filter,
            'float': float,
            'format': format,
            'frozenset': frozenset,
            'hash': hash,
            'hex': hex,
            'int': int,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'iter': iter,
            'len': len,
            'list': list,
            'map': map,
            'max': max,
            'min': min,
            'next': next,
            'oct': oct,
            'ord': ord,
            'pow': pow,
            'print': print,
            'range': range,
            'repr': repr,
            'reversed': reversed,
            'round': round,
            'set': set,
            'slice': slice,
            'sorted': sorted,
            'str': str,
            'sum': sum,
            'tuple': tuple,
            'type': type,
            'zip': zip,
        }
        return safe_builtins
    
    def _format_variables_preview(self) -> str:
        """Format variables for preview in dry run mode."""
        if not self.variables:
            return "No variables defined"
        
        preview_lines = []
        for name, value in self.variables.items():
            # Truncate long values for readability
            if isinstance(value, str) and len(str(value)) > 100:
                preview = f"{str(value)[:100]}... (truncated)"
            else:
                preview = str(value)
            preview_lines.append(f"  {name}: {preview}")
        
        return "\n".join(preview_lines)
    
    def set_variable(self, name: str, value: Any):
        """Set a variable in the execution environment."""
        self.variables[name] = value
    
    def get_variable(self, name: str) -> Any:
        """Get a variable from the execution environment."""
        return self.variables.get(name)
    
    def clear_variables(self):
        """Clear all variables."""
        self.variables.clear()


class PreviewExecutor(PythonExecutor):
    """Executor that shows code without executing it - for preview purposes."""
    
    def __init__(self, variables: Optional[Dict[str, Any]] = None):
        self.variables = variables or {}
    
    def execute(self, code: str, variables: Optional[Dict[str, Any]] = None) -> Tuple[Any, str]:
        """Show code preview without executing."""
        # Update variables
        if variables:
            self.variables.update(variables)
        
        # Create a formatted preview
        preview = self._create_code_preview(code)
        return None, preview
    
    def _create_code_preview(self, code: str) -> str:
        """Create a formatted preview of the code."""
        preview_lines = [
            "🔍 CODE PREVIEW MODE",
            "=" * 50,
            "",
            "📝 Code that would be executed:",
            "```python",
            code,
            "```",
            "",
            "📊 Available variables:",
        ]
        
        if self.variables:
            for name, value in self.variables.items():
                # Format the value nicely
                if isinstance(value, str):
                    if len(value) > 80:
                        preview_lines.append(f"  {name}: '{value[:80]}...' (str, {len(value)} chars)")
                    else:
                        preview_lines.append(f"  {name}: '{value}' (str)")
                elif isinstance(value, (int, float)):
                    preview_lines.append(f"  {name}: {value} ({type(value).__name__})")
                elif isinstance(value, (list, tuple)):
                    preview_lines.append(f"  {name}: {value} ({type(value).__name__}, {len(value)} items)")
                elif isinstance(value, dict):
                    preview_lines.append(f"  {name}: {value} (dict, {len(value)} keys)")
                else:
                    preview_lines.append(f"  {name}: {value} ({type(value).__name__})")
        else:
            preview_lines.append("  No variables defined")
        
        preview_lines.extend([
            "",
            "⚠️  This code was NOT executed for safety reasons.",
            "   To execute the code, use a regular executor.",
            "=" * 50
        ])
        
        return "\n".join(preview_lines)
    
    def set_variable(self, name: str, value: Any):
        """Set a variable in the preview environment."""
        self.variables[name] = value
    
    def get_variable(self, name: str) -> Any:
        """Get a variable from the preview environment."""
        return self.variables.get(name)
    
    def clear_variables(self):
        """Clear all variables."""
        self.variables.clear()


class CodeParser:
    """Parser for extracting code from text."""
    
    @staticmethod
    def extract_code_blocks(text: str) -> List[str]:
        """Extract code blocks from text."""
        code_blocks = []
        
        # Look for markdown code blocks
        lines = text.split('\n')
        in_code_block = False
        current_block = []
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block
                    if current_block:
                        code_blocks.append('\n'.join(current_block))
                    current_block = []
                    in_code_block = False
                else:
                    # Start of code block
                    in_code_block = True
            elif in_code_block:
                current_block.append(line)
        
        return code_blocks
    
    @staticmethod
    def extract_python_code(text: str) -> List[str]:
        """Extract Python code from text."""
        code_blocks = CodeParser.extract_code_blocks(text)
        python_blocks = []
        
        for block in code_blocks:
            # Check if it's Python code
            if any(keyword in block for keyword in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
                python_blocks.append(block)
        
        return python_blocks
