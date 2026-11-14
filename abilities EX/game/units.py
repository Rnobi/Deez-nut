import random
from dataclasses import dataclass, replace

from . import config
from .packs import DEFAULT_PACK

# the pack the game draws units (and items) from
PACK = DEFAULT_PACK
# (name, attack, health) of every unit in the pack, all tiers
ROSTER = [unit for tier in PACK.units.values() for unit in tier]


@dataclass
class Unit:
    name: str
    attack: int
    health: int
    level: int = 1
    tier: int = 1
    armor: int = 0  # damage taken per hit is reduced by this (never below 1)
    poison: bool = False  # whatever this unit damages faints
    temp_attack: int = 0  # buffs that only last until the end of the next battle
    temp_health: int = 0
    perks: tuple = ()  # extra abilities handed out by items (see abilities.PERKS)

    def copy(self):
        return replace(self)

    def battle_copy(self):
        """a copy for fighting: temporary buffs are folded into the stats"""
        c = replace(self)
        c.attack += c.temp_attack
        c.health += c.temp_health
        c.temp_attack = c.temp_health = 0
        return c

    @property
    def sell_value(self):
        return self.level

    def can_merge(self, other):
        return self.name == other.name and self.level < config.MAX_LEVEL and self.level == other.level

    def merge(self, other):
        """combine two copies of the same unit: keep the best stats, +whatever"""
        self.attack = max(self.attack, other.attack) + 2
        self.health = max(self.health, other.health) + 2
        self.level += 1
        self.armor = max(self.armor, other.armor)
        self.temp_attack = max(self.temp_attack, other.temp_attack)
        self.temp_health = max(self.temp_health, other.temp_health)
        self.perks = tuple(dict.fromkeys(self.perks + other.perks))


def random_unit(rng, bonus=0, turn=1, pack=PACK, tier_boost=0):
    """a random unit from the tiers unlocked on this turn (tier_boost peeks further ahead)"""
    top = min(config.max_tier(turn) + tier_boost, max(pack.units))
    tier, name, atk, hp = rng.choice(pack.units_up_to(top))
    return Unit(name, atk + bonus, hp + bonus, tier=tier)
