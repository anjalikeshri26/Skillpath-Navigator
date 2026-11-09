"""Transparent, rule-based resume analysis.

The score is a sum of five components whose points and maximums are returned to the caller, so a user can
see exactly where points were gained or lost. It is a screening heuristic, not an ATS simulation, and it
is only as good as the skill taxonomy in data/skills.json.
"""
import re

from .embeddings import TfidfIndex
from .skills import Taxonomy

DISCLAIMER = (
    "Rule-based feedback from keyword and structure checks, not a certified ATS score. "
    "Only add skills and claims that match your real experience."
)

_HEADINGS = {
    "education": ("education", "academic background", "academics"),
    "experience": ("experience", "work experience", "internship", "internships", "professional experience", "employment"),
    "projects": ("projects", "academic projects", "personal projects", "project work"),
    "skills": ("skills", "technical skills", "core competencies", "technologies", "tech stack"),
    "certifications": ("certifications", "certificates", "courses"),
    "summary": ("summary", "objective", "profile", "about me", "career objective"),
    "achievements": ("achievements", "awards", "honors", "accomplishments", "extracurricular"),
}
_HEADING_LOOKUP = {alias: key for key, aliases in _HEADINGS.items() for alias in aliases}

_ACTION_VERBS = frozenset(
    """built developed designed implemented created led reduced improved automated deployed optimized optimised trained
    analysed analyzed integrated engineered launched migrated wrote achieved managed delivered architected refactored
    tested scaled increased decreased streamlined collaborated mentored organised organized researched produced
    configured containerized containerised debugged presented established""".split()
)
_BULLET = re.compile(r"^\s*(?:[-*\u2022\u25aa\u25cf\u2013\u2014>]|\d+[.)])\s+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)\d{3,5}[\s-]?\d{3,5}(?!\d)")


def split_sections(text: str) -> dict[str, str]:
    """Group lines under the most recent recognised heading. Unrecognised leading text goes to 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        stripped = line.strip().strip(":").strip()
        key = _HEADING_LOOKUP.get(stripped.lower()) if 0 < len(stripped) <= 32 else None
        if key:
            current = key
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items() if "\n".join(v).strip()}


def _bullets(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if len(line.split()) >= 4]
    bulleted = [_BULLET.sub("", line) for line in lines if _BULLET.match(line)]
    return bulleted or [line for line in lines if line.split()[0].lower().strip(".,:") in _ACTION_VERBS]


def _is_quantified(bullet: str) -> bool:
    return bool(re.search(r"\d", _YEAR.sub("", bullet)))


def analyse(text: str, role: str, taxonomy: Taxonomy, job_description: str | None = None) -> dict:
    sections = split_sections(text)
    requirements = taxonomy.requirements(role)
    mentions = taxonomy.find_skills(text)

    # Evidence: a skill is "demonstrated" when it shows up in an experience or project section,
    # and merely "listed" when it only appears in a skills list or elsewhere.
    evidence_text = "\n".join(sections.get(k, "") for k in ("experience", "projects"))
    demonstrated_ids = set(taxonomy.find_skills(evidence_text)) if evidence_text else set()
    skills_found = []
    for sid in sorted(mentions, key=lambda s: -requirements.get(s, 0)):
        skills_found.append({
            "id": sid,
            "name": taxonomy.skills[sid].name,
            "evidence": "demonstrated" if sid in demonstrated_ids else "listed",
            "required_for_role": sid in requirements,
        })
    missing = [
        {"id": sid, "name": taxonomy.skills[sid].name, "weight": weight}
        for sid, weight in sorted(requirements.items(), key=lambda kv: -kv[1])
        if sid not in mentions
    ]

    total_weight = sum(requirements.values())
    found_weight = sum(w for sid, w in requirements.items() if sid in mentions)
    required_found = [sid for sid in requirements if sid in mentions]
    demo_weight = sum(requirements[sid] for sid in required_found if sid in demonstrated_ids)

    bullets = _bullets(evidence_text) if evidence_text else _bullets(text)
    quantified = [b for b in bullets if _is_quantified(b)]
    action_led = [b for b in bullets if b.split()[0].lower().strip(".,:") in _ACTION_VERBS]
    words = len(text.split())
    has_email = bool(_EMAIL.search(text))
    has_phone = bool(_PHONE.search(text))
    has_github = "github.com" in text.lower()
    has_linkedin = "linkedin.com" in text.lower()
    has_experience = "experience" in sections
    has_projects = "projects" in sections

    coverage_pts = round(40 * found_weight / total_weight, 1) if total_weight else 0.0
    evidence_pts = round(20 * demo_weight / found_weight, 1) if found_weight else 0.0
    if bullets:
        impact_pts = round(10 * min(1.0, len(quantified) / len(bullets) / 0.4) + 5 * min(1.0, len(action_led) / len(bullets) / 0.7), 1)
    else:
        impact_pts = 0.0
    structure_pts = 4 * ("education" in sections) + 4 * has_projects + 3 * has_experience + 4 * ("skills" in sections)
    contact_pts = 4 * has_email + 2 * has_phone + 2 * has_github + 2 * has_linkedin

    breakdown = [
        {"key": "coverage", "label": "Role skill coverage", "points": coverage_pts, "max": 40,
         "detail": f"{len(required_found)} of {len(requirements)} skills expected for {role} were found."},
        {"key": "evidence", "label": "Skills shown in projects or experience", "points": evidence_pts, "max": 20,
         "detail": f"{sum(1 for s in skills_found if s['required_for_role'] and s['evidence'] == 'demonstrated')} required skills appear in context, not only in a list."},
        {"key": "impact", "label": "Impact and action language", "points": impact_pts, "max": 15,
         "detail": f"{len(quantified)} of {len(bullets)} bullet points include a number; {len(action_led)} start with an action verb." if bullets else "No bullet points were detected."},
        {"key": "structure", "label": "Standard sections", "points": float(structure_pts), "max": 15,
         "detail": "Found: " + (", ".join(sorted(k for k in sections if k != "header")) or "none recognised")},
        {"key": "contact", "label": "Contact details and links", "points": float(contact_pts), "max": 10,
         "detail": "Email, phone, GitHub and LinkedIn are each worth points."},
    ]
    score = round(sum(item["points"] for item in breakdown))

    recommendations = []
    for item in [m for m in missing if m["weight"] >= 2][:3]:
        recommendations.append(f"{item['name']} is a high-weight skill for {role} and is not on your resume. If you have used it, add a project or bullet that shows how; if not, it belongs on your study plan.")
    listed_only = [s for s in skills_found if s["required_for_role"] and s["evidence"] == "listed"]
    if listed_only:
        names = ", ".join(s["name"] for s in listed_only[:3])
        recommendations.append(f"{names} appear only as keywords. Add a bullet under a project or internship describing what you built with them.")
    if bullets and len(quantified) / len(bullets) < 0.3:
        recommendations.append("Few bullets include numbers. Where it is true, state size, speed, accuracy or users, for example dataset rows, latency, accuracy or test coverage.")
    if bullets and len(action_led) / len(bullets) < 0.6:
        recommendations.append("Start bullets with a verb such as built, reduced or automated, followed by what you did and the result.")
    if not has_projects:
        recommendations.append("Add a Projects section. For a fresher it is the strongest evidence of skill.")
    if not (has_github or has_linkedin):
        recommendations.append("Add your GitHub and LinkedIn links so recruiters can verify your work.")
    if words < 150 or words > 1200:
        recommendations.append(f"The resume has about {words} words. Aim for one focused page, roughly 300 to 700 words.")

    result = {
        "score": score,
        "role": role,
        "breakdown": breakdown,
        "skills": skills_found,
        "missing_skills": missing,
        "metrics": {"words": words, "bullets": len(bullets), "quantified_bullets": len(quantified), "action_bullets": len(action_led), "sections": sorted(k for k in sections if k != "header")},
        "checks": [
            {"label": "Readable text extracted", "passed": words >= 80},
            {"label": "Email present", "passed": has_email},
            {"label": "Projects section present", "passed": has_projects},
            {"label": "Reasonable length", "passed": 150 <= words <= 1200},
        ],
        "recommendations": recommendations,
        "jd_match": None,
        "disclaimer": DISCLAIMER,
    }
    if job_description and job_description.strip():
        result["jd_match"] = match_job_description(text, job_description, taxonomy)
    return result


def match_job_description(resume_text: str, job_description: str, taxonomy: Taxonomy) -> dict:
    resume_skills = set(taxonomy.find_skills(resume_text))
    jd_skills = set(taxonomy.find_skills(job_description))
    matched = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)
    index = TfidfIndex({"resume": resume_text, "jd": job_description})
    similarity = index.search(job_description, k=2, allowed={"resume"})
    return {
        "skill_coverage": round(len(matched) / len(jd_skills), 2) if jd_skills else None,
        "matched": [taxonomy.skills[s].name for s in matched],
        "missing": [taxonomy.skills[s].name for s in missing],
        "text_similarity": round(similarity[0][1], 2) if similarity else 0.0,
        "note": "Coverage counts only skills that exist in the taxonomy. Text similarity is lexical overlap, not meaning." if jd_skills else
                "No taxonomy skills were recognised in the job description, so coverage could not be computed.",
    }
