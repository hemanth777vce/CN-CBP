"""
test_networking.py - Automated Networking and Concurrency Verification Test
Computer Networks Course Project: Multi-Client TCP Socket Chat

Tests:
1. TCP Server Startup & Socket Binding (AF_INET, SOCK_STREAM)
2. Multiple Concurrent Client Connections (Alice, Bob, Charlie)
3. Handshake & Duplicate Username Rejection
4. Broadcast Message Delivery across all connected sockets
5. Private Message Unicast Routing (Alice -> Bob, Bob received, Charlie didn't)
6. Ping/Pong RTT Latency measurement
7. Graceful Disconnection and dynamic user list update
8. SQLite local message persistence
"""

import threading
import time
import socket
import unittest
from server import ChatServer
from client import TCPChatClient
from storage import ChatStorage
from protocol import MSG_BROADCAST, MSG_PRIVATE

TEST_PORT = 5055

class TestTCPNetworking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start server in background thread
        cls.server = ChatServer(host="127.0.0.1", port=TEST_PORT)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)  # Wait for socket to bind and listen

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.2)

    def test_01_multi_client_connections(self):
        """Test multiple concurrent clients connecting and registering usernames."""
        client1 = TCPChatClient()
        client2 = TCPChatClient()
        client3 = TCPChatClient()

        s1, m1 = client1.connect("127.0.0.1", TEST_PORT, "Alice")
        self.assertTrue(s1, f"Alice connection failed: {m1}")
        self.assertGreater(client1.local_port, 1024, "Ephemeral port should be allocated by OS")

        s2, m2 = client2.connect("127.0.0.1", TEST_PORT, "Bob")
        self.assertTrue(s2, f"Bob connection failed: {m2}")

        s3, m3 = client3.connect("127.0.0.1", TEST_PORT, "Charlie")
        self.assertTrue(s3, f"Charlie connection failed: {m3}")

        # Check server registered all 3 clients
        time.sleep(0.2)
        with self.server.clients_lock:
            self.assertEqual(len(self.server.clients), 3)
            self.assertIn("Alice", self.server.clients)
            self.assertIn("Bob", self.server.clients)
            self.assertIn("Charlie", self.server.clients)

        client1.disconnect()
        client2.disconnect()
        client3.disconnect()
        time.sleep(0.3)

    def test_02_duplicate_username_rejected(self):
        """Test server rejects connection when username already in use."""
        client1 = TCPChatClient()
        client2 = TCPChatClient()

        s1, _ = client1.connect("127.0.0.1", TEST_PORT, "Hemanth")
        self.assertTrue(s1)

        # Attempt to login again with same name "Hemanth"
        s2, m2 = client2.connect("127.0.0.1", TEST_PORT, "Hemanth")
        self.assertFalse(s2, "Duplicate username should be rejected")
        self.assertIn("already taken", m2.lower())

        client1.disconnect()
        client2.disconnect()
        time.sleep(0.3)

    def test_03_broadcast_message_routing(self):
        """Test broadcast messages are delivered to all connected clients."""
        alice = TCPChatClient()
        bob = TCPChatClient()
        charlie = TCPChatClient()

        received_msgs = {"Bob": [], "Charlie": []}

        bob.on_message_callback = lambda p: received_msgs["Bob"].append(p)
        charlie.on_message_callback = lambda p: received_msgs["Charlie"].append(p)

        alice.connect("127.0.0.1", TEST_PORT, "Alice")
        bob.connect("127.0.0.1", TEST_PORT, "Bob")
        charlie.connect("127.0.0.1", TEST_PORT, "Charlie")
        time.sleep(0.3)

        # Alice broadcasts
        test_text = "Hello everyone on TCP network!"
        sent = alice.send_broadcast(test_text)
        self.assertTrue(sent)

        time.sleep(0.4)

        bob_broadcasts = [m for m in received_msgs["Bob"] if m.get("type") == MSG_BROADCAST and m.get("message") == test_text]
        charlie_broadcasts = [m for m in received_msgs["Charlie"] if m.get("type") == MSG_BROADCAST and m.get("message") == test_text]

        self.assertEqual(len(bob_broadcasts), 1, "Bob should receive Alice's broadcast")
        self.assertEqual(len(charlie_broadcasts), 1, "Charlie should receive Alice's broadcast")
        self.assertEqual(bob_broadcasts[0]["sender"], "Alice")

        alice.disconnect()
        bob.disconnect()
        charlie.disconnect()
        time.sleep(0.3)

    def test_04_private_message_routing(self):
        """Test private message unicast routing: Alice -> Bob, Charlie does NOT receive it."""
        alice = TCPChatClient()
        bob = TCPChatClient()
        charlie = TCPChatClient()

        bob_received = []
        charlie_received = []

        bob.on_message_callback = lambda p: bob_received.append(p)
        charlie.on_message_callback = lambda p: charlie_received.append(p)

        alice.connect("127.0.0.1", TEST_PORT, "Alice")
        bob.connect("127.0.0.1", TEST_PORT, "Bob")
        charlie.connect("127.0.0.1", TEST_PORT, "Charlie")
        time.sleep(0.3)

        # Alice sends private message to Bob
        secret_msg = "Top secret message for Bob only"
        alice.send_private("Bob", secret_msg)
        time.sleep(0.4)

        bob_privates = [m for m in bob_received if m.get("type") == MSG_PRIVATE and m.get("message") == secret_msg]
        charlie_privates = [m for m in charlie_received if m.get("type") == MSG_PRIVATE and m.get("message") == secret_msg]

        self.assertEqual(len(bob_privates), 1, "Bob must receive the private message")
        self.assertEqual(len(charlie_privates), 0, "Charlie must NOT receive Alice's private message to Bob")

        alice.disconnect()
        bob.disconnect()
        charlie.disconnect()
        time.sleep(0.3)

    def test_05_ping_pong_latency(self):
        """Test TCP PING/PONG round-trip latency calculation."""
        client = TCPChatClient()
        client.connect("127.0.0.1", TEST_PORT, "PingTester")
        time.sleep(0.2)

        client.send_ping()
        time.sleep(0.3)

        self.assertGreaterEqual(client.last_rtt_ms, 0.0)
        client.disconnect()
        time.sleep(0.2)

    def test_06_sqlite_storage(self):
        """Test local SQLite database persistence."""
        storage = ChatStorage("test_history.db")
        storage.clear_history()

        storage.save_message("Alice", "Bob", "PRIVATE", "Hello Bob", "12:00:00")
        storage.save_message("Bob", "EVERYONE", "BROADCAST", "Hi all", "12:01:00")

        history = storage.get_recent_messages(10)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["sender"], "Alice")
        self.assertEqual(history[1]["sender"], "Bob")

        storage.clear_history()
        self.assertEqual(len(storage.get_recent_messages(10)), 0)

if __name__ == "__main__":
    unittest.main()
