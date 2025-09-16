#!/usr/bin/env python3
"""
AI-powered fix suggestions for CI/CD debugger.
"""

import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FixSuggestion:
    """Represents a suggested fix for a CI/CD failure."""
    title: str
    description: str
    commands: List[str]
    files_to_modify: List[str]
    confidence: float
    fix_type: str  # "command", "file_edit", "config_change", "dependency"
    priority: str = "medium"  # "low", "medium", "high", "critical"


class FixSuggester:
    """Suggests fixes for CI/CD failures using AI and rule-based approaches."""
    
    def __init__(self, model=None, readonly_mode=True):
        self.model = model
        self.readonly_mode = readonly_mode
        self.rule_based_fixes = self._initialize_rule_based_fixes()
    
    def _is_readonly_command(self, command: str) -> bool:
        """Check if a command is read-only and safe."""
        command_lower = command.lower()
        
        # Safe read-only commands
        safe_patterns = [
            'echo', 'cat', 'ls', 'find', 'grep', 'head', 'tail',
            'python --version', 'python3 --version',
            'git status', 'git log', 'git show',
            'gh run view', 'gh run list',
            'curl -I', 'ping', 'nslookup',
            'ps aux', 'df -h', 'free -h',
            'which', 'whereis', 'type',
            'python -m py_compile',  # Only checks syntax, doesn't modify
            'flake8', 'black --check',  # Only checks, doesn't modify
            'pytest --collect-only',  # Only collects, doesn't run
            'npm list', 'pip list', 'pip show'
        ]
        
        # Dangerous patterns that modify files
        dangerous_patterns = [
            'rm ', 'rmdir', 'del ', 'delete',
            'mv ', 'move', 'cp ', 'copy',
            'chmod', 'chown', 'chgrp',
            'sed -i', 'awk -i',  # In-place editing
            '>', '>>',  # File redirection
            'install', 'uninstall', 'remove',
            'update', 'upgrade', 'modify',
            'create', 'add', 'set',
            'export ', 'unset ',
            'git add', 'git commit', 'git push', 'git pull',
            'npm install', 'npm uninstall', 'npm update',
            'pip install', 'pip uninstall', 'pip upgrade',
            'sudo ', 'source ', 'activate'
        ]
        
        # Check if command contains dangerous patterns
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return False
        
        # Check if command contains safe patterns
        for pattern in safe_patterns:
            if pattern in command_lower:
                return True
        
        # Default to unsafe if we can't determine
        return False
    
    def _filter_readonly_commands(self, commands: List[str]) -> List[str]:
        """Filter commands to only include read-only ones."""
        if not self.readonly_mode:
            return commands
        
        readonly_commands = []
        for command in commands:
            if self._is_readonly_command(command):
                readonly_commands.append(command)
        
        return readonly_commands
    
    def _initialize_rule_based_fixes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize rule-based fix suggestions."""
        return {
            "module_not_found": [
                {
                    "title": "Install Missing Python Package",
                    "description": "Add the missing package to requirements.txt or install it directly",
                    "commands": [
                        "pip install {missing_module}",
                        "echo '{missing_module}' >> requirements.txt"
                    ],
                    "files_to_modify": ["requirements.txt"],
                    "fix_type": "dependency",
                    "priority": "high"
                },
                {
                    "title": "Check Virtual Environment",
                    "description": "Ensure you're in the correct virtual environment",
                    "commands": [
                        "source venv/bin/activate",
                        "pip list | grep {missing_module}"
                    ],
                    "files_to_modify": [],
                    "fix_type": "config_change",
                    "priority": "medium"
                }
            ],
            "command_not_found": [
                {
                    "title": "Install Missing Tool",
                    "description": "Install the missing command/tool",
                    "commands": [
                        "sudo apt-get install {command_name}",
                        "brew install {command_name}",
                        "npm install -g {command_name}"
                    ],
                    "files_to_modify": [],
                    "fix_type": "dependency",
                    "priority": "high"
                },
                {
                    "title": "Add to PATH",
                    "description": "Ensure the tool is in the system PATH",
                    "commands": [
                        "export PATH=$PATH:/path/to/tool",
                        "which {command_name}"
                    ],
                    "files_to_modify": [".bashrc", ".zshrc"],
                    "fix_type": "config_change",
                    "priority": "medium"
                }
            ],
            "file_not_found": [
                {
                    "title": "Create Missing File",
                    "description": "Create the missing file that the script is trying to access",
                    "commands": [
                        "echo 'File content here' > /non/existent/file.txt",
                        "mkdir -p /non/existent"
                    ],
                    "files_to_modify": ["missing_file.txt"],
                    "fix_type": "file_edit",
                    "priority": "high"
                },
                {
                    "title": "Check File Path",
                    "description": "Verify the file path is correct and the file exists",
                    "commands": [
                        "find . -name '$(basename {file_path})'",
                        "pwd && ls -la"
                    ],
                    "files_to_modify": [],
                    "fix_type": "command",
                    "priority": "medium"
                }
            ],
            "permission_denied": [
                {
                    "title": "Fix File Permissions",
                    "description": "Change file permissions to allow execution/access",
                    "commands": [
                        "chmod +x {file_path}",
                        "chmod 755 {file_path}",
                        "sudo chown $USER {file_path}"
                    ],
                    "files_to_modify": [],
                    "fix_type": "command",
                    "priority": "high"
                },
                {
                    "title": "Check Directory Permissions",
                    "description": "Ensure the directory has proper permissions",
                    "commands": [
                        "ls -la {directory}",
                        "chmod 755 {directory}"
                    ],
                    "files_to_modify": [],
                    "fix_type": "command",
                    "priority": "medium"
                }
            ],
            "test_failure": [
                {
                    "title": "Run Tests Locally",
                    "description": "Run the failing tests locally to debug",
                    "commands": [
                        "python -m pytest {test_file} -v",
                        "python -m pytest {test_file}::test_name -v -s"
                    ],
                    "files_to_modify": [],
                    "fix_type": "command",
                    "priority": "medium"
                },
                {
                    "title": "Check Test Dependencies",
                    "description": "Ensure all test dependencies are installed",
                    "commands": [
                        "pip install -r requirements-dev.txt",
                        "pip install pytest pytest-cov"
                    ],
                    "files_to_modify": ["requirements-dev.txt"],
                    "fix_type": "dependency",
                    "priority": "medium"
                }
            ],
            "build_failure": [
                {
                    "title": "Clean and Rebuild",
                    "description": "Clean build artifacts and rebuild",
                    "commands": [
                        "make clean",
                        "rm -rf build/ dist/",
                        "python setup.py clean --all"
                    ],
                    "files_to_modify": [],
                    "fix_type": "command",
                    "priority": "medium"
                },
                {
                    "title": "Check Build Dependencies",
                    "description": "Ensure all build dependencies are installed",
                    "commands": [
                        "pip install -r requirements.txt",
                        "npm install",
                        "bundle install"
                    ],
                    "files_to_modify": ["requirements.txt", "package.json", "Gemfile"],
                    "fix_type": "dependency",
                    "priority": "high"
                }
            ],
            "syntax_error": [
                {
                    "title": "Fix Syntax Errors",
                    "description": "Correct Python syntax errors in source code",
                    "commands": [
                        "python -m py_compile {file_path}",
                        "python -m flake8 {file_path} --fix",
                        "black {file_path}"
                    ],
                    "files_to_modify": ["*.py"],
                    "fix_type": "code_fix",
                    "priority": "high"
                },
                {
                    "title": "Check for Missing Colons",
                    "description": "Look for missing colons in function definitions",
                    "commands": [
                        "grep -n 'def .*[^:]$' {file_path}",
                        "python -m py_compile {file_path}"
                    ],
                    "files_to_modify": ["*.py"],
                    "fix_type": "code_fix",
                    "priority": "high"
                }
            ],
            "security_vulnerability": [
                {
                    "title": "Run Security Scan",
                    "description": "Scan for security vulnerabilities",
                    "commands": [
                        "bandit -r src/",
                        "safety check",
                        "npm audit",
                        "snyk test"
                    ],
                    "files_to_modify": [],
                    "fix_type": "security",
                    "priority": "critical"
                },
                {
                    "title": "Update Dependencies",
                    "description": "Update packages with known vulnerabilities",
                    "commands": [
                        "pip install --upgrade {package_name}",
                        "npm update",
                        "bundle update"
                    ],
                    "files_to_modify": ["requirements.txt", "package.json"],
                    "fix_type": "dependency",
                    "priority": "high"
                }
            ],
            "performance_issue": [
                {
                    "title": "Profile Performance",
                    "description": "Profile the application to identify bottlenecks",
                    "commands": [
                        "python -m cProfile -o profile.stats {script}",
                        "python -m pstats profile.stats",
                        "python -m memory_profiler {script}"
                    ],
                    "files_to_modify": [],
                    "fix_type": "optimization",
                    "priority": "medium"
                },
                {
                    "title": "Check Performance Thresholds",
                    "description": "Review and adjust performance thresholds",
                    "commands": [
                        "python -m pytest tests/performance/ -v",
                        "locust --host=http://localhost:8000"
                    ],
                    "files_to_modify": ["tests/performance/"],
                    "fix_type": "config_change",
                    "priority": "medium"
                }
            ],
            "deployment_permission": [
                {
                    "title": "Check GitHub Permissions",
                    "description": "Verify GitHub token and repository permissions",
                    "commands": [
                        "gh auth status",
                        "gh repo view --json permissions",
                        "echo $GITHUB_TOKEN"
                    ],
                    "files_to_modify": [],
                    "fix_type": "config_change",
                    "priority": "high"
                },
                {
                    "title": "Update Environment Access",
                    "description": "Ensure proper access to deployment environment",
                    "commands": [
                        "gh secret list",
                        "gh environment list",
                        "gh repo view --json environments"
                    ],
                    "files_to_modify": [".github/workflows/*.yml"],
                    "fix_type": "config_change",
                    "priority": "high"
                }
            ],
            "database_error": [
                {
                    "title": "Check Database Connection",
                    "description": "Verify database connection and credentials",
                    "commands": [
                        "psql $DATABASE_URL -c 'SELECT 1'",
                        "python -c 'import psycopg2; print(psycopg2.connect(\"$DATABASE_URL\"))'"
                    ],
                    "files_to_modify": [],
                    "fix_type": "config_change",
                    "priority": "high"
                },
                {
                    "title": "Verify Database Service",
                    "description": "Check if database service is running",
                    "commands": [
                        "docker ps | grep postgres",
                        "systemctl status postgresql",
                        "pg_isready -h localhost -p 5432"
                    ],
                    "files_to_modify": [],
                    "fix_type": "service",
                    "priority": "high"
                }
            ],
            "docker_error": [
                {
                    "title": "Check Docker Build",
                    "description": "Debug Docker build issues",
                    "commands": [
                        "docker build -t test-image .",
                        "docker run --rm test-image",
                        "docker logs {container_id}"
                    ],
                    "files_to_modify": ["Dockerfile"],
                    "fix_type": "build",
                    "priority": "high"
                },
                {
                    "title": "Verify Dockerfile",
                    "description": "Check Dockerfile syntax and dependencies",
                    "commands": [
                        "docker build --no-cache .",
                        "docker run --rm {image} ls -la"
                    ],
                    "files_to_modify": ["Dockerfile"],
                    "fix_type": "code_fix",
                    "priority": "medium"
                }
            ],
            "node_error": [
                {
                    "title": "Fix Node.js Dependencies",
                    "description": "Resolve Node.js dependency issues",
                    "commands": [
                        "npm ci",
                        "npm audit fix",
                        "rm -rf node_modules package-lock.json && npm install"
                    ],
                    "files_to_modify": ["package.json", "package-lock.json"],
                    "fix_type": "dependency",
                    "priority": "high"
                },
                {
                    "title": "Check Node.js Version",
                    "description": "Ensure correct Node.js version",
                    "commands": [
                        "node --version",
                        "npm --version",
                        "nvm use {version}"
                    ],
                    "files_to_modify": [".nvmrc", "package.json"],
                    "fix_type": "config_change",
                    "priority": "medium"
                }
            ],
            "build_failure": [
                {
                    "title": "Install Build Dependencies",
                    "description": "Install system build dependencies",
                    "commands": [
                        "pip install build wheel",
                        "apt-get install build-essential"
                    ],
                    "files_to_modify": [],
                    "fix_type": "dependency",
                    "priority": "high"
                }
            ],
            "configuration_error": [
                {
                    "title": "Check Environment Variables",
                    "description": "Verify all required environment variables are set",
                    "commands": [
                        "echo $REQUIRED_VAR",
                        "export REQUIRED_VAR=value"
                    ],
                    "files_to_modify": [".env", ".github/workflows/*.yml"],
                    "fix_type": "config_change",
                    "priority": "high"
                },
                {
                    "title": "Validate Configuration Files",
                    "description": "Check configuration file syntax and values",
                    "commands": [
                        "python -c 'import yaml; yaml.safe_load(open(\"config.yml\"))'",
                        "python -c 'import json; json.load(open(\"config.json\"))'"
                    ],
                    "files_to_modify": ["config.yml", "config.json"],
                    "fix_type": "file_edit",
                    "priority": "medium"
                },
                {
                    "title": "Update Python Version",
                    "description": "Update to a supported Python version for Ubuntu 24.04",
                    "commands": [
                        "python --version",
                        "python3 --version"
                    ],
                    "files_to_modify": [".github/workflows/*.yml"],
                    "fix_type": "config_change",
                    "priority": "high"
                },
                {
                    "title": "Update Deprecated Actions",
                    "description": "Update deprecated GitHub Actions to latest versions",
                    "commands": [
                        "grep -r 'actions/upload-artifact@v3' .github/workflows/",
                        "sed -i 's/actions\\/upload-artifact@v3/actions\\/upload-artifact@v4/g' .github/workflows/*.yml"
                    ],
                    "files_to_modify": [".github/workflows/*.yml"],
                    "fix_type": "file_edit",
                    "priority": "high"
                }
            ]
        }
    
    def suggest_fixes(self, errors: List[Any], logs: Dict[str, str] = None) -> List[FixSuggestion]:
        """
        Suggest fixes for the given errors.
        
        Args:
            errors: List of parsed errors
            logs: Original logs for context (optional)
            
        Returns:
            List of suggested fixes
        """
        suggestions = []
        
        # Generate rule-based suggestions
        rule_suggestions = self._generate_rule_based_suggestions(errors)
        suggestions.extend(rule_suggestions)
        
        # Generate AI-based suggestions if model is available
        if self.model:
    
            ai_suggestions = self._generate_ai_suggestions(errors, logs)

            suggestions.extend(ai_suggestions)
        else:
            print("⚠️  No AI model available - using rule-based suggestions only")
        
        # Remove duplicates based on title and fix_type
        unique_suggestions = self._remove_duplicate_suggestions(suggestions)
        
        # Prioritize AI suggestions if available
        ai_suggestions = [s for s in unique_suggestions if s.fix_type == "ai_generated"]
        rule_suggestions = [s for s in unique_suggestions if s.fix_type != "ai_generated"]
        
        if ai_suggestions:
            # If we have AI suggestions, put them first
            unique_suggestions = ai_suggestions + rule_suggestions
        else:
            # Otherwise sort by priority and confidence
            unique_suggestions.sort(key=lambda x: (self._priority_score(x.priority), x.confidence), reverse=True)
        
        return unique_suggestions
    
    def _remove_duplicate_suggestions(self, suggestions: List[FixSuggestion]) -> List[FixSuggestion]:
        """Remove duplicate suggestions based on title and fix_type."""
        seen = set()
        unique_suggestions = []
        
        for suggestion in suggestions:
            # Create a unique key based on title and fix_type
            key = (suggestion.title, suggestion.fix_type)
            
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
            else:
                # If we have a duplicate, keep the one with higher confidence
                existing_index = next(i for i, s in enumerate(unique_suggestions) 
                                    if (s.title, s.fix_type) == key)
                if suggestion.confidence > unique_suggestions[existing_index].confidence:
                    unique_suggestions[existing_index] = suggestion
        
        return unique_suggestions
    
    def _generate_rule_based_suggestions(self, errors: List[Any]) -> List[FixSuggestion]:
        """Generate rule-based fix suggestions."""
        suggestions = []
        
        # Group errors by type to avoid duplicates
        errors_by_type = {}
        for error in errors:
            error_type = error.error_type.value
            if error_type not in errors_by_type:
                errors_by_type[error_type] = []
            errors_by_type[error_type].append(error)
        
        # Generate one suggestion per error type
        for error_type, type_errors in errors_by_type.items():
            if error_type in self.rule_based_fixes:
                for fix_rule in self.rule_based_fixes[error_type]:
                    # Use the first error of this type for customization
                    # but consider all errors of this type for context
                    primary_error = type_errors[0]
                    
                    # Customize the fix based on error context
                    customized_fix = self._customize_fix(fix_rule, primary_error)
                    if customized_fix:
                        # Enhance description to mention multiple errors if applicable
                        if len(type_errors) > 1:
                            customized_fix.description += f" (Addresses {len(type_errors)} similar errors)"
                        
                        suggestions.append(customized_fix)
        
        return suggestions
    
    def _customize_fix(self, fix_rule: Dict[str, Any], error: Any) -> Optional[FixSuggestion]:
        """Customize a fix rule based on error context."""
        try:
            # Replace placeholders in commands
            commands = []
            customization_score = 0.0  # Track how well we can customize
            
            for cmd in fix_rule["commands"]:
                customized_cmd = cmd
                
                # Replace common placeholders
                if "{missing_module}" in cmd and error.context.get("missing_module"):
                    customized_cmd = cmd.replace("{missing_module}", error.context["missing_module"])
                    customization_score += 0.2
                
                if "{file_path}" in cmd and error.file_path:
                    customized_cmd = cmd.replace("{file_path}", error.file_path)
                    customization_score += 0.2
                
                if "{command_name}" in cmd:
                    # Extract command name from error message
                    import re
                    cmd_match = re.search(r"command.*?['\"]([^'\"]+)['\"]", error.message, re.IGNORECASE)
                    if cmd_match:
                        customized_cmd = cmd.replace("{command_name}", cmd_match.group(1))
                        customization_score += 0.2
                
                commands.append(customized_cmd)
            
            # Filter commands to read-only if enabled
            filtered_commands = self._filter_readonly_commands(commands)
            
            # Skip this suggestion if no read-only commands available and in readonly mode
            if self.readonly_mode and not filtered_commands:
                return None
            
            # Calculate dynamic confidence based on error type and customization
            base_confidence = self._calculate_base_confidence(error, fix_rule)
            final_confidence = min(0.95, base_confidence + customization_score)
            
            # Adjust title and description for read-only mode
            title = fix_rule["title"]
            description = fix_rule["description"]
            
            if self.readonly_mode:
                title += " (Read-Only)"
                description += " [SAFE: Read-only commands only]"
            
            return FixSuggestion(
                title=title,
                description=description,
                commands=filtered_commands,
                files_to_modify=fix_rule["files_to_modify"],
                confidence=final_confidence,
                fix_type=fix_rule["fix_type"],
                priority=fix_rule["priority"]
            )
            
        except Exception as e:
            logger.warning(f"Failed to customize fix: {e}")
            return None
    
    def _calculate_base_confidence(self, error: Any, fix_rule: Dict[str, Any]) -> float:
        """Calculate base confidence score based on error type and fix rule."""
        # Base confidence by error type
        error_type_confidence = {
            "module_not_found": 0.85,
            "command_not_found": 0.90,
            "file_not_found": 0.83,
            "permission_denied": 0.80,
            "test_failure": 0.70,
            "build_failure": 0.75,
            "syntax_error": 0.95,
            "configuration_error": 0.85,
            "security_vulnerability": 0.90,
            "performance_issue": 0.65,
            "deployment_permission": 0.80,
            "database_error": 0.75,
            "docker_error": 0.80,
            "node_error": 0.85,
            "unknown_error": 0.50
        }
        
        # Get base confidence for this error type
        base_confidence = error_type_confidence.get(error.error_type.value, 0.70)
        
        # Adjust based on fix rule priority
        priority_boost = {
            "critical": 0.10,
            "high": 0.05,
            "medium": 0.00,
            "low": -0.05
        }
        
        priority_boost_value = priority_boost.get(fix_rule.get("priority", "medium"), 0.00)
        
        # Adjust based on error message specificity
        message_specificity = 0.0
        if error.message and len(error.message) > 50:
            message_specificity = 0.05  # More specific error messages get higher confidence
        
        # Adjust based on whether we have file path or command context
        context_boost = 0.0
        if error.file_path:
            context_boost += 0.05
        if error.command:
            context_boost += 0.05
        if error.exit_code:
            context_boost += 0.03
        
        final_confidence = base_confidence + priority_boost_value + message_specificity + context_boost
        
        # Ensure confidence is between 0.1 and 0.95
        return max(0.1, min(0.95, final_confidence))
    
    def _generate_ai_suggestions(self, errors: List[Any], logs: Dict[str, str] = None) -> List[FixSuggestion]:
        """Generate AI-based fix suggestions."""
        if not self.model:
            return []
        
        try:
            # Prepare context for AI
            error_summary = self._prepare_error_summary(errors)
            log_context = self._prepare_log_context(logs) if logs else ""
            
            prompt = f"""
            You are a CI/CD debugging expert. Analyze this specific error and provide ONE fix.
            
            ERROR DETAILS:
            {error_summary}
            
            LOG CONTEXT:
            {log_context}
            
            TASK: Provide exactly ONE fix for this specific error in this exact format:
            
            Title: [Brief title of the fix]
            Description: [Detailed description of what this fix does]
            Command: [Specific command to run]
            
            EXAMPLES:
            - For "file not found" errors: Create the missing file or fix the path
            - For "command not found" errors: Install the missing tool
            - For "permission denied" errors: Fix file permissions
            - For "module not found" errors: Install missing Python packages
            
            Now provide your fix for the above error:
            """
            
            # Get AI response
            from iagent.models import ChatMessage
            messages = [ChatMessage(role="user", content=prompt)]
            model_response = self.model.generate(messages)
            response = model_response.content
            

            
            # Parse AI response into FixSuggestion objects
            return self._parse_ai_response(response)
            
        except Exception as e:
            logger.error(f"Failed to generate AI suggestions: {e}")
            return []
    
    def _prepare_error_summary(self, errors: List[Any]) -> str:
        """Prepare a summary of errors for AI analysis."""
        summary_parts = []
        
        for error in errors:
            summary_parts.append(f"- {error.error_type.value}: {error.message}")
            if error.file_path:
                summary_parts.append(f"  File: {error.file_path}")
            if error.command:
                summary_parts.append(f"  Command: {error.command}")
            if error.exit_code:
                summary_parts.append(f"  Exit Code: {error.exit_code}")
        
        return "\n".join(summary_parts)
    
    def _prepare_log_context(self, logs: Dict[str, str]) -> str:
        """Prepare log context for AI analysis."""
        context_parts = []
        
        for job_name, log_content in logs.items():
            # Take the last 500 characters of each log for context
            context = log_content[-500:] if len(log_content) > 500 else log_content
            context_parts.append(f"Job: {job_name}\n{context}")
        
        return "\n\n".join(context_parts)
    
    def _parse_ai_response(self, response: str) -> List[FixSuggestion]:
        """Parse AI response into FixSuggestion objects."""
        # This is a simplified parser - in practice, you'd want more robust parsing
        suggestions = []
        
        # Look for structured patterns in the response
        lines = response.split('\n')
        current_suggestion = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('Title:') or line.startswith('Fix:'):
                if current_suggestion:
                    suggestions.append(current_suggestion)
                
                title = line.split(':', 1)[1].strip()
                current_suggestion = FixSuggestion(
                    title=title,
                    description="",
                    commands=[],
                    files_to_modify=[],
                    confidence=self._calculate_ai_confidence(response),  # Dynamic confidence for AI suggestions
                    fix_type="ai_generated",
                    priority="medium"
                )
            
            elif line.startswith('Description:') and current_suggestion:
                current_suggestion.description = line.split(':', 1)[1].strip()
            
            elif line.startswith('Command:') and current_suggestion:
                command = line.split(':', 1)[1].strip()
                current_suggestion.commands.append(command)
        
        if current_suggestion:
            suggestions.append(current_suggestion)
        
        return suggestions
    
    def _calculate_ai_confidence(self, response: str) -> float:
        """Calculate confidence for AI-generated suggestions based on response quality."""
        # Base confidence for AI suggestions
        base_confidence = 0.6
        
        # Adjust based on response length (longer responses might be more detailed)
        length_boost = min(0.1, len(response) / 1000)  # Max 0.1 boost for long responses
        
        # Adjust based on response structure (presence of commands, descriptions)
        structure_boost = 0.0
        if "command:" in response.lower():
            structure_boost += 0.05
        if "description:" in response.lower():
            structure_boost += 0.05
        if "file:" in response.lower():
            structure_boost += 0.03
        
        # Adjust based on specificity indicators
        specificity_boost = 0.0
        if any(word in response.lower() for word in ["specific", "exact", "precise", "definite"]):
            specificity_boost += 0.05
        
        # Adjust based on action-oriented language
        action_boost = 0.0
        if any(word in response.lower() for word in ["run", "execute", "install", "update", "fix", "modify"]):
            action_boost += 0.03
        
        final_confidence = base_confidence + length_boost + structure_boost + specificity_boost + action_boost
        
        # Ensure confidence is between 0.3 and 0.85 for AI suggestions
        return max(0.3, min(0.85, final_confidence))
    
    def _priority_score(self, priority: str) -> int:
        """Convert priority string to numeric score for sorting."""
        priority_scores = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1
        }
        return priority_scores.get(priority, 2)
    
    def format_suggestions_for_output(self, suggestions: List[FixSuggestion]) -> str:
        """Format suggestions for CLI output."""
        if not suggestions:
            return "No specific fixes found. Please check the logs manually."
        
        output_parts = []
        
        for i, suggestion in enumerate(suggestions, 1):
            output_parts.append(f"{i}. {suggestion.title}")
            output_parts.append(f"   Description: {suggestion.description}")
            output_parts.append(f"   Priority: {suggestion.priority}")
            output_parts.append(f"   Confidence: {suggestion.confidence:.1%}")
            
            if suggestion.commands:
                output_parts.append("   Commands to run:")
                for cmd in suggestion.commands:
                    output_parts.append(f"     $ {cmd}")
            
            if suggestion.files_to_modify:
                output_parts.append("   Files to modify:")
                for file_path in suggestion.files_to_modify:
                    output_parts.append(f"     - {file_path}")
            
            output_parts.append("")
        
        return "\n".join(output_parts)
