import os
import time
import math
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Query
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
    allow_origins=["*"],
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
    client_id: int

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    client_id: int = None

class ClientCreateRequest(BaseModel):
    name: str
    type: str

# 1. AUTH ENDPOINTS
@app.post("/api/auth/login")
async def login_endpoint(request: LoginRequest):
    user = database.get_user_by_credentials(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    return {
        "username": user["username"],
        "role": user["role"],
        "token": user["token"],
        "client_id": user["client_id"],
        "client_name": user["client_name"]
    }

# 2. CLIENT MANAGEMENT ENDPOINTS
@app.get("/api/clients")
async def list_clients(user=Depends(get_current_user)):
    return database.get_all_clients()

@app.post("/api/clients")
async def create_client(request: ClientCreateRequest, user=Depends(get_current_user)):
    if user["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Hanya Superadmin atau Admin yang dapat menambahkan client.")
    try:
        return database.add_client(request.name, request.type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/clients/{client_id}")
async def remove_client(client_id: int, user=Depends(get_current_user)):
    if user["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Hanya Superadmin atau Admin yang dapat menghapus client.")
    database.delete_client(client_id)
    # Hapus juga koleksi ChromaDB jika diinginkan
    try:
        vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, collection_name=f"client_{client_id}")
        vector_db.delete_collection()
    except Exception as e:
        print(f"Gagal menghapus koleksi ChromaDB client_{client_id}: {e}")
    return {"message": "Client berhasil dihapus."}

# 3. CHAT SESSION ENDPOINTS
@app.get("/api/chat/sessions")
async def get_sessions(user=Depends(get_current_user)):
    return database.get_chat_sessions(user["id"])

@app.post("/api/chat/sessions")
async def create_session(request: CreateSessionRequest, user=Depends(get_current_user)):
    return database.create_chat_session(user["id"], request.client_id, request.title)

@app.get("/api/chat/sessions/{session_id}")
async def get_session_messages(session_id: str, user=Depends(get_current_user)):
    sessions = database.get_chat_sessions(user["id"])
    session_ids = [s["id"] for s in sessions]
    
    if session_id not in session_ids and user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak ke sesi chat ini.")
        
    return database.get_chat_messages(session_id)

@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    success = database.delete_chat_session(session_id, user["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Gagal menghapus sesi. Pastikan Anda adalah pemiliknya.")
    return {"message": "Sesi chat berhasil dihapus."}

# 4. CHAT ENDPOINT
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    start_time = time.time()
    user_input = request.message.strip().lower()
    
    # Dapatkan info session untuk tahu client_id
    conn = database.get_db_connection()
    session = conn.execute("SELECT client_id FROM chat_sessions WHERE id = ?", (request.session_id,)).fetchone()
    conn.close()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")
    
    client_id = session["client_id"]
    
    # Simpan pertanyaan user ke SQLite DB
    database.save_message(request.session_id, "user", request.message)
    
    # Ubah teks input menjadi vektor
    query_embedding = embeddings.embed_query(user_input)
    
    # FASE SEMANTIC CACHING
    for cached_item in PROMPT_CACHE:
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        # Pastikan cache yang diambil berasal dari client_id yang sama
        if sim_score >= CACHE_THRESHOLD and cached_item.get("client_id") == client_id:
            cached_response = cached_item['response']
            database.save_message(request.session_id, "assistant", cached_response)
            
            async def stream_cache():
                words = cached_response.split(" ")
                for word in words:
                    yield word + " "
                    await asyncio.sleep(0.01) 
                yield f"\n\n*(⚡ Diambil dari Semantic Cache - {sim_score*100:.1f}% dalam {time.time() - start_time:.4f} detik)*"
            
            return StreamingResponse(stream_cache(), media_type="text/plain")

    try:
        llm = Ollama(
            model="qwen_slm",
            temperature=0.2,
            num_predict=2048,
            repeat_penalty=1.15
        )
        context = ""
        is_rag_mode = False

        # Inisialisasi ChromaDB spesifik untuk Client
        collection_name = f"client_{client_id}"
        if os.path.exists(persist_directory):
            try:
                vector_db = Chroma(
                    persist_directory=persist_directory, 
                    embedding_function=embeddings,
                    collection_name=collection_name
                )
                
                # Cari dokumen yang relevan dari koleksi client
                mmr_docs = vector_db.max_marginal_relevance_search(
                    request.message, k=3, fetch_k=10
                )
                if mmr_docs:
                    context = "\n\n".join([doc.page_content for doc in mmr_docs])
                    is_rag_mode = True
            except Exception as e:
                print(f"Gagal membaca ChromaDB koleksi {collection_name}: {e}")

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
                if full_response.strip():
                    try:
                        database.save_message(request.session_id, "assistant", full_response)
                    except Exception as db_err:
                        print(f"Gagal menyimpan pesan parsial: {db_err}")
                    
                    if not asyncio.current_task().cancelled():
                        PROMPT_CACHE.append({
                            "query": user_input,
                            "embedding": query_embedding,
                            "response": full_response,
                            "client_id": client_id
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

# 5. DOCUMENT MANAGEMENT ENDPOINTS (RAG Upload per Client)
@app.get("/api/documents/{client_id}")
async def list_documents(client_id: int, user=Depends(get_current_user)):
    # Cek otorisasi role
    if user["role"] == "admin_client" and user["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="Akses ditolak. Anda hanya dapat melihat dokumen milik client Anda.")
    return database.get_documents_by_client(client_id)

@app.post("/api/upload")
async def upload_endpoint(
    file: UploadFile = File(...), 
    client_id: int = Query(...),
    user=Depends(get_current_user)
):
    # Verifikasi hak akses upload
    if user["role"] not in ["superadmin", "admin", "admin_client"]:
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat mengunggah dokumen.")
    if user["role"] == "admin_client" and user["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="Anda hanya diizinkan mengunggah dokumen ke Client Anda sendiri.")
        
    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"./temp_uploads/{file.filename}"
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        # Tentukan tipe dokumen
        ext = os.path.splitext(file.filename)[1].lower()
        doc_type = "PDF"
        if ext in [".png", ".jpg", ".jpeg"]:
            doc_type = "GAMBAR"
        elif ext in [".mp4", ".avi", ".mkv"]:
            doc_type = "VIDEO"

        # Proses PDF ke VectorDB jika tipe adalah PDF
        if doc_type == "PDF":
            loader = PyPDFLoader(file_path)
            data = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=400,
                separators=["\n\n", "\n", ". ", " "]
            )
            chunks = text_splitter.split_documents(data)
            
            # Masukkan ke ChromaDB dengan Collection khusus Client
            collection_name = f"client_{client_id}"
            Chroma.from_documents(
                documents=chunks, 
                embedding=embeddings, 
                persist_directory=persist_directory,
                collection_name=collection_name
            )
        else:
            # Untuk Gambar / Video (Non-PDF), kita hanya catat metadatanya di SQLite 
            # agar muncul di daftar "Informasi Data" Dashboard
            pass
            
        os.remove(file_path)

        # Simpan metadata ke SQLite
        doc_metadata = database.add_document(client_id, file.filename, doc_type)

        global PROMPT_CACHE
        PROMPT_CACHE = [c for c in PROMPT_CACHE if c.get("client_id") != client_id]

        return {"message": f"Sip! sudah dibaca '{file.filename}' sebagai {doc_type}.", "doc": doc_metadata}
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Gagal proses file: {str(e)}")

@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: int, user=Depends(get_current_user)):
    # Ambil info dokumen dulu untuk verifikasi client_id
    conn = database.get_db_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")
        
    client_id = doc["client_id"]
    filename = doc["filename"]
    
    if user["role"] not in ["superadmin", "admin", "admin_client"]:
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    if user["role"] == "admin_client" and user["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="Anda hanya dapat menghapus dokumen milik client Anda.")
        
    # Hapus dari SQLite
    database.delete_document(doc_id)
    
    # Hapus dari ChromaDB
    try:
        collection_name = f"client_{client_id}"
        vector_db = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings,
            collection_name=collection_name
        )
        # Hapus berdasarkan metadata source file
        vector_db.delete(where={"source": filename})
    except Exception as e:
        print(f"Gagal menghapus vector dokumen {filename} dari ChromaDB: {e}")
        
    # Hapus cache client ini
    global PROMPT_CACHE
    PROMPT_CACHE = [c for c in PROMPT_CACHE if c.get("client_id") != client_id]
    
    return {"message": f"Dokumen '{filename}' berhasil dihapus."}

# 6. USER MANAGEMENT ENDPOINTS (Hanya Superadmin / Admin)
@app.get("/api/admin/users")
async def list_users(user=Depends(get_current_user)):
    if user["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Hanya Superadmin atau Admin yang memiliki akses ke daftar user.")
    return database.get_all_users()

@app.post("/api/admin/users")
async def create_user(request: UserCreateRequest, user=Depends(get_current_user)):
    if user["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    try:
        return database.add_user(request.username, request.password, request.role, request.client_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/users/{user_id}")
async def remove_user(user_id: int, user=Depends(get_current_user)):
    if user["role"] not in ["superadmin", "admin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    database.delete_user(user_id)
    return {"message": "User berhasil dihapus."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
