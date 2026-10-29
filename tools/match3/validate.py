"""Проверка форм уровней: в каждую клетку должны падать фишки (сверху или по диагонали) при целых препятствиях.

Лед и ящики не двигаются, поэтому клетка под широким льдом или ящиками остается пустой, пока препятствие не разбито.
Под ящиками у дна это допустимо (ящики там - цель), подо льдом и в середине поля - нет.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from levels import LEVELS  # noqa: E402


def starving(cells):
    rows, cols = len(cells), len(cells[0])
    fill = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            ch = cells[r][c]
            if ch == "-":
                continue
            y = r - 1
            while y >= 0 and cells[y][c] == "-":
                y -= 1
            if y < 0:
                ok = True
            else:
                ok = fill[y][c] and cells[y][c] in ".j"
            for x in (c - 1, c + 1):
                if 0 <= x < cols and r > 0 and cells[r - 1][x] in ".j" and fill[r - 1][x]:
                    ok = True
            fill[r][c] = ok
    return [(r, c) for r in range(rows) for c in range(cols)
            if cells[r][c] in ".jiIk" and not fill[r][c]]


if __name__ == "__main__":
    bad = 0
    for lv in LEVELS:
        s = starving(lv["cells"])
        if s:
            bad += 1
            print(lv["id"], s)
    print("levels with starving cells:", bad)
