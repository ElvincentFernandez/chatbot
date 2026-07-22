import sqlite3
import os
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatbot.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if we need to migration/recreate (if old db exists without password column)
    recreate = False
    try:
        cursor.execute("SELECT password FROM users LIMIT 1")
    except sqlite3.OperationalError:
        recreate = True
        
    if recreate:
        print("Migrating/recreating database to support password authentication...")
        cursor.execute("DROP TABLE IF EXISTS messages")
        cursor.execute("DROP TABLE IF EXISTS chat_sessions")
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL
    )
    """)
    
    # Create chat sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    
    # Create messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
    )
    """)
    
    # Seed default users if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0:
        default_users = [
            ("superadmin", "super123", "token-super", "superadmin"),
            ("admin", "admin123", "token-admin", "admin"),
            ("user", "user123", "token-user", "user")
        ]
        cursor.executemany(
            "INSERT INTO users (username, password, token, role) VALUES (?, ?, ?, ?)",
            default_users
        )
        conn.commit()
        print("Default users with passwords seeded.")
        
    conn.close()

# Initialize DB on import
init_db()

# Helper functions
def get_user_by_token(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def get_user_by_credentials(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, token, role FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def add_user(username: str, password: str, role: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    token = uuid.uuid4().hex
    try:
        cursor.execute("INSERT INTO users (username, password, token, role) VALUES (?, ?, ?, ?)", 
                       (username, password, token, role))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {"id": user_id, "username": username, "token": token, "role": role}
    except sqlite3.IntegrityError as e:
        conn.close()
        raise Exception(f"Username already exists. {str(e)}")

def delete_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def create_chat_session(user_id: int, title: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_sessions (id, user_id, title, created_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, title, created_at)
    )
    conn.commit()
    conn.close()
    return {"id": session_id, "user_id": user_id, "title": title, "created_at": created_at}

def get_chat_sessions(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions

def get_chat_messages(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,)
    )
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages

def save_message(session_id: str, role: str, content: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (msg_id, session_id, role, content, timestamp)
    )
    conn.commit()
    conn.close()
    return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "timestamp": timestamp}

def delete_chat_session(session_id: str, user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return False
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return True
