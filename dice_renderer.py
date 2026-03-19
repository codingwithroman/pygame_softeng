import pygame
from constants import COLOR_WHITE, COLOR_BLACK, DICE_SIZE, PIP_RADIUS

def draw_die(surface, x, y, value):
    """
    Draws a programmatic die on the given surface.
    :param surface: Pygame surface to draw on.
    :param x: X coordinate of top-left.
    :param y: Y coordinate of top-left.
    :param value: Die value (1-6).
    """
    # Draw die body
    die_rect = pygame.Rect(x, y, DICE_SIZE, DICE_SIZE)
    pygame.draw.rect(surface, COLOR_WHITE, die_rect, border_radius=8)
    pygame.draw.rect(surface, COLOR_BLACK, die_rect, width=2, border_radius=8)

    # Draw pips
    # Relative positions for pips (center of pips)
    # Positions are roughly:
    # (1/4, 1/4) (1/2, 1/4) (3/4, 1/4)
    # (1/4, 1/2) (1/2, 1/2) (3/4, 1/2)
    # (1/4, 3/4) (1/2, 3/4) (3/4, 3/4)
    
    q1 = DICE_SIZE // 4
    q2 = DICE_SIZE // 2
    q3 = 3 * DICE_SIZE // 4
    
    pip_positions = {
        1: [(q2, q2)],
        2: [(q1, q1), (q3, q3)],
        3: [(q1, q1), (q2, q2), (q3, q3)],
        4: [(q1, q1), (q1, q3), (q3, q1), (q3, q3)],
        5: [(q1, q1), (q1, q3), (q3, q1), (q3, q3), (q2, q2)],
        6: [(q1, q1), (q1, q2), (q1, q3), (q3, q1), (q3, q2), (q3, q3)]
    }
    
    if value in pip_positions:
        for px, py in pip_positions[value]:
            pygame.draw.circle(surface, COLOR_BLACK, (x + px, y + py), PIP_RADIUS)
