import { Suspense } from "react";
import { useParams } from "next/navigation";
import { AlignRequest } from "../../types";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/polling";
import GeneratedResume from "../GeneratedResume";

export default function GenerateResumePage() {
  const { id } = useParams();
  const [alignResult, setAlignResult] = useState<{
    summary: string;
    skills: { category: string; skills: string[] }[];
    workExperience: { company: string; title: string; startDate: string; endDate?: string | null; bullets: ResumeBullet[] }[];
    projects: { name: string; url?: string; technologies: string[]; bullets: ResumeBullet[] }[];
    keywordCoverage: { covered: string[]; missing: string[] };
    warnings: string[];
    jobTitle: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!id) {
    return <div>Profile ID required</div>;
  }

  // Check if profile is ready for alignment
  useEffect(() => {
    async function checkProfile() {
      const profile = await apiFetch(`/api/v1/profiles/${id}`);
      if (profile.ingest_status !== "completed") {
        setError(
          `Profile not yet ingested (status: ${profile.ingest_status}). ` +
          "Please run ingestion first."
        );
        return;
      }
      // Profile is ready
    }
    checkProfile();
  }, [id]);

  const alignWithJob = async (request: AlignRequest) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiFetch("/api/v1/align/", {
        method: "POST",
        body: JSON.stringify(request),
      });
      setAlignResult(response);
    } catch (err: any) {
      setError(err.message || "Alignment failed");
    } finally {
      setLoading(false);
    }
  };

  if (error) {
    return (
      <div className="p-6">
        <h2>Error</h2>
        <p>{error}</p>
        <button onClick={() => window.history.back()}>Go Back</button>
      </div>
    );
  }

  if (!alignResult && !loading) {
    return (
      <div className="p-6">
        <h2>Generate Resume</h2>
        <p>
          Paste a job description below to generate a tailored resume using your
          profile data. Your profile must be ingested first.
        </p>
        <AlignForm onSubmit={alignWithJob} profileId={id} />
      </div>
    );
  }

  // Show the generated resume
  return (
    <Suspense fallback={<div>Generating your tailored resume...</div>}>
      <div className="p-6">
        <h2>Tailored Resume for {alignResult?.jobTitle}</h2>

        <div className="mb-4">
          <p className="font-medium">Summary:</p>
          <p>{alignResult?.summary}</p>
        </div>

        <div className="mb-4">
          <p className="font-medium">Keyword Coverage:</p>
          <p>
            Covered: {alignResult?.keywordCoverage.covered.join(", ")}
            {" "}
           Missing: {alignResult?.keywordCoverage.missing.join(", ")}
          </p>
        </div>

        <div className="mb-6">
          <p className="font-medium">Warnings:</p>
          {alignResult?.warnings.length > 0 ? (
            <ul>
              {alignResult.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : (
            <p>No warnings.</p>
          )}
        </div>

        <GeneratedResume
          summary={alignResult?.summary || ""}
          skills={alignResult?.skills || []}
          workExperience={alignResult?.workExperience || []}
          projects={alignResult?.projects || []}
          keywordCoverage={{ covered: alignResult?.keywordCoverage.covered, missing: alignResult?.keywordCoverage.missing }}
          warnings={alignResult?.warnings || []}
          jobTitle={alignResult?.jobTitle || ""}
        />

        <div className="mt-6">
          <button
            onClick={() => window.open(`/api/v1/export?format=docx&profileId=${id}&jobTitle=${encodeURIComponent(alignResult?.jobTitle || "")}`, "_blank")}
            className="bg-blue-600 text-white px-4 py-2 rounded"
          >
            Download as DOCX
          </button>
          <button
            onClick={() => window.open(`/api/v1/export?format=pdf&profileId=${id}&jobTitle=${encodeURIComponent(alignResult?.jobTitle || "")}`, "_blank")}
            className="bg-green-600 text-white px-4 py-2 rounded ml-2"
          >
            Download as PDF
          </button>
        </div>
      </div>
    </Suspense>
  );
}

// Align form component
function AlignForm({ onSubmit }: { onSubmit: (request: AlignRequest) => void; profileId: string }) {
  const [rawText, setRawText] = useState("");
  const [company, setCompany] = useState("");
  const [maxProjects, setMaxProjects] = useState(4);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const request: AlignRequest = {
      title: `Resume for ${company || "Target Role"}`,
      company,
      rawText,
      topK: 12,
      maxProjects,
    };
    onSubmit(request);
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
      <div>
        <label className="block text-sm font-medium mb-2">
          Job Description
        </label>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          rows={5}
          className="w-full border rounded p-2"
          required
        ></textarea>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">
          Company (optional)
        </label>
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          className="w-full border rounded p-2"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">
          Max Projects to Include
        </label>
        <select
          value={maxProjects}
          onChange={(e) => setMaxProjects(Number(e.target.value))}
          className="w-full border rounded p-2"
        >
          <option value={1}>1</option>
          <option value={2}>2</option>
          <option value={3}>3</option>
          <option value={4} selected>4</option>
          <option value={5}>5</option>
          <option value={6}>6</option>
        </select>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="bg-primary-600 text-white px-6 py-2 rounded hover:bg-primary-700"
      >
        {loading ? "Generating..." : "Generate Tailored Resume"}
      </button>
    </form>
  );
}