from enum import Enum
from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    REPO_README = "repo_readme"
    REPO_METADATA = "repo_metadata"  # description, topics, languages, stars
    PORTFOLIO_SECTION = "portfolio_section"
    USER_SUPPLIED = "user_supplied"  # manual additions / corrections


class IngestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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


class ParsedJobRequirements(BaseModel):
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    domain_keywords: list[str] = []  # e.g. "payments", "ML ops", "healthcare"
    seniority: str | None = None
    soft_skills: list[str] = []


class JobDescription(BaseModel):
    id: str
    title: str
    company: str | None = None
    raw_text: str = Field(min_length=50)
    parsed: ParsedJobRequirements | None = None  # filled by jd_parser


class AlignRequest(BaseModel):
    title: str
    company: str | None = None
    raw_text: str = Field(min_length=50)
    top_k: int = Field(default=12, ge=3, le=30)
    max_projects: int = Field(default=4, ge=1, le=8)


class ResumeBullet(BaseModel):
    text: str = Field(max_length=300)
    source_chunk_ids: list[str] = Field(min_length=1)  # required for grounding
    matched_keywords: list[str] = []


class ResumeHeader(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    linkedin_url: str | None = None


class ResumeSkillGroup(BaseModel):
    category: str  # "Languages", "Frameworks", "Tools"
    skills: list[str]


class ResumeWorkEntry(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    bullets: list[ResumeBullet]


class ResumeProjectEntry(BaseModel):
    name: str
    url: str | None = None
    technologies: list[str] = []
    bullets: list[ResumeBullet]


class ResumeEducation(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    end_year: int | None = None


class KeywordCoverage(BaseModel):
    covered: list[str] = []  # JD keywords honestly supported by evidence
    missing: list[str] = []  # JD keywords with NO evidence (never fabricated)


class FinalResume(BaseModel):
    id: str
    profile_id: str
    job_title: str
    company: str | None = None
    header: ResumeHeader
    summary: str = Field(max_length=500)
    skills: list[ResumeSkillGroup]
    work_experience: list[ResumeWorkEntry] = []
    projects: list[ResumeProjectEntry] = []
    education: list[ResumeEducation] = []
    keyword_coverage: KeywordCoverage
    warnings: list[str] = []  # verifier flags, e.g. "bullet 2 weakly supported"