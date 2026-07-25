"""
Vector Store — abstraction over ChromaDB with TF-IDF fallback.

Provides semantic search over memories, conversations, and artifacts.
If ChromaDB is installed, uses it (better semantic matching).
Otherwise, falls back to TF-IDF (keyword-based, no extra dependencies).

This is the "Memory ≠ Database" layer — memories are stored in SQLite
(structured), but their semantic vectors live here (for retrieval).

Usage:
    from app.vector_store import get_vector_store
    vs = get_vector_store(db_path)
    vs.add("memories", id="mem_123", text="用户喜欢 TypeScript", metadata={"importance": 80})
    results = vs.query("memories", text="编程语言偏好", top_k=5)
"""
from __future__ import annotations
import sqlite3
import json
import hashlib
import re
import math
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict, Counter

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


# Singleton instances keyed by db_path
_stores: Dict[str, "VectorStore"] = {}


def get_vector_store(db_path: Path) -> "VectorStore":
    """Get or create the vector store for a given db_path."""
    key = str(db_path)
    if key not in _stores:
        _stores[key] = VectorStore(db_path)
    return _stores[key]


class VectorStore:
    """Vector store with ChromaDB backend (preferred) or TF-IDF fallback."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.vectors_dir = db_path.parent / "vectors"
        self.vectors_dir.mkdir(exist_ok=True)
        self._backend = "chromadb" if CHROMA_AVAILABLE else "tfidf"
        self._chroma_client = None
        self._collections: Dict[str, Any] = {}
        # TF-IDF fallback storage: {collection_name: {id: {text, metadata, tf}}}
        self._tfidf_store: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        self._idf_cache: Dict[str, Dict[str, float]] = defaultdict(dict)
        if CHROMA_AVAILABLE:
            try:
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self.vectors_dir),
                    settings=Settings(anonymized_telemetry=False, allow_reset=True),
                )
                print(f"[vector_store] using ChromaDB backend at {self.vectors_dir}")
            except Exception as e:
                print(f"[vector_store] ChromaDB init failed, falling back to TF-IDF: {e}")
                self._backend = "tfidf"
                self._chroma_client = None
        else:
            print("[vector_store] ChromaDB not installed, using TF-IDF backend")
            print("[vector_store] install with: pip install chromadb")

    @property
    def backend(self) -> str:
        return self._backend

    def _get_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        if not CHROMA_AVAILABLE or not self._chroma_client:
            return None
        if name not in self._collections:
            try:
                self._collections[name] = self._chroma_client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                print(f"[vector_store] collection create failed: {e}")
                return None
        return self._collections[name]

    def add(self, collection: str, id: str, text: str, metadata: Optional[Dict] = None):
        """Add or update an item in a collection."""
        if not text or not text.strip():
            return
        metadata = metadata or {}
        if self._backend == "chromadb":
            col = self._get_collection(collection)
            if col:
                try:
                    col.upsert(
                        ids=[id],
                        documents=[text],
                        metadatas=[metadata],
                    )
                    return
                except Exception as e:
                    print(f"[vector_store] chromadb add failed: {e}")
        # TF-IDF fallback
        self._tfidf_store[collection][id] = {
            "text": text,
            "metadata": metadata,
            "tf": self._compute_tf(text),
        }
        # Invalidate IDF cache for this collection
        if collection in self._idf_cache:
            del self._idf_cache[collection]

    def delete(self, collection: str, id: str):
        """Delete an item from a collection."""
        if self._backend == "chromadb":
            col = self._get_collection(collection)
            if col:
                try:
                    col.delete(ids=[id])
                    return
                except Exception as e:
                    print(f"[vector_store] chromadb delete failed: {e}")
        # TF-IDF fallback
        if id in self._tfidf_store[collection]:
            del self._tfidf_store[collection][id]
            if collection in self._idf_cache:
                del self._idf_cache[collection]

    def query(self, collection: str, text: str, top_k: int = 5,
              where: Optional[Dict] = None) -> List[Dict]:
        """Query a collection for similar items. Returns list of {id, text, metadata, score}."""
        if not text or not text.strip():
            return []
        if self._backend == "chromadb":
            col = self._get_collection(collection)
            if col:
                try:
                    results = col.query(
                        query_texts=[text],
                        n_results=top_k,
                        where=where,
                    )
                    out = []
                    if results and results.get("ids"):
                        for i, id in enumerate(results["ids"][0]):
                            out.append({
                                "id": id,
                                "text": results["documents"][0][i] if results.get("documents") else "",
                                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                                "score": 1.0 - results["distances"][0][i] if results.get("distances") else 0.5,
                            })
                    return out
                except Exception as e:
                    print(f"[vector_store] chromadb query failed: {e}")
        # TF-IDF fallback
        return self._tfidf_query(collection, text, top_k, where)

    def count(self, collection: str) -> int:
        """Count items in a collection."""
        if self._backend == "chromadb":
            col = self._get_collection(collection)
            if col:
                try:
                    return col.count()
                except Exception:
                    pass
        return len(self._tfidf_store[collection])

    def clear(self, collection: str):
        """Clear all items in a collection."""
        if self._backend == "chromadb":
            col = self._get_collection(collection)
            if col:
                try:
                    self._chroma_client.delete_collection(name=collection)
                    self._collections.pop(collection, None)
                    return
                except Exception as e:
                    print(f"[vector_store] chromadb clear failed: {e}")
        self._tfidf_store[collection].clear()
        self._idf_cache.pop(collection, None)

    def get_stats(self) -> Dict:
        """Get stats for all collections."""
        stats = {"backend": self._backend, "collections": {}}
        if self._backend == "chromadb" and self._chroma_client:
            try:
                for col_info in self._chroma_client.list_collections():
                    name = col_info.name if hasattr(col_info, "name") else str(col_info)
                    try:
                        col = self._get_collection(name)
                        if col:
                            stats["collections"][name] = col.count()
                    except Exception:
                        stats["collections"][name] = 0
            except Exception as e:
                print(f"[vector_store] stats failed: {e}")
        else:
            for name, items in self._tfidf_store.items():
                stats["collections"][name] = len(items)
        return stats

    # ===== TF-IDF implementation (fallback) =====

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize: split by non-word chars, keep CJK chars as single tokens."""
        # Match sequences of latin/digit chars OR single CJK chars
        tokens = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]', text.lower())
        # Filter very short tokens
        return [t for t in tokens if len(t) >= 2 or '\u4e00' <= t <= '\u9fff']

    def _compute_tf(self, text: str) -> Dict[str, float]:
        """Compute term frequency for a text."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        count = Counter(tokens)
        total = len(tokens)
        return {t: c / total for t, c in count.items()}

    def _compute_idf(self, collection: str) -> Dict[str, float]:
        """Compute inverse document frequency for a collection."""
        if collection in self._idf_cache:
            return self._idf_cache[collection]
        docs = self._tfidf_store[collection]
        n_docs = len(docs)
        if n_docs == 0:
            return {}
        # Count how many docs contain each term
        df = defaultdict(int)
        for item in docs.values():
            for term in item["tf"]:
                df[term] += 1
        # IDF = ln(N / (1 + df))
        idf = {t: math.log(n_docs / (1 + d)) for t, d in df.items()}
        self._idf_cache[collection] = idf
        return idf

    def _tfidf_query(self, collection: str, text: str, top_k: int,
                     where: Optional[Dict] = None) -> List[Dict]:
        """TF-IDF cosine similarity query."""
        docs = self._tfidf_store[collection]
        if not docs:
            return []
        idf = self._compute_idf(collection)
        query_tf = self._compute_tf(text)
        # Compute query tf-idf vector
        query_vec = {t: tf * idf.get(t, 0) for t, tf in query_tf.items()}
        query_norm = math.sqrt(sum(v ** 2 for v in query_vec.values())) or 1.0

        scored = []
        for doc_id, item in docs.items():
            # Apply metadata filter if specified
            if where:
                match = all(item["metadata"].get(k) == v for k, v in where.items())
                if not match:
                    continue
            # Compute doc tf-idf vector
            doc_vec = {t: tf * idf.get(t, 0) for t, tf in item["tf"].items()}
            doc_norm = math.sqrt(sum(v ** 2 for v in doc_vec.values())) or 1.0
            # Cosine similarity
            dot = sum(query_vec.get(t, 0) * doc_vec.get(t, 0) for t in query_vec if t in doc_vec)
            score = dot / (query_norm * doc_norm) if (query_norm and doc_norm) else 0
            scored.append((score, doc_id, item))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [
            {"id": doc_id, "text": item["text"], "metadata": item["metadata"], "score": score}
            for score, doc_id, item in scored[:top_k] if score > 0
        ]
