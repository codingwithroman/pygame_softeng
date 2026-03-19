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
        
        self.players = [
            Player("P1 (You)", is_ai=False),
            Player("P2 (AI)", is_ai=True),
            Player("P3 (AI)", is_ai=True),
            Player("P4 (AI)", is_ai=True)
        ]
        
        self.state = STATE_INITIATIVE
        self.round = 1
        self.pot = 0
        self.starter = None
        
        # State specific variables
        self.initiative_rolls = {} # player: roll_value
        self.tied_players = []
        self.message = "Rolling for Initiative..."
        self.state_timer = 0
        
        # Initial call to start the game
        self.start_initiative()

    def start_initiative(self):
        self.initiative_rolls = {}
        self.tied_players = self.get_active_players()
        self.message = "Rolling for Initiative..."
        self.resolve_initiative()

    def get_active_players(self):
        return [p for p in self.players if not p.is_bust]

    def resolve_initiative(self):
        # Roll for all tied players
        for p in self.tied_players:
            roll = random.randint(1, 6)
            self.initiative_rolls[p] = roll
            p.dice = [roll] # Storing for display
            
        # Find max
        max_roll = max(self.initiative_rolls.values())
        highest_players = [p for p, roll in self.initiative_rolls.items() if roll == max_roll]
        
        if len(highest_players) > 1:
            self.tied_players = highest_players
            self.message = f"Tie! {', '.join([p.name for p in highest_players])} roll again!"
            # We will wait for a bit before rolling again (handled in update)
            self.state_timer = 120 # 2 seconds at 60 FPS
        else:
            self.starter = highest_players[0]
            self.starter.is_starter = True
            self.message = f"{self.starter.name} wins the roll! Starting Game..."
            self.state_timer = 120
            # Transition handled in update

    def update(self):
        if self.state == STATE_INITIATIVE:
            if self.state_timer > 0:
                self.state_timer -= 1
                if self.state_timer == 0:
                    if self.starter:
                        self.state = STATE_BETTING
                        self.message = f"{self.starter.name} sets the bet."
                    else:
                        self.resolve_initiative()

    def draw(self):
        self.screen.fill(COLOR_TABLE_GREEN)
        
        # Draw Title/Round info
        status_text = self.large_font.render(f"Round {self.round} - {self.state}", True, COLOR_GOLD)
        self.screen.blit(status_text, (SCREEN_WIDTH // 2 - status_text.get_width() // 2, 20))
        
        # Draw Message
        msg_text = self.font.render(self.message, True, COLOR_WHITE)
        self.screen.blit(msg_text, (SCREEN_WIDTH // 2 - msg_text.get_width() // 2, 80))

        # Draw Players
        for i, p in enumerate(self.players):
            box_width = 250
            box_height = 180
            # Layout: P1 Bottom Center, P2 Left, P3 Top Center, P4 Right
            layout_pos = [
                (SCREEN_WIDTH // 2 - 125, SCREEN_HEIGHT - 200), # P1
                (50, SCREEN_HEIGHT // 2 - 90),                  # P2
                (SCREEN_WIDTH // 2 - 125, 120),                 # P3
                (SCREEN_WIDTH - 300, SCREEN_HEIGHT // 2 - 90)   # P4
            ]
            x, y = layout_pos[i]

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
                # Center dice in the box relative to other dice
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

        game.update()
        game.draw()

        pygame.display.flip()
        game.clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
