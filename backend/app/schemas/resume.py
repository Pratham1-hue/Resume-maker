from pydantic import BaseModel, Field, HttpUrl


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


class ExperienceSummary(BaseModel):
    """A consolidated experience/project built from one or more retrieved chunks."""
    id: str
    kind: str  # "project" | "work" | "open_source" | "other"
    title: str
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