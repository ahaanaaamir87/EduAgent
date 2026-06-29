"""
Retrieval-Augmented Generation (RAG) service.

Pipeline:
  1. Ingest a document (txt or pdf) -> extract text
  2. Chunk text into overlapping windows
  3. Embed each chunk using an Ollama embedding model (e.g. nomic-embed-text)
  4. Store vectors + text in a per-user ChromaDB collection
  5. At query time, embed the query, retrieve top-k similar chunks,
     and return them as context for the LLM prompt.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

import chromadb
import ollama
from pypdf import PdfReader

from app.config import settings

_chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
_ollama_client = ollama.Client(host=settings.OLLAMA_HOST)


def _collection_name(user_id: int) -> str:
    return f"user_{user_id}_docs"


def get_collection(user_id: int):
    return _chroma_client.get_or_create_collection(name=_collection_name(user_id))


def extract_text(filepath: str) -> str:
    """Extract raw text from a .pdf or .txt file."""
    path = Path(filepath)
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        text_parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(text_parts)
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """Simple sliding-window chunker over characters, respecting word boundaries."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    text = " ".join(text.split())  # normalize whitespace
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        # try not to cut mid-word
        if end < n:
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts using the configured Ollama embedding model."""
    vectors = []
    for t in texts:
        resp = _ollama_client.embeddings(model=settings.OLLAMA_EMBED_MODEL, prompt=t)
        vectors.append(resp["embedding"])
    return vectors


def ingest_document(user_id: int, filepath: str, doc_id: int) -> int:
    """
    Extract -> chunk -> embed -> store a document's chunks in the user's
    ChromaDB collection. Returns the number of chunks stored.
    """
    text = extract_text(filepath)
    chunks = chunk_text(text)
    if not chunks:
        return 0

    collection = get_collection(user_id)
    vectors = embed_texts(chunks)
    ids = [f"doc{doc_id}_chunk{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))]

    collection.add(ids=ids, embeddings=vectors, documents=chunks, metadatas=metadatas)
    return len(chunks)


def retrieve_context(user_id: int, query: str, top_k: int = None) -> List[str]:
    """Embed the query and retrieve the top_k most relevant chunks for this user."""
    top_k = top_k or settings.RAG_TOP_K
    collection = get_collection(user_id)
    if collection.count() == 0:
        return []

    query_vector = embed_texts([query])[0]
    results = collection.query(query_embeddings=[query_vector], n_results=min(top_k, collection.count()))
    docs = results.get("documents", [[]])
    return docs[0] if docs else []


def delete_document_chunks(user_id: int, doc_id: int):
    collection = get_collection(user_id)
    collection.delete(where={"doc_id": doc_id})
