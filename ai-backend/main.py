"""
main.py -- FastAPI app: routing, autentikasi, dan manajemen sesi chat.

Semua logic RAG (ingestion, retrieval, semantic cache, generation) ada di
rag.py -- file ini cuma orchestrator: terima request HTTP, cek auth, simpan
riwayat chat ke database, panggil fungsi-fungsi di rag.py, dan kembalikan
response (termasuk streaming).
"""
import os
import time
import asyncio
import threading
import traceback
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import database
import rag
from access import validate_upload_access


# =========================================================
# LIFESPAN -- inisialisasi resource RAG saat server startup
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await rag.initialize()
    yield


app = FastAPI(lifespan=lifespan)

# Bearer token (bukan cookie) -> allow_credentials tidak diperlukan.
# Origin dikembalikan ke spesifik (bukan "*") -- lebih aman untuk sistem yang
# sekarang punya login & role.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper Dependency untuk Autentikasi
async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header otentikasi tidak valid atau kosong.")
    token = authorization.split(" ")[1]
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token tidak valid atau tidak dikenali.")
    return user


def require_role(user: dict, allowed_roles: list, action: str):
    if user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Akses ditolak. {action} hanya untuk: {', '.join(allowed_roles)}.")


# =========================================================
# SCHEMAS
# =========================================================
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    document: Optional[str] = None
    general_mode: bool = False

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

# 3. CHAT (Hybrid RAG + Semantic Cache per dokumen + riwayat SQLite + stop)
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    start_time = time.time()
    user_input = request.message.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")

    sessions = database.get_chat_sessions(user["id"])
    session_ids = [s["id"] for s in sessions]
    if request.session_id not in session_ids and user["role"] not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Akses ditolak ke sesi chat ini.")

    conn = database.get_db_connection()
    session = conn.execute("SELECT client_id FROM chat_sessions WHERE id = ?", (request.session_id,)).fetchone()
    conn.close()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi chat tidak ditemukan.")

    client_id = session["client_id"]
    if request.document and request.document not in rag.state.documents:
        raise HTTPException(status_code=404, detail=f"Dokumen '{request.document}' tidak ditemukan.")

    database.save_message(request.session_id, "user", request.message)

    cache_key = rag.make_cache_key(request.document, request.general_mode)
    user_input_lower = user_input.lower()
    query_embedding = rag.state.embeddings.embed_query(user_input_lower)

    # 1. CEK SEMANTIC CACHE (di-scope per dokumen aktif)
    best_match, best_score = await rag.check_cache(cache_key, user_input_lower, query_embedding)

    if best_match:
        async def stream_cache():
            words = best_match["response"].split(" ")
            for word in words:
                yield word + " "
                await asyncio.sleep(0.01)
            yield f"\n\n*(⚡ Diambil dari Semantic Cache - {best_score*100:.1f}% mirip, {time.time() - start_time:.4f} detik)*"
            database.save_message(request.session_id, "assistant", best_match["response"])

        return StreamingResponse(stream_cache(), media_type="text/plain")

    # 2. HYBRID RAG RETRIEVAL (scoped ke dokumen aktif kalau ada)
    retrieval_start = time.time()
    context, is_rag_mode = rag.get_context(user_input_lower, query_embedding, request.document)
    print(f"[TIMING] Retrieval: {time.time() - retrieval_start:.3f} detik")

    system_prompt = rag.select_system_prompt(is_rag_mode, request.general_mode)
    prompt = rag.build_prompt(system_prompt, user_input, context)

    stop_event = threading.Event()

    async def generate_stream():
        full_response = ""
        generation_start = time.time()
        first_token_time = None
        token_count = 0
        try:
            # Send a tiny initial chunk to flush headers and trigger browser streaming
            yield "\n"
            async for chunk in rag.stream_llm(prompt, stop_event):
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"[TIMING] Waktu sampai token pertama: {first_token_time - generation_start:.3f} detik")
                full_response += chunk
                token_count += 1
                if chunk:
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

                if not stop_event.is_set():
                    await rag.store_cache(cache_key, user_input_lower, query_embedding, full_response)

    return StreamingResponse(generate_stream(), media_type="text/plain")

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
    client_id: Optional[int] = Query(None),
    user=Depends(get_current_user)
):
    require_role(user, ["admin", "superadmin", "admin_client"], "Upload dokumen")
    client_id = validate_upload_access(user, client_id)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    file_path = f"./temp_uploads/{file.filename}"
    try:
        os.makedirs("temp_uploads", exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        n_chunks = rag.ingest_pdf(file_path, file.filename)
        doc_metadata = database.add_document(client_id, file.filename, "PDF")

        return {
            "message": f"Sip! sudah dibaca '{file.filename}' ({n_chunks} halaman/potongan).",
            "doc": doc_metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print("=== ERROR SAAT UPLOAD PDF ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

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

# 5. DOCUMENT & USER MANAGEMENT ENDPOINTS
@app.get("/api/documents")
async def list_documents(user=Depends(get_current_user)):
    return {"documents": rag.state.documents}


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

@app.get("/api/health")
async def health():
    total_cache_items = sum(len(v) for v in rag.state.prompt_cache.values())
    return {
        "status": "ok",
        "rag_ready": os.path.exists(rag.CHROMA_DIR) and bool(os.listdir(rag.CHROMA_DIR)),
        "documents": rag.state.documents,
        "bm25_indexed_chunks": len(rag.state.bm25_index.doc_ids) if rag.state.bm25_index else 0,
        "cache_size": total_cache_items,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
