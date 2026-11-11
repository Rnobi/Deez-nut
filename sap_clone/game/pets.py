import random
from dataclasses import dataclass, replace

from . import config

# (name, attack, health)
ROSTER = [
    ("Ant", 2, 2),
    ("Beaver", 2, 3),
    ("Cricket", 1, 2),
    ("Duck", 1, 4),
    ("Fish", 3, 2),
    ("Horse", 2, 1),
    ("Mosquito", 3, 1),
    ("Otter", 1, 3),
    ("Pig", 2, 4),
]


@dataclass
class Pet:
    name: str
    attack: int
    health: int
    level: int = 1

    def copy(self):
        return replace(self)

    @property
    def sell_value(self):
        return self.level

    def can_merge(self, other):
        return self.name == other.name and self.level < config.MAX_LEVEL and self.level == other.level

    def merge(self, other):
        """combine two copies of the same pet: keep the best stats, +whatever"""
        self.attack = max(self.attack, other.attack) + 2
        self.health = max(self.health, other.health) + 2
        self.level += 1


def random_pet(rng, bonus=0):
    name, atk, hp = rng.choice(ROSTER)
    return Pet(name, atk + bonus, hp + bonus)
