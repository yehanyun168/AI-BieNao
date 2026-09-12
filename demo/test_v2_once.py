"""V2 选择事件在同一局中最多出现一次。"""

import random
import tempfile
import unittest
from unittest.mock import patch

import engine
import save_manager
import v2_events
from tech_tree import PlayerTech


class V2OnceTests(unittest.TestCase):
    def test_seen_event_is_excluded_from_candidate_pool(self):
        event = v2_events.V2Event(
            id="seen_event", title="已出现", flavor="", category="narrative",
            icon="?", weight=10, cooldown=30)
        ctx = {
            "penetration": 0.5,
            "suspicion": 50,
            "tech": PlayerTech(),
            "countries": {},
            "seen_events": {event.id},
        }

        with patch.object(v2_events, "EVENTS", [event]):
            picked = v2_events.pick_event(ctx, {}, random.Random(1))

        self.assertIsNone(picked)

    def test_unseen_event_remains_eligible(self):
        event = v2_events.V2Event(
            id="new_event", title="未出现", flavor="", category="narrative",
            icon="?", weight=10, cooldown=30)
        ctx = {
            "penetration": 0.5, "suspicion": 50, "tech": PlayerTech(),
            "countries": {}, "seen_events": set(),
        }

        with patch.object(v2_events, "EVENTS", [event]):
            picked = v2_events.pick_event(ctx, {}, random.Random(1))

        self.assertIs(picked, event)

    def test_seen_events_survive_save_and_load(self):
        engine.init_game()
        engine.player.v2_seen = {"persisted_event"}

        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}\\slot.json"
            save_manager.save(path)
            engine.player.v2_seen.clear()
            self.assertTrue(save_manager.load(path))

        self.assertEqual(engine.player.v2_seen, {"persisted_event"})


if __name__ == "__main__":
    unittest.main()
