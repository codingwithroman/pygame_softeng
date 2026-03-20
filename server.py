# server.py
import socket
import threading
import json
import time
from core_game import Game

HOST = "0.0.0.0"
PORT = 5555
MAX_HUMAN_PLAYERS = 4
MIN_PLAYERS_TO_START = 2

clients = {}  # player_name -> socket
client_threads = {}  # player_name -> thread
host_player_name = None
lock = threading.Lock()
game = Game()
server_running = True


def send_json(conn, payload):
    message = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
    conn.sendall(message)


def recv_json_lines(conn_file):
    while True:
        line = conn_file.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        yield json.loads(line)


def send_error(conn, message):
    try:
        send_json(conn, {
            "type": "error",
            "message": message
        })
    except Exception:
        pass


def send_info(conn, message):
    try:
        send_json(conn, {
            "type": "info",
            "message": message
        })
    except Exception:
        pass


def safe_broadcast(payload):
    dead_players = []
    with lock:
        for player_name, conn in list(clients.items()):
            try:
                send_json(conn, payload)
            except Exception:
                dead_players.append(player_name)

        for player_name in dead_players:
            try:
                clients[player_name].close()
            except Exception:
                pass
            clients.pop(player_name, None)
            client_threads.pop(player_name, None)
            try:
                game.mark_player_disconnected(player_name)
            except Exception:
                pass


def broadcast_state():
    with lock:
        state = game.serialize_state()
        payload = {
            "type": "state",
            "state": state,
            "host": host_player_name,
            "can_start": (not game.is_started()) and (len(clients) >= MIN_PLAYERS_TO_START)
        }
    safe_broadcast(payload)


def normalize_action(raw_action):
    if not isinstance(raw_action, dict):
        return None

    action_type = raw_action.get("action")
    if not action_type:
        return None

    return {
        "player": raw_action.get("player"),
        "action": action_type,
        "value": raw_action.get("value"),
        "target": raw_action.get("target"),
        "item": raw_action.get("item")
    }


def process_action(action):
    player_name = action["player"]

    with lock:
        changed = False
        message = None
        try:
            changed, message = game.apply_player_action(player_name, action)
        except Exception as exc:
            return False, f"Server/game error: {exc}"

        if changed:
            try:
                progressed = True
                safety = 0
                while progressed and safety < 50:
                    progressed = game.tick()
                    safety += 1
            except Exception as exc:
                return False, f"Tick error: {exc}"

    return changed, message


def start_game_by_host(requesting_player):
    global host_player_name

    with lock:
        if game.is_started():
            return False, "Game is al gestart."

        if requesting_player != host_player_name:
            return False, "Alleen de host mag de game starten."

        human_count = len(clients)
        if human_count < MIN_PLAYERS_TO_START:
            return False, f"Minstens {MIN_PLAYERS_TO_START} spelers nodig om te starten."

        try:
            game.fill_with_ai_until_full()
            game.start_game()

            progressed = True
            safety = 0
            while progressed and safety < 50:
                progressed = game.tick()
                safety += 1

            return True, "Game gestart door host."
        except Exception as exc:
            return False, f"Game kon niet starten: {exc}"


def client_thread(conn, addr):
    global host_player_name
    player_name = None
    conn_file = conn.makefile("r", encoding="utf-8")

    try:
        first_line = conn_file.readline()
        if not first_line:
            conn.close()
            return

        hello = json.loads(first_line.strip())
        if hello.get("type") != "join":
            send_error(conn, "Eerste bericht moet type='join' zijn.")
            conn.close()
            return

        requested_name = str(hello.get("player_name", "")).strip()
        if not requested_name:
            send_error(conn, "Spelernaam ontbreekt.")
            conn.close()
            return

        with lock:
            if requested_name in clients:
                send_error(conn, "Deze spelernaam is al in gebruik.")
                conn.close()
                return

            if len(clients) >= MAX_HUMAN_PLAYERS:
                send_error(conn, "Server zit vol.")
                conn.close()
                return

            if game.is_started():
                send_error(conn, "Game is al gestart. Join eerst vóór de host op start drukt.")
                conn.close()
                return

            try:
                game.add_human_player(requested_name)
            except Exception as exc:
                send_error(conn, f"Kan speler niet toevoegen: {exc}")
                conn.close()
                return

            clients[requested_name] = conn
            client_threads[requested_name] = threading.current_thread()
            player_name = requested_name

            if host_player_name is None:
                host_player_name = player_name

            is_host = (player_name == host_player_name)

        send_json(conn, {
            "type": "welcome",
            "player_name": player_name,
            "is_host": is_host,
            "host": host_player_name,
            "message": f"Welkom, {player_name}"
        })

        send_info(conn, f"Joined lobby. Host is {host_player_name}.")
        broadcast_state()
        safe_broadcast({
            "type": "info",
            "message": f"{player_name} joined from {addr[0]}:{addr[1]}"
        })

        for incoming in recv_json_lines(conn_file):
            msg_type = incoming.get("type")

            if msg_type == "ping":
                send_json(conn, {"type": "pong"})
                continue

            if msg_type == "lobby":
                lobby_action = incoming.get("action")

                if lobby_action == "start_game":
                    changed, message = start_game_by_host(player_name)
                    if message:
                        send_info(conn, message)
                        if changed:
                            safe_broadcast({
                                "type": "info",
                                "message": f"{player_name} started the game."
                            })
                            broadcast_state()
                        else:
                            broadcast_state()
                    continue

                send_error(conn, "Ongeldige lobby action.")
                continue

            if msg_type != "action":
                send_error(conn, "Ongeldig berichttype.")
                continue

            action = normalize_action(incoming)
            if not action:
                send_error(conn, "Ongeldige action payload.")
                continue

            if action["player"] != player_name:
                send_error(conn, "Je mag alleen acties sturen voor je eigen speler.")
                continue

            changed, message = process_action(action)

            if message:
                send_info(conn, message)

            broadcast_state()

    except Exception as exc:
        print(f"[SERVER] Fout met client {addr}: {exc}")

    finally:
        new_host = None

        with lock:
            if player_name:
                clients.pop(player_name, None)
                client_threads.pop(player_name, None)

                try:
                    game.mark_player_disconnected(player_name)
                except Exception:
                    pass

                if player_name == host_player_name:
                    remaining = list(clients.keys())
                    host_player_name = remaining[0] if remaining else None
                    new_host = host_player_name

        try:
            conn_file.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

        if player_name:
            print(f"[SERVER] {player_name} disconnected")
            safe_broadcast({
                "type": "info",
                "message": f"{player_name} disconnected"
            })

            if new_host:
                safe_broadcast({
                    "type": "info",
                    "message": f"{new_host} is nu de host."
                })

            broadcast_state()


def server_tick_loop():
    global server_running

    while server_running:
        changed = False
        with lock:
            try:
                changed = game.tick()
            except Exception as exc:
                print(f"[SERVER] Tick loop error: {exc}")

        if changed:
            broadcast_state()

        time.sleep(1 / 20.0)


def start_server():
    global server_running

    tick_thread = threading.Thread(target=server_tick_loop, daemon=True)
    tick_thread.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen()

    print(f"[SERVER] Luistert op {HOST}:{PORT}")

    try:
        while True:
            conn, addr = sock.accept()
            print(f"[SERVER] Nieuwe verbinding van {addr}")
            threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[SERVER] Afsluiten...")
    finally:
        server_running = False
        sock.close()
        with lock:
            for conn in clients.values():
                try:
                    conn.close()
                except Exception:
                    pass
            clients.clear()
            client_threads.clear()


if __name__ == "__main__":
    start_server()