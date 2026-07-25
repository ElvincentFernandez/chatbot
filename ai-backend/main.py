import os
import json
import time
import math
import pickle
import asyncio
import threading
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Iterator, List, Optional, Sequence, Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_community.llms import LlamaCpp
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.stores import BaseStore

try:
    from langchain_classic.retrievers import ParentDocumentRetriever
except ImportError:
    from langchain.retrievers import ParentDocumentRetriever

import database  # modul SQLite: users, chat_sessions, messages (dari teman)

# =========================================================
# KONFIGURASI
# =========================================================
MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3.5-2B.Q4_K_M.gguf")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
PARENT_STORE_DIR = os.getenv("PARENT_STORE_DIR", "./parent_docstore")
DOCUMENTS_REGISTRY_PATH = os.getenv("DOCUMENTS_REGISTRY_PATH", "./documents_registry.json")
N_CTX = int(os.getenv("N_CTX", 8192))
N_THREADS = int(os.getenv("N_THREADS", os.cpu_count() or 4))
CACHE_THRESHOLD = 0.95
MAX_CACHE_ITEMS = 100

PARENT_CHUNK_SIZE = 800
PARENT_CHUNK_OVERLAP = 80
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50
RETRIEVER_K = 4

ALL_DOCS_CACHE_KEY = "__all__"

SYSTEM_PROMPT_RAG_STRICT = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.

[ATURAN WAJIB]
1. WAJIB gunakan kata "aku" dan "kamu", jangan kaku/formal.
2. ANTI-HALUSINASI: jawab HANYA berdasarkan [SUMBER INFORMASI] yang diberikan.
3. Jika [SUMBER INFORMASI] kosong atau tidak relevan, katakan terus terang kamu tidak menemukan jawabannya di dokumen.
4. Susun jawaban dengan rapi, gunakan bullet point kalau perlu, dan JANGAN mengulang poin yang sama."""

# Mode non-default (general_mode=True di request). TIDAK dipakai sebagai default
# supaya perilaku sistem tetap konsisten dengan Ruang Lingkup & evaluasi RAGAS
# (faithfulness) di skripsi. User bisa aktifkan manual per-request untuk obrolan
# santai di luar topik dokumen.
SYSTEM_PROMPT_RAG_FLEXIBLE = """Kamu adalah Qwen, asisten AI yang cerdas, santai, dan ramah. Gunakan kata "aku" dan "kamu" dalam menjawab, selalu dalam Bahasa Indonesia.

Berikut adalah informasi referensi dari dokumen (gunakan ini jika relevan dengan pertanyaan):
[Lihat SUMBER INFORMASI di bawah]

[ATURAN]
1. Jika pertanyaan bisa dijawab menggunakan [SUMBER INFORMASI], prioritaskan informasi tersebut.
2. Jika pertanyaan tidak ada hubungannya dengan [SUMBER INFORMASI] (sapaan umum, sejarah, sains, tokoh publik, dll), jawablah secara bebas dan santai berdasarkan pengetahuan umum yang kamu miliki."""

SYSTEM_PROMPT_CHAT = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.
Gunakan kata "aku" dan "kamu". Jawab dengan detail tapi tidak bertele-tele."""


# =========================================================
# DOCSTORE PERSISTEN UNTUK PARENT CHUNKS
# =========================================================
class LocalFileByteStore(BaseStore[str, object]):
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.pkl"

    def mget(self, keys: Sequence[str]) -> List[Optional[object]]:
        result = []
        for key in keys:
            p = self._path(key)
            result.append(pickle.loads(p.read_bytes()) if p.exists() else None)
        return result

    def mset(self, key_value_pairs: Sequence[Tuple[str, object]]) -> None:
        for key, value in key_value_pairs:
            self._path(key).write_bytes(pickle.dumps(value))

    def mdelete(self, keys: Sequence[str]) -> None:
        for key in keys:
            p = self._path(key)
            if p.exists():
                p.unlink()

    def yield_keys(self, *, prefix: Optional[str] = None) -> Iterator[str]:
        for p in self.root.glob("*.pkl"):
            key = p.stem
            if prefix is None or key.startswith(prefix):
                yield key


# =========================================================
# REGISTRY DOKUMEN
# =========================================================
def load_documents_registry() -> List[str]:
    if os.path.exists(DOCUMENTS_REGISTRY_PATH):
        with open(DOCUMENTS_REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_documents_registry(documents: List[str]) -> None:
    with open(DOCUMENTS_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)


# =========================================================
# STATE GLOBAL
# =========================================================
class AppState:
    embeddings: HuggingFaceEmbeddings = None
    llm: LlamaCpp = None
    retriever: ParentDocumentRetriever = None
    documents: List[str] = []
    prompt_cache: dict = {}
    cache_lock: asyncio.Lock = None
    inference_lock: threading.Lock = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: pakai sentence-transformers (bukan OllamaEmbeddings bge-m3) supaya
    # konsisten dengan Ruang Lingkup skripsi: "tanpa server model pihak ketiga
    # terpisah". Kalau mau ganti ke bge-m3 via Ollama, ganti blok ini saja.
    state.embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Model GGUF tidak ditemukan di '{MODEL_PATH}'. "
            f"Download dari https://huggingface.co/unsloth/Qwen3.5-2B-GGUF "
            f"(atau hasil fine-tuning sendiri, format UD-Q4_K_XL/q4_k_m)."
        )

    state.llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=0,
        n_batch=512,
        temperature=0.2,
        repeat_penalty=1.2,
        frequency_penalty=0.3,
        presence_penalty=0.3,
        last_n_tokens_size=512,
        max_tokens=1024,
        stop=["<|im_end|>", "<|im_start|>", "<think>"],
        streaming=True,
        verbose=os.getenv("VERBOSE_LLM", "false").lower() == "true",
    )

    vectorstore = Chroma(
        collection_name="rag_child_chunks",
        embedding_function=state.embeddings,
        persist_directory=CHROMA_DIR,
    )
    parent_docstore = LocalFileByteStore(PARENT_STORE_DIR)

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE, chunk_overlap=PARENT_CHUNK_OVERLAP
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE, chunk_overlap=CHILD_CHUNK_OVERLAP
    )

    state.retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=parent_docstore,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
        search_type="similarity",
        search_kwargs={"k": RETRIEVER_K},
    )

    state.documents = load_documents_registry()
    state.prompt_cache = {}
    state.cache_lock = asyncio.Lock()
    state.inference_lock = threading.Lock()

    yield


app = FastAPI(lifespan=lifespan)

# Bearer token (bukan cookie) -> allow_credentials tidak diperlukan.
# Origin dikembalikan ke spesifik (bukan "*") -- lebih aman untuk sistem yang
# sekarang punya login & role.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# AUTENTIKASI
# =========================================================
async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header otentikasi tidak valid atau kosong.")
    token = authorization.split(" ")[1]
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token tidak valid atau tidak dikenali.")
    return user


def require_role(user: dict, allowed_roles: List[str], action: str):
    if user["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Akses ditolak. {action} hanya untuk: {', '.join(allowed_roles)}.")


# =========================================================
# UTIL RAG (Parent Document Retriever + Semantic Cache per dokumen)
# =========================================================
def calculate_cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def build_prompt(system_prompt: str, user_message: str, context: str = "") -> str:
    if context:
        user_block = f"[SUMBER INFORMASI]:\n{context}\n\n[PERTANYAAN USER]:\n{user_message}"
    else:
        user_block = user_message
    return (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_block}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def retrieve_parent_docs(query_embedding, source_filter: Optional[str] = None):
    vectorstore = state.retriever.vectorstore
    search_kwargs = {"k": RETRIEVER_K}
    if source_filter:
        search_kwargs["filter"] = {"source": source_filter}
    child_docs = vectorstore.similarity_search_by_vector(query_embedding, **search_kwargs)
    id_key = state.retriever.id_key
    seen_ids = []
    for doc in child_docs:
        doc_id = doc.metadata.get(id_key)
        if doc_id and doc_id not in seen_ids:
            seen_ids.append(doc_id)
    if not seen_ids:
        return []
    parent_docs = state.retriever.docstore.mget(seen_ids)
    return [d for d in parent_docs if d is not None]


def remove_existing_document(filename: str) -> None:
    vectorstore = state.retriever.vectorstore
    id_key = state.retriever.id_key
    existing = vectorstore.get(where={"source": filename})
    if not existing or not existing.get("ids"):
        return
    child_ids = existing["ids"]
    metadatas = existing.get("metadatas") or []
    parent_ids = list({m.get(id_key) for m in metadatas if m and m.get(id_key)})
    vectorstore.delete(ids=child_ids)
    if parent_ids:
        state.retriever.docstore.mdelete(parent_ids)


def invalidate_document_cache(document: Optional[str]) -> None:
    """Hapus semua entri cache (mode strict & general) untuk 1 dokumen,
    plus cache mode 'semua dokumen' (karena hasil pencarian lintas-dokumen
    ikut berubah juga saat 1 dokumen di-upload/dihapus)."""
    key_base = document or ALL_DOCS_CACHE_KEY
    for base in {key_base, ALL_DOCS_CACHE_KEY}:
        state.prompt_cache.pop(f"{base}::strict", None)
        state.prompt_cache.pop(f"{base}::general", None)


async def stream_llm(prompt: str, stop_event: Optional[threading.Event] = None):
    """
    Generate streaming di thread terpisah (non-blocking terhadap event loop).
    stop_event memungkinkan generation dihentikan LEBIH AWAL secara nyata
    (bukan cuma berhenti nge-relay ke frontend) -- penting untuk fitur
    "Force Stop", supaya CPU tidak terus dipakai generate token yang
    tidak akan dipakai setelah user menekan Stop.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    SENTINEL = object()

    def worker():
        with state.inference_lock:
            try:
                for token in state.llm.stream(prompt):
                    if stop_event is not None and stop_event.is_set():
                        break
                    asyncio.run_coroutine_threadsafe(queue.put(token), loop).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put(e), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(SENTINEL), loop).result()

    threading.Thread(target=worker, daemon=True).start()

    while True:
        item = await queue.get()
        if item is SENTINEL:
            break
        if isinstance(item, Exception):
            raise item
        yield item


# =========================================================
# SCHEMAS
# =========================================================
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    document: Optional[str] = None  # nama file dokumen aktif; None = cari di semua dokumen
    general_mode: bool = False      # False (default) = ketat sesuai dokumen; True = boleh jawab umum

class SavePartialRequest(BaseModel):
    session_id: str
    content: str

class CreateSessionRequest(BaseModel):
    title: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str


# =========================================================
# 1. AUTH
# =========================================================
@app.post("/api/auth/login")
async def login_endpoint(request: LoginRequest):
    user = database.get_user_by_credentials(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    return {"username": user["username"], "role": user["role"], "token": user["token"]}


# =========================================================
# 2. CHAT SESSIONS (riwayat chat permanen)
# =========================================================
@app.get("/api/chat/sessions")
async def get_sessions(user=Depends(get_current_user)):
    return database.get_chat_sessions(user["id"])

@app.post("/api/chat/sessions")
async def create_session(request: CreateSessionRequest, user=Depends(get_current_user)):
    return database.create_chat_session(user["id"], request.title)

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


# =========================================================
# 3. CHAT (RAG + Semantic Cache per dokumen + riwayat SQLite + stop)
# =========================================================
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, http_request: Request, user=Depends(get_current_user)):
    start_time = time.time()
    user_input = request.message.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    if request.document and request.document not in state.documents:
        raise HTTPException(status_code=404, detail=f"Dokumen '{request.document}' tidak ditemukan.")

    database.save_message(request.session_id, "user", request.message)

    mode_suffix = "general" if request.general_mode else "strict"
    cache_key = f"{request.document or ALL_DOCS_CACHE_KEY}::{mode_suffix}"
    user_input_lower = user_input.lower()
    query_embedding = state.embeddings.embed_query(user_input_lower)

    # 1. CEK SEMANTIC CACHE (di-scope per dokumen aktif)
    async with state.cache_lock:
        cache_snapshot = list(state.prompt_cache.get(cache_key, []))

    best_match, best_score = None, 0.0
    for cached_item in cache_snapshot:
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD and sim_score > best_score:
            best_match, best_score = cached_item, sim_score

    if best_match:
        async def stream_cache():
            words = best_match["response"].split(" ")
            for word in words:
                yield word + " "
                await asyncio.sleep(0.01)
            yield f"\n\n*(⚡ Diambil dari Semantic Cache - {best_score*100:.1f}% mirip, {time.time() - start_time:.4f} detik)*"
            database.save_message(request.session_id, "assistant", best_match["response"])

        return StreamingResponse(stream_cache(), media_type="text/plain")

    # 2. RAG RETRIEVAL (scoped ke dokumen aktif kalau ada)
    context, is_rag_mode = "", False
    retrieval_start = time.time()
    try:
        parent_docs = retrieve_parent_docs(query_embedding, source_filter=request.document)
        if parent_docs:
            context = "\n\n".join(doc.page_content for doc in parent_docs)
            is_rag_mode = True
    except Exception as e:
        print(f"Retrieval gagal: {e}")
        traceback.print_exc()
    print(f"[TIMING] Retrieval: {time.time() - retrieval_start:.3f} detik")

    if is_rag_mode:
        system_prompt = SYSTEM_PROMPT_RAG_FLEXIBLE if request.general_mode else SYSTEM_PROMPT_RAG_STRICT
    else:
        system_prompt = SYSTEM_PROMPT_CHAT
    prompt = build_prompt(system_prompt, user_input, context)

    # 3. GENERATE STREAMING -- thread-safe, bisa di-stop lebih awal secara nyata
    stop_event = threading.Event()

    async def generate_stream():
        full_response = ""
        generation_start = time.time()
        first_token_time = None
        token_count = 0
        try:
            async for chunk in stream_llm(prompt, stop_event):
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"[TIMING] Waktu sampai token pertama: {first_token_time - generation_start:.3f} detik")
                full_response += chunk
                token_count += 1
                yield chunk

                # Deteksi kalau user menekan Stop (fetch di-abort di frontend)
                # -> hentikan thread generate juga, bukan cuma berhenti nge-relay.
                if await http_request.is_disconnected():
                    stop_event.set()
                    break
        except Exception as e:
            print(f"Error saat generate: {e}")
            traceback.print_exc()
            yield "\n\nAduh, aku lagi pusing nih."
        finally:
            elapsed = time.time() - generation_start
            if elapsed > 0:
                print(f"[TIMING] Total generate: {elapsed:.3f} detik untuk ~{token_count} chunk "
                      f"(~{token_count / elapsed:.2f} chunk/detik)")
            if full_response.strip():
                try:
                    database.save_message(request.session_id, "assistant", full_response)
                except Exception as db_err:
                    print(f"Gagal menyimpan pesan: {db_err}")

                # Cache cuma diisi kalau generate selesai NORMAL (bukan di-stop),
                # supaya cache tidak pernah menyimpan jawaban yang terpotong.
                if not stop_event.is_set():
                    async with state.cache_lock:
                        bucket = state.prompt_cache.setdefault(cache_key, [])
                        bucket.append({
                            "query": user_input_lower,
                            "embedding": query_embedding,
                            "response": full_response,
                        })
                        if len(bucket) > MAX_CACHE_ITEMS:
                            bucket.pop(0)

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


# =========================================================
# 4. DOKUMEN RAG (upload: admin/superadmin, lihat: semua yang login)
# =========================================================
@app.post("/api/upload")
async def upload_endpoint(file: UploadFile = File(...), user=Depends(get_current_user)):
    require_role(user, ["admin", "superadmin"], "Upload dokumen")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"./temp_uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        loader = PyMuPDFLoader(file_path)
        documents = loader.load()
        if not documents:
            raise HTTPException(status_code=422, detail="Tidak ada teks yang bisa diekstrak dari PDF ini.")

        for doc in documents:
            doc.metadata["source"] = file.filename

        remove_existing_document(file.filename)
        state.retriever.add_documents(documents)

        os.remove(file_path)

        if file.filename not in state.documents:
            state.documents.append(file.filename)
            save_documents_registry(state.documents)

        async with state.cache_lock:
            invalidate_document_cache(file.filename)

        return {"message": f"Sip! sudah dibaca '{file.filename}' ({len(documents)} halaman)."}
    except HTTPException:
        raise
    except Exception as e:
        print("=== ERROR SAAT UPLOAD PDF ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")


@app.get("/api/documents")
async def list_documents(user=Depends(get_current_user)):
    return {"documents": state.documents}


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str, user=Depends(get_current_user)):
    require_role(user, ["admin", "superadmin"], "Hapus dokumen")

    if filename not in state.documents:
        raise HTTPException(status_code=404, detail=f"Dokumen '{filename}' tidak ditemukan.")

    remove_existing_document(filename)
    state.documents.remove(filename)
    save_documents_registry(state.documents)

    async with state.cache_lock:
        invalidate_document_cache(filename)

    return {"message": f"Dokumen '{filename}' sudah dihapus."}


# =========================================================
# 5. MANAJEMEN USER (superadmin only)
# =========================================================
@app.get("/api/admin/users")
async def list_users(user=Depends(get_current_user)):
    require_role(user, ["superadmin"], "Melihat daftar user")
    return database.get_all_users()

@app.post("/api/admin/users")
async def create_user(request: UserCreateRequest, user=Depends(get_current_user)):
    require_role(user, ["superadmin"], "Menambah user")
    try:
        return database.add_user(request.username, request.password, request.role)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/admin/users/{user_id}")
async def remove_user(user_id: int, user=Depends(get_current_user)):
    require_role(user, ["superadmin"], "Menghapus user")
    database.delete_user(user_id)
    return {"message": "User berhasil dihapus."}


@app.get("/api/health")
async def health():
    total_cache_items = sum(len(v) for v in state.prompt_cache.values())
    return {
        "status": "ok",
        "rag_ready": os.path.exists(CHROMA_DIR) and bool(os.listdir(CHROMA_DIR)),
        "documents": state.documents,
        "cache_size": total_cache_items,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
