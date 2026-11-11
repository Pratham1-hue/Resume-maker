import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.jobs import job_registry

router = APIRouter(prefix="/profiles", tags=["profiles"])


class CreateProfileRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    github_username: str = Field(min_length=1)
    portfolio_url: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    education: list = []
    work_history: list = []


class ProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str
    github_username: str
    portfolio_url: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    ingest_status: str = "pending"
    chunk_count: int = 0
    last_ingested_at: Optional[str] = None


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(request: CreateProfileRequest):
    """Create a new user profile."""
    # Stable within a run and unique: uuid-based IDs (Python's hash() is
    # salted per process, so the old hash-based IDs changed on restart).
    profile_id = f"profile_{uuid.uuid4().hex[:8]}"
    profile = {
        "id": profile_id,
        "full_name": request.full_name,
        "email": str(request.email),
        "github_username": request.github_username,
        "portfolio_url": _blank_to_none(request.portfolio_url),
        "phone": _blank_to_none(request.phone),
        "location": _blank_to_none(request.location),
        "linkedin_url": _blank_to_none(request.linkedin_url),
        "education": request.education,
        "work_history": request.work_history,
        "ingest_status": "pending",
        "chunk_count": 0,
        "last_ingested_at": None,
    }
    job_registry.register_profile(profile_id, profile)
    return profile


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str):
    """Get a profile by ID."""
    profile = job_registry.get_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile {profile_id} not found",
        )
    return profile


@router.get("/{profile_id}/ingest/status")
async def get_ingest_status(profile_id: str):
    """Get ingestion status for a profile (polled by the frontend)."""
    status_info = job_registry.get_ingest_status(profile_id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile {profile_id} not found",
        )
    return status_info
