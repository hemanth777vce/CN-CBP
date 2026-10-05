"""
client.py - TCP Socket Client Networking Engine
Computer Networks Course Project: Transport Layer - Socket Programming

Core Concepts:
- TCP Client Lifecycle: socket(AF_INET, SOCK_STREAM) -> connect() -> send() / recv() -> close()
- Concurrency: Background daemon listener thread prevents UI blocking on socket.recv()
- Telemetry: Real-time tracking of transmitted/received bytes, packet counts, ephemeral ports, and RTT
"""

import socket
import threading
import time
from typing import Callable, Optional, List
from protocol import (
    send_packet, recv_packet, get_current_timestamp,
    MSG_LOGIN, MSG_LOGIN_RESP, MSG_BROADCAST, MSG_PRIVATE,
    MSG_USER_JOIN, MSG_USER_LEAVE, MSG_USER_LIST, MSG_PING, MSG_PONG,
    MSG_SYSTEM, MSG_ERROR
)

class TCPChatClient:
    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.host: str = "127.0.0.1"
        self.port: int = 5000
        self.username: str = ""
        self.connected: bool = False
        
        # Local Socket Endpoints (Assigned by OS Kernel)
        self.local_ip: str = ""
        self.local_port: int = 0
        
        # Telemetry / Networking Stats for Viva Inspection
        self.packets_sent: int = 0
        self.packets_received: int = 0
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self.last_rtt_ms: float = 0.0
        self.connect_time: Optional[float] = None
        
        # Listener Thread
        self.recv_thread: Optional[threading.Thread] = None
        
        # Event Callbacks
        self.on_message_callback: Optional[Callable[[dict], None]] = None
        self.on_user_list_callback: Optional[Callable[[List[str]], None]] = None
        self.on_status_callback: Optional[Callable[[str, str], None]] = None # level, text
        self.on_network_activity_callback: Optional[Callable[[str, str], None]] = None # 'TX' or 'RX', desc
        self.on_disconnect_callback: Optional[Callable[[str], None]] = None
        self.on_rtt_update_callback: Optional[Callable[[float], None]] = None

    def connect(self, host: str, port: int, username: str) -> tuple[bool, str]:
        """
        Establishes TCP connection to the chat server and logs in.
        Returns (success: bool, message: str).
        """
        self.host = host
        self.port = port
        self.username = username.strip()

        if not self.username:
            return False, "Username cannot be empty."

        try:
            # 1. Create IPv4 TCP Socket (AF_INET = IPv4, SOCK_STREAM = TCP)
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)  # 5-second timeout for connection attempt

            # 2. Complete TCP 3-Way Handshake (SYN -> SYN-ACK -> ACK)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)  # Reset to blocking mode

            # Retrieve dynamic Ephemeral Port allocated by Operating System
            local_addr = self.sock.getsockname()
            self.local_ip = local_addr[0]
            self.local_port = local_addr[1]

            # 3. Transmit Login Handshake Packet
            login_packet = {
                "type": MSG_LOGIN,
                "username": self.username,
                "timestamp": get_current_timestamp()
            }
            sent_bytes = send_packet(self.sock, login_packet)
            self.packets_sent += 1
            self.bytes_sent += sent_bytes

            # 4. Await Server Login Response
            resp, resp_bytes = recv_packet(self.sock)
            if not resp:
                self.sock.close()
                return False, "Server closed the connection during authentication."

            self.packets_received += 1
            self.bytes_received += resp_bytes

            if resp.get("type") == MSG_LOGIN_RESP and resp.get("success"):
                self.connected = True
                self.connect_time = time.time()
                
                # 5. Start background receiver thread to prevent GUI freezing
                self.recv_thread = threading.Thread(
                    target=self._receive_loop,
                    name=f"TCPReceiver-{self.username}",
                    daemon=True
                )
                self.recv_thread.start()

                # Trigger initial online users list callback
                initial_users = resp.get("users", [])
                if self.on_user_list_callback:
                    self.on_user_list_callback(initial_users)

                return True, resp.get("message", "Connected successfully!")
            else:
                err_msg = resp.get("message", "Login rejected by server.")
                self.sock.close()
                return False, err_msg

        except ConnectionRefusedError:
            return False, f"Connection refused. Ensure server is running at {host}:{port}."
        except socket.timeout:
            return False, f"Connection timed out while reaching {host}:{port}."
        except Exception as e:
            return False, f"Network error: {str(e)}"

    def _receive_loop(self):
        """
        Background worker thread:
        Continuously executes blocking recv_packet() until socket closes.
        """
        while self.connected and self.sock:
            try:
                packet, num_bytes = recv_packet(self.sock)
                if packet is None:
                    # Clean EOF from server (FIN packet)
                    break

                self.packets_received += 1
                self.bytes_received += num_bytes
                
                # Signal network activity visualizer (RX)
                if self.on_network_activity_callback:
                    self.on_network_activity_callback("RX", f"Server ──► {self.username} ({num_bytes}B)")

                msg_type = packet.get("type")

                if msg_type in (MSG_BROADCAST, MSG_PRIVATE, MSG_SYSTEM, MSG_ERROR):
                    if self.on_message_callback:
                        self.on_message_callback(packet)

                elif msg_type == MSG_USER_JOIN:
                    if self.on_message_callback:
                        self.on_message_callback(packet)
                    if self.on_user_list_callback:
                        self.on_user_list_callback(packet.get("users", []))

                elif msg_type == MSG_USER_LEAVE:
                    if self.on_message_callback:
                        self.on_message_callback(packet)
                    if self.on_user_list_callback:
                        self.on_user_list_callback(packet.get("users", []))

                elif msg_type == MSG_USER_LIST:
                    if self.on_user_list_callback:
                        self.on_user_list_callback(packet.get("users", []))

                elif msg_type == MSG_PONG:
                    # Calculate round-trip time (RTT)
                    sent_ts = packet.get("timestamp", 0)
                    rtt = (time.time() - sent_ts) * 1000.0
                    self.last_rtt_ms = max(0.1, round(rtt, 2))
                    if self.on_rtt_update_callback:
                        self.on_rtt_update_callback(self.last_rtt_ms)

            except (ConnectionError, OSError):
                break
            except Exception as e:
                if self.connected:
                    print(f"[Client Recv Loop Error] {e}")
                break

        # Socket was closed or disconnected
        was_connected = self.connected
        self.connected = False
        if was_connected and self.on_disconnect_callback:
            self.on_disconnect_callback("Server closed the connection.")

    def send_broadcast(self, text: str) -> bool:
        """Sends broadcast message to all connected clients."""
        if not self.connected or not self.sock:
            return False
        try:
            packet = {
                "type": MSG_BROADCAST,
                "sender": self.username,
                "message": text,
                "timestamp": get_current_timestamp()
            }
            n_bytes = send_packet(self.sock, packet)
            self.packets_sent += 1
            self.bytes_sent += n_bytes
            if self.on_network_activity_callback:
                self.on_network_activity_callback("TX", f"{self.username} ──► Server ({n_bytes}B)")
            return True
        except Exception:
            self.disconnect()
            return False

    def send_private(self, receiver: str, text: str) -> bool:
        """Sends unicast message to a specific client via the server."""
        if not self.connected or not self.sock:
            return False
        try:
            packet = {
                "type": MSG_PRIVATE,
                "sender": self.username,
                "receiver": receiver,
                "message": text,
                "timestamp": get_current_timestamp()
            }
            n_bytes = send_packet(self.sock, packet)
            self.packets_sent += 1
            self.bytes_sent += n_bytes
            if self.on_network_activity_callback:
                self.on_network_activity_callback("TX", f"{self.username} ──► Server [to {receiver}] ({n_bytes}B)")
            return True
        except Exception:
            self.disconnect()
            return False

    def send_ping(self):
        """Sends PING packet to calculate TCP round-trip latency."""
        if not self.connected or not self.sock:
            return
        try:
            packet = {
                "type": MSG_PING,
                "timestamp": time.time()
            }
            n_bytes = send_packet(self.sock, packet)
            self.packets_sent += 1
            self.bytes_sent += n_bytes
            if self.on_network_activity_callback:
                self.on_network_activity_callback("TX", f"PING ──► Server ({n_bytes}B)")
        except Exception:
            pass

    def request_users(self):
        """Requests updated online user list from server."""
        if not self.connected or not self.sock:
            return
        try:
            packet = {"type": MSG_USER_LIST}
            n_bytes = send_packet(self.sock, packet)
            self.packets_sent += 1
            self.bytes_sent += n_bytes
        except Exception:
            pass

    def disconnect(self):
        """Cleanly closes the TCP socket and terminates listener thread."""
        self.connected = False
        sock_to_close = self.sock
        self.sock = None
        if sock_to_close:
            try:
                sock_to_close.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock_to_close.close()
            except Exception:
                pass
