"""AI question generation with structural validation, de-duplication and independent verification.

A generated question is only stored if (1) it is well-formed, (2) it is not a near-duplicate of an existing
question on the topic, and (3) a second, independent model call that never saw the generator's answer picks
the same option. Anything that fails a gate is discarded rather than shown to learners.
"""
import logging
import threading
from collections import defaultdict

from sqlalchemy.orm import Session

from ..ai import prompts
from ..ai.groq_client import GroqClient
from ..domain.embeddings import TfidfIndex
from ..models import Question, Topic
from .question_bank import add_question, prompt_key

log = logging.getLogger(__name__)
DUPLICATE_THRESHOLD = 0.80
_locks: dict[tuple[int, str], threading.Lock] = defaultdict(threading.Lock)


def _clean(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    prompt = str(item.get("prompt", "")).strip()
    options = item.get("options")
    try:
        answer = int(item.get("answer_index"))
    except (TypeError, ValueError):
        return None
    if len(prompt) < 20 or not isinstance(options, list) or len(options) != 4 or not 0 <= answer < 4:
        return None
    options = [str(o).strip() for o in options]
    if any(not o for o in options) or len({o.lower() for o in options}) != 4:
        return None
    if any(o.lower().startswith(("all of the above", "none of the above")) for o in options):
        return None
    return {"prompt": prompt, "options": options, "answer_index": answer, "explanation": str(item.get("explanation", "")).strip()[:600]}


def _verify(ai: GroqClient, candidates: list[dict]) -> list[dict]:
    payload = [{"id": i, "prompt": c["prompt"], "options": c["options"]} for i, c in enumerate(candidates)]
    reply = ai.chat_json(prompts.question_verification(payload), max_tokens=2500, reasoning_effort="medium")
    answers = reply.get("answers", []) if isinstance(reply, dict) else []
    solved = {a.get("id"): a.get("answer_index") for a in answers if isinstance(a, dict)}
    return [c for i, c in enumerate(candidates) if solved.get(i) == c["answer_index"]]


def generate_questions(db: Session, ai: GroqClient, topic: Topic, difficulty: str, count: int) -> int:
    """Create up to `count` verified questions. Returns how many were stored. May raise AIError."""
    with _locks[(topic.id, difficulty)]:
        existing = db.query(Question.id, Question.prompt).filter(Question.topic_id == topic.id).all()
        index = TfidfIndex({str(qid): text for qid, text in existing}) if existing else None
        recent = [text for _, text in existing[-15:]]
        reply = ai.chat_json(prompts.question_generation(topic.name, difficulty, count, recent), max_tokens=5000)
        items = reply.get("questions", []) if isinstance(reply, dict) else reply
        accepted: list[dict] = []
        for raw in items if isinstance(items, list) else []:
            item = _clean(raw)
            if item is None:
                continue
            if index and (nearest := index.nearest(item["prompt"])) and nearest[1] >= DUPLICATE_THRESHOLD:
                continue
            if accepted and (near := TfidfIndex({str(i): a["prompt"] for i, a in enumerate(accepted)}).nearest(item["prompt"])) and near[1] >= DUPLICATE_THRESHOLD:
                continue
            accepted.append(item)
        verified = _verify(ai, accepted) if accepted else []
        stored = 0
        for item in verified:
            if add_question(db, topic, difficulty=difficulty, source="ai", model=ai.model, **item):
                stored += 1
        db.commit()
        log.info("Generated %s: %d proposed, %d accepted, %d verified, %d stored", topic.name, len(items or []), len(accepted), len(verified), stored)
        return stored
