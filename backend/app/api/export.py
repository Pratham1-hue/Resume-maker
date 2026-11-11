from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Literal

from app.core.jobs import job_registry
from app.export.renderer import render_resume

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    profile_id: str
    job_title: str
    company: Optional[str] = None
    format: Literal["docx", "pdf"] = "docx"


class ExportResponse(BaseModel):
    download_url: str
    format: str
    filename: str


@router.post("/", response_model=ExportResponse)
async def export_resume(request: ExportRequest):
    """Export a tailored resume in the requested format."""
    profile = job_registry.get_profile(request.profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile {request.profile_id} not found",
        )

    if profile.get("ingest_status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile {request.profile_id} not yet ingested",
        )

    result = render_resume(
        profile_id=request.profile_id,
        job_title=request.job_title,
        company=request.company,
        format=request.format,
    )

    return ExportResponse(
        download_url=result.get("download_url", ""),
        format=result.get("format", "docx"),
        filename=result.get("filename", "resume.docx"),
    )