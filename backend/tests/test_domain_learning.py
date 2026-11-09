from app.domain import adaptive, grading, mastery, roadmap_planner
from app.domain.mastery import MasteryState
from app.domain.skills import load_taxonomy

tax = load_taxonomy()


def test_mastery_rises_with_correct_hard_answers_more_than_easy():
    base = MasteryState()
    easy = mastery.update(base, correct=True, difficulty="Easy")
    hard = mastery.update(base, correct=True, difficulty="Hard")
    assert hard.score > easy.score > base.score


def test_wrong_easy_answer_hurts_more_than_wrong_hard_answer():
    base = MasteryState()
    assert mastery.update(base, correct=False, difficulty="Easy").score < mastery.update(base, correct=False, difficulty="Hard").score


def test_old_evidence_decays_toward_prior():
    strong = MasteryState(alpha=11.0, beta=1.0)
    later = mastery.decay(strong, days=90)
    assert 0.5 < later.score < strong.score


def test_new_learner_starts_easy_and_strong_learner_advances():
    assert adaptive.recommend_difficulty(None) == "Easy"
    assert adaptive.recommend_difficulty(MasteryState(alpha=15, beta=2)) == "Advanced"


def test_plan_session_gives_weak_topics_more_slots():
    states = {"SQL": MasteryState(alpha=2, beta=8), "Python": MasteryState(alpha=9, beta=2)}
    plan = adaptive.plan_session(["SQL", "Python"], states, limit=10)
    assert len(plan) == 10
    assert sum(1 for t, _ in plan if t == "SQL") > sum(1 for t, _ in plan if t == "Python")


def test_fixed_difficulty_is_respected():
    plan = adaptive.plan_session(["SQL", "DSA"], {}, limit=6, difficulty="Hard")
    assert {d for _, d in plan} == {"Hard"}


def test_grading_maps_shuffled_positions_back_to_original_options():
    key = {1: 2, 2: 0}
    orders = {1: [3, 1, 2, 0], 2: [0, 1, 2, 3]}  # q1: original option 2 is shown at position 2
    graded = {g.question_id: g for g in grading.grade(key, orders, {1: 2, 2: None})}
    assert graded[1].is_correct and not graded[1].skipped
    assert graded[2].skipped and not graded[2].is_correct


def test_grading_ignores_answers_for_unserved_questions_and_bad_positions():
    graded = grading.grade({1: 0}, {1: [0, 1, 2, 3]}, {1: 9, 99: 0})
    assert len(graded) == 1 and graded[0].skipped


def test_plan_orders_prerequisites_first_and_pulls_in_weak_ones():
    plan = roadmap_planner.build_plan("AI/ML Engineer", "Beginner", tax, {})
    order = [i.skill_id for i in plan]
    assert order.index("python") < order.index("numpy") < order.index("pandas")
    assert order.index("ml") > order.index("statistics")


def test_mastered_skills_leave_the_plan_and_weak_quiz_topics_rise():
    states = {"Python": MasteryState(alpha=20, beta=1), "SQL": MasteryState(alpha=2, beta=9)}
    plan = roadmap_planner.build_plan("Python Developer", "Intermediate", tax, states)
    ids = [i.skill_id for i in plan]
    assert "python" not in ids
    sql = next(i for i in plan if i.skill_id == "sql")
    assert sql.priority == "High" and "mastery" in sql.reason


def test_resume_evidence_changes_the_reason_and_priority():
    without = {i.skill_id: i for i in roadmap_planner.build_plan("Data Analyst", "Beginner", tax, {})}
    with_ev = {i.skill_id: i for i in roadmap_planner.build_plan("Data Analyst", "Beginner", tax, {}, {"sql": "demonstrated"})}
    assert with_ev["sql"].priority_score < without["sql"].priority_score
    assert "resume" in with_ev["sql"].reason


def test_unknown_role_falls_back_to_default():
    assert roadmap_planner.build_plan("Astronaut", "Beginner", tax, {})
