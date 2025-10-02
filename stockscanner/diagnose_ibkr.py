#!/usr/bin/env python3
"""
Diagnose IBKR connection issues
"""

import socket
import time
import sys
from datetime import datetime

def check_port(port):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def diagnose():
    """Run diagnostic checks"""
    print("\n" + "="*60)
    print("IBKR CONNECTION DIAGNOSTICS")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")

    # Check common IBKR ports
    ports = {
        7497: "TWS Paper Trading",
        7496: "TWS Live Trading",
        4001: "IB Gateway Paper",
        4002: "IB Gateway Live",
        5000: "Client Portal"
    }

    open_ports = []
    for port, desc in ports.items():
        status = "✓ OPEN" if check_port(port) else "✗ CLOSED"
        print(f"Port {port:4} ({desc:20}): {status}")
        if check_port(port):
            open_ports.append((port, desc))

    print("\n" + "-"*60)

    if not open_ports:
        print("\n❌ NO IBKR PORTS ARE OPEN")
        print("\nPossible solutions:")
        print("1. Start TWS or IB Gateway")
        print("2. Log in to TWS/Gateway")
        print("3. Enable API connections in TWS:")
        print("   - File -> Global Configuration -> API -> Settings")
        print("   - Check 'Enable ActiveX and Socket Clients'")
        print("   - Check 'Socket port' is 7497 (paper) or 7496 (live)")
        print("4. Add '127.0.0.1' to trusted IPs")
        return False

    print(f"\n✅ Found {len(open_ports)} open port(s):")
    for port, desc in open_ports:
        print(f"   - Port {port}: {desc}")

    # Try raw socket connection to first open port
    if open_ports:
        test_port = open_ports[0][0]
        print(f"\nTesting raw socket to port {test_port}...")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(('127.0.0.1', test_port))

            # Send API version handshake
            sock.send(b'API\0')
            time.sleep(0.1)

            # Try to receive response
            sock.settimeout(1)
            try:
                data = sock.recv(1024)
                if data:
                    print(f"✓ Received response: {len(data)} bytes")
                    print(f"  First 50 bytes: {data[:50]}")
                else:
                    print("✗ No response from API")
            except socket.timeout:
                print("✗ API response timeout")

            sock.close()

        except Exception as e:
            print(f"✗ Socket error: {e}")

    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)

    if open_ports:
        port, desc = open_ports[0]
        print(f"\n1. TWS/Gateway is running on port {port}")
        print("2. But API connection is not responding properly")
        print("\nCheck TWS API settings:")
        print("   - File -> Global Configuration -> API -> Settings")
        print("   - Ensure 'Enable ActiveX and Socket Clients' is checked")
        print("   - Add '127.0.0.1' to 'Trusted IP Addresses'")
        print("   - Uncheck 'Read-Only API' if checked")
        print("\n3. Try restarting TWS/Gateway")
        print("4. Check TWS log for API errors")
    else:
        print("\nPlease start TWS or IB Gateway and log in")

    return bool(open_ports)

if __name__ == "__main__":
    success = diagnose()
    sys.exit(0 if success else 1)