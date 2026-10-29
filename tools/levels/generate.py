"""Генератор уровней Sortelier.

Запуск: python3 tools/levels/generate.py [--biome 2] [номера уровней]
Пишет Sortelier/Resources/Data/catalog.json и levels_<биом>.json.
Каждый уровень проверяется решателем из rules.py, пороги звезд считаются по его решению.
"""
from __future__ import annotations

import json
from collections import Counter
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from rules import Catalog, Order, solve, replay_score, normalize, settle, base, SLOTS, GOURMET_MULT  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "Sortelier", "Resources", "Data")

COINS_PER_ORDER = 5
EFFICIENCY_SHARE = 0.3
# Терпение покупателя в ходах: PATIENCE_K ходов решателя на заказ, не меньше PATIENCE_MIN
PATIENCE_K = 3.5
PATIENCE_MIN = 7
TIP_MAX = 4

CATALOG = {
    "items": [
        # ингредиенты
        {"id": "bun", "kind": "ingredient", "biome": 1},
        {"id": "patty", "kind": "ingredient", "biome": 1},
        {"id": "lettuce", "kind": "ingredient", "biome": 1},
        {"id": "cheese", "kind": "ingredient", "biome": 1},
        {"id": "tomato", "kind": "ingredient", "biome": 1},
        {"id": "sausage", "kind": "ingredient", "biome": 1},
        {"id": "hotdog_bun", "kind": "ingredient", "biome": 1},
        {"id": "ketchup", "kind": "ingredient", "biome": 1},
        {"id": "bread", "kind": "ingredient", "biome": 1},
        {"id": "ham", "kind": "ingredient", "biome": 1},
        {"id": "baguette", "kind": "ingredient", "biome": 1},
        {"id": "egg", "kind": "ingredient", "biome": 1},
        {"id": "milk", "kind": "ingredient", "biome": 1},
        {"id": "honey", "kind": "ingredient", "biome": 1},
        # готовые продукты, их заказывают тройками
        {"id": "fries", "kind": "snack", "biome": 1},
        {"id": "soda", "kind": "snack", "biome": 1},
        {"id": "donut", "kind": "snack", "biome": 1},
        {"id": "cupcake", "kind": "snack", "biome": 1},
        {"id": "cookie", "kind": "snack", "biome": 1},
        {"id": "icecream", "kind": "snack", "biome": 1},
        {"id": "corn", "kind": "snack", "biome": 1},
        {"id": "muffin", "kind": "snack", "biome": 1},
        {"id": "corndog", "kind": "snack", "biome": 1},
        {"id": "waffle", "kind": "snack", "biome": 1},
        {"id": "pie", "kind": "snack", "biome": 1},
        # биом 2: японская кухня
        {"id": "rice", "kind": "ingredient", "biome": 2},
        {"id": "fish", "kind": "ingredient", "biome": 2},
        {"id": "soy", "kind": "ingredient", "biome": 2},
        {"id": "avocado", "kind": "ingredient", "biome": 2},
        {"id": "carrot", "kind": "ingredient", "biome": 2},
        {"id": "leek", "kind": "ingredient", "biome": 2},
        {"id": "mushroom", "kind": "ingredient", "biome": 2},
        {"id": "egg", "kind": "ingredient", "biome": 2, "shared": True},
        {"id": "edamame", "kind": "snack", "biome": 2},
        {"id": "mochi", "kind": "snack", "biome": 2},
        {"id": "dango", "kind": "snack", "biome": 2},
        {"id": "matcha", "kind": "snack", "biome": 2},
        {"id": "gyoza", "kind": "snack", "biome": 2},
        {"id": "taiyaki", "kind": "snack", "biome": 2},
        {"id": "tempura", "kind": "snack", "biome": 2},
        # биом 3: итальянская кухня
        {"id": "flour", "kind": "raw", "biome": 3, "chain": "dough"},
        {"id": "dough", "kind": "chain", "biome": 3},
        {"id": "mozzarella", "kind": "ingredient", "biome": 3},
        {"id": "basil", "kind": "ingredient", "biome": 3},
        {"id": "pasta", "kind": "ingredient", "biome": 3},
        {"id": "olive_oil", "kind": "ingredient", "biome": 3},
        {"id": "grapes", "kind": "ingredient", "biome": 3},
        {"id": "tomato", "kind": "ingredient", "biome": 3, "shared": True},
        {"id": "baguette", "kind": "ingredient", "biome": 3, "shared": True},
        {"id": "gelato", "kind": "snack", "biome": 3},
        {"id": "espresso", "kind": "snack", "biome": 3},
        {"id": "cannoli", "kind": "snack", "biome": 3},
        {"id": "tiramisu", "kind": "snack", "biome": 3},
        {"id": "olives", "kind": "snack", "biome": 3},
        {"id": "focaccia", "kind": "snack", "biome": 3},
        {"id": "grissini", "kind": "snack", "biome": 3},
        {"id": "panna_cotta", "kind": "snack", "biome": 3},
        # биом 4: мексиканская кухня
        {"id": "masa", "kind": "raw", "biome": 4, "chain": "tortilla"},
        {"id": "tortilla", "kind": "chain", "biome": 4},
        {"id": "beef", "kind": "ingredient", "biome": 4},
        {"id": "salsa", "kind": "ingredient", "biome": 4},
        {"id": "beans", "kind": "ingredient", "biome": 4},
        {"id": "chili", "kind": "ingredient", "biome": 4},
        {"id": "lime", "kind": "ingredient", "biome": 4},
        {"id": "onion", "kind": "ingredient", "biome": 4},
        {"id": "avocado", "kind": "ingredient", "biome": 4, "shared": True},
        {"id": "rice", "kind": "ingredient", "biome": 4, "shared": True},
        {"id": "cheese", "kind": "ingredient", "biome": 4, "shared": True},
        {"id": "nachos", "kind": "snack", "biome": 4},
        {"id": "churros", "kind": "snack", "biome": 4},
        {"id": "horchata", "kind": "snack", "biome": 4},
        {"id": "tamale", "kind": "snack", "biome": 4},
        {"id": "flan", "kind": "snack", "biome": 4},
        {"id": "concha", "kind": "snack", "biome": 4},
        {"id": "paleta", "kind": "snack", "biome": 4},
        # биом 5: французская пекарня
        {"id": "flour", "kind": "raw", "biome": 5, "chain": "dough", "shared": True},
        {"id": "dough", "kind": "chain", "biome": 5, "shared": True},
        {"id": "butter", "kind": "ingredient", "biome": 5},
        {"id": "chocolate", "kind": "ingredient", "biome": 5},
        {"id": "strawberry", "kind": "ingredient", "biome": 5},
        {"id": "cream", "kind": "ingredient", "biome": 5},
        {"id": "sugar", "kind": "ingredient", "biome": 5},
        {"id": "egg", "kind": "ingredient", "biome": 5, "shared": True},
        {"id": "milk", "kind": "ingredient", "biome": 5, "shared": True},
        {"id": "macaron", "kind": "snack", "biome": 5},
        {"id": "madeleine", "kind": "snack", "biome": 5},
        {"id": "brioche", "kind": "snack", "biome": 5},
        {"id": "canele", "kind": "snack", "biome": 5},
        {"id": "meringue", "kind": "snack", "biome": 5},
        {"id": "cafe_creme", "kind": "snack", "biome": 5},
        {"id": "millefeuille", "kind": "snack", "biome": 5},
        # продукты сезонных ивентов (биом 0): заказываются только на уровнях своей темы
        {"id": "pumpkin", "kind": "ingredient", "biome": 0, "event": "halloween"},
        {"id": "caramel_apple", "kind": "snack", "biome": 0, "event": "halloween"},
        {"id": "ghost_cookie", "kind": "snack", "biome": 0, "event": "halloween"},
        {"id": "candy_corn", "kind": "snack", "biome": 0, "event": "halloween"},
        {"id": "marshmallow", "kind": "ingredient", "biome": 0, "event": "winter"},
        {"id": "gingerbread", "kind": "snack", "biome": 0, "event": "winter"},
        {"id": "candy_cane", "kind": "snack", "biome": 0, "event": "winter"},
        {"id": "mandarin", "kind": "snack", "biome": 0, "event": "winter"},
        {"id": "lollipop", "kind": "snack", "biome": 0, "event": "sweets"},
        {"id": "cotton_candy", "kind": "snack", "biome": 0, "event": "sweets"},
        {"id": "cake_slice", "kind": "snack", "biome": 0, "event": "sweets"},
        {"id": "watermelon", "kind": "snack", "biome": 0, "event": "bbq"},
        {"id": "lemonade", "kind": "snack", "biome": 0, "event": "bbq"},
        {"id": "smores", "kind": "snack", "biome": 0, "event": "bbq"},
        {"id": "apple", "kind": "ingredient", "biome": 0, "event": "autumn"},
        {"id": "chestnuts", "kind": "snack", "biome": 0, "event": "autumn"},
        {"id": "cider", "kind": "snack", "biome": 0, "event": "autumn"},
        {"id": "cinnamon_bun", "kind": "snack", "biome": 0, "event": "autumn"},
    ],
    "dishes": [
        {"id": "burger", "ingredients": ["bun", "patty", "lettuce"], "biome": 1},
        {"id": "cheeseburger", "ingredients": ["bun", "patty", "cheese"], "biome": 1},
        {"id": "hotdog", "ingredients": ["hotdog_bun", "sausage", "ketchup"], "biome": 1},
        {"id": "sandwich", "ingredients": ["bread", "ham", "lettuce"], "biome": 1},
        {"id": "sub", "ingredients": ["baguette", "ham", "tomato"], "biome": 1},
        {"id": "pancakes", "ingredients": ["egg", "milk", "honey"], "biome": 1},
        {"id": "sushi", "ingredients": ["rice", "fish", "soy"], "biome": 2},
        {"id": "onigiri", "ingredients": ["rice", "rice", "rice"], "biome": 2},
        {"id": "maki", "ingredients": ["rice", "avocado", "carrot"], "biome": 2},
        {"id": "tamago", "ingredients": ["egg", "soy", "leek"], "biome": 2},
        {"id": "ramen", "ingredients": ["leek", "mushroom", "egg"], "biome": 2},
        {"id": "pasta", "ingredients": ["pasta", "tomato", "basil"], "biome": 3},
        {"id": "juice", "ingredients": ["grapes", "grapes", "grapes"], "biome": 3},
        {"id": "pizza", "ingredients": ["dough", "tomato", "mozzarella"], "biome": 3},
        {"id": "caprese", "ingredients": ["mozzarella", "basil", "olive_oil"], "biome": 3},
        {"id": "bruschetta", "ingredients": ["baguette", "tomato", "olive_oil"], "biome": 3},
        {"id": "taco", "ingredients": ["tortilla", "beef", "salsa"], "biome": 4},
        {"id": "limeade", "ingredients": ["lime", "lime", "lime"], "biome": 4},
        {"id": "guacamole", "ingredients": ["avocado", "lime", "onion"], "biome": 4},
        {"id": "quesadilla", "ingredients": ["tortilla", "cheese", "chili"], "biome": 4},
        {"id": "burrito", "ingredients": ["tortilla", "beans", "rice"], "biome": 4},
        {"id": "croissant", "ingredients": ["dough", "butter", "egg"], "biome": 5},
        {"id": "crepes", "ingredients": ["egg", "milk", "sugar"], "biome": 5},
        {"id": "truffles", "ingredients": ["chocolate", "chocolate", "chocolate"], "biome": 5},
        {"id": "pain_chocolat", "ingredients": ["dough", "butter", "chocolate"], "biome": 5},
        {"id": "eclair", "ingredients": ["dough", "cream", "chocolate"], "biome": 5},
        {"id": "tart", "ingredients": ["dough", "strawberry", "cream"], "biome": 5},
        {"id": "pumpkin_soup", "ingredients": ["pumpkin", "milk", "bread"], "biome": 0, "event": "halloween"},
        {"id": "hot_cocoa", "ingredients": ["milk", "chocolate", "marshmallow"], "biome": 0, "event": "winter"},
        {"id": "sundae", "ingredients": ["icecream", "strawberry", "chocolate"], "biome": 0, "event": "sweets"},
        {"id": "kebab", "ingredients": ["beef", "onion", "tomato"], "biome": 0, "event": "bbq"},
        {"id": "charlotte", "ingredients": ["apple", "egg", "sugar"], "biome": 0, "event": "autumn"},
    ],
}

# Порядок открытия блюд и снеков: номер уровня, с которого они могут попасться
UNLOCKS = {
    1: ({"burger": 6, "hotdog": 8, "pancakes": 11, "cheeseburger": 13, "sandwich": 17, "sub": 21},
        {"donut": 1, "fries": 1, "soda": 2, "cupcake": 3, "cookie": 4, "icecream": 5,
         "corn": 7, "muffin": 9, "corndog": 12, "waffle": 16, "pie": 19}),
    2: ({"sushi": 31, "onigiri": 33, "maki": 35, "tamago": 39, "ramen": 44},
        {"edamame": 31, "mochi": 31, "dango": 32, "matcha": 34, "gyoza": 37, "taiyaki": 42, "tempura": 47}),
    3: ({"pasta": 61, "juice": 62, "pizza": 64, "caprese": 68, "bruschetta": 72},
        {"gelato": 61, "espresso": 61, "cannoli": 62, "tiramisu": 63, "olives": 65, "focaccia": 67,
         "grissini": 70, "panna_cotta": 74}),
    4: ({"taco": 91, "limeade": 92, "guacamole": 94, "quesadilla": 98, "burrito": 103},
        {"nachos": 91, "churros": 91, "horchata": 92, "tamale": 93, "flan": 95, "concha": 97, "paleta": 100}),
    5: ({"croissant": 121, "crepes": 122, "truffles": 123, "pain_chocolat": 125, "eclair": 128, "tart": 132},
        {"macaron": 121, "madeleine": 121, "brioche": 122, "canele": 124, "meringue": 126, "cafe_creme": 129,
         "millefeuille": 131}),
}
DISH_UNLOCK, SNACK_UNLOCK = UNLOCKS[1]

# shelves, max_depth, orders, dishes, free_slots, hidden_share, ingredient_triples, hard, intro
# в биомах 2 и 3 еще: замороженных продуктов, замков, гурманов
LEVELS = [
    (3, 1, 2, 0, 3, 0.0, 0, False, "basics"),
    (4, 2, 3, 0, 4, 0.0, 0, False, "patience"),
    (4, 2, 4, 0, 4, 0.0, 0, False, None),
    (5, 2, 5, 0, 5, 0.0, 0, False, None),
    (5, 3, 6, 0, 4, 0.0, 0, True, None),
    (4, 2, 3, 1, 4, 0.0, 0, False, "recipes"),
    (5, 2, 5, 1, 5, 0.0, 0, False, None),
    (5, 3, 6, 2, 5, 0.0, 0, False, None),
    (6, 3, 7, 2, 5, 0.0, 0, False, None),
    (6, 3, 8, 3, 4, 0.0, 0, True, None),
    (6, 3, 8, 2, 5, 0.0, 0, False, None),
    (6, 3, 9, 3, 5, 0.0, 0, False, None),
    (6, 4, 9, 3, 5, 0.0, 0, False, None),
    (7, 3, 10, 3, 6, 0.0, 0, False, None),
    (6, 3, 9, 3, 5, 0.3, 0, False, "hidden"),
    (7, 3, 10, 4, 6, 0.3, 0, False, None),
    (7, 4, 11, 4, 6, 0.3, 0, False, None),
    (7, 4, 12, 4, 5, 0.35, 0, False, None),
    (8, 4, 12, 4, 7, 0.35, 0, False, None),
    (8, 4, 13, 5, 6, 0.4, 0, True, None),
    (8, 4, 13, 4, 7, 0.4, 1, False, "conflict"),
    (8, 4, 14, 5, 6, 0.4, 1, False, None),
    (8, 5, 14, 5, 7, 0.4, 1, False, None),
    (9, 4, 15, 5, 7, 0.45, 1, False, None),
    (9, 5, 16, 6, 6, 0.45, 2, True, None),
    (9, 5, 16, 6, 7, 0.45, 1, False, None),
    (9, 5, 17, 6, 7, 0.5, 2, False, None),
    (9, 5, 18, 7, 7, 0.5, 2, False, None),
    (9, 5, 18, 7, 7, 0.5, 2, False, None),
    (9, 5, 20, 8, 6, 0.5, 2, True, None),
]

F, T = False, True
LEVELS2 = [
    (6, 3, 8, 2, 5, 0.2, 0, F, None, 0, 0, 0),
    (6, 3, 9, 2, 5, 0.25, 0, F, None, 0, 0, 0),
    (6, 3, 9, 3, 5, 0.25, 0, F, "onigiri", 0, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 0, 0, 0),
    (7, 3, 11, 4, 6, 0.3, 0, T, None, 0, 0, 0),
    (6, 3, 9, 3, 5, 0.3, 0, F, "ice", 2, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 2, 0, 0),
    (7, 4, 11, 4, 6, 0.35, 0, F, None, 3, 0, 0),
    (7, 4, 12, 4, 6, 0.35, 1, F, None, 3, 0, 0),
    (8, 4, 13, 5, 6, 0.4, 1, T, None, 3, 0, 0),
    (7, 3, 11, 4, 6, 0.35, 0, F, "gourmet", 2, 0, 1),
    (8, 4, 12, 4, 7, 0.35, 1, F, None, 3, 0, 1),
    (8, 4, 13, 5, 6, 0.4, 1, F, None, 3, 0, 1),
    (8, 4, 13, 5, 7, 0.4, 1, F, None, 4, 0, 1),
    (8, 4, 14, 5, 6, 0.4, 1, T, None, 4, 0, 2),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 4, 0, 1),
    (8, 4, 15, 6, 7, 0.45, 1, F, None, 4, 0, 1),
    (9, 4, 15, 6, 7, 0.45, 1, F, None, 5, 0, 2),
    (9, 5, 16, 6, 7, 0.45, 2, F, None, 5, 0, 1),
    (9, 5, 17, 7, 6, 0.5, 2, T, None, 5, 0, 2),
    (8, 4, 15, 6, 7, 0.45, 1, F, None, 4, 0, 1),
    (9, 4, 16, 6, 7, 0.45, 1, F, None, 5, 0, 2),
    (9, 5, 17, 7, 7, 0.5, 2, F, None, 5, 0, 1),
    (9, 5, 17, 7, 7, 0.5, 2, F, None, 6, 0, 2),
    (9, 5, 18, 7, 6, 0.5, 2, T, None, 6, 0, 2),
    (9, 5, 18, 7, 7, 0.5, 2, F, None, 5, 0, 1),
    (9, 5, 19, 8, 7, 0.5, 2, F, None, 6, 0, 2),
    (9, 5, 19, 8, 7, 0.5, 2, F, None, 6, 0, 2),
    (9, 5, 20, 8, 7, 0.5, 2, F, None, 6, 0, 2),
    (9, 5, 21, 9, 6, 0.55, 2, T, None, 7, 0, 3),
]

LEVELS3 = [
    (6, 3, 8, 2, 5, 0.25, 0, F, None, 0, 0, 1),
    (6, 3, 9, 3, 5, 0.25, 0, F, "juice", 2, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 2, 0, 1),
    (6, 3, 8, 3, 5, 0.25, 0, F, "dough", 0, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, T, None, 2, 0, 1),
    (7, 3, 10, 3, 6, 0.3, 0, F, "lock", 0, 1, 0),
    (7, 3, 11, 4, 6, 0.3, 0, F, None, 2, 1, 1),
    (7, 4, 11, 4, 6, 0.35, 1, F, None, 2, 1, 1),
    (8, 4, 12, 4, 7, 0.35, 1, F, None, 3, 1, 1),
    (8, 4, 13, 5, 6, 0.4, 1, T, None, 3, 1, 2),
    (8, 4, 13, 5, 7, 0.4, 1, F, None, 3, 1, 1),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 3, 2, 1),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 4, 1, 2),
    (9, 4, 15, 6, 7, 0.45, 1, F, None, 4, 2, 1),
    (9, 5, 16, 6, 6, 0.45, 2, T, None, 4, 2, 2),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 4, 1, 1),
    (9, 4, 15, 6, 7, 0.45, 1, F, None, 4, 2, 2),
    (9, 5, 16, 6, 7, 0.45, 2, F, None, 5, 2, 1),
    (9, 5, 17, 7, 7, 0.5, 2, F, None, 5, 2, 2),
    (9, 5, 18, 7, 6, 0.5, 2, T, None, 5, 2, 2),
    (9, 5, 17, 7, 7, 0.5, 2, F, None, 5, 2, 1),
    (9, 5, 18, 7, 7, 0.5, 2, F, None, 6, 2, 2),
    (9, 5, 18, 7, 7, 0.5, 2, F, None, 6, 2, 2),
    (9, 5, 19, 8, 7, 0.5, 2, F, None, 6, 2, 2),
    (9, 5, 20, 8, 6, 0.55, 2, T, None, 6, 2, 3),
    (9, 5, 19, 8, 7, 0.5, 2, F, None, 6, 2, 2),
    (9, 5, 20, 8, 7, 0.55, 2, F, None, 6, 2, 2),
    (9, 5, 20, 8, 7, 0.55, 2, F, None, 7, 2, 2),
    (9, 5, 21, 9, 7, 0.55, 2, F, None, 7, 2, 3),
    (9, 5, 22, 9, 6, 0.6, 2, T, None, 7, 2, 3),
]

# биомы 4 и 5: еще замки с ключом (keys) и цепи (chains)
# shelves, depth, orders, dishes, free, hidden, ing_triples, hard, intro, ice, locks, gourmet, keys, chains
LEVELS4 = [
    (6, 3, 8, 2, 5, 0.25, 0, F, "masa", 0, 0, 0, 0, 0),
    (6, 3, 9, 3, 5, 0.25, 0, F, "limeade", 1, 0, 1, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 2, 0, 1, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 2, 1, 0, 0, 0),
    (7, 3, 11, 4, 6, 0.3, 0, T, None, 2, 1, 1, 0, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, "key", 0, 0, 0, 1, 0),
    (7, 3, 11, 4, 6, 0.3, 0, F, None, 2, 0, 1, 1, 0),
    (7, 4, 11, 4, 6, 0.35, 1, F, None, 2, 0, 1, 1, 0),
    (8, 4, 12, 4, 7, 0.35, 1, F, None, 3, 1, 1, 1, 0),
    (8, 4, 13, 5, 6, 0.4, 1, T, None, 3, 1, 2, 1, 0),
    (8, 4, 13, 5, 7, 0.4, 1, F, None, 3, 0, 1, 2, 0),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 3, 1, 1, 1, 0),
    (8, 4, 14, 5, 7, 0.4, 1, F, None, 4, 1, 2, 2, 0),
    (9, 4, 15, 6, 7, 0.45, 1, F, None, 4, 1, 1, 2, 0),
    (9, 5, 16, 6, 6, 0.45, 2, T, None, 4, 2, 2, 2, 0),
    (8, 4, 14, 5, 8, 0.4, 1, F, None, 4, 1, 1, 1, 0),
    (9, 4, 15, 6, 8, 0.45, 1, F, None, 4, 0, 2, 2, 0),
    (9, 5, 16, 6, 8, 0.45, 2, F, None, 5, 0, 1, 2, 0),
    (9, 5, 17, 7, 8, 0.5, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 18, 7, 7, 0.5, 2, T, None, 5, 0, 2, 2, 0),
    (9, 5, 17, 7, 8, 0.5, 2, F, None, 5, 0, 1, 2, 0),
    (9, 5, 18, 7, 8, 0.5, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 18, 7, 8, 0.5, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 19, 8, 8, 0.5, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 20, 8, 7, 0.55, 2, T, None, 5, 0, 3, 2, 0),
    (9, 5, 19, 8, 8, 0.5, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 20, 8, 8, 0.55, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 20, 8, 8, 0.55, 2, F, None, 5, 0, 2, 2, 0),
    (9, 5, 21, 9, 8, 0.55, 2, F, None, 5, 0, 3, 2, 0),
    (9, 5, 22, 9, 7, 0.6, 2, T, None, 5, 0, 3, 2, 0),
]

LEVELS5 = [
    (6, 3, 8, 2, 5, 0.25, 0, F, "bakery", 0, 0, 0, 0, 0),
    (6, 3, 9, 3, 5, 0.25, 0, F, None, 1, 0, 1, 1, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, "truffles", 2, 0, 1, 1, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, None, 2, 1, 0, 1, 0),
    (7, 3, 11, 4, 6, 0.3, 0, T, None, 2, 1, 1, 1, 0),
    (7, 3, 10, 3, 6, 0.3, 0, F, "chain", 0, 0, 0, 0, 1),
    (7, 3, 11, 4, 6, 0.3, 0, F, None, 2, 0, 1, 0, 1),
    (7, 4, 11, 4, 6, 0.35, 1, F, None, 2, 0, 1, 1, 1),
    (8, 4, 12, 4, 7, 0.35, 1, F, None, 3, 1, 1, 0, 1),
    (8, 4, 13, 5, 6, 0.4, 1, T, None, 3, 1, 2, 1, 1),
    (8, 4, 13, 5, 8, 0.4, 1, F, None, 3, 0, 1, 1, 1),
    (8, 4, 14, 5, 8, 0.4, 1, F, None, 3, 0, 1, 1, 1),
    (8, 4, 14, 5, 8, 0.4, 1, F, None, 4, 0, 2, 1, 2),
    (9, 4, 15, 6, 8, 0.45, 1, F, None, 4, 0, 1, 1, 1),
    (9, 5, 16, 6, 7, 0.45, 2, T, None, 4, 0, 2, 1, 2),
    (8, 4, 14, 5, 8, 0.4, 1, F, None, 4, 0, 1, 1, 1),
    (9, 4, 15, 6, 8, 0.45, 1, F, None, 4, 0, 2, 1, 2),
    (9, 5, 16, 6, 8, 0.45, 2, F, None, 5, 0, 1, 1, 1),
    (9, 5, 17, 7, 8, 0.5, 2, F, None, 5, 1, 2, 0, 2),
    (9, 5, 18, 7, 7, 0.5, 2, T, None, 5, 0, 2, 1, 2),
    (9, 5, 17, 7, 8, 0.5, 2, F, None, 5, 0, 1, 1, 2),
    (9, 5, 18, 7, 8, 0.5, 2, F, None, 5, 0, 2, 1, 2),
    (9, 5, 18, 7, 8, 0.5, 2, F, None, 5, 0, 2, 1, 2),
    (9, 5, 19, 8, 8, 0.5, 2, F, None, 5, 0, 2, 1, 2),
    (9, 5, 20, 8, 7, 0.55, 2, T, None, 5, 0, 3, 1, 3),
    (9, 5, 19, 8, 8, 0.5, 2, F, None, 5, 0, 2, 1, 2),
    (9, 5, 20, 8, 8, 0.55, 2, F, None, 5, 0, 2, 1, 3),
    (9, 5, 20, 8, 8, 0.55, 2, F, None, 5, 0, 2, 1, 2),
    (9, 5, 21, 9, 8, 0.55, 2, F, None, 5, 0, 3, 1, 3),
    (9, 5, 22, 9, 7, 0.6, 2, T, None, 5, 0, 3, 1, 3),
]

BIOME_LEVELS = {1: (1, LEVELS), 2: (31, LEVELS2), 3: (61, LEVELS3), 4: (91, LEVELS4), 5: (121, LEVELS5)}


def triple_ok(item):
    """Тройку ингредиента можно заказать, если три одинаковых не дают блюдо или цепочку."""
    if item in CAT.chains or CATALOG_KIND.get(item) in ("raw", "chain"):
        return False
    return (item, item, item) not in CAT.recipe_index


def pick_orders(rng, level_no, n_orders, n_dishes, n_ing_triples, biome=1):
    dish_unlock, snack_unlock = UNLOCKS[biome]
    dishes = [d for d, lv in dish_unlock.items() if lv <= level_no]
    snacks = [s for s, lv in snack_unlock.items() if lv <= level_no]
    orders = []
    # новое блюдо уровня-открытия обязательно попадает в заказы
    newest = [d for d, lv in dish_unlock.items() if lv == level_no]
    for i in range(n_dishes):
        d = newest[0] if (i == 0 and newest) else rng.choice(dishes)
        orders.append(Order("dish", d))
    used_ings = sorted({ing for o in orders for ing in CAT.dishes[o.target]["ingredients"] if triple_ok(ing)})
    for _ in range(n_ing_triples):
        if used_ings:
            orders.append(Order("triple", rng.choice(used_ings)))
    newest_snack = [s for s, lv in snack_unlock.items() if lv == level_no]
    while len(orders) < n_orders:
        if newest_snack and not any(o.target == newest_snack[0] for o in orders):
            orders.append(Order("triple", newest_snack[0]))
        else:
            orders.append(Order("triple", rng.choice(snacks)))
    rng.shuffle(orders)
    return orders


def items_for(orders):
    items = []
    raw_of = {v: k for k, v in CAT.chains.items()}
    for o in orders:
        if o.kind == "triple":
            items += [o.target] * 3
        else:
            for ing in CAT.dishes[o.target]["ingredients"]:
                # продукт цепочки собирается на полке из трех сырых
                items += [raw_of[ing]] * 3 if ing in raw_of else [ing]
    return items


def layout(rng, items, n_shelves, max_depth, free_slots):
    items = list(items)
    rng.shuffle(items)
    front_count = min(len(items), n_shelves * SLOTS - free_slots)
    shelves = [[[None] * SLOTS] for _ in range(n_shelves)]
    cells = [(s, k) for s in range(n_shelves) for k in range(SLOTS)]
    rng.shuffle(cells)
    for (s, k), item in zip(cells[:front_count], items[:front_count]):
        shelves[s][0][k] = item
    rest = items[front_count:]
    for item in rest:
        options = []
        for s in range(n_shelves):
            layers = shelves[s]
            last = layers[-1] if len(layers) > 1 else None
            if last is not None and None in last and sum(c is not None for c in last) < rng.choice([2, 3, 3]):
                options.append((s, "same"))
            if len(layers) < max_depth:
                options.append((s, "new"))
        if not options:
            return None
        s, mode = rng.choice(options)
        if mode == "new":
            layer = [None] * SLOTS
            layer[rng.randrange(SLOTS)] = item
            shelves[s].append(layer)
        else:
            last = shelves[s][-1]
            free = [k for k in range(SLOTS) if last[k] is None]
            last[rng.choice(free)] = item
    # передний ряд не должен быть пустым у полки с задними рядами
    for layers in shelves:
        if len(layers) > 1 and all(c is None for c in layers[0]):
            return None
    return shelves


def ready_to_fire(shelves, orders):
    wanted = {(o.kind, o.target) for o in orders}
    for layers in shelves:
        for layer in layers:
            res = CAT.result_of(layer)
            if res and res in wanted:
                return True
            if CAT.transform_of(layer):
                return True
    return False


def add_ice(rng, shelves, count, n_orders):
    """Замораживает count продуктов: лед тает после 1..3 обслуженных покупателей."""
    # лед виден, только если продукт впереди или сразу за передним рядом: туда и ставим
    front = [(s, 0, k) for s, layers in enumerate(shelves) for k, c in enumerate(layers[0]) if c]
    second = [(s, 1, k) for s, layers in enumerate(shelves) if len(layers) > 1 for k, c in enumerate(layers[1]) if c]
    rng.shuffle(front)
    rng.shuffle(second)
    n_front = min(len(front), (count + 1) // 2)
    top = max(1, min(3, n_orders // 3))
    for s, d, k in front[:n_front] + second[:count - n_front]:
        lo = 1 if d == 0 else 2
        shelves[s][d][k] = f"{shelves[s][d][k]}@{rng.randint(lo, max(lo, top + d))}"


def pick_locks(rng, shelves, count, n_orders):
    """Замки на полках: открываются после 2..5 обслуженных покупателей."""
    locks = [0] * len(shelves)
    candidates = [s for s, layers in enumerate(shelves) if any(c for c in layers[0])]
    rng.shuffle(candidates)
    top = max(2, min(5, n_orders // 3))
    for s in candidates[:count]:
        locks[s] = rng.randint(2, top)
    return locks


def replay(shelves, orders, path, locks=None, keys=None, chains=None):
    """Проигрывает решение с препятствиями. Возвращает (первый ход, задевший полку; ход, на котором впервые
    обслужен каждый спрайт заказа) или None, если с этими препятствиями решение не проходит."""
    from rules import Obstacles, apply_move_detail, settle_detail, sprite
    sh = normalize(shelves)
    od = list(orders)
    obs = Obstacles(od, locks, keys, chains)
    cst = obs.start()
    for _, shelf in settle_detail(CAT, sh, od, range(len(sh))):
        cst = obs.fired(cst, shelf)
    first_touch, served_at = {}, {}
    # сколько покупателей обслужено перед каждым ходом
    served_before = []
    count = len(orders) - len(od)
    for m, (s, k, d) in enumerate(path):
        served_before.append(count)
        first_touch.setdefault(s, m)
        first_touch.setdefault(d, m)
        before = list(od)
        res = apply_move_detail(CAT, sh, od, s, k, d, obs, cst)
        if res is None:
            return None
        sh, od, fired, cst = res
        for idx, _ in fired:
            served_at.setdefault(sprite(before.pop(idx)), m)
        count = len(orders) - len(od)
    if od:
        return None
    replay.served_before = served_before
    return first_touch, served_at


def place_locks(rng, shelves, orders, path, count):
    """Замки по числу обслуженных по готовому решению: полка, которую решение не трогает, пока не обслужено N,
    запирается на N (2..5). Так уровень с замками гарантированно проходим."""
    first_touch, _ = replay(shelves, orders, path)
    before = replay.served_before
    locks = [0] * len(shelves)
    options = []
    for s, layers in enumerate(shelves):
        if not any(c for c in layers[0]):
            continue
        touch = first_touch.get(s, len(path))
        n = before[touch] if touch < len(before) else len(orders)
        if n >= 2:
            options.append((s, min(5, n)))
    rng.shuffle(options)
    for s, n in options[:count]:
        locks[s] = rng.randint(2, n)
    return locks if any(locks) else None


def place_keys(rng, shelves, orders, path, count, locks):
    """Замки с ключом по готовому решению: полку, которую решение не трогает до первого обслуживания заказа X,
    запираем на ключ X. Решение остается верным, уровень гарантированно проходим."""
    first_touch, served_at = replay(shelves, orders, path, locks)
    keys = [None] * len(shelves)
    options = []
    for s, layers in enumerate(shelves):
        if locks and locks[s]:
            continue
        if not all(c for c in layers[0]):
            continue
        touch = first_touch.get(s, len(path))
        for x, m in served_at.items():
            # ключ не самый первый заказ и полка ждет его хотя бы пару ходов
            if 2 <= m and m + 1 < touch:
                options.append((s, x, touch - m))
    rng.shuffle(options)
    used = set()
    for s, x, _ in sorted(options, key=lambda o: -o[2])[: max(count * 4, 1)]:
        if len([k for k in keys if k]) >= count:
            break
        if s in used or x in keys:
            continue
        keys[s] = x
        used.add(s)
    return keys if any(keys) else None


def place_chains(rng, shelves, orders, path, count, locks, keys):
    """Цепи между соседними полками одного ряда, которые решение проходит без нарушений."""
    pairs = [(i, i + 1) for i in range(len(shelves) - 1) if i % 3 != 2]
    rng.shuffle(pairs)
    chains = []
    used = set()
    for a, b in pairs:
        if len(chains) >= count:
            break
        if a in used or b in used:
            continue
        if (locks and (locks[a] or locks[b])) or (keys and (keys[a] or keys[b])):
            continue
        if not any(c for c in shelves[a][0]) or not any(c for c in shelves[b][0]):
            continue
        trial = chains + [[a, b]]
        if replay(shelves, orders, path, locks, keys, trial) is None:
            continue
        chains = trial
        used |= {a, b}
    return chains


# Уровни ивентов включают проверку длины решения сами (events.py)
STRICT_LENGTH = False


def generate_level(level_no, params, seed, biome=1):
    shelves_n, depth, n_orders, n_dishes, free, hidden, ing_triples, hard, intro = params[:9]
    n_ice, n_locks, n_gourmet = params[9:12] if len(params) > 9 else (0, 0, 0)
    n_keys, n_chains = params[12:14] if len(params) > 12 else (0, 0)
    rng = random.Random(seed)
    # слишком длинное решение (решатель петлял) дает нечестные пороги звезд и терпение: ищем короче,
    # но после нескольких длинных берем самое короткое из них (для кухонь 4-5 и ивентов)
    strict = STRICT_LENGTH or biome >= 4
    long_ones = []
    for attempt in range(600):
        orders = pick_orders(rng, level_no, n_orders, n_dishes, ing_triples, biome)
        items = items_for(orders)
        if len(items) > shelves_n * SLOTS * depth - free:
            continue
        shelves = layout(rng, items, shelves_n, depth, free)
        if shelves is None or ready_to_fire(shelves, orders):
            continue
        if n_ice:
            add_ice(rng, shelves, n_ice, n_orders)
        # глубину поиска ограничиваем: слишком длинное решение все равно не возьмем, а тупиковые раскладки
        # иначе ищутся очень долго
        depth_cap = int(len(items) * 2.4) + 12 if strict else 400
        if biome >= 4:
            # кухни 4-5: сначала решение без замков, замки ставятся по нему
            path = solve(CAT, shelves, orders, beam=120 if n_orders > 12 else 200, max_depth=depth_cap)
            if path is None:
                continue
            locks = place_locks(rng, shelves, orders, path, n_locks) if n_locks else None
            if n_locks and not locks:
                continue
        else:
            locks = pick_locks(rng, shelves, n_locks, n_orders) if n_locks else None
            path = solve(CAT, shelves, orders, beam=120 if n_orders > 12 else 200, max_depth=depth_cap, locks=locks)
            if path is None:
                continue
        # замки с ключом и цепи ставятся по найденному решению: оно остается верным
        keys = place_keys(rng, shelves, orders, path, n_keys, locks) if n_keys else None
        # по плану может быть два ключа или три цепи; если решение позволяет меньше, хватит одного
        if n_keys and not any(keys or []):
            continue
        chains = place_chains(rng, shelves, orders, path, n_chains, locks, keys) if n_chains else None
        if n_chains and not chains:
            continue
        # слишком простой уровень для своей позиции пропускаем
        if level_no > 3 and len(path) < len(items) * 0.45:
            continue
        if strict and len(path) > len(items) * 1.8:
            long_ones.append((len(path) / len(items), attempt, orders, shelves, path, locks, keys, chains))
            if len(long_ones) < 4:
                continue
            _, attempt, orders, shelves, path, locks, keys, chains = min(long_ones, key=lambda c: c[0])
        # Гурман: не больше одного за уровень, приходит посреди уровня (не в первой тройке очереди),
        # обычно ждет блюдо
        gourmet = []
        if n_gourmet:
            late = [i for i in range(len(orders)) if 3 <= i <= max(3, len(orders) // 2)]
            dish_idx = [i for i in late if orders[i].kind == "dish"]
            pool = dish_idx or late
            if pool:
                gourmet = [rng.choice(pool)]
        patience = max(PATIENCE_MIN, round(PATIENCE_K * len(path) / n_orders))
        coins = replay_score(CAT, shelves, orders, path, COINS_PER_ORDER, patience=patience, tip_max=TIP_MAX,
                             locks=locks, gourmet=gourmet, keys=keys, chains=chains)
        base = COINS_PER_ORDER * n_orders
        best = coins + round(EFFICIENCY_SHARE * base)
        star2 = base + round(0.35 * (best - base))
        star3 = base + round(0.8 * (best - base))
        hidden_mask = []
        for layers in shelves:
            hidden_mask.append([[(depth_i > 0 and c is not None and rng.random() < hidden) for c in layer]
                                for depth_i, layer in enumerate(layers)])
        cells = []
        for layers, mask_layers in zip(shelves, hidden_mask):
            cells.append([[("?" + c if c and m else c) for c, m in zip(layer, mask)]
                          for layer, mask in zip(layers, mask_layers)])
        level = {
            "id": level_no,
            "biome": biome,
            "shelves": cells,
            "orders": [o.to_json() for o in orders],
            "par": len(path),
            "patience": patience,
            "tipMax": TIP_MAX,
            "stars": [star2, star3],
            "best": best,
            "hard": hard,
            "intro": intro,
            "attempts": attempt + 1,
        }
        if locks:
            level["locks"] = locks
        if keys and any(keys):
            level["keys"] = keys
        if chains:
            level["chains"] = chains
        if gourmet:
            level["gourmet"] = gourmet
        return level
    raise RuntimeError(f"level {level_no}: no solvable layout")


CAT = Catalog(CATALOG)
CATALOG_KIND = {i["id"]: i["kind"] for i in CATALOG["items"]}


def catalog_json():
    """Каталог для игры: продукт входит в биом, где появился впервые (shared не дублируем)."""
    items = [{k: v for k, v in i.items() if k != "shared"} for i in CATALOG["items"] if not i.get("shared")]
    return {"items": items, "dishes": CATALOG["dishes"]}


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "catalog.json"), "w") as f:
        json.dump(catalog_json(), f, ensure_ascii=False, indent=1)
    args = sys.argv[1:]
    biome = 1
    if "--biome" in args:
        i = args.index("--biome")
        biome = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    only = set(int(x) for x in args) if args else None
    first, table = BIOME_LEVELS[biome]
    levels = []
    path = os.path.join(DATA, f"levels_{biome}.json")
    if only and os.path.exists(path):
        levels = json.load(open(path))
    for i, params in enumerate(table, start=first):
        if only and i not in only:
            continue
        t = time.time()
        lv = generate_level(i, params, seed=1000 + i, biome=biome)
        levels = [l for l in levels if l["id"] != i] + [lv]
        print(f"level {i:2d}: orders {params[2]:2d}, par {lv['par']:3d}, patience {lv['patience']}, stars {lv['stars']}, "
              f"attempts {lv['attempts']}, {time.time() - t:.1f}s", flush=True)
    levels.sort(key=lambda l: l["id"])
    for l in levels:
        l.pop("attempts", None)
    with open(path, "w") as f:
        json.dump(levels, f, ensure_ascii=False, separators=(",", ":"))
    print("written", len(levels), "levels")


if __name__ == "__main__":
    main()
