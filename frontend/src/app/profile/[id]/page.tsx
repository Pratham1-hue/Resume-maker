import { Suspense } from "react";
import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { pollIngestionStatus, apiFetch } from "../lib/polling";
import ChunkReviewList from "../components/ingest/ChunkReviewList";
import GenerateResume from "../components/resume/GenerateResume";

export default function ProfilePage() {
  const { id } = useParams();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"pending" | "completed" | "failed" | null>(null);
  const [chunkCount, setChunkCount] = useState(0);
  const [reviewedChunks, setReviewedChunks] = useState<SourceChunk[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  // Fetch profile data
  useEffect(() => {
    if (!id) return;

    async function loadProfile() {
      const data = await apiFetch(`/api/v1/profiles/${id}`);
      setProfile(data);

      // Check if ingestion is complete
      if (data.ingest_status === "completed") {
        setChunkCount(data.chunk_count);
      } else {
        // Poll for status
        const interval = pollIngestionStatus(id, setStatus, setChunkCount);
        return () => clearInterval(interval);
      }
    }

    loadProfile();
  }, [id]);

  // Handle ingestion status updates
  useEffect(() => {
    if (!id) return;
    async function checkStatus() {
      const statusData = await apiFetch(`/api/v1/profiles/${id}/ingest/status`);
      setStatus(statusData.status);
      setChunkCount(statusData.chunk_count ?? 0);
    }
    checkStatus();
  }, [id, status]);

  if (!id) {
    return <div>Profile ID required</div>;
  }

  // If profile not loaded yet, show spinner
  if (!profile) {
    return <div>Loading profile...</div>;
  }

  // If ingestion failed, show error
  if (status === "failed") {
    return (
      <div className="p-6">
        <h2>Ingestion Failed</h2>
        <p>The profile could not be ingested. Please check your GitHub username and try again.</p>
        <ProfileForm />
      </div>
    );
  }

  // If ingestion completed, show review and generate options
  return (
    <Suspense fallback={<div>Loading profile {id}...</div>}>
      <div className="p-6">
        <h2>Profile: {profile.fullName}</h2>

        <div className="mt-4">
          <p>Chunks extracted: {chunkCount}</p>

          {chunkCount > 0 && (
            <ChunkReviewList chunks={reviewedChunks} profileId={id} />
          )}

          <GenerateResume profile={profile} profileId={id} />
        </div>
      </div>
    </Suspense>
  );
}