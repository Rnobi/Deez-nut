# Discount Village (pygame auto-battler)

Buy units and items in the shop, arrange your team, then watch it auto-battle a
computer-generated team. 5 lives, first to 10 wins.

## Run
    pip install -r requirements.txt
    python main.py

## Start screen
`config.TITLE` is the title (start screen and window). **Play** swaps for the three difficulty buttons
(**Normal**, **Hard**, **Rigged**) in the same spot. **Units** swaps for **Gacha** and **Create Pack**
side by side in the same spot; both open an empty "Coming soon" scene for now. **Green Mode** toggles a
translucent green overlay (`config.GREEN_ALPHA`) over every screen. While Green Mode is on, an **Endless Mode**
toggle appears right next to it (see below); turning Green Mode off turns Endless Mode off too. Esc steps back (difficulty page, units
page, Gacha, Create Pack) and quits from the main menu.

Each difficulty is a `Difficulty` in `config.DIFFICULTIES` that controls enemy scaling: team size, stats
gained per step (`bonus_every` turns, `bonus_step` stats), random extras (`extra_div`) and `tier_boost`
(enemies drawing from tiers beyond what's unlocked). Edit or add entries; the menu lays them out left to right.

### Enemy levels
Enemy units level up too, the same way on every difficulty: a team gets `max(team size, 1 + (turn + 2) // 2)`
levels in total (`opponents.level_budget`). Every unit starts at level 1 and the spare levels are handed out at
random to units that aren't at max level. Each level adds +2/+2, like a merge, and scales the unit's ability.

### Endless mode
Turn on Green Mode, then **Endless Mode** next to it, then start a game with any difficulty button (the difficulty
is ignored). Enemy teams don't scale at all (base stats, no random extras, no tier boost, all level 1) but have
`turn + 1` units, with no cap, so big teams squeeze together on screen. There is no win limit: the run only ends
when you run out of lives, and the top bar shows "Endless" instead of a difficulty.

## Controls
- Click a shop unit, then a team slot to buy it (same name + same level merges).
- Click an item, then a team unit to use it on that unit.
- Click a team unit, then another slot to move/swap, or onto the same unit to merge.
- Click a team unit then **Sell** to sell it.
- **Right-click** a shop unit or item to freeze/unfreeze it. Frozen slots survive rerolls and new turns.
- Hover (or select) anything to see its description at the bottom of the screen.
- In battle: click or press F to fast-forward. After game over: R plays again on the same difficulty, M returns to the menu.

Team slot 0 is the **front**; the front units fight first.

## The pack and tiers (`game/packs.py`)
A `Pack` holds every unit and item, grouped by tier: 30 units (6 per tier, tiers 1-5) and 12 items
(2 per tier, tiers 1-6). Tiers unlock like Super Auto Pets (`config.TIER_UNLOCK_TURNS`): tier 1 on turn 1,
then tiers 2/3/4/5/6 on turns 3/5/7/9/11. The shop and the enemy teams only draw from unlocked tiers.

The shop has 3 unit slots at first and a **4th slot that unlocks with tier 3** (turn 5): `config.SHOP_SLOT_UNLOCK_TURN`
(it follows `TIER_UNLOCK_TURNS[3]`; set it to e.g. 6 to move it). Until then the slot is drawn as "Locked" and stays empty.

The Standard pack (`packs.STANDARD`, also `DEFAULT_PACK`) is the pack every game uses, and it is **immutable**:
a `Pack` freezes its contents when built, so nothing can edit it at runtime. The plan for custom packs: units won
from the Gacha get put into a *new* `Pack` on the Create Pack page (both scenes are empty for now); they never
modify Standard.

## Abilities (`game/abilities.py`) - every unit has one
Amounts scale with the unit's level. Triggers: start of turn (in the shop), start of battle, faint, sell, level-up, unit bought,
friend ahead attacks, knock-out. Units can also have **armor** (less damage per hit, never below 1)
and **poison** (whatever they damage faints). Add an effect function + an entry in `EFFECTS`, then give
a unit an entry in `ABILITIES`. During a battle an ability's user and receiver both flash, and
start-of-battle abilities fire one at a time.

### Start of turn (Giraffe, Penguin)
`START_OF_TURN` fires in the shop when a new turn begins, front to back, using the `buff_ahead` effect:
Giraffe gives the unit directly in front of it +1/+1, Penguin gives the 2 units in front of it +1/+1 (both scale
with level; `Ability.reach` is how many units ahead). Empty slots are skipped, and it only happens in your shop, not
for enemy teams in battle.

### Summoning (template for your own summoners)
Turtle and Cow use the `summon` effect (Pig is the only unit that still gives gold on sell):
- Turtle: faint, summons a Shell in its own slot.
  Cow: sell, summons a Calf into the slot it was sold from.
- To make your own: (1) add a token to `tokens` in `game/packs.py` (`"Shell": (2, 4)`), (2) give a unit
  `Ability(TRIGGER, "summon", how_many, "TokenName")` in `ABILITIES`. The commented template above `ABILITIES`
  in `game/abilities.py` lists where tokens appear for each trigger. Token stats are base stats x the summoner's
  level, nothing is summoned onto a full team, and tokens are normal units (they can be sold or merged).

## Items (`game/items.py`)
Every item gives the unit its listed stats for good. Some also have an extra effect (a gold dot on the card):
temporary buff until the end of the next battle (Cupcake), buff the shop (Cheese), armor (Carrot),
perks that grant a unit an extra ability (Honey, Steak), buff random other units (Sushi, Pizza),
buff the whole team (Salad) and level-up (Chocolate). See `ITEM_EFFECTS`. Small dots down the left edge of a
unit card show it has poison (purple), armor (steel), an item perk (gold) or a temporary buff (cyan).

A unit holds **one perk at a time**: using another perk item replaces the old perk (the newest wins) and using the
same one again does nothing, so perks never stack. When two units merge, the result keeps its own perk (else the
other's).

## Stat cap
Attack and health can never go above 99 (`config.STAT_CAP`). It is enforced inside `Unit` itself, so every buff,
item, merge, summon, level and enemy bonus is capped. Health can still drop to 0 or below in a fight.

## Backgrounds and music (all optional)
- `assets/backgrounds/shop.png` is behind the in-turn shop screen (and the game-over screen);
  `assets/backgrounds/battle.png` is behind battles. Use 960 x 540; other sizes are cover-scaled and cropped.
- Music, per screen (menu / shop / battle / gacha / create_pack; the last two fall back to the menu track if
  you give them nothing): drop `menu.mp3`, `shop.mp3`, `battle.mp3`, `gacha.mp3`, `create_pack.mp3` (or `.ogg`/`.wav`) into `assets/music/`, or name one `bgm.mp3` to play everywhere. Or set `BGM`
  in `game/config.py` to a **direct link** to an audio file (YouTube/Spotify page links don't work).
  Links download once into `assets/music/cache/`. Details in `assets/music/README.txt`. Volume is `BGM_VOLUME`.

## Your image paths (all optional; placeholders are drawn when missing)
- `assets/units/<name>.png`   all 30 names (and the summoned tokens) are listed in assets/units/README.txt. The art fills
  the WHOLE card (scaled to cover it, centre-cropped, never stretched, rounded corners); the name and stats are drawn on top.
- `assets/items/<name>.png`  all 12 names are listed in assets/items/README.txt
- `assets/ui/freeze.png`     freeze overlay: drawn 15% larger than the card, centred, at half opacity (`FREEZE_SCALE`,
  `FREEZE_OPACITY`), so draw it fully opaque and let the game fade it
- `assets/ui/summoning_circle.png`  the magic circle on the gacha screen (fitted inside `SUMMONING_CIRCLE_SIZE`)
- `assets/ui/ball.png`      the ball on the circle (fitted inside `BALL_SIZE`). Draw it WHOLE: on a pull the game cuts it
  in half vertically, the halves slide apart and away (fading) and the unit is revealed. On the Gacha screen,
  click the ball to preview that (a random unit, until the real gacha exists)

## Layout
- `main.py` - window, input, scenes (menu, gacha, shop, battle, game over)
- `game/config.py` - tunable numbers, difficulties, music settings
- `game/packs.py`, `game/units.py`, `game/items.py`, `game/abilities.py` - content
- `game/core.py` - shop rules and game state (no pygame)
- `game/battle.py` - battle engine (no pygame)
- `game/opponents.py` - enemy team generator
- `game/ui.py`, `game/battle_view.py` - drawing and the bump animation
- `game/gacha_view.py` - the ball-splits-and-reveals animation
- `game/audio.py` - background music (files and links)
- `tests/test_logic.py` - `python -m unittest discover -s tests`
