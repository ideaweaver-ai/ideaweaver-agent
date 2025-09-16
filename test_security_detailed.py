#!/usr/bin/env python3
"""
Detailed security log test - shows full security analysis and LLM recommendations
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
    
    print("Testing SECURITY LOG ANALYSIS with FULL OUTPUT...")
    print("=" * 60)
    
    # Create a security log with various threats
    security_log_content = """Sep 16 09:30:15 server1 sshd[1234]: Failed password for root from 192.168.1.100 port 22 ssh2
Sep 16 09:30:20 server1 sshd[1235]: Failed password for admin from 192.168.1.100 port 22 ssh2
Sep 16 09:30:25 server1 sshd[1236]: Failed password for user from 192.168.1.100 port 22 ssh2
Sep 16 09:30:30 server1 sshd[1237]: Connection closed by 192.168.1.100 port 22 [preauth]
Sep 16 09:30:35 server1 sshd[1238]: Failed password for root from 192.168.1.100 port 22 ssh2
Sep 16 09:30:40 server1 sshd[1239]: Failed password for admin from 192.168.1.100 port 22 ssh2
Sep 16 09:30:45 server1 sshd[1240]: Failed password for user from 192.168.1.100 port 22 ssh2
Sep 16 09:30:50 server1 sshd[1241]: Connection closed by 192.168.1.100 port 22 [preauth]
Sep 16 09:30:55 server1 sshd[1242]: Failed password for root from 192.168.1.100 port 22 ssh2
Sep 16 09:31:00 server1 sshd[1243]: Failed password for admin from 192.168.1.100 port 22 ssh2
Sep 16 09:31:05 server1 sshd[1244]: Failed password for user from 192.168.1.100 port 22 ssh2
Sep 16 09:31:10 server1 sshd[1245]: Connection closed by 192.168.1.100 port 22 [preauth]
Sep 16 09:31:15 server1 sshd[1246]: Failed password for root from 192.168.1.100 port 22 ssh2
Sep 16 09:31:20 server1 sshd[1247]: Failed password for admin from 192.168.1.100 port 22 ssh2
Sep 16 09:31:25 server1 sshd[1248]: Failed password for user from 192.168.1.100 port 22 ssh2
Sep 16 09:31:30 server1 sshd[1249]: Connection closed by 192.168.1.100 port 22 [preauth]
Sep 16 09:31:35 server1 sshd[1250]: Failed password for root from 192.168.1.100 port 22 ssh2
Sep 16 09:31:40 server1 sshd[1251]: Failed password for admin from 192.168.1.100 port 22 ssh2
Sep 16 09:31:45 server1 sshd[1252]: Failed password for user from 192.168.1.100 port 22 ssh2
Sep 16 09:31:50 server1 sshd[1253]: Connection closed by 192.168.1.100 port 22 [preauth]
Sep 16 09:32:00 server1 apache2[2000]: [error] [client 198.51.100.10] File does not exist: /var/www/html/admin.php
Sep 16 09:32:05 server1 apache2[2001]: [error] [client 198.51.100.10] File does not exist: /var/www/html/config.php
Sep 16 09:32:10 server1 apache2[2002]: [error] [client 198.51.100.10] File does not exist: /var/www/html/backup.sql
Sep 16 09:32:15 server1 apache2[2003]: [error] [client 198.51.100.10] File does not exist: /var/www/html/wp-admin.php
Sep 16 09:32:20 server1 apache2[2004]: [error] [client 198.51.100.10] File does not exist: /var/www/html/login.php
"""
    
    # Write test security log
    with open("test_security_detailed.log", "w") as f:
        f.write(security_log_content)
    
    try:
        print("\nANALYZING SECURITY LOGS...")
        print("-" * 40)
        
        result = parse_logs.execute("test_security_detailed.log", window_minutes=1440, log_type="syslog")
        
        # Parse and display FULL analysis
        data = json.loads(result)
        
        print(f"SUMMARY:")
        print(f"  • Total entries: {data['summary']['total_entries']}")
        print(f"  • Analysis window: {data['analysis_window']['duration_minutes']} minutes")
        print(f"  • Log types: {data['summary']['log_types']}")
        
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
        
        print(f"\nLLM-GENERATED SECURITY RECOMMENDATIONS:")
        print("=" * 60)
        
        for i, rec in enumerate(data['devops_recommendations'], 1):
            print(f"\nSECURITY RECOMMENDATION {i}:")
            print("-" * 40)
            print(rec)
            print()
        
        print("Security analysis completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Security test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test file
        if os.path.exists("test_security_detailed.log"):
            os.remove("test_security_detailed.log")
            print("Cleaned up test file")

if __name__ == "__main__":
    main()