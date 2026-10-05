"""
run_server.py - Server Entry Point
Usage:
  python run_server.py          # Starts the CLI TCP Server with rich logs
  python run_server.py --gui    # Starts the Graphical Server Dashboard
  python run_server.py --port 5000 --host 127.0.0.1
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Multi-Client TCP Chat Server Launcher")
    parser.add_argument("--gui", action="store_true", help="Launch the Modern Server Dashboard GUI")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Listening port (default: 5000)")
    args = parser.parse_args()

    if args.gui:
        import server_gui
        server_gui.main()
    else:
        from server import ChatServer
        server = ChatServer(host=args.host, port=args.port)
        try:
            server.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.stop()
            sys.exit(0)

if __name__ == "__main__":
    main()
