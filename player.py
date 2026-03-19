import pygame
from constants import STARTING_CAPITAL, CURRENCY_STEP

class Player:
    def __init__(self, name, is_ai=True):
        self.name = name
        self.is_ai = is_ai
        self.points = STARTING_CAPITAL
        self.inventory = {
            "Reroll": 1,
            "Swap": 1,
            "Extra Die": 1
        }
        self.dice = []
        self.is_bust = False
        self.is_starter = False
        self.has_used_powerup = False

    def add_points(self, amount):
        if amount % CURRENCY_STEP != 0:
            raise ValueError(f"Amount {amount} is not a multiple of {CURRENCY_STEP}")
        self.points += amount

    def subtract_points(self, amount):
        if amount % CURRENCY_STEP != 0:
            raise ValueError(f"Amount {amount} is not a multiple of {CURRENCY_STEP}")
        self.points -= amount
        if self.points <= 0:
            self.points = 0
            self.is_bust = True

    def has_powerup(self, powerup_type):
        return self.inventory.get(powerup_type, 0) > 0

    def use_powerup(self, powerup_type):
        if self.has_powerup(powerup_type):
            self.inventory[powerup_type] -= 1
            return True
        return False

    def reset_dice(self):
        self.dice = []

    def __str__(self):
        return f"{self.name} ({'AI' if self.is_ai else 'Human'}): {self.points} pts | Inv: {self.inventory}"
