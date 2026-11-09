"""Text rules for notes: titles, excerpts, search escaping and cleaning model-written markdown."""
import re
from dataclasses import dataclass

MAX_TITLE = 120
MAX_STUDY_CHARS = 60_000
_FENCE_WRAP = re.compile(r"\A\s*```(?:markdown|md)?[ \t]*\n(.*)\n```\s*\Z", re.DOTALL | re.IGNORECASE)


def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title or "").strip()


def title_key(title: str) -> str:
    """Case-insensitive identity of a title, used for the 'one note per name' rule."""
    return clean_title(title).casefold()


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def excerpt(body: str, limit: int = 160) -> str:
    """Plain-text preview: markdown punctuation removed, cut at a word boundary."""
    plain = re.sub(r"```.*?```", " ", body or "", flags=re.DOTALL)
    plain = re.sub(r"[#>*_`|~-]+", " ", plain)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= limit:
        return plain
    cut = plain[:limit].rsplit(" ", 1)[0] or plain[:limit]
    return cut.rstrip(".,;:") + "\u2026"


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so a search for '50%' matches the text, not everything. Use with escape='\\'."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def unwrap_markdown(text: str) -> str:
    """Models sometimes wrap a whole answer in a ```markdown fence. Remove that wrapper only."""
    match = _FENCE_WRAP.match(text)
    return match.group(1) if match else text


def normalise_study_markdown(text: str, subject: str) -> str:
    body = unwrap_markdown(text.replace("\r\n", "\n")).strip()
    if not body.startswith("# "):
        body = f"# {clean_title(subject)}\n\n{body}"
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body[:MAX_STUDY_CHARS]


def suggest_title(subject: str) -> str:
    return f"{clean_title(subject)}: study notes"[:MAX_TITLE]


@dataclass(frozen=True)
class Depth:
    label_words: str
    max_tokens: int  # gpt-oss models spend part of this budget on reasoning, so it is generous
    timeout: float


DEPTHS = {
    "Quick revision": Depth("600 to 900 words", 4000, 60),
    "Standard": Depth("1,200 to 1,800 words", 7000, 90),
    "In-depth": Depth("2,500 to 3,500 words", 10000, 120),
}
