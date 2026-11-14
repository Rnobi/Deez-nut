import os
import random
import sys
import unittest

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
                unit_tiers |= {p.tier for p in st.shop}
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

    def test_gacha_and_create_pack_use_the_menu_music_key(self):
        for scene in ("gacha", "create_pack"):
            self.app.music.key = None
            self.app.scene = scene
            self.app.update(0.016)
            self.assertEqual(self.app.music.key, "menu")

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
        before = [p.health for p in st.shop]
        st.sell(0)
        self.assertEqual([p.health for p in st.shop], [h + 1 for h in before])

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
        b = Battle([Unit("Scorpion", 1, 10)], [Unit("Cow", 1, 100)])
        self.assertEqual(b.run_to_end(), "win")
        b = Battle([Unit("Scorpion", 0, 10)], [Unit("Cow", 1, 100)])  # 0 attack: no damage, no poison kill
        b.start()
        b.clash()
        self.assertEqual(b.right[0].health, 100)

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
                        p.perks = rng.choice([(), ("honey",), ("steak",), ("honey", "steak")])
                    b = generate_team(turn, rng, diff)
                    self.assertIn(Battle(a, b, rng).run_to_end(), ("win", "lose", "draw"))


class SummonTests(unittest.TestCase):
    def names(self, team):
        return [p.name for p in team]

    def test_only_pig_still_gives_gold_on_sell(self):
        gold_units = [n for n, a in abilities.ABILITIES.items() if a.effect == "gain_gold"]
        self.assertEqual(gold_units, ["Pig"])
        for name in ("Turtle", "Penguin", "Cow"):
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
    def test_start_summon_goes_behind_the_summoner(self):
        b = Battle([Unit("Penguin", 4, 8), Unit("Ant", 2, 2)], [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual(self.names(b.left), ["Penguin", "Chick", "Chick", "Ant"])
        self.assertEqual((b.left[1].attack, b.left[1].health), (2, 1))

    def test_nothing_is_summoned_onto_a_full_team(self):
        team = [Unit("Penguin", 4, 8)] + [Unit("Ant", 2, 2) for _ in range(config.TEAM_SIZE - 1)]
        b = Battle(team, [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual(len(b.left), config.TEAM_SIZE)
        self.assertTrue(any("no room" in line for line in b.log))
        # one free slot -> only one of the two chicks fits
        b = Battle(team[:-1], [Unit("Duck", 1, 50)])
        b.start()
        self.assertEqual(len(b.left), config.TEAM_SIZE)
        self.assertEqual(self.names(b.left).count("Chick"), 1)

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
        b = Battle([Unit("Penguin", 4, 8)], [Unit("Duck", 1, 50)])
        b.begin()
        b.flash_queue.clear()
        self.assertTrue(b.fire_next())
        flashed = [p.name for p in b.flash_queue]
        self.assertEqual(flashed, ["Penguin", "Chick", "Chick"])

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
        app.state.team[0] = Unit("Chick", 2, 1, tier=0)
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
        self.assertEqual(self.st.team[0].perks, ())

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
        before = [(p.attack, p.health) for p in self.st.shop]
        self.use("Cheese", 2, 3)
        self.assertEqual([(p.attack, p.health) for p in self.st.shop], [(a + 1, h + 1) for a, h in before])

    def test_carrot_gives_armor_that_stacks(self):
        self.use("Carrot", 3, 2)
        self.assertEqual(self.st.team[0].armor, 2)
        self.use("Carrot", 3, 2)
        self.assertEqual(self.st.team[0].armor, 4)

    def test_honey_perk_buffs_an_ally_on_faint(self):
        self.use("Honey", 2, 4)
        self.assertEqual(self.st.team[0].perks, ("honey",))
        self.use("Honey", 2, 4)  # no duplicates
        self.assertEqual(self.st.team[0].perks, ("honey",))
        b = Battle([Unit("Duck", 1, 1, perks=("honey",)), Unit("Cow", 6, 10)], [Unit("Fish", 5, 50)])
        b.start()
        b.clash()
        b.cleanup()
        self.assertEqual((b.left[0].attack, b.left[0].health), (8, 12))

    def test_steak_perk_hits_an_enemy_at_the_start(self):
        b = Battle([Unit("Duck", 1, 5, perks=("steak",))], [Unit("Cow", 1, 20)])
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

    def test_perks_survive_merging(self):
        a = Unit("Ant", 2, 2, perks=("honey",), armor=1)
        b = Unit("Ant", 3, 3, perks=("steak",), armor=2)
        a.merge(b)
        self.assertEqual(set(a.perks), {"honey", "steak"})
        self.assertEqual(a.armor, 2)

    def test_describe_shows_perks_armor_and_temp_buffs(self):
        unit = Unit("Ant", 2, 2, armor=2, perks=("honey",), temp_attack=3, temp_health=3)
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
        unit = Unit("Scorpion", 9, 7, tier=5, armor=2, poison=True, perks=("honey", "steak"), temp_attack=3, temp_health=3)
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
        st.team[0] = Unit("Scorpion", 9, 7, tier=5, armor=2, poison=True, perks=("honey",), temp_attack=3, temp_health=3)
        st.items[0] = Item("Honey", 2, 4, 4)
        self.app.selected = ("team", 0)
        self.app.draw()
        self.assertGreater(len(self.app.ui.fonts), 0)
        self.assertEqual(self.app.state.items[0].name, "Honey")


class AbilityTextTests(unittest.TestCase):
    def test_describe(self):
        self.assertIn("3 damage", abilities.describe(Unit("Mosquito", 3, 1, level=3)))
        self.assertIn("no ability", abilities.describe(Unit("Nobody", 1, 4)))


if __name__ == "__main__":
    unittest.main()
