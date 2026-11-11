from pydantic import BaseModel, Field


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


class ResumeSkillGroup(BaseModel):
    category: str  # "Languages", "Frameworks", "Tools"
    skills: list[str]


class KeywordCoverage(BaseModel):
    covered: list[str] = []
    missing: list[str] = []


class FinalResume(BaseModel):
    id: str
    profile_id: str
    job_title: str
    company: str | None = None
    header: BaseModel  # ResumeHeader
    summary: str = Field(max_length=500)
    skills: list[ResumeSkillGroup]
    work_experience: list = []  # ResumeWorkEntry[]
    projects: list = []  # ResumeProjectEntry[]
    education: list = []  # ResumeEducation[]
    keyword_coverage: KeywordCoverage
    warnings: list[str] = []