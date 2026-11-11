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


def card_rect(cx, cy):
    r = pygame.Rect(0, 0, CARD_W, CARD_H)
    r.center = (cx, cy)
    return r


def pet_color(name):
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

    def pet_image(self, name):
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

    def draw_pet(self, surf, pet, cx, cy, selected=False, flip=False, flash=False):
        rect = card_rect(cx, cy)
        dead = pet.health <= 0
        body = (90, 90, 90) if dead else pet_color(pet.name)
        pygame.draw.rect(surf, body, rect, border_radius=12)
        border, width = ((255, 230, 90), 4) if selected else ((20, 20, 20), 2)
        pygame.draw.rect(surf, border, rect, width=width, border_radius=12)

        self.text(surf, pet.name, (cx, rect.top + 13), 20, (20, 20, 20))
        img = self.pet_image(pet.name)
        if img:
            if flip:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, img.get_rect(center=(cx, cy - 4)))
        else:  # placeholder: big initial letter
            self.text(surf, pet.name[0], (cx, cy - 4), 52, (30, 30, 30))

        if pet.level > 1:
            self.text(surf, f"Lv{pet.level}", (cx, rect.bottom - 18), 20, (20, 20, 20))
        for dx, val, col in ((20, pet.attack, (230, 150, 40)), (CARD_W - 20, max(pet.health, 0), (210, 60, 60))):
            center = (rect.left + dx, rect.bottom - 18)
            pygame.draw.circle(surf, col, center, 14)
            pygame.draw.circle(surf, (20, 20, 20), center, 14, 2)
            self.text(surf, val, center, 26, (255, 255, 255))

        if flash:
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(overlay, (255, 255, 255, 140), overlay.get_rect(), border_radius=12)
            surf.blit(overlay, rect)


class Button:
    def __init__(self, rect, label, color):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color = color
        self.enabled = True

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, surf, ui):
        col = self.color if self.enabled else (70, 70, 80)
        pygame.draw.rect(surf, col, self.rect, border_radius=10)
        pygame.draw.rect(surf, (20, 20, 20), self.rect, 2, border_radius=10)
        txt_col = (255, 255, 255) if self.enabled else (140, 140, 150)
        ui.text(surf, self.label, self.rect.center, 28, txt_col)
