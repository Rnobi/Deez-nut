"""animates battle: front pets bump into each other, then the dead drop out"""
import pygame

from .ui import BG

LEFT_FRONT_X = 430
RIGHT_FRONT_X = 530
SPACING = 95
Y = 300
APPROACH = 20  # how far each front pet lunges, in pixels

PHASES = [("approach", 0.30), ("impact", 0.14), ("retreat", 0.22), ("pause", 0.18)]


class BattleView:
    def __init__(self, battle):
        self.battle = battle
        self.phase_i = 0
        self.t = 0.0
        self.delay = 0.6  # short beat to look at the matchup
        self.done = False
        self.fast = False

    def toggle_speed(self):
        self.fast = not self.fast

    # logic -
    def update(self, dt):
        if self.done:
            return
        if self.delay > 0:
            self.delay -= dt
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
        surf.fill(BG)
        off = self.offset()
        flash = PHASES[self.phase_i][0] == "impact" and self.delay <= 0
        for i, pet in enumerate(self.battle.left):
            x = LEFT_FRONT_X - SPACING * i + (off if i == 0 else 0)
            ui.draw_pet(surf, pet, x, Y, flash=flash and i == 0)
        for i, pet in enumerate(self.battle.right):
            x = RIGHT_FRONT_X + SPACING * i - (off if i == 0 else 0)
            ui.draw_pet(surf, pet, x, Y, flip=True, flash=flash and i == 0)

        ui.text(surf, f"Turn {state.turn}", (480, 40), 36)
        ui.text(surf, "Your team", (230, 190), 26, (150, 200, 255))
        ui.text(surf, "Enemy team", (730, 190), 26, (255, 150, 150))
        if self.done:
            res = {"win": "VICTORY", "lose": "DEFEAT", "draw": "DRAW"}[self.battle.result()]
            ui.text(surf, res, (480, 430), 80)
            ui.text(surf, "Click to continue", (480, 490), 26, (180, 180, 190))
        else:
            ui.text(surf, "Click or press F for fast-forward", (480, 510), 20, (140, 140, 150))
