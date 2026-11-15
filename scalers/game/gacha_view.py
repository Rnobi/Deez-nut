"""the gacha reveal: a ball sits on the summoning circle, splits vertically in half, the two halves
slide apart and away (fading as they go) and the unit that was inside is revealed.

the ball is ONE image (assets/ui/ball.png); this module cuts it into a left and a right half.
the unit is drawn first, underneath, so the halves uncover it as they move.
"""
import math

from . import config

IDLE = 0.8  # the whole ball sits there (with a little shake)
SPLIT = 0.35  # the halves open a gap and the unit shows through it
AWAY = 0.6  # the halves slide out and fade
MAX_GAP = 20  # how far apart the halves are when they start to leave
TRAVEL = 280  # how far each half travels on its way out


def split_vertically(img):
    """cut a surface into a left half and a right half (an odd width gives the right half the extra pixel)"""
    w, h = img.get_size()
    left = img.subsurface((0, 0, w // 2, h)).copy()
    right = img.subsurface((w // 2, 0, w - w // 2, h)).copy()
    return left, right


class Reveal:
    def __init__(self, unit, ui):
        self.unit = unit
        self.left, self.right = split_vertically(ui.ball())
        self.t = 0.0

    @property
    def duration(self):
        return IDLE + SPLIT + AWAY

    @property
    def done(self):
        return self.t >= self.duration

    def update(self, dt):
        self.t = min(self.t + dt, self.duration)

    def skip(self):
        self.t = self.duration

    def halves_state(self):
        """(gap, travel, alpha) of the two halves right now: gap is the space between them,
        travel is how far each has slid outward, alpha is 255 (solid) down to 0 (gone)"""
        t = self.t
        if t < IDLE:
            return 0.0, 0.0, 255
        t -= IDLE
        if t < SPLIT:
            p = t / SPLIT
            return MAX_GAP * (1 - (1 - p) ** 2), 0.0, 255  # opens fast, then eases
        p = min((t - SPLIT) / AWAY, 1.0)
        return float(MAX_GAP), TRAVEL * p * p, round(255 * (1 - p))  # speeds up as it fades

    def draw(self, surf, ui, center):
        cx, cy = center
        ui.draw_unit(surf, self.unit, cx, cy)  # underneath the ball the whole time
        if self.done:
            return
        gap, travel, alpha = self.halves_state()
        shake = round(3 * math.sin(self.t * 25)) if self.t < IDLE else 0
        for half, x in ((self.left, cx - self.left.get_width() - gap / 2 - travel), (self.right, cx + gap / 2 + travel)):
            half.set_alpha(alpha)
            surf.blit(half, (round(x) + shake, cy - half.get_height() // 2))
