import random, sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mafia_app.mysite.game_logic import *


class T(unittest.TestCase):
    def test_winner(self):
        self.assertEqual(decide_winner(0, 3), "CITIZENS")
        self.assertEqual(decide_winner(1, 1), "MAFIA")
        self.assertEqual(decide_winner(2, 1), "MAFIA")
        self.assertIsNone(decide_winner(1, 2))
        self.assertEqual(decide_winner(0, 0), "CITIZENS")

    def test_kill_target(self):
        self.assertIsNone(pick_kill_target([]))
        self.assertEqual(pick_kill_target([5, 5, 7]), 5)
        self.assertIn(pick_kill_target([5, 7], random.Random(1)), (5, 7))

    def test_votes(self):
        c, l = tally_votes([(1, 3), (2, 3), (3, 1)])
        self.assertEqual(c, {3: 2, 1: 1}); self.assertEqual(l, [3])
        self.assertEqual(tally_votes([(1, 2), (2, 1)])[1].__len__(), 2)
        self.assertEqual(tally_votes([])[1], [])

    def test_roles(self):
        self.assertIsNone(validate_role_counts(4, 1, 1, 1))
        self.assertIsNotNone(validate_role_counts(4, 2, 1, 1))
        self.assertIsNotNone(validate_role_counts(4, 0, 1, 1))
        self.assertIsNotNone(validate_role_counts(3, 1, 1, 2))
        self.assertIsNotNone(validate_role_counts(6, 1, -1, 1))

    def test_stats(self):
        self.assertEqual(role_stat_field("commissar"), "detective_games")
        self.assertIsNone(most_played_role({"mafia": 0, "doctor": 0}))
        self.assertEqual(most_played_role({"mafia": 1, "doctor": 3}), "doctor")


if __name__ == "__main__":
    unittest.main()
