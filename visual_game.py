import pygame
import sys
from game import Game   # ✅ FIXED import

pygame.init()

WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("High Roller")

font = pygame.font.SysFont("arial", 24)

game = Game()

clock = pygame.time.Clock()

# ===== DRAW FUNCTIONS =====

def draw_table():
    screen.fill((0, 120, 0))  # green casino table


def draw_players():
    positions = {
        "P1": (100, 500),
        "P2": (800, 500),
        "P3": (800, 100),
        "P4": (100, 100),
    }

    for p in game.players:
        x, y = positions[p]

        color = (255, 255, 255)
        if p not in game.active_players:
            color = (120, 120, 120)

        text = font.render(f"{p}: {game.points[p]}", True, color)
        screen.blit(text, (x, y))


def draw_dice():
    if not game.rolls:
        return

    x = WIDTH // 2 - 120
    y = HEIGHT // 2 - 60

    for p in game.active_players:
        dice = game.rolls[p]["dice"]
        total = game.rolls[p]["total"]

        text = font.render(f"{p}: {dice} = {total}", True, (255, 255, 255))
        screen.blit(text, (x, y))

        y += 35


def draw_state():
    text = font.render(
        f"STATE: {game.state.upper()} | ROUND: {game.round}",
        True,
        (255, 255, 0),
    )
    screen.blit(text, (320, 20))


def draw_pot():
    text = font.render(f"POT: {game.pot}", True, (255, 255, 0))
    screen.blit(text, (450, 320))

def draw_game_over():
    if game.state == "gameover":
        winner = max(game.players, key=lambda p: game.points[p])
        text = font.render(f"GAME OVER - WINNER: {winner}", True, (255, 0, 0))
        screen.blit(text, (300, 350))

def draw_current_player():
    if game.start_player:
        text = font.render(f"🎯 Start Player: {game.start_player}", True, (0, 255, 255))
        screen.blit(text, (400, 60))

def draw_turn_order():
    if game.state == "powerup" and game.start_player:
        start_index = game.players.index(game.start_player)
        order = game.players[start_index:] + game.players[:start_index]

        text = font.render(
            "Turn: " + " → ".join(order),
            True,
            (200, 200, 255),
        )
        screen.blit(text, (250, 650))

def draw_leader():
    if game.rolls:
        leader = max(game.active_players, key=lambda p: game.rolls[p]["total"])
        text = font.render(f"🔥 Leader: {leader}", True, (255, 100, 100))
        screen.blit(text, (420, 280))


# ===== MAIN LOOP =====

running = True

while running:
    clock.tick(0.7)  # slow so you can SEE what's happening

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                game = Game()

    # ===== GAME LOGIC STEP =====
    if game.state != "gameover":
        if game.state == "initiative":
            game.handle_initiative()
        elif game.state == "betting":
            game.handle_betting()
        elif game.state == "roll":
            game.handle_roll()
        elif game.state == "powerup":
            game.handle_powerup()
        elif game.state == "showdown":
            game.handle_showdown()
        elif game.state == "shop":
            game.handle_shop()

    # ===== DRAW =====
    draw_table()
    draw_players()
    draw_dice()
    draw_state()
    draw_pot()
    draw_game_over()
    draw_current_player()
    draw_turn_order()
    draw_leader()

    pygame.display.flip()