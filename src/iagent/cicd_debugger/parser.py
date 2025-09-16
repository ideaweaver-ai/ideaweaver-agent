#!/usr/bin/env python3
"""
Log parsing and error classification for CI/CD debugger.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur in CI/CD pipelines."""
    MODULE_NOT_FOUND = "module_not_found"
    COMMAND_NOT_FOUND = "command_not_found"
    PERMISSION_DENIED = "permission_denied"
    TEST_FAILURE = "test_failure"
    BUILD_FAILURE = "build_failure"
    DEPLOYMENT_FAILURE = "deployment_failure"
    CONFIGURATION_ERROR = "configuration_error"
    FILE_NOT_FOUND = "file_not_found"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    SYNTAX_ERROR = "syntax_error"
    SECURITY_VULNERABILITY = "security_vulnerability"
    PERFORMANCE_ISSUE = "performance_issue"
    DEPLOYMENT_PERMISSION = "deployment_permission"
    DATABASE_ERROR = "database_error"
    DOCKER_ERROR = "docker_error"
    NODE_ERROR = "node_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorPattern:
    """Pattern for detecting specific types of errors."""
    error_type: ErrorType
    patterns: List[str]
    severity: str = "error"
    description: str = ""
    
    def matches(self, text: str) -> bool:
        """Check if any pattern matches the text."""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in self.patterns)


@dataclass
class ParsedError:
    """Represents a parsed error from logs."""
    error_type: ErrorType
    message: str
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    command: Optional[str] = None
    exit_code: Optional[int] = None
    severity: str = "error"
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


class LogParser:
    """Parses CI/CD logs to extract errors and classify them."""
    
    def __init__(self):
        self.error_patterns = self._initialize_error_patterns()
    
    def _initialize_error_patterns(self) -> List[ErrorPattern]:
        """Initialize common error patterns."""
        return [
            ErrorPattern(
                error_type=ErrorType.MODULE_NOT_FOUND,
                patterns=[
                    r"modulenotfounderror: no module named ['\"]([^'\"]+)['\"]",
                    r"import.*error.*no module named",
                    r"package.*not found",
                    r"cannot find module"
                ],
                description="Python module or package not found"
            ),
            ErrorPattern(
                error_type=ErrorType.COMMAND_NOT_FOUND,
                patterns=[
                    r"command not found",
                    r"executable not found",
                    r"no such file or directory.*command",
                    r"command.*not found"
                ],
                description="Command or executable not found in PATH"
            ),
            ErrorPattern(
                error_type=ErrorType.PERMISSION_DENIED,
                patterns=[
                    r"permission denied",
                    r"access denied",
                    r"insufficient permissions",
                    r"eacces",
                    r"operation not permitted"
                ],
                description="Permission or access denied error"
            ),
            ErrorPattern(
                error_type=ErrorType.TEST_FAILURE,
                patterns=[
                    r"test.*failed",
                    r"assertion.*failed",
                    r"test.*error",
                    r"failed.*tests",
                    r"test.*suite.*failed"
                ],
                description="Test failure or test suite error"
            ),
            ErrorPattern(
                error_type=ErrorType.BUILD_FAILURE,
                patterns=[
                    r"build.*failed",
                    r"compilation.*failed",
                    r"build.*error",
                    r"make.*error",
                    r"cmake.*error"
                ],
                description="Build or compilation failure"
            ),
            ErrorPattern(
                error_type=ErrorType.DEPLOYMENT_FAILURE,
                patterns=[
                    r"deployment.*failed",
                    r"deploy.*failed",
                    r"kubernetes.*error",
                    r"docker.*error",
                    r"container.*failed"
                ],
                description="Deployment or container error"
            ),
            ErrorPattern(
                error_type=ErrorType.CONFIGURATION_ERROR,
                patterns=[
                    r"configuration.*error",
                    r"config.*not found",
                    r"invalid.*configuration",
                    r"missing.*config",
                    r"environment.*variable.*not set"
                ],
                description="Configuration or environment variable error"
            ),
            ErrorPattern(
                error_type=ErrorType.FILE_NOT_FOUND,
                patterns=[
                    r"no such file or directory",
                    r"file.*not found",
                    r"cannot.*find.*file",
                    r"file.*does.*not.*exist",
                    r"cat:.*no such file"
                ],
                description="File not found or missing file error"
            ),
            ErrorPattern(
                error_type=ErrorType.NETWORK_ERROR,
                patterns=[
                    r"connection.*refused",
                    r"timeout.*error",
                    r"network.*error",
                    r"dns.*error",
                    r"ssl.*error"
                ],
                description="Network connectivity error"
            ),
            ErrorPattern(
                error_type=ErrorType.TIMEOUT_ERROR,
                patterns=[
                    r"timeout",
                    r"timed out",
                    r"execution.*timeout",
                    r"request.*timeout"
                ],
                description="Operation timed out"
            ),
            ErrorPattern(
                error_type=ErrorType.SYNTAX_ERROR,
                patterns=[
                    r"syntax.*error",
                    r"invalid.*syntax",
                    r"expected.*:",
                    r"indentation.*error",
                    r"unexpected.*token"
                ],
                description="Python syntax error"
            ),
            ErrorPattern(
                error_type=ErrorType.SECURITY_VULNERABILITY,
                patterns=[
                    r"vulnerability",
                    r"security.*issue",
                    r"critical.*vulnerability",
                    r"high.*severity",
                    r"security.*scan.*failed"
                ],
                description="Security vulnerability detected"
            ),
            ErrorPattern(
                error_type=ErrorType.PERFORMANCE_ISSUE,
                patterns=[
                    r"performance.*threshold",
                    r"response.*time.*exceeded",
                    r"throughput.*below.*requirement",
                    r"performance.*regression",
                    r"slow.*performance"
                ],
                description="Performance threshold exceeded"
            ),
            ErrorPattern(
                error_type=ErrorType.DEPLOYMENT_PERMISSION,
                patterns=[
                    r"insufficient.*permissions.*to.*deploy",
                    r"admin.*access.*required",
                    r"deployment.*permission.*denied",
                    r"environment.*access.*denied"
                ],
                description="Deployment permission error"
            ),
            ErrorPattern(
                error_type=ErrorType.DATABASE_ERROR,
                patterns=[
                    r"database.*connection.*failed",
                    r"postgres.*error",
                    r"sql.*error",
                    r"connection.*refused.*postgres",
                    r"database.*unavailable"
                ],
                description="Database connection or query error"
            ),
            ErrorPattern(
                error_type=ErrorType.DOCKER_ERROR,
                patterns=[
                    r"docker.*build.*failed",
                    r"container.*failed",
                    r"image.*not.*found",
                    r"docker.*error",
                    r"container.*exited.*with.*code"
                ],
                description="Docker build or container error"
            ),
            ErrorPattern(
                error_type=ErrorType.NODE_ERROR,
                patterns=[
                    r"npm.*error",
                    r"node.*error",
                    r"webpack.*error",
                    r"jest.*failed",
                    r"eslint.*error"
                ],
                description="Node.js build or test error"
            ),
            ErrorPattern(
                error_type=ErrorType.CONFIGURATION_ERROR,
                patterns=[
                    r"version.*not.*found",
                    r"python.*version.*not.*found",
                    r"architecture.*not.*found",
                    r"version.*with.*architecture.*not.*found"
                ],
                description="Python version or architecture not found"
            ),
            ErrorPattern(
                error_type=ErrorType.CONFIGURATION_ERROR,
                patterns=[
                    r"deprecated.*version",
                    r"deprecated.*action",
                    r"automatically.*failed.*because.*deprecated",
                    r"upload-artifact.*v3.*deprecated"
                ],
                description="Deprecated action or version error"
            )
        ]
    
    def parse_logs(self, logs: Dict[str, str]) -> Dict[str, List[ParsedError]]:
        """
        Parse logs and extract errors.
        
        Args:
            logs: Dictionary with job names as keys and log content as values
            
        Returns:
            Dictionary with job names as keys and lists of parsed errors as values
        """
        results = {}
        
        for job_name, log_content in logs.items():
            errors = self._parse_single_log(log_content)
            results[job_name] = errors
        
        return results
    
    def _parse_single_log(self, log_content: str) -> List[ParsedError]:
        """
        Parse a single log file and extract errors.
        
        Args:
            log_content: Log content as string
            
        Returns:
            List of parsed errors
        """
        errors = []
        lines = log_content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for error patterns
            for pattern in self.error_patterns:
                if pattern.matches(line):
                    error = self._extract_error_details(line, line_num, pattern)
                    if error:
                        errors.append(error)
            
            # Look for exit codes
            exit_code_match = re.search(r'exit code (\d+)', line.lower())
            if exit_code_match:
                exit_code = int(exit_code_match.group(1))
                if exit_code != 0:
                    # Find the most recent error for this exit code
                    for error in reversed(errors):
                        if error.exit_code is None:
                            error.exit_code = exit_code
                            break
        
        return errors
    
    def _extract_error_details(self, line: str, line_number: int, pattern: ErrorPattern) -> Optional[ParsedError]:
        """
        Extract detailed error information from a line.
        
        Args:
            line: Log line
            line_number: Line number in the log
            pattern: Error pattern that matched
            
        Returns:
            ParsedError object or None
        """
        # Extract file path if present
        file_path = None
        file_match = re.search(r'([/\w\-\.]+\.(py|js|ts|java|cpp|c|h|go|rs|php|rb|yml|yaml|json|toml|ini|conf))', line)
        if file_match:
            file_path = file_match.group(1)
        
        # Extract command if present
        command = None
        command_match = re.search(r'(\$ [^\s]+.*?)(?:\s|$)', line)
        if command_match:
            command = command_match.group(1)
        
        # Extract exit code if present
        exit_code = None
        exit_match = re.search(r'exit code (\d+)', line.lower())
        if exit_match:
            exit_code = int(exit_match.group(1))
        
        # Extract module name for ModuleNotFoundError
        context = {}
        if pattern.error_type == ErrorType.MODULE_NOT_FOUND:
            module_match = re.search(r"no module named ['\"]([^'\"]+)['\"]", line, re.IGNORECASE)
            if module_match:
                context["missing_module"] = module_match.group(1)
        
        return ParsedError(
            error_type=pattern.error_type,
            message=line.strip(),
            line_number=line_number,
            file_path=file_path,
            command=command,
            exit_code=exit_code,
            severity=pattern.severity,
            context=context
        )
    
    def classify_failure_stage(self, errors: List[ParsedError]) -> str:
        """
        Classify the stage where the failure occurred.
        
        Args:
            errors: List of parsed errors
            
        Returns:
            Stage name (e.g., "build", "test", "deploy")
        """
        stage_indicators = {
            "build": ["build", "compile", "make", "cmake", "gradle", "maven"],
            "test": ["test", "pytest", "unittest", "jest", "mocha"],
            "deploy": ["deploy", "docker", "kubernetes", "helm", "terraform"],
            "install": ["install", "pip", "npm", "yarn", "apt", "brew"],
            "lint": ["lint", "flake8", "eslint", "pylint", "black"]
        }
        
        # Count errors by stage
        stage_counts = {stage: 0 for stage in stage_indicators}
        
        for error in errors:
            error_text = error.message.lower()
            for stage, indicators in stage_indicators.items():
                if any(indicator in error_text for indicator in indicators):
                    stage_counts[stage] += 1
        
        # Return the stage with the most errors
        if stage_counts:
            return max(stage_counts, key=stage_counts.get)
        
        return "unknown"
    
    def get_error_summary(self, errors: List[ParsedError]) -> Dict[str, Any]:
        """
        Generate a summary of errors.
        
        Args:
            errors: List of parsed errors
            
        Returns:
            Summary information about the errors
        """
        summary = {
            "total_errors": len(errors),
            "error_types": {},
            "severity_counts": {},
            "files_affected": set(),
            "commands_failed": set()
        }
        
        for error in errors:
            # Count error types
            error_type_name = error.error_type.value
            summary["error_types"][error_type_name] = summary["error_types"].get(error_type_name, 0) + 1
            
            # Count severity levels
            summary["severity_counts"][error.severity] = summary["severity_counts"].get(error.severity, 0) + 1
            
            # Collect affected files
            if error.file_path:
                summary["files_affected"].add(error.file_path)
            
            # Collect failed commands
            if error.command:
                summary["commands_failed"].add(error.command)
        
        # Convert sets to lists for JSON serialization
        summary["files_affected"] = list(summary["files_affected"])
        summary["commands_failed"] = list(summary["commands_failed"])
        
        return summary
