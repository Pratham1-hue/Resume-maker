import React from "react";
import { FinalResume } from "../../types";

interface ResumePreviewProps {
  resume: FinalResume;
}

export default function ResumePreview({ resume }: ResumePreviewProps) {
  const header = resume.header;

  return (
    <div className="max-w-print mx-auto font-sans">
      {/* Header section */}
      <header className="pt-4 pb-6 border-b border-gray-300">
        <div className="flex items-baseline gap-6">
          <div>
            <h1 className="text-3xl font-bold">{header.fullName}</h1>
            {header.phone && <p className="text-sm text-gray-500">{header.phone}</p>}
            {header.location && <p className="text-sm text-gray-500">{header.location}</p>}
          </div>
          <div>
            {header.github_url && (
              <a
                href={header.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover underline text-sm"
              >
                GitHub
              </a>
            )}
            {header.portfolio_url && (
              <a
                href={header.portfolio_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover underline text-sm"
              >
                Portfolio
              </a>
            )}
            {header.linkedin_url && (
              <a
                href={header.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover underline text-sm"
              >
                LinkedIn
              </a>
            )}
          </div>
        </div>
      </header>

      {/* Summary */}
      {resume.summary && (
        <section className="mb-6 pt-4 border-t border-gray-300">
          <h2 className="text-xl font-semibold mb-2">Professional Summary</h2>
          <p>{resume.summary}</p>
        </section>
      )}

      {/* Skills -->
      {resume.skills.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xl font-semibold mb-3">Skills</h2>
          <div className="grid grid-cols-2 gap-4">
            {resume.skills.map((sg, i) => (
              <div key={i} className="p-3 border rounded">
                <p className="font-medium text-sm">{sg.category}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {sg.skills.map((skill, j) => (
                    <span key={j} className="text-xs bg-gray-100 rounded px-2 py-0.5">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}*/

      {/* Work Experience */}
      {resume.work_experience.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xl font-semibold mb-3">Work Experience</h2>
          {resume.work_experience.map((we, i) => (
            <div key={i} className="mb-4 p-3 border rounded">
              <h3 className="font-medium">{we.title} at {we.company}</h3>
              <p className="text-xs text-gray-500">
                {we.start_date}{we.end_date && ` - ${we.end_date}`}
              </p>
              {we.bullets.map((b, j) => (
                <div key={j} className="mt-2 text-sm">
                  <span className="font-medium">•</span>{" "}
                  {b.text}
                  {b.matched_keywords?.length > 0 && (
                    <span className="text-xs text-gray-400 ml-2">
                      ({b.matched_keywords.join(", ")})
                    </span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      {/* Projects */}
      {resume.projects.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xl font-semibold mb-3">Projects</h2>
          {resume.projects.map((pe, i) => (
            <div key={i} className="mb-4 p-3 border rounded">
              <h3 className="font-medium">{pe.name}</h3>
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
                  <span className="font-medium">•</span>{" "}
                  {b.text}
                  {b.matched_keywords?.length > 0 && (
                    <span className="text-xs text-gray-400 ml-2">
                      ({b.matched_keywords.join(", ")})
                    </span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      {/* Education */}
      {resume.education.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xl font-semibold mb-3">Education</h2>
          {resume.education.map((ed, i) => (
            <div key={i} className="mb-3 p-2 border rounded">
              <p className="font-medium">{ed.institution}</p>
              <p className="text-xs text-gray-500">
                {ed.degree}{ed.field_of_study && ` in ${ed.field_of_study}`}
              </p>
              {ed.end_year && (
                <p className="text-xs text-gray-500">Graduated: {ed.end_year}</p>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}