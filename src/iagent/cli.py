#!/usr/bin/env python3
"""
Command-line interface for iagent.
"""

import argparse
import logging
import os
import re
import sys
from typing import Optional

from .agents import CodeAgent, ToolCallingAgent, TriageAgent
from .models import OpenAIModel, LiteLLMModel, HuggingFaceModel
from .tools import WebSearchTool, FinalAnswerTool, get_tool

logger = logging.getLogger(__name__)


def _format_final_answer(answer: str) -> str:
    """Format the final answer with proper line breaks and structure."""
    if not answer:
        return answer
    
    # Split by common patterns and add proper formatting
    lines = []
    
    # Handle numbered lists (1., 2., etc.)
    if '1.' in answer and '2.' in answer:
        # Split by numbered items
        parts = answer.split('1.')
        if len(parts) > 1:
            lines.append(parts[0].strip())  # Add any text before the first item
            remaining = '1.' + parts[1]
            
            # Split by numbered items
            items = re.split(r'(\d+\.)', remaining)
            
            for i in range(0, len(items), 2):
                if i + 1 < len(items):
                    number = items[i].strip()
                    content = items[i + 1].strip()
                    if number and content:
                        lines.append(f"\n{number} {content}")
        else:
            lines.append(answer)
    else:
        # Handle other formatting patterns
        # Split by sentences and add line breaks
        sentences = answer.split('. ')
        for i, sentence in enumerate(sentences):
            if i == len(sentences) - 1:
                lines.append(sentence)
            else:
                lines.append(sentence + '.')
    
    # Join with proper spacing
    formatted = '\n'.join(lines)
    
    # Clean up any double newlines
    formatted = re.sub(r'\n\s*\n', '\n\n', formatted)
    
    return formatted


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_model(model_type: str, model_id: str, **kwargs):
    """Create a model instance based on type."""
    if model_type.lower() == "openai":
        return OpenAIModel(model_id=model_id, **kwargs)
    elif model_type.lower() == "litellm":
        return LiteLLMModel(model_id=model_id, **kwargs)
    elif model_type.lower() == "huggingface":
        return HuggingFaceModel(model_id=model_id, **kwargs)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def get_available_tools():
    """Get list of available tools."""
    return ["web_search", "parse_logs", "final_answer"]


def create_tools(tool_names: list, log_file: Optional[str] = None):
    """Create tool instances from names."""
    tools = []
    for tool_name in tool_names:
        tool = get_tool(tool_name)
        if tool:
            # Special handling for parse_logs tool
            if tool_name == "parse_logs" and log_file:
                # Modify the task to include the log file path
                # This will be handled in the agent execution
                pass
            tools.append(tool)
        else:
            logger.warning(f"Tool '{tool_name}' not found")
    return tools


def run_agent(task: str, 
              model_type: str = "openai",
              model_id: str = "gpt-4o-mini",  # ← Changed to gpt-4o-mini
              agent_type: str = "code",
              tools: Optional[list] = None,
              max_steps: int = 10,
              stream: bool = False,
              verbose: bool = False,
              execute: bool = False,
              log_file: Optional[str] = None,
              **kwargs):
    """Run an agent with the given configuration."""
    
    # Setup logging
    setup_logging(verbose)
    
    try:
        # Create model
        logger.info(f"Creating {model_type} model: {model_id}")
        model = create_model(model_type, model_id, **kwargs)
        
        # Create tools
        if tools is None:
            tools = ["final_answer"]  # Default tools include final answer
        else:
            # Always include final_answer if other tools are specified
            if "final_answer" not in tools:
                tools.append("final_answer")
        
        tool_instances = create_tools(tools, log_file)
        logger.info(f"Using tools: {[t.name for t in tool_instances]}")
        
        # Create agent with execution mode
        # Auto-select agent type based on tools
        if tools and len(tools) > 1:  # If multiple tools or tools other than just final_answer
            agent_type = "tool"  # Use ToolCallingAgent for tool usage
            logger.info(f"Auto-selected agent type: {agent_type} (tools detected)")
        
        if agent_type.lower() == "code":
            # Create executor with proper execution mode
            from iagent.executor import LocalPythonExecutor
            executor = LocalPythonExecutor(dry_run=not execute)  # ← Set dry_run based on execute flag
            
            agent = CodeAgent(
                model=model,
                tools=tool_instances,
                max_steps=max_steps,
                stream_outputs=stream,
                preview_mode=not execute,  # ← Use execute flag to control preview mode
                executor=executor  # ← Pass the properly configured executor
            )
        elif agent_type.lower() == "tool":
            agent = ToolCallingAgent(
                model=model,
                tools=tool_instances,
                max_steps=max_steps,
                stream_outputs=stream
            )
        elif agent_type.lower() == "triage":
            agent = TriageAgent(
                model=model,
                tools=tool_instances,
                max_steps=max_steps,
                stream_outputs=stream
            )
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        # Show execution mode
        if execute:
            print("⚠️  EXECUTION MODE: Code will be executed locally")
        else:
            print("🔒 SAFE MODE: Code will be previewed only (use --execute to run code)")
        
        # Run agent
        # Modify task if parse_logs tool is used with log file
        modified_task = task
        if log_file and "parse_logs" in tools:
            modified_task = f"Use the parse_logs tool to analyze the log file: {log_file}. {task}"
            logger.info(f"Using log file: {log_file}")
        
        logger.info(f"Running {agent_type} agent on task: {modified_task}")
        
        print("🤖 iagent is thinking...\n")
        
        # Handle the agent response
        agent_response = agent.run(modified_task)
        
        # Remove debug output for cleaner display
        import logging
        logging.getLogger('__main__').setLevel(logging.WARNING)
        
        # Check if it's a generator or a result
        if hasattr(agent_response, '__iter__') and not hasattr(agent_response, 'answer'):
            # It's a generator; consume it and capture StopIteration.value for non-stream runs
            gen = agent_response
            final_result = None
            try:
                while True:
                    step = next(gen)
                    if isinstance(step, dict) and "type" in step:
                        if step["type"] == "stream":
                            print(step["content"], end="", flush=True)
                        elif step["type"] == "code_output":
                            print(f"\n📝 Code output: {step['content']}")
                        elif step["type"] == "tool_result":
                            print(f"\n🔧 Tool result: {step['result']}")
                        elif step["type"] == "error":
                            print(f"\n❌ Error: {step['content']}")
                        elif step["type"] == "final":
                            final_result = step["result"]
            except StopIteration as e:
                if getattr(e, "value", None) is not None and final_result is None:
                    final_result = e.value
            if final_result is not None:
                print(f"\n\n✅ Final Answer:")
                print("=" * 60)
                # Format the answer with proper line breaks
                formatted_answer = _format_final_answer(final_result.answer)
                print(formatted_answer)
                print("=" * 60)
                print(f"⏱️  Duration: {final_result.duration:.2f}s")
                print(f"📊 Steps: {len(final_result.steps)}")
            else:
                print("\n\n⚠️ No final result produced.")
        else:
            # It's a result object
            result = agent_response
            print(f"\n\n✅ Final Answer:")
            print("=" * 60)
            # Format the answer with proper line breaks
            formatted_answer = _format_final_answer(result.answer)
            print(formatted_answer)
            print("=" * 60)
            print(f"⏱️  Duration: {result.duration:.2f}s")
            print(f"📊 Steps: {len(result.steps)}")
    
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="🤖 iagent: DevOps AI Agent with Real-time Log Analysis & Troubleshooting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # DevOps troubleshooting with web search
  iagent "How do I troubleshoot Kubernetes pod restarts?" --tools web_search

  # Log analysis with specific log file
  iagent "Analyze nginx logs from the last 10 minutes" --tools parse_logs --log-file /var/log/nginx/access.log

  # CI/CD debugging
  iagent "Debug my GitHub Actions workflow failure" --tools debug_cicd_failure

  # System performance monitoring
  iagent "Monitor system performance" --tools system_monitor

Available Tools:
  web_search         - AI-powered DevOps search and troubleshooting
  parse_logs         - Real-time log analysis (NGINX, syslog, secure logs)
  system_monitor     - Monitor system performance (CPU, memory, disk, processes)
  get_cicd_status    - Get comprehensive status of recent CI/CD workflow runs
  debug_cicd_failure - AI-powered debugging of GitHub Actions workflow failures
  analyze_cicd_patterns - Analyze error patterns across multiple CI/CD runs

Environment Setup:
  export OPENAI_API_KEY="your-api-key"  # Required for web_search and AI features
  export GITHUB_TOKEN="your-github-token"  # Required for CI/CD debugging tools

Safety Note:
  By default, iagent runs in SAFE MODE and does NOT execute code locally.
  Use --execute flag only when you trust the code and understand the risks.
        """
    )
    
    # Required arguments
    parser.add_argument(
        "task",
        help="Task to perform"
    )
    
    # Optional arguments
    parser.add_argument(
        "--model-type",
        default="openai",
        choices=["openai", "litellm", "huggingface"],
        help="Model provider (default: openai)"
    )
    
    parser.add_argument(
        "--model-id",
        default=os.getenv("IAGENT_MODEL_ID", "gpt-4o-mini"),  # ← Changed to gpt-4o-mini
        help="Model ID (default: gpt-4o-mini, or set IAGENT_MODEL_ID env var)"
    )
    
    parser.add_argument(
        "--agent-type",
        default="code",
        choices=["code", "tool", "triage"],
        help="Agent type (auto-selected when tools are used: tool for web_search/parse_nginx, code for general tasks)"
    )
    
    parser.add_argument(
        "--tools",
        nargs="+",
        help="Tools to use"
    )
    
    parser.add_argument(
        "--log-file",
        help="Path to log file for parse_logs tool (e.g., /var/log/nginx/access.log)"
    )
    
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum number of steps (default: 10)"
    )
    
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream output in real-time"
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="⚠️ Execute code locally (default: safe preview mode only)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run agent
    run_agent(
        task=args.task,
        model_type=args.model_type,
        model_id=args.model_id,
        agent_type=args.agent_type,
        tools=args.tools,
        max_steps=args.max_steps,
        stream=args.stream,
        verbose=args.verbose,
        execute=args.execute, # Pass the execute argument
        log_file=args.log_file # Pass the log file argument
    )


if __name__ == "__main__":
    main()
