"""
state.py -- Manajemen state global dan isolasi penyimpanan data per-client.
"""
import os
import pickle
import shutil
import asyncio
import threading
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from langchain_community.llms import LlamaCpp
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.stores import BaseStore

try:
    from langchain_classic.retrievers import ParentDocumentRetriever
except ImportError:
    from langchain.retrievers import ParentDocumentRetriever

from rag_modules.config import (
    CHROMA_DIR,
    PARENT_STORE_DIR,
    PARENT_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    CHILD_CHUNK_OVERLAP,
    RETRIEVER_K,
)


class LocalFileByteStore(BaseStore[str, object]):
    """Docstore persisten di sistem berkas lokal untuk menyimpan parent chunks per-client."""

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


class RAGState:
    """Wadah resource RAG global (Embeddings, LLM, Lock) & cache/retriever per-client."""
    embeddings: HuggingFaceEmbeddings = None
    llm: LlamaCpp = None
    cache_lock: asyncio.Lock = None
    inference_lock: threading.Lock = None

    retrievers: Dict[int, ParentDocumentRetriever] = {}
    bm25_indexes: Dict[int, object] = {}
    prompt_cache: Dict[str, list] = {}


state = RAGState()


def get_client_collection_name(client_id: int) -> str:
    return f"client_{client_id}_chunks"


def get_client_docstore_path(client_id: int) -> str:
    return os.path.join(PARENT_STORE_DIR, f"client_{client_id}")


def get_client_state(client_id: int) -> Tuple[ParentDocumentRetriever, object]:
    """Mengambil atau menginisialisasi retriever & BM25 index khusus untuk client_id (Lazy Init)."""
    from rag_modules.retrieval import BM25Index, rebuild_bm25_index

    if client_id not in state.retrievers:
        vectorstore = Chroma(
            collection_name=get_client_collection_name(client_id),
            embedding_function=state.embeddings,
            persist_directory=CHROMA_DIR,
        )
        parent_docstore = LocalFileByteStore(get_client_docstore_path(client_id))
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=PARENT_CHUNK_SIZE, chunk_overlap=PARENT_CHUNK_OVERLAP
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHILD_CHUNK_SIZE, chunk_overlap=CHILD_CHUNK_OVERLAP
        )
        state.retrievers[client_id] = ParentDocumentRetriever(
            vectorstore=vectorstore,
            docstore=parent_docstore,
            child_splitter=child_splitter,
            parent_splitter=parent_splitter,
            search_type="similarity",
            search_kwargs={"k": RETRIEVER_K},
        )
        state.bm25_indexes[client_id] = BM25Index()
        rebuild_bm25_index(client_id)
        print(f"[RAG] Resource client_id={client_id} berhasil diinisialisasi.")

    return state.retrievers[client_id], state.bm25_indexes[client_id]


def delete_client_data(client_id: int) -> None:
    """Menghapus seluruh koleksi ChromaDB, docstore disk, BM25 memory, dan cache untuk client_id."""
    try:
        vectorstore = Chroma(
            collection_name=get_client_collection_name(client_id),
            embedding_function=state.embeddings,
            persist_directory=CHROMA_DIR,
        )
        vectorstore.delete_collection()
    except Exception as e:
        print(f"Gagal menghapus koleksi Chroma client_id={client_id}: {e}")

    docstore_path = get_client_docstore_path(client_id)
    if os.path.exists(docstore_path):
        shutil.rmtree(docstore_path, ignore_errors=True)

    state.retrievers.pop(client_id, None)
    state.bm25_indexes.pop(client_id, None)

    prefix = f"{client_id}::"
    for key in list(state.prompt_cache.keys()):
        if key.startswith(prefix):
            state.prompt_cache.pop(key, None)
