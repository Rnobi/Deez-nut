import random
import sys
import pygame


from game import config
from game.battle import Battle
from game.battle_view import BattleView
from game.core import GameState
from game.opponents import generate_team
from game.ui import BG, UI, Button, card_rect, shop_center, team_center


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Discount Village")
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui = UI()
        self.rng = random.Random()
        self.state = GameState(self.rng)
        self.scene = "shop"  # shop/battle/gameover
        self.selected = None
        self.view = None
        self.reroll_btn = Button((700, 120, 200, 45), f"Reroll ({config.REROLL_COST}g)", (60, 110, 200))
        self.sell_btn = Button((490, 450, 200, 45), "Sell", (200, 120, 50))
        self.battle_btn = Button((700, 450, 200, 55), "End Turn", (190, 60, 60))

    # input handling -
    def handle_click(self, pos):
        if self.scene == "shop":
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
        for j, pet in enumerate(st.shop):
            if pet and card_rect(*shop_center(j)).collidepoint(pos):
                self.selected = None if self.selected == ("shop", j) else ("shop", j)
                return
        self.selected = None

    def click_team_slot(self, i):
        st, sel = self.state, self.selected
        if sel and sel[0] == "shop":
            st.buy(sel[1], i)
            self.selected = None
        elif sel and sel[0] == "team":
            if sel[1] != i and not st.merge_team(sel[1], i):
                st.swap(sel[1], i)
            self.selected = None
        elif st.team[i]:
            self.selected = ("team", i)

    # scene changes -
    def start_battle(self):
        st = self.state
        team = st.battle_team()
        if not team:
            st.message = "Buy at least one pet first!"
            return
        enemy = generate_team(st.turn, self.rng)
        self.view = BattleView(Battle(team, enemy))
        self.scene = "battle"
        self.selected = None

    def end_battle(self):
        self.state.finish_battle(self.view.battle.result())
        self.view = None
        self.scene = "shop" if self.state.status == "shop" else "gameover"

    def restart(self):
        self.state = GameState(self.rng)
        self.scene = "shop"
        self.selected = None

    # deltas -
    def update(self, dt):
        if self.scene == "battle":
            self.view.update(dt)

    def draw(self):
        s, ui, st = self.screen, self.ui, self.state
        if self.scene == "battle":
            self.view.draw(s, ui, st)
            return
        s.fill(BG)
        # top bar
        for x, label in ((110, f"Turn {st.turn}"), (330, f"Gold {st.gold}"),
                         (550, f"Lives {st.lives}"), (790, f"Wins {st.wins}/{config.WINS_TO_WIN}")):
            ui.text(s, label, (x, 35), 36)

        if self.scene == "gameover":
            won = st.status == "won"
            ui.text(s, "VICTORY" if won else "GAME OVER", (480, 220), 80)
            ui.text(s, f"Finished on turn {st.turn} with {st.wins} wins", (480, 300), 36)
            ui.text(s, "Press R to play again", (480, 360), 26, (180, 180, 190))
            return

        ui.text(s, "Shop", (530, 85), 26, (180, 180, 190))
        for j, pet in enumerate(st.shop):
            cx, cy = shop_center(j)
            if pet:
                ui.draw_pet(s, pet, cx, cy, selected=self.selected == ("shop", j))
                ui.text(s, f"{config.PET_COST}g", (cx, cy + 70), 26, (255, 215, 90))
            else:
                pygame.draw.rect(s, (45, 50, 68), card_rect(cx, cy), 2, border_radius=12)

        for i in range(config.TEAM_SIZE):
            cx, cy = team_center(i)
            pet = st.team[i]
            if pet:
                ui.draw_pet(s, pet, cx, cy, selected=self.selected == ("team", i))
            else:
                pygame.draw.rect(s, (45, 50, 68), card_rect(cx, cy), 2, border_radius=12)
        ui.text(s, "front", (team_center(0)[0], 410), 20, (140, 140, 150))
        ui.text(s, "back", (team_center(config.TEAM_SIZE - 1)[0], 410), 20, (140, 140, 150))

        self.refresh_buttons()
        for b in (self.reroll_btn, self.sell_btn, self.battle_btn):
            b.draw(s, ui)

        if st.message:
            ui.text(s, st.message, (480, 435), 26, (255, 215, 90))

    def run(self):
        while True:
            dt = self.clock.tick(config.FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f and self.scene == "battle":
                        self.view.toggle_speed()
                    if event.key == pygame.K_r and self.scene == "gameover":
                        self.restart()
            self.update(dt)
            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    App().run()
