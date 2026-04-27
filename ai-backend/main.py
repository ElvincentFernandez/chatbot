import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

app = FastAPI()

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
    try:
        llm = Ollama(model="june-qwen")
        context = ""

        # 1. Cek apakah folder database ada dan tidak kosong
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

        # 2. Susun Prompt berdasarkan kondisi
        if context:
            # Mode RAG: Beri tanda jelas mana yang Konteks, mana yang Pertanyaan
            prompt = f"""Konteks Dokumen:
            {context}

            Pertanyaan User: {request.message}

            Instruksi: 
            1. Jawablah menggunakan gaya santai (aku-kamu).
            2. Gunakan **bullet points** atau daftar bernomor untuk menjelaskan poin-poin penting.
            3. Gunakan format **tebal (bold)** pada istilah kunci.
            4. Jika menjelaskan konsep teknis (seperti CBIM atau CRA), jabarkan definisi, komponen, dan tujuannya secara terstruktur.
            5. Pastikan kalimat terakhir menutup penjelasan dengan ramah."""
        else:
            # Mode Chat Biasa (Bypass)
            prompt = f"Pertanyaan User: {request.message}"

        response = llm.invoke(prompt)
        return {"reply": response}

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
        # Coba naikkan chunk_size agar satu paragraf utuh tidak terpotong
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,   # Sebelumnya 700
            chunk_overlap=200,  # Sebelumnya 100, overlap lebih besar menjaga konteks antar potongan
            separators=["\n\n", "\n", ". ", " "] # Prioritaskan potong di paragraf atau titik
        )
        chunks = text_splitter.split_documents(data)
        
        # Masukkan ke ChromaDB
        Chroma.from_documents(
            documents=chunks, 
            embedding=embeddings, 
            persist_directory=persist_directory
        )
        
        os.remove(file_path) # Bersihkan file temp
        return {"message": f"Sip! Aku sudah baca '{file.filename}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)