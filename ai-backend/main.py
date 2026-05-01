import os
import time
import hashlib
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Inisialisasi FastAPI
app = FastAPI()

# Inisialisasi In-Memory Prompt Cache
PROMPT_CACHE = {}

# Izinkan Frontend Next.js mengakses API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Port default Next.js
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inisialisasi model embedding
# Pakai model yang ringan tapi akurat untuk bahasa Indonesia
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
persist_directory = "./chroma_db"

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # Memulai timer untuk logging waktu respons
    start_time = time.time()

    # Hashing untuk Prompt Caching (Standarisasi input)
    user_input = request.message.strip().lower()
    cache_key = hashlib.md5(user_input.encode('utf-8')).hexdigest()

    # CACHE HIT untuk cek pertanyaan sudah ada di cache
    if cache_key in PROMPT_CACHE:
        process_time = time.time() - start_time
        cached_reply = PROMPT_CACHE[cache_key]
        return {"reply": f"{cached_reply}\n\n*(⚡ Diambil dari Cache dalam {process_time:.4f} detik)*"}

    try:
        llm = Ollama(model="june-qwen")
        context = ""

        # Cek apakah folder database ada dan tidak kosong
        if os.path.exists(persist_directory) and os.listdir(persist_directory):
            try:
                vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
                
                # Cari potongan teks paling relevan
                docs = vector_db.similarity_search(request.message, k=3)
                
                # Tambahkan ambang batas (threshold) sederhana 
                # Agar tidak semua chat dipaksa nyambung ke PDF
                context = "\n".join([doc.page_content for doc in docs])
            except Exception as e:
                print(f"Database ada tapi gagal dibaca: {e}")

        # Susun Prompt berdasarkan kondisi
        if context:
            # Mode RAG: Beri tanda jelas mana yang Konteks, mana yang Pertanyaan
            prompt = f"""Konteks Dokumen:
            {context}

            Pertanyaan User: {request.message}

            Instruksi: 
            1. Kamu adalah asisten AI yang teliti. Jawablah menggunakan gaya santai (aku-kamu).
            2. JAWAB HANYA BERDASARKAN "Konteks Dokumen" di atas. JANGAN menambahkan informasi, bahan, atau langkah dari luar dokumen.
            3. Jika jawaban tidak ditemukan di dalam Konteks Dokumen, katakan dengan jujur: "Maaf, aku nggak nemuin info itu di dokumen yang kamu kasih." JANGAN MENGARANG JAWABAN.
            4. Gunakan **bullet points** atau daftar bernomor jika menjelaskan resep atau langkah-langkah.
            5. Pastikan kalimat terakhir menutup penjelasan dengan ramah."""
        else:
            # Mode Chat Biasa (Bypass)
            prompt = f"Pertanyaan User: {request.message}"
        
        # Generate jawaban dari Qwen
        response = llm.invoke(prompt)

        # SIMPAN KE CACHE
        PROMPT_CACHE[cache_key] = response

        process_time = time.time() - start_time
        return {"reply": f"{response}\n\n*(🤖 Dijawab oleh Qwen dalam {process_time:.2f} detik)*"}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Aduh, Aku lagi pusing nih.")

@app.post("/api/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"./temp_uploads/{file.filename}"
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        # Load dan Split PDF
        loader = PyPDFLoader(file_path)
        data = loader.load()
        # Naikkan chunk_size agar satu paragraf utuh tidak terpotong
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=400,
            separators=["\n\n", "\n", ". ", " "]
        )
        chunks = text_splitter.split_documents(data)
        
        # Masukkan ke ChromaDB
        Chroma.from_documents(
            documents=chunks, 
            embedding=embeddings, 
            persist_directory=persist_directory
        )
        
        os.remove(file_path) # Bersihkan file temp

        # Reset Cache saat
        global PROMPT_CACHE
        PROMPT_CACHE.clear()

        return {"message": f"Sip! Aku sudah baca '{file.filename}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)