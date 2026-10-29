"""Жадный бот для "Рынка": играет уровень, чтобы подобрать число ходов и пороги звезд.

Бот перебирает все засчитываемые ходы, проигрывает каждый на копии поля и берет лучший по прогрессу целей
и созданным спецфишкам. С вероятностью slack берет ход похуже из первой четверки - так он ближе к живому игроку.
"""
from __future__ import annotations

import random

from rules import Board

SPECIAL_VALUE = {"H": 4, "V": 4, "W": 3, "B": 6, "R": 9}


def score(before, after):
    s = 0.0
    for g in before.goal_list:
        need = g["count"] - before.progress(g)
        if need <= 0:
            continue
        gain = min(after.progress(g), g["count"]) - before.progress(g)
        s += gain * (3.0 if g["type"] != "collect" else 1.0)
    for r in range(after.rows):
        for c in range(after.cols):
            t = after.tile[r][c]
            if isinstance(t, str):
                s += SPECIAL_VALUE[t] * 0.6
    return s


def choose(board, rng, slack):
    moves = board.moves_list()
    scored = []
    for m in moves:
        b = board.clone()
        b.rng = random.Random(rng.random())
        if not b.play(m):
            continue
        val = score(board, b)
        if b.won():
            val += 1000
        # тап по спецфишке, когда ее можно было сохранить для комбо, чуть хуже
        scored.append((val + rng.random() * 0.5, m))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None
    if rng.random() < slack and len(scored) > 1:
        return rng.choice(scored[:4])[1]
    return scored[0][1]


def play(level, seed, limit=120, slack=0.25, specials=()):
    """Сколько ходов бот потратил на победу (или None, если не уложился в limit)."""
    board = Board(level, seed, specials)
    rng = random.Random(seed * 7 + 1)
    while board.moves < limit:
        if board.won():
            return board.moves
        m = choose(board, rng, slack)
        if m is None:
            board.shuffle()
            continue
        board.play(m)
    return board.moves if board.won() else None
