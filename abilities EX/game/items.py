"""items: bought in the shop and used on a team unit.

every item gives the unit its listed stats for good (those numbers live in the pack, game/packs.py),
and some items also have an extra effect, listed in ITEM_EFFECTS below. to add an effect kind,
write a function here and add it to EFFECT_KINDS.
"""
from dataclasses import dataclass

from . import abilities, config
from .packs import STANDARD


@dataclass
class Item:
    name: str
    attack: int
    health: int
    tier: int = 1

    @property
    def has_effect(self):
        return self.name in ITEM_EFFECTS

    def describe(self):
        text = f"{self.name} (Tier {self.tier}): +{self.attack}/+{self.health} to a unit"
        if self.has_effect:
            text += ", and " + effect_text(ITEM_EFFECTS[self.name])
        return text


@dataclass(frozen=True)
class ItemEffect:
    kind: str
    amount: int = 0
    count: int = 0  # how many units (buff_random_units)
    perk: str = ""  # which perk (perk)


# effects: (effect, unit, state) -> short text, or None if nothing happened -
def _buff_random_units(eff, unit, state):
    others = [p for p in state.team if p and p is not unit]
    if not others:
        return None
    picked = state.rng.sample(others, min(eff.count, len(others)))
    for p in picked:
        p.attack += eff.amount
        p.health += eff.amount
    return f"{len(picked)} other unit(s) got +{eff.amount}/+{eff.amount}."


def _buff_team(eff, unit, state):
    others = [p for p in state.team if p and p is not unit]
    for p in others:
        p.attack += eff.amount
        p.health += eff.amount
    return f"Every other unit got +{eff.amount}/+{eff.amount}." if others else None


def _temp_buff(eff, unit, state):
    unit.temp_attack += eff.amount
    unit.temp_health += eff.amount
    return f"+{eff.amount}/+{eff.amount} until the end of the next battle."


def _shop_buff(eff, unit, state):
    shop = [p for p in state.shop if p]
    for p in shop:
        p.attack += eff.amount
        p.health += eff.amount
    return f"The shop units got +{eff.amount}/+{eff.amount}." if shop else None


def _armor(eff, unit, state):
    unit.armor += eff.amount
    return f"{unit.name} now takes {unit.armor} less damage per hit."


def _perk(eff, unit, state):
    unit.perks = tuple(dict.fromkeys(unit.perks + (eff.perk,)))
    return f"{unit.name} gained the {eff.perk} perk."


def _level_up(eff, unit, state):
    return state.level_up(unit)


# effect kind -> (function, description template)
EFFECT_KINDS = {
    "buff_random_units": (_buff_random_units, "give {count} other random units +{amount}/+{amount}"),
    "buff_team": (_buff_team, "give every other team unit +{amount}/+{amount}"),
    "temp_buff": (_temp_buff, "give +{amount}/+{amount} until the end of the next battle"),
    "shop_buff": (_shop_buff, "give every shop unit +{amount}/+{amount}"),
    "armor": (_armor, "make it take {amount} less damage per hit (never below 1)"),
    "perk": (_perk, "gain a perk"),
    "level_up": (_level_up, "level it up"),
}

# item name -> extra effect (items not listed here only give their stats)
ITEM_EFFECTS = {
    "Cupcake": ItemEffect("temp_buff", amount=3),
    "Cheese": ItemEffect("shop_buff", amount=1),
    "Carrot": ItemEffect("armor", amount=2),
    "Honey": ItemEffect("perk", perk="honey"),
    "Steak": ItemEffect("perk", perk="steak"),
    "Sushi": ItemEffect("buff_random_units", amount=1, count=3),
    "Pizza": ItemEffect("buff_random_units", amount=2, count=2),
    "Salad": ItemEffect("buff_team", amount=2),
    "Chocolate": ItemEffect("level_up"),
}


def effect_text(eff):
    if eff.kind == "perk":
        return f"gain a perk ({abilities.describe_ability(abilities.PERKS[eff.perk])})"
    return EFFECT_KINDS[eff.kind][1].format(amount=eff.amount, count=eff.count)


def apply(item, unit, state):
    """use the item on the unit: its stats, then its extra effect. returns a message"""
    unit.attack += item.attack
    unit.health += item.health
    note = f"{unit.name} used {item.name} (+{item.attack}/+{item.health})."
    eff = ITEM_EFFECTS.get(item.name)
    if eff:
        extra = EFFECT_KINDS[eff.kind][0](eff, unit, state)
        if extra:
            note += " " + extra
    return note


def random_item(rng, turn=1, pack=STANDARD):
    """a random item from the tiers unlocked on this turn"""
    tier, name, atk, hp = rng.choice(pack.items_up_to(config.max_tier(turn)))
    return Item(name, atk, hp, tier)
