#!/usr/bin/env python3
"""
CLI interface for CI/CD debugger.
"""

import argparse
import logging
import os
import sys
from typing import Optional

from .debugger import CICDDebugger
from .notifier import NotificationConfig

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CI/CD Pipeline Failure Debugger for iagent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Debug the latest failure in a repository
  iagent-cicd-debug your-org/your-repo

  # Debug a specific workflow run
  iagent-cicd-debug your-org/your-repo --run-id 123456

  # Debug with specific workflow name
  iagent-cicd-debug your-org/your-repo --workflow "CI Pipeline"

  # Debug and post to GitHub
  iagent-cicd-debug your-org/your-repo --output github

  # Analyze error patterns over the last 30 days
  iagent-cicd-debug your-org/your-repo --analyze-patterns

  # Get workflow status
  iagent-cicd-debug your-org/your-repo --status
        """
    )
    
    # Required arguments
    parser.add_argument(
        "repo",
        help="Repository in format 'owner/repo'"
    )
    
    # Optional arguments
    parser.add_argument(
        "--run-id",
        type=int,
        help="Specific workflow run ID to debug"
    )
    
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch to monitor (default: main)"
    )
    
    parser.add_argument(
        "--workflow",
        help="Specific workflow name to monitor"
    )
    
    parser.add_argument(
        "--output",
        choices=["cli", "github", "slack", "discord"],
        default="cli",
        help="Output format (default: cli)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Get workflow status instead of debugging"
    )
    
    parser.add_argument(
        "--analyze-patterns",
        action="store_true",
        help="Analyze error patterns over time"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to analyze (default: 30)"
    )
    
    parser.add_argument(
        "--max-runs",
        type=int,
        default=5,
        help="Maximum number of runs to check (default: 5)"
    )
    
    parser.add_argument(
        "--github-token",
        help="GitHub personal access token (or set GITHUB_TOKEN env var)"
    )
    
    parser.add_argument(
        "--slack-webhook",
        help="Slack webhook URL for notifications"
    )
    
    parser.add_argument(
        "--discord-webhook",
        help="Discord webhook URL for notifications"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Get GitHub token
    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("❌ Error: GitHub token is required. Set GITHUB_TOKEN environment variable or use --github-token")
        sys.exit(1)
    
    # Setup notification config
    notification_config = NotificationConfig(
        github_token=github_token,
        slack_webhook_url=args.slack_webhook,
        discord_webhook_url=args.discord_webhook,
        enable_github_comments=args.output == "github",
        enable_slack=args.output == "slack",
        enable_discord=args.output == "discord"
    )
    
    try:
        # Initialize debugger with read-only mode by default
        debugger = CICDDebugger(
            github_token=github_token,
            notification_config=notification_config,
            readonly_mode=True
        )
        
        # Execute based on arguments
        if args.status:
            result = debugger.get_workflow_status(
                repo=args.repo,
                branch=args.branch,
                workflow_name=args.workflow
            )
        elif args.analyze_patterns:
            result = debugger.analyze_error_patterns(
                repo=args.repo,
                branch=args.branch,
                workflow_name=args.workflow,
                days=args.days
            )
        elif args.run_id:
            result = debugger.debug_workflow_run(
                repo=args.repo,
                run_id=args.run_id
            )
        else:
            result = debugger.debug_latest_failure(
                repo=args.repo,
                branch=args.branch,
                workflow_name=args.workflow,
                max_runs=args.max_runs
            )
        
        # Output results
        if args.json:
            import json
            print(json.dumps(result, indent=2, default=str))
        else:
            if args.output == "cli":
                # Format for CLI output
                output = format_result_for_cli(result, args)
                print(output)
            else:
                # Send notification
                output = debugger.notifier.notify(result, args.output)
                print(output)
        
        # Exit with error code if debugging failed
        if not result.get("success", True):
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


def format_result_for_cli(result: dict, args) -> str:
    """Format debug result for CLI output."""
    if not result.get("success", True):
        return f"❌ Debug failed: {result.get('error', 'Unknown error')}"
    
    # Simple output - just error and solution
    if "error_summary" in result and result["error_summary"].get("total_errors", 0) > 0:
        output_parts = []
        
        # Show the main error
        if "parsed_errors" in result:
            for job_name, job_errors in result["parsed_errors"].items():
                if job_errors:
                    error = job_errors[0]  # Show first error
                    output_parts.append(f"❌ Error: {error.message}")
                    break
        
        # Show the main solution
        if "suggestions" in result and result["suggestions"]:
            suggestion = result["suggestions"][0]  # Show first suggestion
            output_parts.append(f"✅ Solution: {suggestion.title}")
            if suggestion.commands:
                output_parts.append(f"   Command: {suggestion.commands[0]}")
        
        return "\n".join(output_parts)
    
    return "✅ No errors found"


if __name__ == "__main__":
    main()
