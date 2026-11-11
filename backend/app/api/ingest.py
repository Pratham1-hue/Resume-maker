from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from app.core.jobs import job_registry

router = APIRouter(prefix="/profiles", tags=["ingest"])


class IngestRequest(BaseModel):
    github_username: str = Field(min_length=1)
    portfolio_url: Optional[str] = None
    force_refresh: bool = False


class IngestStatusResponse(BaseModel):
    profile_id: str
    status: str
    progress: str
    chunk_count: int
    error: Optional[str] = None


@router.post("/{profile_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
async def start_ingest(
    profile_id: str,
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """Start the ingestion pipeline for a profile (runs in the background)."""
    from app.ingestion.pipeline import run_ingestion_pipeline

    profile = job_registry.get_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile {profile_id} not found",
        )

    if not request.force_refresh and profile.get("ingest_status") == "completed":
        return IngestStatusResponse(
            profile_id=profile_id,
            status="completed",
            progress="Already completed. Use force_refresh=true to re-ingest.",
            chunk_count=profile.get("chunk_count", 0),
        )

    job_registry.start_ingest(profile_id, request.github_username, request.portfolio_url)
    background_tasks.add_task(
        run_ingestion_pipeline,
        profile_id,
        request.github_username,
        request.portfolio_url,
    )

    return IngestStatusResponse(
        profile_id=profile_id,
        status="running",
        progress="Ingestion started in background",
        chunk_count=profile.get("chunk_count", 0),
    )
