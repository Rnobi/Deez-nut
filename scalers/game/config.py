"""tunable settings, tweak numbers here to rebalance the game"""
import os
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets", "units")
ITEM_ASSET_DIR = os.path.join(BASE_DIR, "assets", "items")
UI_ASSET_DIR = os.path.join(BASE_DIR, "assets", "ui")  # freeze.png goes here
BG_DIR = os.path.join(BASE_DIR, "assets", "backgrounds")  # shop.png, battle.png
FREEZE_SCALE = 1.15  # freeze.png is drawn this much larger than the card, centred on it...
FREEZE_OPACITY = 0.5  # ...at this opacity (0-1)
SUMMONING_CIRCLE_SIZE = 300  # gacha scene: summoning_circle.png is fitted inside this square
BALL_SIZE = 150  # gacha scene: ball.png is fitted inside this square (keep the art at least as big as a card)
MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")  # drop mp3/ogg/wav files here

TITLE = "Discount Village"  # start screen + window title, change freely
WIDTH, HEIGHT = 960, 540
FPS = 60

TEAM_SIZE = 5
SHOP_SIZE = 4  # most unit slots the shop can have (the last ones unlock later, see shop_size)
SHOP_BASE_SIZE = 3  # unit slots open from turn 1
ITEM_SHOP_SIZE = 2
ITEM_COST = 3
STARTING_GOLD = 10
UNIT_COST = 3
REROLL_COST = 1
STARTING_LIVES = 5
WINS_TO_WIN = 10
MAX_LEVEL = 3
STAT_CAP = 99  # attack and health can never go above this

# turn each shop tier unlocks on (same as Super Auto Pets)
TIER_UNLOCK_TURNS = {1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11}

# the 4th unit slot in the shop opens on the same turn as tier 3 (turn 5); change this to move it
SHOP_SLOT_UNLOCK_TURN = TIER_UNLOCK_TURNS[3]


def stat_bonus(turn, every=3, step=1):
    """Extra attack/health that enemy units gain as turns pass."""
    return step * max(0, (turn - 1) // every)


def shop_size(turn):
    """how many unit slots the shop has open on this turn"""
    return SHOP_SIZE if turn >= SHOP_SLOT_UNLOCK_TURN else SHOP_BASE_SIZE


def max_tier(turn):
    """highest shop tier unlocked on this turn"""
    return max(t for t, from_turn in TIER_UNLOCK_TURNS.items() if turn >= from_turn)


GREEN_ALPHA = 70  # strength of the green-mode overlay, 0-255


@dataclass(frozen=True)
class Difficulty:
    """how enemy teams scale (used by opponents.generate_team)"""
    name: str
    blurb: tuple  # two short lines shown under the menu button
    min_size: int  # enemy team size = min_size + (turn + 1) // 2, capped at TEAM_SIZE
    bonus_every: int  # enemy units gain +1/+1 every this many turns
    extra_div: int  # plus a random 0..turn // extra_div on each stat
    tier_boost: int = 0  # enemies may draw from this many tiers beyond the unlocked ones
    bonus_step: int = 1  # how much each bonus_every step adds (+step/+step)


# the menu shows these left to right; the first is the default
DIFFICULTIES = [
    Difficulty("Normal", ("Enemy teams grow slowly", "+1 stat every 3 turns"), 2, 3, 4),
    Difficulty("Hard", ("Bigger, tougher teams", "more stats every turn"), 3, 2, 3, bonus_step=1),
    Difficulty("Rigged", ("Full teams, 1 tier ahead", "stat monster"), 4, 1, 2, tier_boost=1, bonus_step=2),
]


# background music. drop files in assets/music/ named after the scene (menu.mp3, shop.mp3, battle.mp3,
# gacha.mp3, create_pack.mp3 (those two fall back to the menu track), or
# bgm.mp3 for everything), or set a source below: a direct http(s) link to an audio file, or a file name
# inside assets/music. None = nothing. "default" plays on any scene that has no music of its own.
BGM = {"default": None, "menu": None, "shop": None, "battle": None, "gacha": None, "create_pack": None}
BGM_VOLUME = 0.4  # 0.0 - 1.0
