import pygame
import pygame.gfxdraw
import sys
import random
from constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, HEADER_HEIGHT, FOOTER_HEIGHT, GAME_HEIGHT, FPS, COLOR_TABLE_GREEN, COLOR_WHITE, COLOR_BLACK,
    COLOR_GREY, COLOR_BROWN, COLOR_RED, COLOR_GOLD, STATE_INITIATIVE, STATE_BETTING,
    STATE_ROLL_ALL, STATE_POWERUP_TURN, STATE_SHOWDOWN, STATE_SHOP, STATE_GAMEOVER,
    COST_REROLL, COST_SWAP, COST_EXTRA_DIE, MAX_ROUNDS, CURRENCY_STEP, MAX_BET, DICE_SIZE
)
from dice_renderer import draw_die
from player import Player

class Game:
    def __init__(self, screen):
        self.screen = screen
        self.background_image = pygame.transform.scale(pygame.image.load("assets/Pokertable_edit.png").convert(), (SCREEN_WIDTH, GAME_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 20)
        self.large_font = pygame.font.SysFont("Arial", 40, bold=True)
        self.btn_font = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_title = pygame.font.Font("assets/RetroCasino.ttf", 72)
        self.bet_font = pygame.font.SysFont("Arial", 32, bold=True) # Een stuk groter dan de 18 van de buttons
        self.previous_dice_snapshots = {}
        self.dice_animation_timers = {}
        self.DICE_ANIMATION_LENGTH = 30

        # Initialize attributes to satisfy linter
        self.players = []
        self.round = 1
        self.pot = 0
        self.state = STATE_INITIATIVE
        self.starter = None
        self.turn_order = []
        self.current_turn_idx = 0
        self.message = ""
        self.state_timer = 0
        self.current_bet = 50
        self.initiative_rolls = {}
        self.tied_players = []
        self.buttons = []
        
        self.reset_game()

        try:
            # 1. Laad het muziekbestand
            pygame.mixer.music.load("assets/TheEntertainer.mp3")
            self.diceroll_sfx = pygame.mixer.Sound("assets/rolldice_crop.mp3")

            # 2. Stel het volume in (0.0 tot 1.0)
            # 0.3 is vaak genoeg voor achtergrondmuziek zonder dat het irritant wordt
            pygame.mixer.music.set_volume(0.3)
            self.diceroll_sfx.set_volume(0.5) # Iets luider voor de dobbelsteenrolgeluiden

            # 3. Start het afspelen
            # De parameter -1 zorgt ervoor dat het nummer oneindig herhaalt (loopt)
            pygame.mixer.music.play(-1) 

        except Exception as e:
            print(f"Muziekfout: {e}")
            self.diceroll_sfx = None

    def reset_game(self):
        self.players = [
            Player("P1 (You)", is_ai=False),
            Player("P2 (AI)", is_ai=True, personality="Aggressive"),
            Player("P3 (AI)", is_ai=True, personality="Balanced"),
            Player("P4 (AI)", is_ai=True, personality="Defensive")
        ]
        self.round = 1
        self.pot = 0
        self.state = STATE_INITIATIVE
        self.starter = None
        self.turn_order = []
        self.current_turn_idx = 0
        self.message = "Game Started! Roll for initiative."
        self.state_timer = 0
        self.current_bet = 50
        self.initiative_rolls = {} 
        self.tied_players = []
        self.buttons = []
        
        self.start_initiative()

    def get_table_cap(self):
        active_players = self.get_active_players()
        if not active_players: return 0
        raw_cap = min(p.points for p in active_players)
        return min(raw_cap, MAX_BET)

    def start_initiative(self):
        print(f"DEBUG START: Round {self.round} initiative")
        self.state = STATE_INITIATIVE
        self.initiative_rolls = {}
        self.starter = None
        self.tied_players = self.get_active_players()
        self.message = "Rolling for Initiative..."
        self.roll_initiative() # First roll
        self.state_timer = 150

    def roll_initiative(self):
        # We only roll for tied_players (which is all active players initially)
        for p in self.tied_players:
            roll = random.randint(1, 6)
            self.initiative_rolls[p] = roll
            p.dice = [roll]
        print(f"DEBUG: Initiative rolls: {[(p.name, r) for p, r in self.initiative_rolls.items()]}")

    def get_active_players(self):
        return [p for p in self.players if p and not p.is_bust]

    def resolve_initiative(self):
        if not self.initiative_rolls:
            self.roll_initiative()
            
        max_roll = max(self.initiative_rolls.values())
        highest_players = [p for p, roll in self.initiative_rolls.items() if roll == max_roll]
        
        if len(highest_players) > 1:
            self.tied_players = highest_players
            self.starter = None
            self.message = f"Tie! {', '.join([p.name for p in highest_players])} roll again!"
            # CLEAR ROLLS for next time
            self.initiative_rolls = {}
            for p in self.tied_players: p.dice = []
        else:
            self.starter = highest_players[0]
            self.tied_players = []
            for p in self.players:
                if p: p.is_starter = False
            if self.starter:
                self.starter.is_starter = True
                self.message = f"{self.starter.name} wins the roll! Starting Game..."
                print(f"DEBUG: Starter chosen: {self.starter.name}")
            else:
                self.message = "Tie resolving..."
                print("DEBUG: Starter resolution failed, retrying...")
        
        self.state_timer = 150

    def start_betting(self):
        self.state = STATE_BETTING
        for p in self.players:
            if p: p.dice = [] # Clear initiative rolls
        
        if not self.starter:
            self.message = "Error: No starter player defined!"
            self.state_timer = 150
            return
        
        table_cap = self.get_table_cap()
        self.current_bet = 50
        
        if self.starter.is_ai:
            if self.starter.personality == "Aggressive":
                # Aggressive bets high if possible
                self.current_bet = table_cap if self.starter.points >= 100 else 50
            elif self.starter.personality == "Balanced":
                # Balanced bets half of cap or 100
                self.current_bet = min(table_cap, 150) if self.starter.points >= 300 else 50
            else: # Defensive
                self.current_bet = 50
            
            self.message = f"{self.starter.name} ({self.starter.personality}) set the bet to {self.current_bet}."
            self.state_timer = 180 
        else:
            self.message = f"Your turn! Set the bet (Table Cap: {table_cap})"
            # Buttons will be created in draw/handled in event loop

    def collect_bets(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.subtract_points(self.current_bet)
            self.pot += self.current_bet
        self.message = f"All players paid {self.current_bet}. Pot: {self.pot}. Roll All!"
        self.state_timer = 120

    def roll_all(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.dice = [random.randint(1, 6), random.randint(1, 6)]
            p.has_used_powerup = False
        self.message = "Everyone rolled! Power-up turns starting..."
        self.state = STATE_POWERUP_TURN
        
        # Set turn order: starting from starter clockwise
        try:
            starter_idx = self.players.index(self.starter) if self.starter in self.players else 0
        except ValueError:
            starter_idx = 0
            
        print(f"DEBUG: Preparing powerup turn order from starter index {starter_idx}")
        self.turn_order = []
        for i in range(4):
            p = self.players[(starter_idx + i) % 4]
            if p and not p.is_bust:
                self.turn_order.append(p)
        self.current_turn_idx = 0
        self.prepare_powerup_turn()

    def prepare_powerup_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.state = STATE_SHOWDOWN
            self.resolve_showdown()
            return

        p = None
        if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
            p = self.turn_order[self.current_turn_idx]

        if p and p.is_ai:
            self.execute_ai_powerup()
        else:
            self.message = f"Your turn! Use a power-up or Pass."

    def execute_ai_powerup(self):
        p = None
        if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
            p = self.turn_order[self.current_turn_idx]
        if not p: return
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

        if self.round == 10:
            # Last round: use anything to win
            for pt in ["Extra Die", "Swap", "Reroll"]:
                if p.has_powerup(pt):
                    if pt == "Swap" and max(best_opp.dice) <= min(p.dice): continue
                    if self.use_powerup(p, pt):
                        used = True
                        choice = pt
                        break
        else:
            if p.personality == "Aggressive":
                # Aggressive uses Extra Die early, or Reroll if score < 10
                if p.has_powerup("Extra Die") and len(p.dice) < 3:
                    self.use_powerup(p, "Extra Die")
                    used = True
                    choice = "Extra Die"
                elif p.has_powerup("Reroll") and my_score < 10:
                    self.use_powerup(p, "Reroll")
                    used = True
                    choice = "Reroll"
            elif p.personality == "Balanced":
                # Balanced uses if losing or round >= 7
                if my_score <= opp_score or self.round >= 7:
                    if p.has_powerup("Swap") and max(best_opp.dice) > min(p.dice):
                        self.use_powerup(p, "Swap")
                        used = True
                        choice = "Swap"
                    elif p.has_powerup("Extra Die") and len(p.dice) < 3:
                        self.use_powerup(p, "Extra Die")
                        used = True
                        choice = "Extra Die"
            else: # Defensive
                # Defensive only uses if losing by a lot (>3)
                if opp_score - my_score > 3:
                    if p.has_powerup("Swap") and max(best_opp.dice) > min(p.dice):
                        self.use_powerup(p, "Swap")
                        used = True
                        choice = "Swap"
                    elif p.has_powerup("Reroll") and my_score < 6:
                        self.use_powerup(p, "Reroll")
                        used = True
                        choice = "Reroll"

        if not used:
            self.message = f"{p.name} ({p.personality}) passed."
        else:
            self.message = f"{p.name} ({p.personality}) used {choice}!"
        
        self.current_turn_idx += 1
        self.state_timer = 180

    def use_powerup(self, player, p_type):
        if player.has_used_powerup: return False
        if not player.use_powerup(p_type): return False
        
        player.has_used_powerup = True
        if p_type == "Reroll":
            player.dice = [random.randint(1, 6), random.randint(1, 6)]
            self.message = f"{player.name} used Reroll!"
        elif p_type == "Extra Die":
            player.dice.append(random.randint(1, 6))
            self.message = f"{player.name} added an Extra Die!"
        elif p_type == "Swap":
            # Swap lowest of player with highest of best opponent
            opponents = [o for o in self.get_active_players() if o != player]
            best_opp = max(opponents, key=lambda x: sum(x.dice))
            
            p_min_idx = player.dice.index(min(player.dice))
            o_max_idx = best_opp.dice.index(max(best_opp.dice))
            
            player.dice[p_min_idx], best_opp.dice[o_max_idx] = best_opp.dice[o_max_idx], player.dice[p_min_idx]
            self.message = f"{player.name} swapped with {best_opp.name}!"
        
        return True

    def resolve_showdown(self):
        active_players = self.get_active_players()
        scores = {p: sum(p.dice) for p in active_players}
        max_score = max(scores.values())
        winners = [p for p, s in scores.items() if s == max_score]

        if len(winners) == 1:
            winner = winners[0]
            winner.add_points(self.pot)
            self.message = f"Winner: {winner.name} (+{self.pot} pts)!"
            self.pot = 0
        else:
            self.message = f"Tie! {', '.join([w.name for w in winners])}. Pot Rolls Over!"
        
        self.state_timer = 240 # Show results longer

    def end_round(self):
        # Check for busts
        for p in self.players:
            if p and p.points <= 0:
                p.is_bust = True
                p.points = 0
        
        active_players = self.get_active_players()
        if len(active_players) <= 1 or self.round > MAX_ROUNDS:
            self.state = STATE_GAMEOVER
            self.message = "Game Over!"
            # Sort players by points for standings
            self.turn_order = sorted(self.players, key=lambda x: x.points, reverse=True)
            return
        else:
            self.state = STATE_SHOP
            print("DEBUG: State changed to SHOP")
            self.message = "Round finished! Visiting the Shop..."
            # Use same turn order as power-ups
            try:
                starter_idx = self.players.index(self.starter) if (self.starter and self.starter in self.players) else 0
            except ValueError:
                starter_idx = 0
            self.turn_order = []
            for i in range(4):
                p = self.players[(starter_idx + i) % 4]
                if p and not p.is_bust:
                    self.turn_order.append(p)
            self.current_turn_idx = 0
            self.prepare_shop_turn()

    def prepare_shop_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.start_next_round()
            return

        p = None
        if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
            p = self.turn_order[self.current_turn_idx]

        if p and p.is_ai:
            self.execute_ai_shop_turn()
        else:
            self.message = f"Your turn! Buy items (Min 50 pts reserve)."

    def execute_ai_shop_turn(self):
        p = None
        if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
            p = self.turn_order[self.current_turn_idx]
        if not p: return
        bought = False
        item_name = ""
        
        # Priority based on personality
        if p.personality == "Aggressive":
            targets = [("Extra Die", COST_EXTRA_DIE), ("Reroll", COST_REROLL), ("Swap", COST_SWAP)]
        elif p.personality == "Balanced":
            targets = [("Swap", COST_SWAP), ("Extra Die", COST_EXTRA_DIE), ("Reroll", COST_REROLL)]
        else: # Defensive
            targets = [("Reroll", COST_REROLL), ("Swap", COST_SWAP), ("Extra Die", COST_EXTRA_DIE)]

        for name, cost in targets:
            # Buy if has < 2 and can afford
            if p.inventory.get(name, 0) < 2:
                if p.buy_item(name, cost):
                    self.message = f"{p.name} ({p.personality}) bought {name}!"
                    self.state_timer = 150
                    bought = True
                    item_name = name
                    break
        
        if not bought:
            self.message = f"{p.name} ({p.personality}) skipped the shop."
        
        self.current_turn_idx += 1
        self.state_timer = 150

    def start_next_round(self):
        self.round += 1
        self.starter = None # CRITICAL: Reset starter for new round
        for p in self.players:
            if p:
                p.dice = []
                p.is_starter = False
                p.has_used_powerup = False
        self.start_initiative()

    def update(self):
        if self.state_timer > 0:
            self.state_timer -= 1
            if self.state_timer == 0:
                print(f"Transitioning from {self.state}...")
                if self.state == STATE_INITIATIVE:
                    print("DEBUG: Initiative timer ended")
                    if self.starter:
                        self.start_betting()
                    else:
                        self.resolve_initiative()
                elif self.state == STATE_BETTING:
                    if self.starter and self.starter.is_ai:
                        self.collect_bets()
                        self.state = STATE_ROLL_ALL
                elif self.state == STATE_ROLL_ALL:
                    self.roll_all()
                elif self.state == STATE_POWERUP_TURN:
                    self.prepare_powerup_turn()
                elif self.state == STATE_SHOWDOWN:
                    self.end_round()
                elif self.state == STATE_SHOP:
                    self.prepare_shop_turn()
        if self.state == STATE_GAMEOVER:
            # Fade de muziek uit in 2 seconden (2000 ms) voor een dramatisch effect
            pygame.mixer.music.fadeout(2000)

    def handle_click(self, pos):
        if self.state == STATE_GAMEOVER:
            for btn in self.buttons:
                if btn['rect'].collidepoint(pos):
                    if btn['id'] == "play_again":
                        self.reset_game()
            return

        if self.state == STATE_BETTING and self.starter and not self.starter.is_ai:
            table_cap = self.get_table_cap()
            for btn in self.buttons:
                if btn['rect'].collidepoint(pos):
                    if btn['id'] == "bet_plus":
                        self.current_bet = min(self.current_bet + 50, table_cap, MAX_BET)
                    elif btn['id'] == "bet_minus":
                        if self.current_bet - 50 >= 50:
                            self.current_bet -= 50
                    elif btn['id'] == "bet_confirm":
                        self.collect_bets()
                        self.state = STATE_ROLL_ALL
        
        elif self.state == STATE_POWERUP_TURN:
            if self.current_turn_idx < len(self.turn_order):
                p = None
                if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
                    p = self.turn_order[self.current_turn_idx]
                if p and not p.is_ai:
                    for btn in self.buttons:
                        if btn['rect'].collidepoint(pos):

                            if btn['id'] == "pw_pass":
                                self.message = "You passed."
                                self.current_turn_idx += 1
                                self.state_timer = 90

                            elif btn['id'] == "pw_reroll":
                                if self.use_powerup(p, "Reroll"):
                                    self.current_turn_idx += 1
                                    self.state_timer = 120

                            elif btn['id'] == "pw_extra":
                                if self.use_powerup(p, "Extra Die"):
                                    self.current_turn_idx += 1
                                    self.state_timer = 120

                            elif btn['id'] == "pw_swap":
                                if self.use_powerup(p, "Swap"):
                                    self.current_turn_idx += 1
                                    self.state_timer = 120
        
        elif self.state == STATE_SHOP:
            if self.current_turn_idx < len(self.turn_order):
                p = None
                if self.turn_order and 0 <= self.current_turn_idx < len(self.turn_order):
                    p = self.turn_order[self.current_turn_idx]

                if p and not p.is_ai:
                    for btn in self.buttons:
                        if btn['rect'].collidepoint(pos):

                            if btn['id'] == "shop_exit":
                                self.message = "Skipped shop."
                                self.current_turn_idx += 1
                                self.state_timer = 90

                            elif btn['id'] == "shop_reroll":
                                if p.buy_item("Reroll", COST_REROLL):
                                    self.message = "Bought Reroll!"
                                    self.current_turn_idx += 1
                                    self.state_timer = 120

                            elif btn['id'] == "shop_swap":
                                if p.buy_item("Swap", COST_SWAP):
                                    self.message = "Bought Swap!"
                                    self.current_turn_idx += 1
                                    self.state_timer = 120

                            elif btn['id'] == "shop_extra":
                                if p.buy_item("Extra Die", COST_EXTRA_DIE):
                                    self.message = "Bought Extra Die!"
                                    self.current_turn_idx += 1
                                    self.state_timer = 120

    def draw_aa_rounded_rect(self, surface, rect, color, radius, thickness=1):
        x, y, w, h = rect
        
        # Teken de 4 hoeken (anti-aliased)
        # We tekenen meerdere cirkels voor de dikte, net als bij de pot
        for i in range(thickness):
            r = radius - i
            pygame.gfxdraw.aacircle(surface, x + radius, y + radius, r, color)     # Top-left
            pygame.gfxdraw.aacircle(surface, x + w - radius, y + radius, r, color) # Top-right
            pygame.gfxdraw.aacircle(surface, x + radius, y + h - radius, r, color) # Bottom-left
            pygame.gfxdraw.aacircle(surface, x + w - radius, y + h - radius, r, color) # Bottom-right

        # Teken de 4 zijden (anti-aliased lijnen)
        # Boven
        pygame.draw.line(surface, color, (x + radius, y), (x + w - radius, y), thickness)
        # Onder
        pygame.draw.line(surface, color, (x + radius, y + h - 1), (x + w - radius, y + h - 1), thickness)
        # Links
        pygame.draw.line(surface, color, (x, y + radius), (x, y + h - radius), thickness)
        # Rechts
        pygame.draw.line(surface, color, (x + w - 1, y + radius), (x + w - 1, y + h - radius), thickness)


    def draw_button(self, x, y, w, h, text, color, btn_id):
        rect = pygame.Rect(x, y, w, h)
        mouse_pos = pygame.mouse.get_pos()
        
        # Check of de muis boven de knop zweeft
        if rect.collidepoint(mouse_pos):
            # Zet cursor op handje als we over een knop zweven
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            
            # Kleur lichter maken voor de hover
            draw_color = tuple(min(255, int(c * 1.2)) for c in color)
        else:
            draw_color = color

        # Teken de knop
        pygame.draw.rect(self.screen, draw_color, rect, border_radius=15)

        # Teken de buitenlijn van 1 pixel
        pygame.draw.rect(self.screen, COLOR_BLACK, rect, width=1, border_radius=15)
        # Teken een tweede, iets transparantere binnenlijn voor optische zachtheid
        inner_rect = rect.inflate(-1, -1)
        pygame.draw.rect(self.screen, (0, 0, 0, 60), inner_rect, width=1, border_radius=14)


        
        txt = self.btn_font.render(text, True, COLOR_WHITE)
        self.screen.blit(txt, (x + w//2 - txt.get_width()//2, y + h//2 - txt.get_height()//2))
        
        self.buttons.append({'rect': rect, 'id': btn_id})

    def draw(self):
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        self.buttons = []


        # ===== BACKGROUND (CASINO TABLE) =====
        self.screen.blit(self.background_image, (0, HEADER_HEIGHT))

        # pygame.draw.ellipse(self.screen, (0, 110, 0),
        #                     (80, 40, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 80))
        # pygame.draw.ellipse(self.screen, (212, 175, 55),
        #                     (80, 40, SCREEN_WIDTH - 160, SCREEN_HEIGHT - 80), 6)

        # pygame.draw.circle(self.screen, (0, 90, 0),
        #                 (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), 180)

        # ===== TITLE =====
        title = self.font_title.render("HIGH ROLLER", True, COLOR_GOLD)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 10 + HEADER_HEIGHT))


        # ===== HEADER =====

        # Maak een semi-transparante balk bovenin
        pygame.draw.rect(self.screen, COLOR_BLACK, (0, 0, SCREEN_WIDTH, HEADER_HEIGHT))

        # Verplaats Round & State naar de hoeken
        round_txt = self.font.render(f"ROUND: {self.round}", True, COLOR_WHITE)
        state_txt = self.font.render(f"PHASE: {self.state}", True, COLOR_GOLD)

        self.screen.blit(round_txt, (20, 10)) # Top-links
        self.screen.blit(state_txt, (SCREEN_WIDTH - state_txt.get_width() - 20, 10)) # Top-rechts


        # ==== FOOTER ==== 
        footer_y = SCREEN_HEIGHT - FOOTER_HEIGHT # Dit is 840
        pygame.draw.rect(self.screen, COLOR_BLACK, (0, footer_y, SCREEN_WIDTH, FOOTER_HEIGHT))

        if self.message:
            msg_txt = self.font.render(self.message, True, COLOR_WHITE)
            msg_x = SCREEN_WIDTH // 2 - msg_txt.get_width() // 2
            # We zetten de tekst in de onderste balk
            self.screen.blit(msg_txt, (msg_x, footer_y + 10))

        # ===== POT (CENTER) =====
        cx = SCREEN_WIDTH // 2
        cy = HEADER_HEIGHT + GAME_HEIGHT // 2 

        # pygame.draw.circle(self.screen, (30, 30, 30), (cx, cy), 75)
        # pygame.draw.circle(self.screen, COLOR_GOLD, (cx, cy), 75, 4)

        # Teken de gevulde cirkel (anti-aliased)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, 75, (30, 30, 30))
        pygame.gfxdraw.filled_circle(self.screen, cx, cy, 75, (30, 30, 30))

        # Teken de gouden rand (anti-aliased)
        border_thickness = 6 # Pas dit aan voor meer of minder dikte
        for i in range(border_thickness):
            # We tekenen cirkels van straal 75 naar binnen toe (75, 74, 73, etc.)
            pygame.gfxdraw.aacircle(self.screen, cx, cy, 75 - i, COLOR_GOLD)
        # pygame.gfxdraw.aacircle(self.screen, cx, cy, 75, COLOR_GOLD)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, 74, COLOR_GOLD)

        pot_text = self.large_font.render(f"${self.pot}", True, COLOR_GOLD)
        self.screen.blit(pot_text, (cx - pot_text.get_width() // 2, cy - 19))


        # ===== SHOP MODE BACKGROUND =====
        if self.state == STATE_SHOP:
            overlay = pygame.Surface((SCREEN_WIDTH, GAME_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((20, 20, 35))
            self.screen.blit(overlay, (0, HEADER_HEIGHT))

        # ===== PLAYER PANELS =====
        # Centraal punt voor horizontale uitlijning
        center_x = SCREEN_WIDTH // 2
        # Het verticale midden van de tafel-foto (voor P2 en P4)
        table_center_y = HEADER_HEIGHT + (GAME_HEIGHT // 2)

        positions = [
            # P1 (Onderaan):
            (center_x - 130, SCREEN_HEIGHT - FOOTER_HEIGHT - 210), 
            
            # P2 (Links): Verticaal gecentreerd op het laken
            (50, table_center_y - 85), 
            
            # P3 (Bovenaan): Verlaagd om de titel vrij te houden (y=130)
            (center_x - 130, HEADER_HEIGHT + 110), 
            
            # P4 (Rechts): Verticaal gecentreerd op het laken
            (SCREEN_WIDTH - 310, table_center_y - 85) 
]

        for i, p in enumerate(self.players):
            if not p:
                continue

            x, y = positions[i]
            w, h = 260, 170

            # Panel base
            panel_color = (40, 40, 40) if not p.is_bust else (80, 80, 80)
            pygame.draw.rect(self.screen, panel_color, (x, y, w, h), border_radius=14)

            # Gold border if starter
            if self.starter and p == self.starter:
                pygame.draw.rect(self.screen, COLOR_GOLD, (x-3, y-3, w+6, h+6), 3, border_radius=16)

            # Turn highlight
            is_turn = (
                self.state in [STATE_POWERUP_TURN, STATE_SHOP] and
                self.turn_order and
                self.current_turn_idx < len(self.turn_order) and
                self.turn_order[self.current_turn_idx] == p
            )

            if is_turn:
                pygame.draw.rect(self.screen, (0, 255, 255),
                                (x-5, y-5, w+10, h+10), 3, border_radius=16)

            pygame.draw.rect(self.screen, COLOR_BLACK, (x, y, w, h), 2, border_radius=14)


            # ===== PLAYER PANEL HEADER =====
            # 1. Bereken het totaal aantal ogen
            total_eyes = sum(p.dice) if p.dice else 0

            # 2. Render de tekst voor de drie kolommen
            name_txt = self.font.render(p.name, True, COLOR_WHITE)
            pts_txt = self.font.render(f"${p.points}", True, COLOR_GOLD)
            total_txt = self.font.render(f"Eyes: {total_eyes}", True, (180, 180, 180)) # Subtiel grijs

            # 3. Posities berekenen voor de header-rij (y + 8 voor wat padding)
            header_y = y + 8
            self.screen.blit(name_txt, (x + 12, header_y)) # Links: Naam
            self.screen.blit(total_txt, (x + (w // 2) - (total_txt.get_width() // 2), header_y)) # Midden: Totaal
            self.screen.blit(pts_txt, (x + w - pts_txt.get_width() - 12, header_y)) # Rechts: Saldo

            # 4. Trek een subtiele scheidingslijn (separator)
            # We tekenen een donkergrijze lijn net onder de tekst (op y + 35)
            pygame.draw.line(self.screen, (60, 60, 60), (x, y + 35), (x + w, y + 35), 1)



            # # Player name + points
            # name = self.font.render(p.name, True, COLOR_WHITE)
            # pts = self.font.render(f"${p.points}", True, COLOR_GOLD)

            # self.screen.blit(name, (x + 10, y + 10))
            # self.screen.blit(pts, (x + 10, y + 40))

            # Dice (centered)
            # if p.dice:
            #     total_w = len(p.dice) * (DICE_SIZE + 10) - 10
            #     start_x = x + (w - total_w) // 2

            #     for j, val in enumerate(p.dice):
            #         draw_die(self.screen, start_x + j * (DICE_SIZE + 10), y + 55, val)


            # ===== DICE (CENTER) =====
            current_logical_dice = p.dice if p.dice else [] # Fix: 'player' -> 'p'
            dice_to_render = current_logical_dice

            # --- ANIMATIE LOGICA START ---
            player_name = p.name # Fix: 'player' -> 'p'
            prev_dice = self.previous_dice_snapshots.get(player_name, [])
            curr_timer = self.dice_animation_timers.get(player_name, 0)

            

            if current_logical_dice and current_logical_dice != prev_dice and curr_timer == 0:
                self.dice_animation_timers[player_name] = self.DICE_ANIMATION_LENGTH
                curr_timer = self.DICE_ANIMATION_LENGTH

                if self.diceroll_sfx:
                    self.diceroll_sfx.play()

            self.previous_dice_snapshots[player_name] = list(current_logical_dice)

            if curr_timer > 0:
                num_dice_to_animate = len(current_logical_dice) if len(current_logical_dice) > 0 else 2
                dice_to_render = [random.randint(1, 6) for _ in range(num_dice_to_animate)]
                self.dice_animation_timers[player_name] -= 1
                progress = (self.DICE_ANIMATION_LENGTH - curr_timer) / self.DICE_ANIMATION_LENGTH
                angle = progress * 720 
            else:
                angle = 0

            # --- ANIMATIE LOGICA EIND ---

            # Bereken de startpositie zodat de dobbelstenen gecentreerd staan in het panel
            total_dice_width = len(dice_to_render) * (DICE_SIZE + 10) - 10
            start_dice_x = x + (w - total_dice_width) // 2

            for j, val in enumerate(dice_to_render):
                # Fix: 'dx' -> 'x' en 'dy' -> 'y'
                # We zetten ze op y + 65 om ze onder de nieuwe header te plaatsen
                px = start_dice_x + j * (DICE_SIZE + 10)
                py = y + 55

                if curr_timer > 0:
                    temp_size = int(DICE_SIZE * 1.5)
                    die_surf = pygame.Surface((temp_size, temp_size), pygame.SRCALPHA)
                    
                    # Belangrijk: we roepen draw_die direct aan (niet via self.dice_renderer)
                    # We geven 'self' mee omdat de functie dat verwacht in dice_renderer.py
                    offset = (temp_size - DICE_SIZE) // 2
                    draw_die(self, offset, offset, DICE_SIZE, val, target_surf=die_surf)
                    
                    rotated_die = pygame.transform.rotate(die_surf, angle)
                    new_rect = rotated_die.get_rect(center=(px + DICE_SIZE // 2, py + DICE_SIZE // 2))
                    self.screen.blit(rotated_die, new_rect)
                else:
                    # Statische render
                    draw_die(self, px, py, DICE_SIZE, val)


            # ===== INVENTORY (BADGES) =====
            if p.inventory:
                # Muted palette voor een rustiger totaalbeeld
                badge_colors = {
                    "Reroll": (120, 90, 70),    # Gedempt terracotta
                    "Swap": (80, 95, 120),      # Gedempt staalblauw
                    "Extra Die": (85, 110, 85)   # Gedempt saliegroen
                }
                
                badge_h = 26
                badge_y = y + 138
                gap = 10
                
                # STAP 1: Bereken de totale breedte van de hele rij badges
                active_badges = []
                total_row_width = 0
                
                for item_name, count in p.inventory.items():
                    if count <= 0: continue
                    label = f"{item_name[0]} x{count}"
                    txt_surf = self.font.render(label, True, (220, 220, 220))
                    b_w = txt_surf.get_width() + 16 # Breedte inclusief padding
                    active_badges.append((txt_surf, b_w, item_name))
                    total_row_width += b_w
                
                # Voeg de tussenruimtes (gaps) toe aan de totale breedte
                if active_badges:
                    total_row_width += gap * (len(active_badges) - 1)
                    
                    # STAP 2: Bereken het gecentreerde startpunt
                    # (Panel breedte - Totale rij breedte) / 2
                    current_badge_x = x + (260 - total_row_width) // 2 

                    # STAP 3: Teken de badges
                    for txt_surf, b_w, item_name in active_badges:
                        color = badge_colors.get(item_name, COLOR_GREY)
                        
                        # Achtergrond badge
                        pygame.draw.rect(self.screen, color, (current_badge_x, badge_y, b_w, badge_h), border_radius=6)
                        # Subtiele inner-stroke voor diepte
                        pygame.draw.rect(self.screen, (255, 255, 255, 30), (current_badge_x, badge_y, b_w, badge_h), 1, border_radius=6)
                        
                        # Tekst blitten (optisch verticaal gecentreerd met +1 pixel)
                        text_cent_y = badge_y + (badge_h // 2 - txt_surf.get_height() // 2) + 1
                        self.screen.blit(txt_surf, (current_badge_x + 8, text_cent_y))
                        
                        # Schuif op naar de volgende positie
                        current_badge_x += b_w + gap


        # ===== BUTTONS =====

        # Referentiepunt P1 (de speler onderaan)
        p1_y = SCREEN_HEIGHT - FOOTER_HEIGHT - 210     # De bovenkant van het P1 paneel
        p1_center_x = SCREEN_WIDTH // 2

        # We zetten button_y nu op -110 (was -80) om ze hoger te plaatsen
        button_y = p1_y - 110         

        # Betting
        if self.state == STATE_BETTING and self.starter and not self.starter.is_ai:
            # De min en plus knoppen op de bovenste rij
            self.draw_button(p1_center_x - 120, button_y, 50, 40, "-", COLOR_BROWN, "bet_minus")
            self.draw_button(p1_center_x + 70, button_y, 50, 40, "+", COLOR_BROWN, "bet_plus")

            # Het bedrag met het nieuwe grotere font, precies in het midden
            bet_text = self.bet_font.render(f"${self.current_bet}", True, COLOR_GOLD)
            # We centreren het verticaal t.o.v. de - en + knoppen
            text_y = button_y + (40 // 2) - (bet_text.get_height() // 2)
            self.screen.blit(bet_text, (p1_center_x - bet_text.get_width() // 2, text_y))

            # De CONFIRM knop op de tweede rij (50 pixels lager)
            self.draw_button(p1_center_x - 65, button_y + 55, 130, 45, "CONFIRM", (0, 120, 0), "bet_confirm")

        # Powerups
        if self.state == STATE_POWERUP_TURN and self.turn_order:
            p = self.turn_order[self.current_turn_idx] if self.current_turn_idx < len(self.turn_order) else None
            if p and not p.is_ai:
                btn_w = 110
                gap = 20
                start_x = p1_center_x - 250 

                self.draw_button(start_x, button_y + 20, btn_w, 45, "PASS", COLOR_GOLD, "pw_pass")
                self.draw_button(start_x + (btn_w + gap), button_y + 20, btn_w, 45, "REROLL", COLOR_BROWN, "pw_reroll")
                self.draw_button(start_x + 2 * (btn_w + gap), button_y + 20, btn_w, 45, "SWAP", COLOR_BROWN, "pw_swap")
                self.draw_button(start_x + 3 * (btn_w + gap), button_y + 20, btn_w, 45, "EXTRA", COLOR_BROWN, "pw_extra")

        # Shop
        if self.state == STATE_SHOP and self.turn_order:
            p = self.turn_order[self.current_turn_idx] if self.current_turn_idx < len(self.turn_order) else None
            # In main.py -> draw() onder de STATE_SHOP sectie
            if p and not p.is_ai:
                shop_y = button_y - 40 
                btn_w = 160
                gap = 25
                start_x = p1_center_x - 265 # Perfect gecentreerd

                # --- COLOR LOGIC PER ITEM ---
                # We checken of de speler de kosten + de 50 reserve kan betalen
                color_reroll = COLOR_BROWN if p.points >= COST_REROLL + 50 else COLOR_GREY
                color_swap   = COLOR_BROWN if p.points >= COST_SWAP + 50 else COLOR_GREY
                color_extra  = COLOR_BROWN if p.points >= COST_EXTRA_DIE + 50 else COLOR_GREY

                # --- DRAW THE BUTTONS ---
                self.draw_button(start_x, shop_y, btn_w, 45, f"REROLL ({COST_REROLL})", color_reroll, "shop_reroll")
                self.draw_button(start_x + (btn_w + gap), shop_y, btn_w, 45, f"SWAP ({COST_SWAP})", color_swap, "shop_swap")
                self.draw_button(start_x + 2 * (btn_w + gap), shop_y, btn_w, 45, f"EXTRA ({COST_EXTRA_DIE})", color_extra, "shop_extra")
                
                # EXIT knop blijft altijd groen en klikbaar
                self.draw_button(p1_center_x - 60, shop_y + 50, 120, 40, "EXIT", (0, 120, 0), "shop_exit")

    def draw_gameover(self):
        self.screen.fill(COLOR_TABLE_GREEN)
        title = self.large_font.render("GAME OVER", True, COLOR_GOLD)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))
        
        # Winners info (turn_order was sorted by points in end_round)
        if self.turn_order:
            winner = self.turn_order[0]
            if winner:
                winner_text = self.large_font.render(f"🏆 WINNER: {winner.name} 🏆", True, COLOR_GOLD)
                score_text = self.large_font.render(f"{winner.points} POINTS", True, COLOR_GOLD)
                self.screen.blit(winner_text, (SCREEN_WIDTH // 2 - winner_text.get_width() // 2, 150))
                self.screen.blit(score_text, (SCREEN_WIDTH // 2 - score_text.get_width() // 2, 210))
            
            # Display standings
            for i, p in enumerate(self.turn_order):
                if not p: continue
                color = COLOR_GOLD if i == 0 else COLOR_WHITE
                txt = self.font.render(f"{i+1}. {p.name}: {p.points} points", True, color)
                self.screen.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, 300 + i * 35))
            
        # UI Buttons for Restart
        self.draw_button(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 180, 200, 50, "PLAY AGAIN", (0, 150, 0), "play_again")
        
        restart_msg = self.font.render("Press 'R' to Restart or 'ESC' to Quit", True, COLOR_GREY)
        self.screen.blit(restart_msg, (SCREEN_WIDTH // 2 - restart_msg.get_width() // 2, SCREEN_HEIGHT - 80))

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("High Roller: Power-up")
    
    game = Game(screen)
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r and game.state == STATE_GAMEOVER:
                    game.reset_game()

        game.update()
        if game.state == STATE_GAMEOVER:
            game.draw_gameover()
        else:
            game.draw()

        pygame.display.flip()
        game.clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    try:
        print("Starting High Roller: Power-up...")
        main()
    except KeyboardInterrupt:
        print("\nGame closed by user (Ctrl+C).")
    except SystemExit:
        pass
    except Exception as e:
        print("\n" + "!"*40)
        print(f"CRITICAL ERROR: {e}")
        print("!"*40)
        import traceback
        traceback.print_exc()
        print("!"*40)
        input("Press Enter to close this window...")
    except:
        print("\nAn unexpected system error occurred.")
        input("Press Enter to close this window...")
