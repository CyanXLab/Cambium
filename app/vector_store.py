"""
Vector Store — semantic search with real embedding models.

Backends (in priority order):
  1. sentence-transformers + ChromaDB (production quality)
     - Real multilingual embeddings (paraphrase-multilingual-MiniLM-L12-v2)
     - 384-dim dense vectors, semantic similarity
     - Best for: Chinese + English mixed content
  2. ChromaDB default embedder (all-MiniLM-L6-v2 via onnx)
     - Decent English-only embeddings
     - No extra deps beyond chromadb
  3. TF-IDF fallback (keyword matching only)
     - Zero deps, but no semantic understanding

The backend is auto-detected at startup and logged clearly.
Install the best backend with:
    pip install sentence-transformers chromadb
"""
from __future__ import annotations
import sqlite3
import json
import hashlib
import re
import math
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict, Counter

from app.logging_config import get_logger

log = get_logger(__name__)

# ============================================================
# Backend detection
# ============================================================

# Default embedding model — multilingual, 384-dim, fast
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "CAMBIUM_EMBEDDING_MODEL",
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# Optional: sentence-transformers for real embeddings
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

# Optional: ChromaDB for vector storage
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


# Singleton instances keyed by db_path
_stores: Dict[str, "VectorStore"] = {}

# Singleton embedding model (loaded once, reused across stores)
_embedding_model: Optional[Any] = None
_embedding_model_name: str = ""


def get_embedding_model() -> Optional[Any]:
    """Get or load the sentence-transformers model (singleton).
    Returns None if sentence-transformers is not installed.
    """
    global _embedding_model, _embedding_model_name
    if not ST_AVAILABLE:
        return None
    if _embedding_model is None:
        try:
            log.info("vector_store.loading_embedding_model", extra={
                "model": DEFAULT_EMBEDDING_MODEL,
            })
            _embedding_model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
            _embedding_model_name = DEFAULT_EMBEDDING_MODEL
            # Get dimension
            dim = _embedding_model.get_sentence_embedding_dimension()
            log.info("vector_store.embedding_model_ready", extra={
                "model": _embedding_model_name,
                "dim": dim,
            })
        except Exception as exc:
            log.warning("vector_store.embedding_model_failed", extra={
                "model": DEFAULT_EMBEDDING_MODEL,
                "error": str(exc),
            })
            _embedding_model = None
    return _embedding_model


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a text using the loaded model. Returns None if unavailable."""
    model = get_embedding_model()
    if model is None or not text:
        return None
    try:
        vec = model.encode(text[:8000], normalize_embeddings=True)
        return vec.tolist()
    except Exception as exc:
        log.warning("vector_store.embed_failed", extra={"error": str(exc)})
        return None


def get_vector_store(db_path: Path) -> "VectorStore":
    """Get or create the vector store for a given db_path."""
    key = str(db_path)
    if key not in _stores:
        _stores[key] = VectorStore(db_path)
    return _stores[key]


class VectorStore:
    """Vector store with multiple backends.

    Backend priority:
      1. sentence-transformers + ChromaDB (best)
      2. ChromaDB with default embedder
      3. TF-IDF (keyword only)
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.vectors_dir = db_path.parent / "vectors"
        self.vectors_dir.mkdir(exist_ok=True)

        # Auto-detect best backend
        self._embedding_model = get_embedding_model()
        self._has_real_embeddings = self._embedding_model is not None

        if CHROMA_AVAILABLE:
            try:
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self.vectors_dir),
                    settings=Settings(anonymized_telemetry=False, allow_reset=True),
                )
                if self._has_real_embeddings:
                    self._backend = "sentence-transformers+chromadb"
                else:
                    self._backend = "chromadb-default"
                self._collections: Dict[str, Any] = {}
                log.info("vector_store.ready", extra={
                    "backend": self._backend,
                    "embedding_model": _embedding_model_name if self._has_real_embeddings else "chromadb-default",
                    "path": str(self.vectors_dir),
                })
            except Exception as exc:
                log.warning("vector_store.chroma_init_failed", extra={"error": str(exc)})
                self._backend = "tfidf"
                self._chroma_client = None
                self._collections = {}
        else:
            self._backend = "tfidf"
            self._chroma_client = None
            self._collections = {}
            log.warning("vector_store.using_tfidf_fallback", extra={
                "reason": "neither sentence-transformers nor chromadb installed",
                "install_hint": "pip install sentence-transformers chromadb",
            })

        # TF-IDF fallback storage
        self._tfidf_store: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        self._idf_cache: Dict[str, Dict[str, float]] = defaultdict(dict)

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def has_real_embeddings(self) -> bool:
        """True if using sentence-transformers (real semantic embeddings)."""
        return self._has_real_embeddings

    def _embed(self, text: str) -> Optional[List[float]]:
        """Embed text using the loaded model."""
        if not self._has_real_embeddings:
            return None
        return embed_text(text)

    def _get_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        if not CHROMA_AVAILABLE or not self._chroma_client:
            return None
        if name not in self._collections:
            try:
                # If we have a real embedding model, we pass embeddings ourselves
                # (don't let chromadb use its default embedder)
                if self._has_real_embeddings:
                    self._collections[name] = self._chroma_client.get_or_create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"},
                    )
                else:
                    # Let chromadb use its default embedder (all-MiniLM-L6-v2)
                    self._collections[name] = self._chroma_client.get_or_create_collection(
                        name=name,
                        metadata={"hnsw:space": "cosine"},
                    )
            except Exception as exc:
                log.warning("vector_store.collection_create_failed", extra={
                    "collection": name, "error": str(exc),
                })
                return None
        return self._collections[name]

    # ============================================================
    # Public API
    # ============================================================

    def add(self, collection: str, id: str, text: str, metadata: Optional[Dict] = None):
        """Add or update an item in a collection."""
        if not text or not text.strip():
            return
        metadata = metadata or {}

        if self._backend in ("sentence-transformers+chromadb", "chromadb-default"):
            col = self._get_collection(collection)
            if col:
                try:
                    if self._has_real_embeddings:
                        # Compute embedding ourselves
                        vec = self._embed(text)
                        if vec:
                            col.upsert(
                                ids=[id],
                                embeddings=[vec],
                                documents=[text],
                                metadatas=[metadata],
                            )
                            return
                        else:
                            log.warning("vector_store.embed_failed_fallback_to_text", extra={
                                "collection": collection, "id": id,
                            })
                            # Fall through to TF-IDF
                    else:
                        # Let chromadb embed
                        col.upsert(
                            ids=[id],
                            documents=[text],
                            metadatas=[metadata],
                        )
                        return
                except Exception as exc:
                    log.warning("vector_store.chroma_add_failed", extra={
                        "collection": collection, "error": str(exc),
                    })

        # TF-IDF fallback
        tf = self._compute_tf(text)
        self._tfidf_store[collection][id] = {
            "text": text,
            "metadata": metadata,
            "tf": tf,
        }
        # Invalidate IDF cache for this collection
        if collection in self._idf_cache:
            del self._idf_cache[collection]

    def delete(self, collection: str, id: str):
        """Delete an item from a collection."""
        if self._backend in ("sentence-transformers+chromadb", "chromadb-default") and self._chroma_client:
            col = self._get_collection(collection)
            if col:
                try:
                    col.delete(ids=[id])
                    return
                except Exception as exc:
                    log.warning("vector_store.chroma_delete_failed", extra={
                        "collection": collection, "id": id, "error": str(exc),
                    })

        # TF-IDF
        if id in self._tfidf_store[collection]:
            del self._tfidf_store[collection][id]
            if collection in self._idf_cache:
                del self._idf_cache[collection]

    def query(self, collection: str, text: str, top_k: int = 5,
              where: Optional[Dict] = None) -> List[Dict]:
        """Query a collection for similar items."""
        if not text or not text.strip():
            return []

        if self._backend in ("sentence-transformers+chromadb", "chromadb-default"):
            col = self._get_collection(collection)
            if col:
                try:
                    if self._has_real_embeddings:
                        vec = self._embed(text)
                        if vec:
                            results = col.query(
                                query_embeddings=[vec],
                                n_results=top_k,
                                where=where,
                            )
                        else:
                            # Fall back to text query (chromadb default embedder)
                            results = col.query(
                                query_texts=[text],
                                n_results=top_k,
                                where=where,
                            )
                    else:
                        results = col.query(
                            query_texts=[text],
                            n_results=top_k,
                            where=where,
                        )
                    return self._format_chroma_results(results)
                except Exception as exc:
                    log.warning("vector_store.chroma_query_failed", extra={
                        "collection": collection, "error": str(exc),
                    })

        # TF-IDF fallback
        return self._tfidf_query(collection, text, top_k, where)

    def count(self, collection: str) -> int:
        """Count items in a collection."""
        if self._backend in ("sentence-transformers+chromadb", "chromadb-default"):
            col = self._get_collection(collection)
            if col:
                try:
                    return col.count()
                except Exception:
                    pass
        return len(self._tfidf_store[collection])

    def clear(self, collection: str):
        """Clear all items in a collection."""
        if self._backend in ("sentence-transformers+chromadb", "chromadb-default") and self._chroma_client:
            try:
                self._chroma_client.delete_collection(name=collection)
                if collection in self._collections:
                    del self._collections[collection]
                return
            except Exception as exc:
                log.warning("vector_store.chroma_clear_failed", extra={
                    "collection": collection, "error": str(exc),
                })
        self._tfidf_store[collection].clear()
        if collection in self._idf_cache:
            del self._idf_cache[collection]

    def stats(self) -> Dict:
        """Get stats for all collections."""
        stats: Dict[str, Any] = {
            "backend": self._backend,
            "has_real_embeddings": self._has_real_embeddings,
            "embedding_model": _embedding_model_name if self._has_real_embeddings else None,
            "collections": {},
        }
        if self._backend in ("sentence-transformers+chromadb", "chromadb-default") and self._chroma_client:
            try:
                for col_info in self._chroma_client.list_collections():
                    name = col_info.name if hasattr(col_info, "name") else str(col_info)
                    try:
                        col = self._chroma_client.get_collection(name)
                        stats["collections"][name] = col.count()
                    except Exception:
                        stats["collections"][name] = 0
            except Exception as exc:
                log.warning("vector_store.stats_failed", extra={"error": str(exc)})
        else:
            for name, items in self._tfidf_store.items():
                stats["collections"][name] = len(items)
        return stats

    # Alias for backward compatibility
    get_stats = stats

    def close(self):
        """Clean up resources."""
        if self._chroma_client:
            try:
                self._chroma_client.reset()
            except Exception:
                pass

    # ============================================================
    # Internal helpers
    # ============================================================

    def _format_chroma_results(self, results: Dict) -> List[Dict]:
        """Format ChromaDB query results to a consistent shape."""
        if not results or not results.get("ids"):
            return []
        out = []
        ids = results["ids"][0] if results["ids"] else []
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []
        for i, id_ in enumerate(ids):
            # Convert distance to similarity score (cosine distance → similarity)
            dist = distances[i] if i < len(distances) else 1.0
            score = 1.0 - dist if dist is not None else 0.0
            out.append({
                "id": id_,
                "text": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "score": round(score, 4),
            })
        return out

    # ===== TF-IDF implementation (fallback) =====

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize: split by non-word chars, keep CJK chars as single tokens."""
        tokens = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]', text.lower())
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
        df = defaultdict(int)
        for item in docs.values():
            for term in item["tf"]:
                df[term] += 1
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
        query_vec = {t: tf * idf.get(t, 0) for t, tf in query_tf.items()}
        query_norm = math.sqrt(sum(v ** 2 for v in query_vec.values())) or 1.0

        scored = []
        for doc_id, item in docs.items():
            if where:
                match = all(item["metadata"].get(k) == v for k, v in where.items())
                if not match:
                    continue
            doc_vec = {t: tf * idf.get(t, 0) for t, tf in item["tf"].items()}
            doc_norm = math.sqrt(sum(v ** 2 for v in doc_vec.values())) or 1.0
            dot = sum(query_vec.get(t, 0) * doc_vec.get(t, 0)
                      for t in query_vec if t in doc_vec)
            score = dot / (query_norm * doc_norm) if (query_norm and doc_norm) else 0
            scored.append((score, doc_id, item))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [
            {"id": doc_id, "text": item["text"], "metadata": item["metadata"], "score": round(score, 4)}
            for score, doc_id, item in scored[:top_k] if score > 0
        ]


# ============================================================
# Status helper for /api/vector-store/stats
# ============================================================

def get_status() -> Dict:
    """Get the global vector store status (for diagnostics)."""
    return {
        "sentence_transformers_available": ST_AVAILABLE,
        "chromadb_available": CHROMA_AVAILABLE,
        "default_model": DEFAULT_EMBEDDING_MODEL,
        "loaded_model": _embedding_model_name,
        "install_hint": (
            "pip install sentence-transformers chromadb"
            if not (ST_AVAILABLE and CHROMA_AVAILABLE)
            else "fully loaded"
        ),
    }
