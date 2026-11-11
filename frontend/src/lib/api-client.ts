const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

/** Low-level fetch. `path` must start with "/api/v1/...". */
export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `API error: ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || JSON.stringify(data) || detail;
    } catch {
      try {
        detail = (await response.text()) || detail;
      } catch {
        /* keep default */
      }
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function createProfile(data) {
  const res = await apiFetch("/api/v1/profiles/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return res.id;
}

export async function getIngestStatus(profileId) {
  return apiFetch(`/api/v1/profiles/${profileId}/ingest/status`);
}

export async function startIngest(profileId, { github_username, portfolio_url, force_refresh = false }) {
  return apiFetch(`/api/v1/profiles/${profileId}/ingest`, {
    method: "POST",
    body: JSON.stringify({ github_username, portfolio_url: portfolio_url || null, force_refresh }),
  });
}

/** Backend expects snake_case keys. This maps the camelCase form fields. */
export async function alignResume(profileId, { title, company, rawText, topK = 12, maxProjects = 4 }) {
  return apiFetch("/api/v1/align/", {
    method: "POST",
    body: JSON.stringify({
      profile_id: profileId,
      title,
      company: company || null,
      raw_text: rawText,
      top_k: topK,
      max_projects: maxProjects,
    }),
  });
}

export async function exportResume(profileId, jobTitle, format, company) {
  return apiFetch("/api/v1/export/", {
    method: "POST",
    body: JSON.stringify({
      profile_id: profileId,
      job_title: jobTitle,
      format,
      company: company || null,
    }),
  });
}

/** Poll the ingest-status endpoint until completed/failed. Returns a stop function. */
export function pollIngestionStatus(profileId, onUpdate) {
  const timer = setInterval(async () => {
    try {
      const status = await getIngestStatus(profileId);
      onUpdate(status);
      if (status.status === "completed" || status.status === "failed") {
        clearInterval(timer);
      }
    } catch {
      /* keep polling; the UI shows the last known state */
    }
  }, 3000);
  return () => clearInterval(timer);
}
