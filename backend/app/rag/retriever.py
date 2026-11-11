from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.common import ChunkType, SourceChunk, RetrievedChunk, ParsedJobRequirements
from app.rag.vector_store import ChromaVectorStore, _str_to_list


def _coerce_chunk_type(value: Any) -> ChunkType:
    try:
        return ChunkType(str(value))
    except Exception:
        return ChunkType.REPO_README


def _coerce_list(value: Any) -> List[str]:
    return _str_to_list(value)


def _build_source_chunk(meta: Dict[str, Any], text: str, profile_id: str, fallback_id: str) -> SourceChunk:
    chunk_id = str(meta.get("chunk_id") or meta.get("id") or fallback_id or "").strip()
    if not chunk_id:
        import uuid
        chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
    stars = meta.get("stars", 0)
    try:
        stars_int = int(stars) if stars not in (None, "") else None
    except Exception:
        stars_int = None
    return SourceChunk(
        chunk_id=chunk_id,
        profile_id=profile_id,
        chunk_type=_coerce_chunk_type(meta.get("chunk_type", "repo_readme")),
        text=text or "",
        source_url=meta.get("source_url") or None,
        repo_name=meta.get("repo_name") or None,
        section_heading=meta.get("section_heading") or None,
        languages=_coerce_list(meta.get("languages", [])),
        topics=_coerce_list(meta.get("topics", [])),
        stars=stars_int,
    )


class MultiQueryRetriever:
    """Multi-query retrieval + MMR + dedupe for RAG.

    Retrieves separately for each JD requirement group (required skills,
    responsibilities, domain keywords), then merges, dedupes, and applies MMR.
    """

    def __init__(self, vector_store: ChromaVectorStore, top_k: int = 12):
        self.vector_store = vector_store
        self.top_k = top_k

    async def retrieve_for_jd(
        self,
        profile_id: str,
        jd_requirements: ParsedJobRequirements,
    ) -> List[RetrievedChunk]:
        """Retrieve chunks relevant to a job description's requirements."""
        queries: List[tuple[str, str]] = []
        for skill in (jd_requirements.required_skills or [])[:5]:
            queries.append((f"skill: {skill}", skill))
        for resp in (jd_requirements.responsibilities or [])[:3]:
            queries.append((f"responsibility: {resp}", resp))
        for kw in (jd_requirements.domain_keywords or [])[:5]:
            queries.append((f"keyword: {kw}", kw))
        full_jd_text = self._build_full_jd_text(jd_requirements)
        if full_jd_text.strip():
            queries.append((full_jd_text, "full_jd"))

        retrieved_chunks: List[RetrievedChunk] = []
        for query_text, label in queries:
            try:
                results = await self.vector_store.query(
                    profile_id=profile_id,
                    query_text=query_text,
                    k=3,
                    mmr=True,
                )
            except Exception:
                continue
            for idx, r in enumerate(results):
                meta = r.get("metadata") or {}
                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk=_build_source_chunk(
                            meta,
                            r.get("text", ""),
                            profile_id,
                            f"q{len(retrieved_chunks)}:{idx}",
                        ),
                        score=float(r.get("score", 0.0)),
                        matched_requirement=label,
                    )
                )

        # Deduplicate: keep the highest-scoring entry for each chunk_id.
        seen_ids: Dict[str, RetrievedChunk] = {}
        for rc in retrieved_chunks:
            cid = rc.chunk.chunk_id
            if cid not in seen_ids or rc.score > seen_ids[cid].score:
                seen_ids[cid] = rc

        deduped = list(seen_ids.values())
        deduped.sort(key=lambda x: x.score, reverse=True)
        return deduped[:self.top_k]

    @staticmethod
    def _build_full_jd_text(parsed: ParsedJobRequirements) -> str:
        """Build a comprehensive text representation of the JD for retrieval."""
        parts: List[str] = []
        parts.extend(parsed.required_skills or [])
        parts.extend(parsed.preferred_skills or [])
        parts.extend(parsed.responsibilities or [])
        parts.extend(parsed.domain_keywords or [])
        return " ".join(parts)
