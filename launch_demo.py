"""
launch_demo.py - Quick Multi-Client Demo Launcher
Spawns 1 TCP Chat Server and 2 TCP Chat Client GUIs in separate processes.
"""

import subprocess
import sys
import time

def main():
    print("==================================================")
    print("  Starting TCP Multi-Client Chat Demo (3 Processes)")
    print("==================================================")
    
    # 1. Start Server process
    print("[1/3] Starting TCP Chat Server on 127.0.0.1:5000...")
    server_proc = subprocess.Popen([sys.executable, "run_server.py"])
    time.sleep(1.5)

    # 2. Start First Client GUI
    print("[2/3] Launching Client 1...")
    client1_proc = subprocess.Popen([sys.executable, "run_client.py"])
    time.sleep(0.8)

    # 3. Start Second Client GUI
    print("[3/3] Launching Client 2...")
    client2_proc = subprocess.Popen([sys.executable, "run_client.py"])

    print("\n✓ All processes launched!")
    print("Close individual windows or press Ctrl+C here to terminate all.\n")

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\nTerminating demo processes...")
        server_proc.terminate()
        client1_proc.terminate()
        client2_proc.terminate()

if __name__ == "__main__":
    main()
