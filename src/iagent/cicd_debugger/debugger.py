#!/usr/bin/env python3
"""
Main CI/CD debugger orchestrator.
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from .monitor import GitHubWorkflowMonitor
from .fetch_logs import GitHubLogFetcher
from .parser import LogParser
from .suggest_fix import FixSuggester
from .notifier import Notifier, NotificationConfig
from .pr_generator import PRConfig

logger = logging.getLogger(__name__)


class CICDDebugger:
    """Main CI/CD debugger that orchestrates all components."""
    
    def __init__(self, github_token: str = None, model=None, notification_config: NotificationConfig = None, readonly_mode: bool = True):
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass it directly.")
        
        # Initialize components
        self.monitor = GitHubWorkflowMonitor(self.github_token)
        self.log_fetcher = GitHubLogFetcher(self.github_token)
        self.parser = LogParser()
        self.fix_suggester = FixSuggester(model, readonly_mode=readonly_mode)
        self.notifier = Notifier(notification_config)
        self.readonly_mode = readonly_mode
    
    def debug_latest_failure(self, repo: str, branch: str = "main", 
                           workflow_name: str = None, max_runs: int = 5) -> Dict[str, Any]:
        """
        Debug the latest failed workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor (default: "main")
            workflow_name: Specific workflow name to monitor (optional)
            max_runs: Maximum number of recent runs to check
            
        Returns:
            Dictionary containing debug results
        """
        try:
            # Get the latest failed run
            failed_run = self.monitor.get_latest_failed_run(repo, branch, workflow_name)
            
            if not failed_run:
                return {
                    "success": False,
                    "error": f"No failed workflow runs found for {repo} on branch {branch}"
                }
            
            # Debug the specific run
            return self.debug_workflow_run(repo, failed_run["id"])
            
        except Exception as e:
            logger.error(f"Failed to debug latest failure: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def debug_workflow_run(self, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Debug a specific workflow run.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            
        Returns:
            Dictionary containing debug results
        """
        try:
            logger.info(f"Debugging workflow run {run_id} for {repo}")
            
            # Get workflow details
            workflow_info = self.monitor.get_workflow_run_details(repo, run_id)
            
            # Get failed job logs
            failed_logs = self.log_fetcher.get_failed_job_logs(repo, run_id)
            
            if not failed_logs:
                return {
                    "success": False,
                    "error": "No failed jobs found or unable to fetch logs",
                    "workflow_info": workflow_info
                }
            
            # Parse logs to extract errors
            parsed_errors = self.parser.parse_logs(failed_logs)
            
            # Generate error summary
            all_errors = []
            for job_errors in parsed_errors.values():
                all_errors.extend(job_errors)
            
            error_summary = self.parser.get_error_summary(all_errors)
            failure_stage = self.parser.classify_failure_stage(all_errors)
            error_summary["failure_stage"] = failure_stage
            
            # Generate fix suggestions
            suggestions = self.fix_suggester.suggest_fixes(all_errors, failed_logs)
            
            # Prepare result
            result = {
                "success": True,
                "repo": repo,
                "run_id": run_id,
                "workflow_info": workflow_info,
                "failed_logs": failed_logs,
                "parsed_errors": parsed_errors,
                "error_summary": error_summary,
                "suggestions": suggestions,
                "debugged_at": datetime.now(timezone.utc).isoformat()
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to debug workflow run {run_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo": repo,
                "run_id": run_id
            }
    
    def debug_multiple_runs(self, repo: str, branch: str = "main", 
                          workflow_name: str = None, max_runs: int = 5) -> List[Dict[str, Any]]:
        """
        Debug multiple recent failed workflow runs.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name to monitor (optional)
            max_runs: Maximum number of runs to debug
            
        Returns:
            List of debug results
        """
        try:
            # Get failed runs
            failed_runs = self.monitor.get_failed_workflow_runs(repo, branch, workflow_name, max_runs)
            
            results = []
            for run in failed_runs:
                result = self.debug_workflow_run(repo, run["id"])
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to debug multiple runs: {e}")
            return [{
                "success": False,
                "error": str(e),
                "repo": repo
            }]
    
    def debug_and_notify(self, repo: str, run_id: int, output_format: str = "cli") -> str:
        """
        Debug a workflow run and send notification.
        
        Args:
            repo: Repository in format "owner/repo"
            run_id: Workflow run ID
            output_format: Output format ("cli", "github", "slack", "discord")
            
        Returns:
            Formatted output string
        """
        # Debug the workflow
        debug_result = self.debug_workflow_run(repo, run_id)
        
        # Send notification
        return self.notifier.notify(debug_result, output_format)
    
    def debug_latest_and_notify(self, repo: str, branch: str = "main", 
                              workflow_name: str = None, output_format: str = "cli") -> str:
        """
        Debug the latest failure and send notification.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name to monitor (optional)
            output_format: Output format ("cli", "github", "slack", "discord")
            
        Returns:
            Formatted output string
        """
        # Debug the latest failure
        debug_result = self.debug_latest_failure(repo, branch, workflow_name)
        
        # Send notification
        return self.notifier.notify(debug_result, output_format)
    
    def get_workflow_status(self, repo: str, branch: str = "main", 
                          workflow_name: str = None) -> Dict[str, Any]:
        """
        Get status of recent workflow runs.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name to monitor (optional)
            
        Returns:
            Dictionary containing workflow status information
        """
        try:
            # Get recent runs (both successful and failed)
            from .monitor import GitHubWorkflowMonitor
            
            # We need to modify the monitor to get all runs, not just failed ones
            # For now, let's get failed runs and workflow details
            failed_runs = self.monitor.get_failed_workflow_runs(repo, branch, workflow_name, max_runs=10)
            
            status = {
                "repo": repo,
                "branch": branch,
                "workflow_name": workflow_name,
                "failed_runs_count": len(failed_runs),
                "recent_failures": failed_runs[:5],  # Last 5 failures
                "last_checked": datetime.now(timezone.utc).isoformat()
            }
            
            if failed_runs:
                latest_failure = failed_runs[0]
                status["latest_failure"] = {
                    "id": latest_failure["id"],
                    "name": latest_failure["name"],
                    "created_at": latest_failure["created_at"],
                    "html_url": latest_failure["html_url"]
                }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo": repo,
                "branch": branch
            }
    
    def analyze_error_patterns(self, repo: str, branch: str = "main", 
                             workflow_name: str = None, days: int = 30) -> Dict[str, Any]:
        """
        Analyze error patterns across multiple workflow runs.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor
            workflow_name: Specific workflow name to monitor (optional)
            days: Number of days to analyze
            
        Returns:
            Dictionary containing error pattern analysis
        """
        try:
            # Get failed runs from the last N days
            failed_runs = self.monitor.get_failed_workflow_runs(repo, branch, workflow_name, max_runs=50)
            
            # Filter by date
            from datetime import datetime, timezone, timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            recent_failures = []
            for run in failed_runs:
                # Handle both ISO format with Z and with timezone
                created_at = run["created_at"]
                if created_at.endswith("Z"):
                    run_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    run_date = datetime.fromisoformat(created_at)
                
                if run_date >= cutoff_date:
                    recent_failures.append(run)
            
            # Analyze each failure
            all_errors = []
            error_patterns = {}
            stage_failures = {}
            
            for run in recent_failures[:10]:  # Limit to 10 for performance
                try:
                    debug_result = self.debug_workflow_run(repo, run["id"])
                    if debug_result.get("success"):
                        errors = debug_result.get("parsed_errors", {})
                        for job_errors in errors.values():
                            all_errors.extend(job_errors)
                        
                        # Count error types
                        for error in debug_result.get("parsed_errors", {}).values():
                            for err in error:
                                error_type = err.error_type.value
                                error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
                        
                        # Count stage failures
                        stage = debug_result.get("error_summary", {}).get("failure_stage", "unknown")
                        stage_failures[stage] = stage_failures.get(stage, 0) + 1
                
                except Exception as e:
                    logger.warning(f"Failed to analyze run {run['id']}: {e}")
            
            return {
                "repo": repo,
                "branch": branch,
                "analysis_period_days": days,
                "total_failures_analyzed": len(recent_failures),
                "error_patterns": error_patterns,
                "stage_failures": stage_failures,
                "most_common_errors": sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5],
                "most_failing_stages": sorted(stage_failures.items(), key=lambda x: x[1], reverse=True)[:3],
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze error patterns: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo": repo,
                "branch": branch
            }
    
    def debug_and_fix(self, repo: str, branch: str = "main", create_pr: bool = False, pr_config: PRConfig = None) -> Dict[str, Any]:
        """
        Debug a failure and optionally create a PR with fixes.
        
        Args:
            repo: Repository in format "owner/repo"
            branch: Branch to monitor (default: "main")
            create_pr: Whether to create a PR with fixes
            pr_config: PR configuration (optional)
            
        Returns:
            Dictionary containing debug results and optionally PR URL
        """
        try:
            # First, debug the failure
            debug_result = self.debug_latest_failure(repo, branch)
            
            if not debug_result.get("success"):
                return debug_result
            
            # If PR creation is requested, try to create one
            if create_pr:
                # Ensure PR config exists and is properly configured
                if pr_config is None:
                    pr_config = PRConfig()
                
                # Check if PR creation is enabled in config
                if not pr_config.pr_creation_enabled:
                    debug_result["pr_created"] = False
                    debug_result["pr_error"] = "PR creation is disabled in configuration"
                    logger.warning("PR creation requested but disabled in configuration")
                    return debug_result
                
                try:
                    from .pr_generator import create_fix_pr
                    pr_url = create_fix_pr(debug_result, repo, self.github_token, pr_config)
                    
                    if pr_url:
                        debug_result["pr_url"] = pr_url
                        debug_result["pr_created"] = True
                        logger.info(f"Created fix PR: {pr_url}")
                    else:
                        debug_result["pr_created"] = False
                        debug_result["pr_error"] = "Failed to create PR"
                        logger.warning("Failed to create fix PR")
                
                except Exception as e:
                    debug_result["pr_created"] = False
                    debug_result["pr_error"] = str(e)
                    logger.error(f"Error creating PR: {e}")
            
            return debug_result
            
        except Exception as e:
            logger.error(f"Failed to debug and fix: {e}")
            return {
                "success": False,
                "error": str(e),
                "repo": repo,
                "branch": branch
            }
