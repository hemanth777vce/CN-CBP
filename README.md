# Multi-Client Chat Application using TCP Sockets

A production-grade **Multi-Client Desktop Chat Application** developed for the **Computer Networks (Transport Layer – Socket Programming)** course project.

---

## 📑 Table of Contents
1. [Project Overview](#project-overview)
2. [Core Architecture](#core-architecture)
3. [TCP Socket Lifecycle & Networking Concepts](#tcp-socket-lifecycle--networking-concepts)
4. [Custom Framing & Message Protocol](#custom-framing--message-protocol)
5. [Frontend & Unique Networking Features](#frontend--unique-networking-features)
6. [Project Structure](#project-structure)
7. [Installation & Setup](#installation--setup)
8. [How to Run](#how-to-run)
9. [Supported Commands](#supported-commands)
10. [Automated Verification Tests](#automated-verification-tests)
11. [Computer Networks Viva Q&A Guide](#computer-networks-viva-qa-guide)

---

## Project Overview

- **Course:** Computer Networks
- **Domain:** Transport Layer – Socket Programming
- **Key Concepts:** TCP, Sockets (`AF_INET`, `SOCK_STREAM`), Client-Server Architecture, IP Addressing, Ephemeral Ports, Concurrency & Multithreading, Thread-Safe Shared Memory, Length-Prefixed Framing, SQLite Local Persistence.
- **Backend:** Python `socket`, `threading`, `struct`, `json`
- **Frontend:** Python `customtkinter` (Modern Dark-Themed Desktop UI)
- **Local Storage:** SQLite (`chat_history.db`)

Unlike web-based chat clones, this application communicates strictly over raw **TCP Sockets** at the Transport Layer using native operating system socket APIs.

---

## Core Architecture

### Client-Server Topology
```text
                         TCP SOCKET CONNECTION
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   CHAT SERVER   │
                         │                 │
                         │ IP: 127.0.0.1   │
                         │ PORT: 5000      │
                         └────────┬────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                │
                 ▼                ▼                ▼
            ┌─────────┐      ┌─────────┐      ┌─────────┐
            │ Client 1│      │ Client 2│      │ Client 3│
            │  Alice  │      │   Bob   │      │ Hemanth │
            └─────────┘      └─────────┘      └─────────┘
```

### Server Concurrency Model
The server utilizes a **Thread-per-Client concurrency architecture**:

```text
Server Process
 ├── Main Thread
 │     └── socket() -> bind() -> listen() -> accept() loop
 │
 ├── Client Handler Thread 1 (Alice)
 │     └── recv_packet() -> Route Broadcast / Unicast Private
 │
 ├── Client Handler Thread 2 (Bob)
 │     └── recv_packet() -> Route Broadcast / Unicast Private
 │
 └── Client Handler Thread 3 (Hemanth)
       └── recv_packet() -> Route Broadcast / Unicast Private
```

Shared resources (such as active client dictionaries) are synchronized using `threading.Lock()` to prevent race conditions.

---

## TCP Socket Lifecycle & Networking Concepts

This project explicitly demonstrates all standard POSIX / BSD socket system calls:

```text
       SERVER SOCKET                                 CLIENT SOCKET
       ─────────────                                 ─────────────
       socket(AF_INET, SOCK_STREAM)                  socket(AF_INET, SOCK_STREAM)
              │                                             │
       setsockopt(SO_REUSEADDR)                             │
              │                                             │
       bind((HOST, PORT))                                   │
              │                                             │
       listen(BACKLOG)                                      │
              │                                             │
       accept() <───────────── [SYN] ──────────────── connect((HOST, PORT))
          │     ─────────── [SYN-ACK] ───────────►          │
          │     ◄───────────── [ACK] ─────────────          │
          │       (TCP 3-Way Handshake Established)         │
          │                                                 │
       recv()   ◄────── [Length-Prefixed JSON] ─────────── send()
       send()   ──────► [Length-Prefixed JSON] ─────────── recv()
          │                                                 │
       close()  ◄─────── [FIN] ── [ACK] ────────────────── close()
```

### Socket Parameters:
- `AF_INET`: Address Family for IPv4 Internet protocols.
- `SOCK_STREAM`: Sequenced, reliable, two-way, connection-based byte streams (TCP).

---

## Custom Framing & Message Protocol

### The TCP Framing Problem ("Packet Sticking / Gluing")
TCP is a **stream-oriented protocol**, not a message-oriented protocol. It does not preserve application-layer message boundaries:
1. **Packet Sticking / Coalescing:** If two messages are sent rapidly, TCP may combine them into a single `recv()` chunk.
2. **Packet Fragmentation:** A single message may be split across multiple `recv()` calls due to MTU and OS network buffer limits.

### Our Solution: 4-Byte Length-Prefixed Framing
Each message transmitted over the socket begins with a fixed **4-byte unsigned integer header** (`struct.pack('!I', length)`) in **Network Byte Order (Big-Endian)**, followed by the UTF-8 encoded JSON payload:

```text
┌─────────────────────────────────┬───────────────────────────────────────┐
│  4-Byte Header (Network Order)  │       N-Byte UTF-8 JSON Payload       │
│      Payload Length (N)         │  {"type": "BROADCAST", "message":...} │
└─────────────────────────────────┴───────────────────────────────────────┘
```

The receiver first reads exactly 4 bytes to determine $N$, and then loops `recv()` until exactly $N$ bytes have arrived.

### Message Packet Types (JSON):
| Packet Type | Description | Key Fields |
|---|---|---|
| `LOGIN` | Initial client authentication | `username` |
| `LOGIN_RESP` | Server response to login | `success`, `message`, `users` |
| `BROADCAST` | Message to all online users | `sender`, `message`, `timestamp` |
| `PRIVATE` | Unicast message to single user | `sender`, `receiver`, `message`, `timestamp` |
| `USER_JOIN` | Notification when user connects | `username`, `users`, `timestamp` |
| `USER_LEAVE` | Notification when user disconnects | `username`, `users`, `timestamp` |
| `PING` / `PONG` | Round-trip latency calculation | `timestamp` |
| `ERROR` | Informational network error | `message` |

---

## Frontend & Unique Networking Features

Built using **CustomTkinter** for a polished dark-themed interface:

1. **User Login Modal:**
   - Validates username, host IP, and port with instant connectivity checks.
2. **Dynamic Online Users Sidebar:**
   - Displays real-time connected users with status dots (`🟢`), avatar initials, and a single-click button to initiate private messaging.
3. **Interactive Message Stream:**
   - Distinct speech bubbles:
     - Sent messages: Aligned right, blue accent.
     - Received messages: Aligned left with avatar badges.
     - Private messages: Highlighted in purple with `[PRIVATE]` lock indicator.
     - System events: Centered notifications.
4. **Live Network Activity Visualizer:**
   - Dynamic arrows indicating real-time packet transmissions:
     - Transmitting: `You ──────► Server` (flashes on `send()`)
     - Receiving: `Server ──────► You` (flashes on `recv()`)
5. **Connection Details & Viva Inspector (Expandable Panel):**
   - Live telemetry for viva examination:
     - Protocol: `TCP`
     - Socket Type: `SOCK_STREAM`
     - Socket Family: `AF_INET (IPv4)`
     - Server Endpoint: `127.0.0.1:5000`
     - Client Ephemeral Port: Dynamically assigned OS port (e.g. `54210`)
     - TCP State: `ESTABLISHED`
     - Real-time RTT Ping Latency (ms)
     - Cumulative Packets Sent (TX) & Received (RX)
     - Cumulative Bytes Sent & Received
6. **Local SQLite Chat History:**
   - Stores messages in `chat_history.db` (`sender`, `receiver`, `msg_type`, `content`, `timestamp`) with an inspection modal.
7. **Server Management Dashboard:**
   - Includes both an ANSI-colored **CLI Server** (`server.py`) and a modern **Server GUI Dashboard** (`server_gui.py`) showing active sockets, connected threads, and live event logs.

---

## Project Structure

```text
cn-cbp/
├── protocol.py          # Framing protocol, 4-byte header packing/unpacking, message types
├── storage.py           # SQLite local database storage for chat history
├── server.py            # Multithreaded TCP Chat Server (CLI with ANSI color logs)
├── server_gui.py        # Optional graphical Server Dashboard with live client table
├── client.py            # TCP Client networking engine (background listener thread)
├── client_gui.py        # Modern CustomTkinter GUI (Login, chat feed, networking panels)
├── run_server.py        # Launcher for server (--gui or CLI)
├── run_client.py        # Launcher for client GUI
├── launch_demo.py       # Cross-platform demo launcher (spawns 1 server + 2 clients)
├── launch_demo.bat      # Windows batch file for 1-click launch
├── test_networking.py  # Automated unit tests for socket networking & concurrency
├── requirements.txt     # Python package requirements
└── README.md            # Comprehensive documentation & Viva Q&A Guide
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ installed on Windows / Linux / macOS.
- Standard libraries (`socket`, `threading`, `json`, `sqlite3`, `struct`) are built into Python.

### Install Dependencies
```powershell
pip install -r requirements.txt
```

---

## How to Run

### Method 1: Instant One-Click Demo
To launch the server and two client instances (e.g., Alice and Bob) simultaneously:
```powershell
python launch_demo.py
```
*(On Windows, you can also double-click `launch_demo.bat`)*

---

### Method 2: Manual Step-by-Step Launch

#### Step 1: Start the TCP Server
**Option A — CLI Server with Rich Terminal Logs:**
```powershell
python run_server.py
```

**Option B — Modern Server GUI Dashboard:**
```powershell
python run_server.py --gui
```

#### Step 2: Launch Chat Clients
Open one or more terminal windows and run:
```powershell
python run_client.py
```
1. Enter your Username (e.g., `Alice`).
2. Keep Server IP as `127.0.0.1` and Port as `5000`.
3. Click **CONNECT TO SERVER**.
4. In another terminal, run `python run_client.py` with Username `Bob`.

---

## Supported Commands

Type these directly in the message entry box:

| Command | Syntax | Description |
|---|---|---|
| `/help` | `/help` | Displays list of available commands |
| `/users` | `/users` | Lists all online users connected to the server |
| `/msg` | `/msg <username> <message>` | Sends a private message to a specific user |
| `/ping` | `/ping` | Measures round-trip time (RTT) to the server in milliseconds |
| `/clear` | `/clear` | Clears the local chat feed |
| `/quit` | `/quit` | Cleanly disconnects and closes the TCP socket |

---

## Automated Verification Tests

A comprehensive unit test suite is included to verify the networking implementation under concurrent load:

```powershell
python test_networking.py
```

**Test Cases Covered:**
1. `test_01_multi_client_connections`: Verifies concurrent client logins and ephemeral port allocations.
2. `test_02_duplicate_username_rejected`: Tests server rejection of identical usernames.
3. `test_03_broadcast_message_routing`: Tests broadcast message reception across multiple sockets.
4. `test_04_private_message_routing`: Tests unicast message isolation (target client receives; others do not).
5. `test_05_ping_pong_latency`: Tests TCP round-trip latency calculation.
6. `test_06_sqlite_storage`: Tests local SQLite message persistence and history retrieval.

---

## Computer Networks Viva Q&A Guide

Use these answers during your viva or project presentation:

### Q1: Why did you choose TCP over UDP for this chat application?
> **Answer:**  
> TCP is a connection-oriented, reliable transport protocol that guarantees ordered, error-checked delivery through sequence numbers and acknowledgments. In a chat application, dropping messages (packet loss) or delivering them out of order is unacceptable. UDP is connectionless and does not guarantee delivery or packet order, making it suitable for video streaming or gaming, but unsuitable for reliable text communication.

---

### Q2: What is the TCP 3-Way Handshake, and where does it occur in your code?
> **Answer:**  
> The 3-way handshake establishes a reliable TCP connection:
> 1. **SYN:** Client sends a synchronize segment with an initial sequence number.
> 2. **SYN-ACK:** Server responds acknowledging the sequence number and sending its own SYN.
> 3. **ACK:** Client acknowledges the server's SYN.
> 
> In our code:
> - On the client: `client_sock.connect((host, port))` initiates and completes the handshake.
> - On the server: `server_sock.accept()` blocks until the handshake is complete, returning the connected client socket.

---

### Q3: What is the purpose of `SO_REUSEADDR`?
> **Answer:**  
> When a TCP server shuts down, sockets often enter the `TIME_WAIT` state (typically 1 to 2 minutes) to ensure delayed packets from the old connection do not interfere with new ones. Without `SO_REUSEADDR`:
> ```python
> server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
> ```
> restarting the server immediately would result in `OSError: [Errno 98/10048] Address already in use`. `SO_REUSEADDR` permits immediate re-binding to the port.

---

### Q4: What is an ephemeral port, and how does your app demonstrate it?
> **Answer:**  
> While the server listens on a well-known, fixed port (Port `5000`), the client does not bind to a predetermined port. Instead, when `connect()` is executed, the operating system kernel dynamically assigns an available temporary port (typically in the range 49152–65535), called an **ephemeral port**.  
> In our application, the client discovers its ephemeral port via `sock.getsockname()[1]` and displays it live in the **Connection Details** panel.

---

### Q5: What is the "TCP Packet Sticking / Framing Problem" and how did you resolve it?
> **Answer:**  
> TCP operates as a continuous byte stream without message delimiters. If a client transmits two messages consecutively, the TCP layer may aggregate them into a single packet (via Nagle's algorithm), causing both messages to arrive in a single `recv()` call. Conversely, large messages can be split across multiple `recv()` calls.  
> To solve this, we implemented **Length-Prefixed Framing** in `protocol.py`. Every message is prepended with a 4-byte network-byte-order header specifying the exact byte length of the JSON payload. The receiver reads the 4-byte header first, then precisely accumulates that number of payload bytes.

---

### Q6: Why did you use multithreading on both the server and the client?
> **Answer:**  
> - **Server:** `accept()` and `recv()` are blocking calls. Spawning a separate worker thread for each client allows the server to service multiple connected clients concurrently without one idle client blocking others.
> - **Client:** The GUI operates on an event loop. If `recv()` were called on the main GUI thread, the interface would freeze while waiting for incoming data. Running `recv()` inside a background daemon thread keeps the UI responsive.

---

### Q7: How does your server detect when a client disconnects?
> **Answer:**  
> When a client closes its socket or terminates, the TCP protocol transmits a `FIN` packet. At the socket layer, `sock.recv()` returns an empty byte string (`b''`). Our `recv_packet()` function detects this empty read (or catches `ConnectionResetError`), safely cleans up the client entry from the `clients` dictionary, and broadcasts a `USER_LEAVE` event to the remaining connected clients.

---

### Q8: How is thread safety ensured on the server?
> **Answer:**  
> Multiple client threads access and modify the shared `self.clients` dictionary (adding users during login, reading users during broadcast, and removing users upon exit). To prevent race conditions, all read/write operations on the dictionary are synchronized using a `threading.Lock()` via Python's `with self.clients_lock:` construct.
