#!/usr/bin/env python3
"""
System monitoring tools for iagent.
"""

import subprocess
import platform
import sys
from typing import Dict, Any, List
from .tools import BaseTool


class SystemMonitorTool(BaseTool):
    """Tool for monitoring system performance using actual system commands."""
    
    name = "system_monitor"
    description = "Monitor system performance including CPU, memory, disk, and processes using actual system commands"
    inputs = {
        "command": {
            "type": "string",
            "description": "System monitoring command: 'cpu', 'memory', 'disk', 'processes', or 'all'"
        }
    }
    output_type = "string"
    
    def execute(self, command: str = "all") -> str:
        """Execute system monitoring commands."""
        try:
            if command == "all":
                return self._get_all_stats()
            elif command == "cpu":
                return self._get_cpu_stats()
            elif command == "memory":
                return self._get_memory_stats()
            elif command == "disk":
                return self._get_disk_stats()
            elif command == "processes":
                return self._get_process_stats()
            else:
                return f"Unknown command: {command}. Available: cpu, memory, disk, processes, all"
        except Exception as e:
            return f"Error monitoring system: {str(e)}"
    
    def _get_all_stats(self) -> str:
        """Get all system statistics with LLM recommendations."""
        result = "🖥️ SYSTEM PERFORMANCE MONITOR\n"
        result += "=" * 50 + "\n\n"
        
        cpu_stats = self._get_cpu_stats()
        memory_stats = self._get_memory_stats()
        disk_stats = self._get_disk_stats()
        process_stats = self._get_process_stats()
        
        result += cpu_stats + "\n\n"
        result += memory_stats + "\n\n"
        result += disk_stats + "\n\n"
        result += process_stats + "\n\n"
        
        # Add LLM recommendations
        recommendations = self._generate_recommendations(cpu_stats, memory_stats, disk_stats, process_stats)
        result += recommendations
        
        return result
    
    def _generate_recommendations(self, cpu_stats: str, memory_stats: str, disk_stats: str, process_stats: str) -> str:
        """Generate AI-powered recommendations based on system stats."""
        try:
            from .tools import get_tool
            
            # Prepare analysis data for LLM
            analysis_data = {
                "system_stats": {
                    "cpu": cpu_stats,
                    "memory": memory_stats,
                    "disk": disk_stats,
                    "processes": process_stats
                },
                "timestamp": "2025-09-16T11:22:51Z",
                "platform": "macOS"
            }
            
            # Get the recommendations tool
            recommendations_tool = get_tool('generate_recommendations')
            if recommendations_tool:
                import json
                recommendations = recommendations_tool.execute(json.dumps(analysis_data))
                return f"🤖 AI-POWERED RECOMMENDATIONS:\n{recommendations}\n"
            else:
                return "🤖 AI recommendations not available\n"
        except Exception as e:
            return f"🤖 AI recommendations error: {str(e)}\n"
    
    def _get_cpu_stats(self) -> str:
        """Get CPU statistics using system commands."""
        try:
            result = "📊 CPU Usage:\n"
            result += "-" * 20 + "\n"
            
            if platform.system() == "Darwin":  # macOS
                cmd_result = subprocess.run(['top', '-l', '1'], capture_output=True, text=True, timeout=5)
                if cmd_result.returncode == 0:
                    lines = cmd_result.stdout.split('\n')
                    for line in lines:
                        if 'CPU usage:' in line or 'Load Avg:' in line:
                            result += line.strip() + "\n"
                else:
                    result += "Error getting CPU stats\n"
            else:  # Linux
                # Try multiple Linux CPU monitoring approaches
                try:
                    # First try top command
                    cmd_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True, timeout=5)
                    if cmd_result.returncode == 0:
                        lines = cmd_result.stdout.split('\n')
                        for line in lines[:10]:  # First 10 lines usually contain CPU info
                            if '%Cpu' in line or 'load average' in line:
                                result += line.strip() + "\n"
                    else:
                        # Fallback to /proc/loadavg and /proc/stat
                        try:
                            with open('/proc/loadavg', 'r') as f:
                                loadavg = f.read().strip()
                                result += f"Load Average: {loadavg}\n"
                        except:
                            result += "Error getting CPU stats\n"
                except subprocess.TimeoutExpired:
                    result += "CPU stats: Command timed out\n"
                except Exception as e:
                    result += f"Error getting CPU stats: {str(e)}\n"
            
            return result
        except subprocess.TimeoutExpired:
            return "CPU stats: Command timed out\n"
        except Exception as e:
            return f"Error getting CPU stats: {str(e)}\n"
    
    def _get_memory_stats(self) -> str:
        """Get memory statistics using system commands."""
        try:
            result = "🧠 Memory Usage:\n"
            result += "-" * 20 + "\n"
            
            if platform.system() == "Darwin":  # macOS
                cmd_result = subprocess.run(['vm_stat'], capture_output=True, text=True)
                if cmd_result.returncode == 0:
                    lines = cmd_result.stdout.split('\n')
                    for line in lines[:10]:  # First 10 lines contain key memory info
                        if 'Pages free:' in line or 'Pages active:' in line or 'PhysMem:' in line:
                            result += line.strip() + "\n"
                else:
                    result += "Error getting memory stats\n"
            else:  # Linux
                try:
                    # Try free -h first (human readable), fallback to free -m (megabytes)
                    cmd_result = subprocess.run(['free', '-h'], capture_output=True, text=True)
                    if cmd_result.returncode == 0:
                        result += cmd_result.stdout
                    else:
                        # Fallback to free -m (more compatible)
                        cmd_result = subprocess.run(['free', '-m'], capture_output=True, text=True)
                        if cmd_result.returncode == 0:
                            result += cmd_result.stdout
                        else:
                            # Final fallback to /proc/meminfo
                            try:
                                with open('/proc/meminfo', 'r') as f:
                                    meminfo = f.read()
                                    lines = meminfo.split('\n')
                                    for line in lines[:10]:  # First 10 lines contain key memory info
                                        if any(key in line for key in ['MemTotal:', 'MemFree:', 'MemAvailable:', 'Buffers:', 'Cached:']):
                                            result += line.strip() + "\n"
                            except:
                                result += "Error getting memory stats\n"
                except Exception as e:
                    result += f"Error getting memory stats: {str(e)}\n"
            
            return result
        except Exception as e:
            return f"Error getting memory stats: {str(e)}\n"
    
    def _get_disk_stats(self) -> str:
        """Get disk statistics using system commands."""
        try:
            result = "💾 Disk Usage:\n"
            result += "-" * 20 + "\n"
            
            cmd_result = subprocess.run(['df', '-h'], capture_output=True, text=True)
            if cmd_result.returncode == 0:
                lines = cmd_result.stdout.split('\n')
                # Show first few lines (header + main filesystems)
                for line in lines[:8]:
                    result += line + "\n"
            else:
                result += "Error getting disk stats\n"
            
            return result
        except Exception as e:
            return f"Error getting disk stats: {str(e)}\n"
    
    def _get_process_stats(self) -> str:
        """Get top processes using system commands."""
        try:
            result = "⚡ Top Processes:\n"
            result += "-" * 20 + "\n"
            
            cmd_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            if cmd_result.returncode == 0:
                lines = cmd_result.stdout.split('\n')
                # Show header + top 5 processes
                for line in lines[:6]:
                    result += line + "\n"
            else:
                result += "Error getting process stats\n"
            
            return result
        except Exception as e:
            return f"Error getting process stats: {str(e)}\n"
