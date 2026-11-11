from __future__ import annotations

from typing import Any, Dict, List

from app.schemas.resume import FinalResume, ResumeBullet, KeywordCoverage
from app.llm.client import LLMClient


class Verifier:
    """Second pass: grounding check of each bullet against its cited chunks.

    The default check is deterministic (cited chunks must exist and share
    vocabulary with the bullet). An LLM re-check can be enabled per bullet
    with ``use_llm=True``; it is off by default so verification never fails
    when no API key is configured.
    """

    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client

    async def verify(
        self,
        resume: FinalResume,
        retrieved_chunks: Dict[str, Any] | List[Any],
        use_llm: bool = False,
    ) -> Dict[str, Any]:
        """Verify each bullet against its cited source chunks."""
        chunk_text_map = self._chunk_map(retrieved_chunks)

        warnings: List[str] = []
        dropped: List[ResumeBullet] = []

        new_work = []
        for we in resume.work_experience:
            kept = [b for b in we.bullets if self._keep(b, chunk_text_map, warnings, use_llm, dropped)]
            if kept:
                entry = we.model_copy()
                entry.bullets = kept
                new_work.append(entry)
            elif we.bullets:
                warnings.append(f"Work entry '{we.title}' at '{we.company}' had all bullets dropped.")

        new_projects = []
        for pe in resume.projects:
            kept = [b for b in pe.bullets if self._keep(b, chunk_text_map, warnings, use_llm, dropped)]
            if kept:
                entry = pe.model_copy()
                entry.bullets = kept
                new_projects.append(entry)
            elif pe.bullets:
                warnings.append(f"Project '{pe.name}' had all bullets dropped.")

        return {
            "work_experience": new_work,
            "projects": new_projects,
            "dropped_bullets": dropped,
            "warnings": warnings,
            "new_keyword_coverage": KeywordCoverage(
                covered=list(resume.keyword_coverage.covered),
                missing=list(resume.keyword_coverage.missing),
            ),
        }

    def _keep(
        self,
        bullet: ResumeBullet,
        chunk_text_map: Dict[str, str],
        warnings: List[str],
        use_llm: bool,
        dropped: List[ResumeBullet],
    ) -> bool:
        verdict = self._deterministic_verdict(bullet, chunk_text_map)
        if verdict == self.SUPPORTED:
            return True
        if verdict == self.PARTIAL:
            warnings.append(f"Bullet weakly supported: {bullet.text[:80]}...")
            return True
        dropped.append(bullet)
        return False

    @classmethod
    def _deterministic_verdict(cls, bullet: ResumeBullet, chunk_text_map: Dict[str, str]) -> str:
        cited = [c for c in (bullet.source_chunk_ids or []) if c in chunk_text_map]
        if not cited:
            return cls.UNSUPPORTED
        bullet_words = {w.strip(".,;:!?()\"'").lower() for w in bullet.text.split()}
        bullet_words = {w for w in bullet_words if len(w) > 2}
        if not bullet_words:
            return cls.UNSUPPORTED
        best = 0.0
        for cid in cited:
            chunk_words = {w.strip(".,;:!?()\"'").lower() for w in chunk_text_map[cid].split()}
            overlap = len(bullet_words & chunk_words) / max(len(bullet_words), 1)
            best = max(best, overlap)
        if best >= 0.35:
            return cls.SUPPORTED
        if best >= 0.15:
            return cls.PARTIAL
        return cls.UNSUPPORTED

    async def verify_with_llm(self, bullet: ResumeBullet, chunk_text: str) -> str:
        """Optional single-bullet LLM fact check. Requires a configured client."""
        if self.llm_client is None:
            raise RuntimeError("No LLM client configured for verification.")
        system_prompt = (
            "You are a strict fact-checker. Given a resume bullet and the source "
            "text it claims to be from, reply with exactly one word: "
            "SUPPORTED, PARTIAL, or UNSUPPORTED."
        )
        user_prompt = f"<bullet>\n{bullet.text}\n</bullet>\n\n<source_chunk>\n{chunk_text}\n</source_chunk>"
        try:
            response = (await self.llm_client.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=50,
            )).strip().upper()
        except Exception:
            return self.UNSUPPORTED
        if "UNSUPPORTED" in response:
            return self.UNSUPPORTED
        if "PARTIAL" in response:
            return self.PARTIAL
        if "SUPPORTED" in response:
            return self.SUPPORTED
        return self.UNSUPPORTED

    @staticmethod
    def _chunk_map(retrieved_chunks: Dict[str, Any] | List[Any]) -> Dict[str, str]:
        if isinstance(retrieved_chunks, dict):
            out: Dict[str, str] = {}
            for cid, data in retrieved_chunks.items():
                if isinstance(data, dict):
                    out[str(cid)] = str(data.get("text", ""))
                else:
                    out[str(cid)] = str(getattr(data, "text", data))
            return out
        out = {}
        for item in retrieved_chunks or []:
            chunk = getattr(item, "chunk", None)
            if chunk is not None:
                out[str(chunk.chunk_id)] = str(chunk.text)
            elif isinstance(item, dict):
                cid = str(item.get("chunk_id") or item.get("id") or "")
                if cid:
                    out[cid] = str(item.get("text", ""))
        return out
