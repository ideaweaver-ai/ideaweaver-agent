#!/usr/bin/env python3
"""
Memory management for iagent.

Handles conversation history and step tracking.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of memory steps."""
    TASK = "task"
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"


@dataclass
class TaskStep:
    """Step representing a user task."""
    task: str
    step_type: StepType = field(default=StepType.TASK, init=False)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThoughtStep:
    """Step representing agent reasoning."""
    thought: str
    step_type: StepType = field(default=StepType.THOUGHT, init=False)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionStep:
    """Step representing agent action."""
    action: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    step_type: StepType = field(default=StepType.ACTION, init=False)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObservationStep:
    """Step representing observation result."""
    observation: str
    step_type: StepType = field(default=StepType.OBSERVATION, init=False)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinalAnswerStep:
    """Step representing final answer."""
    answer: str
    step_type: StepType = field(default=StepType.FINAL_ANSWER, init=False)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def add_usage(self, prompt: int = 0, completion: int = 0):
        """Add token usage."""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion


class AgentMemory:
    """Manages agent conversation history and memory."""
    
    def __init__(self, system_prompt: str = ""):
        self.system_prompt = system_prompt
        self.steps: List[Any] = []
        self.token_usage = TokenUsage()
        self.start_time = time.time()
    
    def add_step(self, step: Any):
        """Add a step to memory."""
        self.steps.append(step)
        logger.debug(f"Added {step.step_type.value} step to memory")
    
    def add_task(self, task: str):
        """Add a task step."""
        step = TaskStep(task=task)
        self.add_step(step)
    
    def add_thought(self, thought: str):
        """Add a thought step."""
        step = ThoughtStep(thought=thought)
        self.add_step(step)
    
    def add_action(self, action: str, tool_name: Optional[str] = None, 
                   tool_args: Optional[Dict[str, Any]] = None):
        """Add an action step."""
        step = ActionStep(action=action, tool_name=tool_name, tool_args=tool_args)
        self.add_step(step)
    
    def add_observation(self, observation: str):
        """Add an observation step."""
        step = ObservationStep(observation=observation)
        self.add_step(step)
    
    def add_final_answer(self, answer: str):
        """Add a final answer step."""
        step = FinalAnswerStep(answer=answer)
        self.add_step(step)
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history as list of messages."""
        messages = []
        
        # Add system prompt if exists
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        
        # Add conversation steps
        for step in self.steps:
            if isinstance(step, TaskStep):
                messages.append({"role": "user", "content": step.task})
            elif isinstance(step, ThoughtStep):
                messages.append({"role": "assistant", "content": f"Thought: {step.thought}"})
            elif isinstance(step, ActionStep):
                content = f"Action: {step.action}"
                if step.tool_name:
                    content += f" (using {step.tool_name})"
                messages.append({"role": "assistant", "content": content})
            elif isinstance(step, ObservationStep):
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})
            elif isinstance(step, FinalAnswerStep):
                messages.append({"role": "assistant", "content": f"Final Answer: {step.answer}"})
        
        return messages
    
    def get_last_n_steps(self, n: int) -> List[Any]:
        """Get the last n steps."""
        return self.steps[-n:] if n > 0 else []
    
    def get_steps_by_type(self, step_type: StepType) -> List[Any]:
        """Get all steps of a specific type."""
        return [step for step in self.steps if step.step_type == step_type]
    
    def clear(self):
        """Clear all memory."""
        self.steps.clear()
        self.token_usage = TokenUsage()
        self.start_time = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get memory summary."""
        return {
            "total_steps": len(self.steps),
            "step_types": {step_type.value: len(self.get_steps_by_type(step_type)) 
                          for step_type in StepType},
            "token_usage": {
                "prompt_tokens": self.token_usage.prompt_tokens,
                "completion_tokens": self.token_usage.completion_tokens,
                "total_tokens": self.token_usage.total_tokens
            },
            "duration": time.time() - self.start_time
        }
    
    def __len__(self) -> int:
        """Return number of steps."""
        return len(self.steps)
    
    def __str__(self) -> str:
        """String representation."""
        summary = self.get_summary()
        return f"AgentMemory(steps={summary['total_steps']}, tokens={summary['token_usage']['total_tokens']})"
