"""rng'd enemy teams that scale with the turn number and the difficulty"""
from . import config
from .units import random_unit


def generate_team(turn, rng, difficulty=None):
    diff = difficulty or config.DIFFICULTIES[0]
    size = min(config.TEAM_SIZE, diff.min_size + (turn + 1) // 2)
    bonus = config.stat_bonus(turn, diff.bonus_every, diff.bonus_step)
    team = []
    for _ in range(size):
        unit = random_unit(rng, bonus, turn, tier_boost=diff.tier_boost)
        # random extra stats
        unit.attack += rng.randint(0, turn // diff.extra_div)
        unit.health += rng.randint(0, turn // diff.extra_div)
        team.append(unit)
    return team
