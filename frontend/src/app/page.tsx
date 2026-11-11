import { Suspense } from "react";
import { AlignRequest } from "../types";
import { pollIngestionStatus, apiFetch } from "../lib/polling";
import ProfileForm from "../components/forms/ProfileForm";
import JobDescriptionForm from "../components/forms/JobDescriptionForm";
import GeneratedResume from "../components/resume/GeneratedResume";

export default function Home() {
  return (
    <Suspense fallback={<h1>Quick Resume Maker</h1>}>
      <div className="max-w-2xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Create a Tailored Resume</h1>

        {/* Step 1: Profile Setup */}
        <ProfileForm />

        {/* Step 2: Job Description Input */}
        <JobDescriptionForm />

        {/* Step 3: Generated Resume (shown after alignment) */}
        <GeneratedResume />
      </div>
    </Suspense>
  );
}