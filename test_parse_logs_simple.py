#!/usr/bin/env python3
"""
Ultra-minimal test for parse_logs tool
"""

import sys
import os
sys.path.insert(0, 'src')

from iagent.tools import get_tool

def main():
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY first: export OPENAI_API_KEY='your-key'")
        return
    
    # Get tool
    parse_logs = get_tool('parse_logs')
    
    print("Testing parse_logs...")
    
    # Test NGINX logs
    result = parse_logs.execute("nginx_access.log", window_minutes=600, log_type="nginx")
    
    # Show key info
    import json
    data = json.loads(result)
    
    print(f"Entries: {data['summary']['total_entries']}")
    print(f"Security: {data['security_analysis']['threat_level']}")
    print(f"Recommendations: {len(data['devops_recommendations'])} sections")
    
    print("Test completed!")

if __name__ == "__main__":
    main()