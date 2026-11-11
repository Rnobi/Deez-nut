import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import config
from game.battle import Battle
from game.core import GameState
from game.opponents import generate_team
from game.pets import Pet


class BattleTests(unittest.TestCase):
    def test_random_battles_terminate(self):
        rng = random.Random(1)
        for turn in range(1, 25):
            for _ in range(50):
                a = generate_team(turn, rng)
                b = generate_team(turn, rng)
                self.assertIn(Battle(a, b).run_to_end(), ("win", "lose", "draw"))

    def test_stronger_team_wins(self):
        self.assertEqual(Battle([Pet("A", 5, 5)], [Pet("B", 1, 1)]).run_to_end(), "win")
        self.assertEqual(Battle([Pet("A", 1, 1)], [Pet("B", 5, 5)]).run_to_end(), "lose")

    def test_draw(self):
        self.assertEqual(Battle([Pet("A", 2, 2)], [Pet("B", 2, 2)]).run_to_end(), "draw")

    def test_input_teams_not_mutated(self):
        team = [Pet("A", 2, 2)]
        Battle(team, [Pet("B", 9, 9)]).run_to_end()
        self.assertEqual(team[0].health, 2)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.st = GameState(random.Random(3))

    def test_buy_sell(self):
        self.assertTrue(self.st.buy(0, 0))
        self.assertEqual(self.st.gold, config.STARTING_GOLD - config.PET_COST)
        self.assertIsNone(self.st.shop[0])
        self.assertTrue(self.st.sell(0))
        self.assertIsNone(self.st.team[0])

    def test_cannot_overspend(self):
        for j in range(3):
            self.st.buy(j, j)
        self.assertEqual(self.st.gold, 1)
        self.st.shop[0] = Pet("X", 1, 1)
        self.assertFalse(self.st.buy(0, 3))

    def test_merge(self):
        self.st.team[0] = Pet("Ant", 2, 2)
        self.st.shop[0] = Pet("Ant", 2, 2)
        self.assertTrue(self.st.buy(0, 0))
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health, self.st.team[0].level), (3, 3, 2))

    def test_no_merge_different_pets(self):
        self.st.team[0] = Pet("Ant", 2, 2)
        self.st.shop[0] = Pet("Pig", 2, 4)
        self.assertFalse(self.st.buy(0, 0))
        self.assertEqual(self.st.gold, config.STARTING_GOLD)

    def test_reroll_costs_gold(self):
        self.assertTrue(self.st.reroll())
        self.assertEqual(self.st.gold, config.STARTING_GOLD - config.REROLL_COST)

    def test_lives_and_game_over(self):
        for _ in range(config.STARTING_LIVES):
            self.st.finish_battle("lose")
        self.assertEqual(self.st.status, "lost")

    def test_victory(self):
        for _ in range(config.WINS_TO_WIN):
            self.st.finish_battle("win")
        self.assertEqual(self.st.status, "won")

    def test_new_turn_resets_gold(self):
        self.st.buy(0, 0)
        self.st.finish_battle("draw")
        self.assertEqual(self.st.gold, config.STARTING_GOLD)
        self.assertEqual(self.st.turn, 2)


if __name__ == "__main__":
    unittest.main()
