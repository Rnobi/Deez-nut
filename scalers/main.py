import math
import random
import sys
import pygame


from game import config
from game.abilities import describe
from game.audio import MusicPlayer
from game.battle import Battle
from game.battle_view import BattleView
from game.core import GameState
from game.gacha_view import Reveal
from game.opponents import generate_team
from game.ui import BG, UI, Button, card_rect, item_center, shop_center, team_center
from game.units import random_unit

GACHA_CENTER = (480, 305)  # the summoning circle, the ball and the revealed unit all sit here


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui = UI()
        self.rng = random.Random()
        self.state = GameState(self.rng)
        self.scene = "menu"  # menu/gacha/create_pack/shop/battle/gameover
        self.selected = None
        self.view = None
        self.reroll_btn = Button((780, 125, 160, 45), f"Reroll ({config.REROLL_COST}g)", (60, 110, 200))
        self.sell_btn = Button((490, 450, 200, 45), "Sell", (200, 120, 50))
        self.battle_btn = Button((700, 450, 200, 55), "End Turn", (190, 60, 60))
        # start screen
        colors = [(60, 110, 200), (220, 140, 40), (140, 60, 170)]
        self.diff_btns = [
            (Button((150 + 230 * i, 250, 200, 60), d.name, colors[i % len(colors)]), d)
            for i, d in enumerate(config.DIFFICULTIES)
        ]
        # main: Play + Units. difficulty: Play is swapped for the 3 difficulty buttons.
        # units: Units is swapped for Gacha + Create Pack, side by side in the same spot
        self.menu_page = "main"
        self.play_btn = Button((360, 250, 240, 60), "Play", (60, 110, 200))
        self.units_btn = Button((360, 385, 240, 50), "Units", (50, 140, 140))
        self.gacha_btn = Button((265, 385, 200, 50), "Gacha", (210, 170, 50), text_color=(40, 28, 0))
        self.create_pack_btn = Button((495, 385, 200, 50), "Create Pack", (120, 100, 190))
        self.back_btn = Button((30, 486, 110, 34), "Back", (80, 85, 105), font_size=24)
        self.green_btn = Button((400, 470, 160, 32), "Green Mode: OFF", (0, 255, 0), text_color=(10, 40, 10), font_size=20)
        self.green_mode = False
        # endless mode: only offered (and only on) while green mode is on, right next to its button
        self.endless_btn = Button((570, 470, 160, 32), "Endless Mode: OFF", (255, 170, 40), text_color=(50, 25, 0), font_size=20)
        self.endless_mode = False
        self.reveal = None  # the gacha reveal animation in progress (None = the ball is waiting)
        self.green_overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        self.green_overlay.fill((0, 255, 0, config.GREEN_ALPHA))
        self.music = MusicPlayer()

    # input handling -
    def handle_click(self, pos):
        if self.scene == "menu":
            self.click_menu(pos)
        elif self.scene == "gacha":
            self.click_gacha(pos)
        elif self.scene == "create_pack":
            if self.back_btn.hit(pos):
                self.scene = "menu"
        elif self.scene == "shop":
            self.click_shop(pos)
        elif self.scene == "battle":
            if self.view.done:
                self.end_battle()
            else:
                self.view.toggle_speed()

    def refresh_buttons(self):
        st = self.state
        self.reroll_btn.enabled = st.gold >= config.REROLL_COST
        team_sel = self.selected and self.selected[0] == "team"
        self.sell_btn.enabled = bool(team_sel)
        if team_sel:
            self.sell_btn.label = f"Sell (+{st.team[self.selected[1]].sell_value}g)"
        else:
            self.sell_btn.label = "Sell"

    def click_shop(self, pos):
        st = self.state
        self.refresh_buttons()
        if self.reroll_btn.hit(pos):
            st.reroll()
            self.selected = None
            return
        if self.sell_btn.hit(pos):
            st.sell(self.selected[1])
            self.selected = None
            return
        if self.battle_btn.hit(pos):
            self.start_battle()
            return
        for i in range(config.TEAM_SIZE):
            if card_rect(*team_center(i)).collidepoint(pos):
                self.click_team_slot(i)
                return
        for j, unit in enumerate(st.shop):
            if unit and card_rect(*shop_center(j)).collidepoint(pos):
                self.selected = None if self.selected == ("shop", j) else ("shop", j)
                return
        for j, item in enumerate(st.items):
            if item and card_rect(*item_center(j)).collidepoint(pos):
                self.selected = None if self.selected == ("item", j) else ("item", j)
                return
        self.selected = None

    def click_team_slot(self, i):
        st, sel = self.state, self.selected
        if sel and sel[0] == "shop":
            st.buy(sel[1], i)
            self.selected = None
        elif sel and sel[0] == "item":
            st.buy_item(sel[1], i)
            self.selected = None
        elif sel and sel[0] == "team":
            if sel[1] != i and not st.merge_team(sel[1], i):
                st.swap(sel[1], i)
            self.selected = None
        elif st.team[i]:
            self.selected = ("team", i)

    def handle_right_click(self, pos):
        """right-click a shop unit or item to freeze/unfreeze it"""
        if self.scene != "shop":
            return
        st = self.state
        for j, unit in enumerate(st.shop):
            if unit and card_rect(*shop_center(j)).collidepoint(pos):
                st.toggle_freeze("shop", j)
                return
        for j, item in enumerate(st.items):
            if item and card_rect(*item_center(j)).collidepoint(pos):
                st.toggle_freeze("item", j)
                return

    def info_text(self):
        """description of whatever the mouse is over (or the selected item)"""
        st = self.state
        pos = pygame.mouse.get_pos()
        for i, unit in enumerate(st.team):
            if unit and card_rect(*team_center(i)).collidepoint(pos):
                return describe(unit)
        for j, unit in enumerate(st.shop):
            if unit and card_rect(*shop_center(j)).collidepoint(pos):
                return describe(unit)
        for j, item in enumerate(st.items):
            if item and card_rect(*item_center(j)).collidepoint(pos):
                return item.describe()
        if self.selected:
            kind, idx = self.selected
            thing = {"shop": st.shop, "item": st.items, "team": st.team}[kind][idx]
            if thing is not None:
                return describe(thing) if kind != "item" else thing.describe()
        return ""

    def click_menu(self, pos):
        if self.green_btn.hit(pos):
            self.green_mode = not self.green_mode
            if not self.green_mode:
                self.endless_mode = False  # endless mode only exists while green mode is on
            return
        if self.green_mode and self.endless_btn.hit(pos):
            self.endless_mode = not self.endless_mode
            return
        page = self.menu_page
        if page != "main" and self.back_btn.hit(pos):
            self.menu_page = "main"
            return
        if page == "units":  # Units has been replaced by Gacha + Create Pack
            if self.gacha_btn.hit(pos):
                self.scene = "gacha"
                self.reveal = None
                return
            if self.create_pack_btn.hit(pos):
                self.scene = "create_pack"
                return
        elif self.units_btn.hit(pos):
            self.menu_page = "units"
            return
        if page == "difficulty":  # Play has been replaced by the difficulty buttons
            for btn, diff in self.diff_btns:
                if btn.hit(pos):
                    self.start_game(diff)
                    return
        elif self.play_btn.hit(pos):
            self.menu_page = "difficulty"

    def click_gacha(self, pos):
        """Back leaves. clicking the ball previews the reveal with a random unit (a stand-in until the real
        gacha exists); clicking during it skips ahead, and clicking after it puts the ball back"""
        if self.back_btn.hit(pos):
            self.scene = "menu"
        elif self.reveal is None:
            if math.dist(pos, GACHA_CENTER) <= config.BALL_SIZE / 2:
                self.reveal = Reveal(random_unit(self.rng, 0, 99), self.ui)
        elif self.reveal.done:
            self.reveal = None
        else:
            self.reveal.skip()

    def escape(self):
        """Esc steps back on the sub-screens; returns True when the game should quit"""
        if self.scene in ("gacha", "create_pack"):
            self.scene = "menu"
        elif self.scene == "menu" and self.menu_page != "main":
            self.menu_page = "main"
        else:
            return True
        return False

    # scene changes -
    def start_game(self, difficulty, endless=None):
        endless = self.endless_mode if endless is None else endless
        self.state = GameState(self.rng, difficulty, endless=endless)
        self.scene = "shop"
        self.selected = None

    def back_to_menu(self):
        self.scene = "menu"
        self.menu_page = "main"
        self.selected = None

    def start_battle(self):
        st = self.state
        team = st.battle_team()
        if not team:
            st.message = "Buy at least one unit first!"
            return
        enemy = generate_team(st.turn, self.rng, st.difficulty, st.endless)
        self.view = BattleView(Battle(team, enemy, self.rng))
        self.scene = "battle"
        self.selected = None

    def end_battle(self):
        self.state.finish_battle(self.view.battle.result())
        self.view = None
        self.scene = "shop" if self.state.status == "shop" else "gameover"

    def restart(self):
        """play again on the same difficulty"""
        self.start_game(self.state.difficulty, endless=self.state.endless)

    # deltas -
    def update(self, dt):
        # music follows the scene (the game-over screen keeps the shop track)
        self.music.set_scene({"gameover": "shop"}.get(self.scene, self.scene))
        self.music.update()
        if self.scene == "battle":
            self.view.update(dt)
        elif self.scene == "gacha" and self.reveal:
            self.reveal.update(dt)

    def draw(self):
        """draw the current scene, then the green-mode overlay over everything"""
        self.draw_scene()
        if self.green_mode:
            self.screen.blit(self.green_overlay, (0, 0))

    def draw_menu(self):
        s, ui = self.screen, self.ui
        s.fill(BG)
        ui.text(s, config.TITLE, (480, 115), 80)
        if self.menu_page == "difficulty":
            ui.text(s, "Choose a difficulty to start", (480, 185), 28, (180, 180, 190))
            for btn, diff in self.diff_btns:
                btn.draw(s, ui)
                for k, line in enumerate(diff.blurb):
                    ui.text(s, line, (btn.rect.centerx, btn.rect.bottom + 20 + 20 * k), 20, (150, 150, 165))
        else:
            self.play_btn.draw(s, ui)
        if self.menu_page == "units":
            self.gacha_btn.draw(s, ui)
            self.create_pack_btn.draw(s, ui)
        else:
            self.units_btn.draw(s, ui)
        if self.menu_page != "main":
            self.back_btn.draw(s, ui)
        self.green_btn.label = f"Green Mode: {'ON' if self.green_mode else 'OFF'}"
        self.green_btn.selected = self.green_mode
        self.green_btn.draw(s, ui)
        if self.green_mode:
            self.endless_btn.label = f"Endless Mode: {'ON' if self.endless_mode else 'OFF'}"
            self.endless_btn.selected = self.endless_mode
            self.endless_btn.draw(s, ui)
        hint = "Esc to quit" if self.menu_page == "main" else "Esc to go back"
        ui.text(s, hint, (480, 520), 20, (120, 120, 135))

    def draw_gacha(self):
        s, ui = self.screen, self.ui
        s.fill(BG)
        ui.text(s, "Gacha", (480, 115), 80)
        ui.draw_summoning_circle(s, GACHA_CENTER)
        if self.reveal:
            self.reveal.draw(s, ui, GACHA_CENTER)
        else:
            ui.draw_ball(s, GACHA_CENTER)
        hint = "Click the ball to preview the reveal" if not self.reveal else \
            ("Click to put the ball back" if self.reveal.done else "Click to skip")
        ui.text(s, "Coming soon", (480, 472), 30, (180, 180, 190))
        ui.text(s, hint, (480, 497), 20, (140, 140, 155))
        self.back_btn.draw(s, ui)
        ui.text(s, "Esc to go back", (480, 520), 20, (120, 120, 135))

    def draw_create_pack(self):
        s, ui = self.screen, self.ui
        s.fill(BG)
        ui.text(s, "Create Pack", (480, 115), 80)
        ui.text(s, "Coming soon", (480, 270), 36, (180, 180, 190))
        self.back_btn.draw(s, ui)
        ui.text(s, "Esc to go back", (480, 520), 20, (120, 120, 135))

    def draw_scene(self):
        s, ui, st = self.screen, self.ui, self.state
        if self.scene == "menu":
            self.draw_menu()
            return
        if self.scene == "gacha":
            self.draw_gacha()
            return
        if self.scene == "create_pack":
            self.draw_create_pack()
            return
        if self.scene == "battle":
            self.view.draw(s, ui, st)
            return
        ui.draw_background(s, "shop")  # also behind the game-over screen
        # top bar
        for x, label in ((110, f"Turn {st.turn}"), (330, f"Gold {st.gold}"),
                         (550, f"Lives {st.lives}"), (790, f"Wins {st.wins}" + ("" if st.endless else f"/{config.WINS_TO_WIN}"))):
            ui.text(s, label, (x, 35), 36)
        ui.text(s, f"Tier {config.max_tier(st.turn)} shop", (110, 62), 22, (150, 150, 165))
        ui.text(s, "Endless" if st.endless else st.difficulty.name, (790, 62), 22, (150, 150, 165))

        if self.scene == "gameover":
            won = st.status == "won"
            ui.text(s, "VICTORY" if won else "GAME OVER", (480, 220), 80)
            ui.text(s, f"Finished on turn {st.turn} with {st.wins} wins", (480, 300), 36)
            ui.text(s, "R: play again   |   M: main menu", (480, 360), 26, (180, 180, 190))
            return

        ui.text(s, "Shop (right-click to freeze)", (550, 85), 26, (180, 180, 190))
        for j, unit in enumerate(st.shop):
            cx, cy = shop_center(j)
            if unit:
                ui.draw_unit(s, unit, cx, cy, selected=self.selected == ("shop", j), frozen=st.shop_frozen[j])
                ui.text(s, f"{config.UNIT_COST}g", (cx, cy + 70), 26, (255, 215, 90))
            elif j >= config.shop_size(st.turn):  # not unlocked yet
                pygame.draw.rect(s, (35, 38, 52), card_rect(cx, cy), 2, border_radius=12)
                ui.text(s, "Locked", (cx, cy - 8), 22, (110, 115, 135))
                ui.text(s, f"Turn {config.SHOP_SLOT_UNLOCK_TURN}", (cx, cy + 14), 20, (110, 115, 135))
            else:
                pygame.draw.rect(s, (45, 50, 68), card_rect(cx, cy), 2, border_radius=12)

        ui.text(s, "Items", (250, 85), 26, (180, 180, 190))
        for j, item in enumerate(st.items):
            cx, cy = item_center(j)
            if item:
                ui.draw_item(s, item, cx, cy, selected=self.selected == ("item", j), frozen=st.item_frozen[j])
                ui.text(s, f"{config.ITEM_COST}g", (cx, cy + 70), 26, (255, 215, 90))
            else:
                pygame.draw.rect(s, (45, 50, 68), card_rect(cx, cy), 2, border_radius=30)

        for i in range(config.TEAM_SIZE):
            cx, cy = team_center(i)
            unit = st.team[i]
            if unit:
                ui.draw_unit(s, unit, cx, cy, selected=self.selected == ("team", i))
            else:
                pygame.draw.rect(s, (45, 50, 68), card_rect(cx, cy), 2, border_radius=12)
        ui.text(s, "front", (team_center(0)[0], 410), 20, (140, 140, 150))
        ui.text(s, "back", (team_center(config.TEAM_SIZE - 1)[0], 410), 20, (140, 140, 150))

        self.refresh_buttons()
        for b in (self.reroll_btn, self.sell_btn, self.battle_btn):
            b.draw(s, ui)

        if st.message:
            ui.text(s, st.message, (480, 435), 26, (255, 215, 90))
        info = self.info_text()
        if info:
            size = 22 if len(info) <= 100 else 18
            lines = ui.wrap(info, size, 920)
            for k, line in enumerate(lines):  # long tooltips wrap; the block stays centred on y=522
                ui.text(s, line, (480, 522 - 9 * (len(lines) - 1) + 18 * k), size, (200, 200, 210))

    def run(self):
        while True:
            dt = self.clock.tick(config.FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.escape()):
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    self.handle_right_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f and self.scene == "battle":
                        self.view.toggle_speed()
                    if event.key == pygame.K_r and self.scene == "gameover":
                        self.restart()
                    if event.key == pygame.K_m and self.scene == "gameover":
                        self.back_to_menu()
            self.update(dt)
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    App().run()
