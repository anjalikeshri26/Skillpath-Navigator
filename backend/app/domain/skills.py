"""Skill taxonomy: loading, alias matching and role requirements."""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_ROLE = "Software Engineer"

# Characters that, when adjacent to an alias, mean we matched part of a longer token
# (e.g. "sql" inside "mysql", "c" inside "c++" or "c#").
_LEFT = r"(?<![\w+#.])"
_RIGHT = r"(?![\w+#])"


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    topic: str | None
    hours: int
    prerequisites: tuple[str, ...]
    patterns: tuple[re.Pattern, ...] = field(repr=False, default=())


@dataclass(frozen=True)
class Taxonomy:
    skills: dict[str, Skill]
    roles: dict[str, dict[str, int]]
    level_factor: dict[str, float]

    def requirements(self, role: str) -> dict[str, int]:
        return self.roles.get(role) or self.roles[DEFAULT_ROLE]

    def find_skills(self, text: str) -> dict[str, list[int]]:
        """Return {skill_id: [match start offsets]} for every skill mentioned in the text."""
        found: dict[str, list[int]] = {}
        for skill in self.skills.values():
            offsets = [m.start() for pattern in skill.patterns for m in pattern.finditer(text)]
            if offsets:
                found[skill.id] = sorted(offsets)
        return found

    def topic_to_skills(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for skill in self.skills.values():
            if skill.topic:
                mapping.setdefault(skill.topic, []).append(skill.id)
        return mapping


def _compile(alias) -> re.Pattern:
    text, case_sensitive = (alias["text"], alias.get("case_sensitive", False)) if isinstance(alias, dict) else (alias, False)
    body = r"\s+".join(re.escape(part) for part in text.split())
    return re.compile(_LEFT + body + _RIGHT, 0 if case_sensitive else re.IGNORECASE)


@lru_cache(maxsize=1)
def load_taxonomy(path: Path | None = None) -> Taxonomy:
    raw = json.loads((path or DATA_DIR / "skills.json").read_text(encoding="utf-8"))
    skills = {
        sid: Skill(
            id=sid,
            name=spec["name"],
            topic=spec["topic"],
            hours=spec["hours"],
            prerequisites=tuple(spec["prerequisites"]),
            patterns=tuple(_compile(a) for a in spec["aliases"]),
        )
        for sid, spec in raw["skills"].items()
    }
    for role, weights in raw["roles"].items():
        unknown = set(weights) - set(skills)
        if unknown:
            raise ValueError(f"Role {role!r} references unknown skills: {sorted(unknown)}")
    return Taxonomy(skills=skills, roles=raw["roles"], level_factor=raw["level_factor"])
