#!/usr/bin/env python3
"""
E-Ink Service Status Script

This script checks the status of the e-ink display service.
It's designed to be called via poetry scripts.

Usage:
  poetry run eink-service-status
"""

import os
import sys
import subprocess
import socket
import json
import time

def check_service_process():
    """Check if the e-ink service process is running"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'run_eink_service.py|eink_service.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return True, pids
        return False, []
    except Exception as e:
        print(f"Error checking service process: {e}")
        return False, []

def check_socket(socket_path='/tmp/eink_service.sock'):
    """Check if the e-ink service socket exists and is responsive"""
    if not os.path.exists(socket_path):
        return False, "Socket file does not exist"
    
    try:
        # Try to connect to the socket and send a status request
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(socket_path)
        
        # Send a status request
        command = {"command": "status"}
        sock.sendall(json.dumps(command).encode('utf-8'))
        
        # Receive response
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
        
        # Parse the response
        if response_data:
            response = json.loads(response_data.decode('utf-8'))
            return True, response
        return True, "Socket exists but no response data"
    except Exception as e:
        return False, f"Socket error: {e}"
    finally:
        try:
            sock.close()
        except:
            pass

def check_service_status():
    """Check the status of the e-ink service and display detailed information"""
    print("Checking E-Ink service status...")
    
    # Check if process is running
    process_running, pids = check_service_process()
    if process_running:
        print(f"✅ Service process is running")
        for pid in pids:
            print(f"   - PID: {pid}")
        
        # Get more details with ps
        try:
            ps_result = subprocess.run(
                ['ps', '-p', ','.join(pids), '-o', 'pid,ppid,cmd,%cpu,%mem,etime'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if ps_result.returncode == 0:
                print("\nProcess details:")
                print(ps_result.stdout)
        except Exception:
            pass
    else:
        print("❌ Service process is not running")
        return False
    
    # Check socket
    socket_ok, socket_info = check_socket()
    if socket_ok:
        if isinstance(socket_info, dict):
            print(f"✅ Socket is responsive")
            print("\nService info from socket:")
            for key, value in socket_info.items():
                print(f"   - {key}: {value}")
        else:
            print(f"✅ Socket exists but may not be fully functional")
            print(f"   Info: {socket_info}")
    else:
        print(f"❌ Socket issue: {socket_info}")
        return False
    
    # Check socket file permissions
    try:
        socket_path = '/tmp/eink_service.sock'
        if os.path.exists(socket_path):
            import stat
            socket_stat = os.stat(socket_path)
            mode = stat.filemode(socket_stat.st_mode)
            print(f"\nSocket file permissions: {mode}")
            print(f"Owner: {socket_stat.st_uid}, Group: {socket_stat.st_gid}")
    except Exception as e:
        print(f"Error checking socket permissions: {e}")
    
    # All checks passed
    print("\n✅ E-Ink service is running properly")
    return True

def main():
    """Main function"""
    status_ok = check_service_status()
    return 0 if status_ok else 1

if __name__ == "__main__":
    sys.exit(main()) 