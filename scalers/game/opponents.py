"""rng'd enemy teams that scale with the turn number and the difficulty"""
from . import config
from .units import random_unit


def level_budget(turn, team_size):
    """how many levels an enemy team has in total: max(team size, 1 + (turn + 2) // 2).
    every unit starts at level 1, so a team never has fewer levels than units; the rest are
    spread over the team (see spread_levels). the same formula for every difficulty"""
    return max(team_size, 1 + (turn + 2) // 2)


def spread_levels(team, turn, rng):
    """hand out the team's spare levels at random. each one levels up a unit that isn't at MAX_LEVEL
    the way a merge does (+2/+2, and its ability scales with the level). stops early when every unit is maxed"""
    spare = level_budget(turn, len(team)) - len(team)
    while spare > 0:
        open_units = [u for u in team if u.level < config.MAX_LEVEL]
        if not open_units:
            break
        unit = rng.choice(open_units)
        unit.attack += 2
        unit.health += 2
        unit.level += 1
        spare -= 1


def generate_team(turn, rng, difficulty=None, endless=False):
    team = []
    if endless:
        size = turn + 1
        for _ in range(size):
                unit = random_unit(rng, 0, turn)
                unit.attack += turn // 3
                unit.health += turn // 3
                team.append(unit)
        spread_levels(team, turn, rng)  # the budget is the team size here, so everyone stays level 1
        return team
    diff = difficulty or config.DIFFICULTIES[0]
    size = min(config.TEAM_SIZE, diff.min_size + (turn) // 2)
    bonus = config.stat_bonus(turn, diff.bonus_every, diff.bonus_step)
    for _ in range(size):
        unit = random_unit(rng, bonus, turn, tier_boost=diff.tier_boost)
        # random extra stats
        unit.attack += rng.randint(0, turn // diff.extra_div)
        unit.health += rng.randint(0, turn // diff.extra_div)
        team.append(unit)
    spread_levels(team, turn, rng)
    return team
