import unittest
from dataclasses import replace

from data import SKILLS
from skill_state import validate_skill_table


class SkillTimingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
