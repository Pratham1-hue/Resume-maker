from __future__ import annotations

import base64
import logging
import os
from io import BytesIO
from typing import Any, Optional

from app.schemas.profile import UserProfile
from app.schemas.resume import (
    FinalResume,
    KeywordCoverage,
    ResumeHeader,
    ResumeSkillGroup,
)

logger = logging.getLogger(__name__)


def _build_document_from_scratch(title: str, context: dict):
    """Build a simple .docx with python-docx (no template needed)."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    header = context.get("resume_header", {})
    doc.add_heading(header.get("full_name", "Resume"), level=1)
    contact = " | ".join(
        p for p in [
            header.get("email", ""),
            header.get("phone", ""),
            header.get("location", ""),
        ] if p
    )
    if contact:
        doc.add_paragraph(contact)
    links = " | ".join(
        p for p in [
            header.get("github_url", ""),
            header.get("portfolio_url", ""),
            header.get("linkedin_url", ""),
        ] if p
    )
    if links:
        doc.add_paragraph(links)

    doc.add_heading("Professional Summary", level=2)
    doc.add_paragraph(context.get("resume_summary", ""))

    doc.add_heading("Skills", level=2)
    for group in context.get("resume_skills_groups", []):
        p = doc.add_paragraph()
        run = p.add_run(f"{group.get('category', '')}: ")
        run.bold = True
        p.add_run(", ".join(group.get("skills", [])))

    if context.get("resume_work_experience"):
        doc.add_heading("Work Experience", level=2)
        for we in context["resume_work_experience"]:
            doc.add_heading(f"{we.get('title', '')} at {we.get('company', '')}", level=3)
            for bullet in str(we.get("bullets", "")).split("; "):
                if bullet.strip():
                    doc.add_paragraph(bullet.strip(), style="List Bullet")

    if context.get("resume_projects"):
        doc.add_heading("Projects", level=2)
        for pe in context["resume_projects"]:
            doc.add_heading(pe.get("name", ""), level=3)
            tech = pe.get("technologies", "")
            if tech:
                p = doc.add_paragraph()
                p.add_run("Technologies: ").bold = True
                p.add_run(tech)
            for bullet in str(pe.get("bullets", "")).split("; "):
                if bullet.strip():
                    doc.add_paragraph(bullet.strip(), style="List Bullet")

    if context.get("resume_education"):
        doc.add_heading("Education", level=2)
        for ed in context["resume_education"]:
            doc.add_paragraph(
                f"{ed.get('institution', '')} — {ed.get('degree', '')} "
                f"{ed.get('field_of_study', '')} ({ed.get('end_year', '')})".strip()
            )

    for para in doc.paragraphs:
        for run in para.runs:
            run.font.size = Pt(11)
    doc.add_paragraph(f"Target role: {title}").italic = True
    return doc


class ResumeRenderer:
    """Renders a tailored resume to .docx (PDF: currently DOCX-first)."""

    @staticmethod
    def render_docx(
        resume: FinalResume,
        profile: UserProfile,
        job_title: str,
        company: str | None = None,
    ) -> bytes:
        """Render a .docx resume. Falls back to a built-in layout when the
        template file is missing or invalid."""
        context = ResumeRenderer._build_docx_context(resume, profile, job_title, company)
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "export", "templates", "resume_classic.docx",
        )
        try:
            from docxtpl import DocxTemplate

            if not os.path.exists(template_path):
                raise FileNotFoundError(template_path)
            doc = DocxTemplate(template_path)
            doc.render(context)
            buf = BytesIO()
            doc.save(buf)
            return buf.getvalue()
        except Exception as exc:
            logger.warning("Template render failed (%s); using built-in layout.", exc)
            doc = _build_document_from_scratch(job_title, context)
            buf = BytesIO()
            doc.save(buf)
            return buf.getvalue()

    @staticmethod
    def _build_docx_context(
        resume: FinalResume, profile: UserProfile, job_title: str, company: str | None
    ) -> dict:
        skills_groups: list = [
            {"category": sg.category, "skills": list(sg.skills)}
            for sg in resume.skills
        ]
        work_experience = [
            {
                "company": we.company,
                "title": we.title,
                "start_date": we.start_date,
                "end_date": we.end_date or "Present",
                "bullets": "; ".join(b.text for b in we.bullets),
            }
            for we in resume.work_experience
        ]
        projects = [
            {
                "name": pe.name,
                "url": str(pe.url) if pe.url else "N/A",
                "technologies": ", ".join(pe.technologies),
                "bullets": "; ".join(b.text for b in pe.bullets),
            }
            for pe in resume.projects
        ]
        education = [
            {
                "institution": ed.institution,
                "degree": ed.degree,
                "field_of_study": ed.field_of_study or "",
                "end_year": ed.end_year if ed.end_year is not None else "Present",
            }
            for ed in resume.education
        ]
        return {
            "resume_summary": resume.summary,
            "resume_skills_groups": skills_groups,
            "resume_work_experience": work_experience,
            "resume_projects": projects,
            "resume_education": education,
            "keyword_covered": "; ".join(resume.keyword_coverage.covered) or "None",
            "keyword_missing": "; ".join(resume.keyword_coverage.missing) or "None",
            "resume_header": {
                "full_name": profile.full_name,
                "email": str(profile.email),
                "phone": profile.phone or "",
                "location": profile.location or "",
                "github_url": f"https://github.com/{profile.github_username}",
                "portfolio_url": str(profile.portfolio_url) if profile.portfolio_url else "",
                "linkedin_url": str(profile.linkedin_url) if profile.linkedin_url else "",
            },
            "job_title": job_title,
            "company": company or "",
            "warnings": "; ".join(resume.warnings) or "None",
        }


def _profile_from_registry(profile_id: str) -> UserProfile:
    from app.core.jobs import job_registry

    profile_data = job_registry.get_profile(profile_id)
    if not profile_data:
        raise ValueError(f"Profile {profile_id} not found")

    def _clean_url(value: Any) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        return text if text.startswith(("http://", "https://")) else None

    return UserProfile(
        id=profile_data.get("id", profile_id),
        full_name=profile_data.get("full_name", "") or "Candidate",
        email=str(profile_data.get("email", "")).strip() or "unknown@example.com",
        github_username=profile_data.get("github_username", "") or "unknown",
        portfolio_url=_clean_url(profile_data.get("portfolio_url")),
        phone=profile_data.get("phone"),
        location=profile_data.get("location"),
        linkedin_url=_clean_url(profile_data.get("linkedin_url")),
    )


def _resume_from_alignment(profile_id: str, profile: UserProfile, job_title: str, company: str | None) -> FinalResume:
    """Rebuild a FinalResume from the stored alignment + profile.

    Falls back to a minimal profile-based resume when no alignment exists yet.
    """
    from app.core.jobs import job_registry
    from app.schemas.resume import ResumeBullet, ResumeEducation, ResumeProjectEntry, ResumeWorkEntry

    header = ResumeHeader(
        full_name=profile.full_name,
        email=str(profile.email),
        phone=profile.phone,
        location=profile.location,
        github_url=f"https://github.com/{profile.github_username}",
        portfolio_url=str(profile.portfolio_url) if profile.portfolio_url else None,
        linkedin_url=str(profile.linkedin_url) if profile.linkedin_url else None,
    )

    def _bullets(items: Any) -> list:
        out = []
        for b in items or []:
            if not isinstance(b, dict):
                continue
            text = str(b.get("text", "")).strip()
            if text:
                out.append(ResumeBullet(
                    text=text[:300],
                    source_chunk_ids=list(b.get("source_chunk_ids", []) or ["profile"]),
                    matched_keywords=list(b.get("matched_keywords", []) or []),
                ))
        return out

    alignment = job_registry.get_alignment(profile_id)
    if alignment:
        skills = [
            ResumeSkillGroup(category=str(g.get("category", "Skills")), skills=[str(s) for s in g.get("skills", [])])
            for g in alignment.get("skills", []) if isinstance(g, dict)
        ]
        work = [
            ResumeWorkEntry(
                company=str(w.get("company", "")), title=str(w.get("title", "")),
                start_date=str(w.get("start_date", "")), end_date=w.get("end_date"),
                bullets=_bullets(w.get("bullets")),
            )
            for w in alignment.get("work_experience", []) if isinstance(w, dict)
        ]
        projects = [
            ResumeProjectEntry(
                name=str(p.get("name", "")), url=p.get("url"),
                technologies=[str(t) for t in p.get("technologies", [])],
                bullets=_bullets(p.get("bullets")),
            )
            for p in alignment.get("projects", []) if isinstance(p, dict)
        ]
        kc = alignment.get("keyword_coverage", {}) or {}
        return FinalResume(
            id=f"resume_{profile_id}", profile_id=profile_id,
            job_title=job_title, company=company, header=header,
            summary=str(alignment.get("summary", ""))[:500],
            skills=skills, work_experience=work, projects=projects,
            education=_profile_education(profile_id),
            keyword_coverage=KeywordCoverage(
                covered=[str(c) for c in kc.get("covered", [])],
                missing=[str(m) for m in kc.get("missing", [])],
            ),
            warnings=[str(w) for w in alignment.get("warnings", [])],
        )

    return FinalResume(
        id=f"resume_{profile_id}", profile_id=profile_id,
        job_title=job_title, company=company, header=header,
        summary=f"Software professional tailoring background toward {job_title}.",
        skills=[ResumeSkillGroup(category="Languages", skills=["Python"])],
        education=_profile_education(profile_id),
        keyword_coverage=KeywordCoverage(covered=[], missing=[]),
        warnings=["No alignment stored yet — run Align first for a JD-tailored resume."],
    )


def _profile_education(profile_id: str) -> list:
    from app.core.jobs import job_registry
    from app.schemas.resume import ResumeEducation

    profile_data = job_registry.get_profile(profile_id) or {}
    out = []
    for edu in profile_data.get("education", []) or []:
        if not isinstance(edu, dict):
            continue
        try:
            end_year = edu.get("end_year")
            end_year = int(end_year) if end_year not in (None, "") else None
        except (TypeError, ValueError):
            end_year = None
        out.append(ResumeEducation(
            institution=str(edu.get("institution", "")),
            degree=str(edu.get("degree", "")),
            field_of_study=edu.get("field_of_study") or None,
            end_year=end_year,
        ))
    return out


def render_resume(
    profile_id: str,
    job_title: str,
    company: str | None = None,
    format: str = "docx",
) -> dict:
    """Render the latest stored alignment for a profile (profile-based fallback)."""
    profile = _profile_from_registry(profile_id)
    resume = _resume_from_alignment(profile_id, profile, job_title, company)

    if format == "pdf":
        pdf_bytes = _render_pdf(resume, profile, job_title, company)
        return {
            "download_url": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode(),
            "format": "pdf",
            "filename": "resume.pdf",
        }

    docx_bytes = ResumeRenderer.render_docx(resume, profile, job_title, company)
    return {
        "download_url": (
            "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,"
            + base64.b64encode(docx_bytes).decode()
        ),
        "format": "docx",
        "filename": "resume.docx",
    }


def _render_pdf(resume: FinalResume, profile: UserProfile, job_title: str, company: str | None) -> bytes:
    """Render a clean single-column PDF with reportlab (no LibreOffice needed)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=20, spaceAfter=2)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body2", parent=styles["Normal"], fontSize=10, leading=13)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, leading=12, textColor="#444444")

    story = [Paragraph(escape(resume.header.full_name), title_style)]
    contact = " | ".join(p for p in [
        resume.header.email, resume.header.phone or "", resume.header.location or "",
    ] if p)
    if contact:
        story.append(Paragraph(escape(contact), small))
    links = " | ".join(p for p in [
        resume.header.github_url or "", resume.header.portfolio_url or "", resume.header.linkedin_url or "",
    ] if p)
    if links:
        story.append(Paragraph(escape(links), small))
    story.append(Paragraph(
        "<i>Target role: " + escape(job_title) + (" at " + escape(company) if company else "") + "</i>", small))

    story.append(Paragraph("Professional Summary", h2))
    story.append(Paragraph(escape(resume.summary), body))

    if resume.skills:
        story.append(Paragraph("Skills", h2))
        for group in resume.skills:
            story.append(Paragraph(
                "<b>" + escape(group.category) + ":</b> " + escape(", ".join(group.skills)), body))

    for section_title, entries, is_work in (
        ("Work Experience", resume.work_experience, True),
        ("Projects", resume.projects, False),
    ):
        if not entries:
            continue
        story.append(Paragraph(section_title, h2))
        for entry in entries:
            if is_work:
                if entry.title or entry.company:
                    story.append(Paragraph(
                        "<b>" + escape(entry.title) + "</b>"
                        + (" at " + escape(entry.company) if entry.company else "") + " "
                        "<font color='#666666'>" + escape(entry.start_date)
                        + (" - " + escape(entry.end_date) if entry.end_date else "") + "</font>", body))
            else:
                tech = (" <font color='#666666'>[" + escape(", ".join(entry.technologies)) + "]</font>"
                        if entry.technologies else "")
                story.append(Paragraph("<b>" + escape(entry.name) + "</b>" + tech, body))
            for bullet in entry.bullets:
                story.append(Paragraph("&#8226; " + escape(bullet.text), body))

    if resume.education:
        story.append(Paragraph("Education", h2))
        for edu in resume.education:
            story.append(Paragraph(
                "<b>" + escape(edu.institution) + "</b> &#8212; " + escape(edu.degree)
                + (" in " + escape(edu.field_of_study) if edu.field_of_study else "")
                + (" (" + str(edu.end_year) + ")" if edu.end_year else ""), body))

    story.append(Spacer(1, 0.15 * inch))
    doc.build(story)
    return buf.getvalue()
