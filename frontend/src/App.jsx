import { useEffect, useRef, useState } from "react";
import {
  alignResume,
  createProfile,
  exportResume,
  getIngestStatus,
  startIngest,
} from "./lib/api-client.ts";

const inputCls = "w-full border rounded p-2";
const labelCls = "block text-sm font-medium mb-1";
const btnPrimary = "bg-blue-600 text-white px-5 py-2 rounded hover:bg-blue-700 disabled:opacity-50";
const btnSecondary = "bg-gray-100 text-gray-800 px-4 py-2 rounded hover:bg-gray-200 disabled:opacity-50";
const cardCls = "p-6 border rounded-md mb-6 bg-white";

function ErrorBox({ error }) {
  if (!error) return null;
  return <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</p>;
}

function BulletList({ bullets }) {
  if (!bullets || bullets.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1">
      {bullets.map((b, i) => (
        <li key={i} className="text-sm">
          <span className="font-medium">• </span>
          {b.text}
          {b.matched_keywords && b.matched_keywords.length > 0 && (
            <span className="text-xs text-gray-500 ml-2">({b.matched_keywords.join(", ")})</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function App() {
  const [profileId, setProfileId] = useState("");
  const [profile, setProfile] = useState({ full_name: "", email: "", github_username: "", portfolio_url: "", phone: "", location: "", linkedin_url: "" });
  const [ingest, setIngest] = useState({ status: "idle", progress: "", chunk_count: 0, error: null, warnings: [] });
  const [exportError, setExportError] = useState(null);
  const [jd, setJd] = useState({ title: "", company: "", rawText: "", maxProjects: 4 });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [backendUp, setBackendUp] = useState(null); // null=checking, true/false
  const pollRef = useRef(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  useEffect(() => {
    let alive = true;
    const base = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
    fetch(`${base}/health`)
      .then((r) => { if (alive) setBackendUp(r.ok); })
      .catch(() => { if (alive) setBackendUp(false); });
    return () => { alive = false; };
  }, []);

  const pollUntilDone = (id) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getIngestStatus(id);
        setIngest({ status: s.status, progress: s.progress || "", chunk_count: s.chunk_count ?? 0, error: s.error || null, warnings: s.warnings || [] });
        if (s.status === "completed" || s.status === "failed") stopPolling();
      } catch {
        /* keep last state */
      }
    }, 3000);
  };

  const handleCreateAndIngest = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const id = await createProfile({
        full_name: profile.full_name,
        email: profile.email,
        github_username: profile.github_username,
        portfolio_url: profile.portfolio_url || null,
        phone: profile.phone || null,
        location: profile.location || null,
        linkedin_url: profile.linkedin_url || null,
      });
      setProfileId(id);
      setIngest({ status: "running", progress: "Ingestion started in background", chunk_count: 0, error: null, warnings: [] });
      await startIngest(id, { github_username: profile.github_username, portfolio_url: profile.portfolio_url || null });
      pollUntilDone(id);
    } catch (err) {
      setError(err.message || "Failed to create profile");
    } finally {
      setBusy(false);
    }
  };

  const handleAlign = async (e) => {
    e.preventDefault();
    if (!profileId) {
      setError("Create a profile and ingest it first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await alignResume(profileId, {
        title: jd.title,
        company: jd.company,
        rawText: jd.rawText,
        topK: 12,
        maxProjects: jd.maxProjects,
      });
      setResult(res);
    } catch (err) {
      setError(err.message || "Alignment failed");
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async (format) => {
    if (!profileId || !result) return;
    setExportError(null);
    try {
      const out = await exportResume(profileId, result.job_title || jd.title, format, result.company || jd.company);
      if (!out.download_url) {
        setExportError(out.note || "Export is not available in this format yet.");
        return;
      }
      const a = document.createElement("a");
      a.href = out.download_url;
      a.download = out.filename || `resume.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      setExportError(err.message || "Export failed");
    }
  };

  const ready = ingest.status === "completed";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-1">Quick Resume Maker</h1>
        <p className="text-sm text-gray-600 mb-1">Ingest a profile once, then tailor it to any job description.</p>
        <p className="text-xs mb-6">
          Backend:{" "}
          {backendUp === null && <span className="text-gray-500">checking…</span>}
          {backendUp === true && <span className="text-green-700 font-medium">● connected</span>}
          {backendUp === false && (
            <span className="text-red-700 font-medium">● unreachable — is the backend running on :8000?</span>
          )}
        </p>

        <div className={cardCls}>
          <h2 className="text-xl font-bold mb-4">1. Profile {profileId && <span className="text-sm font-normal text-gray-500">({profileId})</span>}</h2>
          <form onSubmit={handleCreateAndIngest}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className={labelCls}>Full name *</label>
                <input className={inputCls} value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} required placeholder="Jane Doe" />
              </div>
              <div>
                <label className={labelCls}>Email *</label>
                <input className={inputCls} type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} required />
              </div>
              <div>
                <label className={labelCls}>GitHub username *</label>
                <input className={inputCls} value={profile.github_username} onChange={(e) => setProfile({ ...profile, github_username: e.target.value })} required placeholder="octocat" />
              </div>
              <div>
                <label className={labelCls}>Portfolio URL</label>
                <input className={inputCls} type="url" value={profile.portfolio_url} onChange={(e) => setProfile({ ...profile, portfolio_url: e.target.value })} placeholder="https://example.com" />
              </div>
              <div>
                <label className={labelCls}>Phone</label>
                <input className={inputCls} value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
              </div>
              <div>
                <label className={labelCls}>Location</label>
                <input className={inputCls} value={profile.location} onChange={(e) => setProfile({ ...profile, location: e.target.value })} placeholder="City, Country" />
              </div>
            </div>
            <button type="submit" disabled={busy} className={btnPrimary}>
              {busy ? "Working..." : profileId ? "Recreate profile & re-ingest" : "Create profile & ingest"}
            </button>
          </form>
          {profileId && (
            <div className="mt-4 text-sm bg-gray-50 border rounded p-3">
              <p><span className="font-medium">Ingestion:</span> {ingest.status} {ingest.chunk_count > 0 && `(${ingest.chunk_count} chunks)`}</p>
              {ingest.progress && <p className="text-gray-600">{ingest.progress}</p>}
              {ingest.error && <p className="text-red-600">{ingest.error}</p>}
              {ingest.warnings && ingest.warnings.length > 0 && (
                <ul className="mt-1 text-xs text-amber-700 space-y-0.5">
                  {ingest.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
                </ul>
              )}
            </div>
          )}
          <ErrorBox error={error} />
        </div>

        <div className={cardCls}>
          <h2 className="text-xl font-bold mb-4">2. Job description</h2>
          <form onSubmit={handleAlign}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className={labelCls}>Job title *</label>
                <input className={inputCls} value={jd.title} onChange={(e) => setJd({ ...jd, title: e.target.value })} required placeholder="Backend Engineer" />
              </div>
              <div>
                <label className={labelCls}>Company</label>
                <input className={inputCls} value={jd.company} onChange={(e) => setJd({ ...jd, company: e.target.value })} />
              </div>
            </div>
            <div className="mb-4">
              <label className={labelCls}>Full job description (min 50 chars) *</label>
              <textarea className={inputCls} rows={8} value={jd.rawText} onChange={(e) => setJd({ ...jd, rawText: e.target.value })} required minLength={50} placeholder="Paste the job posting here..." />
            </div>
            <div className="mb-4">
              <label className={labelCls}>Max projects</label>
              <select className={inputCls} value={jd.maxProjects} onChange={(e) => setJd({ ...jd, maxProjects: Number(e.target.value) })}>
                {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <button type="submit" disabled={busy || !ready} className={btnPrimary} title={!ready ? "Wait for ingestion to complete" : ""}>
              {busy ? "Generating..." : "Generate tailored resume"}
            </button>
            {!ready && profileId && <p className="text-xs text-gray-500 mt-2">Alignment unlocks once ingestion completes.</p>}
          </form>
        </div>

        {result && (
          <div className={cardCls}>
            <h2 className="text-xl font-bold mb-2">3. Tailored resume {result.job_title && <span className="text-sm font-normal text-gray-500">for {result.job_title}</span>}</h2>
            {(!result.summary && (!result.skills || result.skills.length === 0) &&
              (!result.work_experience || result.work_experience.length === 0) &&
              (!result.projects || result.projects.length === 0)) && (
              <div className="mt-2 p-3 border rounded bg-amber-50 text-xs text-amber-800">
                The model returned an almost-empty resume. Small local models sometimes do this
                on long job descriptions — try Generate again, paste a shorter JD, or switch to a
                larger model. Your keyword coverage below was still computed from your evidence.
              </div>
            )}
            <p className="font-medium mt-4">Summary</p>
            <p className="text-sm mt-1">{result.summary}</p>

            {result.skills && result.skills.length > 0 && (
              <>
                <p className="font-medium mt-4">Skills</p>
                {result.skills.map((g, i) => (
                  <div key={i} className="mt-1">
                    <span className="text-sm font-semibold">{g.category}: </span>
                    {(g.skills || []).map((s, j) => (
                      <span key={j} className="text-xs bg-blue-100 rounded px-2 py-0.5 ml-1">{s}</span>
                    ))}
                  </div>
                ))}
              </>
            )}

            {result.work_experience && result.work_experience.length > 0 && (
              <>
                <p className="font-medium mt-4">Work experience</p>
                {result.work_experience.map((w, i) => (
                  <div key={i} className="mt-2 p-3 border rounded">
                    {(w.title || w.company) && (
                      <p className="font-medium text-sm">{[w.title, w.company].filter(Boolean).join(" at ")}</p>
                    )}
                    <p className="text-xs text-gray-500">{w.start_date}{w.end_date ? ` - ${w.end_date}` : ""}</p>
                    <BulletList bullets={w.bullets} />
                  </div>
                ))}
              </>
            )}

            {result.projects && result.projects.length > 0 && (
              <>
                <p className="font-medium mt-4">Projects</p>
                {result.projects.map((p, i) => (
                  <div key={i} className="mt-2 p-3 border rounded">
                    <p className="font-medium text-sm">{p.name}</p>
                    {(p.technologies || []).map((t, j) => (
                      <span key={j} className="text-xs bg-gray-100 rounded px-1 ml-1">{t}</span>
                    ))}
                    <BulletList bullets={p.bullets} />
                  </div>
                ))}
              </>
            )}

            {result.keyword_coverage && (
              <div className="mt-4 p-3 border rounded bg-green-50 text-xs">
                <span className="font-medium">Covered:</span> {(result.keyword_coverage.covered || []).join(", ") || "none"}
                <span className="mx-2 text-gray-400">|</span>
                <span className="font-medium">Missing:</span> {(result.keyword_coverage.missing || []).join(", ") || "none"}
              </div>
            )}

            {result.warnings && result.warnings.length > 0 && (
              <div className="mt-4 p-3 border rounded bg-yellow-50 text-xs">
                <p className="font-medium">Warnings</p>
                <ul className="mt-1 space-y-1">
                  {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}

            <div className="mt-4 flex gap-2">
              <button onClick={() => handleExport("docx")} className={btnSecondary}>Download DOCX</button>
              <button onClick={() => handleExport("pdf")} className={btnSecondary}>Download PDF</button>
            </div>
            {exportError && (
              <p className="mt-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{exportError}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
