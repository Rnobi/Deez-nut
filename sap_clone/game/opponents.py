"""rng'd enemy teams that scale with the turn number"""
from . import config
from .pets import random_pet


def generate_team(turn, rng):
    size = min(config.TEAM_SIZE, 1 + (turn + 1) // 2)
    bonus = config.stat_bonus(turn)
    team = []
    for _ in range(size):
        pet = random_pet(rng, bonus)
        # random extra stats
        pet.attack += rng.randint(0, turn // 4)
        pet.health += rng.randint(0, turn // 4)
        team.append(pet)
    return team
