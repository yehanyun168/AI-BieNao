# Skill Queue and Persistent Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every paid skill cast execute next tick in FIFO order, honor its declared duration, survive save/load, and show the truthful state in the Kivy UI.

**Architecture:** `demo/skill_state.py` owns small skill-state records, timing validation and pure aggregation. `engine.py` remains the sole mutable cast/tick authority; `save_manager.py` serializes v6 queue/active state with validation and rollback; UI reads that state and suppresses unsupported exact predictions. Each task is sequential at shared-file boundaries, with fresh implementer and independent spec/quality review before the next task.

**Tech Stack:** Python 3.12, Kivy, `unittest`, existing save migration and balance simulator.

---

## Context, isolation, and file map

Work only in `C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\.workbuddy\skill-queue-worktree` on `codex/skill-queue-effects`, based on locked-country commit `93f383d`. Approved specification: `docs/superpowers/specs/2026-09-18-skill-queue-effects-design.md`. Team prompts and ownership: `docs/superpowers/team/2026-09-18-game-optimization-team.md`. Do not change `main`, the old A worktree, real saves, tracked `tools/data/playtest_baseline.json` or an exe. Do not install GitHub resources in this package.

All commands below run from `demo/` with PowerShell environment `KIVY_NO_ARGS=1`, `KIVY_NO_FILELOG=1`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8` and interpreter `C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe`. Tests using `tempfile.TemporaryDirectory()` may need sandbox escalation to write the system TEMP; that is an environment permission request, not permission to use real saves. Baseline already observed in this worktree: `verify_tables.py` 38/38, `verify_tech_tree.py` 29/29, `test_edge_cases.py` 16/16, `test_v4_app.py` 57/57, locked-country `unittest` exited 0.

Set these variables in each new PowerShell test process:

```powershell
$env:KIVY_NO_ARGS = '1'
$env:KIVY_NO_FILELOG = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
```

| File | Single responsibility in this package |
|---|---|
| `demo/skill_state.py` (new) | Typed cast/active records, skill-table timing invariant, pure per-country modifiers and activation delta |
| `demo/engine.py` | Atomic `use_skill`, ordered queue activation, effect lifecycle and sole tick source |
| `demo/save_manager.py` | v5→v6 migration, strict v6 state validation, save/load and rollback |
| `demo/main.py` / `demo/ui_session.py` / `demo/ui_hud.py` / `demo/ui_input.py` / `demo/ui_drop.py` / `demo/i18n.py` | Remove UI-side effect state, show compact queue/active status, honest static preview, localized errors |
| `demo/test_skill_queue_effects.py` (new) | Headless engine/save tests plus isolated Kivy UI assertions |
| `demo/balance_sim.py` / `demo/verify_tables.py` | Explicit combo probe, measured line-budget registration only |
| `docs/superpowers/verification/2026-09-18-skill-queue-effects.md` (new) | Commands, old/new fixed-seed comparison, remaining release risks |

At every task handoff, implementer reports commit and red/green evidence; total manager commissions a spec reviewer first, then a quality reviewer. A failing review returns to the same implementer. No simultaneous edits to `engine.py`, `save_manager.py` or a UI file.

### Task 1: Define the skill-state vocabulary and reject invalid skill timing

**Files:** Create `demo/skill_state.py` and `demo/test_skill_queue_effects.py`; inspect `demo/data.py:141-257`.

- [ ] **Step 1: Add failing timing tests** to `demo/test_skill_queue_effects.py`:

```python
import unittest
from dataclasses import replace
import data
from skill_state import validate_skill_table

class SkillTimingTests(unittest.TestCase):
    def test_current_table_and_equal_boundary(self):
        validate_skill_table(data.SKILLS)
        skill = replace(data.SKILLS['stealth'], duration=2, cooldown=2)
        validate_skill_table({'equal': skill})

    def test_bad_duration_or_cooldown_rejected(self):
        for duration, cooldown in ((3, 2), (0, 2), (True, 2),
                                   (1.5, 2), (1, False)):
            with self.subTest(duration=duration, cooldown=cooldown):
                skill = replace(data.SKILLS['stealth'],
                                duration=duration, cooldown=cooldown)
                with self.assertRaises(ValueError):
                    validate_skill_table({'bad': skill})
```

- [ ] **Step 2: Run the red test.** Run: `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillTimingTests -v`. Expected: import failure because `skill_state` does not exist.
- [ ] **Step 3: Create the minimal records and validator** in `demo/skill_state.py`:

```python
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
        d, c = skill.duration, skill.cooldown
        if (type(d) is not int or type(c) is not int
                or not 1 <= d <= c):
            raise ValueError(f'invalid skill duration/cooldown: {sid}')

# Fail fast on the actual product table at import, not just in a test helper.
validate_skill_table()
```

- [ ] **Step 4: Run green and table checks.** Run the Task 1 unittest command, then `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' verify_tables.py`. Expected: timing tests pass; the existing 38 checks still pass. If the import graph guard rejects `skill_state`, register its true dependency layer, not a broad exemption.
- [ ] **Step 5: Commit only Task 1 files.** `git add demo/skill_state.py demo/test_skill_queue_effects.py`, then `git commit -m "test: enforce skill duration and cooldown invariant"`. Total manager requests spec and code-quality reviews.

### Task 2: Make casting atomic and append an ordered queue

**Files:** Modify `demo/engine.py:56-76,1087-1135`, `demo/skill_state.py`, `demo/test_skill_queue_effects.py` and the obsolete pending assertion in `demo/test_edge_cases.py:315-335`.

- [ ] **Step 1: Add failing cast tests.** Append a `SkillQueueCastTests` class with this setup and core assertions:

```python
import balance
import engine

class SkillQueueCastTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=41)
        engine.player.unlocked_skills.update({'algo_top', 'stealth'})
    def tearDown(self):
        balance.apply_difficulty('normal')
    def test_two_paid_casts_keep_order_and_charge_once(self):
        before = engine.player.compute
        self.assertTrue(engine.use_skill('algo_top'))
        self.assertTrue(engine.use_skill('stealth'))
        self.assertEqual([x.skill_id for x in engine.player.skill_queue],
                         ['algo_top', 'stealth'])
        self.assertEqual(engine.player.compute, before - 50)
        self.assertEqual(engine.player.skill_uses['algo_top'], 1)
    def test_invalid_target_has_zero_side_effects(self):
        before = (engine.player.compute,
                  dict(engine.player.skill_cooldowns),
                  dict(engine.player.skill_uses))
        self.assertFalse(engine.use_skill('algo_top', ['CN', 'NO-SUCH-CODE']))
        self.assertEqual((engine.player.compute,
                          engine.player.skill_cooldowns,
                          engine.player.skill_uses), before)
        self.assertEqual(engine.player.skill_queue, [])

    def test_same_skill_cannot_be_queued_twice(self):
        self.assertTrue(engine.use_skill('stealth'))
        before = (engine.player.compute, dict(engine.player.skill_uses),
                  list(engine.player.skill_queue))
        self.assertFalse(engine.use_skill('stealth'))
        self.assertEqual(
            (engine.player.compute, engine.player.skill_uses,
             engine.player.skill_queue), before)
```

- [ ] **Step 2: Confirm red.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillQueueCastTests -v`. Expected: missing `skill_queue` or assertion failure for overwritten first cast.
- [ ] **Step 3: Add typed fields and target normalization.** Replace `pending_skill`/`pending_skill_targets` with `skill_queue: List[SkillCast]` and `active_skill_effects: List[ActiveSkill]`, both `field(default_factory=list)`. Add to `skill_state.py`:

```python
def normalize_targets(value):
    if value is None or value == '':
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise ValueError('invalid target container')
    if any(not isinstance(code, str) or not code for code in value):
        raise ValueError('invalid target code')
    return tuple(dict.fromkeys(value))
```

- [ ] **Step 4: Replace the mutation tail of `use_skill` with all-or-nothing validation.** Keep its bool API and expose a read-only reason function for UI errors. Compute normalized targets before charging; require game active, known/unlocked skill, zero cooldown, no same-ID active effect, all target codes known/unlocked/below `TUNE['penetration_saturated']`, and enough compute. Implement this decision path in `engine.py`:

```python
def skill_cast_reason(skill_id, target_codes=None):
    if player is None or player.game_over:
        return 'game_over'
    if skill_id not in SKILLS or skill_id not in player.unlocked_skills:
        return 'locked'
    if (player.skill_cooldowns.get(skill_id, 0) > 0
            or any(x.skill_id == skill_id for x in player.active_skill_effects)):
        return 'cooldown'
    try:
        targets = normalize_targets(target_codes)
    except ValueError:
        return 'invalid_target'
    by_code = {c.config.code: c for c in player_countries}
    for code in targets:
        country = by_code.get(code)
        if country is None or not country.unlocked:
            return 'invalid_target'
        if country.penetration_rate >= TUNE['penetration_saturated']:
            return 'saturated'
    if player.compute < skill_cost_for(skill_id, len(targets)):
        return 'no_compute'
    return 'ok'

def use_skill(skill_id, target_codes=None):
    if skill_cast_reason(skill_id, target_codes) != 'ok':
        return False
    targets = normalize_targets(target_codes)
    cost = skill_cost_for(skill_id, len(targets))
    player.compute -= cost
    player.skill_cooldowns[skill_id] = SKILLS[skill_id].cooldown
    player.skill_uses[skill_id] = player.skill_uses.get(skill_id, 0) + 1
    player.skill_queue.append(SkillCast(skill_id, targets))
    return True
```

Import `SkillCast` and `normalize_targets` from `skill_state`. A blocked-but-targetable country retains the existing discounted-outcome semantics.
Update the edge-case AUTO assertion to require either a successful skill use count or a nonempty `skill_queue`, and print the queue in its failure diagnostic. Do not retain a compatibility alias named `pending_skill`.

- [ ] **Step 5: Green, regression, commit.** Run Task 2 unittest command, `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_edge_cases.py` and `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_build.py`. Expected: new cast tests, 16/16 edge checks and old build checks pass. Commit exact changed files with `git commit -m "feat: queue validated skill casts atomically"` after `git diff --check`; obtain two-stage review.

### Task 3: Resolve every queued skill and preserve multiplier duration

**Files:** Modify `demo/skill_state.py`, `demo/engine.py:233-416,465-471`, `demo/test_skill_queue_effects.py`.

- [ ] **Step 1: Add failing cycle tests** for two casts, 1/2/3 duration, same-country stacking, global and targeted one-shot deltas. The first two tests must include:

```python
class SkillCycleTests(SkillQueueCastTests):
    def test_next_tick_activates_every_cast_in_order(self):
        engine.use_skill('algo_top')
        engine.use_skill('stealth')
report = engine.tick_one_round()
        self.assertEqual(report['skills_activated'],
                         ['algo_top', 'stealth'])
        self.assertEqual(engine.player.skill_queue, [])
        self.assertEqual([(x.skill_id, x.remaining_ticks)
                          for x in engine.player.active_skill_effects],
                         [('stealth', 1)])
    def test_duration_two_never_outlives_cooldown(self):
        engine.use_skill('stealth')
        for expected_remaining in (1, 0):
            engine.tick_one_round()
            current = [x for x in engine.player.active_skill_effects
                       if x.skill_id == 'stealth']
            self.assertEqual(current[0].remaining_ticks if current else 0,
                             expected_remaining)
            self.assertTrue(all(engine.player.skill_cooldowns.get(x.skill_id, 0) > 0
                                for x in current))
```

Initialize `report['skills_activated']` to an empty list in the report literal so game-over/no-cast ticks have a stable schema, then overwrite it with the FIFO IDs after activation.

Use isolated fixed-seed copies with random event probabilities set to zero for numeric comparisons. Add this equality boundary and one-shot check (import `patch`, `replace` and `data`):

```python
def test_duration_equal_cooldown_expires_together(self):
    equal = replace(data.SKILLS['stealth'], cooldown=2, duration=2)
    with patch.dict(data.SKILLS, {'stealth': equal}):
        engine.use_skill('stealth')
        for _ in range(2):
            engine.tick_one_round()
            self.assertTrue(all(
                engine.player.skill_cooldowns.get(x.skill_id, 0) > 0
                for x in engine.player.active_skill_effects))
        self.assertNotIn('stealth', engine.player.skill_cooldowns)
        self.assertFalse(engine.player.active_skill_effects)

def test_global_instant_delta_only_first_tick(self):
    engine.player.unlocked_skills.add('open_bait')
    engine.use_skill('open_bait')
    first = engine.tick_one_round()
    second = engine.tick_one_round()
    self.assertEqual(first['suspicion_breakdown']['skill'], 8.0)
    self.assertEqual(second['suspicion_breakdown'].get('skill', 0.0), 0.0)

def test_targeted_delta_counts_distinct_targets(self):
    for n in (1, 2):
        with self.subTest(targets=n):
            engine.init_game(seed=41)
            engine.player.unlocked_skills.add('open_bait')
            codes = [c.config.code for c in engine.player_countries
                     if c.unlocked][:n]
            self.assertEqual(len(codes), n)
            self.assertTrue(engine.use_skill('open_bait', codes + codes[:1]))
            report = engine.tick_one_round()
            self.assertEqual(report['suspicion_breakdown']['skill'], 8.0 * n)
```

For same-country stacking, isolate the first-cycle download equation from later events. On two identical seed-41 games, set all countries other than the same single unlocked test country to locked, set `TUNE['growth_network']=0` and `TUNE['growth_base']` to a known positive value, patch `onboarding.try_unlock` to return False, then compare that country's first-tick `download_growth`. Global `push_song` + `algo_top` must equal baseline × `1.10 × 1.30` within `assertAlmostEqual` tolerance. Separately queue `anon_cdn`, tick three times, and assert active remaining values `2, 1, 0` after each tick; on each active tick its cooldown must stay positive.

Add a targeted multiplier test using two otherwise identical unlocked countries with equalized configuration inputs: cast `algo_top` at one code, run a no-event tick, and assert only that code receives the `1.30` factor while the control country stays at baseline. This is distinct from the targeted one-shot-delta test and proves the per-country selector.
- [ ] **Step 2: Confirm red.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillCycleTests -v`. Expected: old tick consumes one skill and has no active list/report key.
- [ ] **Step 3: Add pure per-country aggregation and lifecycle helpers** in `skill_state.py`:

```python
def applies(active, code):
    return not active.targets or code in active.targets

def modifiers(active_effects, code):
    values = dict(downloads_mult=1.0, suspicion_mult=1.0,
                  compute_mult=1.0, stealth_ratio_bonus=0.0,
                  stealth_ratio_mult=1.0)
    for active in active_effects:
        if not applies(active, code):
            continue
        skill = SKILLS[active.skill_id]
        values['downloads_mult'] *= skill.downloads_mult
        values['suspicion_mult'] *= skill.suspicion_mult
        values['compute_mult'] *= skill.compute_mult
        values['stealth_ratio_bonus'] += skill.stealth_ratio_bonus
        values['stealth_ratio_mult'] *= skill.stealth_ratio_mult
    return values

def instant_deltas(new_casts):
    return (sum(SKILLS[c.skill_id].compute_delta *
                max(1, len(c.targets)) for c in new_casts),
            sum(SKILLS[c.skill_id].suspicion_delta *
                max(1, len(c.targets)) for c in new_casts))
```

- [ ] **Step 4: Replace the one-slot tick path.** After the game-over return but **before** `tick_count += 1`, reject a retired explicit `skill_in_use` argument and preflight every stable active item: `remaining_ticks` is a positive non-bool integer strictly below the skill's declared duration, its cooldown is a positive finite number, and `remaining_ticks <= cooldown`. Also preflight each queued item against the skill table and its positive cooldown. Reject duplicate IDs within either list or across them. This ensures an impossible state cannot partially advance a turn. Then drain the ordered queue once and create `ActiveSkill(id, targets, SKILLS[id].duration)` for every cast. Remove the single-skill scalar block at `engine.py:281-313` and use the following skeleton; keep unchanged technology/event equations around it:

```python
if skill_in_use is not None:
    raise ValueError('explicit skill tick path is retired')
validate_live_skill_state(player.skill_queue, player.active_skill_effects,
                          player.skill_cooldowns)
new_casts = list(player.skill_queue)
player.skill_queue.clear()
player.active_skill_effects.extend(
    ActiveSkill(x.skill_id, x.targets, SKILLS[x.skill_id].duration)
    for x in new_casts)
report['skills_activated'] = [x.skill_id for x in new_casts]
instant_compute, instant_suspicion = instant_deltas(new_casts)
```

Implement `validate_live_skill_state` in `skill_state.py` with explicit checks, and log before rejecting so a corrupt runtime transition leaves a diagnostic:

```python
import logging
import math

LOGGER = logging.getLogger(__name__)

def validate_live_skill_state(queue, active, cooldowns):
    queued_ids = [x.skill_id for x in queue]
    active_ids = [x.skill_id for x in active]
    ids = queued_ids + active_ids
    bad = (
        len(ids) != len(set(ids))
        or any(sid not in SKILLS for sid in ids)
        or any(type(cooldowns.get(sid)) not in (int, float)
               or not math.isfinite(cooldowns[sid])
               or cooldowns[sid] <= 0 for sid in ids)
        or any(type(x.remaining_ticks) is not int
               or not 1 <= x.remaining_ticks < SKILLS[x.skill_id].duration
               or x.remaining_ticks > cooldowns[x.skill_id] for x in active)
    )
    if bad:
        LOGGER.error('invalid live skill state: queue=%r active=%r',
                     queue, active)
        raise ValueError('invalid live skill state')
```

The test suite also creates malformed in-memory states for duplicate IDs, `remaining_ticks == duration` and `remaining_ticks > cooldown`, calls `tick_one_round`, and asserts the entire player/country/RNG snapshot is unchanged.

At each stage-1/2 country loop set `m = modifiers(player.active_skill_effects, cfg.code)`; replace `skill_dl_mult`/`skill_suspicion_mult`/`skill_compute_mult`/`skill_stealth_bonus`/`skill_stealth_mult` with their `m` values. Remove per-country `skill_compute_bonus` and `skill_suspicion_delta` additions. After recurring suspicion uses `soft_cap_suspicion(total_suspicion)`, apply the chosen once-only deltas and trace:

```python
player.compute = max(0.0, player.compute + total_stolen
                     + instant_compute - report['maintenance_fee'])
_sus('steal', total_suspicion)
_sus('skill', instant_suspicion)
player.suspicion = max(0.0, min(
    100.0, player.suspicion + total_suspicion + instant_suspicion))
report['suspicion_gain'] = total_suspicion + instant_suspicion
```

At current stage 5, decrement active remaining and cooldown together and remove expired active before UI-visible return. The entry preflight plus `duration <= cooldown` guarantee the residual invariant; assert it in tests and raise only if an unforeseen programmer error breaks it:

```python
for active in player.active_skill_effects:
    active.remaining_ticks -= 1
player.active_skill_effects = [
    x for x in player.active_skill_effects if x.remaining_ticks > 0]
player.skill_cooldowns = {
    sid: left - 1 for sid, left in player.skill_cooldowns.items()
    if left > 1}
if any(player.skill_cooldowns.get(x.skill_id, 0) <= 0
       for x in player.active_skill_effects):
    raise ValueError('active skill outlived cooldown')
```
- [ ] **Step 5: Green, regression, commit.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillCycleTests -v` and `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_edge_cases.py`. Expected: all new tests and 16/16 edge tests pass. Commit only Task 3 files with `git commit -m "feat: settle queued skills with persistent duration"`, then two-stage review.

### Task 4: Persist queue/active state in v6, migrate real v5 shape, roll back bad loads

**Files:** Modify `demo/save_manager.py:52,150-200,223-312,371-507`, `demo/test_locked_country_economy.py:188-207`, `demo/test_intro_split.py:104-148`, and `demo/test_skill_queue_effects.py`.

- [ ] **Step 1: Add failing v5/v6 save tests.** Build a v5-shaped dictionary independently of the new saver, with its mandatory fields and no v6 keys:

```python
import json
import os
import tempfile
from unittest.mock import patch
import save_manager

def v5_fixture():
    p = engine.player
    return {
        'version': 5,
        'player': {
            'compute': p.compute, 'suspicion': p.suspicion,
            'tick_count': p.tick_count, 'start_year': p.start_year,
            'start_month': p.start_month,
            'skill_cooldowns': dict(p.skill_cooldowns),
            'unlocked_skills': sorted(p.unlocked_skills),
        },
        'tech': {
            't0_unlocked': dict(p.tech.t0_unlocked),
            'branch_levels': dict(p.tech.branch_levels),
            'chosen_branch': dict(p.tech.chosen_branch),
        },
        'countries': [
            {'code': c.config.code, 'unlocked': c.unlocked,
             'downloads_m': c.downloads_m,
             'current_block_intensity': c.current_block_intensity,
             'block_budget_remaining': c.block_budget_remaining}
            for c in engine.player_countries
        ],
    }

class SkillSaveTests(SkillQueueCastTests):
    def test_v5_migration_gets_empty_skill_state(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'v5.json')
            with open(path, 'w', encoding='utf-8') as stream:
                json.dump(v5_fixture(), stream)
            with patch.object(save_manager, 'CRASH_LOG',
                              os.path.join(root, 'crash.log')):
                self.assertEqual(save_manager.load_ex(path),
                                 (True, save_manager.LOAD_OK))
            self.assertEqual(engine.player.skill_queue, [])
            self.assertEqual(engine.player.active_skill_effects, [])

    def test_v6_roundtrip_keeps_fifo_and_remaining(self):
        engine.use_skill('algo_top')
        engine.use_skill('stealth')
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'slot.json')
            with patch.object(save_manager, 'SAVE_DIR', root), \
                 patch.object(save_manager, 'CRASH_LOG',
                              os.path.join(root, 'crash.log')):
                save_manager.save(path)
                engine.init_game(seed=99)
                self.assertEqual(save_manager.load_ex(path),
                                 (True, save_manager.LOAD_OK))
            self.assertEqual([x.skill_id for x in engine.player.skill_queue],
                             ['algo_top', 'stealth'])
```

Extend the round-trip case by ticking once before a second save, reloading it, and asserting the active state is exactly `[('stealth', 1)]` while `algo_top` is absent (its duration-1 effect has expired). This covers both serialized lists rather than only the queue.

Add this bad-schema rollback test in `SkillSaveTests`; import `random` and `copy`:

```python
def test_bad_v6_queue_rolls_back_without_disk_write(self):
    engine.use_skill('algo_top')
    with tempfile.TemporaryDirectory() as root:
        path = os.path.join(root, 'slot.json')
        with patch.object(save_manager, 'SAVE_DIR', root), \
             patch.object(save_manager, 'CRASH_LOG',
                          os.path.join(root, 'crash.log')):
            save_manager.save(path)
            with open(path, encoding='utf-8') as stream:
                bad = json.load(stream)
            bad['player']['skill_queue'][0]['skill_id'] = 'not-a-skill'
            with open(path, 'w', encoding='utf-8') as stream:
                json.dump(bad, stream)
            with open(path, 'rb') as stream:
                original = stream.read()
            before = (engine.player.tick_count, engine.player.compute,
                      copy.deepcopy(engine.player.skill_queue),
                      random.getstate())
            self.assertEqual(save_manager.load_ex(path),
                             (False, save_manager.LOAD_BAD_SCHEMA))
            self.assertEqual((engine.player.tick_count, engine.player.compute,
                              engine.player.skill_queue, random.getstate()),
                             before)
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), original)
```

Add an active item whose `remaining_ticks` exceeds its cooldown as a second `subTest` using the same isolated file pattern.
- [ ] **Step 2: Confirm red.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillSaveTests -v`. Expected: v5 is rejected by current version gate and queue is absent from saves.
- [ ] **Step 3: Add v6 migration and serial form.** Set `SAVE_VERSION = 6`. Add `_v5_to_v6` to the migration map, using an actual copy rather than mutating the caller:

```python
def _v5_to_v6(d: dict) -> dict:
    result = copy.deepcopy(d)
    ps = result['player']
    ps['skill_queue'] = []
    ps['active_skill_effects'] = []
    result['version'] = 6
    return result

_MIGRATIONS[5] = _v5_to_v6
```

Add `import copy`. In `save`, write `skill_queue` as ordered dictionaries `{'skill_id': x.skill_id, 'targets': list(x.targets)}` and `active_skill_effects` as the same fields plus `'remaining_ticks': x.remaining_ticks`. In `_apply_save`, construct `SkillCast`/`ActiveSkill` after restoring `skill_cooldowns`.
- [ ] **Step 4: Validate before applying and preserve prior state on failure.** Add a `_parse_skill_state(ps, countries)` function returning typed queue/active lists. Reject non-lists, bad item shape, unknown or repeated skill IDs, non-string/duplicate/unknown/locked target codes, non-bool-int remaining outside `1..duration-1`, absent/nonpositive cooldown, `remaining_ticks > cooldown`, or the same ID in queue and active. Call it before `_apply_save` and pass the typed result to the apply phase. Wrap `_apply_save` in the transaction helper specified below; on a caught schema/apply error restore the exact pre-load state and return `LOAD_BAD_SCHEMA`. This replaces the current `engine.init_game()` failure rollback, which otherwise loses the player's pre-load position. Keep the locked-country v5 repair path for both incoming v5 and v6 data by changing the existing `elif v == SAVE_VERSION` condition to `elif v >= 5`; otherwise a dirty native v5 file would escape the old repair on migration. Use this core validation pattern:

```python
def _require_skill_id(item, seen):
    sid = item.get('skill_id')
    if not isinstance(sid, str) or sid not in SKILLS or sid in seen:
        raise TypeError('invalid or duplicate skill id')
    seen.add(sid)
    return sid

def _require_remaining(value, skill, cooldown):
    if (type(value) is not int or not 1 <= value < skill.duration
            or type(cooldown) not in (int, float)
            or not math.isfinite(cooldown) or cooldown < value):
        raise TypeError('invalid active skill remaining/cooldown')
    return value
```

Finish `_parse_skill_state` by checking targets against the saved `countries` list, then instantiate the Task 1 dataclasses. Require both v6 keys to exist and both lists to contain only dictionaries; `_v5_to_v6` supplies them for historical files. For each entry validate `targets` is a list of unique nonempty strings and each target exists and is unlocked in the saved country state. Do **not** re-run the saturation gate during load: a valid queued cast may naturally cross that threshold before saving, and the approved no-refund rule says to preserve it. Each queued and active skill requires a finite positive cooldown. Reject repeated IDs across both lists. Validate the whole list before assigning either field to `engine.player`. Import `copy`, `random`, `balance`, `SKILLS` and the `skill_state` records explicitly.

Use a transaction helper around `_apply_save` rather than an incomplete deep copy. Capture the original `engine.player` and `engine.player_countries` object references (the apply path replaces them before mutation), copies of `engine._counterplay_cooldown`, `engine._counterplay_pending`, `engine._recent_commission_templates`, `balance.TUNE`, `balance.ACTIVE_DIFFICULTY`, `balance.ACTIVE_ORIGIN`, and `random.getstate()`. On failure, restore those exact references/values before logging. Do not restore via `init_game`. Add sentinels for these fields to the rollback test so a bad v6 load proves that game state, RNG, difficulty/origin and internal scheduling all survive unchanged.
- [ ] **Step 5: Update existing historical contracts and green.** Keep `test_locked_country_economy.py` checking `_v4_to_v5` idempotency by computing `intermediate_v5 = _v4_to_v5(copy.deepcopy(old_v4))` and asserting a second call leaves that intermediate unchanged; separately assert `_migrate(old, version)` reaches 6 and `_migrate(migrated, 6)` is idempotent. Update `test_intro_split.py`'s fixed version/string guards to expect 6 and explicitly include `_v5_to_v6` and `_MIGRATIONS[5]` while retaining `intro_seen`. Run:

```powershell
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillSaveTests test_locked_country_economy -v
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_intro_split.py
```

Expected: new save cases pass, locked-country 12 tests pass, intro contract passes, original save bytes unchanged until explicit save. Run `git diff --check`, commit exact Task 4 files with `git commit -m "feat: migrate and persist skill state in save v6"`, then two-stage review.

### Task 5: Display queue/active truthfully in both languages and retire unsupported exact previews

**Files:** Modify `demo/main.py:500-515`, `demo/ui_session.py:350-365`, `demo/ui_hud.py:700-790`, `demo/ui_input.py:178-235,321-375,400-470,566-580`, `demo/ui_drop.py:223-268,346-375`, `demo/i18n.py:490-525,835-865`, `demo/test_topbar_prediction_prefix.py` and `demo/test_skill_queue_effects.py`.

- [ ] **Step 1: Add failing localized UI tests** following the Kivy cleanup pattern in `demo/test_locked_country_economy.py:275-324`. For each language, create a `GameUI` from a seeded game with two queued skills; assert queue text displays both skill names in order and the localized “next cycle” term. After one tick, assert the remaining active skill shows one period and both queued names disappear. Core assertion:

```python
from unittest.mock import patch
from kivy.core.window import Window
import balance
import engine
import i18n
import main

class SkillUiTests(unittest.TestCase):
    def setUp(self):
        balance.apply_difficulty('normal')
        engine.init_game(seed=41)
        engine.player.compute = 1000
        engine.player.unlocked_skills.update({'algo_top', 'stealth'})

    def tearDown(self):
        i18n.set_lang('zh')
        balance.apply_difficulty('normal')

    def _make_game(self):
        patches = [
            patch.object(main.GameUI, '_reschedule_tick'),
            patch.object(main.GameUI, '_reschedule_countdown'),
            patch('cursor_fx.install', return_value=True),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return main.GameUI()

    def _close_game(self, game):
        game.stop_ticking()
        keyboard = game._keyboard
        game._keyboard_closed()
        if keyboard is not None:
            keyboard.release()
        game.commission_bar._unbind_window()
        Window.unbind(on_resize=game._on_window_resize,
                      mouse_pos=game._on_skill_hover)

    def test_queue_and_active_text_bilingual(self):
        for lang, token in (('zh', '下周期'), ('en', 'Next cycle')):
            with self.subTest(lang=lang):
                engine.init_game(seed=41)
                engine.player.compute = 1000
                engine.player.unlocked_skills.update({'algo_top', 'stealth'})
                i18n.set_lang(lang)
                self.assertTrue(engine.use_skill('algo_top'))
                self.assertTrue(engine.use_skill('stealth'))
                game = self._make_game()
                try:
                    game.refresh_all()
                    text = game.skill_state_label.text
                    self.assertIn(token, text)
                    self.assertLess(text.index(game._skill_name('algo_top')),
                                    text.index(game._skill_name('stealth')))
                    engine.tick_one_round(auto_choice=False)
                    game.refresh_all()
                    self.assertEqual(
                        [(x.skill_id, x.remaining_ticks)
                         for x in engine.player.active_skill_effects],
                        [('stealth', 1)])
                    self.assertNotIn(token, game.skill_state_label.text)
                    self.assertIn('1', game.skill_state_label.text)
                finally:
                    self._close_game(game)
```

Test that hover/drop/topbar text does not show an exact future download/compute/suspicion delta while queued or active effects exist. Revise `test_topbar_prediction_prefix.py` to assert historical arrows remain, cyan future values and calls to `preview_next_cycle` are gone, and use the same cleanup helper pattern so Kivy bindings do not leak between tests.

Add one UI reconstruction test: save and reload a queue with the Task 4 temporary-path helper, create a fresh `GameUI`, and assert status text comes from the restored engine queue. Toggle `game.paused` and call `refresh_all` to prove pause/resume does not consume or duplicate state. Call `restart_game` under patched scheduling and assert both status lists clear. This covers save/re-entry, pause and restart without introducing UI-owned state.
- [ ] **Step 2: Confirm red.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillUiTests test_topbar_prediction_prefix -v`. Expected: missing `skill_state_label` and old numeric predictions.
- [ ] **Step 3: Add one compact HUD state row and translations.** In `ui_hud.py` add a labeled `HudBox` above the skill bar, using existing `Label` and `HudBox` rather than a new art system:

```python
self.skill_state_hud = HudBox(anchor='bc')
self.skill_state_hud._bot_inset = 0
self.skill_state_label = Label(text='', size_hint=(1, None),
                               height=32, halign='center',
                               valign='middle', font_size=U.FS_BODY)
self.skill_state_label.text_size = (650, 32)
self.skill_state_hud.add_widget(self.skill_state_label)
self.skill_state_hud.content_size(660, 34)
stage.add_widget(self.skill_state_hud)
self.skill_pv_hud._bot_inset = 50
```

In `i18n.py` add these same keys to both language maps:

```python
# zh
'sk_queue_next': '下周期结算', 'sk_active_left': '剩余{n}周期',
'sk_active_left_one': '剩余1周期',
'sk_active_now': '持续中', 'sk_more': '另有{n}项',
'sk_fail_cooldown': '技能冷却中', 'sk_fail_target': '目标不可投放',
'sk_preview_static': '实际收益受连招与事件影响',
# en
'sk_queue_next': 'Next cycle', 'sk_active_left': '{n} cycles left',
'sk_active_left_one': '1 cycle left',
'sk_active_now': 'Active', 'sk_more': '{n} more',
'sk_fail_cooldown': 'Skill cooling down', 'sk_fail_target': 'Invalid target',
'sk_preview_static': 'Actual gain depends on combos and events',
```

Use the engine lists in `refresh_all` to compose ordered status text. A narrow helper keeps any list to the first three names plus a count, avoiding clipped text:

```python
def _skill_state_text(self):
    p = engine.player
    queued = [self._skill_name(x.skill_id) for x in p.skill_queue]
    active = [f"{self._skill_name(x.skill_id)} "
              f"{(t('sk_active_left_one') if x.remaining_ticks == 1 else t('sk_active_left').format(n=x.remaining_ticks))}"
              for x in p.active_skill_effects]
    def compact(items):
        shown = ' · '.join(items[:3])
        extra = len(items) - 3
        return shown + (f" · {t('sk_more').format(n=extra)}"
                        if extra > 0 else '')
    parts = []
    if queued:
        parts.append(f"{t('sk_queue_next')}: {compact(queued)}")
    if active:
        parts.append(f"{t('sk_active_now')}: {compact(active)}")
    return '  |  '.join(parts)
```

The status box occupies the map-stage bottom edge; the hover preview moves to inset 50 so the two HUDs never overlap. In `refresh_all` assign a local `state_text = self._skill_state_text()` after refreshing skill cards, set the label text, and set `self.skill_state_hud.opacity = 1 if state_text else 0` so an empty frame does not cover the map. Delete `selected_skill` initialization/reset from `main.py` and `ui_session.py` as well as all assignments in `ui_drop.py`; it must not survive as an unused compatibility field.
- [ ] **Step 4: Remove double-source and precise unsupported promises.** In `GameUI.game_tick` call `engine.tick_one_round(auto_choice=False, dt_seconds=self._tick_interval())`. In `_confirm_drop`/`_cast_skill_direct`, keep animation and success notice, but do not set `selected_skill`; on failure translate `engine.skill_cast_reason` rather than always saying “no compute”. Replace hover/card and drop-preview numerical outcome rows with deterministic cost/CD/description and `sk_preview_static`; keep target eligibility warning. In `_refresh_spark_deltas` retain historical trend arrows but remove `preview_next_cycle()` and the cyan future-number suffix. Exact replacement patterns:

```python
report = engine.tick_one_round(
    auto_choice=False, dt_seconds=self._tick_interval())

reason = engine.skill_cast_reason(sid, None)
message_key = {
    'cooldown': 'sk_fail_cooldown',
    'invalid_target': 'sk_fail_target',
    'saturated': 'reason_saturated',
    'no_compute': 'sk_state_no_compute',
    'locked': 'sk_state_lock',
    'game_over': 'sk_pv_game_over',
}.get(reason, 'sk_fail_target')
self._notify(t(message_key))

cost = engine.skill_cost_for(sid, len(self._preview_targets(sid)))
static_text = (f"{t('sk_sort_cost')} {cost:.0f} · "
               f"{t('sk_sort_cd')} {data.SKILLS[sid].cooldown} · "
               f"{t('sk_preview_static')}")
```

Use `static_text` for skill hover/card text instead of the five exact outcome chips; in `_show_drop_preview` pass an empty `ests` list and only deterministic `effects`/availability `warn` to the existing `DropPreview.update`. In `_refresh_spark_deltas` finish each suffix after its historical arrow, without calling `preview_next_cycle`. Add a direct test asserting `engine.preview_skill` is not invoked by these UI surfaces while queue/active is present.

After the UI tests, run `rg -n "pending_skill|selected_skill|tick_one_round\\(.*skill_in_use" demo -g "*.py"`. Expected: no executable references; comments/docstrings should also be updated to the queue vocabulary. Existing engine-only tests of `preview_next_cycle` may remain because this package removes unsupported UI promises, not the internal diagnostic API.
- [ ] **Step 5: Green, visual smoke, commit.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.SkillUiTests test_topbar_prediction_prefix -v` and `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_v4_app.py`. Expected: localized state assertions and 57/57 screens pass. Inspect 1280×720 and 1680×980 queue/full-active screenshots if a display is available; mark visual inspection unverified if headless only. Commit exact Task 5 files with `git commit -m "fix: expose queued skills and remove unreliable predictions"` after `git diff --check`; two-stage review.

### Task 6: Add a real combo simulation probe and produce a release-risk report

**Files:** Modify `demo/balance_sim.py:65-185` and measured line whitelist in `demo/verify_tables.py:620-655` only if its guard fails. Create `docs/superpowers/verification/2026-09-18-skill-queue-effects.md`.

- [ ] **Step 1: Add a failing combo test** to `demo/test_skill_queue_effects.py`. Patch the auto player's spend/tech decisions if needed, force both starter skills unlocked and enough compute, call `auto_play(strategy='combo')` once, and assert two different IDs were queued. Use this core test:

```python
import balance_sim

class ComboSimulationTests(unittest.TestCase):
    def test_combo_strategy_queues_two_skills(self):
        engine.init_game(seed=61)
        engine.player.compute = 1000
        engine.player.unlocked_skills.update({'push_song', 'algo_top'})
        with patch.object(engine, 'unlock_t0', return_value=False), \
             patch.object(engine, 'upgrade_branch', return_value=False):
            balance_sim.auto_play(strategy='combo')
        ids = [x.skill_id for x in engine.player.skill_queue]
        self.assertIn('push_song', ids)
        self.assertIn('algo_top', ids)
```

- [ ] **Step 2: Confirm red.** Run `& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects.ComboSimulationTests -v`. Expected: `combo` currently performs no deliberate two-skill cast.
- [ ] **Step 3: Add the probe without altering the 3×3 historical matrix dimensions.** In `balance_sim.auto_play` after the existing decisions, when `strategy == 'combo'` and both skills are unlocked, neither is queued/active/on cooldown, and both are jointly affordable, call `engine.use_skill('push_song')` then `engine.use_skill('algo_top')`. Add `combo` to standalone CLI `--strategy` choices and `STRATEGY_CRISIS_CAPABLE`, but keep `MATRIX_STRATEGIES = ('default', 'compliance', 'afk')` unchanged. In `simulate` count a combo activation when one `report['skills_activated']` contains both IDs, store `combo_pair_activations` in `insp`/`_result` outside `REGRESSION_FIELDS`, and print its total for standalone `--strategy combo` summaries. This observes real FIFO settlement rather than merely detecting that the strategy label existed.
- [ ] **Step 4: Run full technical regression and isolated matrices.** Set `KIVY_NO_ARGS=1`, `KIVY_NO_FILELOG=1`, `PYTHONDONTWRITEBYTECODE=1` and `PYTHONIOENCODING=utf-8`. From `demo/` run every exact command below with the user-designated interpreter:

```powershell
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' -m unittest test_skill_queue_effects -v
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' verify_tables.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' verify_tech_tree.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_edge_cases.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_build.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_intro_split.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' test_v4_app.py
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' balance_sim.py --strategy combo --seeds 30 --ticks 200
& 'C:\Users\tianm\AppData\Local\Programs\Python\Python312\python.exe' balance_sim.py --matrix --seeds 200 --ticks 200 --matrix-output-dir 'C:\Users\tianm\WorkBuddy\workbuddy\game_optimization\.workbuddy\skill-queue-matrix-output'
```

Before running, verify the requested output directory does not exist; never point to `tools/data`. If it already exists, choose a new explicitly named sibling instead of deleting or overwriting it. Compare to `.workbuddy/locked-country-matrix-output/playtest_baseline.json` and re-hash tracked `tools/data/playtest_baseline.json`. If the frozen line guard fails, read its measured count, adjust only touched-file whitelist entries to those counts with a reason comment, then rerun 38/38; never increase unrelated limits. Any regression failure stops this task for debugging, not release.
- [ ] **Step 5: Document evidence and commit.** In the new verification Markdown record every command/exit status, old/new nine-combination outcome and bug/review deltas, combo probe counts, first-crisis and AFK risks, old baseline SHA-256, any Kivy visual checks not performed, and no-exe/no-real-save boundary. Run `git diff --check`, inspect `git status --short` and commit only Task 6 files with `git commit -m "test: document skill combo regression and balance drift"`. Commission a final overall review; do not describe a changed matrix as “balanced” without the separate G2 tuning package.

## Final handoff gate

The total manager verifies every checkbox against the approved spec and reads the actual diff. A fresh independent reviewer checks specification compliance, then code quality, with any Important/Critical finding sent back to the owner and re-reviewed. Only after fresh full regression, clean `git diff --check`, clean branch status and the historical baseline hash check may the team call **this package** complete. Merge, push, PR, packaging or public release each require a separate user decision; fixing the skill contract does not clear the pre-existing first-crisis/AFK balance risks or replace human playtesting.
