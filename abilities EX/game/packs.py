"""a pack: every unit and item the game can offer, grouped by tier.

units and items are (name, attack, health). tiers unlock over the game (see
config.TIER_UNLOCK_TURNS). to make another pack, build another Pack with the same shape.

a Pack can't be edited once it is built (its contents are frozen). the STANDARD pack is the default
pack every game uses and is immutable by design. the plan for custom packs: units won from the gacha
get put into a NEW Pack (the create-pack page), they never modify STANDARD.
"""
from dataclasses import dataclass, field
from types import MappingProxyType


def _freeze(tiers):
    """tier -> tuple of (name, attack, health) tuples, in a read-only mapping"""
    return MappingProxyType({tier: tuple(tuple(entry) for entry in entries) for tier, entries in tiers.items()})


@dataclass(frozen=True, eq=False)
class Pack:
    name: str
    units: dict  # tier -> [(name, attack, health), ...]
    items: dict  # tier -> [(name, attack, health), ...]
    # units that only exist when an ability summons them (never sold in the shop): name -> (attack, health)
    tokens: dict = field(default_factory=dict)

    def __post_init__(self):
        # copy everything into read-only structures so later edits to the source dicts can't leak in
        object.__setattr__(self, "units", _freeze(self.units))
        object.__setattr__(self, "items", _freeze(self.items))
        object.__setattr__(self, "tokens", MappingProxyType(dict(self.tokens)))

    def units_up_to(self, tier):
        """every unit in tiers 1..tier, as (tier, name, attack, health)"""
        return [(t, *p) for t in sorted(self.units) if t <= tier for p in self.units[t]]

    def items_up_to(self, tier):
        """every item in tiers 1..tier, as (tier, name, attack, health)"""
        return [(t, *f) for t in sorted(self.items) if t <= tier for f in self.items[t]]


# 30 units (6 per tier 1-5) and 12 items (2 per tier 1-6)
STANDARD = Pack(
    name="Standard",
    units={
        1: [("Ant", 2, 2), ("Beaver", 2, 3), ("Duck", 1, 4), ("Fish", 3, 2), ("Mosquito", 3, 1), ("Pig", 2, 4)],
        2: [("Cricket", 2, 4), ("Horse", 4, 2), ("Otter", 1, 5), ("Crab", 3, 5), ("Flamingo", 3, 3), ("Hedgehog", 3, 4)],
        3: [("Badger", 5, 4), ("Dog", 4, 5), ("Giraffe", 3, 6), ("Kangaroo", 5, 5), ("Sheep", 4, 5), ("Turtle", 2, 8)],
        4: [("Bison", 6, 6), ("Deer", 5, 6), ("Dolphin", 5, 7), ("Hippo", 6, 7), ("Penguin", 4, 8), ("Rooster", 7, 5)],
        5: [("Cow", 6, 10), ("Crocodile", 8, 8), ("Rhino", 8, 9), ("Scorpion", 9, 7), ("Shark", 8, 8), ("Tiger", 8, 9)],
    },
    items={
        1: [("Apple", 1, 1), ("Pear", 0, 3)],
        2: [("Meat", 3, 0), ("Cupcake", 2, 2)],
        3: [("Cheese", 2, 3), ("Carrot", 3, 2)],
        4: [("Steak", 4, 2), ("Honey", 2, 4)],
        5: [("Sushi", 4, 4), ("Pizza", 5, 3)],
        6: [("Salad", 5, 5), ("Chocolate", 7, 3)],
    },
    tokens={"Shell": (2, 4), "Chick": (2, 1), "Calf": (4, 4)},
)

# the pack every game uses; always available and immutable
DEFAULT_PACK = STANDARD
