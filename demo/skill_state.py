from dataclasses import dataclass
import logging
import math
from numbers import Real
from typing import Tuple

from data import COUNTRIES, SKILLS


logger = logging.getLogger(__name__)
COUNTRY_CODES = frozenset(country.code for country in COUNTRIES)


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


def applies(active, code):
    return not active.targets or code in active.targets


def modifiers(active_effects, code):
    result = {
        'downloads_mult': 1.0,
        'suspicion_mult': 1.0,
        'compute_mult': 1.0,
        'stealth_ratio_bonus': 0.0,
        'stealth_ratio_mult': 1.0,
    }
    for active in active_effects:
        if not applies(active, code):
            continue
        skill = SKILLS[active.skill_id]
        result['downloads_mult'] *= skill.downloads_mult
        result['suspicion_mult'] *= skill.suspicion_mult
        result['compute_mult'] *= skill.compute_mult
        result['stealth_ratio_bonus'] += skill.stealth_ratio_bonus
        result['stealth_ratio_mult'] *= skill.stealth_ratio_mult
    return result


def instant_deltas(new_casts):
    compute = 0.0
    suspicion = 0.0
    for cast in new_casts:
        skill = SKILLS[cast.skill_id]
        count = max(1, len(cast.targets))
        compute += skill.compute_delta * count
        suspicion += skill.suspicion_delta * count
    return compute, suspicion


def _finite_positive(value):
    if isinstance(value, bool) or not isinstance(value, Real) or value <= 0:
        return False
    return not isinstance(value, float) or math.isfinite(value)


def validate_live_skill_state(queue, active, cooldowns):
    """Reject corrupt persisted skill state before a tick mutates anything."""
    try:
        queue_ids = [cast.skill_id for cast in queue]
        active_ids = [effect.skill_id for effect in active]
        all_ids = queue_ids + active_ids

        if any(skill_id not in SKILLS for skill_id in all_ids):
            raise ValueError('unknown queued or active skill')
        if len(queue_ids) != len(set(queue_ids)):
            raise ValueError('duplicate queued skill')
        if len(active_ids) != len(set(active_ids)):
            raise ValueError('duplicate active skill')
        if set(queue_ids) & set(active_ids):
            raise ValueError('skill present in queue and active list')

        for skill_id, cooldown in cooldowns.items():
            if skill_id not in SKILLS or not _finite_positive(cooldown):
                raise ValueError('invalid cooldown')
        for skill_id in all_ids:
            if skill_id not in cooldowns:
                raise ValueError('missing cooldown')

        for cast in queue:
            if cooldowns[cast.skill_id] < SKILLS[cast.skill_id].duration:
                raise ValueError('queued cooldown shorter than duration')

        for item in list(queue) + list(active):
            targets = item.targets
            if (
                type(targets) is not tuple
                or normalize_targets(targets) != targets
                or any(code not in COUNTRY_CODES for code in targets)
            ):
                raise ValueError('invalid skill targets')

        for effect in active:
            remaining = effect.remaining_ticks
            duration = SKILLS[effect.skill_id].duration
            cooldown = cooldowns[effect.skill_id]
            if (
                type(remaining) is not int
                or not 1 <= remaining < duration
                or remaining > cooldown
            ):
                raise ValueError('invalid active duration')
    except (AttributeError, TypeError, ValueError) as exc:
        logger.error('invalid live skill state: %s', exc)
        raise ValueError('invalid live skill state') from None


validate_skill_table()
