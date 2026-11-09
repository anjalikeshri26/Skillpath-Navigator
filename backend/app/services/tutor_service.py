from sqlalchemy.orm import Session

from ..ai import prompts
from ..ai.groq_client import GroqClient
from ..models import User
from . import mastery_service


def answer(db: Session, ai: GroqClient, user: User, message: str, history: list[dict]) -> str:
    mastery = mastery_service.load_mastery(db, user.id)
    weak = sorted(((t, s.score) for t, s in mastery.items() if s.evidence >= 3), key=lambda kv: kv[1])[:3]
    context = f"target role {user.target_role}; level {user.skill_level}."
    if weak:
        context += " Weakest quiz topics: " + ", ".join(f"{t} ({round(score * 100)}%)" for t, score in weak) + "."
    reply = ai.chat(prompts.tutor_messages(context, history, message), fast=True, max_tokens=1500, temperature=0.4)
    return reply.text
