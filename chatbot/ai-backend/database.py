"""
database.py -- Versi PostgreSQL 17
Migrasi dari SQLite ke PostgreSQL.
Semua fungsi dan signature tetap sama persis agar main.py & access.py tidak perlu diubah.
"""
import os
import uuid
import secrets
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

# =========================================================
# KONFIGURASI KONEKSI POSTGRESQL
# =========================================================
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB   = os.getenv("PG_DB", "chatbot")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "77882022")


def get_db_connection():
    """Membuat koneksi ke PostgreSQL dan mengembalikan conn dengan cursor dict-like."""
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS
    )
    conn.autocommit = False
    return conn


def _dict_row(cursor, row):
    """Convert a row to a dict using cursor.description."""
    if row is None:
        return None
    return {col.name: val for col, val in zip(cursor.description, row)}


def _fetchone_dict(cursor):
    row = cursor.fetchone()
    return _dict_row(cursor, row)


def _fetchall_dict(cursor):
    rows = cursor.fetchall()
    return [_dict_row(cursor, r) for r in rows]


def init_db():
    """Membuat tabel jika belum ada dan seed data default."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL,
        api_key TEXT UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        token TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        client_id INTEGER,
        email TEXT,
        password_changed INTEGER DEFAULT 0,
        last_login TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        client_id INTEGER,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE SET NULL
    )
    """)

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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        client_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        upload_date TEXT NOT NULL,
        FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
    )
    """)

    conn.commit()

    # Seed default clients & users if tables are empty
    cursor.execute("SELECT COUNT(*) FROM clients")
    count = cursor.fetchone()[0]
    if count == 0:
        clients = [
            ("Bank DKI", "Bank", "rc_live_bank_dki_8a9b2c"),
            ("Universitas Gunadarma", "Campus", "rc_live_gunadarma_89327f"),
            ("Universitas Pamulang", "Campus", "rc_live_unpam_3d4e5f"),
            ("Universitas Budi Luhur", "Campus", "rc_live_budi_luhur_6a7b8c"),
            ("warung makan", "General", "rc_live_warung_makan_1e2f3d")
        ]
        for name, ctype, api_key in clients:
            cursor.execute(
                "INSERT INTO clients (name, type, api_key) VALUES (%s, %s, %s)",
                (name, ctype, api_key)
            )
        conn.commit()

        cursor.execute("SELECT id, name FROM clients")
        client_map = {row[1]: row[0] for row in cursor.fetchall()}

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_users = [
            ("admin", "admin123", "token-admin", "admin", None, "admin@chatbot.com", 1, now_str, 1),
            ("Budi Santoso", "client123", "token-budi", "admin_client", client_map["Universitas Gunadarma"], "budi@gunadarma.go.id", 0, now_str, 1),
            ("Siti Rahma", "client123", "token-siti", "admin_client", client_map["Universitas Pamulang"], "siti@unpam.go.id", 0, now_str, 1),
            ("Andi Wijaya", "client123", "token-andi", "admin_client", client_map["Universitas Budi Luhur"], "andi@budiluhur.go.id", 0, now_str, 1),
            ("Andi Rijani", "client123", "token-rijani", "admin_client", client_map["Bank DKI"], "Rijani16@instansi.go.id", 0, now_str, 1),
            ("Wijaya", "client123", "token-wijaya", "admin_client", client_map["warung makan"], "Wijaya45@gmail.com", 0, now_str, 1),
            ("user", "user123", "token-user", "user", None, "user@gmail.com", 1, now_str, 1)
        ]
        for u in default_users:
            cursor.execute(
                "INSERT INTO users (username, password, token, role, client_id, email, password_changed, last_login, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                u
            )
        conn.commit()
        print("Default clients and users seeded successfully.")

    cursor.close()
    conn.close()

# Initialize DB on import
init_db()


# --- CLIENT HELPER FUNCTIONS ---
def get_all_clients():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY name ASC")
    clients = _fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return clients

def add_client(name: str, type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    slug = "".join([c if c.isalnum() else "_" for c in name.lower()])
    random_hex = secrets.token_hex(6)
    api_key = f"rc_live_{slug}_{random_hex}"
    try:
        cursor.execute(
            "INSERT INTO clients (name, type, api_key) VALUES (%s, %s, %s) RETURNING id",
            (name, type, api_key)
        )
        client_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return {"id": client_id, "name": name, "type": type, "api_key": api_key}
    except psycopg2.IntegrityError as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise Exception(f"Client name already exists. {str(e)}")

def delete_client(client_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def get_client_by_api_key(api_key: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE api_key = %s", (api_key,))
    client = _fetchone_dict(cursor)
    cursor.close()
    conn.close()
    return client

def generate_client_api_key(client_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM clients WHERE id = %s", (client_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        raise Exception("Client tidak ditemukan.")

    client_name = row[0]
    slug = "".join([c if c.isalnum() else "_" for c in client_name.lower()])
    random_hex = secrets.token_hex(6)
    new_key = f"rc_live_{slug}_{random_hex}"

    cursor.execute("UPDATE clients SET api_key = %s WHERE id = %s", (new_key, client_id))
    conn.commit()
    cursor.close()
    conn.close()
    return new_key


# --- USER HELPER FUNCTIONS ---
def get_user_by_token(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, c.name as client_name
        FROM users u
        LEFT JOIN clients c ON u.client_id = c.id
        WHERE u.token = %s
    """, (token,))
    user = _fetchone_dict(cursor)
    cursor.close()
    conn.close()
    return user

def check_and_deactivate_inactive_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Nonaktifkan akun hanya jika tidak login lebih dari 30 hari (bukan 7 hari)
    cutoff = datetime.now() - timedelta(days=30)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE users
        SET is_active = 0
        WHERE last_login IS NOT NULL
          AND last_login < %s
          AND role != 'admin'
    """, (cutoff_str,))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_by_credentials(username: str, password: str):
    check_and_deactivate_inactive_users()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, c.name as client_name
        FROM users u
        LEFT JOIN clients c ON u.client_id = c.id
        WHERE u.username = %s AND u.password = %s
    """, (username, password))
    user = _fetchone_dict(cursor)
    if user:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Saat user berhasil login dengan kredensial benar, aktifkan kembali statusnya dan update last_login
        cursor.execute("UPDATE users SET is_active = 1, last_login = %s WHERE id = %s", (now_str, user["id"]))
        conn.commit()
        user["last_login"] = now_str
        user["is_active"] = 1
        cursor.close()
        conn.close()
        return user
    cursor.close()
    conn.close()
    return None

def get_all_users():
    check_and_deactivate_inactive_users()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.password, u.token, u.role, u.client_id, u.email,
               u.password_changed, u.last_login, u.is_active,
               c.name as client_name, c.type as client_type, c.api_key as client_api_key
        FROM users u
        LEFT JOIN clients c ON u.client_id = c.id
    """)
    users = _fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return users

def add_user(username: str, password: str, role: str, client_id: int = None, email: str = None, password_changed: int = 0):
    conn = get_db_connection()
    cursor = conn.cursor()
    token = uuid.uuid4().hex
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            "INSERT INTO users (username, password, token, role, client_id, email, password_changed, last_login, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1) RETURNING id",
            (username, password, token, role, client_id, email, password_changed, now_str)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return {"id": user_id, "username": username, "token": token, "role": role, "client_id": client_id, "email": email, "password_changed": password_changed, "last_login": now_str, "is_active": 1}
    except psycopg2.IntegrityError as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise Exception(f"Username already exists. {str(e)}")

def update_client_instansi(user_id: int, username: str, instansi_name: str, client_type: str, password: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT client_id FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            raise Exception("User tidak ditemukan.")
        client_id = row[0]

        if client_id is not None:
            cursor.execute("UPDATE clients SET name = %s, type = %s WHERE id = %s", (instansi_name, client_type, client_id))

        if password:
            cursor.execute("UPDATE users SET username = %s, password = %s, password_changed = 0 WHERE id = %s", (username, password, user_id))
        else:
            cursor.execute("UPDATE users SET username = %s WHERE id = %s", (username, user_id))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

def update_user_password(user_id: int, new_password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s, password_changed = 1 WHERE id = %s", (new_password, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def delete_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def set_user_status(user_id: int, is_active: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (is_active, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def activate_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET is_active = 1, last_login = %s", (now_str,))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def get_document_by_id(doc_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
    doc = _fetchone_dict(cursor)
    cursor.close()
    conn.close()
    return doc


# --- DOCUMENT HELPER FUNCTIONS ---
def get_documents_by_client(client_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE client_id = %s ORDER BY upload_date DESC", (client_id,))
    docs = _fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return docs

def add_document(client_id: int, filename: str, doc_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO documents (client_id, filename, doc_type, upload_date) VALUES (%s, %s, %s, %s) RETURNING id",
        (client_id, filename, doc_type, upload_date)
    )
    doc_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return {"id": doc_id, "client_id": client_id, "filename": filename, "doc_type": doc_type, "upload_date": upload_date}

def delete_document(doc_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
    row = cursor.fetchone()
    if row:
        filename = row[0]
        cursor.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return filename
    cursor.close()
    conn.close()
    return None


# --- CHAT SESSION HELPER FUNCTIONS ---
def create_chat_session(user_id: int, client_id: int = None, title: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    session_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_sessions (id, user_id, client_id, title, created_at) VALUES (%s, %s, %s, %s, %s)",
        (session_id, user_id, client_id, title, created_at)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"id": session_id, "user_id": user_id, "client_id": client_id, "title": title, "created_at": created_at}

def get_chat_sessions(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, c.name as client_name
        FROM chat_sessions s
        LEFT JOIN clients c ON s.client_id = c.id
        WHERE s.user_id = %s
        ORDER BY s.created_at DESC
    """, (user_id,))
    sessions = _fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return sessions

def get_chat_messages(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE session_id = %s ORDER BY timestamp ASC",
        (session_id,)
    )
    messages = _fetchall_dict(cursor)
    cursor.close()
    conn.close()
    return messages

def save_message(session_id: str, role: str, content: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (%s, %s, %s, %s, %s)",
        (msg_id, session_id, role, content, timestamp)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "timestamp": timestamp}

def delete_chat_session(session_id: str, user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return False
    cursor.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return True
