from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.schemas.resume import (
    FinalResume,
    ResumeBullet,
    ResumeSkillGroup,
    ResumeHeader,
    ResumeWorkEntry,
    ResumeProjectEntry,
    ResumeEducation,
    KeywordCoverage,
)
from app.schemas.profile import UserProfile
from app.schemas.job import AlignRequest, ParsedJobRequirements
from app.rag.retriever import MultiQueryRetriever
from app.llm.client import LLMClient, LLMError


class AlignmentOutput(BaseModel):
    """Exactly what the alignment LLM is asked to return.

    Header/education/ids are filled in by the application afterwards, so
    validating the raw LLM JSON against FinalResume would always fail.
    """

    summary: str = ""
    skills: List[ResumeSkillGroup] = []
    work_experience: List[ResumeWorkEntry] = []
    projects: List[ResumeProjectEntry] = []
    keyword_coverage: KeywordCoverage = KeywordCoverage()
    warnings: List[str] = []


class Aligner:
    """Builds the alignment prompt, calls the LLM, parses JSON, and retries on validation errors."""

    def __init__(self, llm_client: LLMClient, retriever: MultiQueryRetriever):
        self.llm_client = llm_client
        self.retriever = retriever

    async def align(self, profile: UserProfile, request: AlignRequest) -> Dict[str, Any]:
        """Run the alignment phase: retrieve context → generate tailored resume JSON."""

        # Step 1: Parse the job description
        # We need the raw text; request.raw_text is the full JD
        # For parsing, we'll do a quick parse or use the request if already parsed
        # For now, treat raw_text as already parseable or do a light parse
        from app.rag.jd_parser import JDParser
        parser = JDParser(llm_client=self.llm_client)
        parsed_jd = await parser.parse(request.raw_text)

        # Step 2: Retrieve relevant chunks
        retrieved = await self.retriever.retrieve_for_jd(
            profile_id=profile.id,
            jd_requirements=parsed_jd,
        )

        # Step 3: Build the alignment prompt
        context_text = self._build_context(retrieved)
        profile_json = profile.model_dump(mode="json")

        # Step 4: Call LLM with the alignment prompt.
        # Small local models degrade on long instruction sets, so they get a
        # compact prompt with the same JSON contract.
        if getattr(self.llm_client, "provider", "") == "ollama":
            system_prompt = self._get_compact_system_prompt()
        else:
            system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(
            jd_title=request.title,
            jd_company=request.company,
            parsed_jd=parsed_jd,
            profile=profile_json,
            retrieved_context=context_text,
            max_projects=request.max_projects,
        )

        raw_response = await self.llm_client.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=4096,
        )

        # Step 5: Parse the JSON response (tolerate markdown fences).
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(cleaned[start:end])
            else:
                raise ValueError(f"Could not parse LLM response as JSON: {raw_response[:200]}")

        # Step 6: Validate the LLM output (header/education are app-filled).
        # Small/local models are sloppy with the schema (nulls, missing keys),
        # so sanitize first instead of failing the whole request.
        try:
            output = AlignmentOutput.model_validate(self._sanitize_output(result))
        except Exception as exc:
            raise LLMError(f"Model returned invalid resume JSON: {exc}") from exc
        resume_dict = self._resume_to_dict(output)
        resume_dict["projects"] = resume_dict["projects"][: request.max_projects]
        # Step 7: deterministic coverage pass. The LLM sometimes marks a JD
        # keyword "missing" even though the retrieved evidence contains it
        # verbatim — substring matching over the same evidence recovers those.
        resume_dict["keyword_coverage"] = self._merge_coverage(
            parsed_jd, retrieved, output.keyword_coverage
        )
        # Flag thin generations (common with small local models) so the UI
        # can explain the blank sections instead of just showing them.
        has_content = bool(
            resume_dict["summary"].strip()
            or resume_dict["skills"]
            or resume_dict["work_experience"]
            or resume_dict["projects"]
        )
        if not has_content:
            resume_dict["warnings"] = list(resume_dict["warnings"]) + [
                "The model returned an incomplete resume (empty summary and sections). "
                "This happens with small local models on long prompts — retry, shorten "
                "the job description, or use a larger model."
            ]
        return resume_dict

    @staticmethod
    def _sanitize_output(result: Any) -> Dict[str, Any]:
        """Coerce sloppy model JSON into schema-valid shape.

        Small models emit nulls/missing keys (e.g. start_date: null,
        bullets without citations). Fix them here so one malformed field
        never fails the entire alignment.
        """
        if not isinstance(result, dict):
            return {}
        out: Dict[str, Any] = {
            "summary": result.get("summary") or "",
            "warnings": [str(w) for w in result.get("warnings", []) or []],
        }

        def _bullets(items: Any) -> list:
            clean = []
            for b in items or []:
                if not isinstance(b, dict):
                    continue
                text = str(b.get("text") or "").strip()
                if not text:
                    continue
                cites = b.get("source_chunk_ids") or []
                clean.append({
                    "text": text[:300],
                    "source_chunk_ids": [str(c) for c in cites] or ["profile"],
                    "matched_keywords": [str(k) for k in b.get("matched_keywords", []) or []],
                })
            return clean

        skills = []
        for g in result.get("skills", []) or []:
            if not isinstance(g, dict):
                continue
            skills.append({
                "category": str(g.get("category") or "Skills"),
                "skills": [str(s) for s in g.get("skills", []) or []],
            })
        out["skills"] = skills

        work = []
        for w in result.get("work_experience", []) or []:
            if not isinstance(w, dict):
                continue
            bullets = _bullets(w.get("bullets"))
            # Drop vacuous entries (no company/title/bullets) — they render
            # as empty ghost cards and pollute exports.
            if not str(w.get("company") or "").strip() and not str(w.get("title") or "").strip() and not bullets:
                continue
            work.append({
                "company": str(w.get("company") or ""),
                "title": str(w.get("title") or ""),
                "start_date": str(w.get("start_date") or ""),
                "end_date": w.get("end_date"),
                "bullets": bullets,
            })
        out["work_experience"] = work

        projects = []
        for p in result.get("projects", []) or []:
            if not isinstance(p, dict):
                continue
            bullets = _bullets(p.get("bullets"))
            if not str(p.get("name") or "").strip() and not bullets:
                continue
            projects.append({
                "name": str(p.get("name") or ""),
                "url": p.get("url"),
                "technologies": [str(t) for t in p.get("technologies", []) or []],
                "bullets": bullets,
            })
        out["projects"] = projects

        kc = result.get("keyword_coverage", {}) or {}
        out["keyword_coverage"] = {
            "covered": [str(c) for c in kc.get("covered", []) or []],
            "missing": [str(m) for m in kc.get("missing", []) or []],
        }
        return out

    @staticmethod
    def _merge_coverage(
        parsed_jd: ParsedJobRequirements,
        retrieved: List["RetrievedChunk"],
        llm_coverage: KeywordCoverage,
    ) -> Dict[str, list]:
        """Union LLM coverage with evidence-substring coverage."""
        evidence = " ".join(c.chunk.text for c in retrieved).lower()

        def _hit(term_lc: str) -> bool:
            if term_lc in evidence:
                return True
            # Plural/singular tolerance: "REST APIs" matches "REST API".
            if len(term_lc) > 3 and term_lc.endswith("s") and term_lc[:-1] in evidence:
                return True
            if len(term_lc) > 3 and (term_lc + "s") in evidence:
                return True
            return False

        jd_terms: List[str] = []
        for term in (parsed_jd.required_skills + parsed_jd.preferred_skills + parsed_jd.domain_keywords):
            term = str(term).strip()
            if term and term.lower() not in {t.lower() for t in jd_terms}:
                jd_terms.append(term)
        hits = {t for t in jd_terms if _hit(t.lower())}
        covered = list(dict.fromkeys(list(llm_coverage.covered) + sorted(hits)))
        covered_lc = {c.lower() for c in covered}
        missing = [t for t in jd_terms if t.lower() not in covered_lc]
        # Keep LLM-flagged missing terms that are not JD terms (extra signal).
        for m in llm_coverage.missing:
            if m not in missing and m.lower() not in covered_lc:
                missing.append(m)
        return {"covered": covered, "missing": missing}

    def _build_context(self, retrieved: List["RetrievedChunk"]) -> str:
        """Build the <retrieved_context> XML block from retrieved chunks."""
        parts: List[str] = []
        for item in retrieved:
            chunk = item.chunk
            parts.append(
                f'<chunk id="{chunk.chunk_id}" type="{chunk.chunk_type.value}" '
                f'source="{chunk.source_url or ""}" relevance="{item.score:.2f}">'
                f'{chunk.text}</chunk>'
            )
        return "\n".join(parts)

    def _get_compact_system_prompt(self) -> str:
        """Short prompt for small/local models: same JSON contract, minimal rules."""
        return """You write tailored resumes using ONLY the candidate evidence given.

Rules:
1. Every skill, bullet, number, and name must appear in <retrieved_context> or <candidate_profile>. Never invent.
2. If the job wants something with no evidence, put it in keyword_coverage.missing, never in the resume.
3. Pick the most job-relevant projects/work (at most the requested max). 2-3 bullets each.
4. Each bullet: past-tense verb + what was built + technologies. Cite chunk_id(s) in source_chunk_ids.
5. Summary: 2 sentences, no "I", only evidenced strengths.

Return ONLY one JSON object, no fences, exactly this shape:
{
  "summary": string,
  "skills": [{"category": string, "skills": [string]}],
  "work_experience": [{
    "company": string, "title": string,
    "start_date": string, "end_date": string | null,
    "bullets": [{"text": string, "source_chunk_ids": [string], "matched_keywords": [string]}]
  }],
  "projects": [{
    "name": string, "url": string | null, "technologies": [string],
    "bullets": [{"text": string, "source_chunk_ids": [string], "matched_keywords": [string]}]
  }],
  "keyword_coverage": {"covered": [string], "missing": [string]},
  "warnings": [string]
}"""

    def _get_system_prompt(self) -> str:
        """Return the alignment system prompt."""
        return """You are an expert technical resume writer and a strict fact-checker, combined.
Your job is to produce a resume tailored to a specific job description, using
ONLY evidence supplied in the candidate's source material.

# GROUNDING RULES (highest priority)
1. EVIDENCE-ONLY: Every claim must be directly supported by text in <retrieved_context> or <candidate_profile>.
2. NO INVENTED SKILLS: Never add a skill the JD wants but the evidence doesn't mention.
3. NO INVENTED NUMBERS: Never fabricate or estimate metrics.
4. NO INFLATED SCOPE: Do not upgrade the candidate's role or ownership.
5. NO INVENTED DETAILS: Do not invent employers, dates, titles, project names, URLs, or degrees.
6. INFERENCE LIMIT: Only trivial, near-certain inferences allowed.
7. CITATION REQUIRED: Every bullet must list the chunk_id(s) that support it.

# TAILORING RULES
1. RELEVANCE FILTER: Select only the most relevant experiences/projects.
2. KEYWORD MIRRORING: Use the JD's exact terminology where evidence supports it.
3. ORDERING: Put most aligned entries first.
4. SKILLS SECTION: Include only skills evidenced in context or profile.

# BULLET WRITING STANDARD
- 2-4 bullets per entry; one line to two lines each (max ~220 chars).
- Structure: [Strong past-tense action verb] + [what was built/done] + [how: technologies] + [result/impact, ONLY if evidenced].
- Start each bullet with a different action verb. Avoid weak verbs.
- Be specific and concrete. No buzzword filler.

# SUMMARY
Write 2-3 sentences, max 450 chars, in implied first person (no "I").

# HANDLING GAPS
- If evidence is thin, produce a shorter, honest resume.
- List every JD requirement with no supporting evidence under keyword_coverage.missing.
- Use warnings for anything the candidate should review.

# SELF-CHECK
For each bullet and each skill, ask: "Which exact chunk or profile field proves this?"
If you cannot point to one, delete it.

# OUTPUT FORMAT
Return ONLY a single valid JSON object. No markdown fences, no commentary.
It must conform to this schema:
{
  "summary": string,
  "skills": [{"category": string, "skills": [string]}],
  "work_experience": [{
    "company": string, "title": string,
    "start_date": string, "end_date": string | null,
    "bullets": [{"text": string, "source_chunk_ids": [string], "matched_keywords": [string]}]
  }],
  "projects": [{
    "name": string, "url": string | null, "technologies": [string],
    "bullets": [{"text": string, "source_chunk_ids": [string], "matched_keywords": [string]}]
  }],
  "keyword_coverage": {"covered": [string], "missing": [string]},
  "warnings": [string]
}"""

    def _build_user_prompt(
        self,
        jd_title: str,
        jd_company: str | None,
        parsed_jd: ParsedJobRequirements,
        profile: dict,
        retrieved_context: str,
        max_projects: int,
    ) -> str:
        """Build the per-request user prompt (Jinja-templated style)."""
        # Format parsed requirements
        req_str = "\n".join(
            f"- {s}" for s in parsed_jd.required_skills
        ) or "-(none listed)"
        pref_str = "\n".join(
            f"- {s}" for s in parsed_jd.preferred_skills
        ) or "-(none listed)"
        resp_str = "\n".join(
            f"- {r}" for r in parsed_jd.responsibilities
        ) or "-(none listed)"
        kw_str = ", ".join(parsed_jd.domain_keywords) or "-(none listed)"

        # Format profile
        profile_json = json.dumps(profile, indent=2)

        # Format retrieved context
        # retrieved_context is already the XML block built by _build_context

        prompt = f"""<job_description>
Title: {jd_title}
Company: {jd_company or "Not specified"}

Required skills: {req_str}
Preferred skills: {pref_str}
Key responsibilities:
{resp_str}
Domain keywords: {kw_str}

Full text:
{parsed_jd.raw_text if hasattr(parsed_jd, 'raw_text') else ""}
</job_description>

<candidate_profile>
{profile_json}
</candidate_profile>

<retrieved_context>
{retrieved_context}
</retrieved_context>

Generate the tailored resume JSON now."""

        return prompt

    @staticmethod
    def _resume_to_dict(output: AlignmentOutput) -> Dict[str, Any]:
        """Convert an AlignmentOutput model to a plain dict."""

        def bullets_to_dict(bullets):
            return [
                {
                    "text": b.text,
                    "source_chunk_ids": b.source_chunk_ids,
                    "matched_keywords": b.matched_keywords,
                }
                for b in bullets
            ]

        def skills_to_dict(skills):
            return [{"category": s.category, "skills": s.skills} for s in skills]

        def work_experience_to_dict(we):
            return {
                "company": we.company,
                "title": we.title,
                "start_date": we.start_date,
                "end_date": we.end_date,
                "bullets": bullets_to_dict(we.bullets),
            }

        def projects_to_dict(pe):
            return {
                "name": pe.name,
                "url": str(pe.url) if pe.url else None,
                "technologies": pe.technologies,
                "bullets": bullets_to_dict(pe.bullets),
            }

        def education_to_dict(ed):
            return {
                "institution": ed.institution,
                "degree": ed.degree,
                "field_of_study": ed.field_of_study,
                "end_year": ed.end_year,
            }

        return {
            "summary": output.summary,
            "skills": skills_to_dict(output.skills),
            "work_experience": [work_experience_to_dict(w) for w in output.work_experience],
            "projects": [projects_to_dict(p) for p in output.projects],
            "keyword_coverage": {
                "covered": output.keyword_coverage.covered,
                "missing": output.keyword_coverage.missing,
            },
            "warnings": output.warnings,
        }

async def align_resume(
    profile_id: str,
    job_title: str,
    company: str | None,
    raw_text: str,
    top_k: int = 12,
    max_projects: int = 4,
) -> Dict[str, Any]:
    """Standalone function to align a profile to a job description."""
    from app.core.jobs import job_registry
    from app.llm.client import LLMClient
    from app.rag.retriever import MultiQueryRetriever
    from app.rag.vector_store import ChromaVectorStore
    from app.schemas.job import AlignRequest
    from app.schemas.profile import UserProfile

    profile_data = job_registry.get_profile(profile_id)
    if not profile_data:
        raise ValueError(f"Profile {profile_id} not found")

    def _clean_url(value: Any) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if not text or not (text.startswith("http://") or text.startswith("https://")):
            return None
        return text

    email = str(profile_data.get("email", "")).strip() or "unknown@example.com"
    profile = UserProfile(
        id=profile_data.get("id", profile_id),
        full_name=profile_data.get("full_name", "") or "Candidate",
        email=email,
        github_username=profile_data.get("github_username", "") or "unknown",
        portfolio_url=_clean_url(profile_data.get("portfolio_url")),
        phone=profile_data.get("phone"),
        location=profile_data.get("location"),
        linkedin_url=_clean_url(profile_data.get("linkedin_url")),
    )

    request = AlignRequest(
        title=job_title,
        company=company,
        raw_text=raw_text,
        top_k=top_k,
        max_projects=max_projects,
    )

    llm_client = LLMClient()
    vector_store = ChromaVectorStore()
    retriever = MultiQueryRetriever(vector_store=vector_store, top_k=top_k)
    aligner = Aligner(llm_client=llm_client, retriever=retriever)

    result = await aligner.align(profile=profile, request=request)
    result["job_title"] = job_title
    result["company"] = company
    return result
