import { useEffect, useState } from "react";
import { apiFetch } from "./api-client";

/** Poll the ingestion status endpoint until the profile is ready. */
export function useIngestStatus(profileId) {
  const [status, setStatus] = useState("pending");
  const [chunkCount, setChunkCount] = useState(0);

  useEffect(() => {
    if (!profileId) return undefined;
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await apiFetch(`/api/v1/profiles/${profileId}/ingest/status`);
        if (cancelled) return;
        setStatus(data.status);
        setChunkCount(data.chunk_count ?? 0);
      } catch {
        /* UI keeps the last known state */
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [profileId]);

  return { status, chunkCount };
}
