import pygame
import sys
from constants import *
from dice_renderer import draw_die
from player import Player

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("High Roller: Power-up - Prototype Step 2")
    clock = pygame.time.Clock()

    # Initialize Players
    players = [
        Player("P1 (You)", is_ai=False),
        Player("P2 (AI)", is_ai=True),
        Player("P3 (AI)", is_ai=True),
        Player("P4 (AI)", is_ai=True)
    ]

    font = pygame.font.SysFont("Arial", 20)
    title_font = pygame.font.SysFont("Arial", 32, bold=True)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Fill background
        screen.fill(COLOR_TABLE_GREEN)

        # Draw Title
        title_text = title_font.render("High Roller: Player Status Test", True, COLOR_GOLD)
        screen.blit(title_text, (50, 20))

        # Draw Player Boxes
        for i, p in enumerate(players):
            box_width = 250
            box_height = 150
            x = 50 + (i % 2) * (box_width + 50)
            y = 100 + (i // 2) * (box_height + 50)

            # Draw box
            color = COLOR_GREY if p.is_bust else COLOR_BROWN
            pygame.draw.rect(screen, color, (x, y, box_width, box_height), border_radius=10)
            pygame.draw.rect(screen, COLOR_BLACK, (x, y, box_width, box_height), width=2, border_radius=10)

            # Draw player info
            name_text = font.render(p.name, True, COLOR_WHITE)
            points_text = font.render(f"Points: {p.points}", True, COLOR_GOLD)
            screen.blit(name_text, (x + 10, y + 10))
            screen.blit(points_text, (x + 10, y + 40))

            # Draw inventory
            inv_y = y + 70
            for item, count in p.inventory.items():
                item_text = font.render(f"{item}: {count}", True, COLOR_WHITE)
                screen.blit(item_text, (x + 10, inv_y))
                inv_y += 25

        # Draw Dice row (from Step 1)
        for i in range(1, 7):
            draw_die(screen, 700 + (i-1)*70, 100, i)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
