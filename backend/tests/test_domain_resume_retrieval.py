from app.domain.embeddings import TfidfIndex
from app.domain.resume_analysis import analyse, split_sections
from app.domain.skills import load_taxonomy

tax = load_taxonomy()

RESUME = """Asha Rao
asha@example.com | +91 98765 43210 | github.com/asha | linkedin.com/in/asha

Education
B.Tech in AI and Machine Learning, 2027

Skills
Python, SQL, Git, Docker

Projects
- Built a FastAPI service for resume parsing, reducing manual review time by 40%
- Developed a Flask dashboard with PostgreSQL and 12 REST endpoints
- Implemented a scikit-learn classifier reaching 91% accuracy on 5,000 rows

Experience
- Interned at a startup where I automated report generation using Python
"""


def test_sections_are_detected():
    sections = split_sections(RESUME)
    assert {"education", "skills", "projects", "experience"} <= set(sections)


def test_breakdown_sums_to_score_and_respects_maximums():
    result = analyse(RESUME, "Python Developer", tax)
    assert result["score"] == round(sum(b["points"] for b in result["breakdown"]))
    assert all(0 <= b["points"] <= b["max"] for b in result["breakdown"])
    assert sum(b["max"] for b in result["breakdown"]) == 100


def test_evidence_distinguishes_listed_from_demonstrated():
    skills = {s["id"]: s["evidence"] for s in analyse(RESUME, "Python Developer", tax)["skills"]}
    assert skills["python"] == "demonstrated"
    assert skills["docker"] == "listed"


def test_empty_resume_scores_low_and_gives_recommendations():
    result = analyse("Just a name", "Software Engineer", tax)
    assert result["score"] < 15 and result["recommendations"]


def test_job_description_match_reports_gaps():
    jd = "We need Python, Kubernetes-free Docker skills, SQL, and Java."
    match = analyse(RESUME, "Python Developer", tax, job_description=jd)["jd_match"]
    assert "Java" in match["missing"] and "Python" in match["matched"]


def test_search_ranks_the_relevant_document_first():
    index = TfidfIndex({"a": "binary search trees and graph traversal", "b": "window functions in SQL queries", "c": "TCP congestion control"})
    assert index.search("sql window query", k=1)[0][0] == "b"


def test_near_duplicates_score_higher_than_unrelated_questions():
    index = TfidfIndex({"q": "Which data structure follows last in first out order?"})
    same = index.search("Which data structure follows LIFO last in first out order?", 1)[0][1]
    other = index.search("What is the capital of France?", 1)
    assert same > 0.6 and (not other or other[0][1] < 0.2)
