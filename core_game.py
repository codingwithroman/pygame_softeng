# core_game.py
import random
from typing import Optional, Tuple, List

from constants import (
    STATE_INITIATIVE,
    STATE_BETTING,
    STATE_ROLL_ALL,
    STATE_POWERUP_TURN,
    STATE_SHOWDOWN,
    STATE_SHOP,
    STATE_GAMEOVER,
    COST_REROLL,
    COST_SWAP,
    COST_EXTRA_DIE,
    MAX_ROUNDS,
    CURRENCY_STEP,
    MAX_BET,
)
from player import Player


AI_PERSONALITIES = ["Aggressive", "Balanced", "Defensive"]

STATE_LOBBY = "LOBBY"
class Game:
    """
    Headless, server-authoritative game engine.

    Geen pygame.
    Geen rendering.
    Geen input handling.
    Alleen state, rules en transitions.
    """

    def __init__(self):
        self.players: List[Player] = []
        self.round = 1
        self.pot = 0
        self.state = STATE_LOBBY
        self.message = "Waiting for players..."
        self.starter: Optional[Player] = None
        self.turn_order: List[Player] = []
        self.current_turn_idx = 0
        self.current_bet = 50
        self.initiative_rolls = {}
        self.tied_players: List[Player] = []

        self.started = False
        self.pending_resolution = False
        self.disconnected_players = set()

    # =========================================================
    # Basic lifecycle
    # =========================================================

    def is_started(self) -> bool:
        return self.started

    def reset_runtime_state(self):
        self.round = 1
        self.pot = 0
        self.state = STATE_INITIATIVE
        self.starter = None
        self.turn_order = []
        self.current_turn_idx = 0
        self.message = "Game Started! Roll for initiative."
        self.current_bet = 50
        self.initiative_rolls = {}
        self.tied_players = []
        self.pending_resolution = False

        for p in self.players:
            p.dice = []
            p.is_bust = False
            p.is_starter = False
            p.has_used_powerup = False

    def add_human_player(self, name: str):
        if self.started:
            raise ValueError("Game is al gestart.")
        if any(p.name == name for p in self.players):
            raise ValueError("Spelernaam bestaat al.")
        if len(self.players) >= 4:
            raise ValueError("Game zit vol.")

        self.players.append(Player(name, is_ai=False))
        self.message = f"{name} joined the lobby."

    def fill_with_ai_until_full(self):
        if self.started:
            return

        existing_names = {p.name for p in self.players}
        ai_templates = [
            ("AI Aggressive", "Aggressive"),
            ("AI Balanced", "Balanced"),
            ("AI Defensive", "Defensive"),
            ("AI Wildcard", random.choice(AI_PERSONALITIES)),
        ]

        for base_name, personality in ai_templates:
            if len(self.players) >= 4:
                break

            candidate = base_name
            suffix = 2
            while candidate in existing_names:
                candidate = f"{base_name} {suffix}"
                suffix += 1

            self.players.append(
                Player(candidate, is_ai=True, personality=personality)
            )
            existing_names.add(candidate)
    def setup_singleplayer(self, human_name: str):
        """
        Zet een lokale singleplayer game op met 1 human + AI tot 4 spelers.
        """
        if self.started:
            raise ValueError("Game is al gestart.")

        self.add_human_player(human_name)
        self.fill_with_ai_until_full()
        self.start_game()

        progressed = True
        safety = 0
        while progressed and safety < 50:
            progressed = self.tick()
            safety += 1

    def start_game(self):
        if self.started:
            return
        if len(self.players) < 2:
            raise ValueError("Minstens 2 spelers nodig.")
        if len(self.players) > 4:
            raise ValueError("Maximaal 4 spelers toegestaan.")

        self.started = True
        self.reset_runtime_state()
        self.start_initiative()

    def mark_player_disconnected(self, player_name: str):
        self.disconnected_players.add(player_name)

    # =========================================================
    # Helpers
    # =========================================================

    def get_player_by_name(self, name: str) -> Optional[Player]:
        for p in self.players:
            if p.name == name:
                return p
        return None

    def get_active_players(self) -> List[Player]:
        return [p for p in self.players if p and not p.is_bust]

    def get_current_turn_player(self) -> Optional[Player]:
        if not self.turn_order:
            return None
        if not (0 <= self.current_turn_idx < len(self.turn_order)):
            return None
        return self.turn_order[self.current_turn_idx]

    def get_table_cap(self) -> int:
        active_players = self.get_active_players()
        if not active_players:
            return 0
        raw_cap = min(p.points for p in active_players)
        raw_cap = max(CURRENCY_STEP, raw_cap)
        return min(raw_cap, MAX_BET)

    def _build_turn_order_from_starter(self):
        self.turn_order = []
        if not self.players:
            return

        try:
            starter_idx = self.players.index(self.starter) if self.starter in self.players else 0
        except ValueError:
            starter_idx = 0

        for i in range(len(self.players)):
            p = self.players[(starter_idx + i) % len(self.players)]
            if p and not p.is_bust:
                self.turn_order.append(p)

        self.current_turn_idx = 0

    def _all_humans_disconnected(self) -> bool:
        humans = [p for p in self.players if not p.is_ai and not p.is_bust]
        if not humans:
            return False
        return all(p.name in self.disconnected_players for p in humans)

    def _cleanup_busts(self):
        for p in self.players:
            if p.points <= 0:
                p.points = 0
                p.is_bust = True

    # =========================================================
    # Serialization
    # =========================================================

    def serialize_state(self):
        current_turn = self.get_current_turn_player()
        return {
            "round": self.round,
            "pot": self.pot,
            "state": self.state,
            "message": self.message,
            "current_bet": self.current_bet,
            "starter": self.starter.name if self.starter else None,
            "current_turn": current_turn.name if current_turn else None,
            "players": [p.to_dict() for p in self.players],
        }

    # =========================================================
    # Initiative
    # =========================================================

    def start_initiative(self):
        active_players = self.get_active_players()
        if len(active_players) <= 1:
            self.finish_game()
            return

        self.state = STATE_INITIATIVE
        self.initiative_rolls = {}
        self.starter = None
        self.tied_players = active_players[:]
        self.message = "Rolling for Initiative..."
        self.roll_initiative()
        self.pending_resolution = True

    def roll_initiative(self):
        for p in self.tied_players:
            roll = random.randint(1, 6)
            self.initiative_rolls[p] = roll
            p.dice = [roll]

    def resolve_initiative(self):
        if not self.initiative_rolls:
            self.roll_initiative()

        max_roll = max(self.initiative_rolls.values())
        highest_players = [p for p, roll in self.initiative_rolls.items() if roll == max_roll]

        if len(highest_players) > 1:
            self.tied_players = highest_players
            self.starter = None
            self.message = f"Tie! {', '.join(p.name for p in highest_players)} roll again!"
            self.initiative_rolls = {}
            for p in self.tied_players:
                p.dice = []
            self.roll_initiative()
            self.pending_resolution = True
            return

        self.starter = highest_players[0]
        self.tied_players = []
        for p in self.players:
            p.is_starter = False
        self.starter.is_starter = True
        self.message = f"{self.starter.name} wins initiative."
        self.start_betting()

    # =========================================================
    # Betting
    # =========================================================

    def start_betting(self):
        self.state = STATE_BETTING
        for p in self.players:
            p.dice = []

        if not self.starter:
            self.message = "Error: no starter player defined."
            return

        table_cap = self.get_table_cap()
        self.current_bet = CURRENCY_STEP

        if self.starter.is_ai:
            self.current_bet = self._choose_ai_bet(self.starter, table_cap)
            self.message = f"{self.starter.name} ({self.starter.personality}) set the bet to {self.current_bet}."
            self.collect_bets()
            self.state = STATE_ROLL_ALL
            self.pending_resolution = True
        else:
            self.message = f"{self.starter.name}, set the bet. Table Cap: {table_cap}"

    def _choose_ai_bet(self, player: Player, table_cap: int) -> int:
        if table_cap < CURRENCY_STEP:
            return CURRENCY_STEP

        if player.personality == "Aggressive":
            return table_cap
        if player.personality == "Balanced":
            return min(table_cap, 150) if player.points >= 300 else CURRENCY_STEP
        return CURRENCY_STEP

    def collect_bets(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.subtract_points(self.current_bet)
            self.pot += self.current_bet
        self.message = f"All players paid {self.current_bet}. Pot: {self.pot}."

    # =========================================================
    # Rolling / powerups
    # =========================================================

    def roll_all(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.dice = [random.randint(1, 6), random.randint(1, 6)]
            p.has_used_powerup = False

        self.state = STATE_POWERUP_TURN
        self.message = "Everyone rolled! Power-up turns starting..."
        self._build_turn_order_from_starter()
        self.prepare_powerup_turn()

    def prepare_powerup_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.state = STATE_SHOWDOWN
            self.resolve_showdown()
            return

        p = self.get_current_turn_player()
        if not p:
            self.state = STATE_SHOWDOWN
            self.resolve_showdown()
            return

        if p.is_ai or p.name in self.disconnected_players:
            self.message = f"{p.name}'s turn..."
            self.pending_resolution = True
        else:
            self.message = f"{p.name}, use a power-up or pass."

    def execute_ai_powerup(self):
        p = self.get_current_turn_player()
        if not p:
            return

        my_score = sum(p.dice)
        active_opponents = [o for o in self.get_active_players() if o != p]
        if not active_opponents:
            self.current_turn_idx += 1
            self.prepare_powerup_turn()
            return

        best_opp = max(active_opponents, key=lambda x: sum(x.dice))
        opp_score = sum(best_opp.dice)
        used = False
        choice = "Pass"

        if self.round == MAX_ROUNDS:
            for pt in ["Extra Die", "Swap", "Reroll"]:
                if p.has_powerup(pt):
                    if pt == "Swap" and max(best_opp.dice) <= min(p.dice):
                        continue
                    if self.use_powerup(p, pt):
                        used = True
                        choice = pt
                        break
        else:
            if p.personality == "Aggressive":
                if p.has_powerup("Extra Die") and len(p.dice) < 3:
                    used = self.use_powerup(p, "Extra Die")
                    choice = "Extra Die" if used else choice
                elif p.has_powerup("Reroll") and my_score < 10:
                    used = self.use_powerup(p, "Reroll")
                    choice = "Reroll" if used else choice

            elif p.personality == "Balanced":
                if my_score <= opp_score or self.round >= 7:
                    if p.has_powerup("Swap") and max(best_opp.dice) > min(p.dice):
                        used = self.use_powerup(p, "Swap")
                        choice = "Swap" if used else choice
                    elif p.has_powerup("Extra Die") and len(p.dice) < 3:
                        used = self.use_powerup(p, "Extra Die")
                        choice = "Extra Die" if used else choice

            else:
                if opp_score - my_score > 3:
                    if p.has_powerup("Swap") and max(best_opp.dice) > min(p.dice):
                        used = self.use_powerup(p, "Swap")
                        choice = "Swap" if used else choice
                    elif p.has_powerup("Reroll") and my_score < 6:
                        used = self.use_powerup(p, "Reroll")
                        choice = "Reroll" if used else choice

        if used:
            self.message = f"{p.name} ({p.personality}) used {choice}!"
        else:
            self.message = f"{p.name} ({p.personality}) passed."

        self.current_turn_idx += 1
        self.prepare_powerup_turn()

    def use_powerup(self, player: Player, p_type: str) -> bool:
        if player.has_used_powerup:
            return False
        if not player.use_powerup(p_type):
            return False

        player.has_used_powerup = True

        if p_type == "Reroll":
            player.dice = [random.randint(1, 6), random.randint(1, 6)]
            return True

        if p_type == "Extra Die":
            if len(player.dice) >= 3:
                return False
            player.dice.append(random.randint(1, 6))
            return True

        if p_type == "Swap":
            opponents = [o for o in self.get_active_players() if o != player]
            if not opponents or not player.dice:
                return False

            best_opp = max(opponents, key=lambda x: sum(x.dice))
            if not best_opp.dice:
                return False

            p_min_idx = player.dice.index(min(player.dice))
            o_max_idx = best_opp.dice.index(max(best_opp.dice))
            player.dice[p_min_idx], best_opp.dice[o_max_idx] = best_opp.dice[o_max_idx], player.dice[p_min_idx]
            return True

        return False

    # =========================================================
    # Showdown / round end
    # =========================================================

    def resolve_showdown(self):
        active_players = self.get_active_players()
        if not active_players:
            self.finish_game()
            return

        scores = {p: sum(p.dice) for p in active_players}
        max_score = max(scores.values())
        winners = [p for p, score in scores.items() if score == max_score]

        if len(winners) == 1:
            winner = winners[0]
            winner.add_points(self.pot)
            self.message = f"Winner: {winner.name} (+{self.pot})!"
            self.pot = 0
        else:
            self.message = f"Tie! {', '.join(w.name for w in winners)}. Pot rolls over!"

        self.pending_resolution = True

    def end_round(self):
        self._cleanup_busts()

        active_players = self.get_active_players()
        if len(active_players) <= 1 or self.round >= MAX_ROUNDS:
            self.finish_game()
            return

        self.state = STATE_SHOP
        self.message = "Round finished! Visiting the shop..."
        self._build_turn_order_from_starter()
        self.prepare_shop_turn()

    def prepare_shop_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.start_next_round()
            return

        p = self.get_current_turn_player()
        if not p:
            self.start_next_round()
            return

        if p.is_ai or p.name in self.disconnected_players:
            self.message = f"{p.name} is shopping..."
            self.pending_resolution = True
        else:
            self.message = f"{p.name}, buy an item or exit the shop."

    def execute_ai_shop_turn(self):
        p = self.get_current_turn_player()
        if not p:
            return

        bought = False
        bought_name = None

        if p.personality == "Aggressive":
            targets = [("Extra Die", COST_EXTRA_DIE), ("Reroll", COST_REROLL), ("Swap", COST_SWAP)]
        elif p.personality == "Balanced":
            targets = [("Swap", COST_SWAP), ("Extra Die", COST_EXTRA_DIE), ("Reroll", COST_REROLL)]
        else:
            targets = [("Reroll", COST_REROLL), ("Swap", COST_SWAP), ("Extra Die", COST_EXTRA_DIE)]

        for name, cost in targets:
            if p.inventory.get(name, 0) < 2 and p.buy_item(name, cost):
                bought = True
                bought_name = name
                break

        if bought:
            self.message = f"{p.name} ({p.personality}) bought {bought_name}!"
        else:
            self.message = f"{p.name} ({p.personality}) skipped the shop."

        self.current_turn_idx += 1
        self.prepare_shop_turn()

    def start_next_round(self):
        self.round += 1
        self.starter = None
        self.turn_order = []
        self.current_turn_idx = 0
        self.current_bet = CURRENCY_STEP

        for p in self.players:
            p.dice = []
            p.is_starter = False
            p.has_used_powerup = False

        self.start_initiative()

    def finish_game(self):
        self.state = STATE_GAMEOVER
        standings = sorted(self.players, key=lambda x: x.points, reverse=True)
        self.turn_order = standings

        if standings:
            self.message = f"Game Over! Winner: {standings[0].name}"
        else:
            self.message = "Game Over!"

    # =========================================================
    # Action dispatcher
    # =========================================================

    def apply_player_action(self, player_name: str, action_dict: dict) -> Tuple[bool, Optional[str]]:
        if not self.started:
            return False, "Game is nog niet gestart."

        player = self.get_player_by_name(player_name)
        if not player:
            return False, "Speler niet gevonden."

        if player.is_bust:
            return False, "Bust players kunnen geen acties uitvoeren."

        action = action_dict.get("action")
        value = action_dict.get("value")
        item = action_dict.get("item")

        if self.state == STATE_BETTING:
            return self._handle_betting_action(player, action, value)

        if self.state == STATE_POWERUP_TURN:
            return self._handle_powerup_action(player, action, item)

        if self.state == STATE_SHOP:
            return self._handle_shop_action(player, action, item)

        return False, f"Geen acties toegestaan tijdens fase {self.state}."

    def _handle_betting_action(self, player: Player, action: str, value) -> Tuple[bool, Optional[str]]:
        if player != self.starter:
            return False, "Alleen de starter mag de bet instellen."
        if player.is_ai:
            return False, "AI betting wordt server-side afgehandeld."

        table_cap = self.get_table_cap()

        if action == "change_bet":
            if value not in (-CURRENCY_STEP, CURRENCY_STEP):
                return False, "Ongeldige bet wijziging."

            new_bet = self.current_bet + value
            new_bet = max(CURRENCY_STEP, new_bet)
            new_bet = min(new_bet, table_cap, MAX_BET)

            if new_bet == self.current_bet:
                return False, "Bet blijft ongewijzigd."

            self.current_bet = new_bet
            self.message = f"{player.name} changed the bet to {self.current_bet}."
            return True, self.message

        if action == "confirm_bet":
            self.collect_bets()
            self.state = STATE_ROLL_ALL
            self.pending_resolution = True
            return True, f"{player.name} confirmed the bet."

        return False, "Ongeldige betting action."

    def _handle_powerup_action(self, player: Player, action: str, item: Optional[str]) -> Tuple[bool, Optional[str]]:
        current = self.get_current_turn_player()
        if player != current:
            return False, "Je bent niet aan de beurt."

        if action == "pass_turn":
            self.message = f"{player.name} passed."
            self.current_turn_idx += 1
            self.prepare_powerup_turn()
            return True, self.message

        if action == "use_powerup":
            if item not in ("Reroll", "Swap", "Extra Die"):
                return False, "Ongeldig power-up item."

            if item == "Extra Die" and len(player.dice) >= 3:
                return False, "Extra Die kan niet meer gebruikt worden."

            if item == "Swap":
                opponents = [o for o in self.get_active_players() if o != player]
                if not opponents:
                    return False, "Geen geldige swap target."
                best_opp = max(opponents, key=lambda x: sum(x.dice))
                if not best_opp.dice or not player.dice:
                    return False, "Swap is nu niet mogelijk."

            if not self.use_powerup(player, item):
                return False, f"{item} kon niet gebruikt worden."

            self.message = f"{player.name} used {item}."
            self.current_turn_idx += 1
            self.prepare_powerup_turn()
            return True, self.message

        return False, "Ongeldige power-up action."

    def _handle_shop_action(self, player: Player, action: str, item: Optional[str]) -> Tuple[bool, Optional[str]]:
        current = self.get_current_turn_player()
        if player != current:
            return False, "Je bent niet aan de beurt."

        item_costs = {
            "Reroll": COST_REROLL,
            "Swap": COST_SWAP,
            "Extra Die": COST_EXTRA_DIE,
        }

        if action == "shop_exit":
            self.message = f"{player.name} left the shop."
            self.current_turn_idx += 1
            self.prepare_shop_turn()
            return True, self.message

        if action == "buy_item":
            if item not in item_costs:
                return False, "Ongeldig shop item."

            if not player.buy_item(item, item_costs[item]):
                return False, f"Niet genoeg punten voor {item}."

            self.message = f"{player.name} bought {item}."
            self.current_turn_idx += 1
            self.prepare_shop_turn()
            return True, self.message

        return False, "Ongeldige shop action."

    # =========================================================
    # Engine progression
    # =========================================================

    def tick(self) -> bool:
        """
        Laat de game autonoom verdergaan waar nodig.
        Returnt True als state/message/board waarschijnlijk gewijzigd is.
        """
        if not self.started:
            return False

        if self.state == STATE_GAMEOVER:
            return False

        if self._all_humans_disconnected():
            self.finish_game()
            return True

        if self.pending_resolution:
            self.pending_resolution = False

            if self.state == STATE_INITIATIVE:
                if self.starter:
                    self.start_betting()
                else:
                    self.resolve_initiative()
                return True

            if self.state == STATE_ROLL_ALL:
                self.roll_all()
                return True

            if self.state == STATE_SHOWDOWN:
                self.end_round()
                return True

            if self.state == STATE_POWERUP_TURN:
                p = self.get_current_turn_player()
                if p and (p.is_ai or p.name in self.disconnected_players):
                    self.execute_ai_powerup()
                    return True

            if self.state == STATE_SHOP:
                p = self.get_current_turn_player()
                if p and (p.is_ai or p.name in self.disconnected_players):
                    self.execute_ai_shop_turn()
                    return True

        else:
            if self.state == STATE_POWERUP_TURN:
                p = self.get_current_turn_player()
                if p and (p.is_ai or p.name in self.disconnected_players):
                    self.execute_ai_powerup()
                    return True

            if self.state == STATE_SHOP:
                p = self.get_current_turn_player()
                if p and (p.is_ai or p.name in self.disconnected_players):
                    self.execute_ai_shop_turn()
                    return True

        return False