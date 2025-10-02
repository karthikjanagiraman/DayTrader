#!/usr/bin/env python3
"""
Simple socket test to verify TWS port
"""

import socket
import sys

def test_port():
    """Test if we can connect to TWS port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 7497))
        sock.close()

        if result == 0:
            print("✓ Port 7497 is reachable")
            return True
        else:
            print("✗ Port 7497 is not reachable")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    test_port()