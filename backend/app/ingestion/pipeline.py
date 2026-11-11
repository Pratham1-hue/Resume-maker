from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.schemas.common import ChunkType, SourceChunk

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline: GitHub + Portfolio → chunks."""

    def __init__(self, github_client, portfolio_scraper, http_client):
        self.github_client = github_client
        self.portfolio_scraper = portfolio_scraper
        self.http_client = http_client

    async def run(
        self,
        profile_id: str,
        github_username: str,
        portfolio_url: str | None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Run the full ingestion pipeline and return results."""
        from app.core.jobs import job_registry
        from app.ingestion.html_cleaner import clean_html
        from app.ingestion.chunker import chunk_text
        from app.rag.vector_store import ChromaVectorStore

        chunks: List[SourceChunk] = []
        warnings: List[str] = []

        # Step 0: user-supplied evidence (work history, education).
        # Scraping can never see this, yet it is often where required
        # skills actually live — so it must be embedded like everything else.
        try:
            chunks.extend(self._user_chunks(profile_id))
        except Exception as exc:
            logger.warning("User-supplied chunking failed: %s", exc)

        # Step 1: GitHub
        logger.info("Fetching GitHub data for %s", github_username)
        try:
            github_data = await self.github_client.fetch_all(github_username)
            repo_chunks = self._repos_to_chunks(github_data, profile_id)
            chunks.extend(repo_chunks)
            top_languages = github_data.get("top_languages", {})
            profile = job_registry.get_profile(profile_id)
            if profile is not None:
                profile["top_languages"] = top_languages
        except Exception as exc:
            msg = f"GitHub fetch failed for {github_username}: {exc}"
            logger.warning(msg)
            warnings.append(msg)

        # Step 2: portfolio
        if portfolio_url:
            logger.info("Fetching portfolio data from %s", portfolio_url)
            try:
                portfolio_text = await self.portfolio_scraper.fetch(portfolio_url)
                if portfolio_text:
                    cleaned = clean_html(portfolio_text)
                    chunks.extend(chunk_text(cleaned, ChunkType.PORTFOLIO_SECTION, portfolio_url, profile_id))
                else:
                    warnings.append(f"Portfolio at {portfolio_url} yielded no readable text.")
            except Exception as exc:
                msg = f"Portfolio fetch failed: {exc or type(exc).__name__}"
                logger.warning(msg)
                warnings.append(msg)

        # Step 3: dedupe
        chunks = self._deduplicate_chunks(chunks)

        # Step 4: store (one Chroma collection per profile)
        try:
            store = ChromaVectorStore()
            await store.upsert_chunks(profile_id=profile_id, chunks=chunks, overwrite=True)
        except Exception as exc:
            msg = f"Vector store write failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)

        job_registry.complete_ingest(
            profile_id,
            len(chunks),
            warnings=warnings,
            chunk_types=self._count_chunk_types(chunks),
        )

        return {
            "profile_id": profile_id,
            "chunk_count": len(chunks),
            "status": "completed",
            "chunk_types": self._count_chunk_types(chunks),
            "warnings": warnings,
            "last_ingested_at": _utcnow_iso(),
        }

    def _user_chunks(self, profile_id: str) -> List[SourceChunk]:
        """Embed work history + education from the profile itself."""
        from app.core.jobs import job_registry
        from app.ingestion.chunker import chunk_text

        profile = job_registry.get_profile(profile_id) or {}
        chunks: List[SourceChunk] = []
        for job in profile.get("work_history", []) or []:
            if not isinstance(job, dict):
                continue
            text = " ".join(
                part for part in [
                    f"{job.get('title', '')} at {job.get('company', '')}".strip(),
                    f"{job.get('start_date', '')} to {job.get('end_date') or 'present'}",
                    job.get("description", "") or "",
                ] if part.strip()
            )
            if text.strip():
                chunks.extend(chunk_text(text, ChunkType.USER_SUPPLIED, "work-history", profile_id))
        for edu in profile.get("education", []) or []:
            if not isinstance(edu, dict):
                continue
            text = " ".join(
                part for part in [
                    str(edu.get("degree", "")),
                    str(edu.get("field_of_study", "")),
                    f"at {edu.get('institution', '')}",
                ] if part.strip()
            )
            if text.strip():
                chunks.extend(chunk_text(text, ChunkType.USER_SUPPLIED, "education", profile_id))
        return chunks

    def _repos_to_chunks(self, github_data: dict, profile_id: str) -> List[SourceChunk]:
        from app.ingestion.html_cleaner import clean_html
        from app.ingestion.chunker import chunk_text

        chunks: List[SourceChunk] = []
        for repo in github_data.get("repos", []):
            if not isinstance(repo, dict):
                continue
            name = repo.get("name", "repo")
            readme = repo.get("readme", "") or repo.get("description", "") or ""
            if readme.strip():
                cleaned = clean_html(readme)
                chunks.extend(chunk_text(cleaned, ChunkType.REPO_README, name, profile_id))

            metadata = repo.get("metadata", {}) or {}
            description = repo.get("description", "") or ""
            topics = metadata.get("topics", []) or []
            languages = metadata.get("languages", {}) or {}
            stars = metadata.get("stars", 0) or 0
            meta_text = (
                f"Repository {name}: {description} "
                f"Topics: {', '.join(topics)} "
                f"Languages: {', '.join(languages.keys())} "
                f"Stars: {stars}"
            ).strip()
            chunks.append(
                SourceChunk(
                    chunk_id=f"gh:{name}:metadata",
                    profile_id=profile_id,
                    chunk_type=ChunkType.REPO_METADATA,
                    text=meta_text[:500],
                    source_url=repo.get("html_url"),
                    repo_name=name,
                    languages=list(languages.keys()),
                    topics=list(topics),
                    stars=int(stars) if isinstance(stars, int) else None,
                )
            )
        return chunks

    @staticmethod
    def _deduplicate_chunks(chunks: List[SourceChunk]) -> List[SourceChunk]:
        seen: set[str] = set()
        unique: List[SourceChunk] = []
        for chunk in chunks:
            norm = chunk.text.strip()[:100]
            if norm not in seen:
                seen.add(norm)
                unique.append(chunk)
        return unique

    @staticmethod
    def _count_chunk_types(chunks: List[SourceChunk]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for chunk in chunks:
            ctype = chunk.chunk_type.value
            counts[ctype] = counts.get(ctype, 0) + 1
        return counts


async def run_ingestion_pipeline(
    profile_id: str,
    github_username: str,
    portfolio_url: str | None = None,
) -> Dict[str, Any]:
    """Convenience entry point used by background tasks."""
    import httpx

    from app.core.jobs import job_registry
    from app.ingestion.github_client import GitHubClient
    from app.ingestion.portfolio_scraper import PortfolioScraper

    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            pipeline = IngestionPipeline(
                github_client=GitHubClient(http_client),
                portfolio_scraper=PortfolioScraper(http_client),
                http_client=http_client,
            )
            return await pipeline.run(profile_id, github_username, portfolio_url)
    except Exception as exc:
        job_registry.fail_ingest(profile_id, str(exc))
        raise
