"""animates battle: front units bump into each other, then the dead drop out"""
import pygame

LEFT_FRONT_X = 430
RIGHT_FRONT_X = 530
SPACING = 95
ROOM = 400 # room behind the front unit on each side; bigger teams squeeze together (overlap) to fit


def spacing(n):
    """distance between neighbouring units in a team of n: normal, or squeezed if they would not fit"""
    return SPACING if n <= 1 else min(SPACING, ROOM / (n - 1))

Y = 300
APPROACH = 20  # how far each front unit lunges, in pixels

PHASES = [("approach", 0.30), ("impact", 0.14), ("retreat", 0.22), ("pause", 0.18)]
START_STEP = 0.45  # seconds between start-of-battle abilities firing
FLASH_TIME = 0.3  # how long an ability's user and receiver flash


class BattleView:
    def __init__(self, battle):
        self.battle = battle
        self.phase_i = 0
        self.t = 0.0
        self.delay = 0.6  # short beat to look at the matchup
        self.done = False
        self.fast = False
        self.in_start = False  # True while start-of-battle abilities are firing
        self.flash = {}  # id(unit) -> seconds of flash left
        self.step_t = 0.0

    def toggle_speed(self):
        self.fast = not self.fast

    # logic -
    def update(self, dt):
        if self.done:
            return
        speed = 3.0 if self.fast else 1.0
        for unit in self.battle.flash_queue:
            self.flash[id(unit)] = FLASH_TIME
        self.battle.flash_queue.clear()
        for key in list(self.flash):
            self.flash[key] -= dt * speed
            if self.flash[key] <= 0:
                del self.flash[key]
        if self.delay > 0:
            self.delay -= dt
            if self.delay <= 0:
                self.battle.begin()
                self.in_start = True
                self.step_t = 0.0  # first ability fires right away
            return
        if self.in_start:
            self.step_t -= min(dt, 0.05) * (3.0 if self.fast else 1.0)
            if self.step_t <= 0:
                self.step_t = START_STEP
                if not self.battle.fire_next():  # nothing left: dead are cleared
                    self.in_start = False
            return
        if self.battle.is_over():
            self.done = True
            return
        self.t += min(dt, 0.05) * (3.0 if self.fast else 1.0)
        while self.t >= PHASES[self.phase_i][1]:
            self.t -= PHASES[self.phase_i][1]
            leaving = PHASES[self.phase_i][0]
            self.phase_i = (self.phase_i + 1) % len(PHASES)
            entering = PHASES[self.phase_i][0]
            if entering == "impact":
                self.battle.clash()
            if leaving == "retreat":
                self.battle.cleanup()
            if leaving == "pause" and self.battle.is_over():
                self.done = True
                self.t = 0.0
                self.phase_i = 0
                return

    def is_flashing(self, unit):
        """True while this unit was just the user or receiver of an ability"""
        return not self.done and self.flash.get(id(unit), 0) > 0

    def offset(self):
        name, dur = PHASES[self.phase_i]
        p = self.t / dur
        if name == "approach":
            return APPROACH * p
        if name == "impact":
            return APPROACH
        if name == "retreat":
            return APPROACH * (1 - p)
        return 0

    # drawing -
    def draw(self, surf, ui, state):
        ui.draw_background(surf, "battle")
        off = self.offset()
        flash = PHASES[self.phase_i][0] == "impact" and self.delay <= 0
        sp_left, sp_right = spacing(len(self.battle.left)), spacing(len(self.battle.right))
        for i in reversed(range(len(self.battle.left))):  # back to front, so the front unit sits on top when squeezed
            unit = self.battle.left[i]
            x = LEFT_FRONT_X - sp_left * i + (off if i == 0 else 0)
            ui.draw_unit(surf, unit, x, Y, flash=(flash and i == 0) or self.is_flashing(unit))
        for i in reversed(range(len(self.battle.right))):
            unit = self.battle.right[i]
            x = RIGHT_FRONT_X + sp_right * i - (off if i == 0 else 0)
            ui.draw_unit(surf, unit, x, Y, flip=True, flash=(flash and i == 0) or self.is_flashing(unit))

        ui.text(surf, f"Turn {state.turn}", (480, 40), 36)
        ui.text(surf, "Your team", (230, 190), 26, (150, 200, 255))
        ui.text(surf, "Enemy team", (730, 190), 26, (255, 150, 150))
        if self.battle.log:
            ui.text(surf, self.battle.log[-1], (480, 390), 22, (255, 215, 90))
        if self.done:
            res = {"win": "VICTORY", "lose": "DEFEAT", "draw": "DRAW"}[self.battle.result()]
            ui.text(surf, res, (480, 430), 80)
            ui.text(surf, "Click to continue", (480, 490), 26, (180, 180, 190))
        else:
            ui.text(surf, "Click or press F for fast-forward", (480, 510), 20, (140, 140, 150))
