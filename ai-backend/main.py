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

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_community.llms import LlamaCpp
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.stores import BaseStore

# ParentDocumentRetriever pindah lokasi tergantung versi langchain yang
# terpasang. Coba lokasi baru (langchain_classic) dulu, fallback ke lokasi lama.
try:
    from langchain_classic.retrievers import ParentDocumentRetriever
except ImportError:
    from langchain.retrievers import ParentDocumentRetriever

# =========================================================
# KONFIGURASI
# =========================================================
MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3.5-2B-UD-Q4_K_XL.gguf")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
PARENT_STORE_DIR = os.getenv("PARENT_STORE_DIR", "./parent_docstore")
DOCUMENTS_REGISTRY_PATH = os.getenv("DOCUMENTS_REGISTRY_PATH", "./documents_registry.json")
N_CTX = int(os.getenv("N_CTX", 8192))
N_THREADS = int(os.getenv("N_THREADS", os.cpu_count() or 4))
CACHE_THRESHOLD = 0.95  # 95% mirip baru dianggap sama
MAX_CACHE_ITEMS = 100

# Parent = konteks besar yang dikirim ke LLM. Child = potongan kecil yang
# dicari lewat similarity search (lebih presisi karena granular).
PARENT_CHUNK_SIZE = 800
PARENT_CHUNK_OVERLAP = 80
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50
RETRIEVER_K = 4  # jumlah child hit yang dicari; parent hasil dedup bisa lebih sedikit

# Key cache untuk mode "semua dokumen" (tidak ada dokumen aktif spesifik dipilih)
ALL_DOCS_CACHE_KEY = "__all__"

SYSTEM_PROMPT_RAG = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.

[ATURAN WAJIB]
1. WAJIB gunakan kata "aku" dan "kamu", jangan kaku/formal.
2. ANTI-HALUSINASI: jawab HANYA berdasarkan [SUMBER INFORMASI] yang diberikan.
3. Jika [SUMBER INFORMASI] kosong atau tidak relevan, katakan terus terang kamu tidak menemukan jawabannya di dokumen.
4. Susun jawaban dengan rapi, gunakan bullet point kalau perlu, dan JANGAN mengulang poin yang sama."""

SYSTEM_PROMPT_CHAT = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.
Gunakan kata "aku" dan "kamu". Jawab dengan detail tapi tidak bertele-tele."""


# =========================================================
# DOCSTORE PERSISTEN UNTUK PARENT CHUNKS
# =========================================================
class LocalFileByteStore(BaseStore[str, object]):
    """
    ParentDocumentRetriever di versi langchain_classic ini menyimpan objek
    Document langsung ke docstore (bukan bytes mentah seperti versi lama).
    Ini versi sederhana yang persist ke disk pakai pickle, supaya dokumen
    yang sudah di-upload tidak perlu di-upload ulang tiap server restart.
    """

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
# REGISTRY DOKUMEN (daftar nama file yang sudah di-upload)
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
# STATE GLOBAL (diisi saat startup lewat lifespan)
# =========================================================
class AppState:
    embeddings: HuggingFaceEmbeddings = None
    llm: LlamaCpp = None
    retriever: ParentDocumentRetriever = None
    documents: List[str] = []
    # Cache di-scope PER DOKUMEN (key = nama file, atau ALL_DOCS_CACHE_KEY
    # kalau user tidak memilih dokumen aktif tertentu). Ini supaya jawaban
    # yang di-cache untuk 1 dokumen tidak "nyasar" dipakai untuk dokumen lain
    # yang pertanyaannya kebetulan mirip secara semantik.
    prompt_cache: dict = {}
    cache_lock: asyncio.Lock = None
    inference_lock: threading.Lock = None  # llama.cpp di CPU tidak thread-safe


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Model embedding: ringan & bagus untuk Bahasa Indonesia (multilingual)
    state.embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(
            f"Model GGUF tidak ditemukan di '{MODEL_PATH}'. "
            f"Download dulu dari https://huggingface.co/unsloth/Qwen3.5-2B-GGUF "
            f"(disarankan quant UD-Q4_K_XL untuk keseimbangan speed/kualitas)."
        )

    state.llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=0,        # ganti ke -1 kalau mau full offload ke GPU
        # Default n_batch LangChain cuma 8 - ini penyebab utama waktu
        # "sampai token pertama" jadi lama (prompt/context RAG diproses
        # nyaris per-8-token). Dinaikkan supaya prompt processing jauh
        # lebih cepat, terutama karena context RAG kita cukup panjang.
        n_batch=512,
        temperature=0.2,
        repeat_penalty=1.2,
        frequency_penalty=0.3,
        presence_penalty=0.3,
        # ROOT CAUSE dari respons yang loop tak berhenti: default
        # last_n_tokens_size cuma 64 token, jadi repeat_penalty "lupa"
        # begitu satu blok pengulangan lebih panjang dari itu. Dinaikkan
        # jauh lebih besar supaya penalti tetap "mengingat" pengulangan
        # panjang.
        last_n_tokens_size=512,
        max_tokens=1024,       # dinaikkan lagi karena repeat-loop-nya sudah fix di last_n_tokens_size
        stop=["<|im_end|>", "<|im_start|>", "<think>"],
        streaming=True,
        verbose=os.getenv("VERBOSE_LLM", "false").lower() == "true",
    )

    # ============ PARENT DOCUMENT RETRIEVER ============
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

    yield  # aplikasi jalan di sini

    # cleanup kalau perlu (llama.cpp handle dari python GC sudah cukup)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# UTIL
# =========================================================
def calculate_cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def build_prompt(system_prompt: str, user_message: str, context: str = "") -> str:
    """Format prompt pakai ChatML, sesuai chat template Qwen."""
    if context:
        user_block = f"[SUMBER INFORMASI]:\n{context}\n\n[PERTANYAAN USER]:\n{user_message}"
    else:
        user_block = user_message

    return (
        f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_block}<|im_end|>\n"
        # Pre-fill blok <think> kosong supaya model skip fase reasoning
        # dan langsung generate jawaban (lebih reliable daripada
        # --chat-template-kwargs enable_thinking:false, yang punya bug
        # dan sering gagal mematikan thinking di Qwen3.5).
        f"<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def retrieve_parent_docs(query_embedding, source_filter: Optional[str] = None):
    """
    Ambil dokumen PARENT yang relevan lewat similarity search di level
    CHILD chunk (pakai embedding yang SUDAH dihitung sebelumnya untuk cek
    cache - tidak re-embed query lagi), lalu dedup ke parent lewat doc_id.

    source_filter (opsional): scope pencarian ke 1 dokumen aktif saja,
    berdasarkan metadata "source" yang di-set saat upload. Ini mencegah
    cross-document interference kalau ada banyak dokumen ter-upload
    sekaligus di vectorstore yang sama.
    """
    vectorstore = state.retriever.vectorstore
    search_kwargs = {"k": RETRIEVER_K}
    if source_filter:
        search_kwargs["filter"] = {"source": source_filter}

    child_docs = vectorstore.similarity_search_by_vector(query_embedding, **search_kwargs)

    id_key = state.retriever.id_key  # default "doc_id"
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
    """
    Hapus semua child chunk (vectorstore) + parent chunk (docstore) milik
    sebuah file, supaya kalau file dengan nama sama di-upload ulang, isinya
    tidak numpuk duplikat di database.
    """
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


async def stream_llm(prompt: str):
    """
    Jalankan llm.stream() (sync, blocking) di thread terpisah supaya
    tidak nge-block event loop FastAPI, dan kirim token lewat asyncio.Queue.
    inference_lock memastikan hanya 1 generate berjalan di satu waktu
    (llama.cpp CPU context tidak aman dipakai concurrent).
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    SENTINEL = object()

    def worker():
        with state.inference_lock:
            try:
                for token in state.llm.stream(prompt):
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
class ChatRequest(BaseModel):
    message: str
    document: Optional[str] = None  # nama file dokumen aktif; None = cari di semua dokumen


# =========================================================
# ENDPOINTS
# =========================================================
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    start_time = time.time()
    user_input = request.message.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")

    if request.document and request.document not in state.documents:
        raise HTTPException(status_code=404, detail=f"Dokumen '{request.document}' tidak ditemukan.")

    cache_key = request.document or ALL_DOCS_CACHE_KEY

    user_input_lower = user_input.lower()
    query_embedding = state.embeddings.embed_query(user_input_lower)

    # 1. CEK SEMANTIC CACHE (di-scope per dokumen aktif)
    async with state.cache_lock:
        cache_snapshot = list(state.prompt_cache.get(cache_key, []))

    best_match = None
    best_score = 0.0
    for cached_item in cache_snapshot:
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD and sim_score > best_score:
            best_match = cached_item
            best_score = sim_score

    if best_match:
        async def stream_cache():
            words = best_match["response"].split(" ")
            for word in words:
                yield word + " "
                await asyncio.sleep(0.01)
            yield f"\n\n*(⚡ Diambil dari Semantic Cache - {best_score*100:.1f}% mirip, {time.time() - start_time:.4f} detik)*"

        return StreamingResponse(stream_cache(), media_type="text/plain")

    # 2. RAG RETRIEVAL
    #    - Similarity search jalan di level CHILD chunk (kecil, presisi),
    #      pakai embedding yang sudah dihitung di atas (tidak re-embed lagi).
    #    - Yang dikembalikan adalah dokumen PARENT (besar, konteks utuh).
    #    - Kalau beberapa child match ke parent yang sama, parent itu
    #      cuma dikembalikan SEKALI -> dedup otomatis di level retrieval.
    #    - Kalau request.document di-set, pencarian di-scope ke dokumen itu
    #      saja -> mencegah cross-document interference.
    context = ""
    is_rag_mode = False
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
        prompt = build_prompt(SYSTEM_PROMPT_RAG, user_input, context)
    else:
        prompt = build_prompt(SYSTEM_PROMPT_CHAT, user_input)

    # 3. GENERATE STREAMING (non-blocking, thread-safe)
    async def generate_stream():
        full_response = ""
        generation_start = time.time()
        first_token_time = None
        token_count = 0
        try:
            async for chunk in stream_llm(prompt):
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"[TIMING] Waktu sampai token pertama: {first_token_time - generation_start:.3f} detik")
                full_response += chunk
                token_count += 1
                yield chunk
        except Exception as e:
            print(f"Error saat generate: {e}")
            traceback.print_exc()
            yield "\n\nAduh, aku lagi pusing nih."
            return

        total_gen_time = time.time() - generation_start
        print(f"[TIMING] Total generate: {total_gen_time:.3f} detik untuk ~{token_count} chunk "
              f"(~{token_count / total_gen_time:.2f} chunk/detik)")

        async with state.cache_lock:
            bucket = state.prompt_cache.setdefault(cache_key, [])
            bucket.append(
                {
                    "query": user_input_lower,
                    "embedding": query_embedding,
                    "response": full_response,
                }
            )
            if len(bucket) > MAX_CACHE_ITEMS:
                bucket.pop(0)

    return StreamingResponse(generate_stream(), media_type="text/plain")


@app.post("/api/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang didukung.")

    try:
        os.makedirs("temp_uploads", exist_ok=True)
        file_path = f"./temp_uploads/{file.filename}"

        with open(file_path, "wb") as f:
            f.write(await file.read())

        # PyMuPDF loader - lebih cepat & lebih akurat extract layout-nya dibanding pypdf
        loader = PyMuPDFLoader(file_path)
        documents = loader.load()

        if not documents:
            raise HTTPException(status_code=422, detail="Tidak ada teks yang bisa diekstrak dari PDF ini.")

        # Set metadata "source" ke nama file asli (bukan path temp) supaya
        # filter per-dokumen konsisten walau folder temp_uploads berubah,
        # dan supaya bisa dipakai sebagai identifier stabil di /api/documents.
        for doc in documents:
            doc.metadata["source"] = file.filename

        # Kalau file dengan nama sama pernah di-upload, hapus dulu chunk
        # lamanya supaya tidak numpuk duplikat di vectorstore/docstore.
        remove_existing_document(file.filename)

        # ParentDocumentRetriever yang urus parent+child splitting dan
        # nyimpen ke vectorstore + docstore sekaligus.
        state.retriever.add_documents(documents)

        os.remove(file_path)

        if file.filename not in state.documents:
            state.documents.append(file.filename)
            save_documents_registry(state.documents)

        # Cuma bersihin cache milik dokumen ini + cache mode "semua dokumen"
        # (karena hasil pencarian lintas-dokumen bisa berubah juga).
        # Cache dokumen LAIN yang tidak terlibat tetap aman, tidak perlu
        # di-invalidate.
        async with state.cache_lock:
            state.prompt_cache.pop(file.filename, None)
            state.prompt_cache.pop(ALL_DOCS_CACHE_KEY, None)

        return {"message": f"Sip! sudah dibaca '{file.filename}' ({len(documents)} halaman)."}
    except HTTPException:
        raise
    except Exception as e:
        print("=== ERROR SAAT UPLOAD PDF ===")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal proses PDF: {str(e)}")


@app.get("/api/documents")
async def list_documents():
    return {"documents": state.documents}


@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    if filename not in state.documents:
        raise HTTPException(status_code=404, detail=f"Dokumen '{filename}' tidak ditemukan.")

    remove_existing_document(filename)

    state.documents.remove(filename)
    save_documents_registry(state.documents)

    async with state.cache_lock:
        state.prompt_cache.pop(filename, None)
        state.prompt_cache.pop(ALL_DOCS_CACHE_KEY, None)

    return {"message": f"Dokumen '{filename}' sudah dihapus."}


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
