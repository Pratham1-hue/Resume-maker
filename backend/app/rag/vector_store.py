from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from app.schemas.common import SourceChunk


def _collection_name_for(profile_id: str) -> str:
    # profile IDs already look like "profile_<hex>"; avoid "profile_profile_...".
    if profile_id.startswith("profile_"):
        return profile_id
    return f"profile_{profile_id}"


def _meta_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _str_to_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        # Try JSON first (we store JSON for round-trip fidelity), else CSV.
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except Exception:
            pass
        return [p.strip() for p in value.split(",") if p.strip()]
    return []


class ChromaVectorStore:
    """ChromaDB vector store: collection-per-profile, upsert, delete."""

    def __init__(self, persist_dir: str | None = None):
        try:
            import chromadb
        except ImportError as exc:
            raise ImportError(
                "chromadb is not installed. Run `pip install chromadb`."
            ) from exc
        # Honor CHROMA_PERSIST_DIR (set by docker-compose) so data survives restarts.
        persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        # chromadb>=1.x: PersistentClient takes only `path`.
        self.client = chromadb.PersistentClient(path=persist_dir)

    def _get_collection(self, profile_id: str):
        """Get or create a Chroma collection for a profile."""
        return self.client.get_or_create_collection(name=_collection_name_for(profile_id))

    async def upsert_chunks(
        self,
        profile_id: str,
        chunks: List[SourceChunk],
        overwrite: bool = True,
    ) -> None:
        """Upsert chunks into the profile's Chroma collection."""
        from app.rag.embeddings import embed_texts

        if not chunks:
            return
        collection = self._get_collection(profile_id)
        if overwrite:
            try:
                self.client.delete_collection(name=_collection_name_for(profile_id))
                collection = self._get_collection(profile_id)
            except Exception:
                pass

        texts = [chunk.text for chunk in chunks]
        embeddings = embed_texts(texts)

        # Chroma metadata values must be str/int/float/bool (no lists).
        ids = [chunk.chunk_id for chunk in chunks]
        metadatas = [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_type": chunk.chunk_type.value,
                "profile_id": chunk.profile_id,
                "source_url": _meta_to_str(chunk.source_url),
                "repo_name": _meta_to_str(chunk.repo_name),
                "section_heading": _meta_to_str(chunk.section_heading),
                "languages": json.dumps(chunk.languages or []),
                "topics": json.dumps(chunk.topics or []),
                "stars": int(chunk.stars or 0),
            }
            for chunk in chunks
        ]

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            collection.upsert(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

    async def delete_profile(self, profile_id: str) -> None:
        """Delete all chunks for a profile."""
        try:
            self.client.delete_collection(name=_collection_name_for(profile_id))
        except Exception:
            pass

    async def query(
        self,
        profile_id: str,
        query_text: str,
        k: int = 10,
        mmr: bool = True,
        fetch_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """Query the profile's collection for similar chunks (with MMR option)."""
        from app.rag.embeddings import embed_texts

        collection = self._get_collection(profile_id)
        try:
            count = collection.count()
        except Exception:
            count = 0
        if count == 0:
            return []

        query_embedding = embed_texts([query_text])[0]
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(fetch_k, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []
        ids = (results.get("ids") or [[]])[0] or []

        formatted: List[Dict[str, Any]] = []
        for idx, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            meta = dict(meta or {})
            if not meta.get("chunk_id") and idx < len(ids):
                meta["chunk_id"] = ids[idx]
            similarity = 1 - dist if dist is not None else 0.0
            formatted.append({"text": doc or "", "metadata": meta, "score": similarity})

        if mmr and len(formatted) > k:
            formatted = self._mmr(formatted, k)
        return formatted[:k]

    @staticmethod
    def _mmr(results: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
        """Maximal Marginal Relevance diversity filter."""
        if len(results) <= k:
            return results

        selected: List[Dict[str, Any]] = []
        remaining = sorted(list(results), key=lambda x: x.get("score", 0), reverse=True)
        if remaining:
            selected.append(remaining.pop(0))

        while len(selected) < k and remaining:
            best_idx = 0
            best_score = float("-inf")
            for i, candidate in enumerate(remaining):
                relevance = candidate.get("score", 0)
                max_sim = 0.0
                for sel in selected:
                    candidate_words = set(candidate.get("text", "").lower().split())
                    sel_words = set(sel.get("text", "").lower().split())
                    if sel_words:
                        overlap = len(candidate_words & sel_words) / len(sel_words)
                        max_sim = max(max_sim, overlap)
                mmr_score = relevance - 0.5 * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return selected


async def upsert_chunks_to_chroma(
    collection_name: str,
    chunks: List[SourceChunk],
    overwrite: bool = True,
) -> None:
    """Compatibility wrapper: upsert chunks into a named collection.

    `collection_name` is expected to look like "profile_<id>".
    """
    profile_id = collection_name
    if profile_id.startswith("profile_"):
        profile_id = profile_id[len("profile_"):]
    store = ChromaVectorStore()
    await store.upsert_chunks(profile_id=profile_id, chunks=chunks, overwrite=overwrite)
