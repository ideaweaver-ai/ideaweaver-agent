#!/usr/bin/env python3
"""
Notification system for CI/CD debugger results.
"""

import logging
import os
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    github_token: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    enable_github_comments: bool = False
    enable_slack: bool = False
    enable_discord: bool = False


class Notifier:
    """Handles sending CI/CD debugger results to various channels."""
    
    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig()
        self.session = requests.Session()
        
        if self.config.github_token:
            self.session.headers.update({
                "Authorization": f"token {self.config.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "iagent-cicd-debugger"
            })
    
    def notify(self, debug_result: Dict[str, Any], output_format: str = "cli") -> str:
        """
        Send notification based on the debug result.
        
        Args:
            debug_result: Result from CI/CD debugger
            output_format: Format for output ("cli", "github", "slack", "discord")
            
        Returns:
            Formatted output string
        """
        if output_format == "cli":
            return self._format_cli_output(debug_result)
        elif output_format == "github" and self.config.enable_github_comments:
            return self._send_github_comment(debug_result)
        elif output_format == "slack" and self.config.enable_slack:
            return self._send_slack_message(debug_result)
        elif output_format == "discord" and self.config.enable_discord:
            return self._send_discord_message(debug_result)
        else:
            return self._format_cli_output(debug_result)
    
    def _format_cli_output(self, debug_result: Dict[str, Any]) -> str:
        """Format debug result for CLI output."""
        output_parts = []
        
        # Header
        output_parts.append("🚀 CI/CD Pipeline Failure Debugger")
        output_parts.append("=" * 50)
        
        # Workflow information
        if "workflow_info" in debug_result:
            workflow = debug_result["workflow_info"]
            output_parts.append(f"📋 Workflow: {workflow.get('name', 'Unknown')}")
            output_parts.append(f"🔄 Run ID: {workflow.get('id', 'Unknown')}")
            output_parts.append(f"🌿 Branch: {workflow.get('head_branch', 'Unknown')}")
            output_parts.append(f"⏰ Failed at: {workflow.get('created_at', 'Unknown')}")
            output_parts.append("")
        
        # Error summary
        if "error_summary" in debug_result:
            summary = debug_result["error_summary"]
            output_parts.append("❌ Error Summary:")
            output_parts.append(f"   Total Errors: {summary.get('total_errors', 0)}")
            output_parts.append(f"   Failure Stage: {summary.get('failure_stage', 'Unknown')}")
            
            if "error_types" in summary:
                output_parts.append("   Error Types:")
                for error_type, count in summary["error_types"].items():
                    output_parts.append(f"     - {error_type}: {count}")
            output_parts.append("")
        
        # Failed jobs
        if "failed_jobs" in debug_result:
            output_parts.append("🔍 Failed Jobs:")
            for job_name, job_errors in debug_result["failed_jobs"].items():
                output_parts.append(f"   📦 {job_name}:")
                for error in job_errors[:3]:  # Show first 3 errors per job
                    output_parts.append(f"     • {error.message[:100]}...")
            output_parts.append("")
        
        # Fix suggestions
        if "suggestions" in debug_result:
            output_parts.append("✅ Suggested Fixes:")
            suggestions = debug_result["suggestions"]
            
            if isinstance(suggestions, str):
                output_parts.append(suggestions)
            else:
                for i, suggestion in enumerate(suggestions[:5], 1):  # Show first 5 suggestions
                    output_parts.append(f"   {i}. {suggestion.title}")
                    output_parts.append(f"      {suggestion.description}")
                    if suggestion.commands:
                        output_parts.append(f"      Commands: {'; '.join(suggestion.commands[:2])}")
                    output_parts.append("")
        
        # Footer
        output_parts.append("=" * 50)
        output_parts.append("💡 For more details, check the workflow logs on GitHub.")
        
        return "\n".join(output_parts)
    
    def _send_github_comment(self, debug_result: Dict[str, Any]) -> str:
        """Send debug result as a GitHub comment."""
        if not self.config.github_token:
            return "GitHub token not configured"
        
        try:
            # Extract repository and run information
            repo = debug_result.get("repo")
            run_id = debug_result.get("run_id")
            
            if not repo or not run_id:
                return "Missing repository or run ID information"
            
            # Format comment
            comment_body = self._format_github_comment(debug_result)
            
            # Find the associated pull request
            pr_number = self._find_associated_pr(repo, run_id)
            
            if pr_number:
                # Comment on the PR
                url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
                payload = {"body": comment_body}
                
                response = self.session.post(url, json=payload)
                response.raise_for_status()
                
                return f"Comment posted to PR #{pr_number}"
            else:
                # Create a new issue with the debug results
                url = f"https://api.github.com/repos/{repo}/issues"
                payload = {
                    "title": f"CI/CD Debug Results - Run #{run_id}",
                    "body": comment_body,
                    "labels": ["ci-cd", "debug", "automated"]
                }
                
                response = self.session.post(url, json=payload)
                response.raise_for_status()
                
                issue_data = response.json()
                return f"Issue created: #{issue_data['number']}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send GitHub comment: {e}")
            return f"Failed to send GitHub comment: {e}"
    
    def _format_github_comment(self, debug_result: Dict[str, Any]) -> str:
        """Format debug result for GitHub comment."""
        comment_parts = []
        
        # Header
        comment_parts.append("🤖 **CI/CD Pipeline Failure Debugger**")
        comment_parts.append("")
        
        # Workflow information
        if "workflow_info" in debug_result:
            workflow = debug_result["workflow_info"]
            comment_parts.append(f"**Workflow:** {workflow.get('name', 'Unknown')}")
            comment_parts.append(f"**Run ID:** {workflow.get('id', 'Unknown')}")
            comment_parts.append(f"**Branch:** {workflow.get('head_branch', 'Unknown')}")
            comment_parts.append("")
        
        # Error summary
        if "error_summary" in debug_result:
            summary = debug_result["error_summary"]
            comment_parts.append("## ❌ Error Summary")
            comment_parts.append(f"- **Total Errors:** {summary.get('total_errors', 0)}")
            comment_parts.append(f"- **Failure Stage:** {summary.get('failure_stage', 'Unknown')}")
            comment_parts.append("")
        
        # Fix suggestions
        if "suggestions" in debug_result:
            comment_parts.append("## ✅ Suggested Fixes")
            suggestions = debug_result["suggestions"]
            
            if isinstance(suggestions, str):
                comment_parts.append(suggestions)
            else:
                for i, suggestion in enumerate(suggestions[:3], 1):  # Show first 3 suggestions
                    comment_parts.append(f"### {i}. {suggestion.title}")
                    comment_parts.append(f"{suggestion.description}")
                    
                    if suggestion.commands:
                        comment_parts.append("**Commands to run:**")
                        for cmd in suggestion.commands[:2]:
                            comment_parts.append(f"```bash\n{cmd}\n```")
                    
                    comment_parts.append("")
        
        # Footer
        comment_parts.append("---")
        comment_parts.append("*This comment was automatically generated by iagent CI/CD Debugger*")
        
        return "\n".join(comment_parts)
    
    def _find_associated_pr(self, repo: str, run_id: int) -> Optional[int]:
        """Find the pull request associated with a workflow run."""
        try:
            url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
            response = self.session.get(url)
            response.raise_for_status()
            
            run_data = response.json()
            head_branch = run_data.get("head_branch", "")
            
            # Look for PRs with this head branch
            url = f"https://api.github.com/repos/{repo}/pulls"
            params = {"head": f"{repo.split('/')[0]}:{head_branch}", "state": "open"}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            prs = response.json()
            if prs:
                return prs[0]["number"]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to find associated PR: {e}")
            return None
    
    def _send_slack_message(self, debug_result: Dict[str, Any]) -> str:
        """Send debug result to Slack."""
        if not self.config.slack_webhook_url:
            return "Slack webhook URL not configured"
        
        try:
            # Format Slack message
            slack_payload = self._format_slack_message(debug_result)
            
            response = self.session.post(self.config.slack_webhook_url, json=slack_payload)
            response.raise_for_status()
            
            return "Slack message sent successfully"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack message: {e}")
            return f"Failed to send Slack message: {e}"
    
    def _format_slack_message(self, debug_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format debug result for Slack message."""
        # Create Slack message blocks
        blocks = []
        
        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚀 CI/CD Pipeline Failure Debugger"
            }
        })
        
        # Workflow info
        if "workflow_info" in debug_result:
            workflow = debug_result["workflow_info"]
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Workflow:*\n{workflow.get('name', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Run ID:*\n{workflow.get('id', 'Unknown')}"
                    }
                ]
            })
        
        # Error summary
        if "error_summary" in debug_result:
            summary = debug_result["error_summary"]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *Error Summary:*\n• Total Errors: {summary.get('total_errors', 0)}\n• Failure Stage: {summary.get('failure_stage', 'Unknown')}"
                }
            })
        
        # Simple error and solution
        if "parsed_errors" in debug_result and "suggestions" in debug_result:
            for job_name, job_errors in debug_result["parsed_errors"].items():
                if job_errors and debug_result["suggestions"]:
                    error = job_errors[0]
                    suggestion = debug_result["suggestions"][0]
                    
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"❌ *Error:* {error.message[:100]}{'...' if len(error.message) > 100 else ''}\n✅ *Solution:* {suggestion.title}"
                        }
                    })
                    break
        
        # Remove the verbose suggestions section since we show it above
        
        # Add explanation footer only if there are errors
        if debug_result.get("error_summary", {}).get("total_errors", 0) > 0:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "💡 *Error Consolidation:*\nSimilar errors are consolidated into comprehensive fixes."
                }
            })
        
        return {
            "blocks": blocks,
            "text": "CI/CD Pipeline Failure Debug Results"
        }
    
    def _send_discord_message(self, debug_result: Dict[str, Any]) -> str:
        """Send debug result to Discord."""
        if not self.config.discord_webhook_url:
            return "Discord webhook URL not configured"
        
        try:
            # Format Discord message
            discord_payload = self._format_discord_message(debug_result)
            
            response = self.session.post(self.config.discord_webhook_url, json=discord_payload)
            response.raise_for_status()
            
            return "Discord message sent successfully"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Discord message: {e}")
            return f"Failed to send Discord message: {e}"
    
    def _format_discord_message(self, debug_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format debug result for Discord message."""
        # Create Discord embed
        embed = {
            "title": "🚀 CI/CD Pipeline Failure Debugger",
            "color": 0xFF6B6B,  # Red color for failures
            "fields": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Workflow info
        if "workflow_info" in debug_result:
            workflow = debug_result["workflow_info"]
            embed["fields"].extend([
                {
                    "name": "Workflow",
                    "value": workflow.get('name', 'Unknown'),
                    "inline": True
                },
                {
                    "name": "Run ID",
                    "value": str(workflow.get('id', 'Unknown')),
                    "inline": True
                }
            ])
        
        # Error summary
        if "error_summary" in debug_result:
            summary = debug_result["error_summary"]
            embed["fields"].append({
                "name": "❌ Error Summary",
                "value": f"Total Errors: {summary.get('total_errors', 0)}\nFailure Stage: {summary.get('failure_stage', 'Unknown')}",
                "inline": False
            })
        
        # Fix suggestions
        if "suggestions" in debug_result:
            suggestions = debug_result["suggestions"]
            if isinstance(suggestions, list) and suggestions:
                suggestion_text = "\n".join([f"{i}. {s.title}" for i, s in enumerate(suggestions[:3], 1)])
                embed["fields"].append({
                    "name": "✅ Top Suggestions",
                    "value": suggestion_text,
                    "inline": False
                })
        
        return {
            "embeds": [embed]
        }
