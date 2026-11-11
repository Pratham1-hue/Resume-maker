from __future__ import annotations

import re
from typing import List

from app.schemas.common import ChunkType, SourceChunk


def chunk_text(
    text: str,
    chunk_type: ChunkType,
    source: str = "",
    profile_id: str = "",
) -> List[SourceChunk]:
    """Semantic chunking: heading-aware, ~300-500 tokens per chunk.

    Splits large bodies of text into manageable chunks while preserving
    heading context. Each chunk gets a unique chunk_id.
    """
    if not text or not text.strip():
        return []

    if isinstance(chunk_type, str):
        try:
            chunk_type = ChunkType(chunk_type)
        except Exception:
            chunk_type = ChunkType.REPO_README

    # Normalize whitespace
    text = " ".join(text.strip().split())

    chunks: List[SourceChunk] = []

    # Strategy: split by major headings (H1, H2, H3 in markdown or HTML)
    # Heuristic: split on lines that look like headings (# text, **text**, or all-caps short lines)
    heading_pattern = re.compile(r"^(#{1,3}\s+.+|^\*\*+.+\*\*|^[A-Z][A-Z\s]{3,}$)", re.MULTILINE)

    # Find all heading positions
    headings = list(heading_pattern.finditer(text))

    if not headings:
        # No headings found - split into fixed-size pieces (never truncate).
        return [
            SourceChunk(
                chunk_id=f"{chunk_type.value}:{source}:{idx:03d}",
                profile_id=profile_id,
                chunk_type=chunk_type,
                text=piece[:2000],
                source_url=source if chunk_type == ChunkType.REPO_README else None,
                repo_name=source if chunk_type == ChunkType.REPO_README else None,
            )
            for idx, piece in enumerate(_split_by_size(text, 1500), start=1)
        ]

    # Split text by headings
    last_end = 0
    for i, heading_match in enumerate(headings):
        heading_start = heading_match.start()
        heading_text = heading_match.group()

        # Add text before this heading as a chunk (if there's content)
        if last_end < heading_start:
            before_text = text[last_end:heading_start].strip()
            if before_text:
                chunk_id = f"{chunk_type.value}:{source}:{i:03d}"
                chunks.append(
                    SourceChunk(
                        chunk_id=chunk_id,
                        profile_id=profile_id,
                        chunk_type=chunk_type,
                        text=before_text[:500],
                        source_url=source if chunk_type == ChunkType.REPO_README else None,
                        repo_name=source if chunk_type == ChunkType.REPO_README else None,
                        section_heading=heading_text if i > 0 else None,
                    )
                )

        # The heading itself becomes a chunk (or we skip it and use it as context)
        last_end = heading_match.end()

    # Add remaining text after last heading
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            chunk_id = f"{chunk_type.value}:{source}:{len(headings):03d}"
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    profile_id=profile_id,
                    chunk_type=chunk_type,
                    text=remaining[:500],
                    source_url=source if chunk_type == ChunkType.REPO_README else None,
                    repo_name=source if chunk_type == ChunkType.REPO_README else None,
                    section_heading=headings[-1].group() if headings else None,
                )
            )

    # If we have fewer than 2 chunks and text is long, split by token count
    if len(chunks) <= 1:
        # Heading split produced nothing useful (e.g. the whole text matched
        # as one heading). Fall back to fixed-size pieces so text is never lost.
        pieces = _split_by_size(text, 1500)
        if pieces and (len(chunks) == 0 or len(text) > 800):
            chunks = []
            for idx, piece in enumerate(pieces, start=1):
                chunks.append(
                    SourceChunk(
                        chunk_id=f"{chunk_type.value}:{source}:{idx:03d}",
                        profile_id=profile_id,
                        chunk_type=chunk_type,
                        text=piece[:2000],
                        source_url=source if chunk_type == ChunkType.REPO_README else None,
                        repo_name=source if chunk_type == ChunkType.REPO_README else None,
                    )
                )

    return chunks


def _split_by_size(text: str, size: int) -> List[str]:
    """Split text into word-boundary pieces of roughly `size` chars."""
    words = text.split()
    pieces: List[str] = []
    current: List[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > size and current:
            pieces.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces or ([text] if text else [])