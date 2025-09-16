#!/usr/bin/env python3
"""
GitHub workflow monitoring for CI/CD debugger.
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)


class GitHubWorkflowMonitor:
    """Monitors GitHub workflows for failures."""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass it directly.")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "iagent-cicd-debugger"
        })
    
    def get_failed_workflow_runs(self, repo: str, branch: str = "main", 
                                workflow_name: str = None, max_runs: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent failed workflow runs.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name (optional)
            max_runs: Maximum number of runs to fetch
            
        Returns:
            List of failed workflow run data
        """
        owner, repo_name = repo.split("/", 1)
        
        # Build API URL
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs"
        params = {
            "status": "failure",
            "branch": branch,
            "per_page": min(max_runs, 100)
        }
        
        if workflow_name:
            # First get workflow ID
            workflow_id = self._get_workflow_id(owner, repo_name, workflow_name)
            if workflow_id:
                params["workflow_id"] = workflow_id
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            runs_data = response.json()
            failed_runs = []
            
            for run in runs_data.get("workflow_runs", []):
                if run["conclusion"] == "failure":
                    failed_runs.append({
                        "id": run["id"],
                        "name": run["name"],
                        "head_branch": run["head_branch"],
                        "head_sha": run["head_sha"],
                        "created_at": run["created_at"],
                        "updated_at": run["updated_at"],
                        "conclusion": run["conclusion"],
                        "status": run["status"],
                        "workflow_id": run["workflow_id"],
                        "html_url": run["html_url"]
                    })
            
            return failed_runs[:max_runs]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch workflow runs: {e}")
            raise
    
    def get_workflow_run_details(self, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            Workflow run details
        """
        owner, repo_name = repo.split("/", 1)
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs/{run_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch workflow run details: {e}")
            raise
    
    def get_workflow_jobs(self, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """
        Get jobs for a specific workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            List of job data
        """
        owner, repo_name = repo.split("/", 1)
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs/{run_id}/jobs"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            jobs_data = response.json()
            return jobs_data.get("jobs", [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch workflow jobs: {e}")
            raise
    
    def _get_workflow_id(self, owner: str, repo_name: str, workflow_name: str) -> Optional[int]:
        """Get workflow ID by name."""
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/workflows"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            workflows = response.json().get("workflows", [])
            for workflow in workflows:
                if workflow["name"] == workflow_name:
                    return workflow["id"]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch workflows: {e}")
            return None
    
    def get_latest_failed_run(self, repo: str, branch: str = "main", 
                             workflow_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Get the most recent failed workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name (optional)
            
        Returns:
            Latest failed run data or None
        """
        failed_runs = self.get_failed_workflow_runs(repo, branch, workflow_name, max_runs=1)
        return failed_runs[0] if failed_runs else None
