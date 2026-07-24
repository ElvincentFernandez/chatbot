
### RAGChat - AI Research Assistant

Proyek ini adalah implementasi sistem Retrieval-Augmented Generation (RAG) berbasis monorepo yang memadukan
antarmuka chatbot modern dengan backend AI lokal. Sistem ini dirancang untuk membaca dan menganalisis
dokumen PDF serta menjawab pertanyaan secara interaktif menggunakan Small Language Model (SLM), berjalan
sepenuhnya lokal (offline) baik di CPU maupun GPU.

```markdown
# Struktur Direktori
project_rag/
├── ai-backend/          # Backend FastAPI (RAG, ChromaDB, llama.cpp)
│   └── models/          # Tempat file model .gguf (dibuat manual, lihat langkah 1)
└── chatbot-frontend/    # Frontend Next.js (UI Chatbot interaktif)
```

## Arsitektur Singkat

- **Inference model**: langsung via `llama-cpp-python` — model GGUF di-load in-process oleh
  backend FastAPI, tidak butuh server model terpisah.
- **Retrieval**: Parent Document Retriever (LangChain) — pencarian similarity jalan di level *child chunk*
  (kecil, presisi), tapi konteks yang dikirim ke LLM adalah *parent chunk* (lebih utuh) dan otomatis
  ter-dedup kalau beberapa child chunk mengarah ke parent yang sama.
- **Vector store**: ChromaDB, persist ke disk.
- **Multi-dokumen**: sistem mendukung banyak PDF ter-upload sekaligus, dengan opsi scoping pencarian ke
  1 dokumen aktif spesifik atau ke semua dokumen.
- **Semantic cache**: prompt yang mirip secara makna (bukan cuma exact match) dijawab dari cache tanpa
  generate ulang, di-scope per dokumen aktif supaya tidak salah campur antar dokumen.

## Persyaratan Sistem
Pastikan sistem sudah terinstal perangkat lunak berikut:
1. **Node.js** (v18 atau lebih baru)
2. **Python** (v3.11 atau lebih baru)
3. **Git**
---

1. Spesifikasi Minimum (Running on CPU)
* **Prosesor:** Intel Core i5 Gen 10 / AMD Ryzen 5 3000 Series ke atas (teruji lancar di Intel Core i5-12450H).
* **RAM:** 8 GB (minimal sisa RAM bebas 4 GB untuk model & backend).
* **Penyimpanan:** ruang kosong minimal 5 GB.
* Waktu respons di CPU murni berkisar **8-15 detik** sampai token pertama muncul, tergantung panjang
  konteks dokumen yang di-retrieve.

2. Spesifikasi Rekomendasi (Running on GPU)
* **Prosesor:** Intel Core i7 / AMD Ryzen 7 Series terbaru.
* **RAM:** 16 GB (sangat disarankan untuk stabilitas *monorepo*).
* **GPU:** NVIDIA RTX 3050 / 4050 (atau lebih tinggi) dengan **VRAM 4 GB+** — cukup untuk full-offload
  model 2B ke GPU (`n_gpu_layers=-1` di `main.py`).
* **Penyimpanan:** ruang kosong minimal 5 GB.

## Panduan Instalasi & Menjalankan Sistem

### 1. Unduh Model GGUF
Proyek ini menggunakan model **Qwen3.5-2B** format GGUF agar bisa berjalan secara lokal via llama.cpp.
1. Buka tautan repositori: [Model Qwen Fine-Tuned](https://huggingface.co/RamIsFine/qwen-alpaca-bisa)
2. Unduh file `Qwen3.5-2B.Q4_K_M.gguf`.
3. Buat folder `models/` di dalam `ai-backend/`, lalu pindahkan file `.gguf` tersebut ke sana:
   ```
   ai-backend/models/Qwen3.5-2B.Q4_K_M.gguf
   ```
   Kalau nama file atau lokasinya berbeda, sesuaikan lewat environment variable `MODEL_PATH` (lihat
   Bagian Konfigurasi di bawah), tidak perlu mengubah kode.

### 2. Menjalankan Backend (FastAPI)
Backend mengelola pemrosesan PDF, penyimpanan vektor, dan langsung menjalankan inference model (tanpa
server model terpisah).
1. Masuk ke folder backend:
   ```bash
   cd ai-backend
   ```
2. Buat dan aktifkan *Virtual Environment*:
   ```bash
   python -m venv venv
   ```
   Di PowerShell:
      ```bash
      .\venv\Scripts\Activate.ps1
      ```
   Di Command Prompt (CMD):
      ```bash
      venv\Scripts\activate
      ```
   Di Git Bash / Terminal Linux:
      ```bash
      source venv/Scripts/activate
      ```
3. Instal dependensi Python:
   ```bash
   pip install -r requirements.txt
   ```
   > `requirements.txt` sudah mengarah ke wheel `llama-cpp-python` yang pre-built untuk CPU, jadi tidak
   > perlu compiler C++ terpasang. Kalau ingin build dengan akselerasi GPU (CUDA), lihat komentar di
   > dalam `requirements.txt`.
4. Jalankan server backend:
   ```bash
   python main.py
   ```
   *(Backend berjalan di `http://localhost:8000`)*.

### 3. Menjalankan Frontend (Next.js)
1. Buka tab terminal baru (biarkan terminal backend tetap menyala) dan arahkan ke folder frontend:
   ```bash
   cd chatbot-frontend
   ```
2. Instal dependensi Node.js:
   ```bash
   npm install
   ```
3. Jalankan server frontend:
   ```bash
   npm run dev
   ```
   *(Frontend berjalan di `http://localhost:3000`)*.

---

## ⚙️ Konfigurasi (Environment Variables)

Semua opsional — kalau tidak di-set, backend pakai nilai default yang sudah teruji jalan.

| Variabel | Default | Keterangan |
|---|---|---|
| `MODEL_PATH` | `./models/Qwen3.5-2B-UD-Q4_K_XL.gguf` | Lokasi file model GGUF |
| `CHROMA_DIR` | `./chroma_db` | Lokasi penyimpanan vector store |
| `PARENT_STORE_DIR` | `./parent_docstore` | Lokasi penyimpanan parent chunk (Parent Document Retriever) |
| `DOCUMENTS_REGISTRY_PATH` | `./documents_registry.json` | Daftar nama dokumen yang sudah di-upload |
| `N_CTX` | `8192` | Context window model |
| `N_THREADS` | jumlah core CPU | Jumlah thread untuk inference |
| `VERBOSE_LLM` | `false` | Set `true` untuk lihat log detail llama.cpp saat startup (mis. cek dukungan AVX2) |

## 🔗 Cara Kerja Integrasi (Alur Sistem)

1. **Frontend (Port 3000):** Pengguna mengunggah PDF atau mengirim pesan lewat antarmuka UI. Pengguna
   juga bisa memilih **dokumen aktif** (atau "semua dokumen") lewat dropdown di atas kolom chat. Data
   dikirim via *HTTP POST* ke Backend.
2. **Backend (Port 8000):**
   - Saat PDF di-upload: teks diekstrak (PyMuPDF), dipecah jadi *parent* dan *child chunk* (Parent
     Document Retriever), lalu disimpan ke **ChromaDB** (child, untuk pencarian) dan **docstore lokal**
     (parent, untuk konteks yang dikirim ke model).
   - Saat ada pertanyaan chat: backend cek dulu apakah pertanyaan mirip secara makna dengan yang pernah
     ditanyakan sebelumnya **untuk dokumen yang sama** (semantic cache). Kalau tidak ada cache yang cocok,
     backend mencari potongan teks relevan dari ChromaDB (di-scope ke dokumen aktif kalau dipilih),
     menggabungkannya dengan pertanyaan pengguna, dan menjalankan generate lewat llama.cpp secara langsung
     di dalam proses backend (tidak ada server model terpisah).
3. **Model (llama.cpp, in-process):** Memproses prompt yang berisi konteks dari Backend dan mengembalikan
   jawaban secara streaming (token demi token) ke layar pengguna.

## 📄 Manajemen Dokumen

- `GET /api/documents` — daftar semua dokumen yang sudah di-upload.
- `DELETE /api/documents/{filename}` — hapus 1 dokumen beserta seluruh chunk dan cache-nya.
- Upload ulang file dengan nama yang sama akan otomatis menggantikan (bukan menumpuk duplikat) chunk lama.

## ⚠️ Catatan Penting
* File `.gguf`, folder `ai-backend/models/`, `chroma_db/`, dan `parent_docstore/` diabaikan oleh Git
  (lewat `.gitignore`) karena ukurannya besar dan bersifat data lokal/hasil generate ulang. Jika melakukan
  *clone* proyek ini di komputer baru, model wajib diunduh ulang dari Hugging Face (lihat langkah 1), dan
  seluruh dokumen PDF perlu di-upload ulang lewat UI.
* Sistem berjalan sepenuhnya lokal/offline setelah model ter-unduh — tidak ada panggilan API eksternal
  saat chat maupun upload dokumen.
