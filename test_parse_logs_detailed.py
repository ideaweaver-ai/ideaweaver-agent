#!/usr/bin/env python3
"""
Detailed test for parse_logs tool - shows full LLM recommendations and analysis
"""

import sys
import os
import json
sys.path.insert(0, 'src')

from iagent.tools import get_tool

def main():
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY first: export OPENAI_API_KEY='your-key'")
        return
    
    # Get tool
    parse_logs = get_tool('parse_logs')
    
    print("Testing parse_logs with FULL OUTPUT...")
    print("=" * 60)
    
    # Test NGINX logs
    print("\nANALYZING NGINX LOGS...")
    print("-" * 40)
    
    result = parse_logs.execute("nginx_access.log", window_minutes=600, log_type="nginx")
    
    # Parse and display FULL analysis
    data = json.loads(result)
    
    print(f"SUMMARY:")
    print(f"  • Total entries: {data['summary']['total_entries']}")
    print(f"  • Analysis window: {data['analysis_window']['duration_minutes']} minutes")
    print(f"  • Entries per minute: {data['summary']['entries_per_minute']}")
    
    print(f"\nERROR ANALYSIS:")
    if 'error_4xx_rate' in data['error_analysis']:
        print(f"  • 4xx Client Error Rate: {data['error_analysis']['error_4xx_rate']}%")
        print(f"  • 5xx Server Error Rate: {data['error_analysis']['error_5xx_rate']}%")
        print(f"  • Total 4xx errors: {data['error_analysis']['error_4xx']}")
        print(f"  • Total 5xx errors: {data['error_analysis']['error_5xx']}")
    else:
        print(f"  • Message: {data['error_analysis'].get('message', 'No error data')}")
    
    print(f"\nSECURITY ANALYSIS:")
    print(f"  • Threat level: {data['security_analysis']['threat_level']}")
    print(f"  • Total security events: {data['security_analysis']['total_security_events']}")
    
    if data['security_analysis']['security_events']:
        print(f"  • Security events detected:")
        for event in data['security_analysis']['security_events']:
            print(f"    - {event['pattern']}: {event['count']} occurrences")
    
    print(f"\nPERFORMANCE ANALYSIS:")
    print(f"  • Request trend: {data['performance_analysis']['request_trend']}")
    print(f"  • Peak requests/min: {data['performance_analysis']['peak_requests_per_minute']}")
    print(f"  • Average requests/min: {data['performance_analysis']['average_requests_per_minute']}")
    
    print(f"\nLLM-GENERATED RECOMMENDATIONS:")
    print("=" * 60)
    
    for i, rec in enumerate(data['devops_recommendations'], 1):
        print(f"\nRECOMMENDATION {i}:")
        print("-" * 30)
        print(rec)
        print()
    
    print("Full analysis completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()