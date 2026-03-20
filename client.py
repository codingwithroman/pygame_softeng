import socket
import json
import threading
import time
import pygame

from core_game import Game
from server import start_server

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

pygame.init()

WIDTH, HEIGHT = 1200, 800
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("High Roller")

FONT = pygame.font.SysFont("arial", 22)
SMALL_FONT = pygame.font.SysFont("arial", 18)
BIG_FONT = pygame.font.SysFont("arial", 34, bold=True)

COOLDOWN_MS = 180


def now_ms():
    return int(time.time() * 1000)


class Button:
    def __init__(self, x, y, w, h, text):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text

    def draw(self, surface, active=False):
        bg = (60, 60, 60) if not active else (90, 90, 120)
        pygame.draw.rect(surface, bg, self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        txt = FONT.render(self.text, True, (255, 255, 255))
        tx = self.rect.x + (self.rect.w - txt.get_width()) // 2
        ty = self.rect.y + (self.rect.h - txt.get_height()) // 2
        surface.blit(txt, (tx, ty))

    def clicked(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)


class NetworkClient:
    def __init__(self):
        self.sock = None
        self.running = False
        self.connected = False
        self.player_name = None

        self.state_lock = threading.Lock()
        self.game_state = None
        self.last_error = ""
        self.last_info = ""
        self.info_message = "Niet verbonden"

        self.host_name = None
        self.is_host = False
        self.can_start = False

    def connect(self, host, port, player_name):
        self.player_name = player_name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.send_json({
            "type": "join",
            "player_name": player_name
        })

        self.running = True
        self.connected = True
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def disconnect(self):
        self.running = False
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None

    def send_json(self, payload):
        if not self.sock:
            return
        message = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
        self.sock.sendall(message)

    def send_action(self, action, value=None, target=None, item=None):
        payload = {
            "type": "action",
            "player": self.player_name,
            "action": action
        }
        if value is not None:
            payload["value"] = value
        if target is not None:
            payload["target"] = target
        if item is not None:
            payload["item"] = item

        try:
            self.send_json(payload)
        except Exception as exc:
            self.last_error = f"Verzenden mislukt: {exc}"

    def send_lobby_start(self):
        try:
            self.send_json({
                "type": "lobby",
                "action": "start_game"
            })
        except Exception as exc:
            self.last_error = f"Lobby start mislukt: {exc}"

    def receive_loop(self):
        conn_file = self.sock.makefile("r", encoding="utf-8")
        try:
            while self.running:
                line = conn_file.readline()
                if not line:
                    self.last_error = "Verbinding met server verbroken."
                    self.connected = False
                    break

                msg = json.loads(line.strip())
                msg_type = msg.get("type")

                if msg_type == "state":
                    with self.state_lock:
                        self.game_state = msg.get("state")
                        self.host_name = msg.get("host")
                        self.can_start = msg.get("can_start", False)

                elif msg_type == "welcome":
                    self.last_info = msg.get("message", "")
                    self.info_message = self.last_info
                    self.host_name = msg.get("host")
                    self.is_host = msg.get("is_host", False)

                elif msg_type == "info":
                    self.last_info = msg.get("message", "")

                elif msg_type == "error":
                    self.last_error = msg.get("message", "")

                elif msg_type == "pong":
                    pass

        except Exception as exc:
            self.last_error = f"Ontvangstfout: {exc}"
            self.connected = False
        finally:
            try:
                conn_file.close()
            except Exception:
                pass

    def get_state(self):
        with self.state_lock:
            if self.game_state is None:
                return None
            return json.loads(json.dumps(self.game_state))


class LocalSingleplayerSession:
    def __init__(self, player_name):
        self.player_name = player_name
        self.game = Game()
        self.last_error = ""
        self.last_info = "Singleplayer gestart"
        self.pending_bet_preview = None
        self.game.setup_singleplayer(player_name)

    def get_state(self):
        return self.game.serialize_state()

    def send_action(self, action, value=None, target=None, item=None):
        try:
            changed, message = self.game.apply_player_action(
                self.player_name,
                {
                    "action": action,
                    "value": value,
                    "target": target,
                    "item": item
                }
            )
            if message:
                self.last_info = message
            if changed:
                progressed = True
                safety = 0
                while progressed and safety < 50:
                    progressed = self.game.tick()
                    safety += 1
        except Exception as exc:
            self.last_error = f"Local game error: {exc}"


class App:
    def __init__(self):
        self.running = True
        self.state = "menu"
        self.player_name = ""
        self.join_code = ""
        self.room_code_display = ""
        self.status_message = "Welkom"
        self.hosting_server = False
        self.server_thread = None
        self.session = None
        self.input_cooldowns = {}
        self.name_input_active = True
        self.join_input_active = False

        self.buttons = {
            "singleplayer": Button(430, 220, 340, 60, "Singleplayer"),
            "host": Button(430, 310, 340, 60, "Room aanmaken"),
            "join": Button(430, 400, 340, 60, "Room joinen"),
            "quit": Button(430, 490, 340, 60, "Quit"),
            "join_confirm": Button(430, 470, 340, 60, "Verbind"),
            "join_back": Button(430, 550, 340, 60, "Terug"),
            "back_menu": Button(20, 20, 140, 45, "Menu"),
            "start_game": Button(430, 650, 340, 60, "Start Game"),
        }

    def can_press(self, key_name):
        current = now_ms()
        next_ok = self.input_cooldowns.get(key_name, 0)
        if current >= next_ok:
            self.input_cooldowns[key_name] = current + COOLDOWN_MS
            return True
        return False

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def start_singleplayer(self):
        if not self.player_name.strip():
            self.status_message = "Voer eerst een spelernaam in."
            return

        self.session = LocalSingleplayerSession(self.player_name.strip())
        self.state = "game"
        self.status_message = "Singleplayer gestart."

    def start_hosted_room(self):
        if not self.player_name.strip():
            self.status_message = "Voer eerst een spelernaam in."
            return

        if not self.hosting_server:
            self.server_thread = threading.Thread(target=start_server, daemon=True)
            self.server_thread.start()
            self.hosting_server = True
            time.sleep(0.5)

        net = NetworkClient()
        try:
            net.connect("127.0.0.1", 5555, self.player_name.strip())
        except Exception as exc:
            self.status_message = f"Hosten/connecten mislukt: {exc}"
            return

        self.session = net
        self.room_code_display = f"{self.get_local_ip()}:5555"
        self.state = "lobby"
        self.status_message = f"Room aangemaakt. Code: {self.room_code_display}"

    def join_room(self):
        if not self.player_name.strip():
            self.status_message = "Voer eerst een spelernaam in."
            return

        code = self.join_code.strip()
        if ":" not in code:
            self.status_message = "Gebruik ip:poort, bv 192.168.1.10:5555"
            return

        host, port_text = code.split(":", 1)
        try:
            port = int(port_text)
        except ValueError:
            self.status_message = "Poort is ongeldig."
            return

        net = NetworkClient()
        try:
            net.connect(host.strip(), port, self.player_name.strip())
        except Exception as exc:
            self.status_message = f"Join mislukt: {exc}"
            return

        self.session = net
        self.state = "lobby"
        self.status_message = f"Verbonden met {host}:{port}"

    def go_to_join_menu(self):
        self.state = "join_menu"
        self.status_message = "Voer room code in als ip:poort"

    def back_to_menu(self):
        self.state = "menu"
        self.join_code = ""
        self.status_message = "Terug naar menu"

    def get_state(self):
        if not self.session:
            return None
        return self.session.get_state()

    def get_me(self, state):
        if not state:
            return None
        for p in state.get("players", []):
            if p.get("name") == self.player_name:
                return p
        return None

    def send_action(self, action, value=None, target=None, item=None):
        if not self.session:
            return
        self.session.send_action(action, value=value, target=target, item=item)

    def draw_text(self, text, x, y, color=(255, 255, 255), font=FONT):
        surface = font.render(str(text), True, color)
        WIN.blit(surface, (x, y))

    def draw_panel(self, rect, color=(40, 40, 40), border=(255, 255, 255)):
        pygame.draw.rect(WIN, color, rect, border_radius=12)
        pygame.draw.rect(WIN, border, rect, 2, border_radius=12)

    def draw_dice(self, dice, x, y):
        size = 46
        gap = 10
        for i, value in enumerate(dice):
            r = pygame.Rect(x + i * (size + gap), y, size, size)
            pygame.draw.rect(WIN, (240, 240, 240), r, border_radius=8)
            pygame.draw.rect(WIN, (0, 0, 0), r, 2, border_radius=8)
            self.draw_text(value, r.x + 16, r.y + 10, (0, 0, 0), FONT)

    def draw_menu(self):
        WIN.fill((18, 50, 24))
        self.draw_text("HIGH ROLLER", 460, 80, (255, 215, 0), BIG_FONT)
        self.draw_text("Spelernaam:", 350, 155)
        self.draw_name_input()
        mouse_pos = pygame.mouse.get_pos()
        self.buttons["singleplayer"].draw(WIN, self.buttons["singleplayer"].clicked(mouse_pos))
        self.buttons["host"].draw(WIN, self.buttons["host"].clicked(mouse_pos))
        self.buttons["join"].draw(WIN, self.buttons["join"].clicked(mouse_pos))
        self.buttons["quit"].draw(WIN, self.buttons["quit"].clicked(mouse_pos))
        self.draw_text(self.status_message, 350, 580, (180, 220, 255), SMALL_FONT)

    def draw_join_menu(self):
        WIN.fill((18, 50, 24))
        self.draw_text("ROOM JOINEN", 470, 110, (255, 215, 0), BIG_FONT)
        self.draw_text("Spelernaam:", 350, 200)
        self.draw_name_input(y=235)
        self.draw_text("Room code (ip:poort):", 350, 320)
        self.draw_join_input()
        mouse_pos = pygame.mouse.get_pos()
        self.buttons["join_confirm"].draw(WIN, self.buttons["join_confirm"].clicked(mouse_pos))
        self.buttons["join_back"].draw(WIN, self.buttons["join_back"].clicked(mouse_pos))
        self.draw_text(self.status_message, 350, 640, (180, 220, 255), SMALL_FONT)

    def draw_lobby(self):
        WIN.fill((18, 50, 24))
        self.buttons["back_menu"].draw(WIN)

        self.draw_text("LOBBY", 530, 50, (255, 215, 0), BIG_FONT)

        if self.room_code_display:
            self.draw_text(f"Room code: {self.room_code_display}", 420, 100, (180, 220, 255), FONT)

        if isinstance(self.session, NetworkClient):
            host_name = self.session.host_name or "onbekend"
            self.draw_text(f"Host: {host_name}", 420, 140, (255, 255, 255), FONT)
            self.draw_text(
                "Jij bent host" if self.session.is_host else "Wachten op host...",
                420,
                175,
                (255, 215, 0) if self.session.is_host else (180, 220, 255),
                FONT
            )

        state = self.get_state()
        if not state:
            self.draw_text("Wachten op lobby state...", 420, 240)
            if hasattr(self.session, "last_info") and self.session.last_info:
                self.draw_text(self.session.last_info, 420, 280, (180, 220, 255))
            if hasattr(self.session, "last_error") and self.session.last_error:
                self.draw_text(self.session.last_error, 420, 320, (255, 120, 120))
            return

        players = state.get("players", [])
        self.draw_text(f"Spelers in lobby: {len(players)}/4", 420, 230)

        y = 280
        for p in players:
            label = p.get("name", "?")
            if isinstance(self.session, NetworkClient) and label == self.session.host_name:
                label += " (HOST)"
            if p.get("is_ai"):
                label += " [AI]"
            self.draw_text(label, 450, y, (255, 255, 255))
            y += 40

        self.draw_text("Minstens 2 spelers nodig om te starten.", 420, 500, (180, 220, 255), SMALL_FONT)
        self.draw_text("Bij starten wordt automatisch opgevuld met AI tot 4 spelers.", 420, 530, (180, 220, 255), SMALL_FONT)

        if isinstance(self.session, NetworkClient) and self.session.is_host:
            mouse_pos = pygame.mouse.get_pos()
            active = self.buttons["start_game"].clicked(mouse_pos) and self.session.can_start
            self.buttons["start_game"].draw(WIN, active)

            if not self.session.can_start:
                self.draw_text("Nog niet genoeg spelers om te starten.", 430, 720, (255, 120, 120), SMALL_FONT)

        if hasattr(self.session, "last_info") and self.session.last_info:
            self.draw_text(self.session.last_info, 420, 580, (180, 220, 255), SMALL_FONT)

        if hasattr(self.session, "last_error") and self.session.last_error:
            self.draw_text(self.session.last_error, 420, 610, (255, 120, 120), SMALL_FONT)

        if state.get("state") != "LOBBY":
            self.state = "game"

    def draw_name_input(self, y=185):
        rect = pygame.Rect(350, y, 500, 42)
        color = (255, 255, 255) if self.name_input_active else (180, 180, 180)
        pygame.draw.rect(WIN, (30, 30, 30), rect, border_radius=8)
        pygame.draw.rect(WIN, color, rect, 2, border_radius=8)
        self.draw_text(self.player_name or "typ hier je naam...", rect.x + 10, rect.y + 9, (255, 255, 255), FONT)

    def draw_join_input(self):
        rect = pygame.Rect(350, 355, 500, 42)
        color = (255, 255, 255) if self.join_input_active else (180, 180, 180)
        pygame.draw.rect(WIN, (30, 30, 30), rect, border_radius=8)
        pygame.draw.rect(WIN, color, rect, 2, border_radius=8)
        self.draw_text(self.join_code or "bv 192.168.1.55:5555", rect.x + 10, rect.y + 9, (255, 255, 255), FONT)

    def draw_game(self):
        WIN.fill((18, 50, 24))
        self.buttons["back_menu"].draw(WIN)

        state = self.get_state()

        self.draw_text("HIGH ROLLER", 460, 20, (255, 215, 0), BIG_FONT)

        if self.room_code_display:
            self.draw_text(f"Room code: {self.room_code_display}", 850, 28, (180, 220, 255), SMALL_FONT)

        if not state:
            self.draw_text("Wachten op game state...", 430, 120)
            if hasattr(self.session, "last_info") and self.session.last_info:
                self.draw_text(self.session.last_info, 430, 160, (180, 220, 255))
            if hasattr(self.session, "last_error") and self.session.last_error:
                self.draw_text(self.session.last_error, 430, 200, (255, 120, 120))
            return

        round_no = state.get("round", "?")
        pot = state.get("pot", 0)
        phase = state.get("state", "UNKNOWN")
        message = state.get("message", "")
        current_bet = state.get("current_bet", 0)
        starter = state.get("starter")
        current_turn = state.get("current_turn")

        self.draw_text(f"Ronde: {round_no}", 40, 30)
        self.draw_text(f"Fase: {phase}", 40, 60)
        self.draw_text(f"Pot: ${pot}", 40, 90, (255, 215, 0))
        self.draw_text(f"Huidige inzet: ${current_bet}", 40, 120)
        self.draw_text(f"Starter: {starter}", 40, 150)
        self.draw_text(f"Beurt: {current_turn}", 40, 180, (0, 255, 180))
        self.draw_text(f"Bericht: {message}", 40, 220, (220, 220, 255))

        if hasattr(self.session, "last_info") and self.session.last_info:
            self.draw_text(f"Info: {self.session.last_info}", 40, 260, (180, 220, 255), SMALL_FONT)

        if hasattr(self.session, "last_error") and self.session.last_error:
            self.draw_text(f"Error: {self.session.last_error}", 40, 285, (255, 120, 120), SMALL_FONT)

        players = state.get("players", [])
        positions = [
            (60, 350),
            (340, 350),
            (620, 350),
            (900, 350),
        ]

        for idx, p in enumerate(players[:4]):
            x, y = positions[idx]
            rect = pygame.Rect(x, y, 240, 200)

            border = (255, 255, 255)
            if p.get("name") == self.player_name:
                border = (255, 215, 0)
            if p.get("name") == current_turn:
                border = (0, 255, 255)
            if p.get("is_bust"):
                border = (120, 120, 120)

            self.draw_panel(rect, (36, 36, 36), border)
            self.draw_text(p.get("name", "?"), x + 12, y + 12)
            self.draw_text(f"Points: ${p.get('points', 0)}", x + 12, y + 42, (255, 215, 0))
            self.draw_text(f"AI: {p.get('is_ai', False)}", x + 12, y + 72)
            self.draw_text(f"Starter: {p.get('is_starter', False)}", x + 12, y + 98)
            self.draw_text(f"Used powerup: {p.get('has_used_powerup', False)}", x + 12, y + 124, font=SMALL_FONT)

            inv = p.get("inventory", {})
            inv_text = f"R:{inv.get('Reroll', 0)} S:{inv.get('Swap', 0)} E:{inv.get('Extra Die', 0)}"
            self.draw_text(inv_text, x + 12, y + 150, (220, 220, 255), SMALL_FONT)

            self.draw_dice(p.get("dice", []), x + 12, y + 170)

        me = self.get_me(state)
        if me:
            help_y = 600
            self.draw_text("Controls", 40, help_y, (255, 215, 0))
            self.draw_text("R = Reroll", 40, help_y + 35, font=SMALL_FONT)
            self.draw_text("W = Swap", 40, help_y + 60, font=SMALL_FONT)
            self.draw_text("E = Extra Die", 40, help_y + 85, font=SMALL_FONT)
            self.draw_text("SPACE = Pass", 40, help_y + 110, font=SMALL_FONT)
            self.draw_text("+ / - = Bet verhogen/verlagen", 280, help_y + 35, font=SMALL_FONT)
            self.draw_text("ENTER = Bet bevestigen", 280, help_y + 60, font=SMALL_FONT)
            self.draw_text("1 = Koop Reroll", 560, help_y + 35, font=SMALL_FONT)
            self.draw_text("2 = Koop Swap", 560, help_y + 60, font=SMALL_FONT)
            self.draw_text("3 = Koop Extra Die", 560, help_y + 85, font=SMALL_FONT)
            self.draw_text("0 = Shop verlaten", 560, help_y + 110, font=SMALL_FONT)

    def handle_game_input(self):
        keys = pygame.key.get_pressed()

        if keys[pygame.K_r] and self.can_press("reroll"):
            self.send_action("use_powerup", item="Reroll")
        if keys[pygame.K_w] and self.can_press("swap"):
            self.send_action("use_powerup", item="Swap")
        if keys[pygame.K_e] and self.can_press("extra"):
            self.send_action("use_powerup", item="Extra Die")
        if keys[pygame.K_SPACE] and self.can_press("pass"):
            self.send_action("pass_turn")
        if keys[pygame.K_EQUALS] and self.can_press("bet_plus"):
            self.send_action("change_bet", value=50)
        if keys[pygame.K_MINUS] and self.can_press("bet_minus"):
            self.send_action("change_bet", value=-50)
        if keys[pygame.K_RETURN] and self.can_press("bet_confirm"):
            self.send_action("confirm_bet")
        if keys[pygame.K_1] and self.can_press("shop_reroll"):
            self.send_action("buy_item", item="Reroll")
        if keys[pygame.K_2] and self.can_press("shop_swap"):
            self.send_action("buy_item", item="Swap")
        if keys[pygame.K_3] and self.can_press("shop_extra"):
            self.send_action("buy_item", item="Extra Die")
        if keys[pygame.K_0] and self.can_press("shop_exit"):
            self.send_action("shop_exit")

    def handle_mouse_click(self, pos):
        if self.state == "menu":
            if self.buttons["singleplayer"].clicked(pos):
                self.start_singleplayer()
            elif self.buttons["host"].clicked(pos):
                self.start_hosted_room()
            elif self.buttons["join"].clicked(pos):
                self.go_to_join_menu()
            elif self.buttons["quit"].clicked(pos):
                self.running = False

            name_rect = pygame.Rect(350, 185, 500, 42)
            self.name_input_active = name_rect.collidepoint(pos)

        elif self.state == "join_menu":
            if self.buttons["join_confirm"].clicked(pos):
                self.join_room()
            elif self.buttons["join_back"].clicked(pos):
                self.back_to_menu()

            name_rect = pygame.Rect(350, 235, 500, 42)
            code_rect = pygame.Rect(350, 355, 500, 42)
            self.name_input_active = name_rect.collidepoint(pos)
            self.join_input_active = code_rect.collidepoint(pos)

        elif self.state == "lobby":
            if self.buttons["back_menu"].clicked(pos):
                if isinstance(self.session, NetworkClient):
                    self.session.disconnect()
                self.session = None
                self.room_code_display = ""
                self.back_to_menu()
                return

            if isinstance(self.session, NetworkClient) and self.session.is_host:
                if self.session.can_start and self.buttons["start_game"].clicked(pos):
                    self.session.send_lobby_start()

        elif self.state == "game":
            if self.buttons["back_menu"].clicked(pos):
                if isinstance(self.session, NetworkClient):
                    self.session.disconnect()
                self.session = None
                self.room_code_display = ""
                self.back_to_menu()

    def handle_text_input(self, event):
        if event.key == pygame.K_BACKSPACE:
            if self.state == "menu" and self.name_input_active:
                self.player_name = self.player_name[:-1]
            elif self.state == "join_menu":
                if self.join_input_active:
                    self.join_code = self.join_code[:-1]
                elif self.name_input_active:
                    self.player_name = self.player_name[:-1]
            return

        if event.key == pygame.K_TAB:
            if self.state == "join_menu":
                if self.name_input_active:
                    self.name_input_active = False
                    self.join_input_active = True
                else:
                    self.name_input_active = True
                    self.join_input_active = False
            return

        ch = event.unicode
        if not ch or ord(ch) < 32:
            return

        if self.state == "menu" and self.name_input_active:
            if len(self.player_name) < 20:
                self.player_name += ch
        elif self.state == "join_menu":
            if self.name_input_active and len(self.player_name) < 20:
                self.player_name += ch
            elif self.join_input_active and len(self.join_code) < 40:
                self.join_code += ch

    def draw(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "join_menu":
            self.draw_join_menu()
        elif self.state == "lobby":
            self.draw_lobby()
        elif self.state == "game":
            self.draw_game()

        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()

        while self.running:
            clock.tick(30)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_mouse_click(event.pos)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state in ("game", "lobby"):
                            if isinstance(self.session, NetworkClient):
                                self.session.disconnect()
                            self.session = None
                            self.room_code_display = ""
                            self.back_to_menu()
                        elif self.state == "join_menu":
                            self.back_to_menu()
                        else:
                            self.running = False
                    else:
                        if self.state in ("menu", "join_menu"):
                            self.handle_text_input(event)

            if self.state == "game":
                self.handle_game_input()

            self.draw()

            if self.state == "lobby":
                state = self.get_state()
                if state and state.get("state") != "LOBBY":
                    self.state = "game"

        if isinstance(self.session, NetworkClient):
            self.session.disconnect()

        pygame.quit()


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()