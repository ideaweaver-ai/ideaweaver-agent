#!/usr/bin/env python3
"""
CI/CD debugger tools for iagent.
"""

import logging
import os
from typing import Dict, Any, Optional
from ..tools import BaseTool

logger = logging.getLogger(__name__)


class DebugCICDFailureTool(BaseTool):
    """Debug a CI/CD pipeline failure by analyzing GitHub workflow logs and suggesting fixes."""
    
    name = "debug_cicd_failure"
    description = "Debug a CI/CD pipeline failure by analyzing GitHub workflow logs and suggesting fixes"
    inputs = {
        "repo": {
            "type": "string",
            "description": "Repository in format 'owner/repo'"
        },
        "run_id": {
            "type": "integer",
            "description": "Specific workflow run ID to debug (optional)"
        },
        "branch": {
            "type": "string",
            "description": "Branch to monitor (default: main)"
        },
        "workflow_name": {
            "type": "string",
            "description": "Specific workflow name to monitor (optional)"
        }
    }
    output_type = "string"
    
    def execute(self, repo: str, run_id: Optional[int] = None, 
                branch: str = "main", workflow_name: Optional[str] = None, model=None) -> str:
        """
        Debug a CI/CD pipeline failure.
        
        Args:
            repo: Repository in format 'owner/repo'
            run_id: Specific workflow run ID to debug (optional)
            branch: Branch to monitor (default: main)
            workflow_name: Specific workflow name to monitor (optional)
            model: AI model instance for enhanced analysis
            
        Returns:
            Formatted debug results
        """
        try:
            from .debugger import CICDDebugger
            
            # Get GitHub token
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                return "❌ Error: GITHUB_TOKEN environment variable is required"
            
            # Initialize debugger with model
            debugger = CICDDebugger(github_token=github_token, model=model)
            
            # Debug the failure
            if run_id:
                result = debugger.debug_workflow_run(repo, run_id)
            else:
                result = debugger.debug_latest_failure(repo, branch, workflow_name)
            
            if not result.get("success", True):
                return f"❌ Debug failed: {result.get('error', 'Unknown error')}"
            
            # Format the result
            return format_debug_result(result)
            
        except Exception as e:
            logger.error(f"Failed to debug CI/CD failure: {e}")
            return f"❌ Error: {e}"


class GetCICDStatusTool(BaseTool):
    """Get the status of recent CI/CD workflow runs."""
    
    name = "get_cicd_status"
    description = "Get the status of recent CI/CD workflow runs"
    inputs = {
        "repo": {
            "type": "string",
            "description": "Repository in format 'owner/repo'"
        },
        "branch": {
            "type": "string",
            "description": "Branch to monitor (default: main)"
        },
        "workflow_name": {
            "type": "string",
            "description": "Specific workflow name to monitor (optional)"
        }
    }
    output_type = "string"
    
    def execute(self, repo: str, branch: str = "main", workflow_name: Optional[str] = None, model=None) -> str:
        """
        Get the status of recent CI/CD workflow runs.
        
        Args:
            repo: Repository in format 'owner/repo'
            branch: Branch to monitor (default: main)
            workflow_name: Specific workflow name to monitor (optional)
            model: AI model instance for enhanced analysis
            
        Returns:
            Formatted status information
        """
        try:
            from .debugger import CICDDebugger
            
            # Get GitHub token
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                return "❌ Error: GITHUB_TOKEN environment variable is required"
            
            # Initialize debugger with model and read-only mode
            debugger = CICDDebugger(github_token=github_token, model=model, readonly_mode=True)
            
            # Get status
            result = debugger.get_workflow_status(repo, branch, workflow_name)
            
            if not result.get("success", True):
                return f"❌ Failed to get status: {result.get('error', 'Unknown error')}"
            
            # Format the result
            return format_status_result(result)
            
        except Exception as e:
            logger.error(f"Failed to get CI/CD status: {e}")
            return f"❌ Error: {e}"


class AnalyzeCICDPatternsTool(BaseTool):
    """Analyze error patterns across multiple CI/CD workflow runs."""
    
    name = "analyze_cicd_patterns"
    description = "Analyze error patterns across multiple CI/CD workflow runs"
    inputs = {
        "repo": {
            "type": "string",
            "description": "Repository in format 'owner/repo'"
        },
        "branch": {
            "type": "string",
            "description": "Branch to monitor (default: main)"
        },
        "workflow_name": {
            "type": "string",
            "description": "Specific workflow name to monitor (optional)"
        },
        "days": {
            "type": "integer",
            "description": "Number of days to analyze (default: 30)"
        }
    }
    output_type = "string"
    
    def execute(self, repo: str, branch: str = "main", 
                workflow_name: Optional[str] = None, days: int = 30, model=None) -> str:
        """
        Analyze error patterns across multiple CI/CD workflow runs.
        
        Args:
            repo: Repository in format 'owner/repo'
            branch: Branch to monitor (default: main)
            workflow_name: Specific workflow name to monitor (optional)
            days: Number of days to analyze (default: 30)
            model: AI model instance for enhanced analysis
            
        Returns:
            Formatted pattern analysis
        """
        try:
            from .debugger import CICDDebugger
            
            # Get GitHub token
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                return "❌ Error: GITHUB_TOKEN environment variable is required"
            
            # Initialize debugger with model and read-only mode
            debugger = CICDDebugger(github_token=github_token, model=model, readonly_mode=True)
            
            # Analyze patterns
            result = debugger.analyze_error_patterns(repo, branch, workflow_name, days)
            
            if not result.get("success", True):
                return f"❌ Failed to analyze patterns: {result.get('error', 'Unknown error')}"
            
            # Format the result
            return format_pattern_analysis(result)
            
        except Exception as e:
            logger.error(f"Failed to analyze CI/CD patterns: {e}")
            return f"❌ Error: {e}"


class CreateCICDFixPRTool(BaseTool):
    """Create a pull request with automated fixes for CI/CD pipeline failures."""
    
    name = "create_cicd_fix_pr"
    description = "Create a pull request with automated fixes for CI/CD pipeline failures"
    inputs = {
        "repo": {
            "type": "string",
            "description": "Repository in format 'owner/repo'"
        },
        "branch": {
            "type": "string",
            "description": "Branch to monitor (default: main)"
        },
        "workflow_name": {
            "type": "string",
            "description": "Specific workflow name to monitor (optional)"
        },
        "base_branch": {
            "type": "string",
            "description": "Base branch for PR (default: main)"
        },
        "auto_merge": {
            "type": "boolean",
            "description": "Whether to enable auto-merge (default: false)"
        },
        "enable_pr_creation": {
            "type": "boolean",
            "description": "Enable PR creation (default: true, enabled by default)"
        }
    }
    output_type = "string"
    
    def execute(self, repo: str, branch: str = "main", 
                workflow_name: Optional[str] = None, base_branch: str = "main",
                auto_merge: bool = False,             enable_pr_creation: bool = True) -> str:
        """
        Create a pull request with automated fixes for CI/CD pipeline failures.
        
        Args:
            repo: Repository in format 'owner/repo'
            branch: Branch to monitor (default: main)
            workflow_name: Specific workflow name to monitor (optional)
            base_branch: Base branch for PR (default: main)
            auto_merge: Whether to enable auto-merge (default: false)
            enable_pr_creation: Enable PR creation (default: true, enabled by default)
            
        Returns:
            Formatted PR creation result
        """
        try:
            from .debugger import CICDDebugger
            from .pr_generator import PRConfig
            
            # Get GitHub token
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                return "❌ Error: GITHUB_TOKEN environment variable is required"
            
            # Initialize debugger
            debugger = CICDDebugger(github_token=github_token, readonly_mode=True)
            
            # Configure PR settings
            pr_config = PRConfig(
                pr_creation_enabled=True,  # Enabled by default
                base_branch=base_branch,
                auto_merge=auto_merge,
                require_user_confirmation=True
            )
            
            # Debug and create PR
            result = debugger.debug_and_fix(repo, branch, create_pr=True, pr_config=pr_config)
            
            if not result.get("success", True):
                return f"❌ Debug failed: {result.get('error', 'Unknown error')}"
            
            # Format the result
            return format_pr_result(result)
            
        except Exception as e:
            logger.error(f"Failed to create CI/CD fix PR: {e}")
            return f"❌ Error: {e}"


class EnableCICDPRGenerationTool(BaseTool):
    """Configure PR generation for CI/CD fixes (enabled by default)."""
    
    name = "enable_cicd_pr_generation"
    description = "Configure PR generation for CI/CD fixes (enabled by default)"
    inputs = {
        "enable": {
            "type": "boolean",
            "description": "Enable PR generation (default: true)"
        },
        "auto_merge": {
            "type": "boolean",
            "description": "Enable auto-merge (default: false)"
        },
        "require_confirmation": {
            "type": "boolean",
            "description": "Require user confirmation for each PR (default: true)"
        }
    }
    output_type = "string"
    
    def execute(self, enable: bool = True, auto_merge: bool = False, 
                require_confirmation: bool = True) -> str:
        """
        Enable or disable PR generation for CI/CD fixes.
        
        Args:
            enable: Enable PR generation (default: false)
            auto_merge: Enable auto-merge (default: false)
            require_confirmation: Require user confirmation (default: true)
            
        Returns:
            Status message
        """
        try:
            if enable:
                return """✅ PR Generation Enabled

⚠️  WARNING: PR generation is now enabled!
- The system can create pull requests with automated fixes
- All PRs will be created in read-only mode by default
- User confirmation is required for each PR
- Auto-merge is disabled for safety

To create a PR, use:
create_cicd_fix_pr(repo="owner/repo", enable_pr_creation=True)

To disable PR generation, run this tool again with enable=False"""
            else:
                return """✅ PR Generation Disabled

PR generation is now disabled for safety.
No automated PRs will be created."""
                
        except Exception as e:
            logger.error(f"Failed to configure PR generation: {e}")
            return f"❌ Error: {e}"


# Create tool instances
debug_cicd_failure = DebugCICDFailureTool()
get_cicd_status = GetCICDStatusTool()
analyze_cicd_patterns = AnalyzeCICDPatternsTool()
create_cicd_fix_pr = CreateCICDFixPRTool()
enable_cicd_pr_generation = EnableCICDPRGenerationTool()


def format_debug_result(result: Dict[str, Any]) -> str:
    """Format debug result for tool output."""
    output_parts = []
    
    # Header
    output_parts.append("🚀 CI/CD Pipeline Failure Debugger")
    output_parts.append("=" * 50)
    
    # Repository info
    output_parts.append(f"📦 Repository: {result.get('repo', 'Unknown')}")
    if result.get('run_id'):
        output_parts.append(f"🔄 Run ID: {result['run_id']}")
    
    # Workflow info
    if "workflow_info" in result:
        workflow = result["workflow_info"]
        output_parts.append(f"📋 Workflow: {workflow.get('name', 'Unknown')}")
        output_parts.append(f"🌿 Branch: {workflow.get('head_branch', 'Unknown')}")
    
    output_parts.append("")
    
    # Error summary
    if "error_summary" in result:
        summary = result["error_summary"]
        output_parts.append("❌ Error Summary:")
        output_parts.append(f"   Total Errors: {summary.get('total_errors', 0)}")
        output_parts.append(f"   Failure Stage: {summary.get('failure_stage', 'Unknown')}")
        
        if "error_types" in summary and summary["error_types"]:
            output_parts.append("   Error Types:")
            for error_type, count in summary["error_types"].items():
                output_parts.append(f"     • {error_type}: {count}")
        
        output_parts.append("")
    
    # Fix suggestions
    if "suggestions" in result:
        output_parts.append("✅ Suggested Fixes:")
        suggestions = result["suggestions"]
        
        if isinstance(suggestions, str):
            output_parts.append(suggestions)
        else:
            for i, suggestion in enumerate(suggestions[:3], 1):  # Show first 3 suggestions
                output_parts.append(f"   {i}. {suggestion.title}")
                output_parts.append(f"      {suggestion.description}")
                
                if suggestion.commands:
                    output_parts.append("      Commands:")
                    for cmd in suggestion.commands[:2]:  # Show first 2 commands
                        output_parts.append(f"        $ {cmd}")
                
                output_parts.append("")
    
    return "\n".join(output_parts)


def format_pr_result(result: Dict[str, Any]) -> str:
    """Format PR creation result for tool output."""
    output_parts = []
    
    # Header
    output_parts.append("🚀 CI/CD Fix Pull Request")
    output_parts.append("=" * 40)
    
    # Repository info
    output_parts.append(f"📦 Repository: {result.get('repo', 'Unknown')}")
    if result.get('run_id'):
        output_parts.append(f"🔄 Run ID: {result['run_id']}")
    
    # PR creation status
    if result.get("pr_created"):
        output_parts.append("✅ PR Created Successfully!")
        output_parts.append(f"🔗 PR URL: {result.get('pr_url', 'Unknown')}")
    else:
        output_parts.append("❌ PR Creation Failed")
        if result.get("pr_error"):
            output_parts.append(f"   Error: {result['pr_error']}")
    
    output_parts.append("")
    
    # Debug summary
    if "error_summary" in result:
        summary = result["error_summary"]
        output_parts.append("❌ Issues Found:")
        output_parts.append(f"   Total Errors: {summary.get('total_errors', 0)}")
        
        if "error_types" in summary and summary["error_types"]:
            for error_type, count in summary["error_types"].items():
                output_parts.append(f"   • {error_type}: {count}")
        
        output_parts.append("")
    
    # Fixes applied
    if "suggestions" in result:
        output_parts.append("✅ Fixes Applied:")
        suggestions = result["suggestions"]
        
        if isinstance(suggestions, list):
            for i, suggestion in enumerate(suggestions[:5], 1):  # Show first 5
                # Handle both FixSuggestion objects and dictionaries
                if hasattr(suggestion, 'title'):
                    title = suggestion.title
                    confidence = suggestion.confidence
                else:
                    title = suggestion.get('title', 'Unknown fix')
                    confidence = suggestion.get('confidence')
                
                output_parts.append(f"   {i}. {title}")
                if confidence:
                    output_parts.append(f"      Confidence: {confidence:.1%}")
        
        output_parts.append("")
    
    # Next steps
    if result.get("pr_created"):
        output_parts.append("📋 Next Steps:")
        output_parts.append("   1. Review the PR changes")
        output_parts.append("   2. Run the workflow to verify fixes")
        output_parts.append("   3. Merge if tests pass")
        output_parts.append("   4. Monitor for any new issues")
    
    return "\n".join(output_parts)


def format_status_result(result: Dict[str, Any]) -> str:
    """Format status result for tool output."""
    output_parts = []
    
    # Header
    output_parts.append("📊 CI/CD Workflow Status")
    output_parts.append("=" * 40)
    
    # Repository info
    output_parts.append(f"📦 Repository: {result.get('repo', 'Unknown')}")
    output_parts.append(f"🌿 Branch: {result.get('branch', 'Unknown')}")
    
    if result.get('workflow_name'):
        output_parts.append(f"📋 Workflow: {result['workflow_name']}")
    
    output_parts.append("")
    
    # Status summary
    output_parts.append(f"❌ Failed Runs: {result.get('failed_runs_count', 0)}")
    output_parts.append(f"⏰ Last Checked: {result.get('last_checked', 'Unknown')}")
    
    # Recent failures
    if "recent_failures" in result and result["recent_failures"]:
        output_parts.append("")
        output_parts.append("🔍 Recent Failures:")
        for failure in result["recent_failures"][:3]:  # Show last 3
            output_parts.append(f"   • Run #{failure['id']}: {failure['name']}")
            output_parts.append(f"     Created: {failure['created_at']}")
    
    # Latest failure details
    if "latest_failure" in result:
        latest = result["latest_failure"]
        output_parts.append("")
        output_parts.append("🚨 Latest Failure:")
        output_parts.append(f"   Run ID: {latest['id']}")
        output_parts.append(f"   Name: {latest['name']}")
        output_parts.append(f"   Created: {latest['created_at']}")
        output_parts.append(f"   URL: {latest['html_url']}")
    
    return "\n".join(output_parts)


def format_pattern_analysis(result: Dict[str, Any]) -> str:
    """Format pattern analysis for tool output."""
    output_parts = []
    
    # Header
    output_parts.append("📈 CI/CD Error Pattern Analysis")
    output_parts.append("=" * 50)
    
    # Repository info
    output_parts.append(f"📦 Repository: {result.get('repo', 'Unknown')}")
    output_parts.append(f"🌿 Branch: {result.get('branch', 'Unknown')}")
    output_parts.append(f"📅 Analysis Period: {result.get('analysis_period_days', 0)} days")
    output_parts.append(f"🔍 Failures Analyzed: {result.get('total_failures_analyzed', 0)}")
    
    output_parts.append("")
    
    # Most common errors
    if "most_common_errors" in result and result["most_common_errors"]:
        output_parts.append("❌ Most Common Errors:")
        for error_type, count in result["most_common_errors"]:
            output_parts.append(f"   • {error_type}: {count} occurrences")
        output_parts.append("")
    
    # Most failing stages
    if "most_failing_stages" in result and result["most_failing_stages"]:
        output_parts.append("🚨 Most Failing Stages:")
        for stage, count in result["most_failing_stages"]:
            output_parts.append(f"   • {stage}: {count} failures")
        output_parts.append("")
    
    # Error patterns breakdown
    if "error_patterns" in result and result["error_patterns"]:
        output_parts.append("📊 Error Pattern Breakdown:")
        for error_type, count in result["error_patterns"].items():
            output_parts.append(f"   • {error_type}: {count}")
        output_parts.append("")
    
    # Stage failures breakdown
    if "stage_failures" in result and result["stage_failures"]:
        output_parts.append("📊 Stage Failure Breakdown:")
        for stage, count in result["stage_failures"].items():
            output_parts.append(f"   • {stage}: {count}")
    
    output_parts.append("")
    output_parts.append(f"⏰ Analyzed at: {result.get('analyzed_at', 'Unknown')}")
    
    return "\n".join(output_parts)
