from typing import Literal
from pydantic import BaseModel, Field, HttpUrl
from .common import ChunkType


class SourceChunk(BaseModel):
    """One embedded unit in ChromaDB. The metadata mirrors what we store in Chroma."""
    chunk_id: str  # e.g. "gh:repo-name:readme:003"
    profile_id: str
    chunk_type: ChunkType
    text: str
    source_url: str | None = None
    repo_name: str | None = None
    section_heading: str | None = None
    languages: list[str] = []
    topics: list[str] = []
    stars: int | None = None


class RetrievedChunk(BaseModel):
    chunk: SourceChunk
    score: float  # similarity (higher = better)
    matched_requirement: str | None = None  # which JD requirement pulled it in


class ExtractedExperience(BaseModel):
    """A consolidated experience/project built from one or more retrieved chunks.
    This is the grounded 'fact sheet' the LLM is allowed to write from."""
    id: str
    kind: Literal["project", "work", "open_source", "other"]
    title: str  # repo name / project name / job title
    organization: str | None = None
    url: HttpUrl | None = None
    start_date: str | None = None
    end_date: str | None = None
    technologies: list[str] = []
    facts: list[str] = Field(
        description="Atomic, source-backed statements (e.g. 'Built REST API with FastAPI')"
    )
    source_chunk_ids: list[str]
    relevance_score: float | None = None