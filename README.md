walkthrough - High Roller: Power-up
The prototype for High Roller: Power-up is now complete and fully functional. This 4-player dice game features a robust economic system, strategic power-ups, and distinct AI personalities.

Key Features Implemented
1. Core Engine & Economy
4 Players: 1 Human (P1) and 3 AI (P2-P4).
50-Point Increment rule: All bets, wins, and costs are strictly in multiples of 50.
Starting Stats: 500 points and a starter inventory (Reroll, Swap, Extra Die).
Elimination: Players are "Bust" at 0 points; UI turns grey.
Victory: Game ends after 10 rounds or when only 1 player remains.
2. AI Personalities
Each AI bot has a unique behavioral profile:

Aggressive (P2): Bets the table cap if possible, uses "Extra Die" early, and buys aggressive items.
Balanced (P3): Bets moderately, saves power-ups for later rounds or when trailing, and prioritizes "Swap".
Defensive (P4): Minimum bets, only uses defensive power-ups (Reroll) when significantly behind, and prioritizes safety.
3. Phases & UI
Initiative Phase: Determined by highest roll (with tie-breaking).
Betting Phase: The starter sets the "Table Stakes" (capped by the poorest player).
Power-up Turn: Each player can use MAX ONE power-up per round.
Showdown: Automatic dice resolution and pot distribution.
Shop Phase: Intermission to restock power-ups (enforcing the 50-point safety reserve).
Game Over Screen: Displays final rankings and a "Restart" option ('R' key).
Technical Implementation
Modular Design: Separated constants, dice rendering, and player logic into distinct modules.
Clean UI: Programmatic dice shapes, responsive layouts, and intuitive button controls.
State Machine: Robust handling of turns and transitions.
Verification
Verified 10-round limit.
Verified AI personality logic (Aggressive AI consistently bets higher).
Verified "Bust" player grey-out and exclusion from play.
Verified Restart mechanic.
How to Run
bash
python3 main.py
Note: Requires pygame-ce.