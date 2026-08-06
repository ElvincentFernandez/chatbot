"""
config.py -- Parameter konfigurasi dan system prompt untuk RAG engine.
"""
import os

# Model & Storage Paths
MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3.5-2B-UD-Q4_K_XL.gguf")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
PARENT_STORE_DIR = os.getenv("PARENT_STORE_DIR", "./parent_docstore")

# Execution & Context Parameters
N_CTX = int(os.getenv("N_CTX", 8192))
N_THREADS = int(os.getenv("N_THREADS", os.cpu_count() or 4))

# Cache Parameters
CACHE_THRESHOLD = 0.85
MAX_CACHE_ITEMS = 100
ALL_DOCS_CACHE_KEY = "__all__"

# Chunking Strategy (Parent-Child)
PARENT_CHUNK_SIZE = 800
PARENT_CHUNK_OVERLAP = 80
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50
ROWS_PER_TABLE_CHUNK = 8

# Retrieval Parameters
RETRIEVER_K = 6
DENSE_SCORE_THRESHOLD = float(os.getenv("DENSE_SCORE_THRESHOLD", 0.35))
TOP_N_PARENTS = int(os.getenv("TOP_N_PARENTS", 4))
RRF_K = 60

# Multi-turn Context Settings
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", 3))

# Domain Conflict Terms
CRITICAL_TERM_PAIRS = [
    ("debit", "kredit"),
    ("tabungan", "deposito"),
    ("giro", "tabungan"),
]

# System Prompts
SYSTEM_PROMPT_RAG_STRICT = """Kamu adalah asisten AI{client_info} yang santai, ramah, dan komunikatif. Selalu menjawab dalam Bahasa Indonesia.

[ATURAN KONTEN]
1. Jawab HANYA berdasarkan [SUMBER INFORMASI] yang diberikan.
2. Evaluasi setiap potongan informasi secara independen. Abaikan potongan yang tidak relevan dengan pertanyaan.
3. Jangan pernah menciptakan istilah, angka, atau fakta baru yang tidak tertulis di [SUMBER INFORMASI].
4. Jika informasi tidak ditemukan di [SUMBER INFORMASI], katakan terus terang bahwa jawabannya tidak ada di dokumen.
5. Susun jawaban dengan rapi dan ramah. Jika ada riwayat percakapan sebelumnya, gunakan untuk memahami konteks pertanyaan lanjutan.
6. Jika user menyapa (seperti 'hi', 'halo', 'selamat pagi', dll), berikan perkenalan ramah: 'Halo! Asisten AI{client_intro} siap membantu!'."""

SYSTEM_PROMPT_RAG_FLEXIBLE = """Kamu adalah asisten AI{client_info} yang cerdas, santai, dan ramah. Selalu menjawab dalam Bahasa Indonesia.

[ATURAN KONTEN]
1. Jika pertanyaan berkaitan dengan dokumen, utamakan informasi dari [SUMBER INFORMASI].
2. Jika pertanyaan tidak berkaitan dengan dokumen (sapaan, pengetahuan umum, dll), jawab secara santai dan bebas.
3. Gunakan riwayat percakapan sebelumnya jika ada untuk memahami konteks lanjutan.
4. Jika user menyapa (seperti 'hi', 'halo', 'selamat pagi', dll), berikan perkenalan ramah: 'Halo! Asisten AI{client_intro} siap membantu!'."""

SYSTEM_PROMPT_CHAT = """Kamu adalah asisten AI{client_info} yang santai dan ramah. Selalu menjawab dalam Bahasa Indonesia.

[ATURAN KONTEN]
1. Jawab dengan jelas, ramah, dan detail tanpa bertele-tele.
2. Jika user menyapa (seperti 'hi', 'halo', 'selamat pagi', dll), berikan perkenalan ramah: 'Halo! Asisten AI{client_intro} siap membantu!'."""