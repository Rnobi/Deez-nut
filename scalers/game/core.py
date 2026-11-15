"""game state and shop rules"""
import random

from . import abilities, config
from . import items as item_defs
from .units import random_unit


class GameState:
    def __init__(self, rng=None, difficulty=None, endless=False):
        self.rng = rng or random.Random()
        self.endless = endless  # no win limit: you play until you run out of lives
        self.difficulty = difficulty or config.DIFFICULTIES[0]
        self.turn = 0
        self.lives = config.STARTING_LIVES
        self.wins = 0
        self.gold = 0
        self.team = [None] * config.TEAM_SIZE  # index 0 = front
        self.shop = [None] * config.SHOP_SIZE
        self.items = [None] * config.ITEM_SHOP_SIZE
        # frozen slots keep their item through rerolls and new turns
        self.shop_frozen = [False] * config.SHOP_SIZE
        self.item_frozen = [False] * config.ITEM_SHOP_SIZE
        self.status = "shop"  # shop/won/lost
        self.message = ""
        self.start_turn()

    # turn structure -
    def start_turn(self):
        self.turn += 1
        self.gold = config.STARTING_GOLD
        self.roll_shop()
        if self.turn > 1 and self.turn in config.TIER_UNLOCK_TURNS.values():
            note = f"Tier {config.max_tier(self.turn)} unlocked!"
            self.message = f"{self.message} {note}" if self.message else note
        if config.shop_size(self.turn) > config.shop_size(self.turn - 1):
            note = f"Shop slot {config.shop_size(self.turn)} unlocked!"
            self.message = f"{self.message} {note}" if self.message else note
        # start-of-turn abilities (Giraffe, Penguin), front to back
        for unit in [p for p in self.team if p]:
            note = self._trigger(unit, abilities.START_OF_TURN)
            if note:
                self.message = f"{self.message} {note}" if self.message else note

    def roll_shop(self):
        """refill every slot that isn't frozen"""
        for j in range(config.shop_size(self.turn)):  # slots that haven't unlocked yet stay empty
            if not self.shop_frozen[j]:
                self.shop[j] = random_unit(self.rng, turn=self.turn)
        for j in range(config.ITEM_SHOP_SIZE):
            if not self.item_frozen[j]:
                self.items[j] = item_defs.random_item(self.rng, self.turn)

    def battle_team(self):
        return [p.battle_copy() for p in self.team if p]

    def finish_battle(self, result):
        for p in self.team:  # temporary buffs (Cupcake) only last one battle
            if p:
                p.temp_attack = p.temp_health = 0
        if result == "win":
            self.wins += 1
            self.message = "You won the last battle."
        elif result == "lose":
            self.lives -= 1
            self.message = "You lost the last battle (-1 life)."
        else:
            self.message = "The last battle was a draw."
        if self.wins >= config.WINS_TO_WIN and not self.endless:
            self.status = "won"
        elif self.lives <= 0:
            self.status = "lost"
        else:
            self.start_turn()

    # shop actions -
    def reroll(self):
        if self.gold < config.REROLL_COST:
            self.message = "Not enough gold to reroll."
            return False
        open_slots = range(config.shop_size(self.turn))
        if all(self.shop_frozen[j] for j in open_slots) and all(self.item_frozen):
            self.message = "Everything is frozen."
            return False
        self.gold -= config.REROLL_COST
        self.roll_shop()
        self.message = ""
        return True

    def toggle_freeze(self, kind, idx):
        """kind is 'shop' (units) or 'item'; only slots that hold something can freeze"""
        slots, flags = (self.shop, self.shop_frozen) if kind == "shop" else (self.items, self.item_frozen)
        if slots[idx] is None:
            return False
        flags[idx] = not flags[idx]
        self.message = f"{slots[idx].name} {'frozen' if flags[idx] else 'unfrozen'}."
        return True

    def _shop_summoner(self, slot=None):
        """the ctx.summon callback for the shop: the sold unit's slot if it is free, else the first free slot"""
        def summon(token, source):
            order = ([slot] if slot is not None else []) + list(range(len(self.team)))
            for i in order:
                if self.team[i] is None:
                    self.team[i] = token
                    return True
            return False
        return summon

    def _trigger(self, unit, when, subject=None, slot=None):
        """fire a shop-phase ability; returns its text (or '')"""
        ctx = abilities.Context(self.rng, [p for p in self.team if p], state=self, subject=subject)
        ctx.summon = self._shop_summoner(slot)
        return abilities.trigger(unit, when, ctx) or ""

    def buy(self, shop_idx, slot):
        unit = self.shop[shop_idx]
        if unit is None:
            return False
        if self.gold < config.UNIT_COST:
            self.message = "Not enough gold."
            return False
        target = self.team[slot]
        notes = []
        if target is None:
            self.team[slot] = unit
            self.message = f"Bought {unit.name}."
            for other in self.team:  # abilities that react to a unit being bought
                if other and other is not unit:
                    notes.append(self._trigger(other, abilities.FRIEND_BOUGHT, subject=unit))
        elif target.can_merge(unit):
            target.merge(unit)
            self.message = f"{target.name} merged! Now level {target.level}."
            notes.append(self._trigger(target, abilities.LEVEL_UP))
        else:
            self.message = "That slot is taken (drop onto the same level unit to merge)."
            return False
        self.gold -= config.UNIT_COST
        self.shop[shop_idx] = None
        self.shop_frozen[shop_idx] = False
        notes = [n for n in notes if n]
        if notes:
            self.message += " " + "; ".join(notes)
        return True

    def buy_item(self, item_idx, slot):
        item = self.items[item_idx]
        if item is None:
            return False
        unit = self.team[slot]
        if unit is None:
            self.message = "Drop items onto a unit."
            return False
        if self.gold < config.ITEM_COST:
            self.message = "Not enough gold."
            return False
        self.gold -= config.ITEM_COST
        self.items[item_idx] = None
        self.item_frozen[item_idx] = False
        self.message = item_defs.apply(item, unit, self)
        return True

    def level_up(self, unit):
        """give a unit a level (+2/+2 like a merge) and fire its level-up ability; returns text"""
        if unit.level >= config.MAX_LEVEL:
            return f"{unit.name} is already at max level."
        unit.attack += 2
        unit.health += 2
        unit.level += 1
        note = self._trigger(unit, abilities.LEVEL_UP)
        return f"{unit.name} reached level {unit.level}." + (f" {note}" if note else "")

    def sell(self, slot):
        unit = self.team[slot]
        if unit is None:
            return False
        self.gold += unit.sell_value
        self.team[slot] = None
        self.message = f"Sold {unit.name} for {unit.sell_value}g."
        note = self._trigger(unit, abilities.SELL, slot=slot)
        if note:
            self.message += " " + note
        return True

    def swap(self, a, b):
        self.team[a], self.team[b] = self.team[b], self.team[a]

    def merge_team(self, src, dst):
        """merge the unit in slot src into the unit in slot dst (same name only),
        returns True if a merge happened; the src slot is then emptied
        """
        a, b = self.team[src], self.team[dst]
        if src == dst or a is None or b is None or not b.can_merge(a):
            return False
        b.merge(a)
        self.team[src] = None
        self.message = f"{b.name} merged! Now level {b.level}."
        note = self._trigger(b, abilities.LEVEL_UP)
        if note:
            self.message += " " + note
        return True
