"""Уровни "Рынка" 61-600: собираются из форм и узоров препятствий с постоянным зерном, поэтому повторяемы.

Ходы и звезды по-прежнему подбирает generate.py по прогонам бота.

Ритм главы из 30 уровней (номер внутри главы):
- 5, 10, 15, 20, 25, 30 - сложные;
- 7, 13, 22, 28 - праздничные ("Фейерверк"): 4 продукта, спецфишки на поле со старта и падают сверху,
  новые фишки чаще повторяют цвет соседа - все взрывается, цели крупные, ходов с запасом;
- 3, 11, 18, 24 - с подкруткой: новые фишки иногда подстраиваются под соседей, чтобы чаще выходили
  длинные ряды и уголки (скалки, бомбы, пончики), но не настолько, чтобы уровень играл сам.
"""
from __future__ import annotations

import random

from levels import COLORS6, PER_CHAPTER, SHAPES, block, checker, count, level, mirror, put, rows_
from validate import starving

FEVER_SLOTS = (7, 13, 22, 28)
LUCKY_SLOTS = (3, 11, 18, 24)
HARD_SLOTS = (5, 10, 15, 20, 25, 30)

# Формы для новых глав: к старым добавлены еще несколько.
SHAPES.update({
    "cross": ["--....--", "--....--", "........", "........", "........", "........", "........", "--....--", "--....--"],
    "arch": ["........", "........", "........", "........", "........", "..----..", "..-..-..", ".-....-.", "........"],
    "pyramid": ["---..---", "--....--", "--....--", "-......-", "-......-", "........", "........", "........"],
    "zigzag": ["........", "------..", "........", "........", "..------", "........", "........", "........"],
    "frame": ["........", "........", "..-..-..", "........", "........", "..-..-..", "........", "........", "........"],
    "tower": ["--....--", "--....--", "--....--", "-......-", "-......-", "........", "........", "........", "........"],
    "butterfly": ["..-..-..", "........", "........", "-......-", "--....--", "-......-", "........", "........", "..-..-.."],
})

NORMAL_SHAPES = ["full", "wide", "diamond", "heart", "hourglass", "ring", "columns", "stairs", "plus", "twins",
                 "mushroom", "house", "bowl", "window", "corners", "cross", "arch", "pyramid", "zigzag", "frame",
                 "tower", "butterfly"]
FEVER_SHAPES = ["full", "wide", "diamond", "heart", "plus", "corners", "house", "cross", "frame"]

FEVER_START = ["B", "H", "W"]


def fever(lv, first=False):
    """Делает уровень праздничным."""
    lv["fever"] = True
    lv["colors"] = lv["colors"][:4]
    lv["goals"] = [g for g in lv["goals"] if g["type"] != "collect" or g["item"] in lv["colors"]] or \
        [{"type": "collect", "item": lv["colors"][0], "count": 60}]
    lv["luck"] = 0.25
    lv["gift"] = 0.05
    lv["start"] = FEVER_START + (["R"] if lv["id"] > 60 else [])
    if first:
        lv["intro"] = "m3.fever"
    return lv


def rows_of(g):
    return len(g)


def bottom_rows(g, k, cols=None):
    n = rows_of(g)
    return rows_(g, range(n - k, n), cols)


# MARK: - Узоры препятствий

def crate_pattern(rng, g, layers):
    """Ящики снизу: 1-3 нижних ряда, иногда только середина или края. Слои растут к низу."""
    n = rows_of(g)
    depth = rng.choice([1, 2, 2, 3])
    cols = rng.choice([range(8), range(8), range(1, 7), [0, 1, 2, 5, 6, 7], range(2, 6)])
    for i in range(depth):
        r = n - 1 - i
        layer = max(1, min(layers, layers - (i if rng.random() < 0.6 else 0)))
        put(g, str(layer), rows_(g, [r], cols))


def ice_pattern(rng, g, thick):
    n = rows_of(g)
    ch = "I" if thick else "i"
    kind = rng.choice(["checker", "pairs", "line", "scatter"])
    if kind == "checker":
        r0 = rng.randint(2, max(2, n - 5))
        put(g, ch, checker(r0, rng.choice([0, 2]), rng.choice([2, 3]), rng.choice([4, 8]), rng.randint(0, 1)))
    elif kind == "pairs":
        r = rng.randint(1, n - 3)
        c = rng.randint(0, 2)
        put(g, ch, mirror([(r, c), (r + 2, c + 1)]))
    elif kind == "line":
        put(g, ch, checker(rng.randint(1, n - 2), 0, 1, 8, rng.randint(0, 1)))
    else:
        cells = {(rng.randint(1, n - 2), rng.randint(0, 3)) for _ in range(rng.randint(2, 4))}
        put(g, ch, mirror(sorted(cells)))


def jam_pattern(rng, g):
    n = rows_of(g)
    kind = rng.choice(["rows", "block", "top", "checker", "frame"])
    if kind == "rows":
        r0 = rng.randint(0, n - 3)
        put(g, "j", rows_(g, range(r0, r0 + rng.randint(2, 3))))
    elif kind == "block":
        put(g, "j", block(rng.randint(1, n - 5), rng.randint(0, 2), rng.randint(3, 5), rng.randint(4, 6)))
    elif kind == "top":
        put(g, "j", rows_(g, range(0, rng.randint(2, 4))))
    elif kind == "checker":
        put(g, "j", [(r, c) for r in range(n) for c in range(8) if (r + c) % 2 == 0 and rng.random() < 0.8])
    else:
        put(g, "j", rows_(g, [0, n - 1]) + [(r, c) for r in range(n) for c in (0, 7)])


def mixed_ice_jam(rng, g, thick):
    """Лед и варенье в одной клетке ("k") поверх пятна."""
    jam_pattern(rng, g)
    n = rows_of(g)
    put(g, "k", checker(rng.randint(1, n - 3), 0, 1, 8, rng.randint(0, 1)))
    if thick:
        ice_pattern(rng, g, True)


# MARK: - Сборка

def blank_ok(g):
    cells = ["".join(row) for row in g]
    return not starving(cells)


def collect_goals(rng, colors, k, total):
    items = rng.sample(COLORS6[:colors], k)
    per = max(10, int(round(total / k / 5.0)) * 5)
    return [("collect", it, per) for it in items]


def make_normal(n, rng, hard):
    ch = (n - 1) // PER_CHAPTER + 1
    pos = (n - 1) % PER_CHAPTER + 1
    tier = min(1.0, (ch - 3) / 10)  # 0 в главе 3, 1 к главе 13
    colors = 6 if rng.random() < 0.85 else 5
    layers = 2 if ch < 6 else 3
    thick = ch >= 4 and rng.random() < 0.5 + 0.3 * tier
    recipes = ["collect", "crate", "ice", "jam", "crate+jam", "ice+crate", "jam+ice", "jam_only", "crate_only", "mixed"]
    weights = [3, 3, 3, 3, 2, 2, 2, 1, 1, 1 + 2 * tier]
    if hard:
        weights = [1, 2, 2, 2, 3, 3, 3, 1, 2, 3]
    for attempt in range(80):
        shape = rng.choice(NORMAL_SHAPES)
        recipe = rng.choices(recipes, weights)[0]
        state = {}

        def build(g, recipe=recipe):
            if "crate" in recipe:
                crate_pattern(rng, g, layers if (hard or rng.random() < 0.5) else max(1, layers - 1))
            if "ice" in recipe:
                ice_pattern(rng, g, thick)
            if "jam" in recipe:
                jam_pattern(rng, g)
            if recipe == "mixed":
                crate_pattern(rng, g, layers)
                mixed_ice_jam(rng, g, thick)
            state["g"] = g

        goals = []
        if "crate" in recipe or recipe == "mixed":
            goals.append(("crate",))
        if "ice" in recipe or recipe == "mixed":
            goals.append(("ice",))
        if "jam" in recipe or recipe == "mixed":
            goals.append(("jam",))
        base = 70 + 6 * min(ch, 15) + (25 if hard else 0)
        if recipe == "collect":
            k = rng.choice([2, 2, 3, 3] + ([4] if ch >= 5 else []))
            goals = [c for c in collect_goals(rng, colors, k, base * (1 + 0.35 * (k - 2)))]
        elif not recipe.endswith("_only") and len(goals) < 3:
            goals += collect_goals(rng, colors, 1, base * 0.45)
        try:
            lv = level(n, shape, colors, goals, hard=hard, build=build)
        except AssertionError:
            continue
        g = state["g"]
        if not blank_ok(g):
            continue
        blockers = count(g, "123iIjk")
        open_cells = count(g, ".ijIk")
        if open_cells < 36 or blockers > (34 if hard else 28):
            continue
        if "ice" in recipe and count(g, "iIk") > 14:
            continue
        if any(gl["type"] != "collect" and gl["count"] < (16 if recipe.endswith("_only") else 6) for gl in lv["goals"]):
            continue
        if pos in LUCKY_SLOTS:
            lv["luck"] = 0.15
        return lv
    raise RuntimeError(f"level {n}: no layout")


def make_fever(n, rng):
    ch = (n - 1) // PER_CHAPTER + 1
    shape = rng.choice(FEVER_SHAPES)
    kind = rng.choice(["collect", "collect", "jam", "crate"])
    build = None
    goals = []
    total = 120 + 8 * min(ch, 15)
    if kind == "collect":
        k = rng.choice([2, 3])
        goals = collect_goals(rng, 4, k, total * (1 + 0.4 * (k - 2)))
    elif kind == "jam":
        goals = [("jam",)] + collect_goals(rng, 4, 1, total * 0.5)
        build = lambda g: put(g, "j", [(r, c) for r in range(len(g)) for c in range(8)])  # noqa: E731
    else:
        goals = [("crate",)] + collect_goals(rng, 4, 1, total * 0.5)
        build = lambda g: put(g, "2", bottom_rows(g, 2)) and None  # noqa: E731
    lv = level(n, shape, 4, goals, build=build)
    return fever(lv)


def desired_length(lv):
    """Сколько ходов (медиана бота) должен длиться уровень: generate.py подгоняет под это цели сбора."""
    n = lv["id"]
    if lv.get("fever"):
        return 16
    ch = (n - 1) // PER_CHAPTER + 1
    return min(30, 20 + ch // 2) + (4 if lv["hard"] else 0)


def generated(first, last):
    out = []
    for n in range(first, last + 1):
        rng = random.Random(n * 1009 + 17)
        pos = (n - 1) % PER_CHAPTER + 1
        if pos in FEVER_SLOTS:
            out.append(make_fever(n, rng))
        else:
            out.append(make_normal(n, rng, hard=pos in HARD_SLOTS))
    return out
