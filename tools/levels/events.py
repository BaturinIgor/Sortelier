"""Уровни больших ивентов: своя мини-карта на 20 уровней для каждой темы.

Запуск: python3 tools/levels/events.py
Пишет Sortelier/Resources/Data/events.json: {тема: [уровни]}. Каждый уровень проверен решателем.
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import generate as G  # noqa: E402
from rules import Order  # noqa: E402

# Тема: какие блюда и сладости попадаются в заказах
THEMES = {
    "autumn": {"dishes": ["pancakes", "sandwich", "burger"], "snacks": ["pie", "corn", "muffin", "cookie", "waffle"]},
    "winter": {"dishes": ["pancakes", "hotdog", "cheeseburger"], "snacks": ["cookie", "cupcake", "donut", "pie", "soda"]},
    "sweets": {"dishes": ["pancakes", "sub", "sandwich"], "snacks": ["donut", "cupcake", "icecream", "waffle", "muffin"]},
    "bbq": {"dishes": ["burger", "hotdog", "cheeseburger"], "snacks": ["corn", "corndog", "fries", "soda", "icecream"]},
}

# Параметры 20 уровней: от простых к сложным (как в генераторе основной карты)
PARAMS = [
    (4, 2, 4, 1, 4, 0.0, 0, False, None), (5, 2, 5, 1, 5, 0.0, 0, False, None),
    (5, 3, 6, 1, 5, 0.0, 0, False, None), (6, 3, 7, 2, 5, 0.0, 0, False, None),
    (6, 3, 8, 2, 4, 0.0, 0, True, None), (6, 3, 8, 2, 5, 0.2, 0, False, None),
    (6, 3, 9, 3, 5, 0.2, 0, False, None), (7, 3, 9, 3, 6, 0.25, 0, False, None),
    (7, 4, 10, 3, 6, 0.3, 0, False, None), (7, 4, 11, 4, 5, 0.3, 1, True, None),
    (7, 4, 11, 3, 6, 0.3, 1, False, None), (8, 4, 12, 4, 7, 0.35, 1, False, None),
    (8, 4, 12, 4, 6, 0.35, 1, False, None), (8, 4, 13, 4, 7, 0.4, 1, False, None),
    (8, 5, 14, 5, 6, 0.4, 1, True, None), (8, 4, 13, 4, 7, 0.4, 1, False, None),
    (9, 4, 14, 5, 7, 0.4, 1, False, None), (9, 5, 15, 5, 7, 0.45, 2, False, None),
    (9, 5, 16, 6, 7, 0.45, 2, False, None), (9, 5, 17, 6, 6, 0.5, 2, True, None),
]


def themed_orders(theme):
    cfg = THEMES[theme]

    def pick(rng, level_no, n_orders, n_dishes, n_ing_triples, biome=1):
        orders = [Order("dish", rng.choice(cfg["dishes"])) for _ in range(n_dishes)]
        used = sorted({ing for o in orders for ing in G.CAT.dishes[o.target]["ingredients"]})
        for _ in range(n_ing_triples):
            if used:
                orders.append(Order("triple", rng.choice(used)))
        while len(orders) < n_orders:
            orders.append(Order("triple", rng.choice(cfg["snacks"])))
        rng.shuffle(orders)
        return orders
    return pick


def main():
    out = {}
    t = time.time()
    original = G.pick_orders
    for ti, theme in enumerate(THEMES):
        G.pick_orders = themed_orders(theme)
        levels = []
        for i, params in enumerate(PARAMS):
            lv = G.generate_level(30, params, seed=70000 + ti * 100 + i)
            lv["id"] = 3000 + ti * 100 + i + 1
            lv["intro"] = None
            lv.pop("attempts", None)
            levels.append(lv)
        out[theme] = levels
        print(f"{theme}: {len(levels)} levels, {time.time() - t:.0f}s", flush=True)
    G.pick_orders = original
    with open(os.path.join(G.DATA, "events.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("written", sum(len(v) for v in out.values()), "event levels")


if __name__ == "__main__":
    random.seed(0)
    main()
