import { apiFetch } from "../lib/api-client";

// NOTE: apiFetch() already prefixes "/api/v1", so paths below start with it once.
// Backend speaks snake_case; callers must send snake_case keys.

export async function createProfileAPI(data: {
  full_name: string;
  email: string;
  github_username: string;
  portfolio_url?: string;
  phone?: string;
  location?: string;
  linkedin_url?: string;
}) {
  return apiFetch("/api/v1/profiles/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getProfileAPI(id: string) {
  return apiFetch(`/api/v1/profiles/${id}`);
}

export async function startIngestAPI(profileId: string, githubUsername: string, portfolioUrl?: string) {
  return apiFetch(`/api/v1/profiles/${profileId}/ingest`, {
    method: "POST",
    body: JSON.stringify({ github_username: githubUsername, portfolio_url: portfolioUrl ?? null }),
  });
}

export async function checkIngestStatusAPI(profileId: string) {
  return apiFetch(`/api/v1/profiles/${profileId}/ingest/status`);
}

export async function alignResumeAPI(request: {
  profileId: string;
  title: string;
  company?: string;
  rawText: string;
  topK?: number;
  maxProjects?: number;
}) {
  return apiFetch("/api/v1/align/", {
    method: "POST",
    body: JSON.stringify({
      profile_id: request.profileId,
      title: request.title,
      company: request.company ?? null,
      raw_text: request.rawText,
      top_k: request.topK ?? 12,
      max_projects: request.maxProjects ?? 4,
    }),
  });
}

export async function exportResumeAPI(profileId: string, jobTitle: string, format: "docx" | "pdf", company?: string) {
  return apiFetch("/api/v1/export/", {
    method: "POST",
    body: JSON.stringify({ profile_id: profileId, job_title: jobTitle, format, company: company ?? null }),
  });
}
