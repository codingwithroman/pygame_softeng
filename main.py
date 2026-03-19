import pygame
import sys
import random
from constants import *
from dice_renderer import draw_die
from player import Player

class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 20)
        self.large_font = pygame.font.SysFont("Arial", 40, bold=True)
        self.btn_font = pygame.font.SysFont("Arial", 24, bold=True)
        
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
        return min(p.points for p in active_players)

    def start_initiative(self):
        self.initiative_rolls = {}
        self.tied_players = self.get_active_players()
        self.message = "Rolling for Initiative..."
        self.resolve_initiative()

    def get_active_players(self):
        return [p for p in self.players if not p.is_bust]

    def resolve_initiative(self):
        for p in self.tied_players:
            roll = random.randint(1, 6)
            self.initiative_rolls[p] = roll
            p.dice = [roll]
            
        max_roll = max(self.initiative_rolls.values())
        highest_players = [p for p, roll in self.initiative_rolls.items() if roll == max_roll]
        
        if len(highest_players) > 1:
            self.tied_players = highest_players
            self.message = f"Tie! {', '.join([p.name for p in highest_players])} roll again!"
            self.state_timer = 150
        else:
            self.starter = highest_players[0]
            for p in self.players: p.is_starter = False
            self.starter.is_starter = True
            self.message = f"{self.starter.name} wins the roll! Starting Game..."
            self.state_timer = 150

    def start_betting(self):
        self.state = STATE_BETTING
        for p in self.players: p.dice = [] # Clear initiative rolls
        
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
        self.state_timer = 60

    def roll_all(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.dice = [random.randint(1, 6), random.randint(1, 6)]
            p.has_used_powerup = False
        self.message = "Everyone rolled! Power-up turns starting..."
        self.state = STATE_POWERUP_TURN
        
        # Set turn order: starting from starter clockwise
        starter_idx = self.players.index(self.starter)
        self.turn_order = []
        for i in range(4):
            p = self.players[(starter_idx + i) % 4]
            if not p.is_bust:
                self.turn_order.append(p)
        self.current_turn_idx = 0
        self.prepare_powerup_turn()

    def prepare_powerup_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.state = STATE_SHOWDOWN
            self.resolve_showdown()
            return

        p = self.turn_order[self.current_turn_idx]
        if p.is_ai:
            self.message = f"{p.name}'s turn (AI)..."
            self.state_timer = 90 # Delay to see AI turn
        else:
            self.message = f"Your turn! Use a power-up or Pass."

    def execute_ai_powerup(self):
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
        self.prepare_powerup_turn()

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
            if p.points <= 0:
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
            self.message = "Round finished! Visiting the Shop..."
            # Use same turn order as power-ups
            starter_idx = self.players.index(self.starter)
            self.turn_order = []
            for i in range(4):
                p = self.players[(starter_idx + i) % 4]
                if not p.is_bust:
                    self.turn_order.append(p)
            self.current_turn_idx = 0
            self.prepare_shop_turn()

    def prepare_shop_turn(self):
        if self.current_turn_idx >= len(self.turn_order):
            self.start_next_round()
            return

        p = self.turn_order[self.current_turn_idx]
        if p.is_ai:
            self.message = f"{p.name} is shopping (AI)..."
            self.state_timer = 180 # Delay for AI shop
        else:
            self.message = f"Your turn! Buy items (Min 50 pts reserve)."

    def execute_ai_shop_turn(self):
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
        self.prepare_shop_turn()

    def start_next_round(self):
        self.round += 1
        for p in self.players:
            p.dice = []
            p.is_starter = False
            p.has_used_powerup = False
        self.start_initiative()

    def update(self):
        if self.state_timer > 0:
            self.state_timer -= 1
            if self.state_timer == 0:
                if self.state == STATE_INITIATIVE:
                    if self.starter:
                        self.start_betting()
                    else:
                        self.resolve_initiative()
                elif self.state == STATE_BETTING:
                    if self.starter.is_ai:
                        self.collect_bets()
                        self.state = STATE_ROLL_ALL
                elif self.state == STATE_ROLL_ALL:
                    self.roll_all()
                elif self.state == STATE_POWERUP_TURN:
                    p = self.turn_order[self.current_turn_idx]
                    if p.is_ai:
                        self.execute_ai_powerup()
                elif self.state == STATE_SHOWDOWN:
                    self.end_round()
                elif self.state == STATE_SHOP:
                    p = self.turn_order[self.current_turn_idx]
                    if p.is_ai:
                        self.execute_ai_shop_turn()

    def handle_click(self, pos):
        if self.state == STATE_BETTING and not self.starter.is_ai:
            table_cap = self.get_table_cap()
            for btn in self.buttons:
                if btn['rect'].collidepoint(pos):
                    if btn['id'] == "bet_plus":
                        if self.current_bet + 50 <= table_cap:
                            self.current_bet += 50
                    elif btn['id'] == "bet_minus":
                        if self.current_bet - 50 >= 50:
                            self.current_bet -= 50
                    elif btn['id'] == "bet_confirm":
                        self.collect_bets()
                        self.state = STATE_ROLL_ALL
        
        elif self.state == STATE_POWERUP_TURN:
            p = self.turn_order[self.current_turn_idx]
            if not p.is_ai:
                for btn in self.buttons:
                    if btn['rect'].collidepoint(pos):
                        if btn['id'] == "pw_pass":
                            self.current_turn_idx += 1
                            self.prepare_powerup_turn()
                        elif btn['id'] == "pw_reroll":
                            if self.use_powerup(p, "Reroll"):
                                self.current_turn_idx += 1
                                self.state_timer = 90
                        elif btn['id'] == "pw_extra":
                            if self.use_powerup(p, "Extra Die"):
                                self.current_turn_idx += 1
                                self.state_timer = 90
                        elif btn['id'] == "pw_swap":
                            if self.use_powerup(p, "Swap"):
                                self.current_turn_idx += 1
                                self.state_timer = 90
        
        elif self.state == STATE_SHOP:
            p = self.turn_order[self.current_turn_idx]
            if not p.is_ai:
                for btn in self.buttons:
                    if btn['rect'].collidepoint(pos):
                        if btn['id'] == "shop_exit":
                            self.current_turn_idx += 1
                            self.prepare_shop_turn()
                        elif btn['id'] == "shop_reroll":
                            if p.buy_item("Reroll", COST_REROLL):
                                self.message = "Bought Reroll!"
                        elif btn['id'] == "shop_swap":
                            if p.buy_item("Swap", COST_SWAP):
                                self.message = "Bought Swap!"
                        elif btn['id'] == "shop_extra":
                            if p.buy_item("Extra Die", COST_EXTRA_DIE):
                                self.message = "Bought Extra Die!"

    def draw_button(self, x, y, w, h, text, color, btn_id):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, COLOR_BLACK, rect, width=2, border_radius=5)
        txt = self.btn_font.render(text, True, COLOR_WHITE)
        self.screen.blit(txt, (x + w//2 - txt.get_width()//2, y + h//2 - txt.get_height()//2))
        self.buttons.append({'rect': rect, 'id': btn_id})

    def draw(self):
        self.screen.fill(COLOR_TABLE_GREEN)
        self.buttons = [] # Reset buttons each frame
        
        if self.state == STATE_GAMEOVER:
            self.draw_gameover()
            return # Don't draw other game elements if game is over
        
        # Draw Title/Round info
        status_text = self.large_font.render(f"Round {self.round} - {self.state}", True, COLOR_GOLD)
        self.screen.blit(status_text, (SCREEN_WIDTH // 2 - status_text.get_width() // 2, 20))
        
        # Draw Pot info
        pot_text = self.font.render(f"POT: {self.pot}", True, COLOR_GOLD)
        self.screen.blit(pot_text, (SCREEN_WIDTH // 2 - pot_text.get_width() // 2, 60))

        # Draw Message
        msg_text = self.font.render(self.message, True, COLOR_WHITE)
        self.screen.blit(msg_text, (SCREEN_WIDTH // 2 - msg_text.get_width() // 2, 90))

        # Draw Betting Controls for human
        if self.state == STATE_BETTING and not self.starter.is_ai:
            self.draw_button(SCREEN_WIDTH//2 - 160, 130, 50, 40, "-", COLOR_BROWN, "bet_minus")
            bet_display = self.btn_font.render(f"Bet: {self.current_bet}", True, COLOR_GOLD)
            self.screen.blit(bet_display, (SCREEN_WIDTH//2 - bet_display.get_width()//2, 135))
            self.draw_button(SCREEN_WIDTH//2 + 110, 130, 50, 40, "+", COLOR_BROWN, "bet_plus")
            self.draw_button(SCREEN_WIDTH//2 - 60, 180, 120, 40, "CONFIRM", (0, 100, 0), "bet_confirm")

        # Draw Power-up Controls for human
        if self.state == STATE_POWERUP_TURN:
            p = self.turn_order[self.current_turn_idx]
            if not p.is_ai:
                self.draw_button(SCREEN_WIDTH//2 - 250, 140, 100, 40, "PASS", COLOR_GREY, "pw_pass")
                if p.has_powerup("Reroll"):
                    self.draw_button(SCREEN_WIDTH//2 - 140, 140, 100, 40, "REROLL", COLOR_BROWN, "pw_reroll")
                if p.has_powerup("Swap"):
                    self.draw_button(SCREEN_WIDTH//2 - 30, 140, 100, 40, "SWAP", COLOR_BROWN, "pw_swap")
                if p.has_powerup("Extra Die"):
                    self.draw_button(SCREEN_WIDTH//2 + 80, 140, 120, 40, "EXTRA DIE", COLOR_BROWN, "pw_extra")

        # Draw Shop Controls for human
        if self.state == STATE_SHOP:
            p = self.turn_order[self.current_turn_idx]
            if not p.is_ai:
                # Layout shop buttons
                self.draw_button(SCREEN_WIDTH//2 - 250, 140, 120, 40, f"Reroll ({COST_REROLL})", COLOR_BROWN if p.points-COST_REROLL>=50 else COLOR_GREY, "shop_reroll")
                self.draw_button(SCREEN_WIDTH//2 - 100, 140, 120, 40, f"Swap ({COST_SWAP})", COLOR_BROWN if p.points-COST_SWAP>=50 else COLOR_GREY, "shop_swap")
                self.draw_button(SCREEN_WIDTH//2 + 50, 140, 140, 40, f"Extra ({COST_EXTRA_DIE})", COLOR_BROWN if p.points-COST_EXTRA_DIE>=50 else COLOR_GREY, "shop_extra")
                self.draw_button(SCREEN_WIDTH//2 - 60, 190, 120, 40, "EXIT SHOP", (0, 100, 0), "shop_exit")

        # Draw Players
        for i, p in enumerate(self.players):
            # ... (rest of the drawing logic remains similar)
            box_width = 250
            box_height = 180
            layout_pos = [
                (SCREEN_WIDTH // 2 - 125, SCREEN_HEIGHT - 200), # P1
                (50, SCREEN_HEIGHT // 2 - 90),                  # P2
                (SCREEN_WIDTH // 2 - 125, 120),                 # P3
                (SCREEN_WIDTH - 300, SCREEN_HEIGHT // 2 - 90)   # P4
            ]
            x, y = layout_pos[i]
            
            # Shifting P3 logic
            needs_shift = False
            if i == 2:
                if self.state == STATE_BETTING and self.starter and not self.starter.is_ai:
                    needs_shift = True
                elif self.state in [STATE_POWERUP_TURN, STATE_SHOP] and self.turn_order and self.current_turn_idx < len(self.turn_order):
                    if not self.turn_order[self.current_turn_idx].is_ai:
                        needs_shift = True
            
            if needs_shift:
                y = 250 

            # highlight current turn
            is_turn = self.state in [STATE_POWERUP_TURN, STATE_SHOP] and self.turn_order and self.current_turn_idx < len(self.turn_order) and self.turn_order[self.current_turn_idx] == p
            
            # Draw box
            color = COLOR_GREY if p.is_bust else (COLOR_RED if p.is_starter else COLOR_BROWN)
            pygame.draw.rect(self.screen, color, (x, y, box_width, box_height), border_radius=10)
            if is_turn:
                pygame.draw.rect(self.screen, COLOR_GOLD, (x-4, y-4, box_width+8, box_height+8), width=4, border_radius=12)
            pygame.draw.rect(self.screen, COLOR_BLACK, (x, y, box_width, box_height), width=2, border_radius=10)

            # Draw player info
            text_color = COLOR_GREY if p.is_bust else COLOR_WHITE
            points_color = COLOR_GREY if p.is_bust else COLOR_GOLD
            name_text = self.font.render(f"{p.name} {'(STARTER)' if p.is_starter else ''}", True, text_color)
            points_text = self.font.render(f"Points: {p.points}", True, points_color)
            self.screen.blit(name_text, (x + 10, y + 10))
            self.screen.blit(points_text, (x + 10, y + 40))

            # Draw dice if any
            for j, val in enumerate(p.dice):
                total_dice_w = len(p.dice) * (DICE_SIZE + 10) - 10
                start_x = x + (box_width - total_dice_w) // 2
                draw_die(self.screen, start_x + j * (DICE_SIZE + 10), y + 70, val)

            # Draw inventory summary
            inv_str = ", ".join([f"{k[0]}:{v}" for k, v in p.inventory.items()])
            inv_text = self.font.render(f"Inv: {inv_str}", True, COLOR_WHITE)
            self.screen.blit(inv_text, (x + 10, y + 145))

    def draw_gameover(self):
        self.screen.fill(COLOR_TABLE_GREEN)
        title = self.large_font.render("GAME OVER", True, COLOR_GOLD)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        
        # Winners info (turn_order was sorted by points in end_round)
        if self.turn_order:
            winner = self.turn_order[0]
            win_msg = self.large_font.render(f"WINNER: {winner.name} ({winner.points} pts)", True, COLOR_WHITE)
            self.screen.blit(win_msg, (SCREEN_WIDTH // 2 - win_msg.get_width() // 2, 200))
            
            # Display standings
            for i, p in enumerate(self.turn_order):
                txt = self.font.render(f"{i+1}. {p.name}: {p.points} points", True, COLOR_WHITE)
                self.screen.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, 300 + i * 40))
            
        restart_msg = self.font.render("Press 'R' to Restart or 'ESC' to Quit", True, COLOR_GOLD)
        self.screen.blit(restart_msg, (SCREEN_WIDTH // 2 - restart_msg.get_width() // 2, SCREEN_HEIGHT - 100))

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
        game.draw()

        pygame.display.flip()
        game.clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
