from dataclasses import dataclass
from typing import Tuple

from data import SKILLS


@dataclass(frozen=True)
class SkillCast:
    skill_id: str
    targets: Tuple[str, ...] = ()


@dataclass
class ActiveSkill:
    skill_id: str
    targets: Tuple[str, ...]
    remaining_ticks: int


def normalize_targets(value):
    """Return validated, de-duplicated target codes in first-seen order."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("invalid skill targets")

    targets = []
    seen = set()
    for code in value:
        if not isinstance(code, str) or not code:
            raise ValueError("invalid skill targets")
        if code not in seen:
            seen.add(code)
            targets.append(code)
    return tuple(targets)


def validate_skill_table(skills=SKILLS):
    for sid, skill in skills.items():
        duration = skill.duration
        cooldown = skill.cooldown
        if (
            type(duration) is not int
            or type(cooldown) is not int
            or not 1 <= duration <= cooldown
        ):
            raise ValueError(f"invalid skill duration/cooldown: {sid}")


validate_skill_table()
