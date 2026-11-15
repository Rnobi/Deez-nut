import os
import random
import sys
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import abilities, config, packs
from game.battle import Battle
from game.core import GameState
from game.items import Item
from game.opponents import generate_team
from game.units import Unit


class BattleTests(unittest.TestCase):
    def test_random_battles_terminate(self):
        rng = random.Random(1)
        for turn in range(1, 25):
            for _ in range(50):
                a = generate_team(turn, rng)
                b = generate_team(turn, rng)
                self.assertIn(Battle(a, b, rng).run_to_end(), ("win", "lose", "draw"))

    def test_stronger_team_wins(self):
        self.assertEqual(Battle([Unit("A", 5, 5)], [Unit("B", 1, 1)]).run_to_end(), "win")
        self.assertEqual(Battle([Unit("A", 1, 1)], [Unit("B", 5, 5)]).run_to_end(), "lose")

    def test_draw(self):
        self.assertEqual(Battle([Unit("A", 2, 2)], [Unit("B", 2, 2)]).run_to_end(), "draw")

    def test_input_teams_not_mutated(self):
        team = [Unit("A", 2, 2)]
        Battle(team, [Unit("B", 9, 9)]).run_to_end()
        self.assertEqual(team[0].health, 2)

    def test_zero_attack_stalemate_is_a_draw(self):
        b = Battle([Unit("Folk", 0, 10)], [Unit("Folk", 0, 10)])
        self.assertEqual(b.run_to_end(), "draw")

    def test_zero_attack_unit_still_loses_to_attacker(self):
        self.assertEqual(Battle([Unit("Folk", 0, 10)], [Unit("Ant", 2, 2)]).run_to_end(), "lose")

    # abilities -
    def test_start_of_battle_damage(self):
        b = Battle([Unit("Mosquito", 3, 1)], [Unit("Duck", 1, 4)])
        b.start()
        self.assertEqual(b.right[0].health, 3)
        self.assertTrue(b.log)

    def test_ability_scales_with_level(self):
        b = Battle([Unit("Mosquito", 3, 1, level=3)], [Unit("Duck", 1, 9)])
        b.start()
        self.assertEqual(b.right[0].health, 6)

    def test_start_abilities_fire_one_at_a_time(self):
        b = Battle([Unit("Mosquito", 2, 2) for _ in range(3)], [Unit("Duck", 1, 50)], random.Random(0))
        b.begin()
        for fired in (1, 2, 3):
            b.flash_queue.clear()
            self.assertTrue(b.fire_next())
            self.assertEqual(50 - b.right[0].health, fired)
            # both the attacker and the receiver are queued to flash
            self.assertEqual(len(b.flash_queue), 2)
            attacker, receiver = b.flash_queue
            self.assertEqual(attacker.name, "Mosquito")
            self.assertIs(receiver, b.right[0])
        self.assertFalse(b.fire_next())

    def test_faint_damage_flashes_receiver_and_chains(self):
        # Hedgehog faints and hits a random enemy; if that kills an Ant, the Ant's own faint fires too
        chained = 0
        for seed in range(30):
            b = Battle([Unit("Hedgehog", 1, 1), Unit("Duck", 1, 9)],
                       [Unit("Ant", 1, 1), Unit("Duck", 1, 50)], random.Random(seed))
            b.left[0].health = 0
            b.cleanup()
            self.assertEqual(len(b.left), 1)
            if len(b.right) == 1:  # the Ant died to the faint damage...
                chained += 1
                self.assertEqual(b.right[0].attack, 2)  # ...and its faint buffed the Duck
                self.assertTrue(any(p.name == "Hedgehog" for p in b.flash_queue))
        self.assertGreater(chained, 0)

    def test_every_mosquito_fires(self):
        for n in (1, 2, 3, 5):
            b = Battle([Unit("Mosquito", 2, 2) for _ in range(n)], [Unit("Duck", 1, 50)] * 3, random.Random(n))
            b.start()
            self.assertEqual(sum(50 - p.health for p in b.right), n)

    def test_start_runs_once(self):
        b = Battle([Unit("Mosquito", 3, 1)], [Unit("Duck", 1, 4)])
        b.start()
        b.start()
        self.assertEqual(b.right[0].health, 3)

    def test_start_ability_can_win_before_first_clash(self):
        self.assertEqual(Battle([Unit("Mosquito", 1, 1)], [Unit("Horse", 5, 1)]).run_to_end(), "win")

    def test_faint_buffs_ally(self):
        b = Battle([Unit("Ant", 1, 1), Unit("Cricket", 2, 5)], [Unit("Fish", 3, 9)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual(len(b.left), 1)
        self.assertEqual((b.left[0].attack, b.left[0].health), (3, 6))


class StateTests(unittest.TestCase):
    def setUp(self):
        self.st = GameState(random.Random(3))

    def test_buy_sell(self):
        self.assertTrue(self.st.buy(0, 0))
        self.assertEqual(self.st.gold, config.STARTING_GOLD - config.UNIT_COST)
        self.assertIsNone(self.st.shop[0])
        self.assertTrue(self.st.sell(0))
        self.assertIsNone(self.st.team[0])

    def test_cannot_overspend(self):
        self.st.gold = config.UNIT_COST - 1
        self.st.shop[0] = Unit("X", 1, 1)
        self.assertFalse(self.st.buy(0, 0))
        self.assertIsNone(self.st.team[0])

    def test_merge(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.shop[0] = Unit("Ant", 2, 2)
        self.assertTrue(self.st.buy(0, 0))
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health, self.st.team[0].level), (4, 4, 2))

    def test_no_merge_different_units_or_levels(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.shop[0] = Unit("Pig", 2, 4)
        self.assertFalse(self.st.buy(0, 0))
        self.st.shop[1] = Unit("Ant", 2, 2, level=2)
        self.assertFalse(self.st.buy(1, 0))

    def test_merge_team_units(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[3] = Unit("Ant", 4, 3)
        self.assertTrue(self.st.merge_team(0, 3))
        self.assertIsNone(self.st.team[0])
        merged = self.st.team[3]
        self.assertEqual((merged.attack, merged.health, merged.level), (6, 5, 2))

    def test_merge_team_rejects_different_or_maxed(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Pig", 2, 4)
        self.assertFalse(self.st.merge_team(0, 1))
        self.st.team[2] = Unit("Ant", 5, 5, level=config.MAX_LEVEL)
        self.assertFalse(self.st.merge_team(0, 2))
        self.assertFalse(self.st.merge_team(0, 0))
        self.assertFalse(self.st.merge_team(0, 4))  # empty target

    def test_reroll_costs_gold(self):
        self.assertTrue(self.st.reroll())
        self.assertEqual(self.st.gold, config.STARTING_GOLD - config.REROLL_COST)

    def test_lives_and_game_over(self):
        for _ in range(config.STARTING_LIVES):
            self.st.finish_battle("lose")
        self.assertEqual(self.st.status, "lost")

    def test_victory(self):
        for _ in range(config.WINS_TO_WIN):
            self.st.finish_battle("win")
        self.assertEqual(self.st.status, "won")

    def test_new_turn_resets_gold(self):
        self.st.buy(0, 0)
        self.st.finish_battle("draw")
        self.assertEqual(self.st.gold, config.STARTING_GOLD)
        self.assertEqual(self.st.turn, 2)

    # sell abilities -
    def test_sell_gold_ability(self):
        self.st.team[0] = Unit("Pig", 2, 4)
        self.st.sell(0)
        self.assertEqual(self.st.gold, config.STARTING_GOLD + 1 + 2)

    def test_sell_buff_ability(self):
        self.st.team[0] = Unit("Beaver", 2, 3)
        self.st.team[1] = Unit("Ant", 2, 2)
        self.st.sell(0)
        self.assertEqual((self.st.team[1].attack, self.st.team[1].health), (3, 3))

    # item -
    def test_buy_item(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.items[0] = Item("Meat", 3, 0)
        self.assertTrue(self.st.buy_item(0, 0))
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (5, 2))
        self.assertEqual(self.st.gold, config.STARTING_GOLD - config.ITEM_COST)
        self.assertIsNone(self.st.items[0])

    def test_item_needs_a_unit_and_gold(self):
        self.st.items[0] = Item("Apple", 1, 1)
        self.assertFalse(self.st.buy_item(0, 0))  # empty slot
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.gold = 0
        self.assertFalse(self.st.buy_item(0, 0))
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (2, 2))

    def test_item_buff_is_permanent_through_battle(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.items[0] = Item("Pear", 0, 3)
        self.st.buy_item(0, 0)
        Battle(self.st.battle_team(), [Unit("Fish", 3, 9)]).run_to_end()
        self.assertEqual(self.st.team[0].health, 5)

    # freeze -
    def test_freeze_survives_reroll_and_new_turn(self):
        kept_unit, kept_item = self.st.shop[1], self.st.items[0]
        self.st.toggle_freeze("shop", 1)
        self.st.toggle_freeze("item", 0)
        self.st.reroll()
        self.assertIs(self.st.shop[1], kept_unit)
        self.assertIs(self.st.items[0], kept_item)
        self.st.finish_battle("draw")
        self.assertIs(self.st.shop[1], kept_unit)
        self.assertIs(self.st.items[0], kept_item)

    def test_unfreeze_and_buying_clears_flag(self):
        self.st.toggle_freeze("shop", 0)
        self.assertTrue(self.st.shop_frozen[0])
        self.st.buy(0, 0)
        self.assertFalse(self.st.shop_frozen[0])
        self.assertIsNone(self.st.shop[0])
        self.assertFalse(self.st.toggle_freeze("shop", 0))  # empty slot can't freeze

    def test_reroll_refused_when_all_frozen(self):
        for j in range(config.SHOP_SIZE):
            self.st.toggle_freeze("shop", j)
        for j in range(config.ITEM_SHOP_SIZE):
            self.st.toggle_freeze("item", j)
        gold = self.st.gold
        self.assertFalse(self.st.reroll())
        self.assertEqual(self.st.gold, gold)


class PackTests(unittest.TestCase):
    def test_pack_size_and_tiers(self):
        pack = packs.STANDARD
        self.assertEqual(sorted(pack.units), [1, 2, 3, 4, 5])
        self.assertTrue(all(len(v) == 6 for v in pack.units.values()))
        self.assertEqual(sum(len(v) for v in pack.units.values()), 30)
        self.assertEqual(sorted(pack.items), [1, 2, 3, 4, 5, 6])
        self.assertTrue(all(len(v) == 2 for v in pack.items.values()))
        self.assertEqual(sum(len(v) for v in pack.items.values()), 12)

    def test_names_unique_and_abilities_valid(self):
        pack = packs.STANDARD
        units = [p[0] for tier in pack.units.values() for p in tier]
        items = [f[0] for tier in pack.items.values() for f in tier]
        self.assertEqual(len(set(units)), len(units))
        self.assertEqual(len(set(items)), len(items))
        for name, ability in abilities.ABILITIES.items():
            self.assertIn(name, units)
            self.assertIn(ability.effect, abilities.EFFECTS)
            self.assertIn(ability.trigger, abilities.TRIGGER_TEXT)

    def test_higher_tiers_are_stronger(self):
        avg = [sum(a + h for _, a, h in packs.STANDARD.units[t]) / 6 for t in range(1, 6)]
        self.assertEqual(avg, sorted(avg))
        avg = [sum(a + h for _, a, h in packs.STANDARD.items[t]) / 2 for t in range(1, 7)]
        self.assertEqual(avg, sorted(avg))

    def test_tier_unlock_turns_match_sap(self):
        expected = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 11: 6, 12: 6, 30: 6}
        for turn, tier in expected.items():
            self.assertEqual(config.max_tier(turn), tier, turn)

    def test_shop_only_offers_unlocked_tiers(self):
        for turn in (1, 2, 3, 5, 7, 9, 11, 14):
            st = GameState(random.Random(turn))
            st.turn = turn - 1
            st.start_turn()
            unit_tiers, item_tiers = set(), set()
            for _ in range(300):
                st.gold = 100
                st.reroll()
                unit_tiers |= {p.tier for p in st.shop if p}
                item_tiers |= {f.tier for f in st.items}
            top = config.max_tier(turn)
            self.assertEqual(max(item_tiers), top)
            self.assertEqual(max(unit_tiers), min(top, 5))  # the pack has no tier 6 units
            self.assertTrue(unit_tiers <= set(range(1, top + 1)))

    def test_enemies_use_unlocked_tiers(self):
        rng = random.Random(0)
        for turn in (1, 2, 3, 6, 9):
            tiers = {p.tier for _ in range(100) for p in generate_team(turn, rng)}
            self.assertTrue(tiers <= set(range(1, config.max_tier(turn) + 1)))

    def test_unlock_message(self):
        st = GameState(random.Random(1))
        st.finish_battle("draw")  # now turn 2: nothing new
        self.assertNotIn("unlocked", st.message)
        st.finish_battle("win")  # turn 3
        self.assertIn("Tier 2 unlocked", st.message)

    def test_describe_includes_tier(self):
        self.assertIn("Tier 3", abilities.describe(Unit("Badger", 5, 4, tier=3)))


class DifficultyTests(unittest.TestCase):
    NORMAL, HARD, RIGGED = config.DIFFICULTIES

    def test_three_difficulties_in_order(self):
        self.assertEqual([d.name for d in config.DIFFICULTIES], ["Normal", "Hard", "Rigged"])

    def test_normal_matches_the_original_scaling(self):
        rng = random.Random(0)
        for turn in range(1, 20):
            team = generate_team(turn, rng)  # no difficulty given -> Normal
            self.assertEqual(len(team), min(config.TEAM_SIZE, 2 + (turn + 1) // 2))
            self.assertEqual(config.stat_bonus(turn), max(0, (turn - 1) // 3))

    def test_enemies_get_stronger_with_difficulty(self):
        def avg_strength(diff, turn):
            rng = random.Random(7)
            teams = [generate_team(turn, rng, diff) for _ in range(300)]
            return sum(p.attack + p.health for t in teams for p in t) / len(teams)
        for turn in (3, 6, 10):
            n, h, r = (avg_strength(d, turn) for d in (self.NORMAL, self.HARD, self.RIGGED))
            self.assertLess(n, h, turn)
            self.assertLess(h, r, turn)

    def test_rigged_gets_full_teams_and_a_tier_ahead(self):
        rng = random.Random(1)
        self.assertEqual(len(generate_team(1, rng, self.RIGGED)), config.TEAM_SIZE)
        self.assertEqual(len(generate_team(1, rng, self.NORMAL)), 2 + 1)  # turn 1: 2 + (1+1)//2
        rigged_tiers = {p.tier for _ in range(200) for p in generate_team(1, rng, self.RIGGED)}
        normal_tiers = {p.tier for _ in range(200) for p in generate_team(1, rng, self.NORMAL)}
        self.assertEqual(normal_tiers, {1})
        self.assertEqual(rigged_tiers, {1, 2, 3})  # tier_boost=2: up to tier 3 on turn 1

    def test_stat_bonus_step(self):
        self.assertEqual(config.stat_bonus(7, 2, 3), 9)  # (7-1)//2 = 3 steps of +3
        self.assertEqual(config.stat_bonus(1, 1, 6), 0)  # nothing on turn 1
        self.assertEqual(config.stat_bonus(7), 2)  # defaults are the original Normal formula

    def test_tier_boost_never_exceeds_the_pack(self):
        rng = random.Random(2)
        tiers = {p.tier for _ in range(200) for p in generate_team(30, rng, self.RIGGED)}
        self.assertLessEqual(max(tiers), max(packs.STANDARD.units))

    def test_game_state_remembers_difficulty(self):
        self.assertIs(GameState(random.Random(0)).difficulty, self.NORMAL)
        self.assertIs(GameState(random.Random(0), self.HARD).difficulty, self.HARD)


class MenuTests(unittest.TestCase):
    """drives the real App headlessly (SDL dummy video driver)"""

    def setUp(self):
        import main
        self.app = main.App()

    def test_starts_on_the_menu(self):
        self.assertEqual(self.app.scene, "menu")
        self.app.draw()

    def open_difficulty_page(self):
        self.app.back_to_menu()
        self.app.handle_click(self.app.play_btn.rect.center)

    def test_each_difficulty_button_starts_that_difficulty(self):
        for btn, diff in self.app.diff_btns:
            self.open_difficulty_page()
            self.assertEqual(self.app.menu_page, "difficulty")
            self.app.handle_click(btn.rect.center)
            self.assertEqual(self.app.scene, "shop")
            self.assertIs(self.app.state.difficulty, diff)
            self.assertEqual(self.app.state.turn, 1)

    def test_difficulty_buttons_are_hidden_until_play_is_clicked(self):
        app = self.app
        self.assertEqual(app.menu_page, "main")
        app.handle_click(app.diff_btns[0][0].rect.center)  # Normal's spot does nothing yet
        self.assertEqual(app.scene, "menu")
        app.handle_click(app.play_btn.rect.center)
        self.assertEqual(app.menu_page, "difficulty")
        self.assertEqual(app.scene, "menu")  # Play alone does not start a game

    def test_play_is_replaced_by_the_difficulty_buttons_in_the_same_spot(self):
        app = self.app
        mid = app.diff_btns[1][0]
        self.assertEqual(mid.rect.center, app.play_btn.rect.center)
        self.assertEqual(mid.rect.y, app.play_btn.rect.y)
        app.draw()
        probe = (400, 255)  # inside Play, and inside the middle difficulty button
        self.assertEqual(tuple(app.screen.get_at(probe))[:3], app.play_btn.color)
        app.handle_click(app.play_btn.rect.center)
        app.draw()
        self.assertEqual(tuple(app.screen.get_at(probe))[:3], mid.color)  # Play is gone, Hard is there
        app.handle_click(app.back_btn.rect.center)
        self.assertEqual(app.menu_page, "main")

    def open_units_page(self):
        self.app.back_to_menu()
        self.app.handle_click(self.app.units_btn.rect.center)

    def color_at(self, pos):
        return tuple(self.app.screen.get_at(pos))[:3]

    def test_layout_units_below_play_and_green_smaller_and_lowest(self):
        app = self.app
        ys = {btn.rect.y for btn, _ in app.diff_btns}
        xs = [btn.rect.x for btn, _ in app.diff_btns]
        self.assertEqual(len(ys), 1)  # one horizontal row
        self.assertEqual(xs, sorted(xs))
        self.assertGreater(app.units_btn.rect.top, max(b.rect.bottom for b, _ in app.diff_btns) + 40)  # clear of the blurbs
        self.assertGreater(app.green_btn.rect.top, app.units_btn.rect.bottom)
        gb, ub = app.green_btn.rect, app.units_btn.rect
        self.assertLess(gb.width * gb.height, ub.width * ub.height)  # green mode is the smaller one
        self.assertEqual(app.green_btn.color, (0, 255, 0))

    def test_units_is_replaced_by_gacha_and_create_pack_in_the_same_spot(self):
        app = self.app
        app.draw()
        probe_a, probe_b = (365, 392), (500, 392)  # inside Units, and inside Gacha / Create Pack respectively
        self.assertEqual(self.color_at(probe_a), app.units_btn.color)
        self.assertEqual(self.color_at(probe_b), app.units_btn.color)
        app.handle_click(app.units_btn.rect.center)
        self.assertEqual(app.menu_page, "units")
        self.assertEqual(app.scene, "menu")  # Units alone opens nothing
        app.draw()
        self.assertEqual(self.color_at(probe_a), app.gacha_btn.color)
        self.assertEqual(self.color_at(probe_b), app.create_pack_btn.color)
        # side by side on the same row, centred where Units was
        g, c, u = app.gacha_btn.rect, app.create_pack_btn.rect, app.units_btn.rect
        self.assertEqual(g.y, u.y)
        self.assertEqual(c.y, u.y)
        self.assertLess(g.right, c.left)
        self.assertEqual((g.left + c.right) / 2, u.centerx)

    def test_gacha_and_create_pack_open_their_empty_scenes(self):
        app = self.app
        self.open_units_page()
        app.handle_click(app.gacha_btn.rect.center)
        self.assertEqual(app.scene, "gacha")
        app.draw()
        app.handle_click(app.back_btn.rect.center)
        self.assertEqual(app.scene, "menu")
        self.assertEqual(app.menu_page, "units")  # comes back to the units page
        app.handle_click(app.create_pack_btn.rect.center)
        self.assertEqual(app.scene, "create_pack")
        app.draw()
        app.handle_click(app.back_btn.rect.center)
        self.assertEqual(app.scene, "menu")
        self.assertEqual(app.menu_page, "units")

    def test_play_and_units_pages_swap_each_other_out(self):
        app = self.app
        self.open_units_page()
        app.handle_click(app.play_btn.rect.center)  # Play still works from the units page
        self.assertEqual(app.menu_page, "difficulty")
        app.draw()  # the Units button is back
        app.handle_click(app.units_btn.rect.center)
        self.assertEqual(app.menu_page, "units")
        app.handle_click(app.back_btn.rect.center)
        self.assertEqual(app.menu_page, "main")

    def test_back_to_menu_resets_the_page(self):
        self.open_units_page()
        self.app.start_game(config.DIFFICULTIES[0])
        self.app.back_to_menu()
        self.assertEqual((self.app.scene, self.app.menu_page), ("menu", "main"))

    def test_escape_steps_back_then_quits(self):
        app = self.app
        self.assertTrue(app.escape())  # main menu: quit
        self.open_difficulty_page()
        self.assertFalse(app.escape())
        self.assertEqual(app.menu_page, "main")
        self.open_units_page()
        self.assertFalse(app.escape())
        self.assertEqual(app.menu_page, "main")
        for scene in ("gacha", "create_pack"):
            app.scene = scene
            self.assertFalse(app.escape())
            self.assertEqual(app.scene, "menu")

    def test_gacha_and_create_pack_have_their_own_music_slots(self):
        for scene in ("gacha", "create_pack"):
            self.app.music.key = None
            self.app.scene = scene
            self.app.update(0.016)
            self.assertEqual(self.app.music.key, scene)  # no longer borrowing the menu slot
            self.assertIn(scene, config.BGM)
        self.app.music.key = None
        self.app.scene = "gameover"
        self.app.update(0.016)
        self.assertEqual(self.app.music.key, "shop")  # the game-over screen keeps the shop track

    def test_green_mode_toggles_and_overlays_every_scene(self):
        from game.ui import BG
        self.app.draw()
        self.assertEqual(tuple(self.app.screen.get_at((5, 5)))[:3], BG)
        self.app.handle_click(self.app.green_btn.rect.center)
        self.assertTrue(self.app.green_mode)
        self.app.draw()
        px = tuple(self.app.screen.get_at((5, 5)))[:3]
        self.assertGreater(px[1], BG[1] + 30)  # more green than the plain background
        self.assertLess(px[0], BG[0])  # and the other channels were tinted down, not brightened
        # still there in the shop and in battle
        self.app.start_game(config.DIFFICULTIES[0])
        self.app.draw()
        self.assertGreater(tuple(self.app.screen.get_at((5, 5)))[1], BG[1] + 30)
        self.app.state.team[0] = Unit("Ant", 2, 2)
        self.app.start_battle()
        self.app.draw()
        self.assertGreater(tuple(self.app.screen.get_at((5, 5)))[1], BG[1] + 30)
        # and toggles back off
        self.app.scene = "menu"
        self.app.handle_click(self.app.green_btn.rect.center)
        self.app.draw()
        self.assertEqual(tuple(self.app.screen.get_at((5, 5)))[:3], BG)

    def test_replay_keeps_difficulty_and_menu_key_returns(self):
        hard = config.DIFFICULTIES[1]
        self.app.start_game(hard)
        self.app.restart()
        self.assertIs(self.app.state.difficulty, hard)
        self.assertEqual(self.app.scene, "shop")
        self.app.back_to_menu()
        self.assertEqual(self.app.scene, "menu")

    def test_battle_uses_the_chosen_difficulty(self):
        self.app.start_game(config.DIFFICULTIES[2])
        self.app.state.team[0] = Unit("Ant", 2, 2)
        self.app.start_battle()
        self.assertEqual(len(self.app.view.battle.right), config.TEAM_SIZE)


def make_wav(path, seconds=0.3):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * int(22050 * seconds))


class DefaultPackTests(unittest.TestCase):
    def test_the_default_pack_is_the_standard_pack_the_game_uses(self):
        from game import units as unit_defs
        self.assertIs(packs.DEFAULT_PACK, packs.STANDARD)
        self.assertIs(unit_defs.PACK, packs.DEFAULT_PACK)

    def test_the_default_pack_cannot_be_edited(self):
        pack = packs.DEFAULT_PACK
        with self.assertRaises(TypeError):
            pack.units[1] = ()
        with self.assertRaises(TypeError):
            pack.units[1][0] = ("X", 1, 1)
        with self.assertRaises(TypeError):
            pack.items[7] = ()
        with self.assertRaises(TypeError):
            pack.tokens["Nope"] = (1, 1)
        with self.assertRaises(AttributeError):
            pack.name = "Mine"
        with self.assertRaises(AttributeError):
            pack.units = {}
        with self.assertRaises(AttributeError):
            pack.units[1].append(("X", 1, 1))  # tiers are tuples, nothing can be appended

    def test_a_built_pack_ignores_later_edits_to_its_source(self):
        source = {1: [("A", 1, 1)]}
        pack = packs.Pack("Test", source, {})
        source[1].append(("B", 1, 1))
        source[2] = [("C", 1, 1)]
        self.assertEqual(len(pack.units[1]), 1)
        self.assertNotIn(2, pack.units)
        self.assertEqual(pack.units_up_to(5), [(1, "A", 1, 1)])


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.old_dir = config.BG_DIR
        config.BG_DIR = self.tmp

    def tearDown(self):
        config.BG_DIR = self.old_dir

    def save_png(self, name, color, size=(100, 50)):
        import pygame
        pygame.init()
        surf = pygame.Surface(size)
        surf.fill(color)
        pygame.image.save(surf, os.path.join(self.tmp, name + ".png"))

    def test_missing_files_fall_back_to_plain_background(self):
        import main
        from game.ui import BG
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.draw()
        self.assertEqual(tuple(app.screen.get_at((5, 530)))[:3], BG)

    def test_shop_and_battle_backgrounds(self):
        import main
        self.save_png("shop", (200, 0, 0))
        self.save_png("battle", (0, 0, 200), size=(1920, 1080))  # big image: still covers the window
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.draw()
        self.assertEqual(tuple(app.screen.get_at((5, 530)))[:3], (200, 0, 0))
        self.assertEqual(tuple(app.screen.get_at((955, 5)))[:3], (200, 0, 0))
        app.state.team[0] = Unit("Ant", 2, 2)
        app.start_battle()
        app.draw()
        self.assertEqual(tuple(app.screen.get_at((5, 530)))[:3], (0, 0, 200))
        self.assertEqual(tuple(app.screen.get_at((955, 5)))[:3], (0, 0, 200))

    def test_odd_aspect_ratio_is_cropped_not_stretched(self):
        import pygame
        import main
        pygame.init()
        surf = pygame.Surface((100, 400))  # tall and narrow
        surf.fill((0, 200, 0))
        pygame.image.save(surf, os.path.join(self.tmp, "shop.png"))
        app = main.App()
        img = app.ui.background("shop")
        self.assertEqual(img.get_size(), (config.WIDTH, config.HEIGHT))
        self.assertEqual(tuple(img.get_at((0, 0)))[:3], (0, 200, 0))
        self.assertEqual(tuple(img.get_at((config.WIDTH - 1, config.HEIGHT - 1)))[:3], (0, 200, 0))

    def test_green_overlay_still_covers_backgrounds(self):
        import main
        self.save_png("shop", (200, 0, 0))
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.green_mode = True
        app.draw()
        r, g, b = tuple(app.screen.get_at((5, 530)))[:3]
        self.assertGreater(g, 60)
        self.assertLess(r, 200)


class MusicTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from game import audio
        self.audio = audio
        self.tmp = tempfile.mkdtemp()
        self.old = (config.MUSIC_DIR, dict(config.BGM))
        config.MUSIC_DIR = self.tmp
        config.BGM.update({"default": None, "menu": None, "shop": None, "battle": None})
        self.player = audio.MusicPlayer()
        if not self.player.ok:
            self.skipTest("no audio device available")

    def tearDown(self):
        self.player.stop()
        config.MUSIC_DIR, saved = self.old
        config.BGM.clear()
        config.BGM.update(saved)

    def path(self, name):
        return os.path.join(self.tmp, name)

    def test_silent_when_nothing_is_set(self):
        for scene in ("menu", "shop", "battle"):
            self.player.set_scene(scene)
            self.assertIsNone(self.player.playing)

    def test_dropin_file_per_scene(self):
        make_wav(self.path("shop.wav"))
        make_wav(self.path("battle.wav"))
        self.player.set_scene("shop")
        self.assertEqual(self.player.playing, self.path("shop.wav"))
        self.player.set_scene("battle")
        self.assertEqual(self.player.playing, self.path("battle.wav"))
        self.player.set_scene("menu")  # no music for the menu
        self.assertIsNone(self.player.playing)

    def test_resolution_order(self):
        make_wav(self.path("bgm.wav"))
        make_wav(self.path("menu.wav"))
        make_wav(self.path("named.wav"))
        config.BGM["battle"] = "named.wav"
        self.assertEqual(self.audio.resolve("menu"), ("file", self.path("menu.wav")))  # drop-in beats everything
        self.assertEqual(self.audio.resolve("battle"), ("file", self.path("named.wav")))  # config file name
        self.assertEqual(self.audio.resolve("shop"), ("file", self.path("bgm.wav")))  # bgm fallback
        os.remove(self.path("bgm.wav"))
        config.BGM["default"] = "http://example.com/a.mp3"
        self.assertEqual(self.audio.resolve("shop"), ("url", "http://example.com/a.mp3"))  # default link

    def test_same_track_keeps_playing_across_scenes(self):
        make_wav(self.path("bgm.wav"))
        self.player.set_scene("shop")
        first = self.player.playing
        self.player.set_scene("battle")
        self.assertEqual(self.player.playing, first)

    def test_broken_file_does_not_crash_or_retry_forever(self):
        with open(self.path("shop.mp3"), "wb") as f:
            f.write(b"this is not audio")
        self.player.set_scene("shop")
        self.assertIsNone(self.player.playing)
        self.player.update()  # still fine

    def test_unplayable_file_falls_back_to_the_next_source(self):
        with open(self.path("battle.ogg"), "wb") as f:  # an Ogg-looking file that is not Vorbis
            f.write(b"OggS" + b"\x00" * 40)
        make_wav(self.path("bgm.wav"))
        self.player.set_scene("battle")
        self.assertEqual(self.player.playing, self.path("bgm.wav"))

    def test_other_format_next_to_a_bad_ogg_wins(self):
        with open(self.path("battle.ogg"), "wb") as f:
            f.write(b"not audio")
        make_wav(self.path("battle.wav"))
        self.player.set_scene("battle")
        self.assertEqual(self.player.playing, self.path("battle.wav"))

    def test_unplayable_file_message_is_plain_english_and_printed_once(self):
        import contextlib
        import io
        with open(self.path("battle.ogg"), "wb") as f:
            f.write(b"OggS" + b"\x00" * 40)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.player.set_scene("battle")
            self.player.key = None
            self.player.set_scene("battle")  # same bad file again: not retried or re-reported
        text = out.getvalue()
        self.assertIn("can't play battle.ogg", text)
        self.assertIn(".mp3", text)
        self.assertEqual(text.count("can't play"), 1)

    def test_dead_link_falls_back_to_bgm_file(self):
        base = self.serve({})
        config.BGM["shop"] = base + "/gone.mp3"
        make_wav(self.path("bgm.wav"))
        self.player.set_scene("shop")
        # the dead link is never played; the fallback starts as soon as the link has failed
        self.assertTrue(self.wait_until(lambda: self.player.playing == self.path("bgm.wav")))

    def serve(self, routes):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in routes:
                    ctype, body = routes[self.path]
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def wait_until(self, cond, seconds=5):
        import time
        end = time.time() + seconds
        while time.time() < end:
            self.player.update()
            if cond():
                return True
            time.sleep(0.02)
        return False

    def test_link_downloads_then_plays_and_is_cached(self):
        make_wav(self.path("src.wav"))
        with open(self.path("src.wav"), "rb") as f:
            body = f.read()
        base = self.serve({"/song.wav": ("audio/wav", body)})
        config.BGM["shop"] = base + "/song.wav"
        self.player.set_scene("shop")  # returns immediately; the download runs on a thread
        self.assertTrue(self.wait_until(lambda: self.player.playing is not None))
        self.assertTrue(self.player.playing.startswith(os.path.join(self.tmp, "cache")))
        # a fresh player finds it in the cache without any network
        self.player.stop()
        again = self.audio.MusicPlayer()
        again.set_scene("shop")
        self.assertIsNotNone(again.playing)  # cached from the first download, so it plays immediately

    def test_link_without_extension_uses_content_type(self):
        make_wav(self.path("src.wav"))
        with open(self.path("src.wav"), "rb") as f:
            body = f.read()
        base = self.serve({"/stream": ("audio/x-wav", body)})
        config.BGM["menu"] = base + "/stream"
        self.player.set_scene("menu")
        self.assertTrue(self.wait_until(lambda: self.player.playing is not None))
        self.assertTrue(self.player.playing.endswith(".wav"))

    def test_bad_links_fail_quietly(self):
        base = self.serve({"/page": ("text/html", b"<html>not audio</html>")})
        for link in (base + "/missing.mp3", base + "/page"):
            config.BGM["shop"] = link
            self.player.key = None
            self.player.set_scene("shop")
            self.assertTrue(self.wait_until(lambda: self.player._links.get(link) == "failed"))
            self.assertIsNone(self.player.playing)


class EveryAbilityTests(unittest.TestCase):
    def test_every_unit_has_an_ability(self):
        names = [p[0] for tier in packs.STANDARD.units.values() for p in tier]
        self.assertEqual([n for n in names if n not in abilities.ABILITIES], [])

    def test_perks_and_item_effects_are_valid(self):
        from game import items as item_defs
        for ability in abilities.PERKS.values():
            self.assertIn(ability.effect, abilities.EFFECTS)
            self.assertIn(ability.trigger, abilities.TRIGGER_TEXT)
        item_names = [i[0] for tier in packs.STANDARD.items.values() for i in tier]
        for name, eff in item_defs.ITEM_EFFECTS.items():
            self.assertIn(name, item_names)
            self.assertIn(eff.kind, item_defs.EFFECT_KINDS)
            if eff.kind == "perk":
                self.assertIn(eff.perk, abilities.PERKS)
            self.assertTrue(item_defs.effect_text(eff))
        # every item can be described and drawn
        for tier in packs.STANDARD.items.values():
            for name, a, h in tier:
                self.assertIn(name, Item(name, a, h).describe())

    # new unit abilities -
    def test_duck_sell_buffs_shop_units(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Duck", 1, 4)
        before = [p.health for p in st.shop if p]
        st.sell(0)
        self.assertEqual([p.health for p in st.shop if p], [h + 1 for h in before])

    def test_fish_level_up_buffs_allies(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Fish", 3, 2)
        st.team[1] = Unit("Ant", 2, 2)
        st.shop[0] = Unit("Fish", 3, 2)
        self.assertTrue(st.buy(0, 0))  # merge -> level 2 -> +2/+2 to the others
        self.assertEqual((st.team[1].attack, st.team[1].health), (4, 4))
        st.team[2] = Unit("Fish", 3, 2)
        st.team[3] = Unit("Fish", 3, 2)
        self.assertTrue(st.merge_team(3, 2))  # merging two team units triggers it too
        self.assertEqual((st.team[1].attack, st.team[1].health), (6, 6))

    def test_horse_buffs_the_unit_you_buy(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Horse", 4, 2)
        st.shop[0] = Unit("Ant", 2, 2)
        st.buy(0, 1)
        self.assertEqual(st.team[1].attack, 3)
        self.assertEqual(st.team[0].attack, 4)  # the Horse itself is unchanged

    def test_crab_copies_health(self):
        b = Battle([Unit("Crab", 3, 5), Unit("Cow", 6, 10)], [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual(b.left[0].health, 5 + 10 * 25 // 100)

    def test_kangaroo_grows_when_the_friend_ahead_attacks(self):
        b = Battle([Unit("Ant", 1, 9), Unit("Kangaroo", 5, 5)], [Unit("Duck", 1, 50)])
        b.start()
        b.clash()
        self.assertEqual((b.left[1].attack, b.left[1].health), (7, 7))
        b.clash()
        self.assertEqual((b.left[1].attack, b.left[1].health), (9, 9))

    def test_hippo_knock_out(self):
        b = Battle([Unit("Hippo", 6, 7)], [Unit("Ant", 1, 1), Unit("Duck", 1, 50)])
        b.start()
        b.clash()
        self.assertEqual((b.left[0].attack, b.left[0].health), (8, 8))  # took 1, then +2/+2
        # no knock-out bonus if the hippo itself went down
        b = Battle([Unit("Hippo", 6, 1)], [Unit("Ant", 1, 1), Unit("Duck", 1, 50)])
        b.start()
        b.clash()
        self.assertEqual(b.left[0].attack, 6)

    def test_scorpion_poison_kills_anything_it_damages(self):
        b = Battle([Unit("Scorpion", 1, 10)], [Unit("Cow", 1, 90)])
        self.assertEqual(b.run_to_end(), "win")
        b = Battle([Unit("Scorpion", 0, 10)], [Unit("Cow", 1, 90)])  # 0 attack: no damage, no poison kill
        b.start()
        b.clash()
        self.assertEqual(b.right[0].health, 90)

    # armor -
    def test_armor_reduces_damage_but_never_below_one(self):
        b = Battle([Unit("Ant", 5, 10)], [Unit("Duck", 1, 10, armor=2)])
        b.clash()
        self.assertEqual(b.right[0].health, 7)
        b = Battle([Unit("Ant", 2, 10)], [Unit("Duck", 1, 10, armor=5)])
        b.clash()
        self.assertEqual(b.right[0].health, 9)
        b = Battle([Unit("Ant", 0, 10)], [Unit("Duck", 1, 10, armor=5)])
        b.clash()
        self.assertEqual(b.right[0].health, 10)

    def test_random_battles_with_all_new_mechanics_terminate(self):
        rng = random.Random(5)
        for turn in range(1, 25):
            for diff in config.DIFFICULTIES:
                for _ in range(8):
                    a = generate_team(turn, rng, diff)
                    for p in a:  # sprinkle in the item-given mechanics
                        p.armor = rng.randint(0, 3)
                        p.perk = rng.choice(["", "honey", "steak"])
                    b = generate_team(turn, rng, diff)
                    self.assertIn(Battle(a, b, rng).run_to_end(), ("win", "lose", "draw"))


class SummonTests(unittest.TestCase):
    def names(self, team):
        return [p.name for p in team]

    def test_only_pig_still_gives_gold_on_sell(self):
        gold_units = [n for n, a in abilities.ABILITIES.items() if a.effect == "gain_gold"]
        self.assertEqual(gold_units, ["Pig"])
        for name in ("Turtle", "Cow"):
            self.assertEqual(abilities.ABILITIES[name].effect, "summon")

    def test_template_is_valid(self):
        from game.units import ROSTER, PACK
        for name, ability in abilities.ABILITIES.items():
            if ability.effect == "summon":
                self.assertIn(ability.arg, PACK.tokens)
                self.assertGreaterEqual(ability.amount, 1)
        unit_names = {p[0] for p in ROSTER}
        self.assertFalse(unit_names & set(PACK.tokens))  # tokens never clash with shop units
        self.assertEqual(len(ROSTER), 30)  # tokens are not part of the 30

    # faint: the token takes the fainted unit's own slot
    def test_faint_summon_replaces_the_unit_in_its_slot(self):
        b = Battle([Unit("Turtle", 2, 1), Unit("Ant", 2, 2)], [Unit("Fish", 5, 50)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual(self.names(b.left), ["Shell", "Ant"])
        self.assertEqual((b.left[0].attack, b.left[0].health), (2, 4))
        self.assertTrue(any("summoned 1 Shell" in line for line in b.log))

    def test_two_identical_fainting_summoners_each_fill_their_own_slot(self):
        b = Battle([Unit("Turtle", 2, 8), Unit("Ant", 2, 2), Unit("Turtle", 2, 8)], [Unit("Fish", 5, 50)])
        b.left[0].health = 0
        b.left[2].health = 0
        b.cleanup()
        self.assertEqual(self.names(b.left), ["Shell", "Ant", "Shell"])

    def test_enemies_summon_too(self):
        b = Battle([Unit("Fish", 9, 50)], [Unit("Turtle", 1, 1)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual(self.names(b.right), ["Shell"])
        self.assertFalse(b.is_over())  # the fight goes on against the token

    def test_summon_stats_scale_with_level(self):
        b = Battle([Unit("Turtle", 2, 1, level=2)], [Unit("Fish", 5, 50)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual((b.left[0].attack, b.left[0].health), (4, 8))
        self.assertEqual(b.left[0].level, 1)  # tokens start at level 1
        self.assertIn("summon 1 Shell (4/8)", abilities.describe(Unit("Turtle", 2, 8, level=2)))

    # start of battle: tokens appear right behind the summoner
    # (no standard unit summons at the start of battle any more, so these use a made-up one)
    SUMMONER = {"Summoner": abilities.Ability(abilities.START_OF_BATTLE, "summon", 2, "Shell")}

    def test_start_summon_goes_behind_the_summoner(self):
        with mock.patch.dict(abilities.ABILITIES, self.SUMMONER):
            b = Battle([Unit("Summoner", 4, 8), Unit("Ant", 2, 2)], [Unit("Duck", 1, 50)])
            b.start()
        self.assertEqual(self.names(b.left), ["Summoner", "Shell", "Shell", "Ant"])
        self.assertEqual((b.left[1].attack, b.left[1].health), (2, 4))

    def test_nothing_is_summoned_onto_a_full_team(self):
        team = [Unit("Summoner", 4, 8)] + [Unit("Ant", 2, 2) for _ in range(config.TEAM_SIZE - 1)]
        with mock.patch.dict(abilities.ABILITIES, self.SUMMONER):
            b = Battle(team, [Unit("Duck", 1, 50)])
            b.start()
            self.assertEqual(len(b.left), config.TEAM_SIZE)
            self.assertTrue(any("no room" in line for line in b.log))
            # one free slot -> only one of the two shells fits
            b = Battle(team[:-1], [Unit("Duck", 1, 50)])
            b.start()
        self.assertEqual(len(b.left), config.TEAM_SIZE)
        self.assertEqual(self.names(b.left).count("Shell"), 1)

    def test_a_full_team_never_exceeds_the_limit_in_random_battles(self):
        rng = random.Random(11)
        for turn in range(1, 20):
            for diff in config.DIFFICULTIES:
                a, b = generate_team(turn, rng, diff), generate_team(turn, rng, diff)
                battle = Battle(a, b, rng)
                battle.start()
                while not battle.is_over():
                    battle.clash()
                    battle.cleanup()
                    self.assertLessEqual(len(battle.left), config.TEAM_SIZE)
                    self.assertLessEqual(len(battle.right), config.TEAM_SIZE)

    def test_summoner_and_tokens_flash(self):
        with mock.patch.dict(abilities.ABILITIES, self.SUMMONER):
            b = Battle([Unit("Summoner", 4, 8)], [Unit("Duck", 1, 50)])
            b.begin()
            b.flash_queue.clear()
            self.assertTrue(b.fire_next())
        flashed = [p.name for p in b.flash_queue]
        self.assertEqual(flashed, ["Summoner", "Shell", "Shell"])

    # sell: the token goes into the sold unit's slot
    def test_sell_summon_fills_the_sold_slot_and_pays_normal_sell_value(self):
        st = GameState(random.Random(1))
        st.team[2] = Unit("Cow", 6, 10)
        st.sell(2)
        self.assertEqual(st.team[2].name, "Calf")
        self.assertEqual((st.team[2].attack, st.team[2].health), (4, 4))
        self.assertEqual(st.gold, config.STARTING_GOLD + 1)  # just the level-1 sell value, no bonus gold
        self.assertIn("summoned 1 Calf", st.message)

    def test_sell_summon_scales_and_uses_a_free_slot_if_needed(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Cow", 6, 10, level=3)
        st.sell(0)
        self.assertEqual((st.team[0].attack, st.team[0].health), (12, 12))

    def test_summoned_tokens_are_real_units(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Cow", 6, 10)
        st.team[1] = Unit("Cow", 6, 10)
        st.sell(0)
        st.sell(1)
        self.assertEqual(self.names(st.team[:2]), ["Calf", "Calf"])
        self.assertTrue(st.merge_team(0, 1))  # two Calves merge like any units
        self.assertEqual(st.team[1].level, 2)

    def test_summon_effect_is_safe_without_a_summoner(self):
        ctx = abilities.Context(random.Random(0), [])
        ctx.ability = abilities.ABILITIES["Turtle"]
        self.assertIsNone(abilities.EFFECTS["summon"][0](Unit("Turtle", 1, 1), 1, ctx))

    def test_tokens_describe_and_draw(self):
        import main
        self.assertIn("Token", abilities.describe(Unit("Calf", 4, 4, tier=0)))
        self.assertIn("no ability", abilities.describe(Unit("Calf", 4, 4, tier=0)))
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.state.team[0] = Unit("Shell", 2, 4, tier=0)
        app.draw()


class ItemEffectTests(unittest.TestCase):
    def setUp(self):
        self.st = GameState(random.Random(2))
        self.st.team[0] = Unit("Ant", 2, 2)

    def use(self, name, a=0, h=0, tier=1, slot=0):
        self.st.items[0] = Item(name, a, h, tier)
        self.assertTrue(self.st.buy_item(0, slot))

    def test_plain_items_only_give_stats(self):
        self.use("Apple", 1, 1)
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (3, 3))
        self.assertEqual(self.st.team[0].perk, "")

    def test_cupcake_is_temporary_and_lasts_one_battle(self):
        self.use("Cupcake", 2, 2)
        unit = self.st.team[0]
        self.assertEqual((unit.attack, unit.health, unit.temp_attack, unit.temp_health), (4, 4, 3, 3))
        fighter = self.st.battle_team()[0]
        self.assertEqual((fighter.attack, fighter.health), (7, 7))
        self.st.finish_battle("draw")
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (4, 4))  # back to normal
        self.assertEqual((self.st.team[0].temp_attack, self.st.team[0].temp_health), (0, 0))

    def test_cheese_buffs_the_shop(self):
        before = [(p.attack, p.health) for p in self.st.shop if p]
        self.use("Cheese", 2, 3)
        self.assertEqual([(p.attack, p.health) for p in self.st.shop if p], [(a + 1, h + 1) for a, h in before])

    def test_carrot_gives_armor_that_stacks(self):
        self.use("Carrot", 3, 2)
        self.assertEqual(self.st.team[0].armor, 2)
        self.use("Carrot", 3, 2)
        self.assertEqual(self.st.team[0].armor, 4)

    def test_honey_perk_buffs_an_ally_on_faint(self):
        self.use("Honey", 2, 4)
        self.assertEqual(self.st.team[0].perk, "honey")
        self.use("Honey", 2, 4)  # using it again does not stack
        self.assertEqual(self.st.team[0].perk, "honey")
        b = Battle([Unit("Duck", 1, 1, perk="honey"), Unit("Cow", 6, 10)], [Unit("Fish", 5, 50)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual((b.left[0].attack, b.left[0].health), (8, 12))

    def test_steak_perk_hits_an_enemy_at_the_start(self):
        b = Battle([Unit("Duck", 1, 5, perk="steak")], [Unit("Cow", 1, 20)])
        b.start()
        self.assertEqual(b.right[0].health, 17)

    def test_sushi_and_pizza_buff_random_other_units(self):
        for i in range(1, 5):
            self.st.team[i] = Unit("Duck", 1, 4)
        self.use("Sushi", 4, 4)
        buffed = [p for p in self.st.team[1:] if p.attack == 2]
        self.assertEqual(len(buffed), 3)  # exactly 3 of the 4 others
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (6, 6))  # fed unit: just the item's stats
        self.use("Pizza", 5, 3)
        self.assertEqual(sum(p.attack >= 3 for p in self.st.team[1:]), 2)

    def test_salad_buffs_every_other_unit(self):
        self.st.team[1] = Unit("Duck", 1, 4)
        self.st.team[2] = Unit("Pig", 2, 4)
        self.use("Salad", 5, 5)
        self.assertEqual((self.st.team[1].attack, self.st.team[1].health), (3, 6))
        self.assertEqual((self.st.team[2].attack, self.st.team[2].health), (4, 6))

    def test_chocolate_levels_the_unit_up_and_fires_level_up(self):
        self.st.team[1] = Unit("Fish", 3, 2)
        self.use("Chocolate", 7, 3, tier=6, slot=1)
        fish = self.st.team[1]
        self.assertEqual(fish.level, 2)
        self.assertEqual((fish.attack, fish.health), (3 + 7 + 2, 2 + 3 + 2))
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (4, 4))  # Fish buffed its ally
        self.st.team[2] = Unit("Duck", 1, 4, level=config.MAX_LEVEL)
        self.use("Chocolate", 7, 3, tier=6, slot=2)
        self.assertEqual(self.st.team[2].level, config.MAX_LEVEL)
        self.assertIn("max level", self.st.message)

    def test_items_need_a_unit_and_gold(self):
        self.st.items[0] = Item("Salad", 5, 5, 6)
        self.assertFalse(self.st.buy_item(0, 3))  # empty slot
        self.assertEqual(self.st.gold, config.STARTING_GOLD)
        self.st.gold = 0
        self.assertFalse(self.st.buy_item(0, 0))
        self.assertEqual(self.st.team[0].attack, 2)

    def test_a_merged_unit_still_has_only_one_perk(self):
        a = Unit("Ant", 2, 2, perk="honey", armor=1)
        b = Unit("Ant", 3, 3, perk="steak", armor=2)
        a.merge(b)
        self.assertEqual(a.perk, "honey")  # its own perk wins; perks never combine
        self.assertEqual(a.armor, 2)
        a, b = Unit("Ant", 2, 2), Unit("Ant", 3, 3, perk="steak")
        a.merge(b)
        self.assertEqual(a.perk, "steak")  # no perk of its own: it takes the other's

    def test_describe_shows_perks_armor_and_temp_buffs(self):
        unit = Unit("Ant", 2, 2, armor=2, perk="honey", temp_attack=3, temp_health=3)
        text = abilities.describe(unit)
        for part in ("Honey perk", "Armor 2", "+3/+3 until the end"):
            self.assertIn(part, text)
        self.assertIn("Faint", Item("Honey", 2, 4, 4).describe())
        self.assertNotIn("and", Item("Apple", 1, 1).describe())


class ItemUITests(unittest.TestCase):
    def setUp(self):
        import main
        self.app = main.App()
        self.app.start_game(config.DIFFICULTIES[0])

    def test_click_item_then_unit_uses_it(self):
        from game.ui import card_rect, item_center, team_center
        st = self.app.state
        st.team[0] = Unit("Ant", 2, 2)
        st.items[0] = Item("Apple", 1, 1)
        self.app.handle_click(card_rect(*item_center(0)).center)
        self.assertEqual(self.app.selected, ("item", 0))
        self.app.draw()
        self.app.handle_click(card_rect(*team_center(0)).center)
        self.assertEqual((st.team[0].attack, st.team[0].health), (3, 3))

    def test_right_click_freezes_an_item(self):
        from game.ui import card_rect, item_center
        self.app.handle_right_click(card_rect(*item_center(1)).center)
        self.assertTrue(self.app.state.item_frozen[1])
        self.app.draw()

    def test_long_tooltips_wrap_to_fit_the_window(self):
        unit = Unit("Scorpion", 9, 7, tier=5, armor=2, poison=True, perk="steak", temp_attack=3, temp_health=3)
        text = abilities.describe(unit)
        lines = self.app.ui.wrap(text, 18, 920)
        self.assertGreater(len(lines), 1)
        font = self.app.ui.fonts[18]
        self.assertTrue(all(font.size(line)[0] <= 920 for line in lines))
        self.assertEqual(" ".join(lines).replace("  ", " ").count("perk"), text.count("perk"))  # nothing lost
        short = self.app.ui.wrap("Ant (Tier 1, Lv1) - Faint: give a random ally +1/+1", 22, 920)
        self.assertEqual(len(short), 1)

    def test_cards_with_every_status_draw_and_label_says_items(self):
        st = self.app.state
        st.team[0] = Unit("Scorpion", 9, 7, tier=5, armor=2, poison=True, perk="honey", temp_attack=3, temp_health=3)
        st.items[0] = Item("Honey", 2, 4, 4)
        self.app.selected = ("team", 0)
        self.app.draw()
        self.assertGreater(len(self.app.ui.fonts), 0)
        self.assertEqual(self.app.state.items[0].name, "Honey")


class PerkRuleTests(unittest.TestCase):
    """a unit has one perk at a time; the latest one replaces the old one and perks never stack"""

    def setUp(self):
        self.st = GameState(random.Random(2))
        self.st.team[0] = Unit("Duck", 2, 2)  # no battle ability of its own, so only the perk shows

    def use(self, name, a=0, h=0, tier=1):
        self.st.items[0] = Item(name, a, h, tier)
        self.assertTrue(self.st.buy_item(0, 0))

    def test_a_unit_has_a_single_perk_field(self):
        unit = Unit("Ant", 2, 2)
        self.assertEqual(unit.perk, "")
        self.assertFalse(hasattr(unit, "perks"))

    def test_the_newest_perk_replaces_the_old_one(self):
        self.use("Honey", 2, 4, 4)
        self.assertEqual(self.st.team[0].perk, "honey")
        self.use("Steak", 4, 2, 4)
        self.assertEqual(self.st.team[0].perk, "steak")
        self.assertIn("swapped its honey perk for steak", self.st.message)
        self.use("Honey", 2, 4, 4)  # and back again: still just one
        self.assertEqual(self.st.team[0].perk, "honey")

    def test_only_the_active_perk_does_anything(self):
        self.use("Honey", 2, 4, 4)
        self.use("Steak", 4, 2, 4)  # honey is gone
        fighter = self.st.team[0]
        b = Battle([fighter, Unit("Cow", 6, 10)], [Unit("Fish", 5, 50)])
        b.start()
        self.assertEqual(b.right[0].health, 47)  # steak: 3 damage at the start
        fighter = b.left[0]
        fighter.health = 0
        b.cleanup()
        self.assertEqual((b.left[0].attack, b.left[0].health), (6, 10))  # no honey buff on faint

    def test_using_the_same_perk_twice_does_not_stack_its_effect(self):
        self.use("Steak", 4, 2, 4)
        self.use("Steak", 4, 2, 4)
        self.assertIn("already had the steak perk", self.st.message)
        b = Battle([self.st.team[0]], [Unit("Cow", 1, 20)])
        b.start()
        self.assertEqual(b.right[0].health, 17)  # 3 damage once, not 6
        self.use("Honey", 2, 4, 4)
        self.use("Honey", 2, 4, 4)
        b = Battle([Unit("Duck", 1, 1, perk="honey"), Unit("Cow", 6, 10)], [Unit("Fish", 5, 50)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual((b.left[0].attack, b.left[0].health), (8, 12))  # +2/+2 once

    def test_describe_lists_one_perk(self):
        text = abilities.describe(Unit("Ant", 2, 2, perk="steak"))
        self.assertIn("Steak perk", text)
        self.assertNotIn("Honey", text)
        self.assertIn("replacing its current perk", Item("Honey", 2, 4, 4).describe())


class StatCapTests(unittest.TestCase):
    def test_creating_a_unit_caps_its_stats(self):
        unit = Unit("Ant", 150, 120)
        self.assertEqual((unit.attack, unit.health), (99, 99))
        self.assertEqual(config.STAT_CAP, 99)

    def test_every_way_of_gaining_stats_is_capped(self):
        unit = Unit("Ant", 98, 98)
        unit.attack += 50
        unit.health += 1000
        self.assertEqual((unit.attack, unit.health), (99, 99))
        merged = Unit("Ant", 98, 98)
        merged.merge(Unit("Ant", 98, 98))  # max + 2
        self.assertEqual((merged.attack, merged.health, merged.level), (99, 99, 2))
        self.assertEqual((unit.copy().attack, unit.copy().health), (99, 99))

    def test_items_and_abilities_cannot_break_the_cap(self):
        st = GameState(random.Random(1))
        st.team[0] = Unit("Ant", 98, 98)
        st.team[1] = Unit("Fish", 99, 99)
        st.items[0] = Item("Salad", 5, 5, 6)
        st.buy_item(0, 0)
        self.assertEqual((st.team[0].attack, st.team[0].health), (99, 99))
        self.assertEqual((st.team[1].attack, st.team[1].health), (99, 99))  # Salad buffed it, capped
        b = Battle([Unit("Giraffe", 3, 6), Unit("Ant", 99, 99)], [Unit("Duck", 1, 50)])
        b.left[0].health = 0
        b.cleanup()
        b = Battle([Unit("Bison", 6, 6), Unit("Ant", 99, 99)], [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual((b.left[1].attack, b.left[1].health), (99, 99))

    def test_temporary_buffs_are_capped_in_battle(self):
        unit = Unit("Ant", 99, 99, temp_attack=10, temp_health=10)
        fighter = unit.battle_copy()
        self.assertEqual((fighter.attack, fighter.health), (99, 99))

    def test_health_can_still_drop_to_zero_and_below(self):
        b = Battle([Unit("Ant", 99, 99)], [Unit("Duck", 99, 5)])
        b.clash()
        self.assertEqual(b.right[0].health, -94)
        self.assertEqual(b.left[0].health, 0)

    def test_late_game_enemies_are_capped_too(self):
        rng = random.Random(3)
        for diff in config.DIFFICULTIES:
            for turn in (1, 10, 30, 60, 100):
                for u in generate_team(turn, rng, diff):
                    self.assertLessEqual(u.attack, 99)
                    self.assertLessEqual(u.health, 99)
        team = generate_team(80, rng, config.DIFFICULTIES[2])
        self.assertTrue(all((u.attack, u.health) == (99, 99) for u in team))  # Rigged by turn 80 is all 99/99

    def test_summons_are_capped(self):
        ability = abilities.ABILITIES["Cow"]
        self.assertEqual(ability.effect, "summon")
        calf = Unit("Calf", 4 * 50, 4 * 50, tier=0)
        self.assertEqual((calf.attack, calf.health), (99, 99))


class MusicSlotTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from game import audio
        self.audio = audio
        self.tmp = tempfile.mkdtemp()
        self.old = (config.MUSIC_DIR, dict(config.BGM))
        config.MUSIC_DIR = self.tmp
        for key in config.BGM:
            config.BGM[key] = None

    def tearDown(self):
        config.MUSIC_DIR, saved = self.old
        config.BGM.clear()
        config.BGM.update(saved)

    def make(self, name):
        make_wav(os.path.join(self.tmp, name))
        return os.path.join(self.tmp, name)

    def test_slots_exist_in_the_config(self):
        for key in ("gacha", "create_pack"):
            self.assertIn(key, config.BGM)

    def test_each_page_has_its_own_dropin_slot(self):
        gacha, pack, menu = self.make("gacha.wav"), self.make("create_pack.wav"), self.make("menu.wav")
        self.assertEqual(self.audio.resolve("gacha"), ("file", gacha))
        self.assertEqual(self.audio.resolve("create_pack"), ("file", pack))
        self.assertEqual(self.audio.resolve("menu"), ("file", menu))

    def test_config_slots_work_for_both_pages(self):
        a, b = self.make("a.wav"), self.make("b.wav")
        config.BGM["gacha"] = "a.wav"
        config.BGM["create_pack"] = "b.wav"
        self.assertEqual(self.audio.resolve("gacha"), ("file", a))
        self.assertEqual(self.audio.resolve("create_pack"), ("file", b))
        config.BGM["gacha"] = "https://example.com/gacha.mp3"
        self.assertEqual(self.audio.resolve("gacha"), ("url", "https://example.com/gacha.mp3"))

    def test_unset_pages_fall_back_to_the_menu_track_then_bgm(self):
        menu = self.make("menu.wav")
        self.assertEqual(self.audio.resolve("gacha"), ("file", menu))
        self.assertEqual(self.audio.resolve("create_pack"), ("file", menu))
        os.remove(menu)
        bgm = self.make("bgm.wav")
        self.assertEqual(self.audio.resolve("gacha"), ("file", bgm))  # no menu track: the shared bgm
        self.assertEqual(self.audio.resolve("shop"), ("file", bgm))
        config.BGM["default"] = "https://example.com/d.mp3"
        self.assertEqual(self.audio.resolve("gacha"), ("file", bgm))  # bgm file still beats the default link
        os.remove(bgm)
        self.assertEqual(self.audio.resolve("gacha"), ("url", "https://example.com/d.mp3"))
        config.BGM["default"] = None
        self.assertIsNone(self.audio.resolve("gacha"))

    def test_shop_and_battle_do_not_fall_back_to_the_menu_track(self):
        self.make("menu.wav")
        self.assertIsNone(self.audio.resolve("shop"))
        self.assertIsNone(self.audio.resolve("battle"))


class UnitArtTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pygame
        pygame.init()
        self.pygame = pygame
        self.tmp = tempfile.mkdtemp()
        self.old = config.ASSET_DIR
        config.ASSET_DIR = self.tmp

    def tearDown(self):
        config.ASSET_DIR = self.old

    def save(self, name, color, size):
        surf = self.pygame.Surface(size)
        surf.fill(color)
        self.pygame.image.save(surf, os.path.join(self.tmp, name + ".png"))

    def test_art_fills_the_whole_card_with_rounded_corners(self):
        from game.ui import CARD_H, CARD_W
        import main
        self.save("ant", (200, 0, 0), (20, 60))  # tall and narrow: covered and cropped, not stretched or letterboxed
        img = main.App().ui.unit_image("Ant")
        self.assertEqual(img.get_size(), (CARD_W, CARD_H))
        self.assertEqual(img.get_at((0, 0)).a, 0)  # the corner is rounded off
        self.assertEqual(tuple(img.get_at((CARD_W // 2, CARD_H // 2))), (200, 0, 0, 255))
        self.assertEqual(tuple(img.get_at((CARD_W - 8, 8)))[:3], (200, 0, 0))  # right up to the edges
        self.assertEqual(tuple(img.get_at((8, CARD_H - 8)))[:3], (200, 0, 0))

    def test_art_is_drawn_behind_the_name_and_stats(self):
        from game.ui import card_rect, team_center
        import main
        self.save("ant", (200, 0, 0), (90, 110))
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.state.team[0] = Unit("Ant", 2, 2)
        app.draw()
        rect = card_rect(*team_center(0))
        px = lambda p: tuple(app.screen.get_at(p))[:3]
        self.assertEqual(px((rect.right - 6, rect.top + 18)), (200, 0, 0))  # art reaches the top-right corner area
        self.assertEqual(px((rect.left + 40, rect.bottom - 6)), (200, 0, 0))  # and the bottom edge
        self.assertEqual(px((rect.left + 20, rect.bottom - 18 - 10)), (230, 150, 40))  # the attack circle is on top of the art
        cx = rect.centerx  # the name is on top too: some white outline-text pixels inside the name strip
        strip = [px((x, y)) for x in range(cx - 30, cx + 30) for y in range(rect.top + 6, rect.top + 20)]
        self.assertTrue(any(c == (255, 255, 255) for c in strip))

    def corner_pixel(self, app, slot):
        from game.ui import card_rect, team_center
        rect = card_rect(*team_center(slot))
        return tuple(app.screen.get_at((rect.right - 6, rect.top + 18)))[:3]

    def test_cards_without_art_keep_the_plain_coloured_card(self):
        from game.ui import unit_color
        import main
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.state.team[0] = Unit("Ant", 2, 2)
        app.draw()
        self.assertEqual(self.corner_pixel(app, 0), unit_color("Ant"))  # no art: just the card body

    def test_dead_units_with_art_are_shaded_and_the_enemy_side_flips(self):
        import main
        self.save("ant", (200, 0, 0), (50, 50))
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.state.team[0] = Unit("Ant", 2, 2)
        app.state.team[1] = Unit("Ant", 2, 0)  # dead
        app.draw()
        alive, dead = self.corner_pixel(app, 0), self.corner_pixel(app, 1)
        self.assertEqual(alive, (200, 0, 0))
        self.assertLess(dead[0], alive[0])  # shaded darker
        # an asymmetric image drawn on the enemy side (flip=True) is mirrored left/right
        surf = self.pygame.Surface((90, 110))
        surf.fill((0, 0, 200))
        self.pygame.draw.rect(surf, (250, 250, 0), (0, 40, 30, 30))  # a yellow block on the left edge
        self.pygame.image.save(surf, os.path.join(self.tmp, "duck.png"))
        app = main.App()
        left_probe, right_probe = (480 - 45 + 8, 300), (480 + 45 - 8, 300)
        app.ui.draw_unit(app.screen, Unit("Duck", 1, 4), 480, 300, flip=False)
        normal = (tuple(app.screen.get_at(left_probe))[:3], tuple(app.screen.get_at(right_probe))[:3])
        app.ui.draw_unit(app.screen, Unit("Duck", 1, 4), 480, 300, flip=True)
        flipped = (tuple(app.screen.get_at(left_probe))[:3], tuple(app.screen.get_at(right_probe))[:3])
        self.assertEqual(normal[0], (250, 250, 0))
        self.assertEqual(flipped[1], (250, 250, 0))
        self.assertNotEqual(normal, flipped)


class FreezeOverlayTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pygame
        pygame.init()
        self.pygame = pygame
        self.tmp = tempfile.mkdtemp()
        self.old = config.UI_ASSET_DIR
        config.UI_ASSET_DIR = self.tmp

    def tearDown(self):
        config.UI_ASSET_DIR = self.old

    def save(self, name, color, size):
        surf = self.pygame.Surface(size)
        surf.fill(color)
        self.pygame.image.save(surf, os.path.join(self.tmp, name + ".png"))

    def test_freeze_png_is_slightly_larger_than_the_card_at_half_opacity(self):
        from game.ui import CARD_H, CARD_W
        import main
        self.save("freeze", (0, 0, 200), (40, 40))
        img = main.App().ui.freeze_image()
        w, h = img.get_size()
        self.assertGreater(w, CARD_W)
        self.assertGreater(h, CARD_H)
        self.assertLess(w, CARD_W * 1.3)  # "slightly" larger
        self.assertAlmostEqual(w, CARD_W * config.FREEZE_SCALE, delta=1)
        self.assertAlmostEqual(h, CARD_H * config.FREEZE_SCALE, delta=1)
        self.assertAlmostEqual(img.get_at((w // 2, h // 2)).a, 255 * config.FREEZE_OPACITY, delta=1)
        self.assertEqual(config.FREEZE_OPACITY, 0.5)

    def test_it_is_centred_on_the_card_and_overhangs_it(self):
        from game.ui import BG, card_rect, shop_center
        import main
        self.save("freeze", (0, 0, 200), (40, 40))
        app = main.App()
        app.start_game(config.DIFFICULTIES[0])
        app.state.shop[0] = Unit("Ant", 2, 2)
        app.state.shop_frozen[0] = True
        app.draw()
        rect = card_rect(*shop_center(0))
        px = lambda p: tuple(app.screen.get_at(p))[:3]
        just_outside = px((rect.right + 3, rect.centery))  # inside the overhang, in the gap before the next card
        self.assertGreater(just_outside[2], BG[2] + 40)  # tinted blue
        self.assertEqual(px((rect.right + 9, rect.centery)), BG)  # beyond the overhang: untouched
        self.assertGreater(px((rect.left - 4, rect.centery))[2], BG[2] + 40)  # same on the left: it is centred

    def test_missing_png_falls_back_to_the_placeholder(self):
        import main
        app = main.App()
        self.assertIsNone(app.ui.freeze_image())
        app.start_game(config.DIFFICULTIES[0])
        app.state.shop_frozen[0] = True
        app.draw()


class SummoningCircleTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pygame
        pygame.init()
        self.pygame = pygame
        self.tmp = tempfile.mkdtemp()
        self.old = config.UI_ASSET_DIR
        config.UI_ASSET_DIR = self.tmp

    def tearDown(self):
        config.UI_ASSET_DIR = self.old

    def test_png_slot_is_fitted_and_centred_on_the_gacha_scene(self):
        from game.ui import BG
        import main
        surf = self.pygame.Surface((500, 200))
        surf.fill((0, 200, 0))
        self.pygame.image.save(surf, os.path.join(self.tmp, "summoning_circle.png"))
        app = main.App()
        img = app.ui.summoning_circle()
        self.assertEqual(img.get_size(), (config.SUMMONING_CIRCLE_SIZE, round(200 * config.SUMMONING_CIRCLE_SIZE / 500)))
        app.scene = "gacha"
        app.draw()
        centre = tuple(app.screen.get_at((480 - 100, 305)))[:3]  # beside the ball, which sits in the middle
        for got, want in zip(centre, (0, 200, 0)):
            self.assertAlmostEqual(got, want, delta=8)  # smooth scaling can shift a flat colour slightly
        self.assertEqual(tuple(app.screen.get_at((480, 205)))[:3], BG)  # outside the fitted height

    def test_placeholder_ring_when_there_is_no_png(self):
        import main
        app = main.App()
        self.assertIsNone(app.ui.summoning_circle())
        app.scene = "gacha"
        app.draw()
        r = config.SUMMONING_CIRCLE_SIZE // 2
        row = [tuple(app.screen.get_at((480 - r + dx, 305)))[:3] for dx in range(0, 4)]
        self.assertIn((70, 80, 112), row)  # the ring is there


class GachaBallTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pygame
        pygame.init()
        self.pygame = pygame
        self.tmp = tempfile.mkdtemp()
        self.old = config.UI_ASSET_DIR
        config.UI_ASSET_DIR = self.tmp

    def tearDown(self):
        config.UI_ASSET_DIR = self.old

    def save_ball(self, size=(200, 200), color=(0, 0, 200)):
        surf = self.pygame.Surface(size)
        surf.fill(color)
        self.pygame.image.save(surf, os.path.join(self.tmp, "ball.png"))

    def app(self):
        import main
        return main.App()

    # the slot -
    def test_png_is_fitted_inside_the_ball_size(self):
        self.save_ball((300, 100))
        img = self.app().ui.ball()
        self.assertEqual(img.get_size(), (config.BALL_SIZE, round(100 * config.BALL_SIZE / 300)))

    def test_placeholder_ball_when_there_is_no_png(self):
        app = self.app()
        self.assertEqual(app.ui.ball().get_size(), (config.BALL_SIZE, config.BALL_SIZE))
        app.scene = "gacha"
        app.draw()  # the placeholder ball is drawn in the middle of the circle
        self.assertNotEqual(tuple(app.screen.get_at((480, 305)))[:3], (28, 32, 46))

    def test_the_ball_is_cut_into_two_vertical_halves(self):
        from game.gacha_view import split_vertically
        img = self.pygame.Surface((101, 40), self.pygame.SRCALPHA)
        img.fill((255, 0, 0, 255), (0, 0, 50, 40))
        img.fill((0, 0, 255, 255), (50, 0, 51, 40))
        left, right = split_vertically(img)
        self.assertEqual((left.get_size(), right.get_size()), ((50, 40), (51, 40)))
        self.assertEqual(tuple(left.get_at((0, 0)))[:3], (255, 0, 0))
        self.assertEqual(tuple(left.get_at((49, 39)))[:3], (255, 0, 0))
        self.assertEqual(tuple(right.get_at((0, 0)))[:3], (0, 0, 255))
        self.assertEqual(tuple(right.get_at((50, 39)))[:3], (0, 0, 255))

    # the animation -
    def test_timeline_whole_then_split_then_away(self):
        from game import gacha_view as gv
        r = gv.Reveal(Unit("Ant", 2, 2), self.app().ui)
        self.assertEqual(r.halves_state(), (0.0, 0.0, 255))  # whole ball
        r.t = gv.IDLE + gv.SPLIT / 2
        gap_mid, travel, alpha = r.halves_state()
        self.assertTrue(0 < gap_mid < gv.MAX_GAP and travel == 0 and alpha == 255)  # opening, not leaving yet
        r.t = gv.IDLE + gv.SPLIT
        self.assertEqual(r.halves_state(), (float(gv.MAX_GAP), 0.0, 255))  # fully open, about to leave
        r.t = gv.IDLE + gv.SPLIT + gv.AWAY / 2
        gap, travel, alpha = r.halves_state()
        self.assertTrue(gap == gv.MAX_GAP and 0 < travel < gv.TRAVEL and 0 < alpha < 255)
        self.assertFalse(r.done)
        r.update(10)
        self.assertTrue(r.done)
        self.assertEqual(r.halves_state(), (float(gv.MAX_GAP), float(gv.TRAVEL), 0))  # gone

    def test_halves_only_ever_move_outward_and_fade(self):
        from game import gacha_view as gv
        r = gv.Reveal(Unit("Ant", 2, 2), self.app().ui)
        last = (-1, -1, 256)
        while not r.done:
            r.update(0.01)
            gap, travel, alpha = r.halves_state()
            self.assertGreaterEqual(gap, last[0])
            self.assertGreaterEqual(travel, last[1])
            self.assertLessEqual(alpha, last[2])
            last = (gap, travel, alpha)

    def test_the_unit_is_hidden_then_revealed_through_the_gap_then_fully(self):
        from game import gacha_view as gv
        from game.ui import BG, unit_color
        self.save_ball((150, 150), (0, 0, 200))
        app = self.app()
        r = gv.Reveal(Unit("Ant", 2, 2), app.ui)
        cx, cy = 480, 305
        body, ball = unit_color("Ant"), (0, 0, 200)
        probe_centre, probe_side = (cx, cy + 22), (cx - 30, cy + 22)  # clear of the name, letter and stat circles

        def look(t):
            r.t = t
            app.screen.fill(BG)
            r.draw(app.screen, app.ui, (cx, cy))
            return [tuple(app.screen.get_at(p))[:3] for p in (probe_centre, probe_side)]

        self.assertEqual(look(0), [ball, ball])  # idle: the ball hides the unit
        self.assertEqual(look(gv.IDLE + gv.SPLIT), [body, ball])  # split: the unit shows through the gap only
        self.assertEqual(look(r.duration), [body, body])  # done: halves gone, unit fully visible

    def test_fading_halves_blend_with_what_is_behind(self):
        from game import gacha_view as gv
        from game.ui import BG
        self.save_ball((150, 150), (0, 0, 200))
        app = self.app()
        r = gv.Reveal(Unit("Ant", 2, 2), app.ui)
        r.t = gv.IDLE + gv.SPLIT + gv.AWAY * 0.1  # just started leaving: almost solid, almost no travel
        app.screen.fill(BG)
        r.draw(app.screen, app.ui, (480, 305))
        _, travel, alpha = r.halves_state()
        x = round(480 - gv.MAX_GAP / 2 - travel - 20)  # a column that is still inside the left half
        px = tuple(app.screen.get_at((x, 305 + 22)))[:3]
        self.assertGreater(px[2], 150)  # still mostly the blue ball
        self.assertLess(alpha, 255)

    # the scene -
    def test_gacha_scene_preview_flow(self):
        app = self.app()
        app.rng = random.Random(3)
        app.menu_page = "units"
        app.handle_click(app.gacha_btn.rect.center)
        self.assertEqual((app.scene, app.reveal), ("gacha", None))
        app.draw()
        app.handle_click((100, 100))  # not the ball
        self.assertIsNone(app.reveal)
        app.handle_click((480, 305))  # the ball
        self.assertIsNotNone(app.reveal)
        unit = app.reveal.unit
        self.assertTrue(1 <= unit.tier <= 5)
        app.handle_click((480, 305))  # during the reveal: skip ahead
        self.assertTrue(app.reveal.done)
        app.draw()
        app.handle_click((480, 305))  # after it: the ball comes back
        self.assertIsNone(app.reveal)
        # leaving and coming back always starts from the waiting ball
        app.handle_click((480, 305))
        app.handle_click(app.back_btn.rect.center)
        self.assertEqual(app.scene, "menu")
        app.handle_click(app.gacha_btn.rect.center)
        self.assertIsNone(app.reveal)

    def test_a_full_preview_plays_through_the_game_loop(self):
        app = self.app()
        app.scene = "gacha"
        app.handle_click((480, 305))
        frames = 0
        while not app.reveal.done and frames < 500:
            app.update(0.016)
            app.draw()
            frames += 1
        self.assertTrue(app.reveal.done)
        self.assertLess(frames, 200)  # about 1.75 s at 60 fps
        app.draw()


class EnemyLevelTests(unittest.TestCase):
    def test_budget_formula(self):
        from game.opponents import level_budget
        for turn, total in {1: 2, 2: 3, 3: 3, 4: 4, 6: 5, 10: 7, 20: 12}.items():
            self.assertEqual(level_budget(turn, 1), total, turn)
        self.assertEqual(level_budget(1, 5), 5)  # never fewer levels than units
        self.assertEqual(level_budget(10, 11), 11)

    def test_every_team_gets_its_budget_or_is_maxed_out(self):
        from game.opponents import level_budget
        for diff in config.DIFFICULTIES:
            for turn in range(1, 41):
                for seed in range(4):
                    team = generate_team(turn, random.Random(seed * 100 + turn), diff)
                    self.assertTrue(all(1 <= u.level <= config.MAX_LEVEL for u in team))
                    want = min(level_budget(turn, len(team)), len(team) * config.MAX_LEVEL)
                    self.assertEqual(sum(u.level for u in team), want, (diff.name, turn))

    def test_same_formula_for_every_difficulty(self):
        for turn, total in ((10, 7), (14, 9), (20, 12)):  # all difficulties have a full team of 5 by then
            for diff in config.DIFFICULTIES:
                team = generate_team(turn, random.Random(turn), diff)
                self.assertEqual((len(team), sum(u.level for u in team)), (config.TEAM_SIZE, total), (diff.name, turn))

    def test_late_game_enemies_are_all_max_level(self):
        for diff in config.DIFFICULTIES:
            team = generate_team(40, random.Random(1), diff)
            self.assertTrue(all(u.level == config.MAX_LEVEL for u in team))  # 1 + 21 = 22 levels > 5 x 3

    def test_each_level_gives_merge_stats_and_scales_the_ability(self):
        from game.units import ROSTER
        base = {name: (a, h) for name, a, h in ROSTER}
        flat = config.Difficulty("flat", ("", ""), 5, 1000, 1000)  # no stat bonus, no random extras
        seen_levels = set()
        for seed in range(30):
            for u in generate_team(12, random.Random(seed), flat):
                seen_levels.add(u.level)
                a, h = base[u.name]
                self.assertEqual((u.attack, u.health), (min(99, a + 2 * (u.level - 1)), min(99, h + 2 * (u.level - 1))))
        self.assertEqual(seen_levels, {1, 2, 3})  # all three levels really do show up
        b = Battle([Unit("Mosquito", 3, 1, level=3)], [Unit("Duck", 1, 40)])
        b.start()
        self.assertEqual(b.right[0].health, 37)  # a level 3 enemy ability hits for 3

    def test_endless_teams_stay_level_1(self):
        for turn in range(1, 41):
            team = generate_team(turn, random.Random(turn), endless=True)
            self.assertEqual(len(team), turn + 1)
            self.assertTrue(all(u.level == 1 for u in team))

    def test_enemy_levels_do_not_break_battles(self):
        rng = random.Random(8)
        for turn in range(1, 31):
            for diff in config.DIFFICULTIES:
                self.assertIn(Battle(generate_team(turn, rng, diff), generate_team(turn, rng, diff), rng).run_to_end(),
                              ("win", "lose", "draw"))


class EndlessModeTests(unittest.TestCase):
    def test_enemy_teams_do_not_scale_but_grow_by_one_unit_per_turn(self):
        from game.packs import STANDARD
        base = {name: (a, h) for tier in STANDARD.units.values() for name, a, h in tier}
        rng = random.Random(4)
        for diff in config.DIFFICULTIES:  # the chosen difficulty is ignored
            for turn in range(1, 41):
                team = generate_team(turn, rng, diff, endless=True)
                self.assertEqual(len(team), turn + 1)  # not capped at TEAM_SIZE
                for u in team:
                    self.assertEqual((u.attack, u.health), base[u.name])  # base stats: no bonus, no extras
                    self.assertLessEqual(u.tier, config.max_tier(turn))  # no tier boost

    def test_normal_generation_is_unchanged(self):
        rng = random.Random(0)
        self.assertEqual(len(generate_team(1, rng)), 3)
        self.assertEqual(len(generate_team(1, rng, endless=False)), 3)

    def test_there_is_no_win_limit_but_lives_still_end_the_run(self):
        st = GameState(random.Random(1), endless=True)
        for _ in range(config.WINS_TO_WIN + 5):
            st.finish_battle("win")
        self.assertEqual(st.status, "shop")
        self.assertEqual(st.wins, config.WINS_TO_WIN + 5)
        for _ in range(config.STARTING_LIVES):
            st.finish_battle("lose")
        self.assertEqual(st.status, "lost")
        normal = GameState(random.Random(1))
        for _ in range(config.WINS_TO_WIN):
            normal.finish_battle("win")
        self.assertEqual(normal.status, "won")  # normal runs still have the cap

    def test_huge_hordes_battle_to_the_end(self):
        rng = random.Random(8)
        for turn in (5, 12, 25, 40):
            mine = [Unit("Cow", 40, 60), Unit("Tiger", 30, 50), Unit("Rhino", 35, 55)]
            horde = generate_team(turn, rng, endless=True)
            self.assertIn(Battle(mine, horde, rng).run_to_end(), ("win", "lose", "draw"))
        # faint summons on a horde bigger than the team limit don't crash or exceed anything
        horde = [Unit("Turtle", 1, 1) for _ in range(12)]
        b = Battle([Unit("Cow", 99, 99)], horde, rng)
        self.assertIn(b.run_to_end(), ("win", "lose", "draw"))

    def test_big_teams_squeeze_to_fit_the_window(self):
        from game import battle_view as bv
        self.assertEqual(bv.spacing(1), bv.SPACING)
        self.assertEqual(bv.spacing(5), bv.SPACING)  # normal teams look exactly as before
        self.assertLess(bv.spacing(6), bv.SPACING)
        for n in range(1, 60):
            sp = bv.spacing(n)
            self.assertLessEqual(sp, bv.SPACING)
            self.assertGreaterEqual(bv.LEFT_FRONT_X - sp * (n - 1), 45 - 1e-6)  # last card still on screen (left side)
            self.assertLessEqual(bv.RIGHT_FRONT_X + sp * (n - 1), 915 + 1e-6)  # and on the right side

    def test_the_battle_screen_draws_a_big_horde(self):
        import main
        app = main.App()
        app.start_game(config.DIFFICULTIES[0], endless=True)
        app.state.turn = 15
        app.state.team[0] = Unit("Ant", 2, 2)
        app.start_battle()
        self.assertEqual(len(app.view.battle.right), 16)
        for _ in range(30):
            app.update(0.016)
            app.draw()


class EndlessMenuTests(unittest.TestCase):
    def setUp(self):
        import main
        self.app = main.App()

    def color_at(self, pos):
        return tuple(self.app.screen.get_at(pos))[:3]

    def test_the_button_only_appears_when_green_mode_is_on_and_sits_next_to_it(self):
        from game.ui import BG
        app = self.app
        probe = (app.endless_btn.rect.x + 15, app.endless_btn.rect.y + 5)
        app.draw()
        self.assertEqual(self.color_at(probe), BG)  # hidden
        app.handle_click(app.endless_btn.rect.center)  # clicking where it would be does nothing
        self.assertFalse(app.endless_mode)
        app.handle_click(app.green_btn.rect.center)
        app.draw()
        tinted_bg = self.color_at((5, 5))  # green mode tints everything, so compare with the tinted background
        shown = self.color_at(probe)
        self.assertNotEqual(shown, tinted_bg)  # the button is drawn now
        self.assertGreater(shown[0], 150)  # and it is the orange one (the overlay only adds green)
        g, e = app.green_btn.rect, app.endless_btn.rect
        self.assertEqual(g.y, e.y)  # same row
        self.assertEqual(e.left - g.right, 10)  # right next to it

    def test_toggle_on_off_and_turning_green_off_resets_it(self):
        app = self.app
        app.handle_click(app.green_btn.rect.center)
        app.handle_click(app.endless_btn.rect.center)
        self.assertTrue(app.endless_mode)
        app.draw()
        app.handle_click(app.endless_btn.rect.center)
        self.assertFalse(app.endless_mode)
        app.handle_click(app.endless_btn.rect.center)
        self.assertTrue(app.endless_mode)
        app.handle_click(app.green_btn.rect.center)  # green off: endless goes away with it
        self.assertFalse(app.green_mode)
        self.assertFalse(app.endless_mode)
        app.handle_click(app.green_btn.rect.center)  # green back on: endless is off again
        self.assertFalse(app.endless_mode)

    def test_starting_a_game_uses_the_toggle_and_replay_keeps_it(self):
        app = self.app
        app.handle_click(app.green_btn.rect.center)
        app.handle_click(app.endless_btn.rect.center)
        app.handle_click(app.play_btn.rect.center)
        app.handle_click(app.diff_btns[0][0].rect.center)
        self.assertTrue(app.state.endless)
        app.state.team[0] = Unit("Ant", 2, 2)
        app.start_battle()
        self.assertEqual(len(app.view.battle.right), app.state.turn + 1)  # turn 1: 2 enemies (Normal would send 3)
        app.restart()
        self.assertTrue(app.state.endless)
        app.draw()  # the HUD works in endless mode
        app.back_to_menu()
        app.handle_click(app.endless_btn.rect.center)  # turn it off, then play normally
        app.handle_click(app.play_btn.rect.center)
        app.handle_click(app.diff_btns[0][0].rect.center)
        self.assertFalse(app.state.endless)
        app.state.team[0] = Unit("Ant", 2, 2)
        app.start_battle()
        self.assertEqual(len(app.view.battle.right), 3)


class AbilityTextTests(unittest.TestCase):
    def test_describe(self):
        self.assertIn("3 damage", abilities.describe(Unit("Mosquito", 3, 1, level=3)))
        self.assertIn("no ability", abilities.describe(Unit("Nobody", 1, 4)))


if __name__ == "__main__":
    unittest.main()


class StartOfTurnTests(unittest.TestCase):
    def setUp(self):
        self.st = GameState(random.Random(1))

    def turn(self):
        self.st.finish_battle("draw")

    def test_giraffe_buffs_only_the_unit_in_front(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Giraffe", 3, 6, tier=3)
        self.st.team[2] = Unit("Beaver", 2, 3)
        self.turn()
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (3, 3))
        self.assertEqual((self.st.team[1].attack, self.st.team[1].health), (3, 6))  # not itself
        self.assertEqual((self.st.team[2].attack, self.st.team[2].health), (2, 3))  # not the one behind
        self.assertIn("Giraffe gave Ant +1/+1", self.st.message)

    def test_giraffe_in_front_does_nothing(self):
        self.st.team[0] = Unit("Giraffe", 3, 6, tier=3)
        self.st.team[1] = Unit("Ant", 2, 2)
        self.turn()
        self.assertEqual((self.st.team[1].attack, self.st.team[1].health), (2, 2))

    def test_penguin_buffs_the_two_units_in_front(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Beaver", 2, 3)
        self.st.team[2] = Unit("Penguin", 4, 8, tier=4)
        self.st.team[3] = Unit("Duck", 1, 4)
        self.turn()
        self.assertEqual([(p.attack, p.health) for p in self.st.team[:4]], [(3, 3), (3, 4), (4, 8), (1, 4)])

    def test_penguin_with_one_unit_in_front_buffs_just_it(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Penguin", 4, 8, tier=4)
        self.turn()
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (3, 3))

    def test_gaps_in_the_team_are_skipped(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[3] = Unit("Giraffe", 3, 6, tier=3)
        self.turn()
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (3, 3))

    def test_buff_scales_with_level(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Giraffe", 5, 8, level=2, tier=3)
        self.turn()
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (4, 4))

    def test_it_stacks_every_turn_and_nothing_fires_in_battle(self):
        self.st.team[0] = Unit("Ant", 2, 2)
        self.st.team[1] = Unit("Giraffe", 3, 6, tier=3)
        self.turn()
        self.turn()
        self.assertEqual((self.st.team[0].attack, self.st.team[0].health), (4, 4))
        b = Battle([Unit("Ant", 2, 2), Unit("Giraffe", 3, 6)], [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual((b.left[0].attack, b.left[0].health), (2, 2))

    def test_descriptions(self):
        self.assertIn("Start of turn: give the unit ahead +1/+1", abilities.describe(Unit("Giraffe", 3, 6, tier=3)))
        self.assertIn("Start of turn: give the 2 units ahead +2/+2", abilities.describe(Unit("Penguin", 4, 8, level=2, tier=4)))


class FourthShopSlotTests(unittest.TestCase):
    def test_slot_count_by_turn(self):
        self.assertEqual(config.SHOP_SLOT_UNLOCK_TURN, config.TIER_UNLOCK_TURNS[3])
        for turn in range(1, 15):
            expected = 4 if turn >= config.SHOP_SLOT_UNLOCK_TURN else 3
            self.assertEqual(config.shop_size(turn), expected)

    def test_fourth_slot_fills_only_once_unlocked(self):
        st = GameState(random.Random(1))
        while st.turn < config.SHOP_SLOT_UNLOCK_TURN - 1:
            self.assertIsNone(st.shop[3])
            st.reroll()
            self.assertIsNone(st.shop[3])
            st.finish_battle("draw")
        self.assertIsNone(st.shop[3])
        st.finish_battle("draw")
        self.assertEqual(st.turn, config.SHOP_SLOT_UNLOCK_TURN)
        self.assertIsNotNone(st.shop[3])
        self.assertIn("Shop slot 4 unlocked", st.message)
        st.reroll()
        self.assertIsNotNone(st.shop[3])

    def test_locked_slot_cannot_be_frozen_or_block_the_reroll_check(self):
        st = GameState(random.Random(1))
        self.assertFalse(st.toggle_freeze("shop", 3))
        for j in range(3):
            st.toggle_freeze("shop", j)
        for j in range(config.ITEM_SHOP_SIZE):
            st.toggle_freeze("item", j)
        self.assertFalse(st.reroll())  # everything open is frozen
        self.assertEqual(st.message, "Everything is frozen.")
