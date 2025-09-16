#!/usr/bin/env python3
"""
Show RAW JSON output from parse_logs tool
"""

import sys
import os
import json
sys.path.insert(0, 'src')

from iagent.tools import get_tool

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY first: export OPENAI_API_KEY='your-key'")
        return
    
    parse_logs = get_tool('parse_logs')
    
    print("RAW OUTPUT FROM parse_logs TOOL:")
    print("=" * 50)
    
    # Test NGINX logs
    result = parse_logs.execute("nginx_access.log", window_minutes=600, log_type="nginx")
    
    print("RAW JSON OUTPUT:")
    print("-" * 30)
    print(result)
    
    print("\n" + "=" * 50)
    print("PARSED RECOMMENDATIONS:")
    print("-" * 30)
    
    # Parse and show just the recommendations
    data = json.loads(result)
    for i, rec in enumerate(data['devops_recommendations'], 1):
        print(f"\n--- RECOMMENDATION {i} ---")
        print(rec)
        print()

if __name__ == "__main__":
    main()