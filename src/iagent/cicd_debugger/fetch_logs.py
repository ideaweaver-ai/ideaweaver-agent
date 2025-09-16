#!/usr/bin/env python3
"""
GitHub log fetching for CI/CD debugger.
"""

import logging
import os
import requests
import zipfile
import io
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class GitHubLogFetcher:
    """Fetches logs from GitHub workflow runs."""
    
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
    
    def get_job_logs(self, repo: str, job_id: int) -> str:
        """
        Get logs for a specific job.
        
        Args:
            repo: Repository in format "owner/repo"
            job_id: Job ID
            
        Returns:
            Job logs as string
        """
        owner, repo_name = repo.split("/", 1)
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/jobs/{job_id}/logs"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch job logs: {e}")
            raise
    
    def get_workflow_run_logs(self, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Get all logs for a workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            Dictionary containing logs for each job
        """
        owner, repo_name = repo.split("/", 1)
        url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs/{run_id}/logs"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # GitHub returns logs as a zip file
            if response.headers.get('content-type') == 'application/zip':
                return self._extract_logs_from_zip(response.content)
            else:
                # Fallback to individual job logs
                return self._get_individual_job_logs(repo, run_id)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch workflow logs: {e}")
            raise
    
    def _extract_logs_from_zip(self, zip_content: bytes) -> Dict[str, Any]:
        """
        Extract logs from GitHub's zip file response.
        
        Args:
            zip_content: Raw zip file content
            
        Returns:
            Dictionary with job names as keys and log content as values
        """
        logs = {}
        
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith('.txt'):
                        # Extract job name from filename
                        job_name = file_info.filename.replace('.txt', '')
                        with zip_file.open(file_info.filename) as log_file:
                            logs[job_name] = log_file.read().decode('utf-8')
            
            return logs
            
        except zipfile.BadZipFile as e:
            logger.error(f"Failed to extract logs from zip: {e}")
            raise
    
    def _get_individual_job_logs(self, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Get logs for each job individually.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            Dictionary with job names as keys and log content as values
        """
        from .monitor import GitHubWorkflowMonitor
        
        monitor = GitHubWorkflowMonitor(self.github_token)
        jobs = monitor.get_workflow_jobs(repo, run_id)
        
        logs = {}
        for job in jobs:
            job_name = job["name"]
            job_id = job["id"]
            
            try:
                job_logs = self.get_job_logs(repo, job_id)
                logs[job_name] = job_logs
            except Exception as e:
                logger.warning(f"Failed to fetch logs for job {job_name}: {e}")
                logs[job_name] = f"Failed to fetch logs: {e}"
        
        return logs
    
    def get_failed_job_logs(self, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Get logs only for failed jobs in a workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            Dictionary with failed job names as keys and log content as values
        """
        from .monitor import GitHubWorkflowMonitor
        
        monitor = GitHubWorkflowMonitor(self.github_token)
        jobs = monitor.get_workflow_jobs(repo, run_id)
        
        failed_logs = {}
        for job in jobs:
            if job["conclusion"] == "failure":
                job_name = job["name"]
                job_id = job["id"]
                
                try:
                    job_logs = self.get_job_logs(repo, job_id)
                    failed_logs[job_name] = job_logs
                except Exception as e:
                    logger.warning(f"Failed to fetch logs for failed job {job_name}: {e}")
                    failed_logs[job_name] = f"Failed to fetch logs: {e}"
        
        return failed_logs
    
    def get_log_summary(self, logs: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate a summary of the logs.
        
        Args:
            logs: Dictionary of job logs
            
        Returns:
            Summary information about the logs
        """
        summary = {
            "total_jobs": len(logs),
            "total_log_size": sum(len(log) for log in logs.values()),
            "job_names": list(logs.keys()),
            "failed_jobs": [],
            "error_patterns": []
        }
        
        # Look for common error patterns
        for job_name, log_content in logs.items():
            if any(error_indicator in log_content.lower() for error_indicator in 
                   ["error:", "failed", "failure", "exit code", "command not found"]):
                summary["failed_jobs"].append(job_name)
        
        return summary
