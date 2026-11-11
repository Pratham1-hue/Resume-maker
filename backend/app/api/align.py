from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.core.jobs import job_registry
from app.llm.aligner import align_resume
from app.llm.client import LLMError

router = APIRouter(prefix="/align", tags=["align"])


class AlignRequest(BaseModel):
    profile_id: str
    title: str
    company: Optional[str] = None
    raw_text: str = Field(min_length=50)
    top_k: int = Field(default=12, ge=3, le=30)
    max_projects: int = Field(default=4, ge=1, le=8)


class AlignResponse(BaseModel):
    profile_id: str
    job_title: str
    company: Optional[str]
    summary: str
    skills: list
    work_experience: list
    projects: list
    keyword_coverage: dict
    warnings: list


@router.post("/", response_model=AlignResponse)
async def align_resume_endpoint(request: AlignRequest):
    """Align candidate profile to a job description."""
    profile = job_registry.get_profile(request.profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile {request.profile_id} not found",
        )

    if profile.get("ingest_status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile {request.profile_id} not yet ingested. Please run ingest first.",
        )

    try:
        result = await align_resume(
            profile_id=request.profile_id,
            job_title=request.title,
            company=request.company,
            raw_text=request.raw_text,
            top_k=request.top_k,
            max_projects=request.max_projects,
        )
    except LLMError as exc:
        # Provider-side failure (bad key, bad model id, rate limit, ...).
        # 502, not 500: our code is fine, the upstream call failed — and the
        # message now contains the provider's own reason.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )

    # Persist the alignment so POST /export can render this exact resume
    # (header/education are rebuilt from the profile at export time).
    job_registry.save_alignment(request.profile_id, result)

    return AlignResponse(
        profile_id=request.profile_id,
        job_title=result.get("job_title", request.title),
        company=result.get("company"),
        summary=result.get("summary", ""),
        skills=result.get("skills", []),
        work_experience=result.get("work_experience", []),
        projects=result.get("projects", []),
        keyword_coverage=result.get("keyword_coverage", {"covered": [], "missing": []}),
        warnings=result.get("warnings", []),
    )