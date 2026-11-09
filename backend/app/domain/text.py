"""Small text helpers shared by retrieval, de-duplication and resume analysis."""
import re

_WORD = re.compile(r"[a-z0-9+#]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were which with what "
    "do does did can could would should will not no yes if then than into over under about after before".split()
)


def normalise(text: str) -> str:
    """Lower-case and collapse everything that is not a letter or digit to single spaces."""
    return re.sub(r"[\W_]+", " ", (text or "").lower()).strip()


def tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall((text or "").lower()) if t not in _STOPWORDS]


def features(text: str) -> list[str]:
    """Unigrams plus adjacent bigrams, which gives phrase-level matching without a model."""
    words = tokens(text)
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
