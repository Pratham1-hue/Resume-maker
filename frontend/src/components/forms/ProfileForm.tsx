import { useState, type FormEvent } from "react";
import { createProfile } from "../../lib/api-client";

export interface ProfileFormProps {
  onProfileCreated?: (profileId: string) => void;
}

export default function ProfileForm({ onProfileCreated }: ProfileFormProps = {}) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    github_username: "",
    portfolio_url: "",
    phone: "",
    location: "",
    linkedin_url: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const profileId = await createProfile(form);
      setError(null);
      onProfileCreated?.(profileId);
    } catch (err: any) {
      setError(err.message || "Failed to create profile");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 border rounded-md mb-6">
      <h2 className="text-xl font-bold mb-4">Profile Setup</h2>

      <form onSubmit={handleSubmit} noValidate>
        <div className="grid grid-cols-1 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-1">Full Name</label>
            <input
              value={form.full_name}
              onChange={(e) =>
                setForm({ ...form, full_name: e.target.value })
              }
              required
              className="w-full border rounded p-2"
              placeholder="e.g. John Doe"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              value={form.email}
              onChange={(e) =>
                setForm({ ...form, email: e.target.value })
              }
              type="email"
              required
              className="w-full border rounded p-2"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">GitHub Username</label>
            <input
              value={form.github_username}
              onChange={(e) =>
                setForm({ ...form, github_username: e.target.value })
              }
              required
              className="w-full border rounded p-2"
              placeholder="e.g. johndoe"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Portfolio URL (optional)</label>
            <input
              value={form.portfolio_url}
              onChange={(e) =>
                setForm({ ...form, portfolio_url: e.target.value })
              }
              type="url"
              className="w-full border rounded p-2"
              placeholder="https://example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Phone (optional)</label>
            <input
              value={form.phone}
              onChange={(e) =>
                setForm({ ...form, phone: e.target.value })
              }
              type="tel"
              className="w-full border rounded p-2"
              placeholder="e.g. +1-555-0123"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Location (optional)</label>
            <input
              value={form.location}
              onChange={(e) =>
                setForm({ ...form, location: e.target.value })
              }
              className="w-full border rounded p-2"
              placeholder="e.g. San Francisco, CA"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">LinkedIn URL (optional)</label>
            <input
              value={form.linkedin_url}
              onChange={(e) =>
                setForm({ ...form, linkedin_url: e.target.value })
              }
              type="url"
              className="w-full border rounded p-2"
              placeholder="https://linkedin.com/in/johndoe"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="bg-primary-600 text-white px-6 py-2 rounded hover:bg-primary-700"
        >
          {submitting ? "Creating..." : "Create Profile"}
        </button>

        {error && (
          <p className="mt-2 text-red-600">{error}</p>
        )}
      </form>
    </div>
  );
}