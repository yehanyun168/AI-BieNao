import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from data import SKILLS
from skill_state import ActiveSkill, SkillCast, validate_skill_table


class SkillTimingTests(unittest.TestCase):
    def test_import_rejects_invalid_product_skill_table(self):
        script = """
from dataclasses import replace

import data

data.SKILLS["stealth"] = replace(
    data.SKILLS["stealth"], duration=3, cooldown=2
)
import skill_state
"""

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "ValueError: invalid skill duration/cooldown: stealth",
            result.stderr,
        )

    def test_product_skill_table_is_valid(self):
        validate_skill_table()

    def test_duration_may_equal_cooldown(self):
        skills = dict(SKILLS)
        skills["stealth"] = replace(
            skills["stealth"], duration=2, cooldown=2
        )

        validate_skill_table(skills)

    def test_invalid_duration_and_cooldown_are_rejected(self):
        invalid_timings = (
            (3, 2),
            (0, 2),
            (True, 2),
            (1.5, 2),
            (1, False),
        )

        for duration, cooldown in invalid_timings:
            with self.subTest(duration=duration, cooldown=cooldown):
                skills = dict(SKILLS)
                skills["stealth"] = replace(
                    skills["stealth"],
                    duration=duration,
                    cooldown=cooldown,
                )

                with self.assertRaisesRegex(
                    ValueError,
                    r"^invalid skill duration/cooldown: stealth$",
                ):
                    validate_skill_table(skills)


class SkillStateTests(unittest.TestCase):
    def test_skill_cast_defaults_to_empty_tuple_and_is_frozen(self):
        cast = SkillCast("stealth")

        self.assertEqual(cast.targets, ())
        with self.assertRaises(FrozenInstanceError):
            cast.skill_id = "push_song"

    def test_active_skill_tracks_mutable_remaining_ticks(self):
        active = ActiveSkill("stealth", ("CN",), remaining_ticks=2)

        active.remaining_ticks -= 1

        self.assertEqual(active.remaining_ticks, 1)
        self.assertIsInstance(active.targets, tuple)


if __name__ == "__main__":
    unittest.main()
