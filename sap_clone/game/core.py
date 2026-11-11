"""game state and shop rules"""
import random

from . import config
from .pets import random_pet


class GameState:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.turn = 0
        self.lives = config.STARTING_LIVES
        self.wins = 0
        self.gold = 0
        self.team = [None] * config.TEAM_SIZE  # index 0 = front
        self.shop = []
        self.status = "shop"  # shop/won/lost
        self.message = ""
        self.start_turn()

    # turn structure -
    def start_turn(self):
        self.turn += 1
        self.gold = config.STARTING_GOLD
        self.roll_shop()

    def roll_shop(self):
        bonus = config.stat_bonus(self.turn)
        self.shop = [random_pet(self.rng, bonus) for _ in range(config.SHOP_SIZE)]

    def battle_team(self):
        return [p.copy() for p in self.team if p]

    def finish_battle(self, result):
        if result == "win":
            self.wins += 1
            self.message = "You won the last battle."
        elif result == "lose":
            self.lives -= 1
            self.message = "You lost the last battle (-1 life)."
        else:
            self.message = "The last battle was a draw."
        if self.wins >= config.WINS_TO_WIN:
            self.status = "won"
        elif self.lives <= 0:
            self.status = "lost"
        else:
            self.start_turn()

    # shop actions -
    def reroll(self):
        if self.gold < config.REROLL_COST:
            self.message = "Not enough gold to reroll."
            return False
        self.gold -= config.REROLL_COST
        self.roll_shop()
        self.message = ""
        return True

    def buy(self, shop_idx, slot):
        pet = self.shop[shop_idx]
        if pet is None:
            return False
        if self.gold < config.PET_COST:
            self.message = "Not enough gold."
            return False
        target = self.team[slot]
        if target is None:
            self.team[slot] = pet
            self.message = f"Bought {pet.name}."
        elif target.can_merge(pet):
            target.merge(pet)
            self.message = f"{target.name} merged! Now level {target.level}."
        else:
            self.message = "That slot is taken (drop onto the same level pet to merge)."
            return False
        self.gold -= config.PET_COST
        self.shop[shop_idx] = None
        return True

    def sell(self, slot):
        pet = self.team[slot]
        if pet is None:
            return False
        self.gold += pet.sell_value
        self.team[slot] = None
        self.message = f"Sold {pet.name} for {pet.sell_value}g."
        return True

    def swap(self, a, b):
        self.team[a], self.team[b] = self.team[b], self.team[a]

    def merge_team(self, src, dst):
        """merge the pet in slot src into the pet in slot dst (same name only),
        returns True if a merge happened; the src slot is then emptied
        """
        a, b = self.team[src], self.team[dst]
        if src == dst or a is None or b is None or not b.can_merge(a):
            return False
        b.merge(a)
        self.team[src] = None
        self.message = f"{b.name} merged! Now level {b.level}."
        return True