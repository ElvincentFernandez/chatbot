import os
import time
import math
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Import database module
import database

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
    allow_origins=["*"], # Izinkan semua origin untuk development, atau set spesifik "http://localhost:3000"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inisialisasi model embedding
embeddings = OllamaEmbeddings(model="bge-m3")
persist_directory = "./chroma_db"

# Helper Dependency untuk Autentikasi
async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header otentikasi tidak valid atau kosong.")
    token = authorization.split(" ")[1]
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token tidak valid atau tidak dikenali.")
    return user

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    session_id: str

class SavePartialRequest(BaseModel):
    session_id: str
    content: str

class CreateSessionRequest(BaseModel):
    title: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str

# 1. AUTH ENDPOINTS
@app.post("/api/auth/login")
async def login_endpoint(request: LoginRequest):
    user = database.get_user_by_credentials(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    return {
        "username": user["username"],
        "role": user["role"],
        "token": user["token"]
    }


# 2. CHAT SESSION ENDPOINTS
@app.get("/api/chat/sessions")
async def get_sessions(user=Depends(get_current_user)):
    return database.get_chat_sessions(user["id"])

@app.post("/api/chat/sessions")
async def create_session(request: CreateSessionRequest, user=Depends(get_current_user)):
    return database.create_chat_session(user["id"], request.title)

@app.get("/api/chat/sessions/{session_id}")
async def get_session_messages(session_id: str, user=Depends(get_current_user)):
    # Pastikan session ini milik user atau user adalah admin/superadmin
    sessions = database.get_chat_sessions(user["id"])
    session_ids = [s["id"] for s in sessions]
    
    # Kecuali admin/superadmin yang bisa melihat session siapa saja jika dibutuhkan
    if session_id not in session_ids and user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak ke sesi chat ini.")
        
    return database.get_chat_messages(session_id)

@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    success = database.delete_chat_session(session_id, user["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Gagal menghapus sesi. Pastikan Anda adalah pemiliknya.")
    return {"message": "Sesi chat berhasil dihapus."}

# 3. CHAT ENDPOINT
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    start_time = time.time()
    user_input = request.message.strip().lower()
    
    # Simpan pertanyaan user ke SQLite DB
    database.save_message(request.session_id, "user", request.message)
    
    # Ubah teks input menjadi vektor
    query_embedding = embeddings.embed_query(user_input)
    
    # FASE SEMANTIC CACHING
    for cached_item in PROMPT_CACHE:
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD:
            cached_response = cached_item['response']
            # Simpan jawaban cache ke SQLite DB
            database.save_message(request.session_id, "assistant", cached_response)
            
            async def stream_cache():
                words = cached_response.split(" ")
                for word in words:
                    yield word + " "
                    await asyncio.sleep(0.01) 
                yield f"\n\n*(⚡ Diambil dari Semantic Cache - {sim_score*100:.1f}% dalam {time.time() - start_time:.4f} detik)*"
            
            return StreamingResponse(stream_cache(), media_type="text/plain")

    try:
        # SETUP MODEL & RAG
        llm = Ollama(
            model="qwen_slm",
            temperature=0.2,
            num_predict=2048,
            repeat_penalty=1.15
        )
        context = ""
        is_rag_mode = False

        if os.path.exists(persist_directory) and os.listdir(persist_directory):
            try:
                vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
                mmr_docs = vector_db.max_marginal_relevance_search(
                    request.message, k=3, fetch_k=10
                )
                if mmr_docs:
                    context = "\n\n".join([doc.page_content for doc in mmr_docs])
                    is_rag_mode = True
            except Exception as e:
                print(f"Database ada tapi gagal dibaca: {e}")

        # STRUKTUR PROMPT (Dibuat fleksibel: memprioritaskan dokumen, tetapi bebas menjawab secara umum jika di luar topik)
        if is_rag_mode:
            prompt = f"""Kamu adalah qwen, asisten AI yang cerdas, santai, dan ramah. Gunakan kata "aku" dan "kamu" dalam menjawab.

Berikut adalah informasi referensi dari dokumen kami (gunakan ini jika relevan dengan pertanyaan):
{context}

Pertanyaan: {request.message}

Aturan:
1. Jika pertanyaan bisa dijawab menggunakan informasi referensi di atas, prioritaskan informasi tersebut.
2. Jika pertanyaan tidak ada hubungannya dengan informasi referensi di atas (misalnya sapaan umum, pertanyaan umum sejarah, sains, tokoh, dll), jawablah secara bebas dan santai berdasarkan pengetahuan umum yang kamu miliki."""
        else:
            prompt = f"Pertanyaan: {request.message}\nInstruksi: Jawablah dengan cerdas, santai, dan gunakan kata aku/kamu."
            
        async def generate_stream():
            full_response = ""
            try:
                async for chunk in llm.astream(prompt):
                    full_response += chunk
                    yield chunk
            except asyncio.CancelledError:
                print("Streaming dihentikan oleh user / koneksi terputus.")
                raise
            finally:
                # Simpan jawaban yang berhasil digenerate sejauh ini ke SQLite DB
                if full_response.strip():
                    try:
                        database.save_message(request.session_id, "assistant", full_response)
                    except Exception as db_err:
                        print(f"Gagal menyimpan pesan parsial: {db_err}")
                    
                    # Simpan ke cache jika selesai secara normal
                    if not asyncio.current_task().cancelled():
                        PROMPT_CACHE.append({
                            "query": user_input,
                            "embedding": query_embedding,
                            "response": full_response
                        })
                        if len(PROMPT_CACHE) > 100: PROMPT_CACHE.pop(0)

        return StreamingResponse(generate_stream(), media_type="text/plain")
        
    except Exception as e:
        error_msg = f"Aduh, aku lagi pusing nih. (Error: {str(e)})"
        try:
            database.save_message(request.session_id, "assistant", error_msg)
        except:
            pass
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/chat/save_partial")
async def save_partial_endpoint(request: SavePartialRequest, user=Depends(get_current_user)):
    if request.content.strip():
        try:
            database.save_message(request.session_id, "assistant", request.content)
            return {"status": "saved"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan pesan: {str(e)}")
    return {"status": "empty"}

# 4. RAG DOCUMENT UPLOAD (Hanya Admin / Superadmin)
@app.post("/api/upload")
async def upload_endpoint(file: UploadFile = File(...), user=Depends(get_current_user)):
    if user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak. Hanya Admin atau Superadmin yang boleh mengupload dokumen.")
        
    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"./temp_uploads/{file.filename}"
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        loader = PyPDFLoader(file_path)
        data = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=400,
            separators=["\n\n", "\n", ". ", " "]
        )
        chunks = text_splitter.split_documents(data)
        
        Chroma.from_documents(
            documents=chunks, 
            embedding=embeddings, 
            persist_directory=persist_directory
        )
        
        os.remove(file_path)

        global PROMPT_CACHE
        PROMPT_CACHE.clear()

        return {"message": f"Sip! sudah dibaca '{file.filename}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")

# 5. USER MANAGEMENT ENDPOINTS (Hanya Superadmin)
@app.get("/api/admin/users")
async def list_users(user=Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Hanya Superadmin yang memiliki akses ke daftar user.")
    return database.get_all_users()

@app.post("/api/admin/users")
async def create_user(request: UserCreateRequest, user=Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Hanya Superadmin yang dapat menambahkan user baru.")
    try:
        return database.add_user(request.username, request.password, request.role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/users/{user_id}")
async def remove_user(user_id: int, user=Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Hanya Superadmin yang dapat menghapus user.")
    database.delete_user(user_id)
    return {"message": "User berhasil dihapus."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)