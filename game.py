import random

STATE_INITIATIVE = "initiative"
STATE_BETTING = "betting"
STATE_ROLL = "roll"
STATE_POWERUP = "powerup"
STATE_SHOWDOWN = "showdown"
STATE_SHOP = "shop"
STATE_GAMEOVER = "gameover"

SHOP = {
    "reroll": 100,
    "swap": 150,
    "extra_die": 200
}


class Game:
    def __init__(self):
        self.round = 1
        self.state = STATE_INITIATIVE
        self.players = ["P1", "P2", "P3", "P4"]
        self.start_player = None
        self.rolls = {}
        self.points = {p: 500 for p in self.players}
        self.pot = 0

        self.inventory = {
            p: {"reroll": 1, "swap": 1, "extra_die": 1}
            for p in self.players
        }

        self.active_players = self.players.copy()

    def run(self):
        print("Starting High Roller...")

        while self.state != STATE_GAMEOVER:
            print(f"\n--- ROUND {self.round} | STATE: {self.state} ---")

            if self.state == STATE_INITIATIVE:
                self.handle_initiative()
            elif self.state == STATE_BETTING:
                self.handle_betting()
            elif self.state == STATE_ROLL:
                self.handle_roll()
            elif self.state == STATE_POWERUP:
                self.handle_powerup()
            elif self.state == STATE_SHOWDOWN:
                self.handle_showdown()
            elif self.state == STATE_SHOP:
                self.handle_shop()

        print("\n=== GAME OVER ===")

        winner = max(self.players, key=lambda p: self.points[p])

        for p in self.players:
            status = " (BUST)" if p not in self.active_players else ""
            print(f"{p}: {self.points[p]}{status}")

        print(f"\n👑 OVERALL WINNER: {winner}")

    # ===== STATES =====

    def handle_initiative(self):
        print("\n--- INITIATIVE PHASE ---")

        while True:
            rolls = {}

            for player in self.active_players:
                roll = random.randint(1, 6)
                rolls[player] = roll
                print(f"{player} rolls: {roll}")

            highest = max(rolls.values())
            winners = [p for p in rolls if rolls[p] == highest]

            if len(winners) == 1:
                self.start_player = winners[0]
                print(f"\n🎯 {self.start_player} starts!")
                break
            else:
                print(f"\nTie between {', '.join(winners)} → re-roll\n")

        self.state = STATE_BETTING

    def handle_betting(self):
        print("\n--- BETTING PHASE ---")

        poorest = min(self.points[p] for p in self.active_players)
        table_cap = poorest

        bet = random.choice([50, 100, 150])
        bet = min(bet, table_cap)

        print(f"🎯 {self.start_player} sets bet to {bet}")
        print(f"Table cap: {table_cap}\n")

        self.pot = 0

        for p in self.active_players.copy():
            if self.points[p] < bet:
                print(f"{p} cannot afford the bet and is eliminated!")
                self.points[p] = 0

        self.check_elimination()

        for p in self.active_players:
            self.points[p] -= bet
            self.pot += bet
            print(f"{p} pays {bet} → {self.points[p]} left")

        print(f"\n💰 Pot: {self.pot}")

        self.state = STATE_ROLL

    def handle_roll(self):
        print("\n--- ROLL PHASE ---")

        self.rolls = {}

        for player in self.active_players:
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)

            self.rolls[player] = {
                "dice": [d1, d2],
                "total": d1 + d2
            }

            print(f"{player} rolled {d1} & {d2} → {d1 + d2}")

        self.state = STATE_POWERUP

    def handle_powerup(self):
        print("\n--- POWER-UP PHASE ---")

        start_index = self.players.index(self.start_player)
        ordered = self.players[start_index:] + self.players[:start_index]

        ordered = [p for p in ordered if p in self.active_players]

        print(f"Turn order: {' → '.join(ordered)}")

        leader = max(self.active_players, key=lambda p: self.rolls[p]["total"])
        print(f"🔥 Leader: {leader} ({self.rolls[leader]['total']})\n")

        for player in ordered:
            inv = self.inventory[player]
            my_score = self.rolls[player]["total"]

            leader = max(self.active_players, key=lambda p: self.rolls[p]["total"])
            leader_score = self.rolls[leader]["total"]

            used = False

            if self.round == 10 and inv["extra_die"] > 0:
                extra = random.randint(1, 6)
                self.rolls[player]["dice"].append(extra)
                self.rolls[player]["total"] += extra
                inv["extra_die"] -= 1
                print(f"{player} uses EXTRA DIE (FINAL) → +{extra}")
                continue

            if my_score < leader_score:

                if inv["extra_die"] > 0:
                    extra = random.randint(1, 6)
                    self.rolls[player]["dice"].append(extra)
                    self.rolls[player]["total"] += extra
                    inv["extra_die"] -= 1
                    print(f"{player} uses EXTRA DIE → +{extra}")
                    used = True

                elif inv["swap"] > 0:
                    target = leader
                    my_low = min(self.rolls[player]["dice"])
                    opp_high = max(self.rolls[target]["dice"])

                    self.rolls[player]["dice"].remove(my_low)
                    self.rolls[player]["dice"].append(opp_high)

                    self.rolls[target]["dice"].remove(opp_high)
                    self.rolls[target]["dice"].append(my_low)

                    self.rolls[player]["total"] = sum(self.rolls[player]["dice"])
                    self.rolls[target]["total"] = sum(self.rolls[target]["dice"])

                    inv["swap"] -= 1
                    print(f"{player} swaps with {target}")
                    used = True

                elif inv["reroll"] > 0:
                    d1 = random.randint(1, 6)
                    d2 = random.randint(1, 6)
                    self.rolls[player] = {
                        "dice": [d1, d2],
                        "total": d1 + d2
                    }
                    inv["reroll"] -= 1
                    print(f"{player} rerolls → {d1}, {d2}")
                    used = True

            if not used:
                print(f"{player} passes")

        self.state = STATE_SHOWDOWN

    def handle_showdown(self):
        print("\n--- SHOWDOWN ---")

        for p in self.active_players:
            print(f"{p}: {self.rolls[p]['total']}")

        highest = max(self.rolls[p]["total"] for p in self.active_players)
        winners = [p for p in self.active_players if self.rolls[p]["total"] == highest]

        if len(winners) > 1:
            print(f"\n⚔️ Tie → {', '.join(winners)}")

            while True:
                new = {}
                for p in winners:
                    r = random.randint(1, 6) + random.randint(1, 6)
                    new[p] = r
                    print(f"{p} rolls {r}")

                highest = max(new.values())
                winners = [p for p in new if new[p] == highest]

                if len(winners) == 1:
                    break
                print("Tie again!")

        winner = winners[0]

        print(f"\n🏆 {winner} wins {self.pot}!")
        self.points[winner] += self.pot

        print("\n📊 Scores:")
        for p in self.players:
            print(f"{p}: {self.points[p]}")

        self.start_player = winner

        self.check_elimination()

        if len(self.active_players) == 1:
            print("\n🔥 Only one player left!")
            self.state = STATE_GAMEOVER
        elif self.round >= 10:
            self.state = STATE_GAMEOVER
        else:
            self.state = STATE_SHOP

    def check_elimination(self):
        for p in self.players:
            if self.points[p] <= 0 and p in self.active_players:
                self.active_players.remove(p)
                print(f"💀 {p} is BUST!")

    def handle_shop(self):
        print("\n--- SHOP PHASE ---")

        for p in self.active_players:
            print(f"\n{p}: {self.points[p]} points")

            buy = None

            if self.points[p] >= 200 and self.inventory[p]["extra_die"] == 0:
                buy = "extra_die"
            elif self.points[p] >= 150 and self.inventory[p]["swap"] == 0:
                buy = "swap"
            elif self.points[p] >= 100:
                buy = "reroll"

            if buy and self.points[p] - SHOP[buy] >= 50:
                self.points[p] -= SHOP[buy]
                self.inventory[p][buy] += 1
                print(f"{p} buys {buy.upper()} for {SHOP[buy]}")
            else:
                print(f"{p} buys nothing")

            inv = self.inventory[p]
            print(f"Inventory → R:{inv['reroll']} S:{inv['swap']} E:{inv['extra_die']}")

        self.round += 1
        self.state = STATE_BETTING


if __name__ == "__main__":
    game = Game()
    game.run()