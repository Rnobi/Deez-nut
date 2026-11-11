"""tunable settings, tweak numbers here to rebalance the game"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets", "pets")

WIDTH, HEIGHT = 960, 540
FPS = 60

TEAM_SIZE = 5
SHOP_SIZE = 3
STARTING_GOLD = 10
PET_COST = 3
REROLL_COST = 1
STARTING_LIVES = 5
WINS_TO_WIN = 10
MAX_LEVEL = 3


def stat_bonus(turn):
    """Extra attack/health that shop pets and enemy pets gain as turns pass."""
    return max(0, (turn - 3) // 2)
