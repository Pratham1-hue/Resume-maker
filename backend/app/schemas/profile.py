from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl, Field
from .common import IngestStatus


class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    gpa: str | None = None


class WorkEntry(BaseModel):
    """User-supplied employment history (scraping can't reliably get this)."""
    company: str
    title: str
    start_date: str  # "YYYY-MM"
    end_date: str | None = None  # None = present
    description: str | None = None  # raw notes; gets chunked into the vector store


class UserProfile(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    github_username: str
    portfolio_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    education: list[EducationEntry] = []
    work_history: list[WorkEntry] = []
    top_languages: dict[str, float] = Field(
        default_factory=dict, description="GitHub language → share of bytes (0-1)"
    )
    ingest_status: IngestStatus = IngestStatus.PENDING
    chunk_count: int = 0
    last_ingested_at: datetime | None = None


class CreateProfileRequest(BaseModel):
    full_name: str
    email: EmailStr
    github_username: str
    portfolio_url: HttpUrl | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: HttpUrl | None = None
    education: list[EducationEntry] = []
    work_history: list[WorkEntry] = []