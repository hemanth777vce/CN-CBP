"""
server_gui.py - Modern Server Monitoring Dashboard GUI
Computer Networks Course Project: Transport Layer - Socket Programming

Features:
- Live Socket Status (Listening / Stopped)
- Active Connected Clients table (Username, IP, Ephemeral Port, Thread Name, Time)
- Live Server Telemetry (Active Threads, Total Connections, Messages Routed, Uptime)
- Real-time socket event log stream
- One-click Start/Stop server controls
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import socket
import time
from typing import Dict, Tuple

from protocol import (
    send_packet, recv_packet, get_current_timestamp,
    MSG_LOGIN, MSG_LOGIN_RESP, MSG_BROADCAST, MSG_PRIVATE,
    MSG_USER_JOIN, MSG_USER_LEAVE, MSG_USER_LIST, MSG_PING, MSG_PONG,
    MSG_SYSTEM, MSG_ERROR
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ServerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TCP Chat Server - Network Administration Console")
        self.geometry("980, 680")
        self.minsize(850, 550)

        # Server State
        self.host = "127.0.0.1"
        self.port = 5000
        self.server_sock: socket.socket = None
        self.running = False
        self.start_time = None
        
        # Connected clients: username -> (sock, (ip, port), thread_name, join_time, msg_count)
        self.clients: Dict[str, dict] = {}
        self.clients_lock = threading.Lock()
        
        # Telemetry counters
        self.total_connections = 0
        self.total_messages = 0

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        # Top Bar
        top_bar = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color="#161922")
        top_bar.pack(fill="x", side="top")
        top_bar.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            top_bar, text="TCP SERVER DASHBOARD",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#38BDF8"
        )
        title_lbl.pack(side="left", padx=20, pady=16)

        self.status_badge = ctk.CTkLabel(
            top_bar, text="  ● SERVER STOPPED  ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#EF4444", fg_color="#450A0A", corner_radius=12
        )
        self.status_badge.pack(side="left", padx=10, pady=16)

        # Control Box
        ctrl_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        ctrl_frame.pack(side="right", padx=20, pady=12)

        port_lbl = ctk.CTkLabel(ctrl_frame, text="Port:", font=ctk.CTkFont(weight="bold"))
        port_lbl.pack(side="left", padx=4)

        self.port_entry = ctk.CTkEntry(ctrl_frame, width=70, font=ctk.CTkFont(size=13))
        self.port_entry.insert(0, "5000")
        self.port_entry.pack(side="left", padx=6)

        self.toggle_btn = ctk.CTkButton(
            ctrl_frame, text="START SERVER", width=120, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#059669", hover_color="#047857",
            command=self._toggle_server
        )
        self.toggle_btn.pack(side="left", padx=6)

        # Main Workspace: Left Stats/Clients, Right Logs
        workspace = ctk.CTkFrame(self, corner_radius=0, fg_color="#0F1117")
        workspace.pack(fill="both", expand=True)

        # Stats Cards Grid
        stats_frame = ctk.CTkFrame(workspace, fg_color="transparent")
        stats_frame.pack(fill="x", padx=16, pady=12)

        self.stat_cards = {}
        metrics = [
            ("Active Clients", "0", "#38BDF8"),
            ("Worker Threads", "0", "#A855F7"),
            ("Messages Routed", "0", "#34D399"),
            ("Total Handshakes", "0", "#F59E0B"),
        ]

        for i, (title, val, col) in enumerate(metrics):
            card = ctk.CTkFrame(stats_frame, fg_color="#1E222D", corner_radius=10, height=70)
            card.pack(side="left", fill="both", expand=True, padx=6)
            card.pack_propagate(False)

            t_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8")
            t_lbl.pack(anchor="w", padx=14, pady=(8, 2))

            v_lbl = ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=18, weight="bold"), text_color=col)
            v_lbl.pack(anchor="w", padx=14, pady=(0, 8))
            self.stat_cards[title] = v_lbl

        # Content Split: Client Table (Left) and Event Logs (Right)
        panes = ctk.CTkFrame(workspace, fg_color="transparent")
        panes.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Left Panel: Connected Sockets
        left_box = ctk.CTkFrame(panes, width=440, fg_color="#161922", corner_radius=10)
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        c_hdr = ctk.CTkLabel(left_box, text="ACTIVE TCP CLIENT CONNECTIONS", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38BDF8")
        c_hdr.pack(anchor="w", padx=14, pady=(12, 6))

        self.clients_scroll = ctk.CTkScrollableFrame(left_box, fg_color="transparent", corner_radius=8)
        self.clients_scroll.pack(fill="both", expand=True, padx=10, pady=8)

        # Right Panel: Live Event Log Feed
        right_box = ctk.CTkFrame(panes, fg_color="#161922", corner_radius=10)
        right_box.pack(side="right", fill="both", expand=True, padx=(8, 0))

        log_hdr = ctk.CTkFrame(right_box, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(12, 6))

        l_lbl = ctk.CTkLabel(log_hdr, text="LIVE SERVER EVENT LOGS", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38BDF8")
        l_lbl.pack(side="left")

        clr_btn = ctk.CTkButton(log_hdr, text="Clear Logs", width=80, height=24, font=ctk.CTkFont(size=11), fg_color="#334155", command=self._clear_logs)
        clr_btn.pack(side="right")

        self.log_text = ctk.CTkTextbox(right_box, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#0F1117")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=8)

    def log(self, text: str):
        """Appends log entry to the server log textbox."""
        ts = get_current_timestamp()
        line = f"[{ts}] {text}\n"
        self.after(0, lambda: self._append_log_text(line))

    def _append_log_text(self, line: str):
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)

    def _clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _toggle_server(self):
        """Starts or stops the TCP server."""
        if not self.running:
            try:
                self.port = int(self.port_entry.get().strip())
            except ValueError:
                self.log("Invalid port number specified.")
                return

            self.running = True
            self.toggle_btn.configure(text="STOP SERVER", fg_color="#991B1B", hover_color="#B91C1C")
            self.status_badge.configure(text=f"  ● LISTENING ({self.host}:{self.port})  ", text_color="#10B981", fg_color="#064E3B")
            self.port_entry.configure(state="disabled")

            # Launch accept loop thread
            threading.Thread(target=self._server_listen_thread, daemon=True).start()
        else:
            self._stop_server()

    def _server_listen_thread(self):
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(25)
            self.start_time = time.time()
            self.log(f"Socket created (AF_INET, SOCK_STREAM). Bound to {self.host}:{self.port}")
            self.log(f"Server is listening. Ready to accept client connections.")

            while self.running:
                try:
                    client_sock, client_addr = self.server_sock.accept()
                    self.total_connections += 1
                    tname = f"WorkerThread-{self.total_connections}"
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, client_addr, tname),
                        daemon=True
                    ).start()
                except socket.error:
                    break
        except Exception as e:
            self.log(f"Server listener error: {e}")
        finally:
            self._stop_server()

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int], thread_name: str):
        username = None
        ip, port = client_addr
        self.log(f"New TCP connection accepted from {ip}:{port} on {thread_name}")

        try:
            packet, _ = recv_packet(client_sock)
            if not packet or packet.get("type") != MSG_LOGIN:
                client_sock.close()
                return

            candidate_name = packet.get("username", "").strip()
            with self.clients_lock:
                if not candidate_name or candidate_name in self.clients:
                    send_packet(client_sock, {
                        "type": MSG_LOGIN_RESP,
                        "success": False,
                        "message": "Username invalid or already in use."
                    })
                    client_sock.close()
                    return

                username = candidate_name
                join_time = get_current_timestamp()
                self.clients[username] = {
                    "sock": client_sock,
                    "addr": client_addr,
                    "thread": thread_name,
                    "join_time": join_time,
                    "msg_count": 0
                }
                active_users = list(self.clients.keys())

            send_packet(client_sock, {
                "type": MSG_LOGIN_RESP,
                "success": True,
                "message": f"Welcome, {username}!",
                "users": active_users
            })

            self.log(f"Handshake complete: User '{username}' registered from {ip}:{port}")
            self._broadcast({
                "type": MSG_USER_JOIN,
                "username": username,
                "users": active_users,
                "timestamp": join_time,
                "message": f"● {username} joined the chat"
            }, exclude_user=username)
            self._refresh_client_ui()

            # Message Loop
            while self.running:
                packet, _ = recv_packet(client_sock)
                if packet is None:
                    break

                self.total_messages += 1
                msg_type = packet.get("type")

                if msg_type == MSG_BROADCAST:
                    msg_text = packet.get("message", "")
                    ts = packet.get("timestamp", get_current_timestamp())
                    self.log(f"[BROADCAST] {username} ──► EVERYONE: {msg_text}")
                    with self.clients_lock:
                        if username in self.clients:
                            self.clients[username]["msg_count"] += 1
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
                    send_packet(client_sock, {
                        "type": MSG_PONG,
                        "timestamp": packet.get("timestamp", time.time())
                    })

                elif msg_type == MSG_USER_LIST:
                    with self.clients_lock:
                        u_list = list(self.clients.keys())
                    send_packet(client_sock, {"type": MSG_USER_LIST, "users": u_list})

                self._refresh_client_ui()

        except Exception as e:
            self.log(f"Connection error with client {username or ip}: {e}")
        finally:
            if username:
                with self.clients_lock:
                    if username in self.clients:
                        del self.clients[username]
                    rem = list(self.clients.keys())
                self.log(f"Client disconnected: {username} ({ip}:{port})")
                self._broadcast({
                    "type": MSG_USER_LEAVE,
                    "username": username,
                    "users": rem,
                    "timestamp": get_current_timestamp(),
                    "message": f"● {username} disconnected"
                })
                self._refresh_client_ui()
            try:
                client_sock.close()
            except Exception:
                pass

    def _broadcast(self, packet: dict, exclude_user: str = None):
        with self.clients_lock:
            targets = [(u, d["sock"]) for u, d in self.clients.items() if u != exclude_user]
        for _, sock in targets:
            try:
                send_packet(sock, packet)
            except Exception:
                pass

    def _route_private(self, sender: str, receiver: str, text: str, ts: str, sender_sock: socket.socket):
        target_sock = None
        with self.clients_lock:
            if receiver in self.clients:
                target_sock = self.clients[receiver]["sock"]
                if sender in self.clients:
                    self.clients[sender]["msg_count"] += 1

        if target_sock:
            self.log(f"[PRIVATE] {sender} ──► {receiver}: {text}")
            send_packet(target_sock, {
                "type": MSG_PRIVATE, "sender": sender, "receiver": receiver,
                "message": text, "timestamp": ts
            })
            send_packet(sender_sock, {
                "type": MSG_PRIVATE, "sender": sender, "receiver": receiver,
                "message": text, "timestamp": ts, "is_echo": True
            })
        else:
            send_packet(sender_sock, {
                "type": MSG_ERROR, "message": f"User '{receiver}' is not online."
            })

    def _refresh_client_ui(self):
        self.after(0, self._render_client_cards)

    def _render_client_cards(self):
        # Update cards
        with self.clients_lock:
            client_items = list(self.clients.items())

        self.stat_cards["Active Clients"].configure(text=str(len(client_items)))
        self.stat_cards["Worker Threads"].configure(text=str(threading.active_count()))
        self.stat_cards["Messages Routed"].configure(text=str(self.total_messages))
        self.stat_cards["Total Handshakes"].configure(text=str(self.total_connections))

        for widget in self.clients_scroll.winfo_children():
            widget.destroy()

        if not client_items:
            empty_lbl = ctk.CTkLabel(self.clients_scroll, text="No clients currently connected.", text_color="#94A3B8")
            empty_lbl.pack(pady=20)
            return

        for uname, info in client_items:
            ip, port = info["addr"]
            card = ctk.CTkFrame(self.clients_scroll, fg_color="#1E222D", corner_radius=8)
            card.pack(fill="x", pady=4)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(6, 2))

            u_lbl = ctk.CTkLabel(top_row, text=f"👤 {uname}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8")
            u_lbl.pack(side="left")

            t_lbl = ctk.CTkLabel(top_row, text=f"{info['thread']}", font=ctk.CTkFont(family="Consolas", size=10), text_color="#94A3B8")
            t_lbl.pack(side="right")

            bot_row = ctk.CTkFrame(card, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 6))

            addr_lbl = ctk.CTkLabel(bot_row, text=f"Socket: {ip}:{port} (Ephemeral)", font=ctk.CTkFont(size=11), text_color="#CBD5E1")
            addr_lbl.pack(side="left")

            cnt_lbl = ctk.CTkLabel(bot_row, text=f"Msgs: {info['msg_count']}", font=ctk.CTkFont(size=11), text_color="#34D399")
            cnt_lbl.pack(side="right")

    def _stop_server(self):
        self.running = False
        self.toggle_btn.configure(text="START SERVER", fg_color="#059669", hover_color="#047857")
        self.status_badge.configure(text="  ● SERVER STOPPED  ", text_color="#EF4444", fg_color="#450A0A")
        self.port_entry.configure(state="normal")

        with self.clients_lock:
            for uname, info in list(self.clients.items()):
                try:
                    info["sock"].close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None

        self.log("Server stopped.")
        self._refresh_client_ui()

    def _on_closing(self):
        self._stop_server()
        self.destroy()

def main():
    app = ServerGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
