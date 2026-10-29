"""Проверка баланса "Рынка" на готовых уровнях: доля побед бота в разных режимах.

python3 tools/match3/balance.py [--runs 30] [--step 1]

Режимы: без бустеров, каждый бустер перед уровнем отдельно, все три, +5 ходов, ступени серии побед.
Печатает таблицу по уровням и средние по группам (обучение, обычные, сложные).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from bot import play  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DATA = os.path.join(ROOT, "Sortelier", "Resources", "Data", "match3.json")

# Ступени серии (как MarketBalance.streak в Market.swift) и вариант с пончиком на 5-й ступени для сравнения.
STREAK = [["W"], ["W", "H"], ["W", "H", "H"], ["W", "H", "B"], ["W", "H", "B", "H"]]
STREAK_RAINBOW = ["H", "W", "B", "H", "R"]

MODES = {
    "free": ([], 0),
    "plus5": ([], 5),
    "pin": (["H"], 0),
    "bomb": (["B"], 0),
    "rainbow": (["R"], 0),
    "pre3": (["H", "B", "R"], 0),
    "pre3+5": (["H", "B", "R"], 5),
    "s1": (STREAK[0], 0),
    "s3": (STREAK[2], 0),
    "s5": (STREAK[4], 0),
    "s5R": (STREAK_RAINBOW, 0),
}


def run(args):
    lv, seed, specials, extra = args
    return play(lv, seed, limit=lv["moves"] + extra, specials=specials)


def pct(values, q):
    values = sorted(values)
    if not values:
        return 0
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--stars", action="store_true", help="переписать пороги звезд по победам без бустеров")
    args = ap.parse_args()
    data = json.load(open(DATA))
    levels = data["levels"][::args.step]
    modes = args.modes.split(",")
    table = []
    with Pool(os.cpu_count() or 2) as pool:
        for lv in levels:
            row = {"id": lv["id"], "hard": lv.get("hard", False), "moves": lv["moves"]}
            for name in modes:
                specials, extra = MODES[name]
                jobs = [(lv, 9000 + s, specials, extra) for s in range(args.runs)]
                res = pool.map(run, jobs)
                row[name] = round(sum(1 for m in res if m is not None) / args.runs, 2)
                if name == "free" and args.stars:
                    # 3 звезды - самые быстрые 30% побед, 2 звезды - следующие 40%
                    left = [lv["moves"] - m for m in res if m is not None]
                    s3 = max(2, int(round(pct(left, 0.7))))
                    s2 = max(1, min(s3 - 1, int(round(pct(left, 0.3)))))
                    lv["stars"] = [s2, s3]
                    row["stars"] = [s2, s3]
            table.append(row)
            print(json.dumps(row), flush=True)

    def avg(rows, key):
        return round(sum(r[key] for r in rows) / max(1, len(rows)), 2) if rows else None
    groups = {
        "intro 1-10": [r for r in table if r["id"] <= 10],
        "normal 11-60": [r for r in table if r["id"] > 10 and not r["hard"]],
        "hard 11-60": [r for r in table if r["id"] > 10 and r["hard"]],
    }
    print()
    print("group".ljust(14) + "".join(m.rjust(8) for m in modes))
    for name, rows in groups.items():
        print(name.ljust(14) + "".join(str(avg(rows, m)).rjust(8) for m in modes))
    json.dump(table, open(os.path.join(os.path.dirname(__file__), "balance_modes.json"), "w"), indent=1)
    if args.stars and args.step == 1:
        with open(DATA, "w") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
