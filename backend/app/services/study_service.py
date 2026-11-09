from ..ai import prompts
from ..ai.groq_client import GroqClient
from ..core.errors import ServiceError
from ..domain.notes_text import DEPTHS, normalise_study_markdown, suggest_title, word_count
from ..models import User

MIN_WORDS = 80
CUT_OFF_NOTICE = "\n\n> This answer hit the length limit and may end early. Generate again with a narrower subject or the Quick revision depth."


def generate(ai: GroqClient, user: User, subject: str, depth: str, focus: str) -> dict:
    """Write study notes. Nothing is stored here: the learner reviews, edits and saves them as a note."""
    cfg = DEPTHS[depth]
    result = ai.chat(prompts.study_notes(subject, depth, cfg.label_words, focus, user.skill_level, user.target_role),
                     max_tokens=cfg.max_tokens, temperature=0.3, reasoning_effort="low", timeout=cfg.timeout)
    markdown = normalise_study_markdown(result.text, subject)
    if word_count(markdown) < MIN_WORDS:
        raise ServiceError(502, "The model returned almost nothing. Try again, or make the subject more specific.")
    if result.finish_reason == "length":
        markdown += CUT_OFF_NOTICE
    return {"subject": subject, "title": suggest_title(subject), "markdown": markdown, "words": word_count(markdown),
            "model": result.model, "truncated": result.finish_reason == "length"}
