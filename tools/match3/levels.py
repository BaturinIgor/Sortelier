"""60 уровней "Рынка": форма поля, препятствия, цели, обучение.

Ходы и пороги звезд здесь не пишутся: их подбирает generate.py по прогонам бота (см. TARGETS).
Символы клеток - в rules.py. Цвета (продукты) берутся из основной игры.
"""

COLORS6 = ["tomato", "lime", "cheese", "grapes", "milk", "carrot"]

SHAPES = {
    "full": ["........"] * 9,
    "small": ["-......-"] * 7,
    "wide": ["........"] * 7,
    "diamond": ["---..---", "--....--", "-......-", "........", "........", "........", "-......-", "--....--", "---..---"],
    "heart": ["-..--..-", "........", "........", "........", "........", "-......-", "--....--", "---..---"],
    "hourglass": ["........", "-......-", "--....--", "---..---", "---..---", "--....--", "-......-", "........"],
    "ring": ["........", "........", "..----..", "..----..", "..----..", "........", "........", "........"],
    "columns": ["..-..-..", "..-..-..", "........", "........", "........", "..-..-..", "..-..-..", "........", "........"],
    "stairs": [".....---", ".....---", "......--", ".......-", "........", "........", "-.......", "--......", "---....."],
    "plus": ["--....--", "--....--", "........", "........", "........", "........", "--....--", "--....--", "--....--"],
    "twins": ["...--...", "...--...", "...--...", "...--...", "........", "........", "........", "...--...", "...--..."],
    "mushroom": ["-......-", "........", "........", "........", "--....--", "---..---", "---..---", "--....--"],
    "house": ["---..---", "--....--", "-......-", "........", "........", "........", "........", "........", "........"],
    "bowl": ["........", "........", "........", "........", "-......-", "-......-", "--....--", "---..---"],
    "window": ["........", "........", "...--...", "..----..", "...--...", "........", "........", "........", "........"],
    "corners": ["--....--", "-......-", "........", "........", "........", "........", "........", "-......-", "--....--"],
}


def grid(shape):
    return [list(row) for row in SHAPES[shape]]


def put(g, ch, cells):
    for r, c in cells:
        if 0 <= r < len(g) and 0 <= c < len(g[0]) and g[r][c] != "-":
            g[r][c] = ch
    return g


def rows_(g, rows, cols=None):
    cols = range(len(g[0])) if cols is None else cols
    return [(r, c) for r in rows for c in cols]


def block(r0, c0, h, w):
    return [(r, c) for r in range(r0, r0 + h) for c in range(c0, c0 + w)]


def checker(r0, c0, h, w, parity=0):
    """Клетки блока в шахматном порядке: под ними фишки падают по диагонали."""
    return [(r, c) for r in range(r0, r0 + h) for c in range(c0, c0 + w) if (r + c) % 2 == parity]


def mirror(cells, width=8):
    return sorted(set(cells) | {(r, width - 1 - c) for r, c in cells})


def count(g, chars):
    return sum(1 for row in g for ch in row if ch in chars)


def level(n, shape, colors, goals, intro=None, hard=False, build=None):
    g = grid(shape)
    if build:
        build(g)
    cells = ["".join(row) for row in g]
    out_goals = []
    for goal in goals:
        if goal[0] == "collect":
            out_goals.append({"type": "collect", "item": goal[1], "count": goal[2]})
        else:
            chars = {"crate": "123", "ice": "iIk", "jam": "jk"}[goal[0]]
            total = count(g, chars)
            assert total > 0, (n, goal)
            out_goals.append({"type": goal[0], "count": total})
    return {"id": n, "chapter": 1 if n <= 30 else 2, "cells": cells, "colors": COLORS6[:colors],
            "goals": out_goals, "intro": intro, "hard": hard}


def c(item, n):
    return ("collect", item, n)


CRATE = ("crate",)
ICE = ("ice",)
JAM = ("jam",)


LEVELS = [
    # Глава 1: знакомство
    level(1, "small", 5, [c("tomato", 12)], intro="m3.basic"),
    level(2, "small", 5, [c("lime", 18), c("cheese", 18)], intro="m3.pin"),
    level(3, "wide", 5, [c("grapes", 22), c("milk", 22)], intro="m3.whisk"),
    level(4, "wide", 5, [c("tomato", 28), c("cheese", 28)], intro="m3.bomb"),
    level(5, "full", 5, [c("lime", 35), c("grapes", 35)], intro="m3.rainbow"),
    level(6, "full", 5, [c("milk", 40), c("tomato", 40)], intro="m3.combo"),
    level(7, "diamond", 5, [c("cheese", 30), c("lime", 30), c("grapes", 30)]),
    level(8, "full", 5, [CRATE], intro="m3.crate",
          build=lambda g: put(g, "1", rows_(g, [7, 8]))),
    level(9, "heart", 5, [c("tomato", 40), c("milk", 40)]),
    level(10, "full", 5, [CRATE, c("cheese", 30)], hard=True,
           build=lambda g: put(g, "1", rows_(g, [6, 7, 8], range(1, 7)))),
    level(11, "full", 5, [ICE], intro="m3.ice",
          build=lambda g: put(g, "i", checker(3, 2, 3, 4))),
    level(12, "hourglass", 5, [c("lime", 45), c("grapes", 45)]),
    level(13, "full", 5, [CRATE, ICE],
          build=lambda g: (put(g, "1", rows_(g, [8])), put(g, "i", mirror(checker(4, 0, 2, 2))))),
    level(14, "ring", 5, [c("tomato", 40), c("cheese", 40), c("milk", 40)]),
    level(15, "columns", 5, [CRATE], hard=True,
           build=lambda g: put(g, "1", rows_(g, [7, 8]) + block(4, 3, 1, 2))),
    level(16, "full", 5, [JAM], intro="m3.jam",
          build=lambda g: put(g, "j", block(2, 2, 5, 4))),
    level(17, "stairs", 5, [c("grapes", 50), c("lime", 50)]),
    level(18, "plus", 5, [JAM, c("tomato", 35)],
          build=lambda g: put(g, "j", rows_(g, [2, 3, 4, 5]))),
    level(19, "twins", 5, [ICE, c("milk", 35)],
          build=lambda g: put(g, "i", [p for p in checker(2, 0, 4, 8) if p[1] not in (3, 4)])),
    level(20, "full", 5, [CRATE, JAM], hard=True, intro="m3.crate2",
           build=lambda g: (put(g, "j", rows_(g, [3, 4, 5])), put(g, "2", rows_(g, [8], range(2, 6))),
                            put(g, "1", rows_(g, [8], [0, 1, 6, 7]) + rows_(g, [7], range(2, 6))))),
    level(21, "mushroom", 5, [c("cheese", 55), c("tomato", 55)]),
    level(22, "house", 5, [CRATE, c("lime", 40)],
           build=lambda g: put(g, "1", rows_(g, [7, 8], [0, 1, 2, 5, 6, 7]))),
    level(23, "bowl", 5, [JAM],
           build=lambda g: put(g, "j", rows_(g, [4, 5, 6, 7]))),
    level(24, "window", 5, [ICE, CRATE],
           build=lambda g: (put(g, "i", [(1, 3), (1, 4), (5, 3), (5, 4), (3, 1), (3, 6)]), put(g, "2", rows_(g, [8], range(1, 7))))),
    level(25, "corners", 5, [c("grapes", 45), c("milk", 45), c("lime", 45)], hard=True),
    level(26, "diamond", 5, [JAM, ICE],
           build=lambda g: (put(g, "j", rows_(g, [0, 1, 7, 8])), put(g, "i", block(3, 3, 3, 2)))),
    level(27, "hourglass", 5, [CRATE],
           build=lambda g: put(g, "2", [(1, 1), (1, 6), (6, 1), (6, 6)] + rows_(g, [7], range(0, 8)))),
    level(28, "heart", 5, [JAM, c("tomato", 45)],
           build=lambda g: put(g, "j", rows_(g, [1, 2, 3]))),
    level(29, "full", 5, [ICE, JAM],
           build=lambda g: (put(g, "j", rows_(g, [6, 7, 8])), put(g, "i", checker(2, 0, 1, 8)))),
    level(30, "full", 5, [CRATE, ICE, c("cheese", 40)], hard=True,
           build=lambda g: (put(g, "2", rows_(g, [8])), put(g, "1", rows_(g, [7])), put(g, "i", mirror(block(2, 1, 2, 1))))),

    # Глава 2: шесть продуктов, толстый лед, ящики в три слоя
    level(31, "full", 6, [c("carrot", 30), c("tomato", 30)], intro="m3.carrot"),
    level(32, "diamond", 6, [CRATE],
           build=lambda g: put(g, "1", rows_(g, [6, 7, 8]))),
    level(33, "full", 6, [ICE], intro="m3.ice2",
           build=lambda g: put(g, "I", checker(3, 2, 2, 4))),
    level(34, "plus", 6, [JAM, c("carrot", 30)],
           build=lambda g: put(g, "j", rows_(g, [0, 1, 7, 8]))),
    level(35, "ring", 6, [CRATE, JAM], hard=True,
           build=lambda g: (put(g, "j", rows_(g, [0, 1])), put(g, "2", rows_(g, [7])))),
    level(36, "stairs", 6, [c("lime", 40), c("cheese", 40), c("grapes", 40)]),
    level(37, "full", 6, [CRATE], intro="m3.crate3",
           build=lambda g: put(g, "3", rows_(g, [8], range(2, 6))) and put(g, "1", rows_(g, [7]) + [(8, 0), (8, 1), (8, 6), (8, 7)])),
    level(38, "twins", 6, [ICE, JAM],
           build=lambda g: (put(g, "k", checker(5, 0, 1, 8)), put(g, "j", rows_(g, [6], range(0, 8)) + checker(5, 0, 1, 8, 1)))),
    level(39, "mushroom", 6, [JAM],
           build=lambda g: put(g, "j", rows_(g, [0, 1, 2, 3]))),
    level(40, "full", 6, [CRATE, ICE, c("milk", 35)], hard=True,
           build=lambda g: (put(g, "2", rows_(g, [7, 8], [0, 1, 6, 7])), put(g, "3", rows_(g, [8], [3, 4])),
                            put(g, "I", [(3, 3), (3, 4)]))),
    level(41, "corners", 6, [JAM, ICE],
           build=lambda g: (put(g, "j", block(2, 1, 5, 6)), put(g, "i", [(1, 2), (1, 5), (8, 2), (8, 5)]))),
    level(42, "house", 6, [c("carrot", 45), c("milk", 45)]),
    level(43, "bowl", 6, [CRATE],
           build=lambda g: put(g, "2", rows_(g, [5, 6, 7]))),
    level(44, "window", 6, [JAM, c("tomato", 40)],
           build=lambda g: put(g, "j", rows_(g, [0, 1, 7, 8]))),
    level(45, "columns", 6, [ICE, CRATE], hard=True,
           build=lambda g: (put(g, "I", [(3, 2), (3, 5), (5, 2), (5, 5)]), put(g, "1", rows_(g, [8]) + rows_(g, [7], [0, 1, 6, 7])))),
    level(46, "heart", 6, [c("grapes", 45), c("lime", 45)]),
    level(47, "full", 6, [JAM],
           build=lambda g: put(g, "j", [(r, c2) for r in range(9) for c2 in range(8) if (r + c2) % 2 == 0])),
    level(48, "hourglass", 6, [ICE, c("cheese", 40)],
           build=lambda g: put(g, "i", checker(1, 0, 1, 8) + checker(7, 0, 1, 8, 1))),
    level(49, "plus", 6, [CRATE, JAM],
           build=lambda g: (put(g, "3", [(8, 3), (8, 4)]), put(g, "2", [(7, 3), (7, 4), (8, 2), (8, 5)]), put(g, "j", rows_(g, [2, 3])))),
    level(50, "full", 6, [CRATE, ICE, JAM], hard=True,
           build=lambda g: (put(g, "j", rows_(g, [0, 1])), put(g, "I", block(4, 3, 1, 2)), put(g, "i", [(4, 1), (4, 6)]),
                            put(g, "2", rows_(g, [8])))),
    level(51, "diamond", 6, [c("carrot", 50), c("tomato", 50), c("lime", 50)]),
    level(52, "stairs", 6, [CRATE],
           build=lambda g: put(g, "2", rows_(g, [6, 7, 8]))),
    level(53, "twins", 6, [JAM, ICE],
           build=lambda g: (put(g, "j", rows_(g, [4, 5, 6])), put(g, "I", [(1, 0), (1, 7), (8, 0), (8, 7)]))),
    level(54, "ring", 6, [CRATE, c("milk", 40)],
           build=lambda g: put(g, "3", [(7, 0), (7, 7)]) and put(g, "2", rows_(g, [7], range(1, 7)))),
    level(55, "corners", 6, [CRATE, ICE, c("grapes", 40)], hard=True,
           build=lambda g: (put(g, "3", [(8, 3), (8, 4)]), put(g, "2", [(8, 2), (8, 5), (7, 3), (7, 4)]), put(g, "I", [(3, 0), (3, 7), (5, 0), (5, 7)]))),
    level(56, "mushroom", 6, [JAM, c("cheese", 45)],
           build=lambda g: put(g, "j", rows_(g, [0, 1, 2, 3, 4]))),
    level(57, "window", 6, [ICE, CRATE],
           build=lambda g: (put(g, "I", [(2, 2), (2, 5), (4, 2), (4, 5)]), put(g, "2", rows_(g, [7, 8], [0, 1, 6, 7])))),
    level(58, "bowl", 6, [JAM, CRATE],
           build=lambda g: (put(g, "j", rows_(g, [0, 1, 2])), put(g, "2", rows_(g, [7]) + rows_(g, [6], [1, 6])))),
    level(59, "full", 6, [c("tomato", 50), c("lime", 50), c("cheese", 50), c("grapes", 50)]),
    level(60, "full", 6, [CRATE, ICE, JAM, c("carrot", 40)], hard=True,
           build=lambda g: (put(g, "j", rows_(g, [3, 4], range(1, 7))), put(g, "k", [(3, 0), (3, 7)]), put(g, "I", [(1, 3), (1, 4)]),
                            put(g, "3", [(8, 3), (8, 4)]), put(g, "2", [(8, 1), (8, 2), (8, 5), (8, 6)]))),
]

assert [lv["id"] for lv in LEVELS] == list(range(1, 61))

# Целевая доля побед бота без бустеров (бот играет чуть лучше среднего игрока).
def target(lv):
    n = lv["id"]
    if n <= 6:
        return 1.0
    if n <= 15:
        return 0.88 if not lv["hard"] else 0.7
    if n <= 30:
        return 0.64 if not lv["hard"] else 0.45
    return 0.56 if not lv["hard"] else 0.38
