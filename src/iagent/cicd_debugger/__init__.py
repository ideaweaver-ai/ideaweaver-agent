#!/usr/bin/env python3
"""
CI/CD Pipeline Failure Debugger for iagent.

Automatically monitors failed CI/CD jobs and provides AI-powered debugging assistance.
"""

from .monitor import GitHubWorkflowMonitor
from .fetch_logs import GitHubLogFetcher
from .parser import LogParser, ErrorPattern
from .suggest_fix import FixSuggester
from .notifier import Notifier, NotificationConfig
from .pr_generator import PRGenerator, PRConfig, create_fix_pr
from .debugger import CICDDebugger
from .wrapper import CICDDebuggerWrapper, DebuggerConfig, debug_repo, debug_run

__all__ = [
    'GitHubWorkflowMonitor',
    'GitHubLogFetcher', 
    'LogParser',
    'ErrorPattern',
    'FixSuggester',
    'Notifier',
    'NotificationConfig',
    'CICDDebugger',
    'CICDDebuggerWrapper',
    'DebuggerConfig',
    'debug_repo',
    'debug_run',
    'debug_latest_failure',
    'debug_workflow_run'
]


def debug_latest_failure(repo: str, branch: str = "main", github_token: str = None, 
                        workflow_name: str = None, max_runs: int = 5) -> dict:
    """
    Debug the latest failed workflow run.
    
    Args:
        repo: Repository in format "owner/repo"
        branch: Branch to monitor (default: "main")
        github_token: GitHub personal access token
        workflow_name: Specific workflow name to monitor (optional)
        max_runs: Maximum number of recent runs to check
        
    Returns:
        Dictionary containing debug results
    """
    debugger = CICDDebugger(github_token=github_token)
    return debugger.debug_latest_failure(repo, branch, workflow_name, max_runs)


def debug_workflow_run(repo: str, run_id: int, github_token: str = None) -> dict:
    """
    Debug a specific workflow run by ID.
    
    Args:
        repo: Repository in format "owner/repo"
        run_id: GitHub workflow run ID
        github_token: GitHub personal access token
        
    Returns:
        Dictionary containing debug results
    """
    debugger = CICDDebugger(github_token=github_token)
    return debugger.debug_workflow_run(repo, run_id)
