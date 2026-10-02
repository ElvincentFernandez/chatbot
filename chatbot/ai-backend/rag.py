"""
rag.py -- Clean Facade Module untuk RAG Engine (Multi-Client & Multi-Turn).

Modul ini menyediakan API publik yang bersih untuk diakses oleh main.py,
menggabungkan komponen modular dari paket `rag_modules`.
"""

from rag_modules.config import (
    MODEL_PATH,
    CHROMA_DIR,
    PARENT_STORE_DIR,
    MAX_HISTORY_TURNS,
    ALL_DOCS_CACHE_KEY,
    CACHE_THRESHOLD,
    PARENT_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    CHILD_CHUNK_OVERLAP,
    RETRIEVER_K,
    DENSE_SCORE_THRESHOLD,
    TOP_N_PARENTS,
    RRF_K,
)
from rag_modules.state import (
    RAGState,
    state,
    get_client_collection_name,
    get_client_docstore_path,
    get_client_state,
    delete_client_data,
    LocalFileByteStore,
)
from rag_modules.cache import (
    make_cache_key,
    check_cache,
    store_cache,
    invalidate_document_cache,
    has_conflicting_critical_term,
)
from rag_modules.retrieval import (
    BM25Index,
    rebuild_bm25_index,
    reciprocal_rank_fusion,
    calculate_cosine_similarity,
    retrieve_parent_docs,
    format_context,
    get_context,
)
from rag_modules.ingestion import (
    extract_table_documents,
    remove_existing_document,
    ingest_pdf,
    delete_document,
)
from rag_modules.generation import (
    select_system_prompt,
    build_prompt,
    stream_llm,
    initialize,
)

__all__ = [
    "MODEL_PATH",
    "CHROMA_DIR",
    "PARENT_STORE_DIR",
    "MAX_HISTORY_TURNS",
    "ALL_DOCS_CACHE_KEY",
    "CACHE_THRESHOLD",
    "PARENT_CHUNK_SIZE",
    "PARENT_CHUNK_OVERLAP",
    "CHILD_CHUNK_SIZE",
    "CHILD_CHUNK_OVERLAP",
    "RETRIEVER_K",
    "DENSE_SCORE_THRESHOLD",
    "TOP_N_PARENTS",
    "RRF_K",
    "RAGState",
    "state",
    "get_client_collection_name",
    "get_client_docstore_path",
    "get_client_state",
    "delete_client_data",
    "LocalFileByteStore",
    "make_cache_key",
    "check_cache",
    "store_cache",
    "invalidate_document_cache",
    "has_conflicting_critical_term",
    "BM25Index",
    "rebuild_bm25_index",
    "reciprocal_rank_fusion",
    "calculate_cosine_similarity",
    "retrieve_parent_docs",
    "format_context",
    "get_context",
    "extract_table_documents",
    "remove_existing_document",
    "ingest_pdf",
    "delete_document",
    "select_system_prompt",
    "build_prompt",
    "stream_llm",
    "initialize",
]
