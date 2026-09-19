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
