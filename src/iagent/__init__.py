#!/usr/bin/env python3
"""
iagent: Intelligent Agents that Think in Code

A powerful library for building AI agents that can execute Python code,
use tools, and interact with various language models.

Built from scratch with inspiration from smolagents architecture.
"""

__version__ = "0.0.1"

# Core agent classes
from .agents import CodeAgent, ToolCallingAgent, MultiStepAgent, TriageAgent
from .models import Model, OpenAIModel, LiteLLMModel, HuggingFaceModel, BedrockModel, ChatMessage
from .tools import Tool, tool, BaseTool, get_tool, list_tools, LoadFileHead, ParseLogs, GenerateRecommendations
from .memory import AgentMemory, StepType
from .executor import PythonExecutor, LocalPythonExecutor

# Utility classes
from .utils import AgentError, AgentExecutionError

__all__ = [
    # Agents
    "CodeAgent",
    "ToolCallingAgent", 
    "MultiStepAgent",
    "TriageAgent",
    
    # Models
    "Model",
    "OpenAIModel",
    "LiteLLMModel",
    "HuggingFaceModel",
    "BedrockModel",
    "ChatMessage",
    
    # Tools
    "Tool",
    "tool",
    "BaseTool",
    "get_tool",
    "list_tools",
    "LoadFileHead",
    "ParseNginx",
    "GenerateRecommendations",
    
    # Memory
    "AgentMemory",
    "StepType",
    
    # Executors
    "PythonExecutor",
    "LocalPythonExecutor",
    
    # Utils
    "AgentError",
    "AgentExecutionError",
]
