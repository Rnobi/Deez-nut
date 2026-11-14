import colorsys
import os

import pygame

from . import config

CARD_W, CARD_H = 90, 110
SPACING = 100
BG = (28, 32, 46)


def team_center(i):
    return 630 - SPACING * i, 340


def shop_center(j):
    return 430 + 100 * j, 150


def item_center(j):
    return 200 + 100 * j, 150


def card_rect(cx, cy):
    r = pygame.Rect(0, 0, CARD_W, CARD_H)
    r.center = (cx, cy)
    return r


def unit_color(name):
    hue = (sum(ord(c) * 31 for c in name) % 360) / 360
    r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.75)
    return int(r * 255), int(g * 255), int(b * 255)


class UI:
    def __init__(self):
        self.fonts = {}
        self._images = {}

    def text(self, surf, msg, pos, size=26, color=(235, 235, 235), center=True):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        img = self.fonts[size].render(str(msg), True, color)
        rect = img.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        surf.blit(img, rect)

    def wrap(self, text, size, max_width):
        """split text into lines that fit max_width, preferring to break between ' | ' parts"""
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(None, size)
        font = self.fonts[size]
        lines, line = [], ""
        for part in text.split(" | "):
            trial = f"{line} | {part}" if line else part
            if line and font.size(trial)[0] > max_width:
                lines.append(line)
                line = part
            else:
                line = trial
        lines.append(line)
        out = []  # a single part that is still too wide gets broken by words
        for ln in lines:
            cur = ""
            for word in ln.split(" "):
                trial = f"{cur} {word}" if cur else word
                if cur and font.size(trial)[0] > max_width:
                    out.append(cur)
                    cur = word
                else:
                    cur = trial
            out.append(cur)
        return out

    def unit_image(self, name):
        key = name.lower()
        if key not in self._images:
            img = None
            path = os.path.join(config.ASSET_DIR, key + ".png")
            if os.path.exists(path):
                try:
                    raw = pygame.image.load(path).convert_alpha()
                    k = min(70 / raw.get_width(), 56 / raw.get_height())
                    size = (max(1, int(raw.get_width() * k)), max(1, int(raw.get_height() * k)))
                    img = pygame.transform.smoothscale(raw, size)
                except pygame.error:
                    img = None
            self._images[key] = img
        return self._images[key]

    def draw_unit(self, surf, unit, cx, cy, selected=False, flip=False, flash=False, frozen=False):
        rect = card_rect(cx, cy)
        dead = unit.health <= 0
        body = (90, 90, 90) if dead else unit_color(unit.name)
        pygame.draw.rect(surf, body, rect, border_radius=12)
        border, width = ((255, 230, 90), 4) if selected else ((20, 20, 20), 2)
        pygame.draw.rect(surf, border, rect, width=width, border_radius=12)

        self.text(surf, unit.name, (cx, rect.top + 13), 20, (20, 20, 20))
        img = self.unit_image(unit.name)
        if img:
            if flip:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, img.get_rect(center=(cx, cy - 4)))
        else:  # placeholder: big initial letter
            self.text(surf, unit.name[0], (cx, cy - 4), 52, (30, 30, 30))

        if unit.level > 1:
            self.text(surf, f"Lv{unit.level}", (cx, rect.bottom - 18), 20, (20, 20, 20))
        for dx, val, col in ((20, unit.attack + unit.temp_attack, (230, 150, 40)),
                             (CARD_W - 20, max(unit.health + unit.temp_health, 0), (210, 60, 60))):
            center = (rect.left + dx, rect.bottom - 18)
            pygame.draw.circle(surf, col, center, 14)
            pygame.draw.circle(surf, (20, 20, 20), center, 14, 2)
            self.text(surf, val, center, 26, (255, 255, 255))

        # status dots down the left edge: poison, armor, item perk, temporary buff
        dots = []
        if unit.poison:
            dots.append((170, 60, 210))
        if unit.armor:
            dots.append((150, 175, 205))
        if unit.perks:
            dots.append((240, 200, 60))
        if unit.temp_attack or unit.temp_health:
            dots.append((60, 220, 230))
        for k, color in enumerate(dots):
            c = (rect.left + 9, rect.top + 34 + 12 * k)
            pygame.draw.circle(surf, color, c, 5)
            pygame.draw.circle(surf, (20, 20, 20), c, 5, 1)

        if flash:
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(overlay, (255, 255, 255, 140), overlay.get_rect(), border_radius=12)
            surf.blit(overlay, rect)
        if frozen:
            self.draw_frozen(surf, rect)

    def _load(self, path, fit, stretch=False):
        if not os.path.exists(path):
            return None
        try:
            raw = pygame.image.load(path).convert_alpha()
        except pygame.error:
            return None
        if stretch:
            size = fit
        else:
            k = min(fit[0] / raw.get_width(), fit[1] / raw.get_height())
            size = (max(1, int(raw.get_width() * k)), max(1, int(raw.get_height() * k)))
        return pygame.transform.smoothscale(raw, size)

    def background(self, name):
        """assets/backgrounds/<name>.png scaled to cover the window (cropped, not stretched), or None"""
        key = "bg:" + name
        if key not in self._images:
            img = None
            path = os.path.join(config.BG_DIR, name + ".png")
            if os.path.exists(path):
                try:
                    raw = pygame.image.load(path).convert()
                    k = max(config.WIDTH / raw.get_width(), config.HEIGHT / raw.get_height())
                    size = (max(config.WIDTH, round(raw.get_width() * k)), max(config.HEIGHT, round(raw.get_height() * k)))
                    big = pygame.transform.smoothscale(raw, size)
                    img = pygame.Surface((config.WIDTH, config.HEIGHT))
                    img.blit(big, ((config.WIDTH - size[0]) // 2, (config.HEIGHT - size[1]) // 2))
                except pygame.error:
                    img = None
            self._images[key] = img
        return self._images[key]

    def draw_background(self, surf, name):
        img = self.background(name)
        if img:
            surf.blit(img, (0, 0))
        else:
            surf.fill(BG)

    def item_image(self, name):
        key = "item:" + name.lower()
        if key not in self._images:
            self._images[key] = self._load(os.path.join(config.ITEM_ASSET_DIR, name.lower() + ".png"), (60, 46))
        return self._images[key]

    def freeze_image(self):
        if "freeze" not in self._images:
            path = os.path.join(config.UI_ASSET_DIR, "freeze.png")
            self._images["freeze"] = self._load(path, (CARD_W, CARD_H), stretch=True)
        return self._images["freeze"]

    def draw_item(self, surf, item, cx, cy, selected=False, frozen=False):
        rect = card_rect(cx, cy)
        pygame.draw.rect(surf, unit_color(item.name), rect, border_radius=30)
        border, width = ((255, 230, 90), 4) if selected else ((20, 20, 20), 2)
        pygame.draw.rect(surf, border, rect, width=width, border_radius=30)
        self.text(surf, item.name, (cx, rect.top + 16), 20, (20, 20, 20))
        img = self.item_image(item.name)
        if img:
            surf.blit(img, img.get_rect(center=(cx, cy - 4)))
        else:  # placeholder: big initial letter
            self.text(surf, item.name[0], (cx, cy - 4), 52, (30, 30, 30))
        self.text(surf, f"+{item.attack}/+{item.health}", (cx, rect.bottom - 20), 26, (20, 20, 20))
        if item.has_effect:  # gold dot: this item does something extra (hover for details)
            c = (rect.left + 13, rect.top + 40)
            pygame.draw.circle(surf, (240, 200, 60), c, 5)
            pygame.draw.circle(surf, (20, 20, 20), c, 5, 1)
        if frozen:
            self.draw_frozen(surf, rect, radius=30)

    def draw_frozen(self, surf, rect, radius=12):
        """freeze overlay: assets/ui/freeze.png stretched over the card, or an icy placeholder"""
        img = self.freeze_image()
        if img:
            surf.blit(img, rect.topleft)
            return
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (150, 210, 255, 110), overlay.get_rect(), border_radius=radius)
        pygame.draw.rect(overlay, (225, 245, 255, 230), overlay.get_rect(), 3, border_radius=radius)
        surf.blit(overlay, rect)
        self.text(surf, "FROZEN", (rect.centerx, rect.top + 31), 18, (235, 250, 255))


class Button:
    def __init__(self, rect, label, color, text_color=(255, 255, 255), font_size=28):
        self.rect = pygame.Rect(rect)
        self.font_size = font_size
        self.label = label
        self.color = color
        self.text_color = text_color
        self.selected = False  # draws a thick white outline (used by toggle buttons)
        self.enabled = True

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, surf, ui):
        col = self.color if self.enabled else (70, 70, 80)
        pygame.draw.rect(surf, col, self.rect, border_radius=10)
        pygame.draw.rect(surf, (20, 20, 20), self.rect, 2, border_radius=10)
        if self.selected:
            pygame.draw.rect(surf, (255, 255, 255), self.rect, 4, border_radius=10)
        txt_col = self.text_color if self.enabled else (140, 140, 150)
        ui.text(surf, self.label, self.rect.center, self.font_size, txt_col)
