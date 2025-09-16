#!/usr/bin/env python3
"""
Utility functions and classes for iagent.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class AgentExecutionError(AgentError):
    """Exception raised during agent execution."""
    pass


class AgentGenerationError(AgentError):
    """Exception raised during model generation."""
    pass


class AgentToolError(AgentError):
    """Exception raised during tool execution."""
    pass


def extract_code_from_text(text: str) -> List[str]:
    """Extract code blocks from text."""
    code_blocks = []
    
    # Pattern for markdown code blocks
    pattern = r'```(?:python)?\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for match in matches:
        code_blocks.append(match.strip())
    
    return code_blocks


def sanitize_code(code: str) -> str:
    """Sanitize code by removing dangerous patterns."""
    # Remove potential security risks
    dangerous_patterns = [
        r'__import__\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
        r'compile\s*\(',
        r'open\s*\(',
        r'file\s*\(',
    ]
    
    for pattern in dangerous_patterns:
        code = re.sub(pattern, '# SECURITY_BLOCKED: ' + pattern, code, flags=re.IGNORECASE)
    
    return code


def format_tool_description(tool) -> str:
    """Format tool description for prompts."""
    description = f"Tool: {tool.name}\n"
    description += f"Description: {tool.description}\n"
    description += "Inputs:\n"
    
    for input_name, input_spec in tool.inputs.items():
        description += f"  - {input_name} ({input_spec.get('type', 'string')}): {input_spec.get('description', 'No description')}\n"
    
    description += f"Output: {tool.output_type}\n"
    return description


def create_system_prompt(tools: List[Any], task: str) -> str:
    """Create a system prompt for the agent."""
    prompt = """You are an intelligent AI agent that can think in code and use tools to solve tasks.

You have access to the following tools:
"""
    
    for tool in tools:
        prompt += format_tool_description(tool) + "\n"
    
    prompt += f"""
Task: {task}

Instructions:
1. Think step by step about how to solve the task
2. Use the available tools when needed
3. Write Python code to perform calculations or data processing
4. Provide a clear final answer

When writing code:
- Use markdown code blocks with ```python
- Keep code simple and readable
- Use print() to show intermediate results
- Call tools using their names as functions
- IMPORTANT: To provide the final answer, use the final_answer tool with a string argument

Example:
```python
# Calculate the result
answer = 2 + 2
print("2 + 2 = " + str(answer))

# Use a tool
search_result = web_search("python programming")
print("Search result: " + str(search_result))

# Provide final answer - use the final_answer tool with a string
final_answer("The search result is: " + str(search_result))
```

Note: Only include Python code in the code blocks, not the output.

Let's solve this step by step.
"""
    
    return prompt


def parse_agent_response(response: str) -> Dict[str, Any]:
    """Parse agent response to extract thoughts, code, and actions."""
    parsed = {
        'thought': '',
        'code': '',
        'action': '',
        'final_answer': ''
    }
    
    # Extract thought (before code blocks)
    thought_match = re.search(r'Thought:(.*?)(?=```|$)', response, re.DOTALL | re.IGNORECASE)
    if thought_match:
        parsed['thought'] = thought_match.group(1).strip()
    
    # Extract code blocks
    code_blocks = extract_code_from_text(response)
    if code_blocks:
        parsed['code'] = '\n\n'.join(code_blocks)
    
    # Extract final answer - improved to catch more patterns
    final_answer_match = re.search(r'final_answer\s*\(\s*["\'](.*?)["\']\s*\)', response, re.IGNORECASE)
    if final_answer_match:
        parsed['final_answer'] = final_answer_match.group(1)
    else:
        # Check for final_answer with string concatenation (like "text" + str(variable))
        final_answer_concat_match = re.search(r'final_answer\s*\(\s*["\']([^"\']*?)["\']\s*\+\s*str\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)\s*\)', response, re.IGNORECASE)
        if final_answer_concat_match:
            # Mark that we found a concatenation call
            text_part = final_answer_concat_match.group(1)
            var_name = final_answer_concat_match.group(2)
            parsed['final_answer'] = f"CONCAT_CALL:{text_part}:{var_name}"
        else:
            # Also check for final_answer(variable) calls
            final_answer_var_match = re.search(r'final_answer\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)', response, re.IGNORECASE)
            if final_answer_var_match:
                # Mark that we found a variable call - the agent will need to handle this
                parsed['final_answer'] = f"VARIABLE_CALL:{final_answer_var_match.group(1)}"
            else:
                # Check for final_answer with str() calls
                final_answer_str_match = re.search(r'final_answer\s*\(\s*str\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)\s*\)', response, re.IGNORECASE)
                if final_answer_str_match:
                    parsed['final_answer'] = f"VARIABLE_CALL:{final_answer_str_match.group(1)}"
                else:
                    # Check for final answer in the response text
                    final_text_match = re.search(r'Final answer:\s*(.*?)(?:\n|$)', response, re.IGNORECASE)
                    if final_text_match:
                        parsed['final_answer'] = final_text_match.group(1).strip()
    
    return parsed


def validate_tool_arguments(tool, args: Dict[str, Any]) -> bool:
    """Validate tool arguments against the tool's input schema."""
    for input_name, input_spec in tool.inputs.items():
        if input_spec.get('required', False) and input_name not in args:
            raise AgentToolError(f"Required argument '{input_name}' missing for tool '{tool.name}'")
        
        if input_name in args:
            # Basic type validation
            expected_type = input_spec.get('type', 'string')
            value = args[input_name]
            
            if expected_type == 'string' and not isinstance(value, str):
                raise AgentToolError(f"Argument '{input_name}' must be a string")
            elif expected_type == 'integer' and not isinstance(value, int):
                raise AgentToolError(f"Argument '{input_name}' must be an integer")
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                raise AgentToolError(f"Argument '{input_name}' must be a number")
            elif expected_type == 'boolean' and not isinstance(value, bool):
                raise AgentToolError(f"Argument '{input_name}' must be a boolean")
    
    return True


def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + "... (truncated)"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds*1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def create_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create a logger with consistent formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
