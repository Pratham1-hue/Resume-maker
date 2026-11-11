export type ChunkType =
  | "repo_readme" | "repo_metadata" | "portfolio_section" | "user_supplied";
export type IngestStatus = "pending" | "running" | "completed" | "failed";

export interface EducationEntry {
  institution: string;
  degree: string;
  fieldOfStudy?: string;
  startYear?: number;
  endYear?: number;
  gpa?: string;
}

export interface WorkEntry {
  company: string;
  title: string;
  startDate: string;          // "YYYY-MM"
  endDate?: string | null;    // null = present
  description?: string;
}

export interface UserProfile {
  id: string;
  fullName: string;
  email: string;
  phone?: string;
  location?: string;
  githubUsername: string;
  portfolioUrl?: string;
  linkedinUrl?: string;
  education: EducationEntry[];
  workHistory: WorkEntry[];
  topLanguages: Record<string, number>;
  ingestStatus: IngestStatus;
  chunkCount: number;
  lastIngestedAt?: string;
}

export interface SourceChunk {
  chunkId: string;
  profileId: string;
  chunkType: ChunkType;
  text: string;
  sourceUrl?: string;
  repoName?: string;
  sectionHeading?: string;
  languages: string[];
  topics: string[];
  stars?: number;
}

export interface ExtractedExperience {
  id: string;
  kind: "project" | "work" | "open_source" | "other";
  title: string;
  organization?: string;
  url?: string;
  startDate?: string;
  endDate?: string;
  technologies: string[];
  facts: string[];
  sourceChunkIds: string[];
  relevanceScore?: number;
}

export interface ParsedJobRequirements {
  requiredSkills: string[];
  preferredSkills: string[];
  responsibilities: string[];
  domainKeywords: string[];
  seniority?: string;
  softSkills: string[];
}

export interface JobDescription {
  id: string;
  title: string;
  company?: string;
  rawText: string;
  parsed?: ParsedJobRequirements;
}

export interface AlignRequest {
  title: string;
  company?: string;
  rawText: string;
  topK?: number;
  maxProjects?: number;
}

export interface ResumeBullet {
  text: string;
  sourceChunkIds: string[];
  matchedKeywords: string[];
}

export interface FinalResume {
  id: string;
  profileId: string;
  jobTitle: string;
  company?: string;
  header: {
    fullName: string; email: string; phone?: string; location?: string;
    githubUrl?: string; portfolioUrl?: string; linkedinUrl?: string;
  };
  summary: string;
  skills: { category: string; skills: string[] }[];
  workExperience: {
    company: string; title: string; startDate: string; endDate?: string | null;
    bullets: ResumeBullet[];
  }[];
  projects: {
    name: string; url?: string; technologies: string[]; bullets: ResumeBullet[];
  }[];
  education: {
    institution: string; degree: string; fieldOfStudy?: string; endYear?: number;
  }[];
  keywordCoverage: { covered: string[]; missing: string[] };
  warnings: string[];
}