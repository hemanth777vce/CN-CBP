"""
server.py - Multi-Threaded TCP Chat Server
Computer Networks Course Project: Transport Layer - Socket Programming

Core Concepts Demonstrated:
- TCP Socket Lifecycle: socket() -> bind() -> listen() -> accept() -> recv() / send() -> close()
- Concurrency Model: Dedicated worker thread per connected client (Multithreading)
- Thread Synchronization: threading.Lock() for thread-safe access to shared client registry
- Framing & Protocol: 4-byte Big-Endian length header + JSON payload to prevent packet gluing
"""

import socket
import threading
import sys
import time
from typing import Dict, Tuple
from protocol import (
    send_packet, recv_packet, get_current_timestamp,
    MSG_LOGIN, MSG_LOGIN_RESP, MSG_BROADCAST, MSG_PRIVATE,
    MSG_USER_JOIN, MSG_USER_LEAVE, MSG_USER_LIST, MSG_PING, MSG_PONG,
    MSG_SYSTEM, MSG_ERROR
)

# ANSI Color codes for rich terminal logging
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"

class ChatServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5000, max_clients: int = 20):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        
        # Sockets and Client Registry
        self.server_sock: socket.socket = None
        self.running: bool = False
        
        # Shared State (Protected by clients_lock)
        # username -> (socket, (ip, port), thread_name, join_time)
        self.clients: Dict[str, Tuple[socket.socket, Tuple[str, int], str, str]] = {}
        self.clients_lock = threading.Lock()
        
        # Server Statistics
        self.total_connections = 0
        self.total_messages = 0
        self.start_time = None

    def log(self, message: str, level: str = "INFO"):
        """Prints formatted, timestamped server log messages with ANSI styling."""
        timestamp = get_current_timestamp()
        badge_map = {
            "INFO": f"{Colors.BLUE}[INFO]{Colors.RESET}",
            "SUCCESS": f"{Colors.GREEN}[SUCCESS]{Colors.RESET}",
            "JOIN": f"{Colors.CYAN}[JOIN]{Colors.RESET}",
            "LEAVE": f"{Colors.YELLOW}[LEAVE]{Colors.RESET}",
            "ROUTE": f"{Colors.MAGENTA}[ROUTE]{Colors.RESET}",
            "ERROR": f"{Colors.RED}[ERROR]{Colors.RESET}",
            "THREAD": f"{Colors.GRAY}[THREAD]{Colors.RESET}",
        }
        badge = badge_map.get(level, f"[{level}]")
        print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} {badge} {message}")

    def start(self):
        """Initializes and runs the TCP listening socket and accept loop."""
        try:
            # 1. Create IPv4 TCP Stream Socket
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # 2. Set SO_REUSEADDR to immediately reclaim port upon restarts
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # 3. Bind socket to Network Interface & Port
            self.server_sock.bind((self.host, self.port))
            
            # 4. Enter Listening State with specified backlog
            self.server_sock.listen(self.max_clients)
            
            self.running = True
            self.start_time = time.time()

            self._print_banner()
            self.log(f"Server socket bound to {self.host}:{self.port} (Family: AF_INET, Type: SOCK_STREAM)", "SUCCESS")
            self.log(f"Listening with backlog queue of {self.max_clients} connections...", "INFO")
            self.log("Waiting for incoming client connections...\n" + "-" * 56, "INFO")

            # Main connection accept loop
            while self.running:
                try:
                    # 5. Blocking accept(): completes TCP 3-way handshake (SYN, SYN-ACK, ACK)
                    client_sock, client_addr = self.server_sock.accept()
                    self.total_connections += 1

                    # 6. Concurrency: Spawn a dedicated worker thread for each client
                    thread_name = f"ClientThread-{self.total_connections}"
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, client_addr, thread_name),
                        name=thread_name,
                        daemon=True
                    )
                    client_thread.start()

                except socket.error:
                    if not self.running:
                        break  # Socket closed during shutdown
                    self.log("Error accepting incoming socket connection", "ERROR")

        except Exception as e:
            self.log(f"Fatal error starting server: {e}", "ERROR")
        finally:
            self.stop()

    def _print_banner(self):
        """Displays startup header for viva and grading inspection."""
        banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================
                    TCP MULTI-CLIENT CHAT SERVER
              Computer Networks Lab - Socket Programming
================================================================{Colors.RESET}
  {Colors.BOLD}Protocol:{Colors.RESET}      TCP (Transmission Control Protocol)
  {Colors.BOLD}Socket Type:{Colors.RESET}   SOCK_STREAM (Reliable, Connection-Oriented)
  {Colors.BOLD}IP Address:{Colors.RESET}    {self.host}
  {Colors.BOLD}Port:{Colors.RESET}          {self.port}
  {Colors.BOLD}Concurrency:{Colors.RESET}   Thread-per-client Concurrency Model
================================================================
"""
        print(banner)

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int], thread_name: str):
        """
        Worker thread routine:
        - Authenticates / Registers client username
        - Dispatches messages (Broadcast, Private, Commands)
        - Cleans up and broadcasts disconnection on exit
        """
        username = None
        ip, port = client_addr
        self.log(f"Incoming TCP connection from {ip}:{port} on {thread_name}", "THREAD")

        try:
            # 1. Login Handshake Phase
            packet, _ = recv_packet(client_sock)
            if not packet or packet.get("type") != MSG_LOGIN:
                self.log(f"Unauthenticated connection from {ip}:{port} dropped.", "ERROR")
                client_sock.close()
                return

            candidate_name = packet.get("username", "").strip()
            
            # Validation: Username non-empty and not duplicated
            with self.clients_lock:
                if not candidate_name:
                    send_packet(client_sock, {
                        "type": MSG_LOGIN_RESP,
                        "success": False,
                        "message": "Username cannot be empty."
                    })
                    client_sock.close()
                    return
                
                if candidate_name in self.clients:
                    send_packet(client_sock, {
                        "type": MSG_LOGIN_RESP,
                        "success": False,
                        "message": f"Username '{candidate_name}' is already taken."
                    })
                    client_sock.close()
                    return

                # Register Client in Thread-Safe Registry
                username = candidate_name
                join_time = get_current_timestamp()
                self.clients[username] = (client_sock, client_addr, thread_name, join_time)
                active_users = list(self.clients.keys())

            # Acknowledge successful login
            send_packet(client_sock, {
                "type": MSG_LOGIN_RESP,
                "success": True,
                "message": f"Welcome, {username}! Connected to TCP Chat Server.",
                "users": active_users
            })

            self.log(f"Client authenticated: {Colors.BOLD}{username}{Colors.RESET} ({ip}:{port})", "JOIN")
            self.log(f"Active clients: {len(self.clients)} | Thread: {thread_name}", "INFO")

            # Notify all other clients of new user arrival
            self._broadcast({
                "type": MSG_USER_JOIN,
                "username": username,
                "users": active_users,
                "timestamp": join_time,
                "message": f"● {username} joined the chat"
            }, exclude_user=username)

            # 2. Main Message Processing Loop
            while self.running:
                packet, bytes_read = recv_packet(client_sock)
                if packet is None:
                    # Client closed TCP socket (FIN / RST packet received)
                    break

                self.total_messages += 1
                msg_type = packet.get("type")

                if msg_type == MSG_BROADCAST:
                    msg_text = packet.get("message", "")
                    ts = packet.get("timestamp", get_current_timestamp())
                    self.log(f"{Colors.BOLD}{username}{Colors.RESET} -> {Colors.CYAN}EVERYONE{Colors.RESET}: {msg_text}", "ROUTE")
                    self._broadcast({
                        "type": MSG_BROADCAST,
                        "sender": username,
                        "message": msg_text,
                        "timestamp": ts
                    })

                elif msg_type == MSG_PRIVATE:
                    receiver = packet.get("receiver", "")
                    msg_text = packet.get("message", "")
                    ts = packet.get("timestamp", get_current_timestamp())
                    self._route_private(username, receiver, msg_text, ts, client_sock)

                elif msg_type == MSG_PING:
                    # Echo ping back for round-trip latency calculation
                    send_packet(client_sock, {
                        "type": MSG_PONG,
                        "timestamp": packet.get("timestamp", time.time())
                    })

                elif msg_type == MSG_USER_LIST:
                    with self.clients_lock:
                        users = list(self.clients.keys())
                    send_packet(client_sock, {
                        "type": MSG_USER_LIST,
                        "users": users
                    })

        except (ConnectionError, socket.error) as e:
            self.log(f"Connection reset by client {username or ip}: {e}", "ERROR")
        except Exception as e:
            self.log(f"Unexpected error in thread for {username or ip}: {e}", "ERROR")
        finally:
            # 3. Clean Disconnection & State Cleanup
            if username:
                with self.clients_lock:
                    if username in self.clients:
                        del self.clients[username]
                    remaining_users = list(self.clients.keys())

                leave_time = get_current_timestamp()
                self.log(f"Client disconnected: {Colors.BOLD}{username}{Colors.RESET} ({ip}:{port})", "LEAVE")
                self.log(f"Active clients remaining: {len(remaining_users)}", "INFO")

                # Notify remaining users
                self._broadcast({
                    "type": MSG_USER_LEAVE,
                    "username": username,
                    "users": remaining_users,
                    "timestamp": leave_time,
                    "message": f"● {username} disconnected"
                })

            try:
                client_sock.close()
            except Exception:
                pass

    def _broadcast(self, packet: dict, exclude_user: str = None):
        """Thread-safe broadcast of a packet to all connected clients."""
        with self.clients_lock:
            targets = list(self.clients.items())

        disconnected_users = []
        for uname, (sock, _, _, _) in targets:
            if exclude_user and uname == exclude_user:
                continue
            try:
                send_packet(sock, packet)
            except Exception:
                disconnected_users.append(uname)

        # Cleanup any broken sockets found during broadcast
        if disconnected_users:
            with self.clients_lock:
                for uname in disconnected_users:
                    if uname in self.clients:
                        del self.clients[uname]

    def _route_private(self, sender: str, receiver: str, message: str, timestamp: str, sender_sock: socket.socket):
        """Routes a unicast message directly from sender to target receiver."""
        target_sock = None
        with self.clients_lock:
            if receiver in self.clients:
                target_sock = self.clients[receiver][0]

        if target_sock:
            self.log(f"{Colors.BOLD}{sender}{Colors.RESET} -> {Colors.YELLOW}PRIVATE [{receiver}]{Colors.RESET}: {message}", "ROUTE")
            # Send to receiver
            send_packet(target_sock, {
                "type": MSG_PRIVATE,
                "sender": sender,
                "receiver": receiver,
                "message": message,
                "timestamp": timestamp
            })
            # Echo confirmation to sender
            send_packet(sender_sock, {
                "type": MSG_PRIVATE,
                "sender": sender,
                "receiver": receiver,
                "message": message,
                "timestamp": timestamp,
                "is_echo": True
            })
        else:
            # Target user not found
            self.log(f"Failed private message from {sender}: User '{receiver}' not found", "ERROR")
            send_packet(sender_sock, {
                "type": MSG_ERROR,
                "message": f"User '{receiver}' is not online."
            })

    def stop(self):
        """Closes all client sockets and shuts down server socket gracefully."""
        self.running = False
        self.log("Shutting down TCP Chat Server...", "INFO")
        with self.clients_lock:
            for uname, (sock, _, _, _) in list(self.clients.items()):
                try:
                    send_packet(sock, {
                        "type": MSG_SYSTEM,
                        "message": "Server is shutting down.",
                        "timestamp": get_current_timestamp()
                    })
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        self.log("Server stopped successfully.", "SUCCESS")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Client TCP Chat Server")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Listening port (default: 5000)")
    args = parser.parse_args()

    server = ChatServer(host=args.host, port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Ctrl+C received]")
        server.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
