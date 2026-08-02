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
    
    # Check if we need to migrate/recreate (if old db exists without admin user)
    recreate = False
    try:
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            recreate = True
    except sqlite3.OperationalError:
        recreate = True
        
    if recreate:
        print("Recreating database to support Multi-Client architecture...")
        cursor.execute("DROP TABLE IF EXISTS documents")
        cursor.execute("DROP TABLE IF EXISTS messages")
        cursor.execute("DROP TABLE IF EXISTS chat_sessions")
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS clients")
        conn.commit()
    
    # Create clients table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL -- 'Perbankan', 'Kampus', 'Umum'
    )
    """)

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL, -- 'superadmin', 'admin', 'admin_client', 'user'
        client_id INTEGER,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE SET NULL
    )
    """)
    
    # Create chat sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        client_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
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

    # Create documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        doc_type TEXT NOT NULL, -- 'PDF', 'GAMBAR', 'VIDEO'
        upload_date TEXT NOT NULL,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
    )
    """)
    
    # Seed default clients & users if tables are empty
    cursor.execute("SELECT COUNT(*) as count FROM clients")
    if cursor.fetchone()["count"] == 0:
        clients = [
            ("BANK DKI", "Perbankan"),
            ("BANK BNI", "Perbankan"),
            ("Gunadarma", "Kampus")
        ]
        cursor.executemany(
            "INSERT INTO clients (name, type) VALUES (?, ?)",
            clients
        )
        conn.commit()

        # Get client IDs
        cursor.execute("SELECT id, name FROM clients")
        client_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        default_users = [
            ("admin", "admin123", "token-admin", "superadmin", None), # admin acts as superadmin/global admin
            ("adminclient", "client123", "token-client", "admin_client", client_map["BANK DKI"]),
            ("user", "user123", "token-user", "user", None)
        ]
        cursor.executemany(
            "INSERT INTO users (username, password, token, role, client_id) VALUES (?, ?, ?, ?, ?)",
            default_users
        )
        conn.commit()
        print("Default clients and users seeded successfully.")
        
    conn.close()

# Initialize DB on import
init_db()

# --- CLIENT HELPER FUNCTIONS ---
def get_all_clients():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY name ASC")
    clients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return clients

def add_client(name: str, type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO clients (name, type) VALUES (?, ?)", (name, type))
        conn.commit()
        client_id = cursor.lastrowid
        conn.close()
        return {"id": client_id, "name": name, "type": type}
    except sqlite3.IntegrityError as e:
        conn.close()
        raise Exception(f"Client name already exists. {str(e)}")

def delete_client(client_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()
    return True

# --- USER HELPER FUNCTIONS ---
def get_user_by_token(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, c.name as client_name 
        FROM users u 
        LEFT JOIN clients c ON u.client_id = c.id 
        WHERE u.token = ?
    """, (token,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def get_user_by_credentials(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, c.name as client_name 
        FROM users u 
        LEFT JOIN clients c ON u.client_id = c.id 
        WHERE u.username = ? AND u.password = ?
    """, (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.password, u.token, u.role, u.client_id, c.name as client_name 
        FROM users u
        LEFT JOIN clients c ON u.client_id = c.id
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def add_user(username: str, password: str, role: str, client_id: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    token = uuid.uuid4().hex
    try:
        cursor.execute("INSERT INTO users (username, password, token, role, client_id) VALUES (?, ?, ?, ?, ?)", 
                       (username, password, token, role, client_id))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return {"id": user_id, "username": username, "token": token, "role": role, "client_id": client_id}
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

# --- DOCUMENT HELPER FUNCTIONS ---
def get_documents_by_client(client_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE client_id = ? ORDER BY upload_date DESC", (client_id,))
    docs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return docs

def add_document(client_id: int, filename: str, doc_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO documents (client_id, filename, doc_type, upload_date) VALUES (?, ?, ?, ?)",
        (client_id, filename, doc_type, upload_date)
    )
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    return {"id": doc_id, "client_id": client_id, "filename": filename, "doc_type": doc_type, "upload_date": upload_date}

def delete_document(doc_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    if doc:
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        return doc["filename"]
    conn.close()
    return None

# --- CHAT SESSION HELPER FUNCTIONS ---
def create_chat_session(user_id: int, client_id: int, title: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_sessions (id, user_id, client_id, title, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, user_id, client_id, title, created_at)
    )
    conn.commit()
    conn.close()
    return {"id": session_id, "user_id": user_id, "client_id": client_id, "title": title, "created_at": created_at}

def get_chat_sessions(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, c.name as client_name 
        FROM chat_sessions s
        JOIN clients c ON s.client_id = c.id
        WHERE s.user_id = ? 
        ORDER BY s.created_at DESC
    """, (user_id,))
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
