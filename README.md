```markdown
RAGChat - AI Research Assistant

Proyek ini adalah implementasi sistem Retrieval-Augmented Generation (RAG) berbasis monorepo yang memadukan
antarmuka chatbot modern dengan backend AI lokal. Sistem ini dirancang untuk membaca dan menganalisis
dokumen PDF serta menjawab pertanyaan secara interaktif menggunakan Small Language Model (SLM).

🗂️ Struktur Direktori


project_rag/
├── ai-backend/          # Backend FastAPI (RAG, ChromaDB, Integrasi Model)
└── chatbot-frontend/    # Frontend Next.js (UI Chatbot interaktif)
```

## ⚙️ Persyaratan Sistem
Pastikan sistem sudah terinstal perangkat lunak berikut:
1. **Node.js** (v18 atau lebih baru)
2. **Python** (v3.10 atau lebih baru)
3. [**Ollama**](https://ollama.com/download/windows)
4. **Git**

---

## 🖥️ System Requirements
1. Spesifikasi Minimum (Running on CPU)
* **Prosesor:** Intel Core i5 Gen 10 / AMD Ryzen 5 3000 Series.
* **RAM:** 8 GB (Minimal sisa RAM bebas 4 GB untuk model & backend).
* **Penyimpanan:** ruang kosong minimal 5 GB.

### 2. Spesifikasi Rekomendasi (Running on GPU)
* **Prosesor:** Intel Core i7 / AMD Ryzen 7 Series terbaru.
* **RAM:** 16 GB (Sangat disarankan untuk stabilitas *monorepo*).
* **GPU:** NVIDIA RTX 3050 / 4050 (atau lebih tinggi) dengan **VRAM 4 GB+**.
* **Penyimpanan:** ruang kosong minimal 5 GB.

---

## 🚀 Panduan Instalasi & Menjalankan Sistem

### 1. Unduh Model GGUF
Proyek ini menggunakan model Qwen yang sudah disesuaikan formatnya untuk berjalan secara lokal.
1. Buka tautan repositori: [RamIsFine/Qwen-Model](https://huggingface.co/RamIsFine/Qwen-Model)
2. Unduh file ber-ekstensi `.gguf` (misalnya `qwen2.5-3b-instruct.Q4_K_M.gguf`).
3. Pindahkan file `.gguf` tersebut ke dalam folder `ai-backend/`.

### 2. Konfigurasi Model AI (Ollama)
Model perlu didaftarkan ke sistem Ollama agar bisa menerima instruksi khusus (seperti RAG).
1. Buka terminal dan arahkan ke folder backend:
   ```bash
   cd ai-backend
   ```
2. Bangun model ke dalam sistem Ollama menggunakan `Modelfile` yang sudah ada:
   ```bash
   ollama create SLM_AI -f Modelfile
   ```
3. (Opsional) Uji coba model di terminal untuk memastikan berhasil dimuat:
   ```bash
   ollama run SLM_AI
   ```
   *(Ketik `/bye` untuk keluar).*

### 3. Menjalankan Backend (FastAPI)
Backend mengelola pemrosesan PDF, penyimpanan vektor, dan komunikasi dengan AI.
1. Masih di dalam folder `ai-backend`, buat dan aktifkan *Virtual Environment*:
   ```bash
   python -m venv venv
   
   # Pengguna Windows:
   venv\Scripts\activate
   
   # Pengguna Mac/Linux:
   source venv/bin/activate
   ```
2. Instal dependensi Python:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan server backend:
   ```bash
   python main.py
   ```
   *(Backend sekarang berjalan di `http://localhost:8000`)*.

### 4. Menjalankan Frontend (Next.js)
Frontend menyediakan antarmuka pengguna untuk interaksi *chat* dan unggah berkas.
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
   *(Frontend sekarang berjalan di `http://localhost:3000`)*.

---

## 🔗 Cara Kerja Integrasi (Alur Sistem)

Agar RAGChat bekerja dengan sempurna, ketiga komponen ini berjalan secara paralel:
1. **Frontend (Port 3000):** Pengguna mengunggah PDF atau mengirim pesan melalui antarmuka UI.
   Data dikirim via *HTTP POST* ke Backend.
3. **Backend (Port 8000):** FastAPI menerima data. Jika itu PDF, teks akan dipotong (*chunking*)
   dan disimpan ke **ChromaDB**.
5. Jika itu pertanyaan chat, Backend mencari potongan teks relevan dari ChromaDB, menggabungkannya
   dengan pertanyaan pengguna, dan mengirimkan *Prompt* utuh ke Ollama.
7. **Ollama / Llama.cpp (Port 11434):** Menjalankan model `SLM_AI` secara lokal, memproses *Prompt*
   yang berisi konteks dari Backend, dan mengembalikan jawaban akhir untuk diteruskan kembali ke layar pengguna.

## ⚠️ Catatan Penting
* File `.gguf` dan direktori `chroma_db/` diabaikan oleh Git (melalui `.gitignore`) karena ukurannya yang besar.
  Jika melakukan *clone* proyek ini di komputer baru, model wajib diunduh ulang dari Hugging Face.
* Pastikan aplikasi Ollama selalu berjalan di *background* sistem operasi sebelum menyalakan server backend.
```
