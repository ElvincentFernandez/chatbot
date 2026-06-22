import os
import time
import math
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Inisialisasi FastAPI
app = FastAPI()

# Inisialisasi In-Memory Prompt Cache
PROMPT_CACHE = []
CACHE_THRESHOLD = 0.95 # 95% Mirip baru dianggap sama

# Fungsi untuk menghitung kemiripan makna tanpa library tambahan (murni Python)
def calculate_cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0: return 0.0
    return dot_product / (norm1 * norm2)

# Izinkan Frontend Next.js mengakses API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Port default frontend
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
    query_embedding = embeddings.embed_query(user_input)

    # FASE SEMANTIC CACHING :
    # Ubah teks input menjadi vektor
    query_embedding = embeddings.embed_query(user_input)
    
    # 1. FASE CACHE (Stream Simulasi)
    # Cari di memori cache apakah ada pertanyaan dengan distance terdekat
    for cached_item in PROMPT_CACHE:
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD:
            async def stream_cache():
                # Simulasi typing dari cache
                words = cached_item['response'].split(" ")
                for word in words:
                    yield word + " "
                    await asyncio.sleep(0.01) 
                yield f"\n\n*(⚡ Diambil dari Semantic Cache - {sim_score*100:.1f}% dalam {time.time() - start_time:.4f} detik)*"
            
            return StreamingResponse(stream_cache(), media_type="text/plain")

    try:
        # 2. SETUP MODEL & RAG
        llm = Ollama(
            model="qwen_slm", # Pastikan nama model ("qwen_slm") sudah sesuai dengan yang dibuat di Modelfile
            temperature=0.2,
            num_predict=2048,
            repeat_penalty=1.15
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

        # 2. STRUKTUR PROMPT
        if is_rag_mode:
            prompt = f"""Kamu adalah qwen, asisten AI yang santai dan ramah.

[SUMBER INFORMASI DARI DATABASE]:
{context}

[PERTANYAAN USER]: 
{request.message}

[ATURAN WAJIB]:
1. PERAN: Kamu adalah asisten AI yang cerdas dan santai.
2. GAYA BAHASA: WAJIB gunakan kata "aku" dan "kamu". Jangan kaku.
3. ANTI-HALUSINASI: Jawab HANYA dari [SUMBER INFORMASI].
4. Susun jawaban akhir dengan rapi menggunakan bullet points jika perlu.
5. Jika hanya percakapan seperti bertanya kabar atau sapaan, tidak perlu mencari ke [Sumber Informasi]""" 
        else:
            prompt = f"Pertanyaan: {request.message}\nInstruksi: Berikan jawaban yang detail dan santai (gunakan kata aku/kamu)."
        # 4. FASE GENERASI STREAMING
        async def generate_stream():
            full_response = ""
            # astream() akan memuntahkan kata per kata secara real-time
            async for chunk in llm.astream(prompt):
                full_response += chunk
                yield chunk  # Kirim potongan teks ke frontend seketika
        
            # SIMPAN KE CACHE SETELAH SELESAI
            PROMPT_CACHE.append({
                "query": user_input,
                "embedding": query_embedding,
                "response": full_response
            })
            if len(PROMPT_CACHE) > 100: PROMPT_CACHE.pop(0)

        # Kembalikan response streaming ke frontend
        return StreamingResponse(generate_stream(), media_type="text/plain")
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Aduh, aku lagi pusing nih.")

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

        return {"message": f"Sip! sudah dibaca '{file.filename}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)