#!/usr/bin/env python3
"""
Simple wrapper for CI/CD debugger with user-friendly interface.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .debugger import CICDDebugger
from .notifier import NotificationConfig
from .pr_generator import PRConfig, create_fix_pr

logger = logging.getLogger(__name__)


@dataclass
class DebuggerConfig:
    """Configuration for the CI/CD debugger wrapper."""
    # Repository
    repo: str  # Format: "owner/repo"
    
    # GitHub token (will try to get from environment)
    github_token: Optional[str] = None
    
    # Model for AI suggestions
    model: Optional[Any] = None
    
    # PR Generation
    generate_pr: bool = False
    
    # Documentation Generation
    generate_docs: bool = True
    
    # Notifications
    slack_webhook_url: Optional[str] = None
    
    # Debugging options
    branch: str = "main"
    workflow_name: Optional[str] = None
    max_runs: int = 5
    run_id: Optional[int] = None
    
    # Output options
    output_format: str = "cli"  # "cli", "github", "slack", "discord"
    verbose: bool = False


class CICDDebuggerWrapper:
    """
    Simple wrapper for CI/CD debugger with user-friendly interface.
    
    Usage:
        from iagent.cicd_debugger import CICDDebuggerWrapper
        
        # Simple usage
        debugger = CICDDebuggerWrapper("your-org/your-repo")
        result = debugger.debug_latest_failure()
        
        # Advanced usage with PR generation
        debugger = CICDDebuggerWrapper(
            repo="your-org/your-repo",
            generate_pr=True,
            generate_docs=True,
            slack_webhook_url="https://hooks.slack.com/..."
        )
        result = debugger.debug_latest_failure()
    """
    
    def __init__(self, repo: str, **kwargs):
        """
        Initialize the CI/CD debugger wrapper.
        
        Args:
            repo: Repository in format "owner/repo"
            **kwargs: Additional configuration options
        """
        self.config = DebuggerConfig(repo=repo, **kwargs)
        self._setup_logging()
        self._setup_debugger()
        self._output_printed = False  # Initialize flag
    
    def _setup_logging(self):
        """Setup logging based on verbose flag."""
        level = logging.WARNING  # Only show warnings and errors
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _setup_debugger(self):
        """Setup the underlying debugger with proper configuration."""
        # Get GitHub token from config or environment
        github_token = self.config.github_token or os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable "
                "or pass github_token parameter."
            )
        
        # Setup notification config
        notification_config = NotificationConfig(
            github_token=github_token,
            slack_webhook_url=self.config.slack_webhook_url,
            enable_github_comments=self.config.output_format == "github",
            enable_slack=bool(self.config.slack_webhook_url),  # Enable if webhook URL is provided
            enable_discord=self.config.output_format == "discord"
        )
        
        # Initialize debugger
        self.debugger = CICDDebugger(
            github_token=github_token,
            model=self.config.model,  # Pass the model
            notification_config=notification_config,
            readonly_mode=False  # Allow actionable fixes for PR generation
        )
        
        self.github_token = github_token
    
    def debug_latest_failure(self) -> Dict[str, Any]:
        """
        Debug the latest failed workflow run.
        
        Returns:
            Dictionary containing debug results
        """
        logger.info(f"Debugging latest failure for {self.config.repo}")
        
        # Run the debugger
        result = self.debugger.debug_latest_failure(
            repo=self.config.repo,
            branch=self.config.branch,
            workflow_name=self.config.workflow_name,
            max_runs=self.config.max_runs
        )
        
        # Post-process results
        self._post_process_result(result)
        
        return result
    
    def debug_specific_run(self, run_id: int) -> Dict[str, Any]:
        """
        Debug a specific workflow run.
        
        Args:
            run_id: GitHub workflow run ID
            
        Returns:
            Dictionary containing debug results
        """
        logger.info(f"Debugging run {run_id} for {self.config.repo}")
        
        # Run the debugger
        result = self.debugger.debug_workflow_run(
            repo=self.config.repo,
            run_id=run_id
        )
        
        # Post-process results
        self._post_process_result(result)
        
        return result
    
    def debug_run(self, run_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Debug a workflow run (latest failure or specific run).
        
        Args:
            run_id: Optional specific run ID. If None, debug latest failure.
            
        Returns:
            Dictionary containing debug results
        """
        if run_id:
            return self.debug_specific_run(run_id)
        else:
            return self.debug_latest_failure()
    
    def _post_process_result(self, result: Dict[str, Any]):
        """Post-process the debug result (generate PR, docs, notifications)."""
        if not result.get("success"):
            return
        
        # Print simple error and solution only once
        if not self._output_printed:
            if "error_summary" in result and result["error_summary"].get("total_errors", 0) > 0:
                if "parsed_errors" in result:
                    for job_name, job_errors in result["parsed_errors"].items():
                        if job_errors:
                            error = job_errors[0]
                            print(f"❌ Error: {error.message}")
                            break
                
                if "suggestions" in result and result["suggestions"]:
                    suggestion = result["suggestions"][0]
                    source = "🤖 AI" if suggestion.fix_type == "ai_generated" else "📋 Rule-based"
                    print(f"✅ Solution: {suggestion.title} ({source})")
                    if suggestion.commands:
                        print(f"   Command: {suggestion.commands[0]}")
            self._output_printed = True
        
        # Generate PR if requested
        if self.config.generate_pr:
            self._generate_pr(result)
        
        # Generate documentation if requested
        if self.config.generate_docs:
            self._generate_docs(result)
        
        # Send notifications
        self._send_notifications(result)
        
        # Print success messages
        if self.config.generate_pr and result.get("pr_url"):
            print(f"PR created: {result['pr_url']}")
        if self.config.slack_webhook_url:
            print("Slack notification sent")
    

    
    def _generate_pr(self, result: Dict[str, Any]):
        """Generate a pull request with fixes."""
        try:
            logger.info("Generating pull request with fixes...")
            
            # Setup PR config
            pr_config = PRConfig(
                pr_creation_enabled=True,
                base_branch=self.config.branch,
                require_user_confirmation=False,  # Auto-create for wrapper
                auto_merge=False
            )
            
            # Create PR
            pr_url = create_fix_pr(
                debug_result=result,
                repo=self.config.repo,
                github_token=self.github_token,
                config=pr_config
            )
            
            if pr_url:
                logger.info(f"✅ Pull request created: {pr_url}")
                result["pr_url"] = pr_url
            else:
                logger.warning("❌ Failed to create pull request")
                
        except Exception as e:
            logger.error(f"Failed to generate PR: {e}")
    
    def _generate_docs(self, result: Dict[str, Any]):
        """Generate documentation for the debug results."""
        try:
            logger.info("Generating documentation...")
            
            # Create a simple documentation file
            docs_content = self._create_documentation_content(result)
            
            # For now, just log the documentation
            # In a full implementation, you might save this to a file
            logger.info("📚 Documentation generated:")
            logger.info(docs_content[:500] + "..." if len(docs_content) > 500 else docs_content)
            
            result["documentation"] = docs_content
            
        except Exception as e:
            logger.error(f"Failed to generate documentation: {e}")
    
    def _create_documentation_content(self, result: Dict[str, Any]) -> str:
        """Create documentation content for the debug results."""
        docs = f"""# CI/CD Debug Report

## Summary
- **Repository:** {result.get('repo', 'Unknown')}
- **Run ID:** {result.get('run_id', 'Unknown')}
- **Debugged at:** {result.get('debugged_at', 'Unknown')}

## Error Summary
"""
        
        if "error_summary" in result:
            summary = result["error_summary"]
            docs += f"""
- **Total Errors:** {summary.get('total_errors', 0)}
- **Failure Stage:** {summary.get('failure_stage', 'Unknown')}
- **Error Types:** {', '.join(summary.get('error_types', {}).keys())}
"""
        
        # Add detailed error breakdown
        if "parsed_errors" in result:
            docs += "\n## Detailed Error Breakdown\n"
            for job_name, job_errors in result["parsed_errors"].items():
                docs += f"\n### Job: {job_name}\n"
                docs += f"**Total errors in this job:** {len(job_errors)}\n\n"
                
                for i, error in enumerate(job_errors, 1):
                    docs += f"**Error {i}:**\n"
                    docs += f"- **Type:** {error.error_type.value}\n"
                    docs += f"- **Message:** {error.message}\n"
                    if error.file_path:
                        docs += f"- **File:** {error.file_path}\n"
                    if error.line_number:
                        docs += f"- **Line:** {error.line_number}\n"
                    if error.command:
                        docs += f"- **Command:** {error.command}\n"
                    if error.exit_code:
                        docs += f"- **Exit Code:** {error.exit_code}\n"
                    docs += "\n"
        
        docs += "\n## Suggested Fixes\n"
        
        if "suggestions" in result:
            suggestions = result["suggestions"]
            if isinstance(suggestions, list):
                docs += f"\n**Total suggestions generated:** {len(suggestions)}\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    docs += f"""
### {i}. {suggestion.title}
**Description:** {suggestion.description}
**Priority:** {suggestion.priority}
**Confidence:** {suggestion.confidence:.1%}
**Fix Type:** {suggestion.fix_type}

**Commands:**
"""
                    if suggestion.commands:
                        for cmd in suggestion.commands:
                            docs += f"```bash\n{cmd}\n```\n"
                    
                    if suggestion.files_to_modify:
                        docs += "**Files to modify:**\n"
                        for file_path in suggestion.files_to_modify:
                            docs += f"- {file_path}\n"
        
        docs += "\n---\n*Generated by iagent CI/CD Debugger*"
        
        return docs
    
    def _send_notifications(self, result: Dict[str, Any]):
        """Send notifications based on configuration."""
        try:
            # Send Slack notification if webhook URL is provided
            if self.config.slack_webhook_url:
                logger.info("Sending slack notification...")
                output = self.debugger.notifier.notify(result, "slack")
                logger.info(f"Notification sent: {output}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


# Convenience functions for simple usage
def debug_repo(repo: str, **kwargs) -> Dict[str, Any]:
    """
    Simple function to debug a repository's latest failure.
    
    Args:
        repo: Repository in format "owner/repo"
        **kwargs: Additional configuration options
        
    Returns:
        Dictionary containing debug results
        
    Example:
        from iagent.cicd_debugger import debug_repo
        
        # Simple usage
        result = debug_repo("your-org/your-repo")
        
        # With PR generation
        result = debug_repo("your-org/your-repo", generate_pr=True)
        
        # With Slack notifications
        result = debug_repo(
            "your-org/your-repo",
            slack_webhook_url="https://hooks.slack.com/...",
            output_format="slack"
        )
    """
    debugger = CICDDebuggerWrapper(repo, **kwargs)
    return debugger.debug_latest_failure()


def debug_run(repo: str, run_id: int, **kwargs) -> Dict[str, Any]:
    """
    Simple function to debug a specific workflow run.
    
    Args:
        repo: Repository in format "owner/repo"
        run_id: GitHub workflow run ID
        **kwargs: Additional configuration options
        
    Returns:
        Dictionary containing debug results
        
    Example:
        from iagent.cicd_debugger import debug_run
        
        result = debug_run("your-org/your-repo", 123456)
    """
    debugger = CICDDebuggerWrapper(repo, **kwargs)
    return debugger.debug_specific_run(run_id)


# Export the main classes and functions
__all__ = [
    'CICDDebuggerWrapper',
    'DebuggerConfig',
    'debug_repo',
    'debug_run'
]
