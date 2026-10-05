"""
client_gui.py - Modern Dark-Themed TCP Chat Client GUI
Computer Networks Course Project: Transport Layer - Socket Programming

Built with CustomTkinter:
- Sleek dark theme with responsive layout
- Message bubbles with avatars, initials, and timestamps
- Real-time online users with direct-message selection
- Dynamic Network Activity Indicator (TX/RX packet flow)
- Expandable "Connection Details & Viva Inspector" panel
- Local SQLite Chat History integration
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import time
from typing import Optional, List

from client import TCPChatClient
from storage import ChatStorage
from protocol import (
    MSG_BROADCAST, MSG_PRIVATE, MSG_USER_JOIN, 
    MSG_USER_LEAVE, MSG_SYSTEM, MSG_ERROR, get_current_timestamp
)

# Configure CustomTkinter Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ChatGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TCP Multi-Client Chat - Computer Networks Project")
        self.geometry("1100, 720")
        self.minsize(950, 600)

        # Network Client & Local Database
        self.client = TCPChatClient()
        self.storage = ChatStorage()
        
        # State Tracking
        self.current_recipient: Optional[str] = None  # None = Broadcast (General)
        self.online_users: List[str] = []
        self.details_visible: bool = True
        self.activity_timer_id = None
        
        # Wire Networking Callbacks
        self.client.on_message_callback = self._on_message_received
        self.client.on_user_list_callback = self._on_user_list_updated
        self.client.on_network_activity_callback = self._on_network_activity
        self.client.on_disconnect_callback = self._on_disconnected
        self.client.on_rtt_update_callback = self._on_rtt_updated

        # UI Container: Starts with Login Screen
        self.container = ctk.CTkFrame(self, corner_radius=0)
        self.container.pack(fill="both", expand=True)

        self._show_login_screen()

        # Handle window close cleanly
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # =========================================================================
    # LOGIN SCREEN
    # =========================================================================
    def _show_login_screen(self):
        """Builds modern, clean login screen with networking configuration."""
        for widget in self.container.winfo_children():
            widget.destroy()

        login_frame = ctk.CTkFrame(self.container, width=440, corner_radius=16, fg_color="#181B20")
        login_frame.place(relx=0.5, rely=0.5, anchor="center")

        # Top Badge / Logo
        badge_frame = ctk.CTkFrame(login_frame, fg_color="#23272F", corner_radius=10)
        badge_frame.pack(pady=(28, 12), padx=30, fill="x")

        icon_label = ctk.CTkLabel(
            badge_frame,
            text="⚡ TCP SOCKET CHAT",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#38BDF8"
        )
        icon_label.pack(pady=10)

        sub_label = ctk.CTkLabel(
            login_frame,
            text="Computer Networks Course Project\nTransport Layer • Socket Programming",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8"
        )
        sub_label.pack(pady=(0, 20))

        # Input: Username
        u_label = ctk.CTkLabel(login_frame, text="Username", font=ctk.CTkFont(weight="bold", size=13), anchor="w")
        u_label.pack(fill="x", padx=36, pady=(4, 2))
        self.login_user_entry = ctk.CTkEntry(
            login_frame, placeholder_text="e.g. Hemanth or Alice", height=42, corner_radius=8,
            font=ctk.CTkFont(size=14)
        )
        self.login_user_entry.pack(fill="x", padx=36, pady=(0, 14))
        self.login_user_entry.focus()

        # Input: Server IP
        ip_label = ctk.CTkLabel(login_frame, text="Server IP Address", font=ctk.CTkFont(weight="bold", size=13), anchor="w")
        ip_label.pack(fill="x", padx=36, pady=(4, 2))
        self.login_ip_entry = ctk.CTkEntry(
            login_frame, placeholder_text="127.0.0.1", height=42, corner_radius=8,
            font=ctk.CTkFont(size=14)
        )
        self.login_ip_entry.insert(0, "127.0.0.1")
        self.login_ip_entry.pack(fill="x", padx=36, pady=(0, 14))

        # Input: Server Port
        port_label = ctk.CTkLabel(login_frame, text="Server Port (TCP)", font=ctk.CTkFont(weight="bold", size=13), anchor="w")
        port_label.pack(fill="x", padx=36, pady=(4, 2))
        self.login_port_entry = ctk.CTkEntry(
            login_frame, placeholder_text="5000", height=42, corner_radius=8,
            font=ctk.CTkFont(size=14)
        )
        self.login_port_entry.insert(0, "5000")
        self.login_port_entry.pack(fill="x", padx=36, pady=(0, 16))

        # Error / Status message banner
        self.login_status_label = ctk.CTkLabel(
            login_frame, text="", text_color="#EF4444",
            font=ctk.CTkFont(size=12, weight="bold"), wraplength=360
        )
        self.login_status_label.pack(fill="x", padx=36, pady=(0, 10))

        # Connect Button
        self.connect_btn = ctk.CTkButton(
            login_frame,
            text="CONNECT TO SERVER",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self._handle_connect_submit
        )
        self.connect_btn.pack(fill="x", padx=36, pady=(4, 28))

        # Keyboard Bindings
        self.login_user_entry.bind("<Return>", lambda e: self._handle_connect_submit())
        self.login_ip_entry.bind("<Return>", lambda e: self._handle_connect_submit())
        self.login_port_entry.bind("<Return>", lambda e: self._handle_connect_submit())

    def _handle_connect_submit(self):
        """Validates inputs and attempts TCP connection in a separate thread."""
        username = self.login_user_entry.get().strip()
        ip = self.login_ip_entry.get().strip()
        port_str = self.login_port_entry.get().strip()

        if not username:
            self.login_status_label.configure(text="Please enter a valid username.", text_color="#EF4444")
            return
        if not ip:
            self.login_status_label.configure(text="Please enter server IP address.", text_color="#EF4444")
            return
        try:
            port = int(port_str)
            if port <= 0 or port > 65535:
                raise ValueError()
        except ValueError:
            self.login_status_label.configure(text="Port must be an integer between 1 and 65535.", text_color="#EF4444")
            return

        self.connect_btn.configure(state="disabled", text="Connecting to TCP Socket...")
        self.login_status_label.configure(text="Initiating TCP 3-Way Handshake...", text_color="#38BDF8")

        def connect_worker():
            success, message = self.client.connect(ip, port, username)
            self.after(0, lambda: self._on_connect_result(success, message))

        threading.Thread(target=connect_worker, daemon=True).start()

    def _on_connect_result(self, success: bool, message: str):
        """Handles connection attempt result on main thread."""
        if success:
            self._show_chat_screen()
        else:
            self.connect_btn.configure(state="normal", text="CONNECT TO SERVER")
            self.login_status_label.configure(text=message, text_color="#EF4444")

    # =========================================================================
    # MAIN CHAT SCREEN
    # =========================================================================
    def _show_chat_screen(self):
        """Constructs the full multi-panel chat interface."""
        for widget in self.container.winfo_children():
            widget.destroy()

        # Top Header Bar
        self._build_top_header()

        # Workspace Body: Sidebar (Left), Chat Feed (Center), Details (Right)
        body = ctk.CTkFrame(self.container, corner_radius=0, fg_color="#0F1117")
        body.pack(fill="both", expand=True)

        # 1. Left Sidebar
        self._build_sidebar(body)

        # 2. Right Expandable Details Panel
        self._build_details_panel(body)

        # 3. Center Chat Area
        self._build_chat_center(body)

        # Send initial ping to calculate RTT
        self.after(1000, self._periodic_telemetry)

        # Load recent local history from SQLite
        self._load_local_history_preview()

    def _build_top_header(self):
        """Top navigation bar showing branding, connection indicator, and toggle."""
        header = ctk.CTkFrame(self.container, height=54, corner_radius=0, fg_color="#161922")
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Left Branding
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=16, fill="y")

        brand_title = ctk.CTkLabel(
            brand_frame, text="TCP CHAT NETWORK",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#38BDF8"
        )
        brand_title.pack(side="left", pady=12)

        # Connection Status Indicator
        self.status_badge = ctk.CTkLabel(
            brand_frame, text="  ● TCP CONNECTED  ",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#10B981", fg_color="#064E3B", corner_radius=12
        )
        self.status_badge.pack(side="left", padx=14, pady=12)

        # Right Controls
        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.pack(side="right", padx=16, fill="y")

        self.details_toggle_btn = ctk.CTkButton(
            right_frame, text="⚡ Connection Details", width=140, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E293B", hover_color="#334155",
            command=self._toggle_details_panel
        )
        self.details_toggle_btn.pack(side="right", padx=6, pady=11)

        disconnect_btn = ctk.CTkButton(
            right_frame, text="Disconnect", width=90, height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#991B1B", hover_color="#B91C1C",
            command=self._handle_manual_disconnect
        )
        disconnect_btn.pack(side="right", padx=6, pady=11)

    def _build_sidebar(self, parent):
        """Left sidebar: Current User Card, Channel Switcher, Online Users, Activity Visualizer."""
        self.sidebar = ctk.CTkFrame(parent, width=260, corner_radius=0, fg_color="#161922")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Current User Profile Card
        user_card = ctk.CTkFrame(self.sidebar, fg_color="#1E222D", corner_radius=10)
        user_card.pack(fill="x", padx=12, pady=12)

        initial = self.client.username[0].upper() if self.client.username else "?"
        avatar_lbl = ctk.CTkLabel(
            user_card, text=initial, width=38, height=38, corner_radius=19,
            fg_color="#0284C7", text_color="#FFFFFF",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        avatar_lbl.pack(side="left", padx=10, pady=10)

        user_info_frame = ctk.CTkFrame(user_card, fg_color="transparent")
        user_info_frame.pack(side="left", fill="both", expand=True, pady=10)

        u_name = ctk.CTkLabel(
            user_info_frame, text=self.client.username,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w"
        )
        u_name.pack(fill="x")

        u_ephem = ctk.CTkLabel(
            user_info_frame, text=f"Port: {self.client.local_port} (Ephemeral)",
            font=ctk.CTkFont(size=11), text_color="#94A3B8", anchor="w"
        )
        u_ephem.pack(fill="x")

        # Broadcast Channel Button
        self.btn_broadcast_channel = ctk.CTkButton(
            self.sidebar, text="🌐 General Chat (Broadcast)",
            height=36, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0284C7", hover_color="#0369A1",
            command=self._select_broadcast_channel
        )
        self.btn_broadcast_channel.pack(fill="x", padx=12, pady=(0, 10))

        # Online Users Section Header
        users_hdr = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        users_hdr.pack(fill="x", padx=14, pady=(6, 4))

        self.users_count_label = ctk.CTkLabel(
            users_hdr, text="ONLINE USERS (0)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8"
        )
        self.users_count_label.pack(side="left")

        # Scrollable Online Users List
        self.users_scroll_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", corner_radius=8, height=180
        )
        self.users_scroll_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Network Activity Visualizer Card (Requirement #6)
        activity_card = ctk.CTkFrame(self.sidebar, fg_color="#1E222D", corner_radius=10)
        activity_card.pack(fill="x", padx=12, pady=(4, 12))

        act_title = ctk.CTkLabel(
            activity_card, text="NETWORK ACTIVITY",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#38BDF8"
        )
        act_title.pack(anchor="w", padx=10, pady=(8, 2))

        # Dynamic visual indicator line
        self.act_indicator_label = ctk.CTkLabel(
            activity_card,
            text=f"{self.client.username}  ──►  Server",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#94A3B8"
        )
        self.act_indicator_label.pack(anchor="w", padx=10, pady=(2, 4))

        self.act_status_badge = ctk.CTkLabel(
            activity_card, text="● IDLE (TCP Stream Ready)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#10B981"
        )
        self.act_status_badge.pack(anchor="w", padx=10, pady=(0, 8))

    def _build_chat_center(self, parent):
        """Center chat feed, current channel header, and input area."""
        self.chat_center = ctk.CTkFrame(parent, corner_radius=0, fg_color="#0F1117")
        self.chat_center.pack(side="left", fill="both", expand=True)

        # Channel Banner
        banner_frame = ctk.CTkFrame(self.chat_center, height=44, corner_radius=0, fg_color="#161922")
        banner_frame.pack(fill="x", side="top")
        banner_frame.pack_propagate(False)

        self.channel_title_label = ctk.CTkLabel(
            banner_frame, text="# General Chat",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#E2E8F0"
        )
        self.channel_title_label.pack(side="left", padx=16, pady=10)

        self.channel_desc_label = ctk.CTkLabel(
            banner_frame, text="Broadcast to everyone on TCP port " + str(self.client.port),
            font=ctk.CTkFont(size=12), text_color="#64748B"
        )
        self.channel_desc_label.pack(side="left", padx=8, pady=10)

        # Message Stream (Scrollable Frame)
        self.message_stream = ctk.CTkScrollableFrame(
            self.chat_center, fg_color="#0F1117", corner_radius=0
        )
        self.message_stream.pack(fill="both", expand=True, padx=12, pady=8)

        # Bottom Input Area
        input_container = ctk.CTkFrame(self.chat_center, height=72, corner_radius=0, fg_color="#161922")
        input_container.pack(fill="x", side="bottom")

        # Recipient indicator pill
        self.recipient_pill = ctk.CTkButton(
            input_container, text="To: @Everyone", width=120, height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1E293B", hover_color="#334155",
            command=self._select_broadcast_channel
        )
        self.recipient_pill.pack(side="left", padx=(14, 8), pady=16)

        # Text Entry
        self.msg_entry = ctk.CTkEntry(
            input_container,
            placeholder_text="Type a message or command (/help, /users, /msg <user> <msg>, /ping)...",
            height=42, corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color="#0F1117", border_color="#334155"
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=4, pady=14)
        self.msg_entry.focus()
        self.msg_entry.bind("<Return>", lambda e: self._handle_send_message())

        # Send Button
        self.send_btn = ctk.CTkButton(
            input_container, text="SEND", width=80, height=42, corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0284C7", hover_color="#0369A1",
            command=self._handle_send_message
        )
        self.send_btn.pack(side="right", padx=(8, 14), pady=14)

    def _build_details_panel(self, parent):
        """Right expandable panel: Connection Details & Viva Telemetry Inspector."""
        self.details_panel = ctk.CTkFrame(parent, width=280, corner_radius=0, fg_color="#161922")
        self.details_panel.pack(side="right", fill="y")
        self.details_panel.pack_propagate(False)

        # Panel Header
        hdr = ctk.CTkLabel(
            self.details_panel, text="CONNECTION DETAILS",
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#38BDF8"
        )
        hdr.pack(anchor="w", padx=16, pady=(16, 6))

        sub = ctk.CTkLabel(
            self.details_panel, text="Transport Layer Socket Metrics",
            font=ctk.CTkFont(size=11), text_color="#94A3B8"
        )
        sub.pack(anchor="w", padx=16, pady=(0, 12))

        # Metrics Card
        metrics_box = ctk.CTkFrame(self.details_panel, fg_color="#1E222D", corner_radius=10)
        metrics_box.pack(fill="x", padx=12, pady=4)

        self.telemetry_labels = {}
        rows = [
            ("Protocol", "TCP"),
            ("Socket Type", "SOCK_STREAM"),
            ("Socket Family", "AF_INET (IPv4)"),
            ("Server IP", f"{self.client.host}"),
            ("Server Port", f"{self.client.port}"),
            ("Client Port", f"{self.client.local_port} (Ephemeral)"),
            ("TCP State", "ESTABLISHED"),
            ("Round-Trip (RTT)", "0.0 ms"),
            ("Packets Sent (TX)", "0"),
            ("Packets Recv (RX)", "0"),
            ("Bytes Sent", "0 B"),
            ("Bytes Recv", "0 B"),
        ]

        for key, val in rows:
            row_frame = ctk.CTkFrame(metrics_box, fg_color="transparent")
            row_frame.pack(fill="x", padx=12, pady=3)

            k_lbl = ctk.CTkLabel(
                row_frame, text=key, font=ctk.CTkFont(size=11), text_color="#94A3B8", anchor="w"
            )
            k_lbl.pack(side="left")

            v_lbl = ctk.CTkLabel(
                row_frame, text=val, font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color="#E2E8F0", anchor="e"
            )
            v_lbl.pack(side="right")
            self.telemetry_labels[key] = v_lbl

        # Action Buttons in Details Panel
        btn_box = ctk.CTkFrame(self.details_panel, fg_color="transparent")
        btn_box.pack(fill="x", padx=12, pady=16)

        ping_btn = ctk.CTkButton(
            btn_box, text="⚡ Send TCP Ping", height=32, corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0284C7", hover_color="#0369A1",
            command=self._handle_ping_click
        )
        ping_btn.pack(fill="x", pady=4)

        hist_btn = ctk.CTkButton(
            btn_box, text="📜 View SQLite History", height=32, corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155", hover_color="#475569",
            command=self._open_history_viewer
        )
        hist_btn.pack(fill="x", pady=4)

    def _toggle_details_panel(self):
        """Toggles visibility of the right Connection Details inspection panel."""
        if self.details_visible:
            self.details_panel.pack_forget()
            self.details_visible = False
            self.details_toggle_btn.configure(text="⚡ Show Details")
        else:
            self.details_panel.pack(side="right", fill="y")
            self.details_visible = True
            self.details_toggle_btn.configure(text="⚡ Hide Details")

    # =========================================================================
    # CHAT MESSAGING & RENDERING
    # =========================================================================
    def _handle_send_message(self):
        """Processes user input from entry: commands or chat messages."""
        text = self.msg_entry.get().strip()
        if not text:
            return

        self.msg_entry.delete(0, tk.END)

        # Handle Slash Commands
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Handle Regular Chat Message
        ts = get_current_timestamp()
        if self.current_recipient:
            # Private Direct Message
            target = self.current_recipient
            sent = self.client.send_private(target, text)
            if sent:
                self.storage.save_message(self.client.username, target, "PRIVATE", text, ts)
        else:
            # Broadcast to Everyone
            sent = self.client.send_broadcast(text)
            if sent:
                self.storage.save_message(self.client.username, "EVERYONE", "BROADCAST", text, ts)

        self._update_telemetry_ui()

    def _handle_command(self, cmd_text: str):
        """Executes slash commands such as /help, /users, /msg, /ping, /clear, /quit."""
        parts = cmd_text.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "/help":
            help_msg = (
                "📌 TCP Chat Commands:\n"
                "• /help - Display this command help guide\n"
                "• /users - List all currently connected users\n"
                "• /msg <user> <message> - Send a private unicast message\n"
                "• /ping - Measure TCP round-trip latency (RTT)\n"
                "• /clear - Clear the local message display\n"
                "• /quit - Disconnect and exit cleanly"
            )
            self._render_system_bubble(help_msg, is_info=True)

        elif cmd == "/users":
            users_str = ", ".join(self.online_users) if self.online_users else "None"
            self._render_system_bubble(f"Online Users ({len(self.online_users)}): {users_str}", is_info=True)

        elif cmd == "/msg":
            if len(parts) < 3:
                self._render_system_bubble("Usage: /msg <username> <message>", is_error=True)
                return
            target_user = parts[1]
            private_content = parts[2]
            ts = get_current_timestamp()
            sent = self.client.send_private(target_user, private_content)
            if sent:
                self.storage.save_message(self.client.username, target_user, "PRIVATE", private_content, ts)

        elif cmd == "/ping":
            self.client.send_ping()
            self._render_system_bubble("⚡ Sent TCP PING packet to server...", is_info=True)

        elif cmd == "/clear":
            for widget in self.message_stream.winfo_children():
                widget.destroy()

        elif cmd == "/quit":
            self._handle_manual_disconnect()

        else:
            self._render_system_bubble(f"Unknown command: '{cmd}'. Type /help for available commands.", is_error=True)

    def _on_message_received(self, packet: dict):
        """Thread-safe handler for incoming network packets."""
        self.after(0, lambda: self._process_incoming_packet(packet))

    def _process_incoming_packet(self, packet: dict):
        """Renders packet into the GUI message stream."""
        msg_type = packet.get("type")
        sender = packet.get("sender", "Server")
        text = packet.get("message", "")
        ts = packet.get("timestamp", get_current_timestamp())

        if msg_type == MSG_BROADCAST:
            is_me = (sender == self.client.username)
            self._render_message_bubble(sender, text, ts, is_me=is_me, is_private=False)
            if not is_me:
                self.storage.save_message(sender, "EVERYONE", "BROADCAST", text, ts)

        elif msg_type == MSG_PRIVATE:
            receiver = packet.get("receiver", "")
            is_me = (sender == self.client.username)
            self._render_message_bubble(sender, text, ts, is_me=is_me, is_private=True, target=receiver)
            if not is_me:
                self.storage.save_message(sender, self.client.username, "PRIVATE", text, ts)

        elif msg_type in (MSG_USER_JOIN, MSG_USER_LEAVE, MSG_SYSTEM):
            self._render_system_bubble(text)

        elif msg_type == MSG_ERROR:
            self._render_system_bubble(f"⚠️ {text}", is_error=True)

        self._update_telemetry_ui()

    def _render_message_bubble(self, sender: str, text: str, timestamp: str, is_me: bool, is_private: bool, target: str = ""):
        """Renders modern styled message bubbles with avatars and timestamps."""
        row_frame = ctk.CTkFrame(self.message_stream, fg_color="transparent")
        row_frame.pack(fill="x", pady=6)

        bubble_container = ctk.CTkFrame(row_frame, fg_color="transparent")
        if is_me:
            bubble_container.pack(side="right", padx=10)
        else:
            bubble_container.pack(side="left", padx=10)

        # Header info above bubble
        hdr_frame = ctk.CTkFrame(bubble_container, fg_color="transparent")
        hdr_frame.pack(fill="x", pady=(0, 2))

        if is_me:
            tag_text = "You"
            if is_private:
                tag_text += f" ──► @{target} [PRIVATE]"
            hdr_lbl = ctk.CTkLabel(
                hdr_frame, text=tag_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#93C5FD" if not is_private else "#F472B6"
            )
            hdr_lbl.pack(side="right")
        else:
            # Avatar circle
            initial = sender[0].upper() if sender else "?"
            av_lbl = ctk.CTkLabel(
                hdr_frame, text=initial, width=22, height=22, corner_radius=11,
                fg_color="#0284C7" if not is_private else "#9333EA",
                text_color="#FFFFFF", font=ctk.CTkFont(size=11, weight="bold")
            )
            av_lbl.pack(side="left", padx=(0, 6))

            tag_text = sender
            if is_private:
                tag_text += " [DIRECT MESSAGE]"
            hdr_lbl = ctk.CTkLabel(
                hdr_frame, text=tag_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#38BDF8" if not is_private else "#C084FC"
            )
            hdr_lbl.pack(side="left")

        # The actual message bubble card
        bubble_bg = "#1D4ED8" if is_me else "#1E293B"
        if is_private:
            bubble_bg = "#4C1D95" if is_me else "#581C87"

        bubble = ctk.CTkFrame(bubble_container, fg_color=bubble_bg, corner_radius=12)
        bubble.pack(anchor="e" if is_me else "w")

        msg_lbl = ctk.CTkLabel(
            bubble, text=text,
            font=ctk.CTkFont(size=13),
            text_color="#FFFFFF",
            wraplength=520, justify="left"
        )
        msg_lbl.pack(padx=14, pady=8, anchor="w")

        # Timestamp footer
        ts_lbl = ctk.CTkLabel(
            bubble_container, text=timestamp,
            font=ctk.CTkFont(size=10), text_color="#64748B"
        )
        ts_lbl.pack(anchor="e" if is_me else "w", padx=4, pady=(1, 0))

        # Auto-scroll to latest message
        self.after(20, self._scroll_to_bottom)

    def _render_system_bubble(self, message: str, is_error: bool = False, is_info: bool = False):
        """Renders subtle system/network notification pill in center."""
        pill_frame = ctk.CTkFrame(self.message_stream, fg_color="transparent")
        pill_frame.pack(fill="x", pady=6)

        color = "#EF4444" if is_error else ("#38BDF8" if is_info else "#94A3B8")
        bg = "#450A0A" if is_error else ("#0C4A6E" if is_info else "#181B20")

        pill = ctk.CTkLabel(
            pill_frame, text=f"  {message}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=color, fg_color=bg, corner_radius=12
        )
        pill.pack(anchor="center")
        self.after(20, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scrolls message stream to latest entry."""
        try:
            self.message_stream._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # =========================================================================
    # ONLINE USERS & RECIPIENT SELECTION
    # =========================================================================
    def _on_user_list_updated(self, users: List[str]):
        """Callback triggered when active user list changes."""
        self.after(0, lambda: self._update_users_ui(users))

    def _update_users_ui(self, users: List[str]):
        """Rebuilds online users widget list."""
        self.online_users = users
        self.users_count_label.configure(text=f"ONLINE USERS ({len(users)})")

        for widget in self.users_scroll_frame.winfo_children():
            widget.destroy()

        for user in users:
            is_self = (user == self.client.username)
            item_frame = ctk.CTkFrame(self.users_scroll_frame, fg_color="#1E222D", corner_radius=8, height=36)
            item_frame.pack(fill="x", pady=3)
            item_frame.pack_propagate(False)

            # Green online indicator
            dot = ctk.CTkLabel(item_frame, text="🟢", font=ctk.CTkFont(size=10))
            dot.pack(side="left", padx=(8, 4))

            # User initial avatar
            initial = user[0].upper()
            av = ctk.CTkLabel(
                item_frame, text=initial, width=22, height=22, corner_radius=11,
                fg_color="#0284C7" if is_self else "#475569",
                text_color="#FFFFFF", font=ctk.CTkFont(size=10, weight="bold")
            )
            av.pack(side="left", padx=4)

            # Name label
            display_name = f"{user} (You)" if is_self else user
            name_lbl = ctk.CTkLabel(
                item_frame, text=display_name,
                font=ctk.CTkFont(size=12, weight="bold" if is_self else "normal"),
                anchor="w"
            )
            name_lbl.pack(side="left", padx=6, fill="x", expand=True)

            # Click to Private Message button (if not self)
            if not is_self:
                msg_btn = ctk.CTkButton(
                    item_frame, text="Chat", width=46, height=24, corner_radius=6,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color="#334155", hover_color="#0284C7",
                    command=lambda u=user: self._select_private_recipient(u)
                )
                msg_btn.pack(side="right", padx=6)

    def _select_private_recipient(self, user: str):
        """Sets target chat mode to Unicast (Private Message)."""
        self.current_recipient = user
        self.channel_title_label.configure(text=f"🔒 Direct Message: @{user}")
        self.channel_desc_label.configure(text="Private unicast socket routing to " + user)
        self.recipient_pill.configure(
            text=f"To: @{user} (DM)",
            fg_color="#7C3AED", hover_color="#6D28D9"
        )
        self.msg_entry.focus()

    def _select_broadcast_channel(self):
        """Resets target chat mode to Broadcast (General)."""
        self.current_recipient = None
        self.channel_title_label.configure(text="# General Chat")
        self.channel_desc_label.configure(text="Broadcast to everyone on TCP port " + str(self.client.port))
        self.recipient_pill.configure(
            text="To: @Everyone",
            fg_color="#1E293B", hover_color="#334155"
        )
        self.msg_entry.focus()

    # =========================================================================
    # NETWORK ACTIVITY & TELEMETRY
    # =========================================================================
    def _on_network_activity(self, direction: str, description: str):
        """Visual pulse for transmitted / received TCP packets."""
        self.after(0, lambda: self._animate_activity(direction, description))

    def _animate_activity(self, direction: str, description: str):
        """Updates network activity indicator widget dynamically."""
        if direction == "TX":
            self.act_indicator_label.configure(text=f"{self.client.username} ──────► Server", text_color="#38BDF8")
            self.act_status_badge.configure(text="● TRANSMITTING (TX Packet)", text_color="#38BDF8")
        else:
            self.act_indicator_label.configure(text=f"Server ──────► {self.client.username}", text_color="#34D399")
            self.act_status_badge.configure(text="● RECEIVING (RX Packet)", text_color="#34D399")

        # Reset indicator after 1.2 seconds of inactivity
        if self.activity_timer_id:
            self.after_cancel(self.activity_timer_id)
        self.activity_timer_id = self.after(1200, self._reset_activity_indicator)

    def _reset_activity_indicator(self):
        """Restores idle state on network activity widget."""
        self.act_indicator_label.configure(text=f"{self.client.username}  ──►  Server", text_color="#94A3B8")
        self.act_status_badge.configure(text="● IDLE (TCP Stream Ready)", text_color="#10B981")

    def _handle_ping_click(self):
        """User clicked 'Send TCP Ping' button."""
        self.client.send_ping()
        self._update_telemetry_ui()

    def _on_rtt_updated(self, rtt_ms: float):
        """Callback when PONG is received."""
        self.after(0, lambda: self._update_telemetry_ui())

    def _periodic_telemetry(self):
        """Refreshes telemetry panel every 3 seconds."""
        if self.client.connected:
            self._update_telemetry_ui()
            self.after(3000, self._periodic_telemetry)

    def _update_telemetry_ui(self):
        """Updates the labels in the Connection Details panel."""
        if not self.client.connected:
            return

        def fmt_bytes(b):
            if b < 1024:
                return f"{b} B"
            return f"{round(b / 1024, 2)} KB"

        updates = {
            "Packets Sent (TX)": str(self.client.packets_sent),
            "Packets Recv (RX)": str(self.client.packets_received),
            "Bytes Sent": fmt_bytes(self.client.bytes_sent),
            "Bytes Recv": fmt_bytes(self.client.bytes_received),
            "Round-Trip (RTT)": f"{self.client.last_rtt_ms} ms",
            "Client Port": f"{self.client.local_port} (Ephemeral)",
            "TCP State": "ESTABLISHED" if self.client.connected else "CLOSED"
        }

        for key, val in updates.items():
            if key in self.telemetry_labels:
                self.telemetry_labels[key].configure(text=val)

    # =========================================================================
    # SQLITE HISTORY VIEWER MODAL
    # =========================================================================
    def _load_local_history_preview(self):
        """Optionally loads recent messages from SQLite database on startup."""
        recent = self.storage.get_recent_messages(limit=10)
        if recent:
            self._render_system_bubble("📜 Loaded recent message history from local SQLite database", is_info=True)
            for m in recent:
                sender = m.get("sender")
                is_me = (sender == self.client.username)
                is_private = (m.get("type") == "PRIVATE")
                self._render_message_bubble(
                    sender, m.get("message"), m.get("timestamp"),
                    is_me=is_me, is_private=is_private, target=m.get("receiver", "")
                )

    def _open_history_viewer(self):
        """Opens a modal window showing SQLite chat history table."""
        modal = ctk.CTkToplevel(self)
        modal.title("SQLite Local Chat History")
        modal.geometry("640, 480")
        modal.minsize(500, 350)
        modal.grab_set()

        hdr = ctk.CTkLabel(
            modal, text="Local SQLite Message Storage (chat_history.db)",
            font=ctk.CTkFont(size=15, weight="bold"), text_color="#38BDF8"
        )
        hdr.pack(pady=12)

        scroll = ctk.CTkScrollableFrame(modal, fg_color="#181B20", corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        messages = self.storage.get_recent_messages(limit=100)
        if not messages:
            empty_lbl = ctk.CTkLabel(scroll, text="No saved messages found in SQLite database.", text_color="#94A3B8")
            empty_lbl.pack(pady=40)
        else:
            for row in messages:
                card = ctk.CTkFrame(scroll, fg_color="#1E222D", corner_radius=6)
                card.pack(fill="x", pady=3)

                info_txt = f"[{row['timestamp']}] ({row['type']}) {row['sender']} ──► {row['receiver']}"
                info_lbl = ctk.CTkLabel(card, text=info_txt, font=ctk.CTkFont(size=11, weight="bold"), text_color="#93C5FD")
                info_lbl.pack(anchor="w", padx=10, pady=(4, 1))

                msg_lbl = ctk.CTkLabel(card, text=row['message'], font=ctk.CTkFont(size=12), text_color="#E2E8F0", wraplength=540, justify="left")
                msg_lbl.pack(anchor="w", padx=10, pady=(1, 4))

        # Bottom clear history button
        btn_bar = ctk.CTkFrame(modal, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=12)

        def clear_action():
            self.storage.clear_history()
            modal.destroy()
            messagebox.showinfo("History Cleared", "Local SQLite chat history has been cleared.")

        clr_btn = ctk.CTkButton(
            btn_bar, text="Clear SQLite Database", fg_color="#991B1B", hover_color="#B91C1C",
            command=clear_action
        )
        clr_btn.pack(side="left")

        close_btn = ctk.CTkButton(btn_bar, text="Close", command=modal.destroy)
        close_btn.pack(side="right")

    # =========================================================================
    # DISCONNECTION & CLEANUP
    # =========================================================================
    def _on_disconnected(self, reason: str):
        """Callback when connection to server drops."""
        self.after(0, lambda: self._handle_server_disconnect_ui(reason))

    def _handle_server_disconnect_ui(self, reason: str):
        """Displays disconnected banner and disables inputs."""
        if hasattr(self, "status_badge"):
            self.status_badge.configure(
                text="  ○ DISCONNECTED  ", text_color="#EF4444", fg_color="#450A0A"
            )
        self._render_system_bubble(f"Connection lost: {reason}", is_error=True)
        if hasattr(self, "msg_entry"):
            self.msg_entry.configure(state="disabled")
        if hasattr(self, "send_btn"):
            self.send_btn.configure(state="disabled")

    def _handle_manual_disconnect(self):
        """User manually clicked disconnect."""
        self.client.disconnect()
        self._show_login_screen()

    def _on_closing(self):
        """Clean window closure handling."""
        self.client.disconnect()
        self.destroy()

def main():
    app = ChatGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
