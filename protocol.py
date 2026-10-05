"""
protocol.py - Computer Networks Course Project
TCP Socket Protocol Specification & Packet Framing

Key Networking Concepts:
- TCP is a Stream Protocol: TCP treats data as a continuous stream of bytes without 
  inherent message boundaries (unlike UDP which is message/datagram-oriented).
- Packet Framing: To prevent TCP packet sticking (gluing) and packet fragmentation,
  we implement a 4-byte Length-Prefixed Framing mechanism:
  
  [ 4 Bytes: Payload Length (Big-Endian / Network Byte Order) ] + [ N Bytes: JSON UTF-8 Payload ]
"""

import json
import struct
import socket
from datetime import datetime

# Length prefix: 4 bytes unsigned int (standard network byte order '!I')
HEADER_STRUCT = struct.Struct('!I')
HEADER_SIZE = HEADER_STRUCT.size

# Message Types
MSG_LOGIN = "LOGIN"
MSG_LOGIN_RESP = "LOGIN_RESP"
MSG_BROADCAST = "BROADCAST"
MSG_PRIVATE = "PRIVATE"
MSG_USER_JOIN = "USER_JOIN"
MSG_USER_LEAVE = "USER_LEAVE"
MSG_USER_LIST = "USER_LIST"
MSG_PING = "PING"
MSG_PONG = "PONG"
MSG_SYSTEM = "SYSTEM"
MSG_ERROR = "ERROR"

def get_current_timestamp() -> str:
    """Returns formatted current time HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")

def send_packet(sock: socket.socket, data: dict) -> int:
    """
    Serializes a Python dictionary to JSON, encodes to UTF-8,
    prepends a 4-byte network-byte-order length header,
    and transmits it reliably using sock.sendall().
    
    Returns total bytes transmitted (header + payload).
    Raises ConnectionError if sending fails.
    """
    try:
        payload = json.dumps(data).encode('utf-8')
        header = HEADER_STRUCT.pack(len(payload))
        packet = header + payload
        sock.sendall(packet)
        return len(packet)
    except (socket.error, BrokenPipeError, ConnectionResetError) as e:
        raise ConnectionError(f"Socket send failed: {e}")

def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Helper function to reliably receive exactly `num_bytes` from a TCP socket.
    Handles partial reads caused by network fragmentation.
    
    Returns bytes or raises ConnectionError if the socket is closed prematurely.
    """
    chunks = []
    bytes_received = 0
    while bytes_received < num_bytes:
        chunk = sock.recv(num_bytes - bytes_received)
        if not chunk:
            raise ConnectionError("Socket closed prematurely by peer.")
        chunks.append(chunk)
        bytes_received += len(chunk)
    return b''.join(chunks)

def recv_packet(sock: socket.socket) -> tuple[dict, int]:
    """
    Reads a complete length-prefixed packet from a TCP socket:
    1. Reads 4-byte header to determine payload length.
    2. Reads exactly that many bytes of JSON payload.
    3. Deserializes and returns (data_dict, total_bytes_read).
    
    Returns (None, 0) if the socket was cleanly closed.
    Raises ConnectionError if an unexpected disconnection occurs.
    """
    try:
        header_bytes = recv_exact(sock, HEADER_SIZE)
        payload_len = HEADER_STRUCT.unpack(header_bytes)[0]
        payload_bytes = recv_exact(sock, payload_len)
        data = json.loads(payload_bytes.decode('utf-8'))
        total_bytes = HEADER_SIZE + payload_len
        return data, total_bytes
    except ConnectionError:
        return None, 0
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Malformed packet received: {e}")
