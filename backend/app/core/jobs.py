from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobError(Exception):
    """Base error for background jobs."""


class ProfileNotFoundError(JobError):
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        super().__init__(f"Profile {profile_id} not found")


class JobRegistry:
    """In-memory job and profile registry for v1."""

    def __init__(self):
        self.profiles: Dict[str, dict] = {}
        self.ingest_jobs: Dict[str, dict] = {}

    def register_profile(self, profile_id: str, profile: dict):
        self.profiles[profile_id] = profile

    def get_profile(self, profile_id: str) -> Optional[dict]:
        return self.profiles.get(profile_id)

    def start_ingest(self, profile_id: str, github_username: str, portfolio_url: str | None):
        """Mark ingest as started and create job tracking."""
        profile = self.profiles.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)
        profile["ingest_status"] = IngestStatus.RUNNING.value
        profile["last_ingested_at"] = _utcnow_iso()
        self.ingest_jobs[profile_id] = {
            "profile_id": profile_id,
            "github_username": github_username,
            "portfolio_url": portfolio_url,
            "status": IngestStatus.RUNNING.value,
            "progress": "Ingestion started",
            "chunk_count": profile.get("chunk_count", 0),
            "error": None,
            "started_at": _utcnow_iso(),
        }

    def complete_ingest(
        self,
        profile_id: str,
        chunk_count: int,
        warnings: list | None = None,
        chunk_types: dict | None = None,
    ):
        profile = self.profiles.get(profile_id)
        if profile is not None:
            profile["ingest_status"] = IngestStatus.COMPLETED.value
            profile["chunk_count"] = chunk_count
            profile["last_ingested_at"] = _utcnow_iso()
        job = self.ingest_jobs.get(profile_id)
        if job is not None:
            job.update({
                "status": IngestStatus.COMPLETED.value,
                "progress": "Ingestion completed",
                "chunk_count": chunk_count,
                "error": None,
                "warnings": warnings or [],
                "chunk_types": chunk_types or {},
            })

    def save_alignment(self, profile_id: str, alignment: dict):
        """Store the latest alignment result so /export can render it."""
        self.ingest_jobs.setdefault(profile_id, {})["alignment"] = alignment
        profile = self.profiles.get(profile_id)
        if profile is not None:
            profile["last_alignment"] = alignment

    def get_alignment(self, profile_id: str) -> Optional[dict]:
        job = self.ingest_jobs.get(profile_id)
        if job is not None and job.get("alignment"):
            return job["alignment"]
        profile = self.profiles.get(profile_id)
        if profile is not None:
            return profile.get("last_alignment")
        return None

    def fail_ingest(self, profile_id: str, error: str):
        profile = self.profiles.get(profile_id)
        if profile is not None:
            profile["ingest_status"] = IngestStatus.FAILED.value
        job = self.ingest_jobs.get(profile_id)
        if job is not None:
            job.update({
                "status": IngestStatus.FAILED.value,
                "progress": "Ingestion failed",
                "error": error,
            })

    def get_ingest_status(self, profile_id: str) -> Optional[dict]:
        """Return the ingest status payload the frontend polls.

        Falls back to the profile record itself so this endpoint never
        404s for an existing profile that hasn't started ingestion yet.
        """
        profile = self.profiles.get(profile_id)
        if profile is None:
            return None
        job = self.ingest_jobs.get(profile_id)
        if job is not None:
            return {
                "profile_id": profile_id,
                "status": job.get("status", IngestStatus.RUNNING.value),
                "progress": job.get("progress", "In progress"),
                "chunk_count": job.get("chunk_count", profile.get("chunk_count", 0)),
                "error": job.get("error"),
                "warnings": job.get("warnings", []),
                "chunk_types": job.get("chunk_types", {}),
            }
        return {
            "profile_id": profile_id,
            "status": profile.get("ingest_status", IngestStatus.PENDING.value),
            "progress": "Ingestion not started" if profile.get("ingest_status") == IngestStatus.PENDING.value else "In progress",
            "chunk_count": profile.get("chunk_count", 0),
            "error": None,
            "warnings": [],
            "chunk_types": {},
        }


# Singleton instance
job_registry = JobRegistry()
