"""
rag.py -- Sistem RAG (Retrieval-Augmented Generation) untuk chatbot.

Struktur file ini sengaja disusun mengikuti alur pipeline RAG dari awal sampai
akhir, supaya gampang dipetakan ke Bab 4 (Implementasi Sistem):

    1. KONFIGURASI
    2. STATE & PENYIMPANAN (docstore, registry dokumen)
    3. DATA INGESTION (load PDF, deteksi tabel, chunking, indexing)
    4. RETRIEVAL (hybrid dense + BM25, reciprocal rank fusion)
    5. SEMANTIC PROMPT CACHE
    6. PROMPT CONSTRUCTION & GENERATION (LLM streaming)
    7. INISIALISASI (dipanggil dari lifespan() di main.py)

main.py TIDAK mengandung logic RAG sama sekali -- dia cuma pasang endpoint
FastAPI, urus autentikasi & sesi chat (database.py), lalu panggil fungsi-fungsi
di modul ini.
"""
import os
import re
import json
import math
import pickle
import asyncio
import threading
import traceback
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple

from langchain_community.llms import LlamaCpp
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF low-level API - sudah termasuk paket 'pymupdf' yang sudah ada
from langchain_core.stores import BaseStore
from rank_bm25 import BM25Okapi

try:
    from langchain_classic.retrievers import ParentDocumentRetriever
except ImportError:
    from langchain.retrievers import ParentDocumentRetriever


# =========================================================
# 1. KONFIGURASI
# =========================================================
MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3.5-2B.Q4_K_M.gguf")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
PARENT_STORE_DIR = os.getenv("PARENT_STORE_DIR", "./parent_docstore")
DOCUMENTS_REGISTRY_PATH = os.getenv("DOCUMENTS_REGISTRY_PATH", "./documents_registry.json")
N_CTX = int(os.getenv("N_CTX", 8192))
N_THREADS = int(os.getenv("N_THREADS", os.cpu_count() or 4))

# UPDATE: diturunkan dari 0.95 -> 0.85, berdasarkan eksperimen tuning empiris
# (13 pasangan uji should-hit/should-not-hit, model embedding yang dites:
# paraphrase-multilingual-MiniLM-L12-v2 vs LazarusNLP/all-indo-e5-small-v4
# vs paraphrase-multilingual-mpnet-base-v2). Hasilnya: model embedding TETAP
# yang lama (kandidat pengganti tidak lebih baik secara diskriminatif di titik
# operasi 0 false-positive), tapi threshold 0.95 terlalu ketat -- di 0.85,
# recall naik dari ~14% ke ~57% pada data uji, dengan 0 false positive.
CACHE_THRESHOLD = 0.85
MAX_CACHE_ITEMS = 100

PARENT_CHUNK_SIZE = 800
PARENT_CHUNK_OVERLAP = 80
CHILD_CHUNK_SIZE = 300
CHILD_CHUNK_OVERLAP = 50

# --- Parameter retrieval hybrid (bisa dituning tanpa training ulang) ---
RETRIEVER_K = 6            # jumlah kandidat child chunk yang diambil TIAP retriever (dense & BM25)
DENSE_SCORE_THRESHOLD = float(os.getenv("DENSE_SCORE_THRESHOLD", 0.35))
# ^ buang kandidat dense yang similarity-nya di bawah ini, supaya context tidak
#   selalu "dipaksa" penuh RETRIEVER_K walau sebagian tidak relevan (penyebab
#   utama cross-contamination di evaluasi awal).
TOP_N_PARENTS = int(os.getenv("TOP_N_PARENTS", 4))
# ^ jumlah parent doc final yang dikirim ke LLM setelah fusion, biasanya lebih
#   kecil dari RETRIEVER_K supaya context tidak terlalu gemuk/noisy.
RRF_K = 60                 # konstanta standar reciprocal rank fusion

ALL_DOCS_CACHE_KEY = "__all__"

# UPDATE: guard lexical tambahan untuk cache -- mencegah false positive pada
# pasangan istilah kritis yang gampang keketuker meski cosine similarity-nya
# tinggi (mis. "kartu debit" vs "kartu kredit" pernah terukur 0.83, cukup
# dekat ke threshold 0.85). Kalau salah satu istilah dalam pasangan ini muncul
# di query baru TAPI TIDAK di query yang di-cache (atau sebaliknya), cache
# entry itu di-skip walau similarity-nya lolos threshold.
CRITICAL_TERM_PAIRS = [
    ("debit", "kredit"),
    ("tabungan", "deposito"),
    ("giro", "tabungan"),
]


def has_conflicting_critical_term(query_a: str, query_b: str) -> bool:
    for term1, term2 in CRITICAL_TERM_PAIRS:
        a_has_1, a_has_2 = term1 in query_a, term2 in query_a
        b_has_1, b_has_2 = term1 in query_b, term2 in query_b
        if (a_has_1 and b_has_2 and not a_has_2) or (a_has_2 and b_has_1 and not a_has_1):
            return True
    return False


SYSTEM_PROMPT_RAG_STRICT = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.

[ATURAN WAJIB]
1. WAJIB gunakan kata "aku" dan "kamu", jangan kaku/formal.
2. ANTI-HALUSINASI: jawab HANYA berdasarkan [SUMBER INFORMASI] yang diberikan.
3. [SUMBER INFORMASI] bisa berisi beberapa [Potongan] terpisah -- evaluasi TIAP potongan secara independen.
   Beberapa potongan mungkin TIDAK relevan dengan pertanyaan meskipun ada di daftar; abaikan yang tidak
   menjawab pertanyaan, jangan dipaksa disambung-sambungkan.
4. Jangan pernah menciptakan istilah, singkatan, angka, atau fakta baru yang tidak tertulis persis di
   [SUMBER INFORMASI]. Untuk setiap klaim yang kamu buat, pastikan ada kalimat di [SUMBER INFORMASI] yang
   mendukungnya secara eksplisit -- kalau tidak ada, jangan tuliskan klaim itu, meskipun klaim itu benar
   secara pengetahuan umum.
5. Jika [SUMBER INFORMASI] kosong atau tidak ada potongan yang relevan, katakan terus terang kamu tidak
   menemukan jawabannya di dokumen.
6. Susun jawaban dengan rapi, gunakan bullet point kalau perlu, dan JANGAN mengulang poin yang sama."""

# Mode non-default (general_mode=True di request). TIDAK dipakai sebagai default
# supaya perilaku sistem tetap konsisten dengan Ruang Lingkup & evaluasi RAGAS
# (faithfulness) di skripsi. User bisa aktifkan manual per-request untuk obrolan
# santai di luar topik dokumen.
SYSTEM_PROMPT_RAG_FLEXIBLE = """Kamu adalah Qwen, asisten AI yang cerdas, santai, dan ramah. Gunakan kata "aku" dan "kamu" dalam menjawab, selalu dalam Bahasa Indonesia.

Berikut adalah informasi referensi dari dokumen (gunakan ini jika relevan dengan pertanyaan):
[Lihat SUMBER INFORMASI di bawah]

[ATURAN]
1. Jika pertanyaan bisa dijawab menggunakan [SUMBER INFORMASI], prioritaskan informasi tersebut dan jangan
   menambah klaim yang tidak didukung isinya.
2. Jika pertanyaan tidak ada hubungannya dengan [SUMBER INFORMASI] (sapaan umum, sejarah, sains, tokoh publik, dll), jawablah secara bebas dan santai berdasarkan pengetahuan umum yang kamu miliki."""

SYSTEM_PROMPT_CHAT = """Kamu adalah Qwen, asisten AI yang santai dan ramah, selalu menjawab dalam Bahasa Indonesia.
Gunakan kata "aku" dan "kamu". Jawab dengan detail tapi tidak bertele-tele."""


def select_system_prompt(is_rag_mode: bool, general_mode: bool) -> str:
    if is_rag_mode:
        return SYSTEM_PROMPT_RAG_FLEXIBLE if general_mode else SYSTEM_PROMPT_RAG_STRICT
    return SYSTEM_PROMPT_CHAT


# =========================================================
# 2. STATE & PENYIMPANAN
# =========================================================
class LocalFileByteStore(BaseStore[str, object]):
    """Docstore persisten untuk parent chunks (disimpan sebagai file .pkl di disk,
    bukan cuma di memori -- supaya tidak perlu re-ingest semua dokumen tiap kali
    server restart)."""

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


def load_documents_registry() -> List[str]:
    if os.path.exists(DOCUMENTS_REGISTRY_PATH):
        with open(DOCUMENTS_REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_documents_registry(documents: List[str]) -> None:
    with open(DOCUMENTS_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)


class RAGState:
    """Wadah semua objek/resource RAG yang hidup selama server berjalan
    (dibuat sekali lewat initialize(), dipakai bersama di semua request)."""
    embeddings: HuggingFaceEmbeddings = None
    llm: LlamaCpp = None
    retriever: ParentDocumentRetriever = None
    bm25_index: "BM25Index" = None
    documents: List[str] = []
    prompt_cache: dict = {}
    cache_lock: asyncio.Lock = None
    inference_lock: threading.Lock = None


state = RAGState()


# =========================================================
# 3. DATA INGESTION (load PDF, deteksi tabel, chunking, indexing)
# =========================================================
ROWS_PER_TABLE_CHUNK = 8  # jumlah baris tabel per chunk, header selalu diulang di tiap chunk


def extract_table_documents(file_path: str, filename: str) -> List[Document]:
    """
    Deteksi tabel di tiap halaman PDF (page.find_tables(), bawaan PyMuPDF)
    dan ubah jadi Document terpisah berformat Markdown table, dengan HEADER
    KOLOM DIULANG di setiap potongan.

    Ini mengatasi masalah dokumen tabular (mis. transkrip nilai): loader teks
    biasa (PyMuPDFLoader) nge-dump tabel jadi teks flat tanpa batas kolom,
    dan chunking berbasis karakter bisa motong tabel di tengah sehingga
    potongan yang ke-retrieve kehilangan baris header -- model jadi salah
    mengaitkan angka ke kolom yang salah, atau nyampur baris dari bagian
    dokumen yang berbeda (mis. baris ringkasan/total).
    """
    table_docs: List[Document] = []
    try:
        pdf = fitz.open(file_path)
    except Exception as e:
        print(f"Gagal buka PDF untuk deteksi tabel: {e}")
        return table_docs

    for page_number, page in enumerate(pdf, start=1):
        try:
            tables = page.find_tables()
        except Exception as e:
            print(f"find_tables gagal di halaman {page_number}: {e}")
            continue

        for table in tables:
            try:
                data = table.extract()
            except Exception as e:
                print(f"Gagal extract tabel di halaman {page_number}: {e}")
                continue
            if not data or len(data) < 2:
                continue

            header = [str(c) if c is not None else "" for c in data[0]]
            rows = data[1:]

            for i in range(0, len(rows), ROWS_PER_TABLE_CHUNK):
                batch = rows[i:i + ROWS_PER_TABLE_CHUNK]
                lines = [
                    "| " + " | ".join(header) + " |",
                    "| " + " | ".join(["---"] * len(header)) + " |",
                ]
                for row in batch:
                    cells = [str(c) if c is not None else "" for c in row]
                    lines.append("| " + " | ".join(cells) + " |")

                table_docs.append(Document(
                    page_content="\n".join(lines),
                    metadata={"source": filename, "content_type": "table", "page": page_number},
                ))

    pdf.close()
    return table_docs


def rebuild_bm25_index() -> None:
    collection = state.retriever.vectorstore._collection
    data = collection.get(include=["metadatas", "documents"])
    child_docs = [
        Document(page_content=content, metadata=meta)
        for content, meta in zip(data["documents"], data["metadatas"])
    ]
    state.bm25_index.build(child_docs, state.retriever.id_key)
    print(f"[BM25] Index dibangun ulang: {len(child_docs)} child chunks.")


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


def ingest_pdf(file_path: str, filename: str) -> int:
    """Pipeline ingestion lengkap 1 file PDF: load teks + deteksi tabel,
    replace dokumen lama (kalau nama file sama), index ke vectorstore+BM25,
    update registry, invalidate cache. Return jumlah halaman/potongan yang
    berhasil di-index. Dipanggil dari endpoint /api/upload di main.py."""
    loader = PyMuPDFLoader(file_path)
    documents = loader.load()
    if not documents:
        raise ValueError("Tidak ada teks yang bisa diekstrak dari PDF ini.")

    for doc in documents:
        doc.metadata["source"] = filename

    table_documents = extract_table_documents(file_path, filename)
    documents = documents + table_documents
    if table_documents:
        print(f"Terdeteksi {len(table_documents)} potongan tabel di '{filename}'.")

    remove_existing_document(filename)
    state.retriever.add_documents(documents)
    rebuild_bm25_index()

    if filename not in state.documents:
        state.documents.append(filename)
        save_documents_registry(state.documents)

    invalidate_document_cache(filename)

    return len(documents)


def delete_document(filename: str) -> None:
    """Hapus 1 dokumen dari vectorstore, BM25 index, registry, dan cache
    terkait. Dipanggil dari endpoint DELETE /api/documents/{filename}."""
    remove_existing_document(filename)
    rebuild_bm25_index()
    state.documents.remove(filename)
    save_documents_registry(state.documents)
    invalidate_document_cache(filename)


# =========================================================
# 4. RETRIEVAL (Hybrid: Dense + BM25, Reciprocal Rank Fusion)
# =========================================================
def simple_tokenize(text: str) -> List[str]:
    # Tokenizer sederhana -- cukup untuk BM25, tidak perlu stemming Indonesia
    # yang kompleks; tujuan utamanya menangkap kecocokan literal istilah/akronim
    # (mis. "DHN", "PPATK") yang sering lolos dari embedding kecil.
    return re.findall(r"\w+", text.lower())


class BM25Index:
    """
    Index BM25 in-memory, dibangun ulang dari seluruh child chunks di Chroma
    tiap kali dokumen ditambah/dihapus. Untuk korpus skala skripsi (puluhan-
    ratusan dokumen), rebuild penuh masih cepat -- tidak perlu index inkremental.
    """

    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.doc_ids: List[str] = []
        self.doc_sources: List[str] = []

    def build(self, child_docs: List[Document], id_key: str) -> None:
        self.doc_ids = [d.metadata.get(id_key) for d in child_docs]
        self.doc_sources = [d.metadata.get("source") for d in child_docs]
        corpus_tokens = [simple_tokenize(d.page_content) for d in child_docs]
        self.bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else None

    def search(self, query: str, k: int, source_filter: Optional[str] = None) -> List[str]:
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(simple_tokenize(query))
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results: List[str] = []
        for i in ranked_idx:
            if scores[i] <= 0:  # tidak ada token yang match sama sekali
                break
            if source_filter and self.doc_sources[i] != source_filter:
                continue
            doc_id = self.doc_ids[i]
            if doc_id and doc_id not in results:
                results.append(doc_id)
            if len(results) >= k:
                break
        return results


def reciprocal_rank_fusion(rank_lists: List[List[str]], k: int = RRF_K) -> List[str]:
    """Gabung beberapa daftar hasil (urut dari paling relevan) jadi satu ranking,
    tanpa perlu menyamakan skala skor tiap retriever (skor cosine similarity dan
    BM25 tidak sebanding secara langsung)."""
    scores: dict = {}
    for rank_list in rank_lists:
        for rank, doc_id in enumerate(rank_list):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def calculate_cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def _find_suffix_prefix_overlap(a: str, b: str, min_overlap: int) -> int:
    """Cari overlap terpanjang di mana akhir string a == awal string b."""
    max_check = min(len(a), len(b))
    for size in range(max_check, min_overlap - 1, -1):
        if a[-size:] == b[:size]:
            return size
    return 0


def merge_overlapping_parents(parent_docs: List[Document], min_overlap: int = 30) -> List[Document]:
    """
    Parent chunking pakai overlap (PARENT_CHUNK_OVERLAP), jadi 2 chunk yang
    bersebelahan di dokumen asli bisa sama-sama lolos retrieval (isinya nyaris
    sama -> skor mirip). Kalau dikirim apa adanya ke LLM, teks overlap muncul
    dobel verbatim di context -- salah satu pemicu repetition loop (model
    "mengunci" ke pola kalimat yang berulang di context-nya sendiri).

    Fungsi ini menggabungkan chunk yang overlap jadi 1 teks utuh tanpa
    duplikasi, sekaligus memperbaiki kasus chunk yang kepotong di tengah
    klausul/kata (mis. chunk yang diawali fragmen aneh seperti '"OR"):
    Pemberian instruksi...' jadi kalimat utuh yang lebih mudah "dibaca" model).
    """
    merged: List[Document] = []
    used = [False] * len(parent_docs)

    for i, doc_a in enumerate(parent_docs):
        if used[i]:
            continue
        content = doc_a.page_content
        source_a = doc_a.metadata.get("source")
        changed = True
        while changed:
            changed = False
            for j, doc_b in enumerate(parent_docs):
                if used[j] or j == i or doc_b.metadata.get("source") != source_a:
                    continue
                ov = _find_suffix_prefix_overlap(content, doc_b.page_content, min_overlap)
                if ov > 0:
                    content = content + doc_b.page_content[ov:]
                    used[j] = True
                    changed = True
                    continue
                ov_rev = _find_suffix_prefix_overlap(doc_b.page_content, content, min_overlap)
                if ov_rev > 0:
                    content = doc_b.page_content + content[ov_rev:]
                    used[j] = True
                    changed = True
        used[i] = True
        merged.append(Document(page_content=content, metadata=doc_a.metadata))
    return merged


def retrieve_parent_docs(
    query_text: str,
    query_embedding,
    source_filter: Optional[str] = None,
    score_threshold: float = DENSE_SCORE_THRESHOLD,
    top_n_parents: int = TOP_N_PARENTS,
) -> List[Document]:
    """
    Hybrid retrieval: dense (embedding, dengan score threshold) + sparse (BM25),
    digabung pakai reciprocal rank fusion, lalu parent chunk yang overlap
    digabung jadi teks utuh (lihat merge_overlapping_parents).

    - Dense saja cenderung "kabur" untuk kalimat naratif tapi lemah menangkap
      istilah/akronim spesifik (mis. "DHN", "PPATK").
    - BM25 saja lemah untuk parafrase/sinonim tapi kuat untuk kecocokan literal.
    - Score threshold di sisi dense mencegah chunk yang jauh di bawah relevan
      tetap ikut terbawa cuma karena k selalu dipenuhi.
    """
    id_key = state.retriever.id_key

    # --- Dense retrieval ---
    collection = state.retriever.vectorstore._collection
    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": RETRIEVER_K,
        "include": ["metadatas", "embeddings"],
    }
    if source_filter:
        query_kwargs["where"] = {"source": source_filter}
    dense_results = collection.query(**query_kwargs)

    dense_ids: List[str] = []
    if dense_results["metadatas"]:
        for meta, emb in zip(dense_results["metadatas"][0], dense_results["embeddings"][0]):
            score = calculate_cosine_similarity(query_embedding, emb)
            if score < score_threshold:
                continue
            doc_id = meta.get(id_key)
            if doc_id and doc_id not in dense_ids:
                dense_ids.append(doc_id)

    # --- Sparse (BM25) retrieval ---
    bm25_ids = state.bm25_index.search(query_text, k=RETRIEVER_K, source_filter=source_filter)

    if not dense_ids and not bm25_ids:
        return []

    fused_ids = reciprocal_rank_fusion([dense_ids, bm25_ids])[:top_n_parents]
    parent_docs = state.retriever.docstore.mget(fused_ids)
    parent_docs = [d for d in parent_docs if d is not None]
    return merge_overlapping_parents(parent_docs)


def format_context(parent_docs: List[Document]) -> str:
    """Beri label per potongan supaya model bisa membedakan batas antar sumber
    dan mengevaluasi tiap potongan secara independen (lihat SYSTEM_PROMPT_RAG_STRICT
    aturan #3)."""
    return "\n\n".join(
        f"[Potongan {i + 1}]\n{doc.page_content}" for i, doc in enumerate(parent_docs)
    )


def get_context(user_input_lower: str, query_embedding, document: Optional[str]) -> Tuple[str, bool]:
    """Wrapper retrieval + formatting + debug print, dipanggil dari main.py.
    Return (context_string, is_rag_mode)."""
    context, is_rag_mode = "", False
    try:
        parent_docs = retrieve_parent_docs(user_input_lower, query_embedding, source_filter=document)
        if parent_docs:
            context = format_context(parent_docs)
            is_rag_mode = True
            if os.getenv("DEBUG_CONTEXT", "false").lower() == "true":
                print(f"\n=== CONTEXT UNTUK: '{user_input_lower}' ===")
                print(context)
                print("=== END CONTEXT ===\n")
    except Exception as e:
        print(f"Retrieval gagal: {e}")
        traceback.print_exc()
    return context, is_rag_mode


# =========================================================
# 5. SEMANTIC PROMPT CACHE
# =========================================================
def make_cache_key(document: Optional[str], general_mode: bool) -> str:
    mode_suffix = "general" if general_mode else "strict"
    return f"{document or ALL_DOCS_CACHE_KEY}::{mode_suffix}"


async def check_cache(cache_key: str, user_input_lower: str, query_embedding):
    """Cek apakah ada entry cache yang cocok (similarity >= CACHE_THRESHOLD DAN
    tidak ada konflik istilah kritis). Return (best_match_dict_or_None, best_score)."""
    async with state.cache_lock:
        cache_snapshot = list(state.prompt_cache.get(cache_key, []))

    best_match, best_score = None, 0.0
    for cached_item in cache_snapshot:
        if has_conflicting_critical_term(user_input_lower, cached_item["query"]):
            continue  # guard lexical -- skip meski similarity tinggi
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD and sim_score > best_score:
            best_match, best_score = cached_item, sim_score

    if os.getenv("DEBUG_CACHE", "false").lower() == "true":
        print(f"[CACHE] Query: '{user_input_lower}' | Best score: {best_score:.4f} "
              f"| Threshold: {CACHE_THRESHOLD} | Hit: {best_match is not None}")

    return best_match, best_score


async def store_cache(cache_key: str, user_input_lower: str, query_embedding, response: str) -> None:
    async with state.cache_lock:
        bucket = state.prompt_cache.setdefault(cache_key, [])
        bucket.append({
            "query": user_input_lower,
            "embedding": query_embedding,
            "response": response,
        })
        if len(bucket) > MAX_CACHE_ITEMS:
            bucket.pop(0)


def invalidate_document_cache(document: Optional[str]) -> None:
    """Hapus semua entri cache (mode strict & general) untuk 1 dokumen,
    plus cache mode 'semua dokumen' (karena hasil pencarian lintas-dokumen
    ikut berubah juga saat 1 dokumen di-upload/dihapus)."""
    key_base = document or ALL_DOCS_CACHE_KEY
    for base in {key_base, ALL_DOCS_CACHE_KEY}:
        state.prompt_cache.pop(f"{base}::strict", None)
        state.prompt_cache.pop(f"{base}::general", None)


# =========================================================
# 6. PROMPT CONSTRUCTION & GENERATION
# =========================================================
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
# 7. INISIALISASI (dipanggil dari lifespan() di main.py)
# =========================================================
async def initialize() -> RAGState:
    """Setup semua resource RAG (embedding model, LLM GGUF, vectorstore, BM25,
    registry dokumen, cache). Dipanggil sekali saat FastAPI startup."""

    # NOTE: pakai sentence-transformers (bukan OllamaEmbeddings bge-m3) supaya
    # konsisten dengan Ruang Lingkup skripsi: "tanpa server model pihak ketiga
    # terpisah". Kalau mau ganti ke bge-m3 via Ollama, ganti blok ini saja.
    #
    # UPDATE: model embedding SUDAH dievaluasi vs 2 kandidat lain (LazarusNLP/
    # all-indo-e5-small-v4 dan paraphrase-multilingual-mpnet-base-v2) lewat
    # eksperimen tuning threshold -- model ini (MiniLM-L12-v2) tetap dipakai
    # karena secara diskriminatif (should-hit vs should-not-hit) hasilnya
    # tidak kalah dari kandidat yang lebih besar, dengan ukuran paling ringan.
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
        # -1 = offload semua layer ke GPU. Kalau nanti kena CUDA out-of-memory di
        # RTX 3050 4GB (terutama kalau upgrade ke model 4B), turunkan jadi angka
        # spesifik (mis. 20) supaya sebagian layer tetap di CPU -- verbose=True
        # di bawah akan mencetak jumlah layer & alokasi VRAM saat model di-load,
        # jadi kelihatan berapa yang muat.
        n_gpu_layers=int(os.getenv("N_GPU_LAYERS", "-1")),
        n_batch=512,
        temperature=0.2,
        # Repeat penalty saja (tanpa frequency/presence penalty ditumpuk) --
        # kombinasi ketiganya sekaligus terbukti mendorong model menghindari
        # mengulang istilah ASLI dari dokumen sumber, sehingga "terpaksa"
        # parafrase bebas dan kadang mengarang istilah baru saat RAG strict.
        repeat_penalty=1.1,
        frequency_penalty=0.0,
        presence_penalty=0.0,
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

    state.bm25_index = BM25Index()
    rebuild_bm25_index()

    state.documents = load_documents_registry()
    state.prompt_cache = {}
    state.cache_lock = asyncio.Lock()
    state.inference_lock = threading.Lock()

    return state
