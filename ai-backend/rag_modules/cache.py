"""
cache.py -- Semantic Prompt Cache yang ter-scope per client_id.
"""
import os
from typing import Optional

from rag_modules.config import (
    ALL_DOCS_CACHE_KEY,
    CACHE_THRESHOLD,
    MAX_CACHE_ITEMS,
    CRITICAL_TERM_PAIRS,
)
from rag_modules.state import state


def has_conflicting_critical_term(query_a: str, query_b: str) -> bool:
    """Mengecek konflik istilah sensitif (mis. debit vs kredit) untuk mencegah false match cache."""
    for term1, term2 in CRITICAL_TERM_PAIRS:
        a_has_1, a_has_2 = term1 in query_a, term2 in query_a
        b_has_1, b_has_2 = term1 in query_b, term2 in query_b
        if (a_has_1 and b_has_2 and not a_has_2) or (a_has_2 and b_has_1 and not a_has_1):
            return True
    return False


def make_cache_key(client_id: int, document: Optional[str], general_mode: bool) -> str:
    """Membuat format kunci cache berisikan client_id, nama dokumen, dan mode prompt."""
    mode_suffix = "general" if general_mode else "strict"
    return f"{client_id}::{document or ALL_DOCS_CACHE_KEY}::{mode_suffix}"


async def check_cache(cache_key: str, user_input_lower: str, query_embedding):
    """Mencari entri semantic cache yang relevan berdasarkan skor cosine similarity."""
    async with state.cache_lock:
        cache_snapshot = list(state.prompt_cache.get(cache_key, []))

    best_match, best_score = None, 0.0
    for cached_item in cache_snapshot:
        if has_conflicting_critical_term(user_input_lower, cached_item["query"]):
            continue

        # Hitung similarity antar vektor embedding
        from rag_modules.retrieval import calculate_cosine_similarity
        sim_score = calculate_cosine_similarity(query_embedding, cached_item["embedding"])
        if sim_score >= CACHE_THRESHOLD and sim_score > best_score:
            best_match, best_score = cached_item, sim_score

    if os.getenv("DEBUG_CACHE", "false").lower() == "true":
        print(f"[CACHE] Query: '{user_input_lower}' | Score: {best_score:.4f} | Hit: {best_match is not None}")

    return best_match, best_score


async def store_cache(cache_key: str, user_input_lower: str, query_embedding, response: str) -> None:
    """Menyimpan query, embedding, dan respon LLM ke dalam bucket cache client."""
    async with state.cache_lock:
        bucket = state.prompt_cache.setdefault(cache_key, [])
        bucket.append({
            "query": user_input_lower,
            "embedding": query_embedding,
            "response": response,
        })
        if len(bucket) > MAX_CACHE_ITEMS:
            bucket.pop(0)


def invalidate_document_cache(client_id: int, document: Optional[str]) -> None:
    """Menghapus entri cache terkait dokumen tertentu atau seluruh dokumen milik client."""
    key_base = document or ALL_DOCS_CACHE_KEY
    for base in {key_base, ALL_DOCS_CACHE_KEY}:
        state.prompt_cache.pop(f"{client_id}::{base}::strict", None)
        state.prompt_cache.pop(f"{client_id}::{base}::general", None)
