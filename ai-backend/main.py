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
    start_time = time.time()
    user_input = request.message.strip().lower()
    cache_key = hashlib.md5(user_input.encode('utf-8')).hexdigest()

    if cache_key in PROMPT_CACHE:
        process_time = time.time() - start_time
        cached_reply = PROMPT_CACHE[cache_key]
        return {"reply": f"{cached_reply}\n\n*(⚡ Diambil dari Cache dalam {process_time:.4f} detik)*"}

    try:
        # Inisialisasi model Ollama
        # Pastikan nama model ("SLM_AI") sudah sesuai dengan yang kamu buat di terminal
        llm = Ollama(
            model="SLM_AI",
            temperature=0.2,
            num_predict=1024
        )
        context = ""
        is_rag_mode = False

        # 1. BYPASS THRESHOLD & LANGSUNG GUNAKAN MMR
        if os.path.exists(persist_directory) and os.listdir(persist_directory):
            try:
                vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)

                # Tarik 3 dokumen paling relevan dan beragam secara paksa (tanpa threshold)
                mmr_docs = vector_db.max_marginal_relevance_search(
                    request.message, k=3, fetch_k=10
                )

                # Pastikan dokumen berhasil ditarik
                if mmr_docs:
                    context = "\n\n".join([doc.page_content for doc in mmr_docs])
                    is_rag_mode = True
                    
            except Exception as e:
                print(f"Database ada tapi gagal dibaca: {e}")

        # 2. STRUKTUR PROMPT (Perhatikan teks diratakan ke kiri agar model tidak bingung membaca spasi)
        if is_rag_mode:
            prompt = f"""Kamu adalah June, asisten AI yang santai dan ramah. Gunakan kata ganti "aku" dan "kamu".

[SUMBER INFORMASI DARI DATABASE]:
{context}

[PERTANYAAN USER]: 
{request.message}

Instruksi WAJIB untuk June:
1. Jawab pertanyaan user HANYA berdasarkan [SUMBER INFORMASI DARI DATABASE] di atas.
2. JELASKAN SECARA DETAIL DAN KOMPREHENSIF. Jabarkan semua informasi, alasan, atau contoh penting yang ada di sumber dokumen. Jangan pelit kata.
3. WAJIB 100% menggunakan gaya bahasa santai sehari-hari (aku/kamu). JANGAN pernah menggunakan bahasa kaku, formal, atau seperti robot.
4. Susun jawabanmu menjadi beberapa paragraf yang rapi atau gunakan bullet points agar enak dibaca.
5. Jika informasi sama sekali tidak ada di dokumen, bilang dengan santai bahwa kamu tidak menemukan datanya.
6. Tutup penjelasanmu dengan kalimat sapaan yang asyik di akhir."""
        else:
            prompt = f"""Kamu adalah June, asisten AI yang santai (aku/kamu).    

Pertanyaan: {request.message}
Instruksi: Berikan jawaban yang panjang, detail, dan asyik untuk dibaca."""
        
        # Generate jawaban
        response = llm.invoke(prompt)

        # SIMPAN KE CACHE
        PROMPT_CACHE[cache_key] = response

        process_time = time.time() - start_time
        return {"reply": f"{response}\n\n*(🤖 Dijawab oleh model dalam {process_time:.2f} detik)*"}

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