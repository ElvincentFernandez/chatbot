# Status Proyek: RAGChat Multi-Client Chatbot
**Terakhir Diperbarui:** 2026-08-06

---

## 1. Arsitektur & Teknologi Saat Ini

### Stack Teknologi
| Layer | Teknologi |
|---|---|
| **Frontend** | Next.js (App Router), TypeScript, Tailwind CSS |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Vector Store** | ChromaDB (persist ke disk, per-client collection) |
| **Embedding Model** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (via HuggingFace) |
| **LLM** | LlamaCpp — model GGUF lokal (`Qwen3.5-2B-UD-Q4_K_XL.gguf`) |
| **Keyword Search** | BM25 (rank_bm25, in-memory, per-client) |
| **Database** | SQLite (`chatbot.db`) |
| **PDF Parsing** | PyMuPDF (teks + tabel) |

### Struktur Folder
```
chatbot-fork/
├── ai-backend/
│   ├── main.py              # Entrypoint FastAPI (routing, auth, orchestration)
│   ├── rag.py               # Clean facade — re-export semua simbol dari rag_modules/
│   ├── access.py            # Validasi akses upload per role
│   ├── database.py          # SQLite helper (clients, users, sessions, messages, documents)
│   ├── rag_modules/
│   │   ├── config.py        # Semua konstanta & system prompt (dengan {client_info} template)
│   │   ├── state.py         # RAGState, LocalFileByteStore, lazy-init per-client
│   │   ├── retrieval.py     # BM25Index, Hybrid Dense+BM25, RRF, cosine similarity
│   │   ├── cache.py         # Semantic prompt cache scoped per client
│   │   ├── ingestion.py     # Parsing PDF, ekstraksi tabel PyMuPDF, chunk indexing
│   │   └── generation.py    # build_prompt (multi-turn), stream_llm, initialize, select_system_prompt
│   ├── models/              # Taruh file .gguf di sini (tidak di-commit ke Git)
│   ├── chroma_db/           # Data ChromaDB (tidak di-commit ke Git)
│   ├── parent_docstore/     # Parent chunks per-client (tidak di-commit ke Git)
│   └── requirements.txt
└── chatbot-frontend/
    └── app/
        ├── page.tsx         # Halaman utama chat (termasuk file upload)
        ├── admin/page.tsx   # Halaman admin (manajemen user, client, dokumen)
        └── login/page.tsx   # Halaman login
```

### Skema Database SQLite
| Tabel | Kolom Utama |
|---|---|
| `clients` | `id`, `name`, `type` ('Perbankan'/'Kampus'/'Umum') |
| `users` | `id`, `username`, `password`, `token`, `role`, `client_id` |
| `chat_sessions` | `id` (UUID), `user_id`, `client_id`, `title`, `created_at` |
| `messages` | `id` (UUID), `session_id`, `role`, `content`, `timestamp` |
| `documents` | `id`, `client_id`, `filename`, `doc_type`, `upload_date` |

### Role Hierarki User
| Role | Kemampuan |
|---|---|
| `superadmin` | Akses penuh semua client, user, dokumen |
| `admin` | Sama seperti superadmin |
| `admin_client` | Hanya bisa akses client miliknya sendiri (upload, lihat dokumen, chat) |
| `user` | Hanya bisa chat |

### API Endpoint Utama
```
POST   /api/auth/login
GET    /api/clients
POST   /api/clients
DELETE /api/clients/{client_id}
GET    /api/chat/sessions
POST   /api/chat/sessions
GET    /api/chat/sessions/{session_id}
DELETE /api/chat/sessions/{session_id}
POST   /api/chat                         ← RAG streaming endpoint
POST   /api/chat/save_partial
GET    /api/documents/{client_id}
GET    /api/documents
POST   /api/upload                       ← Upload PDF per client
DELETE /api/documents/{doc_id}
GET    /api/admin/users
POST   /api/admin/users
DELETE /api/admin/users/{user_id}
GET    /api/health
```

### Alur Pipeline RAG (di /api/chat)
1. Autentikasi token → validasi sesi → ambil `client_id` + `client_name` (JOIN ke tabel clients)
2. Ambil riwayat percakapan terakhir (MAX_HISTORY_TURNS=3 pasang) dari DB SEBELUM simpan pesan baru
3. Simpan pesan user ke DB
4. Cek Semantic Cache (hanya jika history kosong / pesan pertama di sesi)
5. Hybrid Retrieval: Dense Embedding (ChromaDB) + BM25 → Reciprocal Rank Fusion
6. Bangun prompt ChatML (system + multi-turn history + konteks dokumen + pertanyaan user)
7. Stream token dari LLM via stream_llm() (non-blocking, thread terpisah)
8. Simpan response penuh ke DB + store ke semantic cache

---

## 2. Fitur yang Sudah Selesai (Done)

### Backend
- [x] Multi-Client Isolation: ChromaDB collection, BM25 index, semantic cache terpisah per client
- [x] Multi-Turn Conversation: 3 pasang riwayat terakhir disertakan ke prompt ChatML
- [x] Semantic Cache: Dilewati jika ada riwayat (mencegah false cache hit)
- [x] Hybrid Retrieval: Dense Vector + BM25 + Reciprocal Rank Fusion (RRF)
- [x] Parent-Child Chunking: Parent 800 token / Child 300 token
- [x] Tabel PDF: Deteksi & ekstraksi tabel PyMuPDF → format Markdown
- [x] Merge Overlapping Chunks: Parent chunks tumpang tindih digabung
- [x] CRUD Dokumen: Upload, list, hapus dokumen per-client + rebuild BM25 + invalidate cache
- [x] CRUD Client & User: Manajemen oleh superadmin/admin
- [x] Refactoring Modular: rag.py (723 baris) → 6 modul di rag_modules/
- [x] System Prompt Dinamis: Nama client di-inject via {client_info} & {client_intro} placeholder
- [x] Perkenalan Otomatis: LLM memperkenalkan diri saat user menyapa dengan nama client
- [x] Upload Fix admin_client: Race condition frontend + type mismatch backend diperbaiki

### Frontend
- [x] Login page dengan redirect otomatis
- [x] Halaman chat utama (page.tsx) dengan file upload + multi-sesi
- [x] Halaman admin (admin/page.tsx) untuk manajemen user, client, dan dokumen
- [x] Upload PDF ke client yang benar untuk role admin_client (baca dari localStorage)

---

## 3. Masalah / Bug yang Sedang Dihadapi (In Progress / Blocked)

### Keamanan (Belum Diimplementasi)
- [ ] Password masih plain-text di SQLite — perlu hash dengan bcrypt/passlib
- [ ] Token statis UUID — tidak kedaluwarsa, tidak bisa di-revoke; perlu JWT
- [ ] Tidak ada rate limiting di endpoint chat/upload

### Kualitas RAG
- [ ] Gaya bahasa LLM tidak konsisten — kadang tetap formal karena meniru teks dokumen perbankan
- [ ] Tidak ada threshold relevansi sebelum dokumen masuk ke konteks prompt

### Infrastruktur
- [ ] LLM hanya berjalan di CPU (GPU belum diverifikasi)
- [ ] Semua logging masih pakai print() — belum pakai logging module
- [ ] requirements.txt ada duplikat: pymupdf muncul 2 kali (baris 17 dan 20)

### Frontend
- [ ] URL backend hardcoded ke http://localhost:8000 di semua file — belum pakai env variable
- [ ] Tidak ada error boundary jika backend down

---

## 4. Rencana Langkah Berikutnya (Next Steps)

### Prioritas Tinggi (Security & Stability)
1. Hash password: Tambahkan `passlib[bcrypt]` ke requirements.txt, update database.py:
   - `add_user()`: hash password sebelum simpan
   - `get_user_by_credentials()`: verifikasi dengan bcrypt.verify()
2. JWT Token: Gunakan `python-jose[cryptography]`, expiry 24 jam, update get_current_user() di main.py
3. Fix duplikat di requirements.txt: Hapus baris `pymupdf` kedua (baris 20)

### Prioritas Menengah (Kualitas)
4. Environment variable frontend: Buat `.env.local` di chatbot-frontend/ dengan:
   `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
   Ganti semua URL hardcoded di page.tsx, admin/page.tsx, login/page.tsx
5. Logging terpusat: Ganti print() dengan logging.getLogger(__name__)
6. Relevance threshold: Jika semua retrieved docs < skor 0.4, set is_rag_mode=False

### Prioritas Rendah (Nice to Have)
7. Streaming frontend: Pastikan frontend render token real-time via ReadableStream
8. Export chat history ke .txt atau .pdf
9. Konfirmasi hapus dokumen/user/client dengan modal

---

## 5. Instruksi untuk AI Baru

### Repo & Workspace
- Repo GitHub (fork): https://github.com/Rambu464/chatbot
- Repo asli (upstream): https://github.com/ElvincentFernandez/chatbot
- Workspace lokal: d:\Personal\Project\chatbot-fork

### Cara Menjalankan
```powershell
# Backend (dari folder ai-backend)
cd d:\Personal\Project\chatbot-fork\ai-backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# Frontend (dari folder chatbot-frontend)
cd d:\Personal\Project\chatbot-fork\chatbot-frontend
npm run dev
```

### Penting: Cara Gunakan Python di Backend
SELALU gunakan `.\venv\Scripts\python.exe` (bukan `python` global) di folder ai-backend:
```powershell
.\venv\Scripts\python.exe -m py_compile main.py rag.py
.\venv\Scripts\python.exe -c "import rag; print(rag.state)"
```

### Konvensi Kode yang Harus Dijaga
1. Semua logic RAG hanya boleh ada di rag_modules/ — main.py hanya orchestrator HTTP
2. Isolasi per-client wajib: setiap operasi RAG selalu menyertakan client_id
3. Komentar harus fokus pada logika dan tujuan fitur, bukan riwayat perubahan
4. rag.py adalah clean facade: jika ada fungsi baru di rag_modules/, tambahkan re-export di rag.py dan __all__

### File Kunci
| File | Yang Perlu Diperhatikan |
|---|---|
| `rag_modules/config.py` | System prompts pakai {client_info} dan {client_intro} — jangan hardcode nama client |
| `rag_modules/generation.py` | `select_system_prompt(is_rag_mode, general_mode, client_name)` mengisi placeholder dinamis |
| `main.py` baris ~212 | Query JOIN ke tabel clients untuk ambil client_name — jangan ubah tanpa menjaga client_name diteruskan ke select_system_prompt |
| `access.py` | validate_upload_access() selalu lock admin_client ke user["client_id"]-nya, abaikan query param client_id dari frontend |
| `admin/page.tsx` baris ~306 | handleFileUpload membaca client_id dari localStorage (bukan selectedClientId state) untuk admin_client |
| `page.tsx` baris ~174 | Sama seperti di atas untuk halaman chat utama |

### Default Credentials (Development Only)
| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | superadmin |
| `adminclient` | `client123` | admin_client (Bank DKI, client_id=1) |
| `user` | `user123` | user |

### Environment Variables Backend (semua ada default, opsional)
```
MODEL_PATH            = ./models/Qwen3.5-2B-UD-Q4_K_XL.gguf
CHROMA_DIR            = ./chroma_db
PARENT_STORE_DIR      = ./parent_docstore
N_CTX                 = 8192
N_THREADS             = <jumlah CPU otomatis>
N_GPU_LAYERS          = -1   (semua ke GPU; 0 untuk CPU only)
MAX_HISTORY_TURNS     = 3
DENSE_SCORE_THRESHOLD = 0.35
TOP_N_PARENTS         = 4
VERBOSE_LLM           = false
DEBUG_CONTEXT         = false
DEBUG_CACHE           = false
CORS_ORIGINS          = *
```
