import React from "react";
import { FinalResume } from "../../types";

interface GenerateResumeProps {
  summary: string;
  skills: { category: string; skills: string[] }[];
  workExperience: {
    company: string;
    title: string;
    startDate: string;
    endDate?: string | null;
    bullets: { text: string; sourceChunkIds: string[]; matchedKeywords: string[] }[];
  }[];
  projects: {
    name: string;
    url?: string;
    technologies: string[];
    bullets: { text: string; sourceChunkIds: string[]; matchedKeywords: string[] }[];
  }[];
  keywordCoverage: { covered: string[]; missing: string[] };
  warnings: string[];
  jobTitle: string;
}

export default function GenerateResume({
  summary,
  skills,
  workExperience,
  projects,
  keywordCoverage,
  warnings,
  jobTitle,
}: GenerateResumeProps) {
  // Format skills into groups for display
  const skillGroups = skills.map((s) => ({
    category: s.category,
    skills: s.skills,
  }));

  // Format work experience
  const workRows = workExperience.map((we, i) => (
    <div key={i} className="mb-4 p-3 border rounded">
      <h4 className="font-medium">{we.title} at {we.company}</h4>
      <p className="text-xs text-gray-500">{we.startDate}{we.endDate && ` - ${we.endDate}`}</p>
      {we.bullets.map((b, j) => (
        <div key={j} className="mt-2 text-sm">
          <span className="font-medium">•</span> {b.text}
          {b.matchedKeywords.length > 0 && (
            <span className="text-xs text-gray-400 ml-2">
              ({b.matchedKeywords.join(", ")})
            </span>
          )}
        </div>
      ))}
    </div>
  ));

  // Format projects
  const projectRows = projects.map((pe, i) => (
    <div key={i} className="mb-4 p-3 border rounded">
      <h4 className="font-medium">{pe.name}</h4>
      <p className="text-xs text-gray-500 mt-1">
        {"GitHub: "}{pe.url || "private repository"}
      </p>
      {pe.technologies.map((t, j) => (
        <span key={j} className="mr-1 text-xs bg-gray-100 rounded px-1">
          {t}
        </span>
      ))}
      {pe.bullets.map((b, j) => (
        <div key={j} className="mt-2 text-sm">
          <span className="font-medium">•</span> {b.text}
          {b.matchedKeywords.length > 0 && (
            <span className="text-xs text-gray-400 ml-2">
              ({b.matchedKeywords.join(", ")})
            </span>
          )}
        </div>
      ))}
    </div>
  ));

  // Format keyword coverage
  const coveredKeywords = keywordCoverage.covered.join(", ") || "None";
  const missingKeywords = keywordCoverage.missing.join(", ") || "None";

  return (
    <div>
      <h3 className="text-xl font-bold mb-4">Generated Resume</h3>

      <p className="text-lg font-medium">Summary:</p>
      <p className="mt-1">{summary}</p>

      <div className="mt-4">
        <p className="font-medium">Skills:</p>
        <div className="grid grid-cols-2 gap-2 mt-2">
          {skillGroups.map((sg, i) => (
            <div key={i}>
              <p className="font-semibold text-sm">{sg.category}</p>
              <div className="mt-1">
                {sg.skills.map((skill, j) => (
                  <span key={j} className="text-xs bg-blue-100 rounded px-2 py-0.5 ml-1">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {workRows.length > 0 && (
        <div className="mt-6">
          <p className="font-medium">Work Experience:</p>
          {workRows}
        </div>
      )}

      {projectRows.length > 0 && (
        <div className="mt-6">
          <p className="font-medium">Projects:</p>
          {projectRows}
        </div>
      )}

      <div className="mt-6 p-3 border rounded" style={{ backgroundColor: "#f0fdf4" }}>
        <p className="font-medium text-sm">Keyword Coverage:</p>
        <p className="text-xs">
          <span className="font-medium">Covered:</span> {coveredKeywords}
          <span className="ml-4 text-gray-400"> | </span>
          <span className="font-medium">Missing:</span> {missingKeywords}
        </p>
      </div>

      {warnings.length > 0 && (
        <div className="mt-6 p-3 border rounded" style={{ backgroundColor: "#fffbeb" }}>
          <p className="font-medium text-sm">Warnings:</p>
          <ul className="text-xs mt-1 space-y-1">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}