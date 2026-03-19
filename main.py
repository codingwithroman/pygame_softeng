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
        
        self.players = [
            Player("P1 (You)", is_ai=False),
            Player("P2 (AI)", is_ai=True),
            Player("P3 (AI)", is_ai=True),
            Player("P4 (AI)", is_ai=True)
        ]
        
        self.state = STATE_INITIATIVE
        self.round = 1
        self.pot = 0
        self.current_bet = 50
        self.starter = None
        
        # State specific variables
        self.initiative_rolls = {} 
        self.tied_players = []
        self.message = "Rolling for Initiative..."
        self.state_timer = 0
        
        # UI Buttons
        self.buttons = []
        
        # Start game
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
            self.state_timer = 90
        else:
            self.starter = highest_players[0]
            for p in self.players: p.is_starter = False
            self.starter.is_starter = True
            self.message = f"{self.starter.name} wins the roll! Starting Game..."
            self.state_timer = 90

    def start_betting(self):
        self.state = STATE_BETTING
        for p in self.players: p.dice = [] # Clear initiative rolls
        
        table_cap = self.get_table_cap()
        self.current_bet = 50
        
        if self.starter.is_ai:
            # AI Logic: Rich (>=300) bets Max, Poor bets 50
            if self.starter.points >= 300:
                self.current_bet = table_cap
            else:
                self.current_bet = 50
            self.message = f"{self.starter.name} set the bet to {self.current_bet}."
            self.state_timer = 120 # Wait to show the bet
        else:
            self.message = f"Your turn! Set the bet (Table Cap: {table_cap})"
            # Buttons will be created in draw/handled in event loop

    def collect_bets(self):
        active_players = self.get_active_players()
        for p in active_players:
            p.subtract_points(self.current_bet)
            self.pot += self.current_bet
        self.message = f"All players paid {self.current_bet}. Pot: {self.pot}. Rolling dice..."
        self.state_timer = 90

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
                    # If human, we wait for button press
                elif self.state == STATE_ROLL_ALL:
                    # Next step functionality placeholder
                    pass

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

        # Draw Players
        for i, p in enumerate(self.players):
            # ... (rest of the drawing logic remains similar)
            box_width = 250
            box_height = 180
            layout_pos = [
                (SCREEN_WIDTH // 2 - 125, SCREEN_HEIGHT - 200), # P1
                (50, SCREEN_HEIGHT // 2 - 90),                  # P2
                (SCREEN_WIDTH // 2 - 125, 230 if self.state == STATE_BETTING and not self.starter.is_ai else 120),# P3 shift down if betting
                (SCREEN_WIDTH - 300, SCREEN_HEIGHT // 2 - 90)   # P4
            ]
            # (Keeping the layout consistent but shifting P3 if buttons are in the way)
            x, y = layout_pos[i]
            if i == 2 and self.state == STATE_BETTING and not self.starter.is_ai:
                y = 250 # Push P3 down even more to avoid overlap with betting UI

            # Draw box
            color = COLOR_GREY if p.is_bust else (COLOR_RED if p.is_starter else COLOR_BROWN)
            pygame.draw.rect(self.screen, color, (x, y, box_width, box_height), border_radius=10)
            pygame.draw.rect(self.screen, COLOR_BLACK, (x, y, box_width, box_height), width=2, border_radius=10)

            # Draw player info
            name_text = self.font.render(f"{p.name} {'(STARTER)' if p.is_starter else ''}", True, COLOR_WHITE)
            points_text = self.font.render(f"Points: {p.points}", True, COLOR_GOLD)
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
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_click(event.pos)

        game.update()
        game.draw()

        pygame.display.flip()
        game.clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
