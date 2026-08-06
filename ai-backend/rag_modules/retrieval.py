"""
retrieval.py -- Logika hybrid retrieval (Dense Vector + BM25 Sparse + RRF) per client.
"""
import os
import re
import math
import traceback
from typing import List, Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from rag_modules.config import (
    DENSE_SCORE_THRESHOLD,
    RETRIEVER_K,
    RRF_K,
    TOP_N_PARENTS,
)
from rag_modules.state import state, get_client_state


def simple_tokenize(text: str) -> List[str]:
    """Tokenisasi kata sederhana untuk kebutuhan pembuatan indeks BM25."""
    return re.findall(r"\w+", text.lower())


class BM25Index:
    """Indeks pencarian kata kunci BM25 in-memory untuk tiap client."""

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
            if scores[i] <= 0:
                break
            if source_filter and self.doc_sources[i] != source_filter:
                continue
            doc_id = self.doc_ids[i]
            if doc_id and doc_id not in results:
                results.append(doc_id)
            if len(results) >= k:
                break
        return results


def rebuild_bm25_index(client_id: int) -> None:
    """Membangun ulang indeks BM25 dari koleksi ChromaDB milik client_id."""
    retriever = state.retrievers[client_id]
    collection = retriever.vectorstore._collection
    data = collection.get(include=["metadatas", "documents"])
    child_docs = [
        Document(page_content=content, metadata=meta)
        for content, meta in zip(data["documents"], data["metadatas"])
    ]
    state.bm25_indexes[client_id].build(child_docs, retriever.id_key)


def reciprocal_rank_fusion(rank_lists: List[List[str]], k: int = RRF_K) -> List[str]:
    """Menggabungkan peringkat dari Dense Vector dan BM25 dengan Reciprocal Rank Fusion (RRF)."""
    scores: dict = {}
    for rank_list in rank_lists:
        for rank, doc_id in enumerate(rank_list):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def calculate_cosine_similarity(vec1, vec2) -> float:
    """Menghitung nilai kemiripan kosinus (Cosine Similarity) antara dua vektor."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def _find_suffix_prefix_overlap(a: str, b: str, min_overlap: int) -> int:
    max_check = min(len(a), len(b))
    for size in range(max_check, min_overlap - 1, -1):
        if a[-size:] == b[:size]:
            return size
    return 0


def merge_overlapping_parents(parent_docs: List[Document], min_overlap: int = 30) -> List[Document]:
    """Menggabungkan parent chunks yang tumpang tindih untuk efisiensi context window."""
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
    client_id: int,
    query_text: str,
    query_embedding,
    source_filter: Optional[str] = None,
    score_threshold: float = DENSE_SCORE_THRESHOLD,
    top_n_parents: int = TOP_N_PARENTS,
) -> List[Document]:
    """Ekstraksi dokumen konteks menggunakan Hybrid Retrieval (Dense Vector + BM25)."""
    retriever, bm25_index = get_client_state(client_id)
    id_key = retriever.id_key

    collection = retriever.vectorstore._collection
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

    bm25_ids = bm25_index.search(query_text, k=RETRIEVER_K, source_filter=source_filter)

    if not dense_ids and not bm25_ids:
        return []

    fused_ids = reciprocal_rank_fusion([dense_ids, bm25_ids])[:top_n_parents]
    parent_docs = retriever.docstore.mget(fused_ids)
    parent_docs = [d for d in parent_docs if d is not None]
    return merge_overlapping_parents(parent_docs)


def format_context(parent_docs: List[Document]) -> str:
    """Format daftar dokumen menjadi teks konteks terstruktur untuk prompt."""
    return "\n\n".join(
        f"[Potongan {i + 1}]\n{doc.page_content}" for i, doc in enumerate(parent_docs)
    )


def get_context(client_id: int, user_input_lower: str, query_embedding, document: Optional[str]):
    """Fungsi utama pembantu retrieval dan format konteks untuk main.py."""
    context, is_rag_mode = "", False
    try:
        parent_docs = retrieve_parent_docs(client_id, user_input_lower, query_embedding, source_filter=document)
        if parent_docs:
            context = format_context(parent_docs)
            is_rag_mode = True
            if os.getenv("DEBUG_CONTEXT", "false").lower() == "true":
                print(f"\n=== CONTEXT [client_id={client_id}] UNTUK: '{user_input_lower}' ===")
                print(context)
                print("=== END CONTEXT ===\n")
    except Exception as e:
        print(f"Retrieval gagal (client_id={client_id}): {e}")
        traceback.print_exc()
    return context, is_rag_mode
