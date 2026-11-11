# Auto Pets Clone (pygame)

Core loop: buy pets in the shop, arrange your team, then watch it auto-battle
a computer-generated team. 5 lives, first to 10 wins.

## Run
    pip install -r requirements.txt
    python main.py

## Controls
- Click a shop pet, then a team slot to buy it (drop onto the same pet to merge: +1/+1 and a level).
- Click a team pet, then another slot to move/swap. Click a team pet then **Sell** to sell it.
- **Reroll** refreshes the shop (1g). **BATTLE!** ends your turn.
- In battle: click or press F to fast-forward. Press R to restart after game over. Esc quits.

Team slot 0 is the **front** (right side); the front pets fight first.

## Layout
- `main.py` – window, input, scenes
- `game/config.py` – all tunable numbers (gold, costs, lives, scaling)
- `game/pets.py` – roster and Pet class (add pets here)
- `game/core.py` – shop rules and game state (no pygame)
- `game/battle.py` – battle engine (no pygame)
- `game/opponents.py` – enemy team generator
- `game/ui.py`, `game/battle_view.py` – drawing and the bump animation
- `assets/pets/` – drop `ant.png`, `pig.png`, etc. to replace placeholder cards
- `tests/test_logic.py` – `python -m unittest discover -s tests`
