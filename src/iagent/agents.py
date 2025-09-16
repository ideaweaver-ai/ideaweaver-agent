#!/usr/bin/env python3
"""
Core agent implementations for iagent.

Provides CodeAgent and MultiStepAgent with ReAct framework.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Generator, Union
from dataclasses import dataclass

from .models import Model, ChatMessage
from .tools import BaseTool, get_tool, TOOL_REGISTRY
from .memory import AgentMemory, StepType
from .executor import LocalPythonExecutor, CodeParser
from .utils import (
    AgentError, AgentExecutionError, AgentGenerationError, AgentToolError,
    create_system_prompt, parse_agent_response, validate_tool_arguments,
    extract_code_from_text, truncate_text
)

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of an agent run."""
    answer: str
    steps: List[Dict[str, Any]]
    memory: AgentMemory
    duration: float
    token_usage: Dict[str, int]


class MultiStepAgent(ABC):
    """Abstract base class for multi-step agents."""
    
    def __init__(self, 
                 model: Model,
                 tools: Optional[List[Union[BaseTool, str]]] = None,
                 system_prompt: str = "",
                 max_steps: int = 10,
                 stream_outputs: bool = False):
        self.model = model
        self.tools = self._process_tools(tools or [])
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.stream_outputs = stream_outputs
        self.memory = AgentMemory(system_prompt)
    
    def _process_tools(self, tools: List[Union[BaseTool, str]]) -> List[BaseTool]:
        """Process tools list, converting strings to tool instances."""
        processed_tools = []
        
        for tool in tools:
            if isinstance(tool, str):
                # Get tool by name
                tool_instance = get_tool(tool)
                if tool_instance is None:
                    raise ValueError(f"Tool '{tool}' not found")
                processed_tools.append(tool_instance)
            elif isinstance(tool, BaseTool):
                processed_tools.append(tool)
            else:
                raise ValueError(f"Invalid tool type: {type(tool)}")
        
        return processed_tools
    
    @abstractmethod
    def run(self, task: str, **kwargs) -> Union[RunResult, Generator[Dict[str, Any], None, None]]:
        """Run the agent on a task."""
        pass
    
    def _create_messages(self, task: str) -> List[ChatMessage]:
        """Create messages for the model."""
        messages = []
        
        # Add system prompt
        if self.system_prompt:
            messages.append(ChatMessage(role="system", content=self.system_prompt))
        
        # Add conversation history
        history = self.memory.get_conversation_history()
        for msg in history:
            messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
        
        # Add current task
        messages.append(ChatMessage(role="user", content=task))
        
        return messages


class CodeAgent(MultiStepAgent):
    """Agent that thinks in code and executes Python code."""
    
    def __init__(self, 
                 model: Model,
                 tools: Optional[List[Union[BaseTool, str]]] = None,
                 system_prompt: str = "",
                 max_steps: int = 10,
                 stream_outputs: bool = False,
                 executor: Optional[LocalPythonExecutor] = None,
                 preview_mode: bool = True):
        super().__init__(model, tools, system_prompt, max_steps, stream_outputs)
        
        # Use preview executor if preview_mode is enabled (default: True)
        if preview_mode:
            from .executor import PreviewExecutor
            self.executor = PreviewExecutor()
        else:
            self.executor = executor or LocalPythonExecutor()
        
        self.preview_mode = preview_mode  # ← Now defaults to True (safe mode)
        self._setup_executor()
    
    def _setup_executor(self):
        """Setup the executor with available tools."""
        # Add tools to executor variables
        for tool in self.tools:
            self.executor.set_variable(tool.name, self._create_tool_function(tool))
    
    def _create_tool_function(self, tool: BaseTool):
        """Create a function wrapper for a tool."""
        def tool_function(*args, **kwargs):
            try:
                # Convert positional args to keyword args based on tool inputs
                if args and not kwargs:
                    # Get the first parameter name from the tool
                    param_names = list(tool.inputs.keys())
                    if len(args) == 1 and len(param_names) == 1:
                        kwargs[param_names[0]] = args[0]
                    elif len(args) == len(param_names):
                        for i, arg in enumerate(args):
                            kwargs[param_names[i]] = arg
                    else:
                        # For tools that expect specific keyword arguments, try to map them
                        if len(args) == 1 and 'repo' in param_names:
                            kwargs['repo'] = args[0]
                        elif len(args) == 2 and 'repo' in param_names and 'branch' in param_names:
                            kwargs['repo'] = args[0]
                            kwargs['branch'] = args[1]
                
                validate_tool_arguments(tool, kwargs)
                result = tool.execute(**kwargs)
                return result
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return f"Error executing {tool.name}: {str(e)}"
        
        return tool_function
    
    def _create_code_prompt(self, task: str) -> List[ChatMessage]:
        """Create system prompt for code execution."""
        prompt = f"""You are an AI agent that can execute Python code to solve tasks.

Task: {task}

You can use Python to:
- Execute system commands using subprocess
- Analyze files and data
- Perform calculations and data processing
- Monitor system performance
- Debug issues

Available tools in the executor:
"""
        
        # Add available tools
        for tool in self.tools:
            prompt += f"- {tool.name}: {tool.description}\n"
        
        prompt += """
Instructions:
1. Think step by step about what needs to be done
2. Write Python code to accomplish the task
3. Use subprocess to run system commands when needed
4. Provide clear output and analysis
5. Use final_answer() to provide the final result

Example:
```python
import subprocess
import json

# Check system performance
result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
print("System Performance:")
print(result.stdout)

final_answer("System performance check completed. See output above.")
```

Now solve the task: {task}
"""
        
        return [ChatMessage(role="system", content=prompt)]
    
    def run(self, task: str, **kwargs) -> Union[RunResult, Generator[Dict[str, Any], None, None]]:
        """Run the code agent on a task."""
        if self.stream_outputs:
            return self._run_streaming(task, **kwargs)
        else:
            return self._run_non_streaming(task, **kwargs)
    
    def _run_streaming(self, task: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Run the agent in streaming mode."""
        start_time = time.time()
        
        # Initialize memory
        self.memory.clear()
        self.memory.add_task(task)
        
        # Create system prompt
        if not self.system_prompt:
            self.system_prompt = create_system_prompt(self.tools, task)
        
        step_count = 0
        final_answer = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.info(f"Step {step_count}/{self.max_steps}")
            
            # Generate response
            messages = [ChatMessage(role="system", content=self.system_prompt), 
                       ChatMessage(role="user", content=task)]
            
            try:
                # Streaming mode
                response_chunks = []
                for chunk in self.model.generate_stream(messages):
                    response_chunks.append(chunk)
                    yield {"type": "stream", "content": chunk}
                
                response = "".join(response_chunks)
                
                # Parse response
                parsed = parse_agent_response(response)
                
                # Add thought to memory
                if parsed['thought']:
                    self.memory.add_thought(parsed['thought'])
                
                # Execute code if present
                if parsed['code']:
                    self.memory.add_action(f"Executing code: {truncate_text(parsed['code'], 100)}")
                    
                    try:
                        result, output = self.executor.execute(parsed['code'])
                        self.memory.add_observation(f"Code output: {output}")
                        yield {"type": "code_output", "content": output}
                    
                    except Exception as e:
                        error_msg = f"Code execution error: {str(e)}"
                        logger.error(f"Code execution failed. Code was:\n{parsed['code']}\nError: {str(e)}")
                        self.memory.add_observation(error_msg)
                        yield {"type": "error", "content": error_msg}
                
                # Check for final answer
                if parsed['final_answer']:
                    if parsed['final_answer'].startswith('VARIABLE_CALL:'):
                        # Extract variable name and get its value from executor
                        var_name = parsed['final_answer'].split(':', 1)[1]
                        try:
                            var_value = self.executor.get_variable(var_name)
                            if var_value:
                                final_answer = str(var_value)
                                self.memory.add_final_answer(final_answer)
                                break
                        except:
                            pass
                    elif parsed['final_answer'].startswith('CONCAT_CALL:'):
                        # Handle concatenation calls like "text" + str(variable)
                        parts = parsed['final_answer'].split(':', 2)
                        if len(parts) == 3:
                            text_part = parts[1]
                            var_name = parts[2]
                            try:
                                var_value = self.executor.get_variable(var_name)
                                if var_value:
                                    final_answer = text_part + str(var_value)
                                    self.memory.add_final_answer(final_answer)
                                    break
                            except:
                                pass
                    else:
                        final_answer = parsed['final_answer']
                        self.memory.add_final_answer(final_answer)
                        break
                
                # If no final answer and no code, assume we're done
                if not parsed['code'] and not parsed['thought']:
                    break
                
            except Exception as e:
                error_msg = f"Step {step_count} failed: {str(e)}"
                logger.error(error_msg)
                self.memory.add_observation(error_msg)
                yield {"type": "error", "content": error_msg}
                break
        
        # Create result
        duration = time.time() - start_time
        result = RunResult(
            answer=final_answer or "No final answer provided",
            steps=self.memory.steps,
            memory=self.memory,
            duration=duration,
            token_usage=self.memory.token_usage.__dict__
        )
        
        yield {"type": "final", "result": result}
    
    def _run_non_streaming(self, task: str, **kwargs) -> RunResult:
        """Run the agent in non-streaming mode."""
        start_time = time.time()
        
        # Initialize memory
        self.memory.clear()
        self.memory.add_task(task)
        
        # Create system prompt
        if not self.system_prompt:
            self.system_prompt = create_system_prompt(self.tools, task)
        
        step_count = 0
        final_answer = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.info(f"Step {step_count}/{self.max_steps}")
            
            # Generate response
            messages = [ChatMessage(role="system", content=self.system_prompt), 
                       ChatMessage(role="user", content=task)]
            
            try:
                # Non-streaming mode
                model_response = self.model.generate(messages)
                response = model_response.content
                
                # Parse response
                parsed = parse_agent_response(response)
                
                # Add thought to memory
                if parsed['thought']:
                    self.memory.add_thought(parsed['thought'])
                
                # Execute code if present
                if parsed['code']:
                    self.memory.add_action(f"Executing code: {truncate_text(parsed['code'], 100)}")
                    
                    try:
                        result, output = self.executor.execute(parsed['code'])
                        self.memory.add_observation(f"Code output: {output}")
                    
                    except Exception as e:
                        error_msg = f"Code execution error: {str(e)}"
                        logger.error(f"Code execution failed. Code was:\n{parsed['code']}\nError: {str(e)}")
                        self.memory.add_observation(error_msg)
                
                # Check for final answer
                if parsed['final_answer']:
                    if parsed['final_answer'].startswith('VARIABLE_CALL:'):
                        # Extract variable name and get its value from executor
                        var_name = parsed['final_answer'].split(':', 1)[1]
                        try:
                            var_value = self.executor.get_variable(var_name)
                            if var_value:
                                final_answer = str(var_value)
                                self.memory.add_final_answer(final_answer)
                                break
                        except:
                            pass
                    elif parsed['final_answer'].startswith('CONCAT_CALL:'):
                        # Handle concatenation calls like "text" + str(variable)
                        parts = parsed['final_answer'].split(':', 2)
                        if len(parts) == 3:
                            text_part = parts[1]
                            var_name = parts[2]
                            try:
                                var_value = self.executor.get_variable(var_name)
                                if var_value:
                                    final_answer = text_part + str(var_value)
                                    self.memory.add_final_answer(final_answer)
                                    break
                            except:
                                pass
                    else:
                        final_answer = parsed['final_answer']
                        self.memory.add_final_answer(final_answer)
                        break
                
                # If no final answer and no code, assume we're done
                if not parsed['code'] and not parsed['thought']:
                    # If we've been running for a while without progress, try to extract a final answer
                    if step_count >= 2:
                        # Look for any text that might be a final answer
                        final_text_match = re.search(r'Final answer:\s*(.*?)(?:\n|$)', response, re.IGNORECASE)
                        if final_text_match:
                            final_answer = final_text_match.group(1).strip()
                            self.memory.add_final_answer(final_answer)
                            break
                    break
                
            except Exception as e:
                error_msg = f"Step {step_count} failed: {str(e)}"
                logger.error(error_msg)
                self.memory.add_observation(error_msg)
                break
        
        # Create result
        duration = time.time() - start_time
        result = RunResult(
            answer=final_answer or "No final answer provided",
            steps=self.memory.steps,
            memory=self.memory,
            duration=duration,
            token_usage=self.memory.token_usage.__dict__
        )
        
        return result


class ToolCallingAgent(MultiStepAgent):
    """Traditional agent using tool calling methods."""
    
    def __init__(self, 
                 model: Model,
                 tools: Optional[List[Union[BaseTool, str]]] = None,
                 system_prompt: str = "",
                 max_steps: int = 10,
                 stream_outputs: bool = False):
        super().__init__(model, tools, system_prompt, max_steps, stream_outputs)
    
    def run(self, task: str, **kwargs) -> Union[RunResult, Generator[Dict[str, Any], None, None]]:
        """Run the tool calling agent on a task."""
        if self.stream_outputs:
            return self._run_streaming_tool_calling(task, **kwargs)
        else:
            return self._run_non_streaming_tool_calling(task, **kwargs)
    
    def _run_streaming_tool_calling(self, task: str, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Run the tool calling agent in streaming mode."""
        start_time = time.time()
        
        # Initialize memory
        self.memory.clear()
        self.memory.add_task(task)
        
        # Create system prompt for code execution
        if not self.system_prompt:
            self.system_prompt = create_system_prompt(self.tools, task)
        
        step_count = 0
        final_answer = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.info(f"Step {step_count}/{self.max_steps}")
            
            # Generate response
            messages = [ChatMessage(role="system", content=self.system_prompt), 
                       ChatMessage(role="user", content=task)]
            
            try:
                # Streaming mode
                response_chunks = []
                for chunk in self.model.generate_stream(messages):
                    response_chunks.append(chunk)
                    yield {"type": "stream", "content": chunk}
                
                response = "".join(response_chunks)
                
                # Parse tool calls from response
                tool_calls = self._parse_tool_calls(response)
                
                # Execute tool calls
                tools_executed = False
                for tool_call in tool_calls:
                    tools_executed = True
                    tool_name = tool_call['tool']
                    tool_args = tool_call['args']
                    
                    # Find tool
                    tool = None
                    for t in self.tools:
                        if t.name == tool_name:
                            tool = t
                            break
                    
                    if tool is None:
                        error_msg = f"Tool '{tool_name}' not found"
                        self.memory.add_observation(error_msg)
                        continue
                    
                    # Execute tool
                    try:
                        result = tool.execute(**tool_args)
                        self.memory.add_action(f"Used {tool_name}: {result}")
                        
                        yield {"type": "tool_result", "tool": tool_name, "result": result}
                        
                        # If this is a final_answer tool, we're done
                        if tool_name == 'final_answer':
                            final_answer = result
                            self.memory.add_final_answer(final_answer)
                            break
                    
                    except Exception as e:
                        error_msg = f"Tool '{tool_name}' execution failed: {str(e)}"
                        self.memory.add_observation(error_msg)
                        yield {"type": "error", "content": error_msg}
                
                # Check if we already found a final answer
                if final_answer:
                    break
                
                # Check for final answer in tool calls first
                final_answer_found = False
                for tool_call in tool_calls:
                    if tool_call['tool'] == 'final_answer':
                        try:
                            final_answer = tool_call['args'].get('answer', 'No answer provided')
                            self.memory.add_final_answer(final_answer)
                            final_answer_found = True
                            break
                        except:
                            # If JSON parsing failed, try to extract from the raw response
                            extracted_answer = self._extract_final_answer_from_text(response)
                            if extracted_answer != "No answer could be extracted":
                                final_answer = extracted_answer
                                self.memory.add_final_answer(final_answer)
                                final_answer_found = True
                                break
                
                if final_answer_found:
                    break
                
                # If no tools were executed and no final answer, check if we should break
                if not tools_executed:
                    # Check if the response contains a final answer pattern
                    if "final_answer" in response.lower():
                        # Extract the actual answer from the final_answer call
                        
                        # Fallback: try to extract from response text
                        final_match = re.search(r'Arguments:\s*\{\s*"answer":\s*"([^"]+)"', response)
                        if final_match:
                            final_answer = final_match.group(1)
                        else:
                            # Look for any final_answer pattern
                            final_match = re.search(r'final_answer\s*\(\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
                            if final_match:
                                final_answer = final_match.group(1)
                            else:
                                final_answer = "Final answer provided but could not extract content"
                        
                        self.memory.add_final_answer(final_answer)
                        break
                    else:
                        # If we've been running for a while without progress, break
                        if step_count >= 3:
                            final_answer = "Task completed but no final answer was provided"
                            self.memory.add_final_answer(final_answer)
                            break
                
                # Add a safety check to prevent infinite loops
                # If we've executed the same tools multiple times without progress, break
                if step_count >= 5:
                    # Check if we have any results from tools
                    tool_results = [step for step in self.memory.steps if hasattr(step, 'step_type') and step.step_type.value == 'action' and hasattr(step, 'action') and 'Used' in step.action]
                    if tool_results:
                        # Use the last tool result as the answer
                        last_result = tool_results[-1].action
                        # Extract the actual analysis from parse_logs results
                        if 'parse_logs' in last_result:
                            # Parse the JSON result from parse_logs
                            try:
                                import json
                                logs_data = last_result.split('Used parse_logs: ')[1]
                                analysis = json.loads(logs_data)
                                
                                # Create a formatted summary
                                summary = f"📊 Log Analysis Summary:\n\n"
                                summary += f"• Total entries analyzed: {analysis['summary']['total_entries']}\n"
                                summary += f"• Analysis window: {analysis['analysis_window']['duration_minutes']} minutes\n"
                                
                                # Handle different log types - check if error analysis has rates
                                if 'error_4xx_rate' in analysis['error_analysis'] and 'error_5xx_rate' in analysis['error_analysis']:
                                    summary += f"• 4xx Client Error Rate: {analysis['error_analysis']['error_4xx_rate']}%\n"
                                    summary += f"• 5xx Server Error Rate: {analysis['error_analysis']['error_5xx_rate']}%\n"
                                else:
                                    # For syslog/security logs, show security events instead
                                    if 'total_security_events' in analysis['security_analysis']:
                                        summary += f"• Total security events: {analysis['security_analysis']['total_security_events']}\n"
                                        if analysis['security_analysis']['security_events']:
                                            top_threat = analysis['security_analysis']['security_events'][0]
                                            summary += f"• Primary threat: {top_threat['pattern']} ({top_threat['count']} occurrences)\n"
                                
                                summary += f"• Security threat level: {analysis['security_analysis']['threat_level']}\n\n"
                                summary += f"🔧 Detailed Recommendations:\n\n"
                                for rec in analysis['devops_recommendations']:
                                    summary += f"{rec}\n\n"
                                
                                final_answer = summary
                            except:
                                final_answer = f"Task completed. {last_result}"
                        # Handle CI/CD debugger tool results
                        elif any(cicd_tool in last_result for cicd_tool in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']):
                            # Extract the CI/CD tool result
                            for cicd_tool in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']:
                                if f'Used {cicd_tool}:' in last_result:
                                    cicd_result = last_result.split(f'Used {cicd_tool}: ')[1]
                                    final_answer = cicd_result
                                    break
                            else:
                                final_answer = f"Task completed. {last_result}"
                        # Handle system monitor tool results
                        elif 'system_monitor' in last_result:
                            # Extract the system monitor result
                            if 'Used system_monitor:' in last_result:
                                monitor_result = last_result.split('Used system_monitor: ')[1]
                                final_answer = monitor_result
                            else:
                                final_answer = f"Task completed. {last_result}"
                        else:
                            final_answer = f"Task completed. {last_result}"
                    else:
                        final_answer = "Task completed but no final answer was provided"
                    self.memory.add_final_answer(final_answer)
                    break
                
            except Exception as e:
                error_msg = f"Step {step_count} failed: {str(e)}"
                logger.error(error_msg)
                self.memory.add_observation(error_msg)
                yield {"type": "error", "content": error_msg}
                break
        
        # Create result
        duration = time.time() - start_time
        result = RunResult(
            answer=final_answer or "No final answer provided",
            steps=self.memory.steps,
            memory=self.memory,
            duration=duration,
            token_usage=self.memory.token_usage.__dict__
        )
        
        yield {"type": "final", "result": result}
    
    def _run_non_streaming_tool_calling(self, task: str, **kwargs) -> RunResult:
        """Run the tool calling agent in non-streaming mode."""
        start_time = time.time()
        
        # Initialize memory
        self.memory.clear()
        self.memory.add_task(task)
        
        # Create system prompt for code execution
        if not self.system_prompt:
            self.system_prompt = create_system_prompt(self.tools, task)
        
        step_count = 0
        final_answer = None
        
        while step_count < self.max_steps:
            step_count += 1
            logger.info(f"Step {step_count}/{self.max_steps}")
            
            # Generate response
            messages = [ChatMessage(role="system", content=self.system_prompt), 
                       ChatMessage(role="user", content=task)]
            
            try:
                # Non-streaming mode
                model_response = self.model.generate(messages)
                response = model_response.content
                
                # Parse tool calls from response
                tool_calls = self._parse_tool_calls(response)
                
                # Execute tool calls
                tools_executed = False
                for tool_call in tool_calls:
                    tools_executed = True
                    tool_name = tool_call['tool']
                    tool_args = tool_call['args']
                    
                    # Find tool
                    tool = None
                    for t in self.tools:
                        if t.name == tool_name:
                            tool = t
                            break
                    
                    if tool is None:
                        error_msg = f"Tool '{tool_name}' not found"
                        self.memory.add_observation(error_msg)
                        continue
                    
                    # Execute tool
                    try:
                        # Pass model to CI/CD tools for enhanced analysis
                        if tool_name in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']:
                            tool_args['model'] = self.model
                        
                        result = tool.execute(**tool_args)
                        self.memory.add_action(f"Used {tool_name}: {result}")
                        
                        # If this is a final_answer tool, we're done
                        if tool_name == 'final_answer':
                            # Include parse_logs results in the final answer if available
                            parse_logs_results = [step for step in self.memory.steps if hasattr(step, 'action') and 'parse_logs' in step.action and 'Used' in step.action]
                            if parse_logs_results:
                                logs_analysis = parse_logs_results[-1].action.split('Used parse_logs: ')[1] if 'Used parse_logs: ' in parse_logs_results[-1].action else ""
                                # Parse the JSON and format it nicely
                                try:
                                    import json
                                    analysis = json.loads(logs_analysis)
                                    
                                    # Create a formatted summary
                                    summary = f"📊 Log Analysis Summary:\n\n"
                                    summary += f"• Total entries analyzed: {analysis['summary']['total_entries']}\n"
                                    summary += f"• Analysis window: {analysis['analysis_window']['duration_minutes']} minutes\n"
                                    summary += f"• 4xx Client Error Rate: {analysis['error_analysis']['error_4xx_rate']}%\n"
                                    summary += f"• 5xx Server Error Rate: {analysis['error_analysis']['error_5xx_rate']}%\n"
                                    summary += f"• Security threat level: {analysis['security_analysis']['threat_level']}\n\n"
                                    summary += f"🔧 Detailed Recommendations:\n\n"
                                    for rec in analysis['devops_recommendations']:
                                        summary += f"{rec}\n\n"
                                    
                                    final_answer = summary
                                except:
                                    final_answer = f"{result}\n\n📊 Log Analysis Results:\n{logs_analysis}"
                            # Include system_monitor results in the final answer if available
                            elif any('system_monitor' in step.action for step in self.memory.steps if hasattr(step, 'action') and 'Used' in step.action):
                                system_monitor_results = [step for step in self.memory.steps if hasattr(step, 'action') and 'system_monitor' in step.action and 'Used' in step.action]
                                if system_monitor_results:
                                    monitor_data = system_monitor_results[-1].action.split('Used system_monitor: ')[1] if 'Used system_monitor: ' in system_monitor_results[-1].action else ""
                                    final_answer = monitor_data
                                else:
                                    final_answer = result
                            else:
                                final_answer = result
                            self.memory.add_final_answer(final_answer)
                            break
                    
                    except Exception as e:
                        error_msg = f"Tool '{tool_name}' execution failed: {str(e)}"
                        self.memory.add_observation(error_msg)
                
                # Check if we already found a final answer
                if final_answer:
                    break
                
                # Check for final answer in tool calls first
                final_answer_found = False
                for tool_call in tool_calls:
                    if tool_call['tool'] == 'final_answer':
                        try:
                            final_answer = tool_call['args'].get('answer', 'No answer provided')
                            self.memory.add_final_answer(final_answer)
                            final_answer_found = True
                            break
                        except:
                            # If JSON parsing failed, try to extract from the raw response
                            extracted_answer = self._extract_final_answer_from_text(response)
                            if extracted_answer != "No answer could be extracted":
                                final_answer = extracted_answer
                                self.memory.add_final_answer(final_answer)
                                final_answer_found = True
                                break
                
                if final_answer_found:
                    break
                
                # If no tools were executed and no final answer, check if we should break
                if not tools_executed:
                    # Check if the response contains a final answer pattern
                    if "final_answer" in response.lower():
                        # Extract the actual answer from the final_answer call
                        
                        # Fallback: try to extract from response text
                        final_match = re.search(r'Arguments:\s*\{\s*"answer":\s*"([^"]+)"', response)
                        if final_match:
                            final_answer = final_match.group(1)
                        else:
                            # Look for any final_answer pattern
                            final_match = re.search(r'final_answer\s*\(\s*["\']([^"\']+)["\']', response, re.IGNORECASE)
                            if final_match:
                                final_answer = final_match.group(1)
                            else:
                                final_answer = "Final answer provided but could not extract content"
                        
                        self.memory.add_final_answer(final_answer)
                        break
                    else:
                        # If we've been running for a while without progress, break
                        if step_count >= 3:
                            final_answer = "Task completed but no final answer was provided"
                            self.memory.add_final_answer(final_answer)
                            break
                
                # Add a safety check to prevent infinite loops
                # If we've executed the same tools multiple times without progress, break
                if step_count >= 5:
                    # Check if we have any results from tools
                    tool_results = [step for step in self.memory.steps if hasattr(step, 'step_type') and step.step_type.value == 'action' and hasattr(step, 'action') and 'Used' in step.action]
                    if tool_results:
                        # Use the last tool result as the answer
                        last_result = tool_results[-1].action
                        # Extract the actual analysis from parse_logs results
                        if 'parse_logs' in last_result:
                            # Parse the JSON result from parse_logs
                            try:
                                import json
                                logs_data = last_result.split('Used parse_logs: ')[1]
                                analysis = json.loads(logs_data)
                                
                                # Create a formatted summary
                                summary = f"📊 Log Analysis Summary:\n\n"
                                summary += f"• Total entries analyzed: {analysis['summary']['total_entries']}\n"
                                summary += f"• Analysis window: {analysis['analysis_window']['duration_minutes']} minutes\n"
                                
                                # Handle different log types - check if error analysis has rates
                                if 'error_4xx_rate' in analysis['error_analysis'] and 'error_5xx_rate' in analysis['error_analysis']:
                                    summary += f"• 4xx Client Error Rate: {analysis['error_analysis']['error_4xx_rate']}%\n"
                                    summary += f"• 5xx Server Error Rate: {analysis['error_analysis']['error_5xx_rate']}%\n"
                                else:
                                    # For syslog/security logs, show security events instead
                                    if 'total_security_events' in analysis['security_analysis']:
                                        summary += f"• Total security events: {analysis['security_analysis']['total_security_events']}\n"
                                        if analysis['security_analysis']['security_events']:
                                            top_threat = analysis['security_analysis']['security_events'][0]
                                            summary += f"• Primary threat: {top_threat['pattern']} ({top_threat['count']} occurrences)\n"
                                
                                summary += f"• Security threat level: {analysis['security_analysis']['threat_level']}\n\n"
                                summary += f"🔧 Detailed Recommendations:\n\n"
                                for rec in analysis['devops_recommendations']:
                                    summary += f"{rec}\n\n"
                                
                                final_answer = summary
                            except:
                                final_answer = f"Task completed. {last_result}"
                        # Handle CI/CD debugger tool results
                        elif any(cicd_tool in last_result for cicd_tool in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']):
                            # Extract the CI/CD tool result
                            for cicd_tool in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']:
                                if f'Used {cicd_tool}:' in last_result:
                                    cicd_result = last_result.split(f'Used {cicd_tool}: ')[1]
                                    final_answer = cicd_result
                                    break
                            else:
                                final_answer = f"Task completed. {last_result}"
                        # Handle system monitor tool results
                        elif 'system_monitor' in last_result:
                            # Extract the system monitor result
                            if 'Used system_monitor:' in last_result:
                                monitor_result = last_result.split('Used system_monitor: ')[1]
                                final_answer = monitor_result
                            else:
                                final_answer = f"Task completed. {last_result}"
                        else:
                            final_answer = f"Task completed. {last_result}"
                    else:
                        final_answer = "Task completed but no final answer was provided"
                    self.memory.add_final_answer(final_answer)
                    break
                
            except Exception as e:
                error_msg = f"Step {step_count} failed: {str(e)}"
                logger.error(error_msg)
                self.memory.add_observation(error_msg)
                break
        
        # Create result
        duration = time.time() - start_time
        result = RunResult(
            answer=final_answer or "No final answer provided",
            steps=self.memory.steps,
            memory=self.memory,
            duration=duration,
            token_usage=self.memory.token_usage.__dict__
        )
        
        return result
    
    def _create_tool_calling_prompt(self, task: str) -> List[ChatMessage]:
        """Create system prompt for tool calling."""
        prompt = """You are an AI agent that can use tools to solve tasks.

Available tools:
"""
        
        for tool in self.tools:
            prompt += f"- {tool.name}: {tool.description}\n"
            if tool.inputs:
                prompt += "  Inputs:\n"
                for input_name, input_spec in tool.inputs.items():
                    prompt += f"    - {input_name} ({input_spec.get('type', 'string')}): {input_spec.get('description', 'No description')}\n"
        
        prompt += f"""
Task: {task}

Instructions:
1. Think about what tools you need to use to solve the task
2. Use the tools by calling them with appropriate arguments
3. IMPORTANT: After using the tools and getting results, you MUST call the final_answer tool to provide the complete solution to the user

IMPORTANT: When using tools, you MUST format your response exactly like this:

Use tool: tool_name
Arguments: {{"arg1": "value1", "arg2": "value2"}}

Examples:

Use tool: system_monitor
Arguments: {{"command": "all"}}

Use tool: final_answer
Arguments: {{"answer": "The result is 4"}}

CRITICAL RULES:
- Use the exact tool names as listed above
- Provide all required arguments for each tool
- ALWAYS call final_answer when you have the complete solution
- Use proper JSON format for arguments (no trailing commas, proper quotes)
- Do not repeat the same tool calls multiple times
- Keep the final_answer text concise and complete
- For system monitoring tasks, ALWAYS use system_monitor tool first

Let's solve this step by step.
"""
        
        return [ChatMessage(role="system", content=prompt)]
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from response."""
        tool_calls = []
        
        # Split response into lines and look for tool call patterns
        lines = response.split('\n')
        current_tool = None
        current_args = {}
        
        for line in lines:
            line = line.strip()
            
            # Look for various tool call patterns
            if (line.startswith('Use tool:') or 
                line.startswith('Tool:') or 
                'parse_logs' in line.lower() or
                'web_search' in line.lower() or
                'system_monitor' in line.lower()):
                
                # Save previous tool call if exists
                if current_tool:
                    tool_calls.append({
                        'tool': current_tool,
                        'args': current_args
                    })
                
                # Extract tool name - be more flexible
                if 'parse_logs' in line.lower():
                    current_tool = 'parse_logs'
                elif 'web_search' in line.lower():
                    current_tool = 'web_search'
                elif 'system_monitor' in line.lower():
                    current_tool = 'system_monitor'
                elif 'final_answer' in line.lower():
                    current_tool = 'final_answer'
                elif ':' in line:
                    current_tool = line.split(':', 1)[1].strip()
                else:
                    # Try to extract from the line
                    for tool_name in ['parse_logs', 'web_search', 'system_monitor', 'final_answer']:
                        if tool_name in line:
                            current_tool = tool_name
                            break
                
                current_args = {}
            
            # Look for "Arguments:" pattern or JSON-like arguments
            elif (line.startswith('Arguments:') or 
                  line.startswith('{') or 
                  'path:' in line.lower() or
                  'window_minutes:' in line.lower()) and current_tool:
                # Always use robust regex extraction instead of trying JSON parsing first
                current_args = self._extract_args_with_regex(line, current_tool)
        
        # Add the last tool call
        if current_tool:
            tool_calls.append({
                'tool': current_tool,
                'args': current_args
            })
        
        # If no tool calls found but parse_logs is mentioned, create a default call
        if not tool_calls and 'parse_logs' in response.lower():
            tool_calls.append({
                'tool': 'parse_logs',
                'args': {'path': 'nginx_access.log', 'window_minutes': 600}
            })
        
        # If no tool calls found but system_monitor is mentioned, create a default call
        if not tool_calls and 'system_monitor' in response.lower():
            tool_calls.append({
                'tool': 'system_monitor',
                'args': {'command': 'all'}
            })
        
        return tool_calls
    
    def _parse_simple_args(self, args_str: str) -> Dict[str, Any]:
        """Parse simple argument format like 'expression: "2 + 2"'."""
        args = {}
        try:
            # Look for key: value patterns
            matches = re.findall(r'(\w+):\s*"([^"]*)"', args_str)
            for key, value in matches:
                args[key] = value
        except:
            pass
        return args
    
    def _extract_args_with_regex(self, line: str, tool_name: str) -> Dict[str, Any]:
        """Extract tool arguments using robust regex patterns."""
        if tool_name == 'web_search':
            # Try multiple patterns for web_search
            patterns = [
                r'"query":\s*"([^"]*)"',
                r'query":\s*"([^"]*)',
                r'query":\s*"([^"]*)(?:.*)'
            ]
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    return {'query': match.group(1)}
        
        elif tool_name == 'parse_logs':
            # Try to extract parse_logs arguments
            try:
                # Look for JSON-like arguments
                json_match = re.search(r'Arguments:\s*(\{.*?\})', line, re.DOTALL)
                if json_match:
                    import json
                    args_str = json_match.group(1)
                    return json.loads(args_str)
            except:
                pass
            
            # Fallback: try to extract individual arguments
            args = {}
            path_match = re.search(r'"path":\s*"([^"]*)"', line)
            if path_match:
                args['path'] = path_match.group(1)
            
            window_match = re.search(r'"window_minutes":\s*(\d+)', line)
            if window_match:
                args['window_minutes'] = int(window_match.group(1))
            
            log_type_match = re.search(r'"log_type":\s*"([^"]*)"', line)
            if log_type_match:
                args['log_type'] = log_type_match.group(1)
            
            return args
        
        elif tool_name == 'system_monitor':
            # Try to extract system_monitor arguments
            args = {}
            command_match = re.search(r'"command":\s*"([^"]*)"', line)
            if command_match:
                args['command'] = command_match.group(1)
            else:
                # Default to "all" if no command specified
                args['command'] = 'all'
            return args
        
        elif tool_name == 'final_answer':
            # Try multiple patterns for final_answer
            patterns = [
                r'"answer":\s*"([^"]*)"',
                r'answer":\s*"([^"]*)',
                r'answer":\s*"([^"]*)(?:.*)',
                r'"answer":\s*"([^"]*)(?:.*)'
            ]
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    answer_content = match.group(1)
                    # If the answer seems incomplete, try to get more content
                    if answer_content.endswith('...') or len(answer_content) < 10:
                        # Look for more content after the quote
                        more_content = re.search(r'answer":\s*"[^"]*(.*?)(?:\s*"|$)', line)
                        if more_content:
                            answer_content += more_content.group(1)
                    
                    # If still incomplete, try to construct a complete answer
                    if answer_content.endswith('...'):
                        # Remove the ... and add a reasonable ending
                        answer_content = answer_content.replace('...', '')
                        if 'weather' in answer_content.lower():
                            answer_content += ' (weather information retrieved)'
                        else:
                            answer_content += ' (information retrieved)'
                    
                    return {'answer': answer_content}
        
        # Handle CI/CD debugger tools
        elif tool_name in ['debug_cicd_failure', 'get_cicd_status', 'analyze_cicd_patterns']:
            args = {}
            
            # Extract repo from the line or task context
            repo_match = re.search(r'"repo":\s*"([^"]*)"', line)
            if repo_match:
                args['repo'] = repo_match.group(1)
            else:
                # Try to extract repo from the task context
                repo_patterns = [
                    r'repository\s+([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                    r'repo\s+([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)',
                    r'([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+)'
                ]
                for pattern in repo_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        args['repo'] = match.group(1)
                        break
            
            # Extract branch
            branch_match = re.search(r'"branch":\s*"([^"]*)"', line)
            if branch_match:
                args['branch'] = branch_match.group(1)
            
            # Extract workflow_name
            workflow_match = re.search(r'"workflow_name":\s*"([^"]*)"', line)
            if workflow_match:
                args['workflow_name'] = workflow_match.group(1)
            
            return args
        
        return {}
    
    def _extract_final_answer_from_text(self, text: str) -> str:
        """Extract final answer from text even when JSON parsing fails."""
        
        # Try to extract the answer from various patterns
        patterns = [
            r'Arguments:\s*\{\s*"answer":\s*"([^"]+)"',
            r'final_answer\s*\(\s*["\']([^"\']+)["\']',
            r'"answer":\s*"([^"]+)"',
            r'answer":\s*"([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # If no pattern matches, try to extract any text that looks like an answer
        # Look for text after "answer" or "final_answer"
        answer_match = re.search(r'(?:answer|final_answer).*?["\']([^"\']{10,})["\']', text, re.IGNORECASE)
        if answer_match:
            return answer_match.group(1)
        
        # If still no answer, check if we have system monitor results in memory
        system_monitor_results = [step for step in self.memory.steps if hasattr(step, 'action') and 'system_monitor' in step.action and 'Used' in step.action]
        if system_monitor_results:
            monitor_data = system_monitor_results[-1].action.split('Used system_monitor: ')[1] if 'Used system_monitor: ' in system_monitor_results[-1].action else ""
            return monitor_data
        
        return "No answer could be extracted"


class TriageAgent(ToolCallingAgent):
    """Specialized agent for SRE incident triage and log analysis."""
    
    def __init__(self, 
                 model: Model,
                 tools: Optional[List[Union[BaseTool, str]]] = None,
                 max_steps: int = 8,
                 stream_outputs: bool = True):
        
        # Default system prompt for SRE triage
        system_prompt = """You are an SRE incident triage assistant.
- Use tools to gather evidence before concluding.
- Prefer concise, structured answers with bullet points and short sentences.
- If metrics show 5xx spikes, propose concrete next actions (ex: rollback service X, scale Y, warm cache Z).
- If evidence is insufficient, say what *additional data* you need.
- Focus on actionable insights and immediate response steps.
- Always provide structured recommendations with priority levels (Critical/High/Medium/Low).
- Include immediate actions (0-5 min), short-term actions (5-30 min), and long-term preventive measures."""
        
        # Default tools for triage
        if tools is None:
            tools = ["load_file_head", "parse_logs", "generate_recommendations", "web_search", "final_answer"]
        
        super().__init__(model, tools, system_prompt, max_steps, stream_outputs)
    
    def run(self, task: str, **kwargs) -> Union[RunResult, Generator[Dict[str, Any], None, None]]:
        """Run the triage agent on an incident task."""
        return super().run(task, **kwargs)
