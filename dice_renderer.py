import pygame
from constants import COLOR_WHITE, COLOR_BLACK, DICE_SIZE, PIP_RADIUS

def draw_die(self, x, y, size, value, target_surf=None):
    # We bepalen op welk 'blaadje' we tekenen. 
    # Als er een target_surf is, tekenen we daarop vanaf (0,0)
    surf = target_surf if target_surf else self.screen
    
    # Als we op een target_surf tekenen, moeten de coördinaten lokaal zijn (0,0)
    # Anders gebruiken we de x en y van het scherm.
    # draw_x = 0 if target_surf else x
    # draw_y = 0 if target_surf else y

    # Gebruik de 'size' parameter in plaats van de hardcoded DICE_SIZE voor flexibiliteit
    die_rect = pygame.Rect(x, y, size, size)
    
    # Body tekenen op 'surf'
    pygame.draw.rect(surf, COLOR_WHITE, die_rect, border_radius=8)
    pygame.draw.rect(surf, COLOR_BLACK, die_rect, width=2, border_radius=8)

    # Pips berekenen op basis van de meegegeven 'size'
    q1 = size // 4
    q2 = size // 2
    q3 = 3 * size // 4
    
    pip_positions = {
        1: [(q2, q2)],
        2: [(q1, q1), (q3, q3)],
        3: [(q1, q1), (q2, q2), (q3, q3)],
        4: [(q1, q1), (q1, q3), (q3, q1), (q3, q3)],
        5: [(q1, q1), (q1, q3), (q3, q1), (q3, q3), (q2, q2)],
        6: [(q1, q1), (q1, q2), (q1, q3), (q3, q1), (q3, q2), (q3, q3)]
    }
    
    # PIP_RADIUS ook schalen met de grootte van de dobbelsteen voor een mooier beeld
    current_pip_radius = max(2, size // 10) 

    if value in pip_positions:
        for px, py in pip_positions[value]:
            # Teken de pips relatief aan draw_x en draw_y
            pygame.draw.circle(surf, COLOR_BLACK, (x + px, y + py), current_pip_radius)
