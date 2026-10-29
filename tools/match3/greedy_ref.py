"""Тот же жадный бот, что в tools/match3/check/main.swift (без случайности), для сверки движков Python и Swift."""
import json, os, sys, random
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from rules import Board
from bot import score

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "Sortelier", "Resources", "Data", "match3.json")


def greedy(board):
    best, best_v = None, -1
    for m in board.moves_list():
        b = board.clone()
        b.rng = random.Random(1)
        if not b.play(m):
            continue
        v = score(board, b) + (1000 if b.won() else 0)
        if v > best_v:
            best, best_v = m, v
    return best


def run(args):
    lv, seed = args
    b = Board(lv, seed)
    moves = 0
    while moves < 160 and not b.won():
        m = greedy(b)
        if m is None:
            break
        b.play(m)
        moves += 1
    return moves if b.won() else 999


if __name__ == "__main__":
    levels = json.load(open(DATA))["levels"]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    with Pool(os.cpu_count() or 2) as pool:
        for lv in levels:
            used = sorted(pool.map(run, [(lv, 7 + s * 104729) for s in range(n)]))
            print(f"G{lv['id']} moves {lv['moves']} win {sum(1 for u in used if u <= lv['moves'])}/{n} p50 {used[n // 2]}", flush=True)
