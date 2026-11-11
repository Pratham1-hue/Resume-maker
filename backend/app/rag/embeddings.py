from __future__ import annotations

import os
from typing import List, Optional

from sentence_transformers import SentenceTransformer


# Local embeddings (default, free, no API key needed)
_embedding_model: Optional[SentenceTransformer] = None


def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """Get or create the embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(model_name)
        print(f"Loaded embedding model: {model_name}")
    return _embedding_model


def embed_texts(texts: List[str], model_name: str = "all-MiniLM-L6-v2") -> List[List[float]]:
    """Embed a list of texts using the specified model."""
    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings


def embed_query(text: str, model_name: str = "all-MiniLM-L6-v2") -> List[float]:
    """Embed a single query text."""
    return embed_texts([text], model_name)[0]