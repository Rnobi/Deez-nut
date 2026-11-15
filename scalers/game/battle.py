"""auto-battle engine:

both teams are lists where index 0 is the front unit. Each clash, the two
front units hit each other simultaneously; dead units are then removed.
Abilities: start-of-battle fires once in start(), knock-out and friend-ahead-attacks fire in clash(),
faint fires in cleanup(). armor and poison are applied in clash()
"""
import random

from . import abilities, config


class Battle:
    def __init__(self, left, right, rng=None):
        self.left = [p.copy() for p in left]
        self.right = [p.copy() for p in right]
        self.rng = rng or random.Random()
        self.started = False
        self.log = []  # short text for each ability that fired, newest last
        self._queue = []  # start-of-battle abilities waiting to fire
        self.flash_queue = []  # units for the view to flash: each ability's user and receiver

    def _say(self, msg, units=()):
        """log an ability and queue its user + receivers for the view to flash"""
        if msg:
            self.log.append(msg)
            self.flash_queue.extend(units)

    def begin(self):
        """queue every start-of-battle ability (highest attack first); fire them with fire_next()"""
        if self.started:
            return
        self.started = True
        queue = [(p, self.left, self.right) for p in self.left]
        queue += [(p, self.right, self.left) for p in self.right]
        queue = [q for q in queue if abilities.has_trigger(q[0], abilities.START_OF_BATTLE)]
        self.rng.shuffle(queue)  # so ties don't always favour one side
        queue.sort(key=lambda q: -q[0].attack)
        self._queue = queue

    def fire_next(self):
        """fire ONE queued start ability. returns False once none are left (the dead
        are cleared at that point). the view calls this on a timer so each one is seen"""
        if not self._queue:
            self.cleanup()
            return False
        unit, allies, enemies = self._queue.pop(0)
        ctx = abilities.Context(self.rng, allies, enemies)
        ctx.summon = self._summoner(allies)
        self._say(abilities.trigger(unit, abilities.START_OF_BATTLE, ctx), (unit, *ctx.targets))
        return True

    def start(self):
        """fire all start-of-battle abilities at once (used when there is no animation)"""
        self.begin()
        while self.fire_next():
            pass

    def is_over(self):
        """over when a side is wiped out, or when neither front unit can deal damage
        (e.g. two 0-attack units would otherwise bump forever; result() calls that a draw)"""
        if not self.left or not self.right:
            return True
        return self.left[0].attack <= 0 and self.right[0].attack <= 0

    def _damage(self, attacker, defender):
        """damage one hit does: attack minus the defender's armor, but never below 1
        (a 0-attack unit deals nothing)"""
        if attacker.attack <= 0:
            return 0
        return max(1, attacker.attack - defender.armor)

    def _summoner(self, team):
        """the ctx.summon callback for one side: the token goes right after the summoner in the
        list. for a fainted summoner that is its own slot (the dead unit is removed in cleanup)"""
        def summon(token, source):
            if sum(1 for p in team if p.health > 0) >= config.TEAM_SIZE:
                return False
            i = next(k for k, p in enumerate(team) if p is source)  # identity, not ==
            team.insert(i + 1, token)
            return True
        return summon

    def _fire(self, unit, when, allies, enemies):
        ctx = abilities.Context(self.rng, [p for p in allies if p.health > 0], enemies)
        ctx.summon = self._summoner(allies)
        self._say(abilities.trigger(unit, when, ctx), (unit, *ctx.targets))

    def clash(self):
        """frontmost units deal damage to each other (dead units stay until cleanup)"""
        a, b = self.left[0], self.right[0]
        hit_a, hit_b = self._damage(b, a), self._damage(a, b)
        a.health -= hit_a
        b.health -= hit_b
        if hit_a > 0 and b.poison:
            a.health = min(a.health, 0)
        if hit_b > 0 and a.poison:
            b.health = min(b.health, 0)
        # knock-out: this unit survived and made the enemy front unit faint
        for unit, foe, allies, enemies in ((a, b, self.left, self.right), (b, a, self.right, self.left)):
            if unit.health > 0 and foe.health <= 0:
                self._fire(unit, abilities.KNOCK_OUT, allies, enemies)
        # friend ahead attacks: the unit directly behind each front unit reacts
        for allies, enemies in ((self.left, self.right), (self.right, self.left)):
            if len(allies) > 1 and allies[1].health > 0:
                self._fire(allies[1], abilities.FRIEND_AHEAD_ATTACKS, allies, enemies)

    def cleanup(self):
        """remove fainted units, firing their faint abilities first. a faint ability can
        kill more units (even ones on its own side), so keep going until nobody new is dead"""
        done = set()
        while True:
            fresh = [(p, a, e) for a, e in ((self.left, self.right), (self.right, self.left))
                     for p in a if p.health <= 0 and id(p) not in done]
            if not fresh:
                break
            for unit, allies, enemies in fresh:
                done.add(id(unit))
                ctx = abilities.Context(self.rng, [p for p in allies if p.health > 0], enemies)
                ctx.summon = self._summoner(allies)
                self._say(abilities.trigger(unit, abilities.FAINT, ctx), (unit, *ctx.targets))
        self.left = [p for p in self.left if p.health > 0]
        self.right = [p for p in self.right if p.health > 0]

    def result(self):
        """win, lose or draw, from the left (player) side"""
        if self.left and not self.right:
            return "win"
        if self.right and not self.left:
            return "lose"
        return "draw"

    def run_to_end(self):
        self.start()
        while not self.is_over():
            self.clash()
            self.cleanup()
        return self.result()
