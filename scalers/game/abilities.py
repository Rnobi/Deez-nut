"""unit abilities: a small trigger system.

an ability is (trigger, effect, amount); amount is multiplied by the unit's level.
- new effect: write a function below and add it to EFFECTS
- give a unit an ability: add it to ABILITIES (keyed by unit name)
- PERKS are abilities that an item can hand to a unit (see items.py)
every unit in the pack has an ability
"""
from dataclasses import dataclass

from .units import PACK, Unit

START_OF_TURN = "start_of_turn"  # fires in the shop, front to back, as each new turn begins
START_OF_BATTLE = "start_of_battle"
FAINT = "faint"
SELL = "sell"
LEVEL_UP = "level_up"  # the unit merged or was levelled by an item
FRIEND_BOUGHT = "friend_bought"  # another unit was bought onto your team
FRIEND_AHEAD_ATTACKS = "friend_ahead_attacks"  # the front unit attacked (fires for the unit right behind it)
KNOCK_OUT = "knock_out"  # this unit's attack made the enemy front unit faint

TRIGGER_TEXT = {
    START_OF_TURN: "Start of turn",
    START_OF_BATTLE: "Start of battle",
    FAINT: "Faint",
    SELL: "Sell",
    LEVEL_UP: "Level-up",
    FRIEND_BOUGHT: "Unit bought",
    FRIEND_AHEAD_ATTACKS: "Friend ahead attacks",
    KNOCK_OUT: "Knock-out",
}


@dataclass(frozen=True)
class Ability:
    trigger: str
    effect: str
    amount: int
    arg: str = ""  # extra setting for an effect (summon: the token's name)
    reach: int = 1  # buff_ahead: how many units in front of the user it buffs


class Context:
    """what an effect is allowed to touch (enemies/state are None when not relevant)"""

    def __init__(self, rng, allies, enemies=None, state=None, subject=None):
        self.rng = rng
        self.allies = allies
        self.enemies = enemies or []
        self.state = state
        self.subject = subject  # e.g. the unit that was just bought
        self.targets = []  # units the effect affected (the battle view flashes them)
        self.ability = None  # the Ability being run (set by trigger())
        self.summon = None  # callable(token, summoner) -> bool, set by the battle or the shop; False = no room


# effects: (unit, n, ctx) -> short log text, or None if nothing happened -
def damage_random_enemy(unit, n, ctx):
    targets = [e for e in ctx.enemies if e.health > 0]
    if not targets:
        return None
    target = ctx.rng.choice(targets)
    target.health -= n
    ctx.targets.append(target)
    return f"{unit.name} hit {target.name} for {n}"


def buff_random_ally(unit, n, ctx):
    targets = [a for a in ctx.allies if a is not unit and a.health > 0]
    if not targets:
        return None
    target = ctx.rng.choice(targets)
    target.attack += n
    target.health += n
    ctx.targets.append(target)
    return f"{unit.name} gave {target.name} +{n}/+{n}"


def buff_all_allies(unit, n, ctx):
    targets = [a for a in ctx.allies if a is not unit and a.health > 0]
    if not targets:
        return None
    for target in targets:
        target.attack += n
        target.health += n
    ctx.targets.extend(targets)
    return f"{unit.name} gave all allies +{n}/+{n}"


def buff_self(unit, n, ctx):
    unit.attack += n
    unit.health += n
    ctx.targets.append(unit)
    return f"{unit.name} grew +{n}/+{n}"


def buff_ahead(unit, n, ctx):
    """give the ctx.ability.reach units directly in front of the user +n/+n (fewer if fewer are ahead).
    "in front" follows team order with empty slots skipped, the same order the battle uses"""
    order = ctx.allies
    i = next((k for k, a in enumerate(order) if a is unit), None)  # identity, not ==
    if i is None:
        return None
    targets = order[max(0, i - ctx.ability.reach):i]
    if not targets:
        return None
    for target in targets:
        target.attack += n
        target.health += n
    ctx.targets.extend(targets)
    names = " and ".join(t.name for t in targets)
    return f"{unit.name} gave {names} +{n}/+{n}"


def buff_bought_attack(unit, n, ctx):
    target = ctx.subject
    if target is None:
        return None
    target.attack += n
    ctx.targets.append(target)
    return f"{unit.name} gave {target.name} +{n} attack"


def buff_shop_health(unit, n, ctx):
    shop = [p for p in ctx.state.shop if p] if ctx.state else []
    if not shop:
        return None
    for p in shop:
        p.health += n
    return f"{unit.name} gave the shop units +{n} health"


def copy_health(unit, n, ctx):
    """gain n% of the healthiest ally's health"""
    others = [a for a in ctx.allies if a is not unit and a.health > 0]
    if not others:
        return None
    best = max(others, key=lambda a: a.health)
    gain = best.health * n // 100
    if gain <= 0:
        return None
    unit.health += gain
    ctx.targets.append(best)
    return f"{unit.name} copied {gain} health from {best.name}"


def gain_poison(unit, n, ctx):
    unit.poison = True
    ctx.targets.append(unit)
    return f"{unit.name} gained poison"


def gain_gold(unit, n, ctx):
    if ctx.state is None:  # only meaningful in the shop
        return None
    ctx.state.gold += n
    return f"{unit.name} gave +{n}g"


def token_stats(name, level=1):
    """a token's stats: its base stats from the pack times the summoner's level"""
    attack, health = PACK.tokens.get(name, (0, 0))
    return attack * level, health * level


def summon(unit, n, ctx):
    """summon ctx.ability.amount copies of the token named ctx.ability.arg (see the template below).
    count comes from the ability, token stats scale with the summoner's level, and nothing is
    summoned onto a full team. where tokens appear is decided by ctx.summon (battle or shop)"""
    ability = ctx.ability
    if ctx.summon is None or ability is None:
        return None
    made = []
    for _ in range(ability.amount):
        attack, health = token_stats(ability.arg, unit.level)
        token = Unit(ability.arg, attack, health, tier=0)
        if not ctx.summon(token, unit):
            break  # no room
        made.append(token)
    if not made:
        return f"{unit.name} had no room to summon"
    ctx.targets.extend(made)
    return f"{unit.name} summoned {len(made)} {ability.arg}"


# effect name -> (function, description template)
EFFECTS = {
    "damage_random_enemy": (damage_random_enemy, "deal {n} damage to a random enemy"),
    "buff_random_ally": (buff_random_ally, "give a random ally +{n}/+{n}"),
    "buff_all_allies": (buff_all_allies, "give all other allies +{n}/+{n}"),
    "buff_self": (buff_self, "gain +{n}/+{n}"),
    "buff_ahead": (buff_ahead, "give {ahead} +{n}/+{n}"),
    "buff_bought_attack": (buff_bought_attack, "give the unit you bought +{n} attack"),
    "buff_shop_health": (buff_shop_health, "give every shop unit +{n} health"),
    "copy_health": (copy_health, "gain {n}% of the healthiest ally's health"),
    "gain_poison": (gain_poison, "gain poison (whatever it damages faints)"),
    "gain_gold": (gain_gold, "gain {n} gold"),
    "summon": (summon, "summon {count} {token} ({ta}/{th})"),
}

# --- template: adding a summoning unit ---------------------------------------------------------
#  1. add the token (a unit that only exists when summoned) to the pack, game/packs.py:
#         tokens={"Shell": (2, 4)}                       # name -> (attack, health)
#  2. give a unit the ability, below:
#         "Turtle": Ability(FAINT, "summon", 1, "Shell")   # Ability(trigger, "summon", how many, token name)
#     where the tokens appear depends on the trigger:
#         FAINT                                   in the fainted unit's own slot
#         START_OF_BATTLE / KNOCK_OUT / FRIEND_AHEAD_ATTACKS   right behind the summoner
#         SELL / LEVEL_UP / FRIEND_BOUGHT         on your team in the shop (the sold unit's slot, else the first free one)
#     token stats = base stats x the summoner's level (change token_stats() to scale differently),
#     and nothing is summoned onto a full team (TEAM_SIZE). the user and the new tokens flash in battle.
#  3. optional art: assets/units/<tokenname>.png (lowercase), same as any unit.
# -----------------------------------------------------------------------------------------------

# unit name -> ability
ABILITIES = {
    # tier 1
    "Ant": Ability(FAINT, "buff_random_ally", 1),
    "Beaver": Ability(SELL, "buff_random_ally", 1),
    "Duck": Ability(SELL, "buff_shop_health", 1),
    "Fish": Ability(LEVEL_UP, "buff_all_allies", 1),
    "Mosquito": Ability(START_OF_BATTLE, "damage_random_enemy", 1),
    "Pig": Ability(SELL, "gain_gold", 2),
    # tier 2
    "Cricket": Ability(FAINT, "buff_random_ally", 2),
    "Horse": Ability(FRIEND_BOUGHT, "buff_bought_attack", 1),
    "Otter": Ability(START_OF_BATTLE, "buff_random_ally", 2),
    "Crab": Ability(START_OF_BATTLE, "copy_health", 25),
    "Flamingo": Ability(FAINT, "buff_random_ally", 3),
    "Hedgehog": Ability(FAINT, "damage_random_enemy", 2),
    # tier 3
    "Badger": Ability(FAINT, "damage_random_enemy", 3),
    "Dog": Ability(SELL, "buff_random_ally", 2),
    "Giraffe": Ability(START_OF_TURN, "buff_ahead", 1),
    "Kangaroo": Ability(FRIEND_AHEAD_ATTACKS, "buff_self", 2),
    "Sheep": Ability(FAINT, "buff_random_ally", 4),
    "Turtle": Ability(FAINT, "summon", 1, "Shell"),
    # tier 4
    "Bison": Ability(START_OF_BATTLE, "buff_random_ally", 2),
    "Deer": Ability(FAINT, "buff_random_ally", 4),
    "Dolphin": Ability(START_OF_BATTLE, "damage_random_enemy", 3),
    "Hippo": Ability(KNOCK_OUT, "buff_self", 2),
    "Penguin": Ability(START_OF_TURN, "buff_ahead", 1, reach=2),
    "Rooster": Ability(FAINT, "damage_random_enemy", 4),
    # tier 5
    "Cow": Ability(SELL, "summon", 1, "Calf"),
    "Crocodile": Ability(START_OF_BATTLE, "damage_random_enemy", 5),
    "Rhino": Ability(START_OF_BATTLE, "damage_random_enemy", 4),
    "Scorpion": Ability(START_OF_BATTLE, "gain_poison", 1),
    "Shark": Ability(FAINT, "buff_random_ally", 5),
    "Tiger": Ability(START_OF_BATTLE, "buff_random_ally", 3),
}

# perk name -> ability an item can give to a unit (works alongside the unit's own ability).
# a unit holds ONE perk at a time: using another perk item replaces it, perks never stack
PERKS = {
    "honey": Ability(FAINT, "buff_random_ally", 2),
    "steak": Ability(START_OF_BATTLE, "damage_random_enemy", 3),
}


def abilities_of(unit):
    """the unit's own ability plus its perk (an item can give a unit one perk at a time)"""
    found = [ABILITIES[unit.name]] if unit.name in ABILITIES else []
    return found + ([PERKS[unit.perk]] if unit.perk in PERKS else [])


def trigger(unit, when, ctx):
    """run every ability of the unit that fires on `when`; returns log text or None"""
    notes = []
    for ability in abilities_of(unit):
        if ability.trigger == when:
            func, _ = EFFECTS[ability.effect]
            ctx.ability = ability
            note = func(unit, ability.amount * unit.level, ctx)
            if note:
                notes.append(note)
    return "; ".join(notes) or None


def has_trigger(unit, when):
    return any(a.trigger == when for a in abilities_of(unit))


def describe_ability(ability, level=1):
    _, text = EFFECTS[ability.effect]
    ta, th = token_stats(ability.arg, level)
    ahead = "the unit ahead" if ability.reach == 1 else f"the {ability.reach} units ahead"
    text = text.format(n=ability.amount * level, count=ability.amount, token=ability.arg, ta=ta, th=th, ahead=ahead)
    return f"{TRIGGER_TEXT[ability.trigger]}: {text}"


def describe(unit):
    head = f"{unit.name} (Token, Lv{unit.level})" if unit.tier == 0 else f"{unit.name} (Tier {unit.tier}, Lv{unit.level})"
    parts = []
    if unit.name in ABILITIES:
        parts.append(describe_ability(ABILITIES[unit.name], unit.level))
    if unit.perk in PERKS:
        parts.append(f"{unit.perk.title()} perk, {describe_ability(PERKS[unit.perk], unit.level)}")
    if unit.armor:
        parts.append(f"Armor {unit.armor}")
    if unit.temp_attack or unit.temp_health:
        parts.append(f"+{unit.temp_attack}/+{unit.temp_health} until the end of the next battle")
    return f"{head} - " + " | ".join(parts) if parts else f"{head}: no ability"
