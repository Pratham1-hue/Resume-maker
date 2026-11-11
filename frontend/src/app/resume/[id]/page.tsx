import { Suspense } from "react";
import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/polling";
import { FinalResume } from "../types";
import ResumePreview from "../components/resume/ResumePreview";

export default function ResumePage() {
  const { id } = useParams();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [format] = useSearchParams().get("format") ? "docx" : "preview";
  const [resume, setResume] = useState<FinalResume | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadResume() {
      const data = await apiFetch(`/api/v1/resumes/export?format=${format}&profileId=${id}`);
      if (typeof data === "object" && data.download_url) {
        // It's an export result, redirect to download
        window.location.href = data.download_url;
      } else {
        setResume(data);
      }
      setLoading(false);
    }

    if (id) {
      loadResume();
    }
  }, [id, format]);

  if (loading) {
    return <div>Loading resume...</div>;
  }

  if (!resume) {
    return <div>Resume not found</div>;
  }

  return (
    <Suspense fallback={<div>Loading resume...</div>}>
      <div className="p-6">
        <h2>Resume Preview</h2>

        <ResumePreview resume={resume} />

        {format === "docx" && (
          <div className="mt-6">
            <a
              href={`/api/v1/export?format=docx&profileId=${id}`}
              className="bg-blue-600 text-white px-4 py-2 rounded"
              download="resume.docx"
            >
              Download DOCX
            </a>
            <a
              href={`/api/v1/export?format=pdf&profileId=${id}`}
              className="bg-green-600 text-white px-4 py-2 rounded ml-2"
              download="resume.pdf"
            >
              Download PDF
            </a>
          </div>
        )}
      </div>
    </Suspense>
  );
}