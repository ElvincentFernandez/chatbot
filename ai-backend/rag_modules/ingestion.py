"""
ingestion.py -- Parsing PDF, ekstraksi tabel PyMuPDF, chunking, dan pengindeksan dokumen.
"""
from typing import List

import fitz  # PyMuPDF
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

from rag_modules.config import ROWS_PER_TABLE_CHUNK
from rag_modules.state import get_client_state
from rag_modules.retrieval import rebuild_bm25_index
from rag_modules.cache import invalidate_document_cache


def extract_table_documents(file_path: str, filename: str) -> List[Document]:
    """Mendeteksi dan mengekstrak tabel PDF dari PyMuPDF menjadi dokumen berformat Markdown."""
    table_docs: List[Document] = []
    try:
        pdf = fitz.open(file_path)
    except Exception as e:
        print(f"Gagal membuka PDF untuk deteksi tabel: {e}")
        return table_docs

    for page_number, page in enumerate(pdf, start=1):
        try:
            tables = page.find_tables()
        except Exception as e:
            print(f"find_tables gagal pada halaman {page_number}: {e}")
            continue

        for table in tables:
            try:
                data = table.extract()
            except Exception as e:
                print(f"Gagal mengekstrak tabel pada halaman {page_number}: {e}")
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


def remove_existing_document(client_id: int, filename: str) -> None:
    """Menghapus entri dokumen lama dari ChromaDB dan docstore parent chunk jika nama file sama."""
    retriever, _ = get_client_state(client_id)
    vectorstore = retriever.vectorstore
    id_key = retriever.id_key
    existing = vectorstore.get(where={"source": filename})
    if not existing or not existing.get("ids"):
        return
    child_ids = existing["ids"]
    metadatas = existing.get("metadatas") or []
    parent_ids = list({m.get(id_key) for m in metadatas if m and m.get(id_key)})
    vectorstore.delete(ids=child_ids)
    if parent_ids:
        retriever.docstore.mdelete(parent_ids)


def ingest_pdf(client_id: int, file_path: str, filename: str) -> int:
    """Pipeline pemrosesan dan pengindeksan dokumen PDF lengkap per client."""
    retriever, _ = get_client_state(client_id)

    loader = PyMuPDFLoader(file_path)
    documents = loader.load()
    if not documents:
        raise ValueError("Tidak ada teks yang dapat diekstrak dari PDF ini.")

    for doc in documents:
        doc.metadata["source"] = filename

    table_documents = extract_table_documents(file_path, filename)
    documents = documents + table_documents

    remove_existing_document(client_id, filename)
    retriever.add_documents(documents)
    rebuild_bm25_index(client_id)
    invalidate_document_cache(client_id, filename)

    return len(documents)


def delete_document(client_id: int, filename: str) -> None:
    """Menghapus dokumen dari indeks vectorstore, BM25, dan cache milik client_id."""
    remove_existing_document(client_id, filename)
    rebuild_bm25_index(client_id)
    invalidate_document_cache(client_id, filename)
