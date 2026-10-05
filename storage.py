"""
storage.py - SQLite Local Message Persistence
Stores chat history locally on the client machine for inspection and offline review.
Focus is kept lightweight so TCP networking remains the primary project focus.
"""

import sqlite3
import os
from typing import List, Dict

DB_PATH = "chat_history.db"

class ChatStorage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes database schema if not already created."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    msg_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_message(self, sender: str, receiver: str, msg_type: str, content: str, timestamp: str):
        """Saves a message record into the local SQLite database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages (sender, receiver, msg_type, content, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (sender, receiver, msg_type, content, timestamp))
                conn.commit()
        except sqlite3.Error as e:
            print(f"[Storage Error] Failed to persist message: {e}")

    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """Fetches recent messages from local database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sender, receiver, msg_type, content, timestamp
                    FROM messages
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                # Return in chronological order
                results = []
                for row in reversed(rows):
                    results.append({
                        "sender": row[0],
                        "receiver": row[1],
                        "type": row[2],
                        "message": row[3],
                        "timestamp": row[4]
                    })
                return results
        except sqlite3.Error as e:
            print(f"[Storage Error] Failed to query messages: {e}")
            return []

    def clear_history(self):
        """Clears local chat history database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM messages")
                conn.commit()
        except sqlite3.Error as e:
            print(f"[Storage Error] Failed to clear messages: {e}")
