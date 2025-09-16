#!/usr/bin/env python3
"""
Tool system for iagent.

Provides tool abstraction and decorator for creating custom tools.
"""

import inspect
import logging
import re
import json
import math
import datetime as dt
from dateutil import parser as dtparser
from collections import Counter, defaultdict
import pandas as pd
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    name: str
    description: str
    inputs: Dict[str, Dict[str, Any]]
    output_type: str
    
    def __init__(self):
        self.validate_tool()
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        pass
    
    def validate_tool(self):
        """Validate tool configuration."""
        required_attrs = ['name', 'description', 'inputs', 'output_type']
        for attr in required_attrs:
            if not hasattr(self, attr):
                raise ValueError(f"Tool must have '{attr}' attribute")
        
        if not isinstance(self.name, str):
            raise ValueError("Tool name must be a string")
        
        if not isinstance(self.description, str):
            raise ValueError("Tool description must be a string")
        
        if not isinstance(self.inputs, dict):
            raise ValueError("Tool inputs must be a dictionary")
        
        if not isinstance(self.output_type, str):
            raise ValueError("Tool output_type must be a string")


class Tool(BaseTool):
    """Concrete tool implementation."""
    
    def __init__(self, func: Callable, name: str, description: str, 
                 inputs: Dict[str, Dict[str, Any]], output_type: str):
        self.func = func
        self.name = name
        self.description = description
        self.inputs = inputs
        self.output_type = output_type
        super().__init__()
    
    def execute(self, **kwargs) -> Any:
        """Execute the tool function."""
        try:
            return self.func(**kwargs)
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            raise


def tool(func_or_name=None, 
         description: Optional[str] = None,
         inputs: Optional[Dict[str, Dict[str, Any]]] = None,
         output_type: str = "string") -> Callable:
    """
    Decorator to convert a function into a tool.
    
    Args:
        func_or_name: Function to decorate or tool name
        description: Tool description (defaults to function docstring)
        inputs: Tool inputs schema (auto-generated from function signature)
        output_type: Tool output type
    
    Returns:
        Decorated function that can be used as a tool
    """
    # Handle case where decorator is called without arguments: @tool
    if func_or_name is not None and callable(func_or_name):
        return tool()(func_or_name)
    
    def decorator(func: Callable) -> Callable:
        # Get function metadata
        func_name = func_or_name if isinstance(func_or_name, str) else func.__name__
        func_description = description or func.__doc__ or f"Tool: {func_name}"
        
        # Auto-generate inputs schema if not provided
        if inputs is None:
            func_inputs = {}
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                param_default = param.default if param.default != inspect.Parameter.empty else None
                
                func_inputs[param_name] = {
                    "type": _get_type_name(param_type),
                    "description": f"Parameter: {param_name}",
                    "required": param_default is None
                }
        else:
            func_inputs = inputs
        
        # Create tool instance
        tool_instance = Tool(
            func=func,
            name=func_name,
            description=func_description,
            inputs=func_inputs,
            output_type=output_type
        )
        
        # Add tool instance to function
        func.tool = tool_instance
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper.tool = tool_instance
        return wrapper
    
    return decorator
    
    return decorator


def _get_type_name(type_obj) -> str:
    """Convert Python type to string representation."""
    if type_obj == str:
        return "string"
    elif type_obj == int:
        return "integer"
    elif type_obj == float:
        return "number"
    elif type_obj == bool:
        return "boolean"
    elif type_obj == list:
        return "array"
    elif type_obj == dict:
        return "object"
    else:
        return "string"  # Default to string


# Built-in tools
class WebSearchTool(BaseTool):
    """LLM-powered search tool for DevOps debugging and technical information."""
    
    name = "web_search"
    description = "Search for DevOps solutions, error fixes, and technical information using AI"
    inputs = {
        "query": {
            "type": "string",
            "description": "Search query for DevOps issues, error codes, or technical problems",
            "required": True
        },
        "model_type": {
            "type": "string", 
            "description": "LLM provider type (openai, litellm, ollama, huggingface, bedrock)",
            "required": False
        },
        "model_id": {
            "type": "string",
            "description": "Specific model ID to use (e.g., gpt-4, claude-3, llama2)",
            "required": False
        },
        "api_key": {
            "type": "string",
            "description": "API key for the LLM provider (if required)",
            "required": False
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
        self._model = None
    
    def execute(self, query: str, model_type: str = "openai", model_id: str = "gpt-3.5-turbo", api_key: str = None) -> str:
        """Execute LLM-powered search for DevOps debugging with direct answers."""
        try:
            # Initialize model if not already done
            if not self._model:
                self._model = self._create_model(model_type, model_id, api_key)
            
            # Create search prompt for DevOps context
            search_prompt = self._create_search_prompt(query)
            
            # Get LLM response
            from .models import ChatMessage
            messages = [
                ChatMessage(role="system", content=search_prompt["system"]),
                ChatMessage(role="user", content=search_prompt["user"])
            ]
            
            response = self._model.generate(messages)
            return response.content
                
        except Exception as e:
            logger.error(f"LLM search error: {e}")
            return f"Error performing AI search: {str(e)}. Please check your API key and model configuration."
    
    def _create_model(self, model_type: str, model_id: str, api_key: str = None):
        """Create a model instance based on type."""
        from .models import OpenAIModel, LiteLLMModel, OllamaModel, HuggingFaceModel, BedrockModel
        
        kwargs = {}
        if api_key:
            kwargs['api_key'] = api_key
        
        if model_type.lower() == "openai":
            return OpenAIModel(model_id=model_id, **kwargs)
        elif model_type.lower() == "litellm":
            return LiteLLMModel(model_id=model_id, **kwargs)
        elif model_type.lower() == "ollama":
            return OllamaModel(model_id=model_id, **kwargs)
        elif model_type.lower() == "huggingface":
            return HuggingFaceModel(model_id=model_id, **kwargs)
        elif model_type.lower() == "bedrock":
            return BedrockModel(model_id=model_id, **kwargs)
        else:
            # Default to OpenAI
            return OpenAIModel(model_id=model_id, **kwargs)
    
    def _create_search_prompt(self, query: str) -> dict:
        """Create a DevOps-focused search prompt for the LLM."""
        system_prompt = """You are a DevOps expert AI assistant specializing in troubleshooting and problem-solving. 
Your role is to provide concise, actionable solutions for DevOps issues.

Guidelines:
1. Provide direct, step-by-step solutions
2. Include specific commands and configurations when relevant
3. Focus on practical troubleshooting steps
4. Mention common causes and prevention tips
5. Keep responses concise but comprehensive
6. Use proper formatting with bullet points and code blocks
7. If you're unsure about something, say so rather than guessing

Areas of expertise:
- Kubernetes and container orchestration
- Docker and containerization
- CI/CD pipelines (GitHub Actions, Jenkins, GitLab CI)
- Infrastructure as Code (Terraform, Ansible, Pulumi)
- Cloud platforms (AWS, Azure, GCP)
- Monitoring and logging
- Security and compliance
- Performance optimization
- Web servers (NGINX, Apache)
- Databases (PostgreSQL, MySQL, MongoDB, Redis)
- Networking and load balancing"""

        user_prompt = f"""Please provide a comprehensive solution for this DevOps issue:

Query: "{query}"

Please include:
1. Root cause analysis
2. Step-by-step troubleshooting
3. Specific commands or configurations
4. Prevention tips
5. Additional resources if helpful

Format your response clearly with proper headings and bullet points."""

        return {
            "system": system_prompt,
            "user": user_prompt
        }
    




class FinalAnswerTool(BaseTool):
    """Simplified tool for providing final answers in DevOps operations."""
    
    name = "final_answer"
    description = "Provide the final answer or recommendation"
    inputs = {
        "answer": {
            "type": "string",
            "description": "The final answer or recommendation",
            "required": True
        }
    }
    output_type = "string"
    
    def execute(self, answer: str) -> str:
        """Return the final answer."""
        return answer


# --- Enhanced Log Analysis Tools ---

# Multiple log format regex patterns
NGINX_LOG_RE = re.compile(
    r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<method>\S+)\s+(?P<path>\S+)[^"]*"\s+(?P<status>\d{3})\s+(?P<size>\S+)'
)

SYSLOG_RE = re.compile(
    r'(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<service>\S+):\s+(?P<message>.*)'
)

SECURE_LOG_RE = re.compile(
    r'(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<service>\S+):\s+(?P<message>.*)'
)

# Security pattern detection
SECURITY_PATTERNS = {
    'failed_login': re.compile(r'Failed password|authentication failure|Invalid user', re.IGNORECASE),
    'brute_force': re.compile(r'Too many authentication failures|Connection closed by.*port.*preauth', re.IGNORECASE),
    'suspicious_ip': re.compile(r'Connection from.*refused|Invalid user.*from', re.IGNORECASE),
    'ddos_attempt': re.compile(r'Connection reset by peer|Too many connections', re.IGNORECASE),
    'sql_injection': re.compile(r'SELECT.*FROM|UNION.*SELECT|DROP.*TABLE', re.IGNORECASE),
    'xss_attempt': re.compile(r'<script|javascript:|onload=|onerror=', re.IGNORECASE),
    'path_traversal': re.compile(r'\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c', re.IGNORECASE)
}

def parse_nginx_ts(s: str) -> dt.datetime:
    """Parse NGINX timestamp format."""
    try:
        # NGINX time like 19/Aug/2025:08:21:03 +0000
        return dt.datetime.strptime(s.split(' ')[0], "%d/%b/%Y:%H:%M:%S")
    except ValueError:
        # Fallback to more flexible parsing
        return dtparser.parse(s.split(' ')[0])

def parse_syslog_ts(s: str) -> dt.datetime:
    """Parse syslog timestamp format."""
    try:
        # Syslog time like Aug 19 08:21:03
        current_year = dt.datetime.now().year
        return dt.datetime.strptime(f"{current_year} {s}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return dtparser.parse(s)

def detect_log_format(line: str) -> str:
    """Detect log format based on line content."""
    if NGINX_LOG_RE.search(line):
        return 'nginx'
    elif SYSLOG_RE.search(line):
        return 'syslog'
    elif SECURE_LOG_RE.search(line):
        return 'secure'
    else:
        return 'unknown'

def analyze_security_patterns(message: str) -> List[str]:
    """Analyze log message for security patterns."""
    detected_patterns = []
    for pattern_name, pattern_regex in SECURITY_PATTERNS.items():
        if pattern_regex.search(message):
            detected_patterns.append(pattern_name)
    return detected_patterns

class LoadFileHead(BaseTool):
    """Preview the first N lines of a text file to understand its format."""
    
    name = "load_file_head"
    description = (
        "Preview the first N lines of a text file to understand its format. "
        "Input: {'path': '...', 'n': 50}"
    )
    inputs = {
        "path": {"type": "string", "description": "Path to the file to read"},
        "n": {"type": "integer", "description": "Number of lines to read from the beginning of the file", "nullable": True}
    }
    output_type = "string"

    def execute(self, path: str, n: int = 50) -> str:
        lines = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= n: break
                lines.append(line.rstrip("\n"))
        return "\n".join(lines)

class ParseLogs(BaseTool):
    """Enhanced log analysis tool for NGINX, syslog, and security logs with DevOps focus."""
    
    name = "parse_logs"
    description = (
        "Parse web server logs (NGINX, syslog, secure) and compute metrics with security analysis. "
        "Input: {'path': '...', 'window_minutes': 15, 'log_type': 'auto'}. "
        "Returns comprehensive analysis including error rates, security threats, and DevOps recommendations."
    )
    inputs = {
        "path": {"type": "string", "description": "Path to the log file"},
        "window_minutes": {"type": "integer", "description": "Time window in minutes to analyze (default: 15)", "nullable": True},
        "log_type": {"type": "string", "description": "Log type: 'nginx', 'syslog', 'secure', or 'auto' (default: auto)", "nullable": True}
    }
    output_type = "string"

    def execute(self, path: str, window_minutes: int = 15, log_type: str = "auto") -> str:
        try:
            # Use current time for real-time analysis
            now = dt.datetime.now().replace(second=0, microsecond=0)
            window_start = now - dt.timedelta(minutes=window_minutes)
            
            # Parse logs based on detected or specified format
            rows = self._parse_log_file(path, log_type, window_start, now)
            
            if not rows:
                return json.dumps({
                    "status": "success",
                    "message": "No log entries found in the specified time window",
                    "window_start": window_start.isoformat(),
                    "window_end": now.isoformat(),
                    "recommendations": ["Check if the log file path is correct", "Verify the time window covers active periods"]
                }, indent=2)
            
            # Perform comprehensive analysis
            analysis = self._analyze_logs(rows, window_start, now, window_minutes)
            
            return json.dumps(analysis, indent=2)
            
        except FileNotFoundError:
            return json.dumps({
                "status": "error",
                "message": f"Log file not found: {path}",
                "recommendations": [
                    "Verify the file path is correct",
                    "Check file permissions",
                    "Ensure the log file exists and is readable"
                ]
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Error analyzing logs: {str(e)}",
                "recommendations": [
                    "Check log file format",
                    "Verify file encoding",
                    "Ensure sufficient disk space and memory"
                ]
            }, indent=2)

    def _parse_log_file(self, path: str, log_type: str, window_start: dt.datetime, window_end: dt.datetime) -> List[Dict]:
        """Parse log file and extract relevant entries."""
        rows = []
        detected_format = None
        
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Auto-detect format if not specified
                        if log_type == "auto":
                            detected_format = detect_log_format(line)
                        else:
                            detected_format = log_type
                        
                        # Parse based on detected format
                        parsed_entry = self._parse_log_line(line, detected_format)
                        if parsed_entry and window_start <= parsed_entry["timestamp"] <= window_end:
                            parsed_entry["line_number"] = line_num
                            rows.append(parsed_entry)
                            
                    except Exception as e:
                        # Log parsing errors but continue processing
                        logger.warning(f"Error parsing line {line_num}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            raise
            
        return rows

    def _parse_log_line(self, line: str, log_type: str) -> Optional[Dict]:
        """Parse a single log line based on format."""
        if log_type == "nginx":
            return self._parse_nginx_line(line)
        elif log_type in ["syslog", "secure"]:
            return self._parse_syslog_line(line)
        else:
            return None

    def _parse_nginx_line(self, line: str) -> Optional[Dict]:
        """Parse NGINX access log line."""
        m = NGINX_LOG_RE.search(line)
        if not m:
            return None
            
        try:
            ts = parse_nginx_ts(m.group("ts"))
            return {
                "timestamp": ts,
                "ip": m.group("ip"),
                "method": m.group("method"),
                "path": m.group("path"),
                "status": int(m.group("status")),
                "size": m.group("size"),
                "log_type": "nginx"
            }
        except Exception:
            return None

    def _parse_syslog_line(self, line: str) -> Optional[Dict]:
        """Parse syslog/secure log line."""
        m = SYSLOG_RE.search(line)
        if not m:
            return None
            
        try:
            ts = parse_syslog_ts(m.group("ts"))
            message = m.group("message")
            security_patterns = analyze_security_patterns(message)
            
            return {
                "timestamp": ts,
                "host": m.group("host"),
                "service": m.group("service"),
                "message": message,
                "security_patterns": security_patterns,
                "log_type": "syslog"
            }
        except Exception:
            return None

    def _analyze_logs(self, rows: List[Dict], window_start: dt.datetime, window_end: dt.datetime, window_minutes: int) -> Dict:
        """Perform comprehensive log analysis."""
        df = pd.DataFrame(rows)
        
        # Basic metrics
        total_entries = len(df)
        
        # Time-based analysis
        df["tmin"] = df["timestamp"].dt.floor('min')
        per_minute = df.groupby("tmin").size().reset_index(name="count")
        
        # Security analysis
        security_analysis = self._analyze_security(df)
        
        # Error analysis (for web logs)
        error_analysis = self._analyze_errors(df)
        
        # Performance analysis
        performance_analysis = self._analyze_performance(df, per_minute)
        
        # DevOps recommendations
        recommendations = self._generate_recommendations(security_analysis, error_analysis, performance_analysis)
        
        return {
            "status": "success",
            "analysis_window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "duration_minutes": window_minutes
            },
            "summary": {
                "total_entries": total_entries,
                "entries_per_minute": round(total_entries / max(window_minutes, 1), 2),
                "log_types": df["log_type"].value_counts().to_dict() if "log_type" in df.columns else {}
            },
            "security_analysis": security_analysis,
            "error_analysis": error_analysis,
            "performance_analysis": performance_analysis,
            "devops_recommendations": recommendations
        }

    def _analyze_security(self, df: pd.DataFrame) -> Dict:
        """Analyze security patterns in logs."""
        security_events = []
        threat_level = "low"
        
        if "security_patterns" in df.columns:
            # Count security patterns
            all_patterns = []
            for patterns in df["security_patterns"].dropna():
                all_patterns.extend(patterns)
            
            pattern_counts = Counter(all_patterns)
            
            # Determine threat level
            if pattern_counts.get("ddos_attempt", 0) > 10 or pattern_counts.get("brute_force", 0) > 5:
                threat_level = "high"
            elif pattern_counts.get("failed_login", 0) > 20 or pattern_counts.get("suspicious_ip", 0) > 5:
                threat_level = "medium"
            
            security_events = [{"pattern": pattern, "count": count} for pattern, count in pattern_counts.items()]
        
        return {
            "threat_level": threat_level,
            "security_events": security_events,
            "total_security_events": sum(event["count"] for event in security_events)
        }

    def _analyze_errors(self, df: pd.DataFrame) -> Dict:
        """Analyze error patterns in web logs."""
        if "status" not in df.columns:
            return {"message": "No HTTP status codes found in logs"}
        
        # Error categorization
        df["is_4xx"] = df["status"].between(400, 499)
        df["is_5xx"] = df["status"].between(500, 599)
        
        total_requests = len(df)
        error_4xx = int(df["is_4xx"].sum())
        error_5xx = int(df["is_5xx"].sum())
        
        # Top error paths and IPs
        top_error_paths = df[df["is_5xx"]].groupby("path").size().sort_values(ascending=False).head(5)
        top_error_ips = df[df["is_5xx"]].groupby("ip").size().sort_values(ascending=False).head(5)
        
        return {
            "total_requests": total_requests,
            "error_4xx": error_4xx,
            "error_5xx": error_5xx,
            "error_4xx_rate": round(100 * error_4xx / max(total_requests, 1), 2),
            "error_5xx_rate": round(100 * error_5xx / max(total_requests, 1), 2),
            "top_error_paths": [{"path": path, "count": int(count)} for path, count in top_error_paths.items()],
            "top_error_ips": [{"ip": ip, "count": int(count)} for ip, count in top_error_ips.items()]
        }

    def _analyze_performance(self, df: pd.DataFrame, per_minute: pd.DataFrame) -> Dict:
        """Analyze performance metrics."""
        # Calculate request rate trends
        if len(per_minute) > 1:
            request_trend = "stable"
            recent_avg = per_minute.tail(5)["count"].mean()
            overall_avg = per_minute["count"].mean()
            
            if recent_avg > overall_avg * 1.5:
                request_trend = "increasing"
            elif recent_avg < overall_avg * 0.5:
                request_trend = "decreasing"
        else:
            request_trend = "insufficient_data"
        
        return {
            "request_trend": request_trend,
            "peak_requests_per_minute": int(per_minute["count"].max()) if len(per_minute) > 0 else 0,
            "average_requests_per_minute": round(per_minute["count"].mean(), 2) if len(per_minute) > 0 else 0
        }

    def _generate_recommendations(self, security_analysis: Dict, error_analysis: Dict, performance_analysis: Dict) -> List[str]:
        """Generate DevOps recommendations using LLM based on analysis."""
        try:
            # Create analysis data for LLM recommendations
            analysis_data = {
                "totals": {
                    "requests": error_analysis.get("total_requests", 0),
                    "5xx": error_analysis.get("error_5xx", 0),
                    "4xx": error_analysis.get("error_4xx", 0),
                    "5xx_pct": error_analysis.get("error_5xx_rate", 0),
                    "4xx_pct": error_analysis.get("error_4xx_rate", 0)
                },
                "top_paths_5xx": [{"path": path["path"], "count": path["count"]} for path in error_analysis.get("top_error_paths", [])],
                "top_ips_5xx": [{"ip": ip["ip"], "count": ip["count"]} for ip in error_analysis.get("top_error_ips", [])],
                "security_threat_level": security_analysis.get("threat_level", "low"),
                "security_events": security_analysis.get("security_events", []),
                "total_security_events": security_analysis.get("total_security_events", 0),
                "request_trend": performance_analysis.get("request_trend", "stable"),
                "spike_minutes": []
            }
            
            # Use the GenerateRecommendations tool
            recommendation_tool = GenerateRecommendations()
            llm_recommendations = recommendation_tool.execute(json.dumps(analysis_data))
            
            # Parse the LLM response and extract recommendations
            if llm_recommendations:
                # Return the full LLM recommendations as a single formatted string
                # Split into sections for better display
                sections = llm_recommendations.split('\n\n')
                formatted_recommendations = []
                for section in sections:
                    if section.strip():
                        formatted_recommendations.append(section.strip())
                return formatted_recommendations
            
        except Exception as e:
            logger.warning(f"Failed to generate LLM recommendations: {e}")
        
        # Fallback to basic recommendations if LLM fails
        recommendations = []
        if error_analysis.get("error_5xx_rate", 0) > 5:
            recommendations.append("🔧 CRITICAL: High 5xx error rate detected - investigate server issues")
        if error_analysis.get("error_4xx_rate", 0) > 20:
            recommendations.append("📝 HIGH: High 4xx error rate detected - check routing and URLs")
        if security_analysis.get("threat_level") == "high":
            recommendations.append("🚨 HIGH PRIORITY: Security threats detected - implement immediate measures")
        if performance_analysis.get("request_trend") == "increasing":
            recommendations.append("📈 Performance: Request load increasing - monitor resources")
        
        if not recommendations:
            recommendations.append("✅ System appears to be operating normally")
        
        return recommendations

class GenerateRecommendations(BaseTool):
    """Generate AI-powered incident response recommendations based on log analysis."""
    
    name = "generate_recommendations"
    description = (
        "Generate structured incident response recommendations based on NGINX log analysis. "
        "Input: {'analysis_data': '...'}. "
        "Returns structured recommendations with priority levels and actionable steps."
    )
    inputs = {
        "analysis_data": {"type": "string", "description": "JSON string containing NGINX log analysis data"}
    }
    output_type = "string"

    def execute(self, analysis_data: str) -> str:
        try:
            data = json.loads(analysis_data)
            totals = data.get("totals", {})
            error_rate = totals.get('5xx_pct', 0)
            total_requests = totals.get('requests', 0)
            total_5xx = totals.get('5xx', 0)
            total_4xx = totals.get('4xx', 0)
            
            # Get top error paths and IPs
            top_paths_5xx = data.get('top_paths_5xx', [])
            top_ips_5xx = data.get('top_ips_5xx', [])
            spike_minutes = data.get('spike_minutes', [])
            
            # Get security events
            security_events = data.get('security_events', [])
            total_security_events = data.get('total_security_events', 0)
            security_threat_level = data.get('security_threat_level', 'low')
            
            # Determine primary failing endpoint
            top_path = top_paths_5xx[0]['path'] if top_paths_5xx else 'unknown'
            top_path_count = top_paths_5xx[0]['count'] if top_paths_5xx else 0
            
            # Determine affected systems based on path patterns
            affected_systems = []
            if '/api/products' in top_path or '/products' in top_path:
                affected_systems = ['Product catalog service', 'Inventory system', 'Price engine']
            elif '/api/checkout' in top_path or '/checkout' in top_path:
                affected_systems = ['Payment processor', 'Order management', 'Checkout system']
            elif '/api/auth' in top_path or '/login' in top_path:
                affected_systems = ['Authentication service', 'User session store', 'Identity provider']
            elif '/api/data' in top_path or '/data' in top_path:
                affected_systems = ['Data processing service', 'Analytics pipeline', 'Database layer']
            else:
                affected_systems = ['Backend service', 'Application layer', 'Core API']
            
            # Handle security events first
            if total_security_events > 0:
                # Get top security patterns
                top_security_patterns = sorted(security_events, key=lambda x: x.get('count', 0), reverse=True)
                primary_threat = top_security_patterns[0] if top_security_patterns else None
                
                if security_threat_level == 'high' or total_security_events > 10:
                    recommendations = f"""🚨 HIGH SECURITY THREAT DETECTED
                    
ROOT CAUSE HYPOTHESIS:
• Active security attack detected with {total_security_events} security events
• Primary threat: {primary_threat['pattern'] if primary_threat else 'unknown'} ({primary_threat['count'] if primary_threat else 0} occurrences)
• Potential brute force, DDoS, or intrusion attempt in progress
• System may be under active attack or reconnaissance

IMMEDIATE ACTIONS (0-5 minutes):
• Block suspicious IPs immediately using firewall rules
• Enable fail2ban or similar intrusion prevention
• Check system resource usage (CPU, memory, network)
• Review active connections and processes
• Alert security team and management

SHORT-TERM ACTIONS (5-30 minutes):
• Analyze attack patterns and source IPs
• Review authentication logs for compromised accounts
• Check for unauthorized file modifications
• Implement rate limiting and connection throttling
• Update security monitoring and alerting

LONG-TERM PREVENTIVE MEASURES:
• Strengthen authentication mechanisms (2FA, strong passwords)
• Implement network segmentation and access controls
• Regular security audits and penetration testing
• Update and patch all systems and applications
• Deploy advanced threat detection and response tools

PRIORITY: HIGH - Immediate security response required, {total_security_events} security events detected"""
                
                elif security_threat_level == 'medium' or total_security_events > 5:
                    recommendations = f"""⚠️ MEDIUM SECURITY CONCERN
                    
ROOT CAUSE HYPOTHESIS:
• Moderate security activity detected with {total_security_events} security events
• Primary concern: {primary_threat['pattern'] if primary_threat else 'unknown'} ({primary_threat['count'] if primary_threat else 0} occurrences)
• Possible reconnaissance or low-level attack attempts
• System monitoring and hardening recommended

IMMEDIATE ACTIONS (0-5 minutes):
• Monitor security events closely for escalation
• Review source IPs and attack patterns
• Check system logs for additional indicators
• Verify system integrity and file permissions

SHORT-TERM ACTIONS (5-30 minutes):
• Implement additional monitoring for detected patterns
• Review and strengthen access controls
• Consider implementing rate limiting
• Update security documentation and procedures

LONG-TERM PREVENTIVE MEASURES:
• Regular security awareness training
• Implement comprehensive logging and monitoring
• Regular vulnerability assessments
• Update incident response procedures
• Deploy security information and event management (SIEM)

PRIORITY: MEDIUM - Monitor closely, {total_security_events} security events detected"""
                
                else:
                    recommendations = f"""🟡 LOW SECURITY ACTIVITY
                    
ROOT CAUSE HYPOTHESIS:
• Minor security events detected with {total_security_events} security events
• Primary activity: {primary_threat['pattern'] if primary_threat else 'unknown'} ({primary_threat['count'] if primary_threat else 0} occurrences)
• Normal security monitoring activity or minor anomalies
• Continue routine security practices

IMMEDIATE ACTIONS (0-5 minutes):
• Continue normal security monitoring
• Document security events for trend analysis
• Verify security controls are functioning properly

SHORT-TERM ACTIONS (5-30 minutes):
• Review security event patterns for trends
• Update security monitoring thresholds if needed
• Ensure security tools are properly configured

LONG-TERM PREVENTIVE MEASURES:
• Maintain regular security updates and patches
• Continue security awareness training
• Regular security assessments and improvements
• Keep security documentation current

PRIORITY: LOW - Continue monitoring, {total_security_events} security events detected"""
                
                return recommendations
            
            elif error_rate > 40:
                recommendations = f"""🔴 CRITICAL INCIDENT DETECTED
            
ROOT CAUSE HYPOTHESIS:
• Primary failure in {top_path} endpoint causing {error_rate}% server errors
• {affected_systems[0]} likely crashed or overwhelmed ({top_path_count} errors)
• Cascading failures affecting {', '.join(affected_systems[1:2])}
• Database connection pool exhaustion or backend service failure

IMMEDIATE ACTIONS (0-5 minutes):
• Check health status of {affected_systems[0]} immediately
• Restart {affected_systems[0]} if unresponsive
• Enable circuit breaker for {top_path} endpoint to prevent further damage
• Scale up healthy instances of {affected_systems[0]} immediately
• Verify database connectivity and connection pool status
• Check load balancer configuration for {top_path}

SHORT-TERM ACTIONS (5-30 minutes):
• Review recent deployments for rollback candidates (last 2 hours)
• Check database performance metrics and slow query logs
• Monitor error recovery trends every 2 minutes
• Implement temporary rate limiting on {top_path} (50% traffic)
• Verify backup systems and failover mechanisms
• Check dependency services: {', '.join(affected_systems)}

LONG-TERM PREVENTIVE MEASURES:
• Add comprehensive health checks for {top_path} endpoint
• Implement auto-scaling based on error rates (trigger at 10%)
• Set up proactive alerting at 5% error threshold for {top_path}
• Add chaos engineering tests for {affected_systems[0]} resilience
• Implement circuit breaker pattern for all critical endpoints
• Add request timeout and retry logic improvements

PRIORITY: CRITICAL - Service degradation affecting {error_rate}% of all requests ({total_5xx}/{total_requests})"""
            elif error_rate > 20:
                recommendations = f"""🟡 HIGH PRIORITY INCIDENT

ROOT CAUSE HYPOTHESIS:
• Significant issues with {top_path} endpoint causing {error_rate}% server errors
• {affected_systems[0]} experiencing resource constraints or dependency failures
• Possible memory leaks, CPU exhaustion, or database connectivity issues
• Load balancer may be routing traffic to unhealthy instances

IMMEDIATE ACTIONS (0-5 minutes):
• Investigate {top_path} endpoint health status
• Check resource utilization (CPU >80%, memory >85%, disk I/O)
• Review recent deployments in the last 4 hours
• Verify {affected_systems[0]} service logs for error patterns
• Check database connection pool and query performance

SHORT-TERM ACTIONS (5-30 minutes):
• Implement temporary fixes and consider rollback if deployment-related
• Scale {affected_systems[0]} horizontally (add 2-3 instances)
• Add additional monitoring for {top_path} endpoint
• Implement temporary caching for {top_path} if applicable
• Review and optimize slow database queries
• Check upstream dependencies: {', '.join(affected_systems[1:])}

LONG-TERM PREVENTIVE MEASURES:
• Improve error handling and retry logic for {top_path}
• Add comprehensive monitoring and alerting (threshold: 15%)
• Implement graceful degradation for {affected_systems[0]}
• Add performance testing for {top_path} under load
• Implement request queuing and backpressure mechanisms

PRIORITY: HIGH - Significant service impact affecting {error_rate}% of requests ({total_5xx}/{total_requests})"""
            elif error_rate > 5:
                recommendations = f"""🟠 MODERATE INCIDENT

ROOT CAUSE HYPOTHESIS:
• Intermittent issues with {top_path} endpoint causing {error_rate}% server errors
• {affected_systems[0]} experiencing moderate resource constraints
• Possible timeout issues, rate limiting, or dependency slowness
• Gradual performance degradation or memory pressure

IMMEDIATE ACTIONS (0-5 minutes):
• Monitor {top_path} error trends every 5 minutes
• Check {affected_systems[0]} resource utilization trends
• Review recent configuration changes (last 24 hours)
• Verify {top_path} response times and latency metrics
• Check if errors correlate with traffic spikes

SHORT-TERM ACTIONS (5-30 minutes):
• Investigate root cause in {affected_systems[0]} logs
• Optimize error-prone {top_path} endpoint queries
• Add targeted monitoring for {top_path} performance
• Consider increasing timeout values if appropriate
• Review and tune {affected_systems[0]} configuration

LONG-TERM PREVENTIVE MEASURES:
• Improve error handling and timeout logic for {top_path}
• Add proactive monitoring with 8% error threshold
• Optimize {affected_systems[0]} performance and resource usage
• Implement better logging and observability
• Add automated alerting for gradual degradation

PRIORITY: MEDIUM - Monitor closely for escalation, {error_rate}% error rate ({total_5xx}/{total_requests})"""
            else:
                recommendations = f"""🟢 LOW PRIORITY MONITORING

ROOT CAUSE HYPOTHESIS:
• Minor issues with {top_path} endpoint causing {error_rate}% server errors
• Normal operational noise in {affected_systems[0]}
• Likely transient network issues or client-side problems
• Expected baseline error rate within acceptable limits

IMMEDIATE ACTIONS (0-5 minutes):
• Continue monitoring {top_path} baseline metrics
• Document error patterns for trend analysis
• Verify error rate stays below 3% threshold
• Check if errors are geographically distributed

SHORT-TERM ACTIONS (5-30 minutes):
• Review {top_path} error patterns for optimization opportunities
• Consider minor performance improvements to {affected_systems[0]}
• Update documentation with current error patterns
• Review client-side error handling and retry logic

LONG-TERM PREVENTIVE MEASURES:
• Optimize {top_path} endpoint for better reliability
• Improve monitoring coverage and baseline establishment
• Add client-side resilience patterns
• Periodic health checks and performance tuning

PRIORITY: LOW - Continue monitoring, {error_rate}% error rate ({total_5xx}/{total_requests}) within normal range"""
            
            return recommendations
            
        except Exception as e:
            return f"Error generating recommendations: {str(e)}"


# Import CI/CD debugger tools
try:
    from .cicd_debugger.tools import debug_cicd_failure, get_cicd_status, analyze_cicd_patterns
    CICD_TOOLS_AVAILABLE = True
except ImportError:
    CICD_TOOLS_AVAILABLE = False

# Tool registry
TOOL_REGISTRY = {
    "web_search": WebSearchTool(),
    "final_answer": FinalAnswerTool(),
    "load_file_head": LoadFileHead(),
    "parse_logs": ParseLogs(),
    "generate_recommendations": GenerateRecommendations(),
}

# Add system monitoring tool
try:
    from .system_monitor import SystemMonitorTool
    TOOL_REGISTRY["system_monitor"] = SystemMonitorTool()
except ImportError as e:
    print(f"Warning: Could not import SystemMonitorTool: {e}")
    pass

# Add CI/CD debugger tools if available
if CICD_TOOLS_AVAILABLE:
    TOOL_REGISTRY.update({
        "debug_cicd_failure": debug_cicd_failure,
        "get_cicd_status": get_cicd_status,
        "analyze_cicd_patterns": analyze_cicd_patterns,
    })


def get_tool(name: str) -> Optional[BaseTool]:
    """Get a tool by name."""
    return TOOL_REGISTRY.get(name)


def register_tool(tool: BaseTool):
    """Register a new tool."""
    TOOL_REGISTRY[tool.name] = tool


def list_tools() -> List[str]:
    """List all available tools."""
    return list(TOOL_REGISTRY.keys())
