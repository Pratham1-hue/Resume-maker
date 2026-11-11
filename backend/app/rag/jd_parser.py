from __future__ import annotations

import json
import logging
import re
from collections import Counter

from app.schemas.job import ParsedJobRequirements

logger = logging.getLogger(__name__)

# Common tech tokens the heuristic fallback can recognise.
_KNOWN_TECH = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby",
    "php", "swift", "kotlin", "scala", "r", "sql", "nosql",
    "react", "angular", "vue", "next.js", "node.js", "express", "django",
    "flask", "fastapi", "spring", "rails", "laravel",
    "docker", "kubernetes", "terraform", "jenkins", "ci/cd", "git", "linux",
    "aws", "azure", "gcp", "postgres", "postgresql", "mysql", "mongodb",
    "redis", "elasticsearch", "kafka", "rabbitmq", "graphql", "rest",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "spark",
    "airflow", "mlflow", "figma", "tableau", "powerbi",
}


class JDParser:
    """Parse a raw job description into structured requirements.

    Uses the LLM when credentials are configured; otherwise falls back to a
    deterministic keyword heuristic so alignment still works offline.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def parse(self, raw_text: str) -> ParsedJobRequirements:
        """Parse a raw job description into structured requirements."""
        if self.llm_client is not None:
            try:
                return await self._parse_with_llm(raw_text)
            except Exception as exc:
                logger.warning("LLM JD parse failed, using heuristic fallback: %s", exc)
        return self._parse_heuristic(raw_text)

    async def _parse_with_llm(self, raw_text: str) -> ParsedJobRequirements:
        system_prompt = (
            "You are an expert technical recruiter. "
            "Parse the job description below and extract the structured requirements.\n\n"
            "Return ONLY a valid JSON object with these fields:\n"
            "- required_skills: list of required technical skills\n"
            "- preferred_skills: list of preferred/bonus skills\n"
            "- responsibilities: list of 5-10 key responsibilities\n"
            "- domain_keywords: list of domain-specific keywords\n"
            "- seniority: one of junior, mid-level, senior, lead, principal, or null\n"
            "- soft_skills: list of 3-5 soft skills\n\n"
            "If any field has no clear information, use an empty list []. "
            "Return only the JSON, no surrounding text."
        )
        user_prompt = f"Job Description:\n\n{raw_text}\n\nParse this into the structured JSON format described above."

        response = await self.llm_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=1000,
        )
        data = self._extract_json(response)
        return ParsedJobRequirements(
            required_skills=[str(s) for s in data.get("required_skills", []) or []],
            preferred_skills=[str(s) for s in data.get("preferred_skills", []) or []],
            responsibilities=[str(s) for s in data.get("responsibilities", []) or []],
            domain_keywords=[str(s) for s in data.get("domain_keywords", []) or []],
            seniority=data.get("seniority"),
            soft_skills=[str(s) for s in data.get("soft_skills", []) or []],
        )

    @staticmethod
    def _extract_json(response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        # Strip markdown fences if the model added them.
        cleaned = re.sub(r"^```(?:json)?\s*", "", response.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end])
        raise ValueError("LLM response contained no JSON object")

    @classmethod
    def _parse_heuristic(cls, raw_text: str) -> ParsedJobRequirements:
        text = raw_text or ""
        lowered = text.lower()
        words = set(re.findall(r"[a-zA-Z][a-zA-Z+#./-]*", lowered))
        found = sorted({t for t in _KNOWN_TECH if t in words})

        # Split into candidate responsibility lines.
        lines = [ln.strip("-•* \t") for ln in re.split(r"[\n;]+", text)]
        responsibilities = [ln[:200] for ln in lines if 20 < len(ln) < 220][:8]

        seniority = None
        for level in ("principal", "lead", "senior", "mid-level", "mid level", "junior"):
            if level in lowered:
                seniority = "mid-level" if level == "mid level" else level
                break

        counts = Counter(re.findall(r"[a-zA-Z][a-zA-Z+#./-]{2,}", lowered))
        stopwords = {
            "the", "and", "for", "with", "you", "your", "our", "will", "from",
            "have", "has", "are", "that", "this", "with", "job", "role", "team",
        }
        domain_keywords = [w for w, _ in counts.most_common(30) if w not in stopwords and w not in found][:10]

        return ParsedJobRequirements(
            required_skills=found[:12],
            preferred_skills=[],
            responsibilities=responsibilities,
            domain_keywords=domain_keywords,
            seniority=seniority,
            soft_skills=[s for s in ("communication", "collaboration", "problem-solving") if s in lowered],
        )
