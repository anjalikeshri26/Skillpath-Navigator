import logging
import random
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ai.groq_client import AIError, GroqClient
from ..core.clock import utcnow
from ..core.errors import ServiceError
from ..domain import adaptive, grading
from ..domain.mastery import MasteryState
from ..models import Question, QuestionReport, QuestionSeen, QuizSession, QuizSessionQuestion, Topic, User
from . import mastery_service
from .question_bank import available_questions
from .question_generation import generate_questions

log = logging.getLogger(__name__)
SECONDS_PER_QUESTION = 75
SUBMIT_GRACE_SECONDS = 90
REPORTS_TO_FLAG = 3
MIN_QUESTIONS = 3


def _gather(db: Session, ai: GroqClient, user: User, topic: Topic, difficulty: str, needed: int,
            chosen: set[int], notices: list[str]) -> list[Question]:
    """Collect `needed` unseen questions for one slot, generating more or relaxing difficulty if the bank is short."""
    pool = available_questions(db, user.id, topic.name, difficulty, chosen)
    if len(pool) < needed and ai.configured:
        try:
            generate_questions(db, ai, topic, difficulty, max(6, needed - len(pool)))
            pool = available_questions(db, user.id, topic.name, difficulty, chosen)
        except AIError as exc:
            log.warning("Question generation failed for %s/%s: %s", topic.name, difficulty, exc)
            notices.append(f"Fresh {topic.name} questions could not be generated right now.")
    picked = random.sample(pool, min(needed, len(pool)))
    for other in adaptive.neighbours(difficulty):
        if len(picked) >= needed:
            break
        extra = [q for q in available_questions(db, user.id, topic.name, other, chosen | {p.id for p in picked})]
        take = random.sample(extra, min(needed - len(picked), len(extra)))
        if take:
            notices.append(f"Used some {other} {topic.name} questions because {difficulty} ones ran out.")
        picked += take
    return picked


def start_session(db: Session, ai: GroqClient, user: User, topic_name: str, difficulty: str, limit: int) -> dict:
    topics = {t.name: t for t in db.query(Topic).order_by(Topic.name).all()}
    if topic_name != "Mixed" and topic_name not in topics:
        raise ServiceError(400, f"Unknown topic: {topic_name}")
    if difficulty != "Adaptive" and difficulty not in adaptive.DIFFICULTIES:
        raise ServiceError(400, f"Unknown difficulty: {difficulty}")

    topic_names = list(topics) if topic_name == "Mixed" else [topic_name]
    mastery = mastery_service.load_mastery(db, user.id)
    plan = adaptive.plan_session(topic_names, mastery, limit, None if difficulty == "Adaptive" else difficulty)
    slots = Counter(plan)

    chosen: dict[int, Question] = {}
    notices: list[str] = []
    for (name, level), needed in slots.items():
        for q in _gather(db, ai, user, topics[name], level, needed, set(chosen), notices):
            chosen[q.id] = q

    # Top up from any topic in the plan if some slots could not be filled.
    if len(chosen) < limit:
        for name in topic_names:
            for level in adaptive.DIFFICULTIES:
                if len(chosen) >= limit:
                    break
                extra = available_questions(db, user.id, name, level, set(chosen))
                for q in random.sample(extra, min(limit - len(chosen), len(extra))):
                    chosen[q.id] = q

    if len(chosen) < MIN_QUESTIONS:
        hint = "" if ai.configured else " Add a GROQ_API_KEY to generate fresh questions."
        raise ServiceError(404, f"You have used up the available questions for this selection. Try another topic or difficulty.{hint}")
    if len(chosen) < limit:
        notices.append(f"Only {len(chosen)} unseen questions were available for this selection.")

    questions = list(chosen.values())
    random.shuffle(questions)
    now = utcnow()
    seconds = len(questions) * SECONDS_PER_QUESTION
    session = QuizSession(user_id=user.id, topic_label=topic_name, difficulty_label=difficulty, created_at=now,
                          expires_at=now + timedelta(seconds=seconds), total=len(questions))
    served = []
    for position, q in enumerate(questions):
        order = list(range(len(q.options)))
        random.shuffle(order)
        session.items.append(QuizSessionQuestion(question_id=q.id, position=position, option_order=order))
        served.append({"id": q.id, "topic": q.topic.name, "difficulty": q.difficulty, "prompt": q.prompt,
                       "options": [q.options[i] for i in order]})
    db.add(session)
    db.commit()
    return {"session_id": session.id, "seconds_allowed": seconds, "expires_at": session.expires_at.isoformat(),
            "notices": sorted(set(notices)), "questions": served}


def submit_session(db: Session, user: User, session_id: int, answers: dict[int, int | None]) -> dict:
    session = db.get(QuizSession, session_id)
    if session is None or session.user_id != user.id:
        raise ServiceError(404, "Test session not found")
    if session.submitted_at is not None:
        raise ServiceError(409, "This test was already submitted")
    now = utcnow()
    if now > session.expires_at + timedelta(seconds=SUBMIT_GRACE_SECONDS):
        raise ServiceError(410, "This test timed out before it was submitted. Start a new one.")
    served_ids = {item.question_id for item in session.items}
    if not set(answers) <= served_ids:
        raise ServiceError(400, "Answers include questions that were not part of this test")

    key = {item.question_id: item.question.answer_index for item in session.items}
    orders = {item.question_id: item.option_order for item in session.items}
    graded = {g.question_id: g for g in grading.grade(key, orders, answers)}

    mastery_input = []
    per_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    details = []
    for item in session.items:
        g, q = graded[item.question_id], item.question
        item.selected_original_index = g.selected_original_index
        item.is_correct = g.is_correct
        item.skipped = g.skipped
        q.times_answered += 1
        q.times_correct += int(g.is_correct)
        mastery_input.append((q.topic_id, q.topic.name, q.difficulty, g.is_correct))
        per_topic[q.topic.name][0] += int(g.is_correct)
        per_topic[q.topic.name][1] += 1
        details.append({
            "question_id": q.id, "topic": q.topic.name, "difficulty": q.difficulty, "prompt": q.prompt,
            "options": [q.options[i] for i in item.option_order],
            "selected_position": g.selected_position,
            "correct_position": item.option_order.index(q.answer_index),
            "is_correct": g.is_correct, "skipped": g.skipped, "explanation": q.explanation,
        })

    already_seen = {qid for (qid,) in db.query(QuestionSeen.question_id).filter(QuestionSeen.user_id == user.id, QuestionSeen.question_id.in_(list(served_ids)))}
    for qid in served_ids - already_seen:
        db.add(QuestionSeen(user_id=user.id, question_id=qid))

    correct = sum(g.is_correct for g in graded.values())
    total = len(graded)
    session.submitted_at, session.correct, session.total = now, correct, total
    session.score = round(100 * correct / total, 1) if total else 0.0
    changes = mastery_service.apply_answers(db, user.id, mastery_input)
    db.commit()

    mastery_after = mastery_service.load_mastery(db, user.id)
    return {
        "session_id": session.id, "score": session.score, "correct": correct, "total": total,
        "skipped": sum(g.skipped for g in graded.values()),
        "per_topic": [{"topic": t, "correct": c, "total": n} for t, (c, n) in sorted(per_topic.items())],
        "mastery_changes": changes,
        "next_difficulty": {t: adaptive.recommend_difficulty(mastery_after.get(t)) for t in per_topic},
        "details": details,
    }


def history(db: Session, user: User, limit: int = 30) -> list[dict]:
    rows = (db.query(QuizSession).filter(QuizSession.user_id == user.id, QuizSession.submitted_at.is_not(None))
            .order_by(QuizSession.submitted_at.desc()).limit(limit).all())
    return [{"id": s.id, "topic": s.topic_label, "difficulty": s.difficulty_label, "score": s.score,
             "correct": s.correct, "total": s.total, "date": s.submitted_at.isoformat()} for s in rows]


def mastery_overview(db: Session, user: User) -> list[dict]:
    states: dict[str, MasteryState] = mastery_service.load_mastery(db, user.id)
    return sorted(
        ({"topic": t, "mastery": round(s.score, 3), "answers": round(s.evidence, 1), "reliable": s.reliable,
          "recommended_difficulty": adaptive.recommend_difficulty(s)} for t, s in states.items()),
        key=lambda row: row["mastery"])


def report_question(db: Session, user: User, question_id: int, reason: str) -> dict:
    question = db.get(Question, question_id)
    if question is None:
        raise ServiceError(404, "Question not found")
    if not db.query(QuestionReport.id).filter_by(user_id=user.id, question_id=question_id).first():
        db.add(QuestionReport(user_id=user.id, question_id=question_id, reason=reason))
        db.flush()
    reports = db.query(func.count(QuestionReport.id)).filter(QuestionReport.question_id == question_id).scalar()
    if reports >= REPORTS_TO_FLAG and question.status == "active":
        question.status = "under_review"
    db.commit()
    return {"reported": True, "status": question.status}
