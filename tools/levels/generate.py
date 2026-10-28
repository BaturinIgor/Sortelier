"""Генератор уровней Sortelier.

Запуск: python3 tools/levels/generate.py
Пишет Sortelier/Resources/Data/catalog.json и levels_1.json.
Каждый уровень проверяется решателем из rules.py, пороги звезд считаются по его решению.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from rules import Catalog, Order, solve, replay_score, normalize, settle, SLOTS  # noqa: E402

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
    ],
    "dishes": [
        {"id": "burger", "ingredients": ["bun", "patty", "lettuce"], "biome": 1},
        {"id": "cheeseburger", "ingredients": ["bun", "patty", "cheese"], "biome": 1},
        {"id": "hotdog", "ingredients": ["hotdog_bun", "sausage", "ketchup"], "biome": 1},
        {"id": "sandwich", "ingredients": ["bread", "ham", "lettuce"], "biome": 1},
        {"id": "sub", "ingredients": ["baguette", "ham", "tomato"], "biome": 1},
        {"id": "pancakes", "ingredients": ["egg", "milk", "honey"], "biome": 1},
    ],
}

# Порядок открытия блюд в биоме 1: номер уровня, с которого блюдо может попасться
DISH_UNLOCK = {"burger": 6, "hotdog": 8, "pancakes": 11, "cheeseburger": 13, "sandwich": 17, "sub": 21}
SNACK_UNLOCK = {"donut": 1, "fries": 1, "soda": 2, "cupcake": 3, "cookie": 4, "icecream": 5,
                "corn": 7, "muffin": 9, "corndog": 12, "waffle": 16, "pie": 19}

# shelves, max_depth, orders, dishes, free_slots, hidden_share, ingredient_triples, hard, intro
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


def pick_orders(rng, level_no, n_orders, n_dishes, n_ing_triples):
    dishes = [d for d, lv in DISH_UNLOCK.items() if lv <= level_no]
    snacks = [s for s, lv in SNACK_UNLOCK.items() if lv <= level_no]
    orders = []
    # новое блюдо уровня-открытия обязательно попадает в заказы
    newest = [d for d, lv in DISH_UNLOCK.items() if lv == level_no]
    for i in range(n_dishes):
        d = newest[0] if (i == 0 and newest) else rng.choice(dishes)
        orders.append(Order("dish", d))
    used_ings = sorted({ing for o in orders for ing in CAT.dishes[o.target]["ingredients"]})
    for _ in range(n_ing_triples):
        if used_ings:
            orders.append(Order("triple", rng.choice(used_ings)))
    newest_snack = [s for s, lv in SNACK_UNLOCK.items() if lv == level_no]
    while len(orders) < n_orders:
        if newest_snack and not any(o.target == newest_snack[0] for o in orders):
            orders.append(Order("triple", newest_snack[0]))
        else:
            orders.append(Order("triple", rng.choice(snacks)))
    rng.shuffle(orders)
    return orders


def items_for(orders):
    items = []
    for o in orders:
        if o.kind == "triple":
            items += [o.target] * 3
        else:
            items += list(CAT.dishes[o.target]["ingredients"])
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
    return False


def generate_level(level_no, params, seed):
    shelves_n, depth, n_orders, n_dishes, free, hidden, ing_triples, hard, intro = params
    rng = random.Random(seed)
    for attempt in range(400):
        orders = pick_orders(rng, level_no, n_orders, n_dishes, ing_triples)
        shelves = layout(rng, items_for(orders), shelves_n, depth, free)
        if shelves is None or ready_to_fire(shelves, orders):
            continue
        path = solve(CAT, shelves, orders, beam=120 if n_orders > 12 else 200)
        if path is None:
            continue
        # слишком простой уровень для своей позиции пропускаем
        if level_no > 3 and len(path) < len(items_for(orders)) * 0.45:
            continue
        patience = max(PATIENCE_MIN, round(PATIENCE_K * len(path) / n_orders))
        coins = replay_score(CAT, shelves, orders, path, COINS_PER_ORDER, patience=patience, tip_max=TIP_MAX)
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
        return {
            "id": level_no,
            "biome": 1,
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
    raise RuntimeError(f"level {level_no}: no solvable layout")


CAT = Catalog(CATALOG)


def main():
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "catalog.json"), "w") as f:
        json.dump(CATALOG, f, ensure_ascii=False, indent=1)
    only = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None
    levels = []
    path = os.path.join(DATA, "levels_1.json")
    if only and os.path.exists(path):
        levels = json.load(open(path))
    for i, params in enumerate(LEVELS, start=1):
        if only and i not in only:
            continue
        t = time.time()
        lv = generate_level(i, params, seed=1000 + i)
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
