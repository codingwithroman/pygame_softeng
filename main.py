import pygame
import sys
from constants import *
from dice_renderer import draw_die

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("High Roller: Power-up - Prototype Step 1")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Fill background (Casino Table)
        screen.fill(COLOR_TABLE_GREEN)

        # Draw a row of all possible dice values for testing
        margin = 50
        y_pos = SCREEN_HEIGHT // 2 - DICE_SIZE // 2
        for i in range(1, 7):
            x_pos = margin + (i - 1) * (DICE_SIZE + 20)
            draw_die(screen, x_pos, y_pos, i)

        # Draw instructions
        font = pygame.font.SysFont("Arial", 24)
        text = font.render("Prototype Step 1: Dice Rendering Test", True, COLOR_WHITE)
        screen.blit(text, (margin, margin))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
